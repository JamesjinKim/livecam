#include "CameraCapture.hpp"
#include <iostream>
#include <iomanip>
#include <fstream>
#include <filesystem>
#include <sstream>
#include <sys/utsname.h>
#include <sys/sysinfo.h>

void DebugUtils::printCameraInfo(const CameraCapture& camera) {
    std::cout << camera.getCameraInfo() << std::endl;
}

void DebugUtils::printFrameInfo(const CameraCapture::Frame& frame) {
    std::cout << "=== Frame Information ===" << std::endl;
    std::cout << "Data size: " << frame.data.size() << " bytes" << std::endl;
    std::cout << "Resolution: " << frame.width << "x" << frame.height << std::endl;
    std::cout << "Format: " << CameraCapture::formatToString(frame.format) << std::endl;
    
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
        std::cout << "Version: " << sys_info.version << std::endl;
        std::cout << "Machine: " << sys_info.machine << std::endl;
    }
    
    // Memory info
    struct sysinfo mem_info;
    if (sysinfo(&mem_info) == 0) {
        std::cout << "Total RAM: " << (mem_info.totalram >> 20) << " MB" << std::endl;
        std::cout << "Free RAM: " << (mem_info.freeram >> 20) << " MB" << std::endl;
        std::cout << "Available RAM: " << ((mem_info.totalram - mem_info.freeram) >> 20) << " MB" << std::endl;
    }
    
    // libcamera version
    checkLibcameraVersion();
    std::cout << std::endl;
}

void DebugUtils::listVideoDevices() {
    std::cout << "=== Available Cameras ===" << std::endl;
    
    auto cameras = CameraCapture::listCameras();
    if (cameras.empty()) {
        std::cout << "No cameras found" << std::endl;
    } else {
        for (size_t i = 0; i < cameras.size(); ++i) {
            std::cout << "[" << i << "] " << cameras[i] << std::endl;
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
                line.find("Cached:") == 0 ||
                line.find("CmaTotal:") == 0 ||
                line.find("CmaFree:") == 0) {
                std::cout << line << std::endl;
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "Error reading memory info: " << e.what() << std::endl;
    }
    std::cout << std::endl;
}

bool DebugUtils::checkLibcameraVersion() {
    std::cout << "libcamera: Available" << std::endl;
    // Note: libcamera doesn't provide a simple version API
    // but we can check if it's working by trying to create a camera manager
    try {
        libcamera::CameraManager manager;
        manager.start();
        std::cout << "libcamera status: Working" << std::endl;
        manager.stop();
        return true;
    } catch (const std::exception& e) {
        std::cout << "libcamera status: Error - " << e.what() << std::endl;
        return false;
    }
}