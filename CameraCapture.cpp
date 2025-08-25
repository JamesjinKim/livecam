#include "CameraCapture.hpp"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <filesystem>
#include <sys/mman.h>
#include <jpeglib.h>
#include <cstring>

using namespace libcamera;

CameraCapture::CameraCapture() = default;

CameraCapture::~CameraCapture() {
    cleanup();
}

bool CameraCapture::initialize(const CameraConfig& config) {
    config_ = config;
    
    std::cout << "Initializing libcamera..." << std::endl;
    
    try {
        // Initialize camera manager
        cameraManager_ = std::make_unique<CameraManager>();
        int ret = cameraManager_->start();
        if (ret) {
            std::cerr << "Failed to start camera manager: " << ret << std::endl;
            return false;
        }
        
        // Get available cameras
        auto cameras = cameraManager_->cameras();
        if (cameras.empty()) {
            std::cerr << "No cameras found" << std::endl;
            return false;
        }
        
        if (config_.cameraIndex >= static_cast<int>(cameras.size())) {
            std::cerr << "Camera index " << config_.cameraIndex 
                      << " out of range (0-" << (cameras.size() - 1) << ")" << std::endl;
            return false;
        }
        
        camera_ = cameras[config_.cameraIndex];
        std::cout << "Selected camera: " << camera_->id() << std::endl;
        
        // Acquire camera
        ret = camera_->acquire();
        if (ret) {
            std::cerr << "Failed to acquire camera: " << ret << std::endl;
            return false;
        }
        
        // Generate camera configuration
        cameraConfig_ = camera_->generateConfiguration({StreamRole::Viewfinder});
        if (!cameraConfig_) {
            std::cerr << "Failed to generate camera configuration" << std::endl;
            return false;
        }
        
        // Configure stream
        StreamConfiguration& streamConfig = cameraConfig_->at(0);
        
        // Set resolution
        streamConfig.size.width = config_.width;
        streamConfig.size.height = config_.height;
        
        // Set pixel format - prefer YUV420 for better performance
        streamConfig.pixelFormat = formats::YUV420;
        
        std::cout << "Requested format: " << streamConfig.pixelFormat.toString() 
                  << " " << streamConfig.size.toString() << std::endl;
        
        // Validate configuration
        CameraConfiguration::Status status = cameraConfig_->validate();
        if (status == CameraConfiguration::Invalid) {
            std::cerr << "Invalid camera configuration" << std::endl;
            return false;
        }
        
        if (status == CameraConfiguration::Adjusted) {
            std::cout << "Camera configuration adjusted to: " 
                      << streamConfig.pixelFormat.toString() 
                      << " " << streamConfig.size.toString() << std::endl;
        }
        
        // Update config with actual values
        config_.width = streamConfig.size.width;
        config_.height = streamConfig.size.height;
        config_.format = streamConfig.pixelFormat;
        
        // Configure camera
        ret = camera_->configure(cameraConfig_.get());
        if (ret) {
            std::cerr << "Failed to configure camera: " << ret << std::endl;
            return false;
        }
        
        // Setup buffers
        setupBuffers();
        
        initialized_ = true;
        std::cout << "Camera initialized successfully" << std::endl;
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "Exception during camera initialization: " << e.what() << std::endl;
        return false;
    }
}

void CameraCapture::setupBuffers() {
    // Allocate framebuffers
    Stream* stream = cameraConfig_->at(0).stream();
    
    for (unsigned int i = 0; i < config_.bufferCount; ++i) {
        auto request = camera_->createRequest();
        if (!request) {
            std::cerr << "Failed to create request" << std::endl;
            continue;
        }
        
        auto buffer = createBuffer(stream);
        if (!buffer) {
            std::cerr << "Failed to create buffer " << i << std::endl;
            continue;
        }
        
        int ret = request->addBuffer(stream, buffer);
        if (ret) {
            std::cerr << "Failed to add buffer to request: " << ret << std::endl;
            continue;
        }
        
        requests_.push_back(std::move(request));
    }
    
    std::cout << "Created " << requests_.size() << " request buffers" << std::endl;
}

FrameBuffer* CameraCapture::createBuffer(const Stream* stream) {
    const StreamConfiguration& config = stream->configuration();
    
    // Create memory mapped buffer  
    std::vector<uint8_t> bufferData(config.frameSize);
    
    // Create FrameBuffer plane
    std::vector<FrameBuffer::Plane> planes;
    FrameBuffer::Plane plane;
    plane.fd = -1;
    plane.offset = 0;
    plane.length = config.frameSize;
    planes.push_back(plane);
    
    auto buffer = std::make_unique<FrameBuffer>(std::move(planes));
    
    FrameBuffer* bufferPtr = buffer.release();
    bufferMap_[bufferPtr] = std::move(bufferData);
    
    return bufferPtr;
}

bool CameraCapture::startCapture() {
    if (!initialized_) {
        std::cerr << "Camera not initialized" << std::endl;
        return false;
    }
    
    if (capturing_) {
        std::cout << "Camera already capturing" << std::endl;
        return true;
    }
    
    std::cout << "Starting camera capture..." << std::endl;
    
    // Set up request completed callback
    camera_->requestCompleted.connect(this, &CameraCapture::onRequestCompleted);
    
    // Start camera
    int ret = camera_->start();
    if (ret) {
        std::cerr << "Failed to start camera: " << ret << std::endl;
        return false;
    }
    
    // Queue initial requests
    for (auto& request : requests_) {
        ret = camera_->queueRequest(request.get());
        if (ret) {
            std::cerr << "Failed to queue request: " << ret << std::endl;
            return false;
        }
    }
    
    capturing_ = true;
    std::cout << "Camera capture started successfully" << std::endl;
    return true;
}

bool CameraCapture::stopCapture() {
    if (!capturing_) {
        return true;
    }
    
    std::cout << "Stopping camera capture..." << std::endl;
    
    int ret = camera_->stop();
    if (ret) {
        std::cerr << "Failed to stop camera: " << ret << std::endl;
        return false;
    }
    
    capturing_ = false;
    std::cout << "Camera capture stopped" << std::endl;
    return true;
}

void CameraCapture::cleanup() {
    if (capturing_) {
        stopCapture();
    }
    
    if (camera_) {
        camera_->release();
        camera_.reset();
    }
    
    if (cameraManager_) {
        cameraManager_->stop();
        cameraManager_.reset();
    }
    
    requests_.clear();
    bufferMap_.clear();
    
    initialized_ = false;
    std::cout << "Camera cleanup completed" << std::endl;
}

void CameraCapture::onRequestCompleted(Request* request) {
    if (request->status() == Request::RequestComplete) {
        // Process completed request
        const Request::BufferMap& buffers = request->buffers();
        
        for (auto& [stream, buffer] : buffers) {
            // Create frame from buffer data
            Frame frame;
            frame.width = config_.width;
            frame.height = config_.height;
            frame.format = config_.format;
            frame.timestamp = std::chrono::steady_clock::now();
            
            // Copy buffer data
            auto it = bufferMap_.find(buffer);
            if (it != bufferMap_.end()) {
                frame.data = it->second;
                
                // Call frame callback if set
                if (frameCallback_) {
                    frameCallback_(frame);
                }
                
                // Add to frame queue
                {
                    std::lock_guard<std::mutex> lock(frameMutex_);
                    frameQueue_.push(std::move(frame));
                    frameCondition_.notify_one();
                }
            }
        }
    }
    
    // Requeue request
    if (capturing_) {
        camera_->queueRequest(request);
    }
}

bool CameraCapture::captureFrame(Frame& frame) {
    if (!capturing_) {
        return false;
    }
    
    std::unique_lock<std::mutex> lock(frameMutex_);
    if (!frameCondition_.wait_for(lock, std::chrono::milliseconds(1000), 
                                  [this] { return !frameQueue_.empty(); })) {
        return false; // Timeout
    }
    
    frame = std::move(frameQueue_.front());
    frameQueue_.pop();
    return true;
}

void CameraCapture::setFrameCallback(FrameCallback callback) {
    frameCallback_ = std::move(callback);
}

std::vector<std::string> CameraCapture::listCameras() {
    std::vector<std::string> cameraList;
    
    try {
        CameraManager manager;
        manager.start();
        
        for (const auto& camera : manager.cameras()) {
            cameraList.push_back(camera->id());
        }
        
        manager.stop();
    } catch (const std::exception& e) {
        std::cerr << "Error listing cameras: " << e.what() << std::endl;
    }
    
    return cameraList;
}

std::string CameraCapture::formatToString(uint32_t format) {
    PixelFormat pixelFormat(format);
    return pixelFormat.toString();
}

std::string CameraCapture::getCameraInfo() const {
    if (!initialized_) {
        return "Camera not initialized";
    }
    
    std::ostringstream info;
    info << "=== Camera Information ===" << std::endl;
    info << "Camera ID: " << camera_->id() << std::endl;
    info << "Resolution: " << config_.width << "x" << config_.height << std::endl;
    info << "Format: " << formatToString(config_.format) << std::endl;
    info << "Buffer count: " << config_.bufferCount << std::endl;
    info << "Capturing: " << (capturing_ ? "Yes" : "No") << std::endl;
    
    return info.str();
}

// JPEG Compression implementation
bool JpegCompressor::compressYUV420(const uint8_t* yuvData, int width, int height,
                                    std::vector<uint8_t>& jpegData,
                                    const CompressConfig& config) {
    if (!yuvData) {
        std::cerr << "Invalid YUV data" << std::endl;
        return false;
    }
    
    // Convert YUV420 to RGB first
    std::vector<uint8_t> rgbData(width * height * 3);
    yuv420ToRgb(yuvData, rgbData.data(), width, height);
    
    return compressRGB(rgbData.data(), width, height, jpegData, config);
}

bool JpegCompressor::compressRGB(const uint8_t* rgbData, int width, int height,
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

void JpegCompressor::yuv420ToRgb(const uint8_t* yuvData, uint8_t* rgbData,
                                int width, int height) {
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

// FileStorage implementation
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
    filename << std::put_time(std::localtime(&time_t), "frame_%Y%m%d_%H%M%S_");
    filename << std::setfill('0') << std::setw(3) << (++sequenceCounter_);
    filename << extension;
    
    return config_.baseDirectory + "/" + filename.str();
}

bool FileStorage::saveFrame(const CameraCapture::Frame& frame, const std::string& filename) {
    std::string filepath = filename.empty() ? generateFilename(".yuv") : filename;
    
    return saveRaw(frame.data, filepath);
}

bool FileStorage::saveJpeg(const std::vector<uint8_t>& jpegData, const std::string& filename) {
    std::string filepath = filename.empty() ? generateFilename(".jpg") : filename;
    
    return saveRaw(jpegData, filepath);
}

bool FileStorage::saveRaw(const std::vector<uint8_t>& rawData, const std::string& filename) {
    std::lock_guard<std::mutex> lock(fileMutex_);
    
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