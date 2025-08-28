#include <iostream>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <linux/videodev2.h>
#include <cstring>
#include <vector>
#include <chrono>
#include <thread>
#include <fstream>

class DmaCaptureHD {
private:
    int fd;
    std::vector<void*> buffers;
    std::vector<size_t> buffer_lengths;
    const int WIDTH = 1920;
    const int HEIGHT = 1080;
    const int BUFFER_COUNT = 6;  // HD용 더 많은 버퍼
    bool use_dma_heap;
    bool use_compression;
    
public:
    DmaCaptureHD() : fd(-1), use_dma_heap(false), use_compression(true) {}
    
    ~DmaCaptureHD() {
        cleanup();
    }
    
    bool init(const char* device = "/dev/video0") {
        // V4L2 디바이스 열기
        fd = open(device, O_RDWR);
        if (fd < 0) {
            std::cerr << "Failed to open device: " << device << std::endl;
            return false;
        }
        
        // 디바이스 capability 확인
        struct v4l2_capability cap;
        if (ioctl(fd, VIDIOC_QUERYCAP, &cap) < 0) {
            std::cerr << "Failed to query capabilities" << std::endl;
            return false;
        }
        
        std::cout << "HD DMA Capture - Device: " << cap.card << std::endl;
        std::cout << "Driver: " << cap.driver << std::endl;
        
        // DMA 지원 확인
        if (cap.capabilities & V4L2_CAP_STREAMING) {
            std::cout << "DMA streaming supported" << std::endl;
        }
        
        // HD 포맷 설정 (1920x1080)
        struct v4l2_format fmt;
        memset(&fmt, 0, sizeof(fmt));
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        fmt.fmt.pix.width = WIDTH;
        fmt.fmt.pix.height = HEIGHT;
        
        // HD는 MJPEG으로 압축하여 DMA 전송 효율 향상
        if (use_compression) {
            fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_MJPEG;
            std::cout << "Using MJPEG compression for HD" << std::endl;
        } else {
            fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUV420;
            std::cout << "Using YUV420 for HD (Warning: high bandwidth)" << std::endl;
        }
        
        fmt.fmt.pix.field = V4L2_FIELD_ANY;
        
        if (ioctl(fd, VIDIOC_S_FMT, &fmt) < 0) {
            std::cerr << "Failed to set HD format" << std::endl;
            // Fallback to YUV420
            fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUV420;
            if (ioctl(fd, VIDIOC_S_FMT, &fmt) < 0) {
                std::cerr << "Failed to set fallback format" << std::endl;
                return false;
            }
        }
        
        std::cout << "HD Format set: " << WIDTH << "x" << HEIGHT << std::endl;
        
        // DMA 버퍼 요청 (HD는 더 많은 버퍼 필요)
        struct v4l2_requestbuffers req;
        memset(&req, 0, sizeof(req));
        req.count = BUFFER_COUNT;
        req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        req.memory = V4L2_MEMORY_MMAP;  // DMA를 위한 MMAP
        
        if (ioctl(fd, VIDIOC_REQBUFS, &req) < 0) {
            std::cerr << "Failed to request buffers" << std::endl;
            return false;
        }
        
        std::cout << "Allocated " << req.count << " HD DMA buffers" << std::endl;
        
        // 버퍼 매핑
        buffers.resize(req.count);
        buffer_lengths.resize(req.count);
        
        for (unsigned int i = 0; i < req.count; i++) {
            struct v4l2_buffer buf;
            memset(&buf, 0, sizeof(buf));
            buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
            buf.memory = V4L2_MEMORY_MMAP;
            buf.index = i;
            
            if (ioctl(fd, VIDIOC_QUERYBUF, &buf) < 0) {
                std::cerr << "Failed to query buffer " << i << std::endl;
                return false;
            }
            
            buffer_lengths[i] = buf.length;
            buffers[i] = mmap(NULL, buf.length, 
                             PROT_READ | PROT_WRITE,
                             MAP_SHARED, fd, buf.m.offset);
                             
            if (buffers[i] == MAP_FAILED) {
                std::cerr << "Failed to mmap HD buffer " << i << std::endl;
                return false;
            }
            
            std::cout << "Mapped HD DMA buffer " << i 
                     << " size: " << buf.length / 1024 << " KB" << std::endl;
        }
        
        // 버퍼를 큐에 넣기
        for (unsigned int i = 0; i < req.count; i++) {
            struct v4l2_buffer buf;
            memset(&buf, 0, sizeof(buf));
            buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
            buf.memory = V4L2_MEMORY_MMAP;
            buf.index = i;
            
            if (ioctl(fd, VIDIOC_QBUF, &buf) < 0) {
                std::cerr << "Failed to queue buffer " << i << std::endl;
                return false;
            }
        }
        
        return true;
    }
    
    bool startCapture() {
        enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        if (ioctl(fd, VIDIOC_STREAMON, &type) < 0) {
            std::cerr << "Failed to start HD streaming" << std::endl;
            return false;
        }
        
        std::cout << "HD DMA streaming started" << std::endl;
        return true;
    }
    
    bool captureFrame(void** data, size_t* size) {
        struct v4l2_buffer buf;
        memset(&buf, 0, sizeof(buf));
        buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        
        // DMA 버퍼에서 HD 프레임 가져오기
        if (ioctl(fd, VIDIOC_DQBUF, &buf) < 0) {
            if (errno == EAGAIN) {
                return false; // 프레임이 아직 준비되지 않음
            }
            std::cerr << "Failed to dequeue HD buffer" << std::endl;
            return false;
        }
        
        *data = buffers[buf.index];
        *size = buf.bytesused;
        
        // 버퍼 다시 큐에 넣기
        if (ioctl(fd, VIDIOC_QBUF, &buf) < 0) {
            std::cerr << "Failed to queue HD buffer" << std::endl;
            return false;
        }
        
        return true;
    }
    
    bool saveFrame(const char* filename) {
        void* data;
        size_t size;
        
        if (!captureFrame(&data, &size)) {
            return false;
        }
        
        std::ofstream file(filename, std::ios::binary);
        if (!file) {
            std::cerr << "Failed to open output file" << std::endl;
            return false;
        }
        
        file.write(static_cast<char*>(data), size);
        file.close();
        
        std::cout << "HD frame saved to " << filename 
                 << " (" << size / 1024 << " KB)" << std::endl;
        return true;
    }
    
    bool stopCapture() {
        enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        if (ioctl(fd, VIDIOC_STREAMOFF, &type) < 0) {
            std::cerr << "Failed to stop HD streaming" << std::endl;
            return false;
        }
        
        std::cout << "HD DMA streaming stopped" << std::endl;
        return true;
    }
    
    void cleanup() {
        if (fd >= 0) {
            stopCapture();
            
            // 버퍼 언매핑
            for (size_t i = 0; i < buffers.size(); i++) {
                if (buffers[i] && buffers[i] != MAP_FAILED) {
                    munmap(buffers[i], buffer_lengths[i]);
                }
            }
            
            close(fd);
            fd = -1;
        }
    }
    
    void benchmark(int seconds = 10) {
        if (!startCapture()) {
            return;
        }
        
        auto start = std::chrono::high_resolution_clock::now();
        int frame_count = 0;
        void* data;
        size_t size;
        size_t total_bytes = 0;
        
        std::cout << "\n=== HD DMA Capture Benchmark (1920x1080) ===" << std::endl;
        
        while (true) {
            auto now = std::chrono::high_resolution_clock::now();
            auto duration = std::chrono::duration_cast<std::chrono::seconds>(now - start);
            
            if (duration.count() >= seconds) {
                break;
            }
            
            if (captureFrame(&data, &size)) {
                frame_count++;
                total_bytes += size;
                
                // 매 초마다 상태 출력
                if (frame_count % 10 == 0) {
                    double fps = frame_count / (duration.count() + 1.0);
                    double mbps = (total_bytes * 8.0) / (1024.0 * 1024.0) / (duration.count() + 1.0);
                    std::cout << "HD Frames: " << frame_count 
                             << ", FPS: " << fps 
                             << ", Bandwidth: " << mbps << " Mbps"
                             << ", Frame size: " << size / 1024 << " KB" << std::endl;
                }
            }
        }
        
        auto end = std::chrono::high_resolution_clock::now();
        auto total_duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
        
        double fps = (frame_count * 1000.0) / total_duration.count();
        double avg_frame_size = total_bytes / (double)frame_count / 1024.0;
        double bandwidth = (total_bytes * 8.0) / (1024.0 * 1024.0) / (total_duration.count() / 1000.0);
        
        std::cout << "\n=== HD Benchmark Results ===" << std::endl;
        std::cout << "Resolution: " << WIDTH << "x" << HEIGHT << std::endl;
        std::cout << "Total frames: " << frame_count << std::endl;
        std::cout << "Duration: " << total_duration.count() << " ms" << std::endl;
        std::cout << "Average FPS: " << fps << std::endl;
        std::cout << "Average frame size: " << avg_frame_size << " KB" << std::endl;
        std::cout << "Bandwidth: " << bandwidth << " Mbps" << std::endl;
        std::cout << "Zero-copy DMA transfers: " << frame_count << std::endl;
        
        stopCapture();
    }
};

int main(int argc, char* argv[]) {
    std::cout << "HD DMA Capture Test (1920x1080 Resolution)" << std::endl;
    std::cout << "===========================================" << std::endl;
    
    DmaCaptureHD capture;
    
    // 카메라 디바이스 선택
    const char* device = "/dev/video0";
    if (argc > 1 && strcmp(argv[1], "-c1") == 0) {
        device = "/dev/video1";
        std::cout << "Using camera 1" << std::endl;
    }
    
    if (!capture.init(device)) {
        std::cerr << "Failed to initialize HD capture" << std::endl;
        return 1;
    }
    
    // 벤치마크 모드
    if (argc > 1 && strcmp(argv[1], "-b") == 0) {
        capture.benchmark();
    }
    // 파일 저장 모드
    else if (argc > 2 && strcmp(argv[1], "-s") == 0) {
        if (!capture.startCapture()) {
            return 1;
        }
        
        // 웜업
        void* data;
        size_t size;
        for (int i = 0; i < 10; i++) {
            capture.captureFrame(&data, &size);
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        
        // HD 프레임 저장
        capture.saveFrame(argv[2]);
        capture.stopCapture();
    }
    // 간단한 테스트
    else {
        if (!capture.startCapture()) {
            return 1;
        }
        
        std::cout << "\nCapturing 30 HD frames..." << std::endl;
        void* data;
        size_t size;
        
        for (int i = 0; i < 30; i++) {
            if (capture.captureFrame(&data, &size)) {
                if (i % 5 == 0) {
                    std::cout << "HD Frame " << i 
                             << " captured, size: " << size / 1024 << " KB" << std::endl;
                }
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(33)); // ~30 FPS
        }
        
        capture.stopCapture();
    }
    
    return 0;
}