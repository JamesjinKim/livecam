#include "RpiCameraCapture.hpp"
#include <iostream>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <thread>
#include <signal.h>
#include <getopt.h>
#include <atomic>
#include <fstream>

static std::atomic<bool> g_running{true};

void signalHandler(int signum) {
    std::cout << "\nReceived signal " << signum << ", stopping..." << std::endl;
    g_running.store(false);
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
              << "  -t, --timeout MS       Capture timeout in ms (default: 5000)\n"
              << "  -v, --verbose          Verbose output\n"
              << "  --test                 Test mode (capture and save frames)\n"
              << "  -b, --benchmark        Performance benchmark\n"
              << "  --help                 Show this help message\n"
              << "\nExamples:\n"
              << "  " << progName << " --test -f 5         # Capture 5 test frames\n"
              << "  " << progName << " -c 0 -v            # Verbose camera info\n"
              << "  " << progName << " -w 640 -h 480 -q 70 # Lower resolution, quality\n";
}

bool testCameraBasic(int cameraIndex, int width, int height, bool verbose) {
    std::cout << "=== Basic Camera Test ===" << std::endl;
    std::cout << "Camera index: " << cameraIndex << std::endl;
    std::cout << "Resolution: " << width << "x" << height << std::endl;
    std::cout << std::endl;
    
    // Show system info
    DebugUtils::printSystemInfo();
    DebugUtils::listCameras();
    
    RpiCameraCapture camera;
    RpiCameraCapture::Config config;
    config.cameraIndex = cameraIndex;
    config.width = width;
    config.height = height;
    config.verbose = verbose;
    config.timeout = 2000; // 2 second test
    
    if (!camera.initialize(config)) {
        std::cerr << "Camera initialization failed!" << std::endl;
        return false;
    }
    
    // Test video capture with timeout
    std::cout << "Testing camera video capture..." << std::endl;
    
    // 짧은 비디오 캡처 테스트 (3초)
    std::ostringstream testCmd;
    testCmd << "rpicam-vid --camera " << cameraIndex 
            << " --width " << width << " --height " << height
            << " --timeout 3000"  // 3초 테스트
            << " --codec yuv420"   // 가장 빠른 형식
            << " --nopreview"
            << " --output test_output.yuv";
    
    if (verbose) {
        std::cout << "Test command: " << testCmd.str() << std::endl;
    }
    
    int result = system(testCmd.str().c_str());
    
    // 테스트 파일 삭제
    system("rm -f test_output.yuv > /dev/null 2>&1");
    
    if (result == 0) {
        std::cout << "Camera test successful!" << std::endl;
        return true;
    } else {
        std::cerr << "Camera test failed! (exit code: " << result << ")" << std::endl;
        return false;
    }
}

bool testFrameCapture(int cameraIndex, int width, int height, int numFrames,
                     const std::string& outputDir, int jpegQuality, 
                     int timeout, bool verbose) {
    std::cout << "=== Frame Capture Test ===" << std::endl;
    std::cout << "Camera index: " << cameraIndex << std::endl;
    std::cout << "Resolution: " << width << "x" << height << std::endl;
    std::cout << "Frames to capture: " << numFrames << std::endl;
    std::cout << "Output directory: " << outputDir << std::endl;
    std::cout << "JPEG quality: " << jpegQuality << std::endl;
    std::cout << "Timeout: " << timeout << " ms" << std::endl;
    std::cout << std::endl;
    
    // Setup file storage
    FileStorage::StorageConfig storageConfig;
    storageConfig.baseDirectory = outputDir;
    FileStorage storage(storageConfig);
    
    signal(SIGINT, signalHandler);
    
    int captured = 0;
    JpegCompressor::CompressConfig jpegConfig;
    jpegConfig.quality = jpegQuality;
    
    // Use rpicam-still for individual frame capture
    for (int i = 0; i < numFrames && g_running.load(); ++i) {
        std::cout << "Capturing frame " << (i+1) << "/" << numFrames << "..." << std::endl;
        
        std::string jpegFilename = outputDir + "/frame_" + std::to_string(i+1) + ".jpg";
        std::string yuvFilename = outputDir + "/frame_" + std::to_string(i+1) + ".yuv";
        
        // Capture JPEG directly
        std::ostringstream jpegCmd;
        jpegCmd << "rpicam-still --camera " << cameraIndex
                << " --width " << width << " --height " << height
                << " --timeout " << timeout
                << " --quality " << jpegQuality
                << " --nopreview"
                << " --output " << jpegFilename;
        
        if (verbose) {
            std::cout << "  Command: " << jpegCmd.str() << std::endl;
        }
        
        int result = system(jpegCmd.str().c_str());
        
        if (result == 0) {
            // Check file size
            std::ifstream file(jpegFilename, std::ios::binary | std::ios::ate);
            if (file.is_open()) {
                size_t fileSize = file.tellg();
                file.close();
                
                std::cout << "  -> Saved JPEG: " << jpegFilename 
                          << " (" << fileSize << " bytes)" << std::endl;
                captured++;
            }
        } else {
            std::cout << "  -> Failed to capture frame " << (i+1) << std::endl;
        }
        
        // Optional: Also capture YUV for testing
        if (verbose) {
            std::ostringstream yuvCmd;
            yuvCmd << "rpicam-vid --camera " << cameraIndex
                   << " --width " << width << " --height " << height
                   << " --timeout 1000"  // 1 second
                   << " --codec yuv420"
                   << " --nopreview"
                   << " --output " << yuvFilename;
            
            system(yuvCmd.str().c_str());
        }
        
        std::cout << std::endl;
        
        // Brief pause between captures
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
    
    std::cout << "Frame capture test completed" << std::endl;
    std::cout << "Total frames captured: " << captured << std::endl;
    return captured > 0;
}

bool benchmarkPerformance(int cameraIndex, int width, int height, bool verbose) {
    std::cout << "=== Performance Benchmark ===" << std::endl;
    std::cout << "Camera index: " << cameraIndex << std::endl;
    std::cout << "Resolution: " << width << "x" << height << std::endl;
    std::cout << "Duration: 10 seconds" << std::endl;
    std::cout << std::endl;
    
    // Use rpicam-vid for continuous capture
    std::string videoFile = "./benchmark_test.h264";
    
    std::ostringstream cmd;
    cmd << "rpicam-vid --camera " << cameraIndex
        << " --width " << width << " --height " << height
        << " --timeout 10000"  // 10 seconds
        << " --framerate 30"
        << " --nopreview";
    
    if (verbose) {
        cmd << " --verbose";
    }
    
    cmd << " --output " << videoFile;
    
    std::cout << "Starting benchmark..." << std::endl;
    if (verbose) {
        std::cout << "Command: " << cmd.str() << std::endl;
    }
    
    auto startTime = std::chrono::steady_clock::now();
    signal(SIGINT, signalHandler);
    
    int result = system(cmd.str().c_str());
    
    auto endTime = std::chrono::steady_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(
        endTime - startTime).count() / 1000.0;
    
    std::cout << "\n=== Benchmark Results ===" << std::endl;
    std::cout << "Duration: " << std::fixed << std::setprecision(1) << duration << " seconds" << std::endl;
    std::cout << "Command result: " << (result == 0 ? "Success" : "Failed") << std::endl;
    
    // Check output file
    if (result == 0) {
        std::ifstream file(videoFile, std::ios::binary | std::ios::ate);
        if (file.is_open()) {
            size_t fileSize = file.tellg();
            file.close();
            
            std::cout << "Output file: " << videoFile << std::endl;
            std::cout << "File size: " << (fileSize / 1024 / 1024) << " MB" << std::endl;
            std::cout << "Data rate: " << std::fixed << std::setprecision(2) 
                      << (fileSize / (duration * 1024 * 1024)) << " MB/s" << std::endl;
            
            // Estimated frame rate (H.264 compressed)
            double estimatedFrames = duration * 30; // 30 FPS target
            std::cout << "Estimated frames: " << static_cast<int>(estimatedFrames) << std::endl;
            std::cout << "Average frame rate: ~30 FPS (H.264)" << std::endl;
        }
    }
    
    // Cleanup
    std::remove(videoFile.c_str());
    
    return result == 0;
}

int main(int argc, char* argv[]) {
    int width = 1920;
    int height = 1080;
    int cameraIndex = 1;
    int numFrames = 10;
    std::string outputDir = "./captures";
    int jpegQuality = 85;
    int timeout = 5000;
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
        {"timeout",   required_argument, 0, 't'},
        {"verbose",   no_argument,       0, 'v'},
        {"test",      no_argument,       0,  0 },
        {"benchmark", no_argument,       0, 'b'},
        {"help",      no_argument,       0,  0 },
        {0,           0,                 0,  0 }
    };
    
    int option_index = 0;
    int c;
    
    while ((c = getopt_long(argc, argv, "w:h:c:f:o:q:t:vb", long_options, &option_index)) != -1) {
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
            case 't':
                timeout = std::atoi(optarg);
                break;
            case 'v':
                verbose = true;
                break;
            case 'b':
                benchmark = true;
                break;
            case 0:
                if (option_index == 8) { // test
                    testMode = true;
                } else if (option_index == 10) { // help
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
    
    std::cout << "Raspberry Pi rpicam-based C++ Test" << std::endl;
    std::cout << "==================================" << std::endl;
    
    try {
        if (benchmark) {
            return benchmarkPerformance(cameraIndex, width, height, verbose) ? 0 : 1;
        } else if (testMode) {
            return testFrameCapture(cameraIndex, width, height, numFrames, 
                                   outputDir, jpegQuality, timeout, verbose) ? 0 : 1;
        } else {
            return testCameraBasic(cameraIndex, width, height, verbose) ? 0 : 1;
        }
    } catch (const std::exception& e) {
        std::cerr << "Exception: " << e.what() << std::endl;
        return 1;
    }
}