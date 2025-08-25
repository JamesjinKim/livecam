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
#include <sys/sysinfo.h>
#include <fstream>

RpiCameraCapture::RpiCameraCapture() = default;

RpiCameraCapture::~RpiCameraCapture() {
    stopCapture();
}

bool RpiCameraCapture::initialize(const Config& config) {
    config_ = config;
    
    if (config_.verbose) {
        std::cout << "Initializing RpiCamera with:" << std::endl;
        std::cout << "  Camera: " << config_.cameraIndex << std::endl;
        std::cout << "  Resolution: " << config_.width << "x" << config_.height << std::endl;
        std::cout << "  Format: " << config_.format << std::endl;
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
    cmd << " --timeout " << config_.timeout;
    cmd << " --nopreview";
    cmd << " --inline";
    
    if (config_.format == "yuv420") {
        cmd << " --codec yuv420";
    } else if (config_.format == "mjpeg") {
        cmd << " --codec mjpeg";
        cmd << " --quality " << config_.quality;
    } else {
        cmd << " --codec yuv420"; // default
    }
    
    cmd << " --output -"; // stdout
    
    if (config_.verbose) {
        std::cout << "rpicam command: " << cmd.str() << std::endl;
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
    const size_t expectedFrameSize = config_.width * config_.height * 3 / 2; // YUV420
    std::vector<uint8_t> buffer(expectedFrameSize);
    
    while (capturing_.load()) {
        if (!rpiCamPipe_) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }
        
        size_t bytesRead = fread(buffer.data(), 1, expectedFrameSize, rpiCamPipe_);
        
        if (bytesRead > 0) {
            Frame frame(config_.width, config_.height, config_.format);
            frame.data.assign(buffer.begin(), buffer.begin() + bytesRead);
            
            if (frameCallback_) {
                frameCallback_(frame);
            }
        } else {
            // No data available, sleep briefly
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    }
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

bool RpiCameraCapture::captureFrame(Frame& /* frame */) {
    if (!capturing_.load()) {
        return false;
    }
    
    // This is a simplified version - in real implementation,
    // you'd want a queue system for thread-safe frame access
    return false; // Use callback instead for now
}

void RpiCameraCapture::setFrameCallback(FrameCallback callback) {
    frameCallback_ = std::move(callback);
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
    
    // Memory info
    struct sysinfo mem_info;
    if (sysinfo(&mem_info) == 0) {
        std::cout << "Total RAM: " << (mem_info.totalram >> 20) << " MB" << std::endl;
        std::cout << "Free RAM: " << (mem_info.freeram >> 20) << " MB" << std::endl;
    }
    
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