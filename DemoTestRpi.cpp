#include "RpiCameraCapture.hpp"
#include <iostream>
#include <iomanip>
#include <sstream>

class DemoFrameGenerator {
public:
    static RpiCameraCapture::Frame createTestFrame(int width, int height) {
        RpiCameraCapture::Frame frame(width, height, "yuv420");
        
        // YUV420 has 1.5 bytes per pixel
        size_t frameSize = width * height * 3 / 2;
        frame.data.resize(frameSize);
        
        // Create test pattern
        createYUV420TestPattern(frame.data.data(), width, height);
        
        return frame;
    }

private:
    static void createYUV420TestPattern(uint8_t* data, int width, int height) {
        // Y plane (luminance) - diagonal gradient
        uint8_t* y_plane = data;
        for (int row = 0; row < height; row++) {
            for (int col = 0; col < width; col++) {
                y_plane[row * width + col] = static_cast<uint8_t>(
                    ((row + col) * 255) / (width + height));
            }
        }
        
        // U plane (chroma) - horizontal gradient
        uint8_t* u_plane = data + width * height;
        for (int row = 0; row < height / 2; row++) {
            for (int col = 0; col < width / 2; col++) {
                u_plane[row * (width / 2) + col] = static_cast<uint8_t>(
                    128 + (col * 127) / (width / 2));
            }
        }
        
        // V plane (chroma) - vertical gradient
        uint8_t* v_plane = data + width * height + (width * height) / 4;
        for (int row = 0; row < height / 2; row++) {
            for (int col = 0; col < width / 2; col++) {
                v_plane[row * (width / 2) + col] = static_cast<uint8_t>(
                    128 + (row * 127) / (height / 2));
            }
        }
    }
};

bool testJpegCompression() {
    std::cout << "=== JPEG Compression Test ===" << std::endl;
    
    int width = 640;
    int height = 480;
    int quality = 85;
    
    auto frame = DemoFrameGenerator::createTestFrame(width, height);
    
    std::cout << "Created test frame: " << width << "x" << height 
              << ", " << frame.data.size() << " bytes" << std::endl;
    
    std::cout << "Compressing to JPEG (quality " << quality << ")..." << std::endl;
    
    std::vector<uint8_t> jpegData;
    JpegCompressor::CompressConfig config;
    config.quality = quality;
    
    if (!JpegCompressor::compressYUV420ToJpeg(frame.data.data(), width, height, jpegData, config)) {
        std::cerr << "JPEG compression failed!" << std::endl;
        return false;
    }
    
    std::cout << "JPEG compression successful!" << std::endl;
    std::cout << "  Original size: " << frame.data.size() << " bytes" << std::endl;
    std::cout << "  JPEG size: " << jpegData.size() << " bytes" << std::endl;
    std::cout << "  Compression ratio: " << std::fixed << std::setprecision(1) 
              << (100.0 * jpegData.size() / frame.data.size()) << "%" << std::endl;
    
    // Save JPEG file
    FileStorage::StorageConfig storageConfig;
    storageConfig.baseDirectory = "./demo";
    FileStorage storage(storageConfig);
    
    if (storage.saveJpeg(jpegData, "./demo/test_frame.jpg")) {
        std::cout << "  Saved test JPEG: ./demo/test_frame.jpg" << std::endl;
    }
    
    std::cout << "JPEG compression test completed successfully\n" << std::endl;
    return true;
}

bool testFileOperations() {
    std::cout << "=== File Operations Test ===" << std::endl;
    
    auto frame = DemoFrameGenerator::createTestFrame(320, 240);
    
    std::cout << "Testing file storage system..." << std::endl;
    
    FileStorage::StorageConfig config;
    config.baseDirectory = "./demo/test_files";
    config.createDirectories = true;
    
    FileStorage storage(config);
    
    // Test frame saving
    std::string filename = storage.generateFilename(".yuv");
    if (!storage.saveFrame(frame, filename)) {
        std::cerr << "Failed to save frame!" << std::endl;
        return false;
    }
    
    // Test raw data saving
    std::vector<uint8_t> testData = {0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77};
    if (!storage.saveRaw(testData, "./demo/test_files/raw_data.bin")) {
        std::cerr << "Failed to save raw data!" << std::endl;
        return false;
    }
    
    std::cout << "File operations test completed successfully\n" << std::endl;
    return true;
}

bool testDebugFunctions() {
    std::cout << "=== Debug Functions Test ===" << std::endl;
    
    auto frame = DemoFrameGenerator::createTestFrame(160, 120);
    
    DebugUtils::printFrameInfo(frame);
    
    std::cout << "Debug functions test completed successfully\n" << std::endl;
    return true;
}

bool testSystemInfo() {
    std::cout << "=== System Information Test ===" << std::endl;
    
    DebugUtils::printSystemInfo();
    DebugUtils::listCameras();
    DebugUtils::analyzeMemoryUsage();
    
    if (DebugUtils::checkRpiCamTools()) {
        std::cout << "System information test completed successfully\n" << std::endl;
        return true;
    } else {
        std::cout << "Warning: rpicam tools not available\n" << std::endl;
        return false;
    }
}

bool testCameraDetection() {
    std::cout << "=== Camera Detection Test ===" << std::endl;
    
    auto cameras = RpiCameraCapture::listCameras();
    std::cout << "Found " << cameras.size() << " camera(s)" << std::endl;
    
    for (int camera : cameras) {
        std::cout << "  Camera " << camera << ": Testing..." << std::endl;
        if (RpiCameraCapture::testCamera(camera)) {
            std::cout << "    -> Working" << std::endl;
        } else {
            std::cout << "    -> Not working" << std::endl;
        }
    }
    
    std::cout << "Camera detection test completed\n" << std::endl;
    return !cameras.empty();
}

void printUsage(const char* progName) {
    std::cout << "Usage: " << progName << " [test_name]\n"
              << "Available tests:\n"
              << "  jpeg      - JPEG compression test\n"
              << "  file      - File operations test\n"
              << "  debug     - Debug functions test\n"
              << "  system    - System information test\n"
              << "  camera    - Camera detection test\n"
              << "  all       - Run all tests (default)\n";
}

int main(int argc, char* argv[]) {
    std::string testName = "all";
    
    if (argc > 1) {
        if (std::string(argv[1]) == "--help") {
            printUsage(argv[0]);
            return 0;
        }
        testName = argv[1];
    }
    
    std::cout << "Raspberry Pi rpicam C++ Components Demo Test" << std::endl;
    std::cout << "============================================" << std::endl;
    std::cout << "Testing core functionality without requiring camera capture.\n" << std::endl;
    
    bool success = true;
    
    try {
        if (testName == "jpeg" || testName == "all") {
            success &= testJpegCompression();
        }
        
        if (testName == "file" || testName == "all") {
            success &= testFileOperations();
        }
        
        if (testName == "debug" || testName == "all") {
            success &= testDebugFunctions();
        }
        
        if (testName == "system" || testName == "all") {
            success &= testSystemInfo();
        }
        
        if (testName == "camera" || testName == "all") {
            // Camera detection is optional - don't fail if no camera
            testCameraDetection();
        }
        
        if (success) {
            std::cout << "🎉 Core demo tests passed successfully!" << std::endl;
            std::cout << "\nNext steps:" << std::endl;
            std::cout << "1. Connect a camera module for full testing" << std::endl;
            std::cout << "2. Run './test_camera_rpi --test -f 3' for actual capture" << std::endl;
            std::cout << "3. Check ./demo/ directory for generated files" << std::endl;
            std::cout << "\nNote: This version uses rpicam-vid/rpicam-still for maximum compatibility!" << std::endl;
        } else {
            std::cout << "❌ Some core tests failed" << std::endl;
        }
        
    } catch (const std::exception& e) {
        std::cerr << "Exception during testing: " << e.what() << std::endl;
        return 1;
    }
    
    return success ? 0 : 1;
}