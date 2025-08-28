#include <iostream>
#include <string>
#include <cstdlib>
#include <unistd.h>
#include <sys/wait.h>

class RpiCamDirect {
public:
    // PRD 목표: rpicam-vid 직접 활용한 640x480 영상 캡처
    static bool captureFrames(int count = 10) {
        std::cout << "🎯 PRD 목표: rpicam-vid 직접 활용 640x480 영상 캡처" << std::endl;
        std::cout << "=======================================================" << std::endl;
        
        for (int i = 1; i <= count; i++) {
            std::string filename = "rpicam_frame_" + std::to_string(i) + ".jpg";
            
            // rpicam-still을 사용한 단일 프레임 캡처
            std::string cmd = "rpicam-still --camera 0 --width 640 --height 480 --output " + filename + " --timeout 1000 --nopreview";
            
            std::cout << "📸 Frame " << i << "/" << count << " capturing..." << std::endl;
            
            int result = system(cmd.c_str());
            if (result != 0) {
                std::cerr << "❌ Failed to capture frame " << i << std::endl;
                return false;
            }
            
            std::cout << "✅ Frame " << i << " saved: " << filename << std::endl;
            usleep(200000); // 0.2초 대기
        }
        
        return true;
    }
    
    // 연속 비디오 캡처 (H.264 형식)
    static bool captureVideo(int duration_ms = 5000) {
        std::cout << "🎬 연속 비디오 캡처 (640x480, " << duration_ms << "ms)" << std::endl;
        
        std::string cmd = "rpicam-vid --camera 0 --width 640 --height 480 --timeout " + 
                         std::to_string(duration_ms) + " --output rpicam_video.h264 --nopreview";
        
        int result = system(cmd.c_str());
        if (result != 0) {
            std::cerr << "❌ Video capture failed" << std::endl;
            return false;
        }
        
        std::cout << "✅ Video saved: rpicam_video.h264" << std::endl;
        return true;
    }
    
    // YUV420 Raw 형식으로 캡처 (최소 CPU 사용)
    static bool captureYUV420(const std::string& filename = "rpicam_raw.yuv") {
        std::cout << "📹 YUV420 Raw 캡처 (CPU 최적화)" << std::endl;
        
        std::string cmd = "rpicam-vid --camera 0 --width 640 --height 480 --timeout 2000 --codec yuv420 --output " + filename + " --nopreview";
        
        int result = system(cmd.c_str());
        if (result != 0) {
            std::cerr << "❌ YUV420 capture failed" << std::endl;
            return false;
        }
        
        std::cout << "✅ YUV420 raw data saved: " << filename << std::endl;
        return true;
    }
    
    // 시스템 정보 출력
    static void printSystemInfo() {
        std::cout << "\n📋 시스템 정보" << std::endl;
        std::cout << "==============" << std::endl;
        
        system("echo '카메라 감지:'");
        system("rpicam-hello --list-cameras 2>/dev/null || echo '카메라를 찾을 수 없습니다'");
        
        std::cout << "\n비디오 디바이스:" << std::endl;
        system("ls -1 /dev/video* | head -5");
        
        std::cout << "\n메모리 사용량:" << std::endl;
        system("free -h | head -2");
    }
};

int main(int argc, char* argv[]) {
    // 시스템 정보 출력
    RpiCamDirect::printSystemInfo();
    
    std::cout << "\n🚀 PRD 목표 테스트 시작" << std::endl;
    
    // 1. 단일 프레임 캡처 (JPEG)
    if (!RpiCamDirect::captureFrames(5)) {
        std::cerr << "Frame capture test failed" << std::endl;
        return -1;
    }
    
    std::cout << "\n" << std::endl;
    
    // 2. YUV420 Raw 캡처 (CPU 최적화)
    if (!RpiCamDirect::captureYUV420()) {
        std::cerr << "YUV420 capture test failed" << std::endl;
        return -1;
    }
    
    std::cout << "\n" << std::endl;
    
    // 3. 연속 비디오 캡처
    if (!RpiCamDirect::captureVideo(3000)) {
        std::cerr << "Video capture test failed" << std::endl;
        return -1;
    }
    
    std::cout << "\n🎉 PRD 목표 달성! rpicam 직접 활용으로 640x480 영상 캡처 성공" << std::endl;
    std::cout << "생성된 파일들:" << std::endl;
    system("ls -lh rpicam_frame_*.jpg rpicam_raw.yuv rpicam_video.h264 2>/dev/null");
    
    return 0;
}