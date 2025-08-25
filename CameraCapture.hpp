#pragma once

#include <memory>
#include <vector>
#include <string>
#include <chrono>
#include <functional>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <map>
#include <fstream>
#include <libcamera/libcamera.h>
#include <libcamera/request.h>
#include <libcamera/framebuffer.h>

class CameraCapture {
public:
    struct Frame {
        std::vector<uint8_t> data;
        std::chrono::steady_clock::time_point timestamp;
        int width;
        int height;
        size_t stride;
        uint32_t format;
        
        Frame() = default;
        Frame(size_t size) : data(size) {}
    };

    struct CameraConfig {
        int width = 1920;
        int height = 1080;
        uint32_t format = 0; // Will be set based on available formats
        unsigned int bufferCount = 4;
        int cameraIndex = 0;
    };

    using FrameCallback = std::function<void(const Frame&)>;

public:
    CameraCapture();
    ~CameraCapture();

    // Core functionality
    bool initialize(const CameraConfig& config = CameraConfig());
    bool startCapture();
    bool stopCapture();
    void cleanup();

    // Frame capture
    bool captureFrame(Frame& frame);
    void setFrameCallback(FrameCallback callback);

    // Configuration
    bool setResolution(int width, int height);
    bool setFormat(uint32_t format);
    std::vector<libcamera::Size> getSupportedResolutions() const;
    std::vector<uint32_t> getSupportedFormats() const;

    // Information
    bool isInitialized() const { return initialized_; }
    bool isCapturing() const { return capturing_; }
    int getWidth() const { return config_.width; }
    int getHeight() const { return config_.height; }
    std::string getCameraInfo() const;

    // Static utility functions
    static std::vector<std::string> listCameras();
    static std::string formatToString(uint32_t format);

private:
    void onRequestCompleted(libcamera::Request* request);
    void setupBuffers();
    libcamera::FrameBuffer* createBuffer(const libcamera::Stream* stream);

private:
    std::unique_ptr<libcamera::CameraManager> cameraManager_;
    std::shared_ptr<libcamera::Camera> camera_;
    std::unique_ptr<libcamera::CameraConfiguration> cameraConfig_;
    
    std::vector<std::unique_ptr<libcamera::Request>> requests_;
    std::map<libcamera::FrameBuffer*, std::vector<uint8_t>> bufferMap_;
    std::queue<libcamera::Request*> freeRequests_;
    
    CameraConfig config_;
    bool initialized_ = false;
    bool capturing_ = false;
    
    FrameCallback frameCallback_;
    std::mutex frameMutex_;
    std::condition_variable frameCondition_;
    std::queue<Frame> frameQueue_;
};

// JPEG Compression class
class JpegCompressor {
public:
    struct CompressConfig {
        int quality = 85;
        bool optimizeHuffman = true;
        bool progressive = false;
    };

public:
    static bool compressYUV420(const uint8_t* yuvData, int width, int height, 
                               std::vector<uint8_t>& jpegData, 
                               const CompressConfig& config = CompressConfig());
    
    static bool compressRGB(const uint8_t* rgbData, int width, int height,
                           std::vector<uint8_t>& jpegData,
                           const CompressConfig& config = CompressConfig());

private:
    static void yuv420ToRgb(const uint8_t* yuvData, uint8_t* rgbData, 
                           int width, int height);
};

// File Storage class
class FileStorage {
public:
    struct StorageConfig {
        std::string baseDirectory = "./captures";
        std::string filenamePattern = "frame_%Y%m%d_%H%M%S_%03d";
        bool createDirectories = true;
        size_t maxFileSize = 100 * 1024 * 1024; // 100MB
    };

public:
    FileStorage(const StorageConfig& config = StorageConfig());
    ~FileStorage() = default;

    bool saveFrame(const CameraCapture::Frame& frame, const std::string& filename = "");
    bool saveJpeg(const std::vector<uint8_t>& jpegData, const std::string& filename = "");
    bool saveRaw(const std::vector<uint8_t>& rawData, const std::string& filename = "");

    std::string generateFilename(const std::string& extension = ".jpg");
    bool createDirectoryStructure() const;

private:
    StorageConfig config_;
    int sequenceCounter_ = 0;
    std::mutex fileMutex_;
};

// Debug utilities
class DebugUtils {
public:
    static void printCameraInfo(const CameraCapture& camera);
    static void printFrameInfo(const CameraCapture::Frame& frame);
    static void printSystemInfo();
    static void listVideoDevices();
    static void analyzeMemoryUsage();
    static bool checkLibcameraVersion();
};