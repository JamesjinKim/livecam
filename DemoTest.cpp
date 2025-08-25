#include "CameraCapture.hpp"
#include "DebugUtils.cpp"
#include <iostream>
#include <memory>

class DemoFrameGenerator {
public:
    static CameraCapture::Frame createTestFrame(int width, int height) {
        CameraCapture::Frame frame;
        frame.width = width;
        frame.height = height;
        frame.format = 0x32315559; // YUV420 format code
        frame.timestamp = std::chrono::steady_clock::now();
        
        // YUV420 has 1.5 bytes per pixel (Y: 1 byte, U+V: 0.5 bytes)
        size_t frameSize = width * height * 3 / 2;
        frame.data.resize(frameSize);
        
        // Create gradient pattern
        createYUV420Gradient(frame.data.data(), width, height);
        
        return frame;
    }

private:
    static void createYUV420Gradient(uint8_t* data, int width, int height) {
        // Y plane (luminance)
        uint8_t* y_plane = data;
        for (int row = 0; row < height; row++) {
            for (int col = 0; col < width; col++) {
                y_plane[row * width + col] = static_cast<uint8_t>(
                    (col * 255) / width);
            }
        }
        
        // U plane (chroma)
        uint8_t* u_plane = data + width * height;
        for (int row = 0; row < height / 2; row++) {
            for (int col = 0; col < width / 2; col++) {
                u_plane[row * (width / 2) + col] = static_cast<uint8_t>(
                    128 + (row * 127) / (height / 2));
            }
        }
        
        // V plane (chroma)
        uint8_t* v_plane = data + width * height + (width * height) / 4;
        for (int row = 0; row < height / 2; row++) {
            for (int col = 0; col < width / 2; col++) {
                v_plane[row * (width / 2) + col] = static_cast<uint8_t>(
                    128 - (row * 127) / (height / 2));
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
    
    if (!JpegCompressor::compressYUV420(frame.data.data(), width, height, jpegData, config)) {
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
    std::vector<uint8_t> testData = {0x00, 0x11, 0x22, 0x33, 0x44, 0x55};
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

bool testCameraListing() {
    std::cout << "=== Camera Listing Test ===" << std::endl;
    
    try {
        DebugUtils::listVideoDevices();
        std::cout << "Camera listing test completed successfully\n" << std::endl;
        return true;
    } catch (const std::exception& e) {
        std::cerr << "Camera listing failed: " << e.what() << std::endl;
        return false;
    }
}

void printUsage(const char* progName) {
    std::cout << "Usage: " << progName << " [test_name]\n"
              << "Available tests:\n"
              << "  jpeg      - JPEG compression test\n"
              << "  file      - File operations test\n"
              << "  debug     - Debug functions test\n"
              << "  camera    - Camera listing test\n"
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
    
    std::cout << "C++ libcamera Components Demo Test" << std::endl;
    std::cout << "==================================" << std::endl;
    std::cout << "Testing core functionality without requiring physical camera.\n" << std::endl;
    
    // Show system info first
    DebugUtils::printSystemInfo();
    
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
        
        if (testName == "camera" || testName == "all") {
            success &= testCameraListing();
        }
        
        if (success) {
            std::cout << "🎉 All demo tests passed successfully!" << std::endl;
            std::cout << "\nNext steps:" << std::endl;
            std::cout << "1. Connect a camera module to test actual capture" << std::endl;
            std::cout << "2. Run './test_camera -t -f 5' when camera is connected" << std::endl;
            std::cout << "3. Check ./demo/ directory for generated files" << std::endl;
            std::cout << "\nNote: This C++ version uses libcamera API for Raspberry Pi 5 compatibility!" << std::endl;
        } else {
            std::cout << "❌ Some tests failed" << std::endl;
        }
        
    } catch (const std::exception& e) {
        std::cerr << "Exception during testing: " << e.what() << std::endl;
        return 1;
    }
    
    return success ? 0 : 1;
}