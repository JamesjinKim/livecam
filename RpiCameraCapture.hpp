#pragma once

#include <string>
#include <vector>
#include <memory>
#include <functional>
#include <thread>
#include <atomic>
#include <chrono>
#include <fstream>
#include <jpeglib.h>

class RpiCameraCapture {
public:
    struct Frame {
        std::vector<uint8_t> data;
        std::chrono::steady_clock::time_point timestamp;
        int width;
        int height;
        std::string format;
        
        Frame() = default;
        Frame(int w, int h, const std::string& fmt) 
            : width(w), height(h), timestamp(std::chrono::steady_clock::now()), format(fmt) {}
    };

    struct Config {
        int width = 1920;
        int height = 1080;
        int cameraIndex = 1;
        int quality = 85;
        std::string format = "yuv420";  // yuv420, rgb, jpeg
        int timeout = 5000; // milliseconds
        bool verbose = false;
    };

    using FrameCallback = std::function<void(const Frame&)>;

public:
    RpiCameraCapture();
    ~RpiCameraCapture();

    bool initialize(const Config& config);
    bool startCapture();
    bool stopCapture();
    bool captureFrame(Frame& frame);
    void setFrameCallback(FrameCallback callback);
    
    bool isInitialized() const { return initialized_; }
    bool isCapturing() const { return capturing_; }
    const Config& getConfig() const { return config_; }
    
    static std::vector<int> listCameras();
    static bool testCamera(int cameraIndex = 0);

private:
    bool startRpiCamProcess();
    void stopRpiCamProcess();
    void frameReaderThread();

private:
    Config config_;
    bool initialized_ = false;
    std::atomic<bool> capturing_{false};
    
    FILE* rpiCamPipe_ = nullptr;
    std::thread readerThread_;
    FrameCallback frameCallback_;
    
    std::string buildRpiCamCommand() const;
};

class JpegCompressor {
public:
    struct CompressConfig {
        int quality = 85;
        bool optimizeHuffman = true;
        bool progressive = false;
    };

    static bool compressYUV420ToJpeg(const uint8_t* yuvData, int width, int height, 
                                    std::vector<uint8_t>& jpegData,
                                    const CompressConfig& config);
                                    
    static bool compressRGBToJpeg(const uint8_t* rgbData, int width, int height,
                                 std::vector<uint8_t>& jpegData,
                                 const CompressConfig& config);

private:
    static void yuv420ToRgb(const uint8_t* yuvData, uint8_t* rgbData, int width, int height);
};

class FileStorage {
public:
    struct StorageConfig {
        std::string baseDirectory = "./captures";
        std::string prefix = "frame";
        bool createDirectories = true;
        size_t maxFileSize = 100 * 1024 * 1024; // 100MB
    };

public:
    explicit FileStorage(const StorageConfig& config);
    
    bool saveFrame(const RpiCameraCapture::Frame& frame, const std::string& filename = "");
    bool saveJpeg(const std::vector<uint8_t>& jpegData, const std::string& filename = "");
    bool saveRaw(const std::vector<uint8_t>& rawData, const std::string& filename = "");
    
    std::string generateFilename(const std::string& extension = ".jpg");
    bool createDirectoryStructure() const;

private:
    StorageConfig config_;
    int sequenceCounter_ = 0;
};

class DebugUtils {
public:
    static void printFrameInfo(const RpiCameraCapture::Frame& frame);
    static void printSystemInfo();
    static void listCameras();
    static void analyzeMemoryUsage();
    static bool checkRpiCamTools();
};