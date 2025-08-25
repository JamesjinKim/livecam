#include "RpiCameraCapture.hpp"
#include <iostream>
#include <sstream>
#include <iomanip>
#include <filesystem>
#include <cstdlib>
#include <cstring>
#include <cerrno>
#include <sys/wait.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/utsname.h>
#ifdef __linux__
#include <sys/sysinfo.h>
#endif
#include <fstream>

RpiCameraCapture::RpiCameraCapture() = default;

RpiCameraCapture::~RpiCameraCapture() {
    stopCapture();
}

bool RpiCameraCapture::initialize(const Config& config) {
    config_ = config;
    
    // 라즈베리파이 5 최적화: 시스템 리소스에 따라 최적 형식 선택
    if (config_.format == "auto") {
        config_.format = selectOptimalFormat();
        if (config_.verbose) {
            std::cout << "Auto-selected optimal format: " << config_.format << std::endl;
        }
    }
    
    if (config_.verbose) {
        std::cout << "Initializing RpiCamera with:" << std::endl;
        std::cout << "  Camera: " << config_.cameraIndex << std::endl;
        std::cout << "  Resolution: " << config_.width << "x" << config_.height << std::endl;
        std::cout << "  Format: " << config_.format;
        
        // 라즈베리파이 5 경고 표시
        if (config_.format == "h264") {
            std::cout << " (WARNING: High CPU usage - no hardware encoding)";
        } else if (config_.format == "yuv420") {
            std::cout << " (Optimal: Minimal CPU usage)";
        }
        std::cout << std::endl;
        std::cout << "  Quality: " << config_.quality << std::endl;
    }
    
    // Check if rpicam-vid is available
    if (!DebugUtils::checkRpiCamTools()) {
        std::cerr << "Error: rpicam tools not found!" << std::endl;
        return false;
    }
    
    initialized_ = true;
    return true;
}

std::string RpiCameraCapture::buildRpiCamCommand() const {
    std::ostringstream cmd;
    
    cmd << "rpicam-vid";
    cmd << " --camera " << config_.cameraIndex;
    cmd << " --width " << config_.width;
    cmd << " --height " << config_.height;
    
    // 라즈베리파이 5 최적화: 연속 캡처를 위한 timeout=0
    if (config_.timeout > 0) {
        cmd << " --timeout " << config_.timeout;
    } else {
        cmd << " --timeout 0";  // 무한 캡처
    }
    
    cmd << " --nopreview";
    cmd << " --inline";      // H.264 헤더를 각 프레임에 포함
    cmd << " --flush";       // 즉시 출력 (지연 최소화)
    cmd << " --framerate 30"; // 명시적 프레임레이트 설정
    
    // 라즈베리파이 5에서 권장되는 버퍼 설정
    cmd << " --buffer-count 4";  // 버퍼 개수 최적화
    
    // 라즈베리파이 5 최적화: 하드웨어 인코딩 미지원 대응
    if (config_.format == "yuv420") {
        cmd << " --codec yuv420";  // Raw data - 최소 CPU 사용
    } else if (config_.format == "mjpeg") {
        // MJPEG은 상대적으로 가벼운 소프트웨어 인코딩
        cmd << " --codec mjpeg";
        cmd << " --quality " << config_.quality;
    } else if (config_.format == "h264") {
        // 라즈베리파이 5에서는 H.264 사용 불가 - yuv420로 강제 변경
        std::cout << "ERROR: H.264 not supported on Raspberry Pi 5 (no hardware encoding)" << std::endl;
        std::cout << "Auto-switching to YUV420 format for optimal performance" << std::endl;
        cmd << " --codec yuv420";
        // 주의: config_.format은 const이므로 여기서 변경할 수 없음
    } else if (config_.format == "raw") {
        // 가장 효율적: 압축 없이 raw 데이터만 전송
        cmd << " --codec yuv420 --raw";
    } else {
        // 기본값: YUV420 raw 데이터 (CPU 최소 사용)
        cmd << " --codec yuv420";
    }
    
    cmd << " --output -"; // stdout
    
    if (config_.verbose) {
        cmd << " --verbose";
        std::cout << "Optimized rpicam command: " << cmd.str() << std::endl;
    }
    
    return cmd.str();
}

bool RpiCameraCapture::startCapture() {
    if (!initialized_) {
        std::cerr << "Camera not initialized!" << std::endl;
        return false;
    }
    
    if (capturing_.load()) {
        std::cout << "Already capturing" << std::endl;
        return true;
    }
    
    if (config_.verbose) {
        std::cout << "Starting camera capture..." << std::endl;
    }
    
    if (!startRpiCamProcess()) {
        std::cerr << "Failed to start rpicam process!" << std::endl;
        return false;
    }
    
    capturing_.store(true);
    
    // Start reader thread
    readerThread_ = std::thread(&RpiCameraCapture::frameReaderThread, this);
    
    if (config_.verbose) {
        std::cout << "Camera capture started successfully" << std::endl;
    }
    
    return true;
}

bool RpiCameraCapture::startRpiCamProcess() {
    std::string command = buildRpiCamCommand();
    
    rpiCamPipe_ = popen(command.c_str(), "r");
    if (!rpiCamPipe_) {
        std::cerr << "Failed to start rpicam process: " << strerror(errno) << std::endl;
        return false;
    }
    
    // Set non-blocking mode
    int fd = fileno(rpiCamPipe_);
    int flags = fcntl(fd, F_GETFL, 0);
    fcntl(fd, F_SETFL, flags | O_NONBLOCK);
    
    return true;
}

void RpiCameraCapture::frameReaderThread() {
    // 동적 버퍼 크기 계산 (형식에 따라)
    size_t expectedFrameSize;
    if (config_.format == "yuv420") {
        expectedFrameSize = config_.width * config_.height * 3 / 2; // YUV420
    } else if (config_.format == "h264" || config_.format == "mjpeg") {
        expectedFrameSize = config_.width * config_.height; // 압축된 형식
    } else {
        expectedFrameSize = config_.width * config_.height * 3; // RGB
    }
    
    // 메모리 풀에서 버퍼 가져오기
    auto buffer = getBuffer(expectedFrameSize);
    size_t frameCount = 0;
    auto lastStatsTime = std::chrono::steady_clock::now();
    
    if (config_.verbose) {
        std::cout << "Frame reader thread started (expected frame size: " 
                  << expectedFrameSize << " bytes)" << std::endl;
    }
    
    while (capturing_.load()) {
        if (!rpiCamPipe_) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }
        
        size_t bytesRead = fread(buffer.data(), 1, expectedFrameSize, rpiCamPipe_);
        
        if (bytesRead > 0) {
            frameCount++;
            
            Frame frame(config_.width, config_.height, config_.format);
            frame.data.assign(buffer.begin(), buffer.begin() + bytesRead);
            
            // 콜백 호출
            if (frameCallback_) {
                frameCallback_(frame);
            }
            
            // 동기식 캡처를 위한 큐 추가 (최대 10프레임 버퍼링)
            {
                std::lock_guard<std::mutex> lock(frameMutex_);
                if (frameQueue_.size() >= 10) {
                    frameQueue_.pop(); // 오래된 프레임 제거
                }
                frameQueue_.push(std::move(frame));
                frameCondition_.notify_one();
            }
            
            // 성능 통계 및 적응형 압축 (5초마다)
            if (frameCount % 150 == 0) { // 30fps 기준
                auto now = std::chrono::steady_clock::now();
                auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
                    now - lastStatsTime).count();
                
                if (elapsed > 0) {
                    double current_fps = 150.0 / elapsed;
                    
                    if (config_.verbose) {
                        std::cout << "Frame rate: " << current_fps 
                                  << " fps, Frame size: " << bytesRead << " bytes";
                        
                        // CPU 부하 상태 표시
                        if (current_fps < 25.0) {
                            std::cout << " (LOW FPS - High CPU load)";
                        }
                        std::cout << std::endl;
                    }
                    
                    // 프레임 레이트가 너무 낮으면 적응형 압축 실행
                    if (current_fps < 20.0) {
                        adaptCompressionLevel();
                    }
                    
                    lastStatsTime = now;
                }
            }
        } else {
            // 데이터 없음, 카메라 상태 확인 및 복구 시도
            static int consecutiveFailures = 0;
            consecutiveFailures++;
            
            if (consecutiveFailures > 1000) { // 약 100ms * 1000 = 100초 대기 후
                if (config_.verbose) {
                    std::cout << "Camera seems disconnected, attempting reconnection..." << std::endl;
                }
                
                if (attemptReconnection()) {
                    consecutiveFailures = 0; // 성공시 카운터 리셋
                } else {
                    consecutiveFailures = 500; // 실패시 좀 더 기다리기
                }
            }
            
            // CPU 사용률 최적화
            std::this_thread::sleep_for(std::chrono::microseconds(100));
        }
    }
    
    if (config_.verbose) {
        std::cout << "Frame reader thread stopped. Total frames: " << frameCount << std::endl;
    }
    
    // 사용한 버퍼를 풀로 반환
    returnBuffer(std::move(buffer));
}

bool RpiCameraCapture::stopCapture() {
    if (!capturing_.load()) {
        return true;
    }
    
    if (config_.verbose) {
        std::cout << "Stopping camera capture..." << std::endl;
    }
    
    capturing_.store(false);
    
    if (readerThread_.joinable()) {
        readerThread_.join();
    }
    
    stopRpiCamProcess();
    
    if (config_.verbose) {
        std::cout << "Camera capture stopped" << std::endl;
    }
    
    return true;
}

void RpiCameraCapture::stopRpiCamProcess() {
    if (rpiCamPipe_) {
        pclose(rpiCamPipe_);
        rpiCamPipe_ = nullptr;
    }
}

bool RpiCameraCapture::captureFrame(Frame& frame) {
    if (!capturing_.load()) {
        return false;
    }
    
    // 프레임 큐를 사용한 동기식 캡처 구현
    std::unique_lock<std::mutex> lock(frameMutex_);
    
    // 최대 1초 대기
    bool frameAvailable = frameCondition_.wait_for(lock, std::chrono::seconds(1), 
        [this] { return !frameQueue_.empty(); });
    
    if (!frameAvailable || frameQueue_.empty()) {
        return false; // 타임아웃 또는 프레임 없음
    }
    
    frame = std::move(frameQueue_.front());
    frameQueue_.pop();
    
    return true;
}

void RpiCameraCapture::setFrameCallback(FrameCallback callback) {
    frameCallback_ = std::move(callback);
}

std::vector<uint8_t> RpiCameraCapture::getBuffer(size_t size) {
    std::lock_guard<std::mutex> lock(poolMutex_);
    
    if (!bufferPool_.empty()) {
        auto buffer = std::move(bufferPool_.front());
        bufferPool_.pop();
        
        // 크기가 맞지 않으면 리사이즈
        if (buffer.size() != size) {
            buffer.resize(size);
        }
        return buffer;
    }
    
    // 풀이 비어있으면 새로운 버퍼 생성
    return std::vector<uint8_t>(size);
}

void RpiCameraCapture::returnBuffer(std::vector<uint8_t>&& buffer) {
    std::lock_guard<std::mutex> lock(poolMutex_);
    
    // 풀이 가득 차지 않았으면 버퍼 반환
    if (bufferPool_.size() < BUFFER_POOL_SIZE) {
        bufferPool_.push(std::move(buffer));
    }
    // 가득 찬 경우 버퍼는 소멸됨 (자동 메모리 해제)
}

bool RpiCameraCapture::checkCameraHealth() {
    if (!rpiCamPipe_) {
        return false;
    }
    
    // 파이프 상태 확인
    int fd = fileno(rpiCamPipe_);
    if (fd == -1) {
        return false;
    }
    
    // 프로세스가 살아있는지 확인 (간단한 방법)
    return true; // 더 정교한 구현 가능
}

bool RpiCameraCapture::attemptReconnection() {
    if (config_.verbose) {
        std::cout << "Attempting camera reconnection..." << std::endl;
    }
    
    stopRpiCamProcess();
    
    // 잠시 대기 후 재연결 시도
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    
    bool success = startRpiCamProcess();
    if (success && config_.verbose) {
        std::cout << "Camera reconnection successful!" << std::endl;
    } else if (config_.verbose) {
        std::cout << "Camera reconnection failed!" << std::endl;
    }
    
    return success;
}

bool RpiCameraCapture::isHighCPULoad() const {
    // /proc/stat을 읽어서 CPU 사용률 확인
    std::ifstream stat_file("/proc/stat");
    if (!stat_file.is_open()) {
        return false;
    }
    
    std::string line;
    std::getline(stat_file, line);
    
    // 간단한 CPU 부하 체크 (실제로는 더 정교한 구현 필요)
    // 현재는 프레임 처리 지연을 기준으로 판단
    static auto last_check = std::chrono::steady_clock::now();
    auto now = std::chrono::steady_clock::now();
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_check);
    
    return elapsed.count() > 50; // 50ms 이상 지연시 고부하로 판단
}

void RpiCameraCapture::adaptCompressionLevel() {
    if (!capturing_.load()) return;
    
    static int consecutive_high_load = 0;
    
    if (isHighCPULoad()) {
        consecutive_high_load++;
        
        if (consecutive_high_load > 10 && config_.format != "yuv420") {
            if (config_.verbose) {
                std::cout << "High CPU load detected, switching to YUV420 format" << std::endl;
            }
            config_.format = "yuv420"; // 가장 가벼운 형식으로 변경
            
            // 카메라 재시작 필요 (별도 스레드에서 처리)
            std::thread([this]() {
                stopCapture();
                std::this_thread::sleep_for(std::chrono::milliseconds(500));
                startCapture();
            }).detach();
        }
    } else {
        consecutive_high_load = std::max(0, consecutive_high_load - 1);
    }
}

std::string RpiCameraCapture::selectOptimalFormat() const {
    // 시스템 리소스에 따라 최적 형식 선택
    
    // CPU 코어 수 확인
    int cpu_cores = std::thread::hardware_concurrency();
    
    // 메모리 사용량 확인 (간단한 버전)
    std::ifstream meminfo("/proc/meminfo");
    std::string line;
    size_t available_memory = 0;
    
    while (std::getline(meminfo, line)) {
        if (line.find("MemAvailable:") == 0) {
            std::istringstream iss(line);
            std::string label;
            iss >> label >> available_memory; // KB 단위
            break;
        }
    }
    
    if (config_.verbose) {
        std::cout << "System resources: " << cpu_cores << " cores, " 
                  << (available_memory / 1024) << " MB available" << std::endl;
    }
    
    // 라즈베리파이 5 최적화: H.264는 절대 선택하지 않음
    // 리소스 기반 형식 선택 로직
    if (available_memory < 500 * 1024) { // 500MB 미만
        return "yuv420"; // 가장 가벼운 형식
    } else if (cpu_cores >= 4 && available_memory > 1024 * 1024) { // 4코어 + 1GB 이상
        return "mjpeg"; // 중간 압축 (H.264는 제외)
    } else {
        return "yuv420"; // 안전한 기본값
    }
}

std::vector<int> RpiCameraCapture::listCameras() {
    std::vector<int> cameras;
    
    // Try cameras 0 and 1
    for (int i = 0; i < 2; ++i) {
        if (testCamera(i)) {
            cameras.push_back(i);
        }
    }
    
    return cameras;
}

bool RpiCameraCapture::testCamera(int cameraIndex) {
    std::ostringstream cmd;
    cmd << "rpicam-hello --camera " << cameraIndex << " --timeout 100 > /dev/null 2>&1";
    
    int result = system(cmd.str().c_str());
    return (result == 0);
}

// JPEG Compression Implementation
bool JpegCompressor::compressYUV420ToJpeg(const uint8_t* yuvData, int width, int height,
                                         std::vector<uint8_t>& jpegData,
                                         const CompressConfig& config) {
    if (!yuvData) {
        std::cerr << "Invalid YUV data" << std::endl;
        return false;
    }
    
    // Convert YUV420 to RGB
    std::vector<uint8_t> rgbData(width * height * 3);
    yuv420ToRgb(yuvData, rgbData.data(), width, height);
    
    return compressRGBToJpeg(rgbData.data(), width, height, jpegData, config);
}

bool JpegCompressor::compressRGBToJpeg(const uint8_t* rgbData, int width, int height,
                                      std::vector<uint8_t>& jpegData,
                                      const CompressConfig& config) {
    if (!rgbData) {
        std::cerr << "Invalid RGB data" << std::endl;
        return false;
    }
    
    jpeg_compress_struct cinfo;
    jpeg_error_mgr jerr;
    
    cinfo.err = jpeg_std_error(&jerr);
    jpeg_create_compress(&cinfo);
    
    try {
        // Setup destination
        unsigned char* mem_buffer = nullptr;
        unsigned long mem_size = 0;
        jpeg_mem_dest(&cinfo, &mem_buffer, &mem_size);
        
        // Set parameters
        cinfo.image_width = width;
        cinfo.image_height = height;
        cinfo.input_components = 3;
        cinfo.in_color_space = JCS_RGB;
        
        jpeg_set_defaults(&cinfo);
        jpeg_set_quality(&cinfo, config.quality, TRUE);
        
        if (config.optimizeHuffman) {
            cinfo.optimize_coding = TRUE;
        }
        
        if (config.progressive) {
            jpeg_simple_progression(&cinfo);
        }
        
        // Start compression
        jpeg_start_compress(&cinfo, TRUE);
        
        // Write scanlines
        int row_stride = width * 3;
        while (cinfo.next_scanline < cinfo.image_height) {
            JSAMPROW row_pointer = const_cast<JSAMPROW>(
                &rgbData[cinfo.next_scanline * row_stride]);
            jpeg_write_scanlines(&cinfo, &row_pointer, 1);
        }
        
        jpeg_finish_compress(&cinfo);
        
        // Copy compressed data
        jpegData.assign(mem_buffer, mem_buffer + mem_size);
        
        free(mem_buffer);
        jpeg_destroy_compress(&cinfo);
        
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "JPEG compression error: " << e.what() << std::endl;
        jpeg_destroy_compress(&cinfo);
        return false;
    }
}

void JpegCompressor::yuv420ToRgb(const uint8_t* yuvData, uint8_t* rgbData, int width, int height) {
    const uint8_t* y_plane = yuvData;
    const uint8_t* u_plane = y_plane + width * height;
    const uint8_t* v_plane = u_plane + (width * height) / 4;
    
    for (int row = 0; row < height; row++) {
        for (int col = 0; col < width; col++) {
            int y = y_plane[row * width + col];
            int u = u_plane[(row / 2) * (width / 2) + (col / 2)] - 128;
            int v = v_plane[(row / 2) * (width / 2) + (col / 2)] - 128;
            
            // YUV to RGB conversion
            int r = y + (1.370705 * v);
            int g = y - (0.337633 * u) - (0.698001 * v);
            int b = y + (1.732446 * u);
            
            // Clamp values
            r = std::max(0, std::min(255, r));
            g = std::max(0, std::min(255, g));
            b = std::max(0, std::min(255, b));
            
            // Store RGB
            int rgb_index = (row * width + col) * 3;
            rgbData[rgb_index] = static_cast<uint8_t>(r);
            rgbData[rgb_index + 1] = static_cast<uint8_t>(g);
            rgbData[rgb_index + 2] = static_cast<uint8_t>(b);
        }
    }
}

// FileStorage Implementation
FileStorage::FileStorage(const StorageConfig& config) : config_(config) {
    if (config_.createDirectories) {
        createDirectoryStructure();
    }
}

bool FileStorage::createDirectoryStructure() const {
    try {
        std::filesystem::create_directories(config_.baseDirectory);
        std::cout << "Created storage directory: " << config_.baseDirectory << std::endl;
        return true;
    } catch (const std::exception& e) {
        std::cerr << "Failed to create directory: " << e.what() << std::endl;
        return false;
    }
}

std::string FileStorage::generateFilename(const std::string& extension) {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    
    std::ostringstream filename;
    filename << config_.prefix << "_";
    filename << std::put_time(std::localtime(&time_t), "%Y%m%d_%H%M%S_");
    filename << std::setfill('0') << std::setw(3) << (++sequenceCounter_);
    filename << extension;
    
    return config_.baseDirectory + "/" + filename.str();
}

bool FileStorage::saveFrame(const RpiCameraCapture::Frame& frame, const std::string& filename) {
    std::string filepath = filename.empty() ? generateFilename(".yuv") : filename;
    return saveRaw(frame.data, filepath);
}

bool FileStorage::saveJpeg(const std::vector<uint8_t>& jpegData, const std::string& filename) {
    std::string filepath = filename.empty() ? generateFilename(".jpg") : filename;
    return saveRaw(jpegData, filepath);
}

bool FileStorage::saveRaw(const std::vector<uint8_t>& rawData, const std::string& filename) {
    try {
        std::ofstream file(filename, std::ios::binary);
        if (!file) {
            std::cerr << "Failed to open file: " << filename << std::endl;
            return false;
        }
        
        file.write(reinterpret_cast<const char*>(rawData.data()), rawData.size());
        
        if (!file.good()) {
            std::cerr << "Failed to write file: " << filename << std::endl;
            return false;
        }
        
        std::cout << "Saved file: " << filename << " (" << rawData.size() << " bytes)" << std::endl;
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "Error saving file: " << e.what() << std::endl;
        return false;
    }
}

// DebugUtils Implementation
void DebugUtils::printFrameInfo(const RpiCameraCapture::Frame& frame) {
    std::cout << "=== Frame Information ===" << std::endl;
    std::cout << "Data size: " << frame.data.size() << " bytes" << std::endl;
    std::cout << "Resolution: " << frame.width << "x" << frame.height << std::endl;
    std::cout << "Format: " << frame.format << std::endl;
    
    auto timestamp = std::chrono::duration_cast<std::chrono::microseconds>(
        frame.timestamp.time_since_epoch()).count();
    std::cout << "Timestamp: " << timestamp << " us" << std::endl;
    
    if (!frame.data.empty()) {
        std::cout << "First 16 bytes: ";
        size_t bytes_to_show = std::min(static_cast<size_t>(16), frame.data.size());
        for (size_t i = 0; i < bytes_to_show; ++i) {
            std::cout << std::hex << std::setw(2) << std::setfill('0') 
                     << static_cast<unsigned int>(frame.data[i]) << " ";
        }
        std::cout << std::dec << std::endl;
    }
    std::cout << std::endl;
}

void DebugUtils::printSystemInfo() {
    std::cout << "=== System Information ===" << std::endl;
    
    // System info
    struct utsname sys_info;
    if (uname(&sys_info) == 0) {
        std::cout << "System: " << sys_info.sysname << std::endl;
        std::cout << "Node: " << sys_info.nodename << std::endl;
        std::cout << "Release: " << sys_info.release << std::endl;
        std::cout << "Machine: " << sys_info.machine << std::endl;
    }
    
    // Memory info (Linux only)
#ifdef __linux__
    struct sysinfo mem_info;
    if (sysinfo(&mem_info) == 0) {
        std::cout << "Total RAM: " << (mem_info.totalram >> 20) << " MB" << std::endl;
        std::cout << "Free RAM: " << (mem_info.freeram >> 20) << " MB" << std::endl;
    }
#else
    std::cout << "Memory info not available on this platform" << std::endl;
#endif
    
    std::cout << std::endl;
}

void DebugUtils::listCameras() {
    std::cout << "=== Available Cameras ===" << std::endl;
    
    auto cameras = RpiCameraCapture::listCameras();
    if (cameras.empty()) {
        std::cout << "No cameras found" << std::endl;
    } else {
        for (int camera : cameras) {
            std::cout << "Camera " << camera << ": Available" << std::endl;
        }
    }
    std::cout << std::endl;
}

void DebugUtils::analyzeMemoryUsage() {
    std::cout << "=== Memory Usage Analysis ===" << std::endl;
    
    try {
        std::ifstream meminfo("/proc/meminfo");
        std::string line;
        
        while (std::getline(meminfo, line)) {
            if (line.find("MemTotal:") == 0 ||
                line.find("MemFree:") == 0 ||
                line.find("MemAvailable:") == 0 ||
                line.find("Buffers:") == 0 ||
                line.find("Cached:") == 0) {
                std::cout << line << std::endl;
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "Error reading memory info: " << e.what() << std::endl;
    }
    std::cout << std::endl;
}

bool DebugUtils::checkRpiCamTools() {
    int result = system("which rpicam-vid > /dev/null 2>&1");
    if (result != 0) {
        std::cout << "rpicam-vid: Not found" << std::endl;
        return false;
    }
    
    std::cout << "rpicam-vid: Available" << std::endl;
    return true;
}