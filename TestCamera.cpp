#include "CameraCapture.hpp"
#include "DebugUtils.cpp"
#include <iostream>
#include <chrono>
#include <thread>
#include <signal.h>
#include <getopt.h>

static volatile bool g_running = true;

void signalHandler(int signum) {
    std::cout << "\nReceived signal " << signum << ", stopping..." << std::endl;
    g_running = false;
}

void printUsage(const char* progName) {
    std::cout << "Usage: " << progName << " [options]\n"
              << "Options:\n"
              << "  -w, --width WIDTH      Frame width (default: 1920)\n"
              << "  -h, --height HEIGHT    Frame height (default: 1080)\n"
              << "  -c, --camera INDEX     Camera index (default: 0)\n"
              << "  -f, --frames COUNT     Number of frames to capture (default: 10)\n"
              << "  -o, --output DIR       Output directory (default: ./captures)\n"
              << "  -q, --quality QUALITY  JPEG quality 1-100 (default: 85)\n"
              << "  -v, --verbose          Verbose output\n"
              << "  -t, --test             Test mode (capture and save frames)\n"
              << "  -b, --benchmark        Performance benchmark\n"
              << "  --help                 Show this help message\n"
              << "\nExamples:\n"
              << "  " << progName << " -t -f 5              # Capture 5 test frames\n"
              << "  " << progName << " -c 0 -v              # Verbose camera info\n"
              << "  " << progName << " -w 640 -h 480 -q 70  # Lower resolution, quality\n";
}

bool testCameraBasic(int cameraIndex, int width, int height, bool verbose) {
    std::cout << "=== Basic Camera Test ===" << std::endl;
    std::cout << "Camera index: " << cameraIndex << std::endl;
    std::cout << "Resolution: " << width << "x" << height << std::endl;
    std::cout << std::endl;
    
    CameraCapture camera;
    CameraCapture::CameraConfig config;
    config.cameraIndex = cameraIndex;
    config.width = width;
    config.height = height;
    
    if (!camera.initialize(config)) {
        std::cerr << "Camera initialization failed!" << std::endl;
        return false;
    }
    
    if (verbose) {
        DebugUtils::printCameraInfo(camera);
    }
    
    if (!camera.startCapture()) {
        std::cerr << "Failed to start streaming!" << std::endl;
        return false;
    }
    
    std::cout << "Camera test successful - streaming started" << std::endl;
    
    camera.stopCapture();
    std::cout << "Camera test completed successfully" << std::endl;
    return true;
}

bool testFrameCapture(int cameraIndex, int width, int height, int numFrames,
                     const std::string& outputDir, int jpegQuality, bool verbose) {
    std::cout << "=== Frame Capture Test ===" << std::endl;
    std::cout << "Camera index: " << cameraIndex << std::endl;
    std::cout << "Resolution: " << width << "x" << height << std::endl;
    std::cout << "Frames to capture: " << numFrames << std::endl;
    std::cout << "Output directory: " << outputDir << std::endl;
    std::cout << "JPEG quality: " << jpegQuality << std::endl;
    std::cout << std::endl;
    
    // Setup file storage
    FileStorage::StorageConfig storageConfig;
    storageConfig.baseDirectory = outputDir;
    FileStorage storage(storageConfig);
    
    // Setup camera
    CameraCapture camera;
    CameraCapture::CameraConfig config;
    config.cameraIndex = cameraIndex;
    config.width = width;
    config.height = height;
    
    if (!camera.initialize(config)) {
        std::cerr << "Camera initialization failed!" << std::endl;
        return false;
    }
    
    if (verbose) {
        DebugUtils::printCameraInfo(camera);
    }
    
    if (!camera.startCapture()) {
        std::cerr << "Failed to start streaming!" << std::endl;
        return false;
    }
    
    std::cout << "Starting frame capture..." << std::endl;
    
    signal(SIGINT, signalHandler);
    
    int captured = 0;
    JpegCompressor::CompressConfig jpegConfig;
    jpegConfig.quality = jpegQuality;
    
    while (g_running && captured < numFrames) {
        CameraCapture::Frame frame;
        if (!camera.captureFrame(frame)) {
            std::cout << "Waiting for frame..." << std::endl;
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            continue;
        }
        
        captured++;
        std::cout << "Captured frame " << captured << "/" << numFrames 
                  << " (size: " << frame.data.size() << " bytes)" << std::endl;
        
        if (verbose) {
            DebugUtils::printFrameInfo(frame);
        }
        
        // Save raw frame
        std::string rawFilename = outputDir + "/frame_" + 
                                 std::to_string(captured) + "_raw.yuv";
        storage.saveFrame(frame, rawFilename);
        
        // Compress and save JPEG
        std::vector<uint8_t> jpegData;
        if (JpegCompressor::compressYUV420(frame.data.data(), frame.width, 
                                          frame.height, jpegData, jpegConfig)) {
            std::string jpegFilename = outputDir + "/frame_" + 
                                      std::to_string(captured) + ".jpg";
            storage.saveJpeg(jpegData, jpegFilename);
            
            double compressionRatio = 100.0 * jpegData.size() / frame.data.size();
            std::cout << "  -> Saved as JPEG: " << jpegFilename 
                      << " (" << jpegData.size() << " bytes, " 
                      << std::fixed << std::setprecision(1) 
                      << compressionRatio << "% of original)" << std::endl;
        } else {
            std::cout << "Warning: JPEG compression failed for frame " << captured << std::endl;
        }
        
        std::cout << std::endl;
    }
    
    camera.stopCapture();
    
    std::cout << "Frame capture test completed" << std::endl;
    std::cout << "Total frames captured: " << captured << std::endl;
    return true;
}

bool benchmarkPerformance(int cameraIndex, int width, int height) {
    std::cout << "=== Performance Benchmark ===" << std::endl;
    std::cout << "Camera index: " << cameraIndex << std::endl;
    std::cout << "Resolution: " << width << "x" << height << std::endl;
    std::cout << "Duration: 10 seconds" << std::endl;
    std::cout << std::endl;
    
    CameraCapture camera;
    CameraCapture::CameraConfig config;
    config.cameraIndex = cameraIndex;
    config.width = width;
    config.height = height;
    
    if (!camera.initialize(config)) {
        std::cerr << "Camera initialization failed!" << std::endl;
        return false;
    }
    
    if (!camera.startCapture()) {
        std::cerr << "Failed to start streaming!" << std::endl;
        return false;
    }
    
    std::cout << "Starting benchmark..." << std::endl;
    
    auto startTime = std::chrono::steady_clock::now();
    signal(SIGINT, signalHandler);
    
    int frames = 0;
    size_t totalBytes = 0;
    
    while (g_running) {
        auto elapsed = std::chrono::steady_clock::now() - startTime;
        if (elapsed > std::chrono::seconds(10)) {
            break;
        }
        
        CameraCapture::Frame frame;
        if (camera.captureFrame(frame)) {
            frames++;
            totalBytes += frame.data.size();
            
            if (frames % 30 == 0) {
                auto elapsedSeconds = std::chrono::duration_cast<std::chrono::seconds>(elapsed).count();
                if (elapsedSeconds > 0) {
                    std::cout << "Captured " << frames << " frames (" 
                              << (frames / elapsedSeconds) << " fps)" << std::endl;
                }
            }
        } else {
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    }
    
    auto endTime = std::chrono::steady_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(
        endTime - startTime).count() / 1000.0;
    
    camera.stopCapture();
    
    std::cout << "\n=== Benchmark Results ===" << std::endl;
    std::cout << "Duration: " << std::fixed << std::setprecision(1) << duration << " seconds" << std::endl;
    std::cout << "Frames captured: " << frames << std::endl;
    std::cout << "Average FPS: " << std::fixed << std::setprecision(2) << (frames / duration) << std::endl;
    if (frames > 0) {
        std::cout << "Average frame size: " << (totalBytes / frames) << " bytes" << std::endl;
        std::cout << "Data rate: " << std::fixed << std::setprecision(2) 
                  << (totalBytes / (duration * 1024 * 1024)) << " MB/s" << std::endl;
    }
    
    return true;
}

int main(int argc, char* argv[]) {
    int width = 1920;
    int height = 1080;
    int cameraIndex = 0;
    int numFrames = 10;
    std::string outputDir = "./captures";
    int jpegQuality = 85;
    bool verbose = false;
    bool testMode = false;
    bool benchmark = false;
    
    // Command line options
    static struct option long_options[] = {
        {"width",     required_argument, 0, 'w'},
        {"height",    required_argument, 0, 'h'},
        {"camera",    required_argument, 0, 'c'},
        {"frames",    required_argument, 0, 'f'},
        {"output",    required_argument, 0, 'o'},
        {"quality",   required_argument, 0, 'q'},
        {"verbose",   no_argument,       0, 'v'},
        {"test",      no_argument,       0, 't'},
        {"benchmark", no_argument,       0, 'b'},
        {"help",      no_argument,       0,  0 },
        {0,           0,                 0,  0 }
    };
    
    int option_index = 0;
    int c;
    
    while ((c = getopt_long(argc, argv, "w:h:c:f:o:q:vtb", long_options, &option_index)) != -1) {
        switch (c) {
            case 'w':
                width = std::atoi(optarg);
                break;
            case 'h':
                height = std::atoi(optarg);
                break;
            case 'c':
                cameraIndex = std::atoi(optarg);
                break;
            case 'f':
                numFrames = std::atoi(optarg);
                break;
            case 'o':
                outputDir = optarg;
                break;
            case 'q':
                jpegQuality = std::atoi(optarg);
                break;
            case 'v':
                verbose = true;
                break;
            case 't':
                testMode = true;
                break;
            case 'b':
                benchmark = true;
                break;
            case 0:
                if (option_index == 9) { // help
                    printUsage(argv[0]);
                    return 0;
                }
                break;
            default:
                printUsage(argv[0]);
                return 1;
        }
    }
    
    // Validate parameters
    if (jpegQuality < 1 || jpegQuality > 100) {
        std::cerr << "Error: JPEG quality must be between 1 and 100" << std::endl;
        return 1;
    }
    
    if (width <= 0 || height <= 0) {
        std::cerr << "Error: Invalid resolution " << width << "x" << height << std::endl;
        return 1;
    }
    
    std::cout << "Raspberry Pi libcamera C++ Test" << std::endl;
    std::cout << "===============================" << std::endl;
    
    // Show system info first
    DebugUtils::printSystemInfo();
    DebugUtils::listVideoDevices();
    
    try {
        if (benchmark) {
            return benchmarkPerformance(cameraIndex, width, height) ? 0 : 1;
        } else if (testMode) {
            return testFrameCapture(cameraIndex, width, height, numFrames, 
                                   outputDir, jpegQuality, verbose) ? 0 : 1;
        } else {
            return testCameraBasic(cameraIndex, width, height, verbose) ? 0 : 1;
        }
    } catch (const std::exception& e) {
        std::cerr << "Exception: " << e.what() << std::endl;
        return 1;
    }
}