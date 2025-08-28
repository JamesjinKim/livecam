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
#include <iomanip>

class V4L2DirectCapture {
private:
    int fd;
    std::vector<void*> buffers;
    std::vector<size_t> buffer_lengths;
    const int WIDTH = 1920;
    const int HEIGHT = 1080;
    const int BUFFER_COUNT = 4;
    
    size_t frame_size;
    __u32 pixel_format;
    std::string format_name;
    
public:
    V4L2DirectCapture() : fd(-1), frame_size(0), pixel_format(0) {}
    
    ~V4L2DirectCapture() {
        cleanup();
    }
    
    const char* fourcc_to_string(__u32 fourcc) {
        static char buf[5];
        buf[0] = (fourcc >> 0) & 0xFF;
        buf[1] = (fourcc >> 8) & 0xFF;
        buf[2] = (fourcc >> 16) & 0xFF;
        buf[3] = (fourcc >> 24) & 0xFF;
        buf[4] = '\0';
        return buf;
    }
    
    bool init(const char* device = "/dev/video0") {
        std::cout << "\n=== V4L2 Direct HD Capture ===" << std::endl;
        std::cout << "Target: " << WIDTH << "x" << HEIGHT << " HD" << std::endl;
        
        fd = open(device, O_RDWR | O_NONBLOCK);
        if (fd < 0) {
            std::cerr << "Failed to open: " << device << std::endl;
            return false;
        }
        
        struct v4l2_capability cap;
        if (ioctl(fd, VIDIOC_QUERYCAP, &cap) < 0) {
            std::cerr << "Failed to query capabilities" << std::endl;
            return false;
        }
        
        std::cout << "Device: " << cap.card << std::endl;
        std::cout << "Driver: " << cap.driver << std::endl;
        
        if (!(cap.capabilities & V4L2_CAP_VIDEO_CAPTURE) || !(cap.capabilities & V4L2_CAP_STREAMING)) {
            std::cerr << "✗ Required capabilities missing" << std::endl;
            return false;
        }
        
        std::cout << "✓ Video capture and streaming supported" << std::endl;
        
        if (!selectBestFormat()) {
            return false;
        }
        
        struct v4l2_format fmt;
        memset(&fmt, 0, sizeof(fmt));
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        fmt.fmt.pix.width = WIDTH;
        fmt.fmt.pix.height = HEIGHT;
        fmt.fmt.pix.pixelformat = pixel_format;
        fmt.fmt.pix.field = V4L2_FIELD_INTERLACED;
        
        if (ioctl(fd, VIDIOC_S_FMT, &fmt) < 0) {
            std::cerr << "Failed to set format" << std::endl;
            return false;
        }
        
        if (ioctl(fd, VIDIOC_G_FMT, &fmt) < 0) {
            std::cerr << "Failed to get format" << std::endl;
            return false;
        }
        
        frame_size = fmt.fmt.pix.sizeimage;
        
        std::cout << "✓ Format: " << format_name << " " << fmt.fmt.pix.width << "x" << fmt.fmt.pix.height << std::endl;
        std::cout << "  Frame size: " << frame_size / 1024.0 << " KB" << std::endl;
        
        return allocateBuffers();
    }
    
    bool selectBestFormat() {
        std::cout << "\nScanning formats..." << std::endl;
        
        struct v4l2_fmtdesc fmtdesc;
        memset(&fmtdesc, 0, sizeof(fmtdesc));
        fmtdesc.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        
        std::vector<std::pair<__u32, std::string>> preferred = {
            {V4L2_PIX_FMT_YUYV, "YUYV"},
            {V4L2_PIX_FMT_RGB24, "RGB24"},
            {V4L2_PIX_FMT_MJPEG, "MJPEG"}
        };
        
        std::vector<__u32> available;
        
        while (ioctl(fd, VIDIOC_ENUM_FMT, &fmtdesc) == 0) {
            std::cout << "  [" << fmtdesc.index << "] " << fmtdesc.description << std::endl;
            available.push_back(fmtdesc.pixelformat);
            fmtdesc.index++;
        }
        
        for (const auto& pref : preferred) {
            for (__u32 avail : available) {
                if (avail == pref.first) {
                    pixel_format = avail;
                    format_name = pref.second;
                    std::cout << "✓ Selected: " << format_name << std::endl;
                    return true;
                }
            }
        }
        
        if (!available.empty()) {
            pixel_format = available[0];
            format_name = "Unknown";
            std::cout << "⚠ Using first available format" << std::endl;
            return true;
        }
        
        return false;
    }
    
    bool allocateBuffers() {
        std::cout << "\nAllocating buffers..." << std::endl;
        
        struct v4l2_requestbuffers req;
        memset(&req, 0, sizeof(req));
        req.count = BUFFER_COUNT;
        req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        req.memory = V4L2_MEMORY_MMAP;
        
        if (ioctl(fd, VIDIOC_REQBUFS, &req) < 0) {
            std::cerr << "Failed to request buffers" << std::endl;
            return false;
        }
        
        if (req.count < 2) {
            std::cerr << "Insufficient buffers" << std::endl;
            return false;
        }
        
        std::cout << "✓ Got " << req.count << " buffers" << std::endl;
        
        buffers.resize(req.count);
        buffer_lengths.resize(req.count);
        
        size_t total_mem = 0;
        
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
            total_mem += buf.length;
            
            buffers[i] = mmap(NULL, buf.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, buf.m.offset);
            
            if (buffers[i] == MAP_FAILED) {
                std::cerr << "Failed to map buffer " << i << std::endl;
                return false;
            }
        }
        
        std::cout << "✓ Mapped " << total_mem / (1024.0 * 1024.0) << " MB" << std::endl;
        
        // 버퍼 큐잉
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
            std::cerr << "Failed to start streaming: " << strerror(errno) << std::endl;
            return false;
        }
        
        std::cout << "✓ Streaming started" << std::endl;
        return true;
    }
    
    bool captureFrame(void** data, size_t* size) {
        fd_set fds;
        struct timeval tv;
        
        FD_ZERO(&fds);
        FD_SET(fd, &fds);
        tv.tv_sec = 2;
        tv.tv_usec = 0;
        
        int r = select(fd + 1, &fds, NULL, NULL, &tv);
        if (r <= 0) {
            if (r == 0) std::cerr << "Select timeout" << std::endl;
            return false;
        }
        
        struct v4l2_buffer buf;
        memset(&buf, 0, sizeof(buf));
        buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        
        if (ioctl(fd, VIDIOC_DQBUF, &buf) < 0) {
            if (errno != EAGAIN) {
                std::cerr << "DQBUF error: " << strerror(errno) << std::endl;
            }
            return false;
        }
        
        *data = buffers[buf.index];
        *size = buf.bytesused;
        
        if (ioctl(fd, VIDIOC_QBUF, &buf) < 0) {
            std::cerr << "QBUF error: " << strerror(errno) << std::endl;
            return false;
        }
        
        return true;
    }
    
    bool stopCapture() {
        enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        if (ioctl(fd, VIDIOC_STREAMOFF, &type) < 0) {
            return false;
        }
        std::cout << "✓ Streaming stopped" << std::endl;
        return true;
    }
    
    void cleanup() {
        if (fd >= 0) {
            stopCapture();
            
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
        if (!startCapture()) return;
        
        auto start = std::chrono::high_resolution_clock::now();
        int frames = 0;
        int errors = 0;
        void* data;
        size_t size;
        size_t total_bytes = 0;
        
        std::cout << "\n=== V4L2 HD Benchmark ===" << std::endl;
        std::cout << "Format: " << format_name << " " << WIDTH << "x" << HEIGHT << std::endl;
        
        while (true) {
            auto now = std::chrono::high_resolution_clock::now();
            auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - start);
            
            if (elapsed.count() >= seconds) break;
            
            if (captureFrame(&data, &size)) {
                frames++;
                total_bytes += size;
                
                if (frames % 20 == 0) {
                    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(now - start);
                    double fps = (frames * 1000.0) / ms.count();
                    double mbps = (total_bytes * 8.0 / 1000000.0) / (ms.count() / 1000.0);
                    
                    std::cout << "  [" << elapsed.count() << "s] " << frames 
                             << " frames | " << std::fixed << std::setprecision(1) 
                             << fps << " FPS | " << mbps << " Mbps" << std::endl;
                }
            } else {
                errors++;
                if (errors > 20) break;
            }
        }
        
        auto end = std::chrono::high_resolution_clock::now();
        auto total_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
        
        double avg_fps = (frames * 1000.0) / total_ms.count();
        double avg_mbps = (total_bytes * 8.0 / 1000000.0) / (total_ms.count() / 1000.0);
        
        std::cout << "\n=== Results ===" << std::endl;
        std::cout << "Frames: " << frames << std::endl;
        std::cout << "Duration: " << total_ms.count() << " ms" << std::endl;
        std::cout << "Average FPS: " << std::fixed << std::setprecision(2) << avg_fps << std::endl;
        std::cout << "Data rate: " << avg_mbps << " Mbps" << std::endl;
        std::cout << "Errors: " << errors << std::endl;
        
        if (avg_fps >= 25) {
            std::cout << "✓ Excellent HD performance" << std::endl;
        } else if (avg_fps >= 15) {
            std::cout << "⚠ Acceptable HD performance" << std::endl;
        } else {
            std::cout << "✗ Poor HD performance" << std::endl;
        }
        
        stopCapture();
    }
    
    void testCapture(int num_frames = 5) {
        if (!startCapture()) return;
        
        std::cout << "\n=== HD Capture Test ===" << std::endl;
        
        void* data;
        size_t size;
        
        for (int i = 0; i < num_frames; i++) {
            if (captureFrame(&data, &size)) {
                std::cout << "Frame " << (i+1) << ": " << size / 1024.0 << " KB" << std::endl;
                
                if (i == 0 || i == num_frames-1) {
                    std::string filename = "v4l2_hd_frame_" + std::to_string(i) + ".raw";
                    std::ofstream file(filename, std::ios::binary);
                    if (file) {
                        file.write(static_cast<char*>(data), size);
                        file.close();
                        std::cout << "  Saved: " << filename << std::endl;
                    }
                }
            } else {
                std::cout << "Frame " << (i+1) << ": FAILED" << std::endl;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        
        stopCapture();
    }
};

int main(int argc, char* argv[]) {
    std::cout << "V4L2 Direct HD Capture Test" << std::endl;
    std::cout << "===========================" << std::endl;
    
    V4L2DirectCapture capture;
    
    const char* device = "/dev/video0";
    bool benchmark_mode = false;
    
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-c1") == 0) {
            device = "/dev/video1";
        } else if (strcmp(argv[i], "-b") == 0) {
            benchmark_mode = true;
        }
    }
    
    if (!capture.init(device)) {
        std::cerr << "Failed to initialize capture" << std::endl;
        return 1;
    }
    
    if (benchmark_mode) {
        capture.benchmark(10);
    } else {
        capture.testCapture(5);
    }
    
    std::cout << "\nTest completed!" << std::endl;
    return 0;
}