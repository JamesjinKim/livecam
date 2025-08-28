/**
 * OptimizedCapture.cpp
 * mmap() 및 io_uring을 활용한 최적화된 영상 캡처
 */

#include <iostream>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <chrono>
#include <thread>
#include <vector>
#include <atomic>

// io_uring 헤더 (Linux 5.15+)
#ifdef USE_IO_URING
#ifdef __has_include
#if __has_include(<liburing.h>)
#include <liburing.h>
#else
#undef USE_IO_URING
#warning "liburing.h not found, io_uring disabled"
#endif
#else
#include <liburing.h>
#endif
#endif

class OptimizedCapture {
private:
    // mmap 관련 변수
    void* mapped_region = nullptr;
    size_t mapped_size = 0;
    int fd = -1;
    
    // 성능 측정
    std::atomic<size_t> bytes_written{0};
    std::atomic<size_t> frames_written{0};
    
#ifdef USE_IO_URING
    struct io_uring ring;
    bool ring_initialized = false;
#endif

public:
    OptimizedCapture() = default;
    ~OptimizedCapture() {
        cleanup();
    }
    
    // 방법 1: mmap() 기반 파일 I/O
    bool setupMmapFile(const std::string& filename, size_t total_size) {
        // 파일 생성 및 크기 설정
        fd = open(filename.c_str(), O_RDWR | O_CREAT | O_TRUNC, 0644);
        if (fd < 0) {
            perror("open");
            return false;
        }
        
        // 파일 크기 미리 할당
        if (ftruncate(fd, total_size) < 0) {
            perror("ftruncate");
            close(fd);
            return false;
        }
        
        // 메모리 맵 생성
        mapped_region = mmap(nullptr, total_size, 
                           PROT_READ | PROT_WRITE, 
                           MAP_SHARED, fd, 0);
        
        if (mapped_region == MAP_FAILED) {
            perror("mmap");
            close(fd);
            return false;
        }
        
        mapped_size = total_size;
        std::cout << "✅ mmap 설정 완료: " << filename 
                  << " (" << total_size / 1024 / 1024 << " MB)" << std::endl;
        return true;
    }
    
    // mmap으로 프레임 쓰기 (DMA 버퍼에서 직접 복사)
    bool writeFrameMmap(const void* frame_data, size_t frame_size, size_t offset) {
        if (!mapped_region || offset + frame_size > mapped_size) {
            std::cerr << "❌ mmap 범위 초과" << std::endl;
            return false;
        }
        
        // DMA 버퍼에서 mmap 영역으로 직접 복사
        // CPU는 메모리 복사만 수행, 실제 디스크 쓰기는 커널이 비동기로 처리
        char* dest = static_cast<char*>(mapped_region) + offset;
        memcpy(dest, frame_data, frame_size);
        
        // 선택적: 즉시 디스크 동기화 (성능 vs 안정성 트레이드오프)
        // msync(dest, frame_size, MS_ASYNC);  // 비동기 동기화
        
        bytes_written += frame_size;
        frames_written++;
        
        return true;
    }
    
#ifdef USE_IO_URING
    // 방법 2: io_uring 비동기 I/O 설정
    bool setupIoUring(const std::string& filename, unsigned queue_depth = 64) {
        // 파일 열기
        fd = open(filename.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_DIRECT, 0644);
        if (fd < 0) {
            perror("open");
            return false;
        }
        
        // io_uring 초기화
        if (io_uring_queue_init(queue_depth, &ring, 0) < 0) {
            perror("io_uring_queue_init");
            close(fd);
            return false;
        }
        
        ring_initialized = true;
        std::cout << "✅ io_uring 설정 완료: " << filename 
                  << " (큐 깊이: " << queue_depth << ")" << std::endl;
        return true;
    }
    
    // io_uring으로 비동기 프레임 쓰기
    bool writeFrameAsync(const void* frame_data, size_t frame_size, off_t offset) {
        if (!ring_initialized) {
            std::cerr << "❌ io_uring 초기화되지 않음" << std::endl;
            return false;
        }
        
        // SQE (Submission Queue Entry) 가져오기
        struct io_uring_sqe* sqe = io_uring_get_sqe(&ring);
        if (!sqe) {
            std::cerr << "❌ SQE 가져오기 실패" << std::endl;
            return false;
        }
        
        // 쓰기 작업 준비
        io_uring_prep_write(sqe, fd, frame_data, frame_size, offset);
        sqe->user_data = reinterpret_cast<uintptr_t>(this);
        
        // 작업 제출 (비동기, CPU 즉시 반환)
        if (io_uring_submit(&ring) < 0) {
            perror("io_uring_submit");
            return false;
        }
        
        bytes_written += frame_size;
        frames_written++;
        
        return true;
    }
    
    // 완료된 비동기 작업 처리
    int processCompletions(unsigned wait_nr = 1) {
        if (!ring_initialized) return 0;
        
        struct io_uring_cqe* cqe;
        unsigned completed = 0;
        
        // 완료된 작업 확인
        for (unsigned i = 0; i < wait_nr; i++) {
            if (io_uring_wait_cqe(&ring, &cqe) < 0) {
                break;
            }
            
            if (cqe->res < 0) {
                std::cerr << "❌ 비동기 쓰기 실패: " << strerror(-cqe->res) << std::endl;
            } else {
                completed++;
            }
            
            io_uring_cqe_seen(&ring, cqe);
        }
        
        return completed;
    }
#endif
    
    // 방법 3: RAM 디스크 (tmpfs) 활용
    bool setupRamDisk(const std::string& filename, size_t size) {
        // /dev/shm은 자동으로 tmpfs (RAM 디스크)
        std::string ram_path = "/dev/shm/" + filename;
        return setupMmapFile(ram_path, size);
    }
    
    // 성능 통계 출력
    void printStats() {
        double mb_written = bytes_written.load() / (1024.0 * 1024.0);
        std::cout << "\n📊 성능 통계:" << std::endl;
        std::cout << "  - 프레임 수: " << frames_written.load() << std::endl;
        std::cout << "  - 데이터 크기: " << mb_written << " MB" << std::endl;
    }
    
    // 정리
    void cleanup() {
        if (mapped_region && mapped_region != MAP_FAILED) {
            msync(mapped_region, mapped_size, MS_SYNC);  // 최종 동기화
            munmap(mapped_region, mapped_size);
            mapped_region = nullptr;
        }
        
#ifdef USE_IO_URING
        if (ring_initialized) {
            io_uring_queue_exit(&ring);
            ring_initialized = false;
        }
#endif
        
        if (fd >= 0) {
            close(fd);
            fd = -1;
        }
    }
};

// 성능 벤치마크
void benchmarkMmap() {
    std::cout << "\n🔬 mmap() 벤치마크 시작\n" << std::endl;
    
    OptimizedCapture capture;
    const size_t frame_size = 640 * 480 * 3 / 2;  // YUV420
    const size_t num_frames = 300;  // 10초 @ 30fps
    const size_t total_size = frame_size * num_frames;
    
    // 더미 프레임 데이터
    std::vector<uint8_t> frame_data(frame_size, 0x80);
    
    // mmap 설정
    if (!capture.setupMmapFile("benchmark_mmap.yuv", total_size)) {
        std::cerr << "mmap 설정 실패" << std::endl;
        return;
    }
    
    // CPU 사용률 측정을 위한 시작 시간
    auto start = std::chrono::high_resolution_clock::now();
    
    // 프레임 쓰기
    for (size_t i = 0; i < num_frames; i++) {
        size_t offset = i * frame_size;
        if (!capture.writeFrameMmap(frame_data.data(), frame_size, offset)) {
            break;
        }
        
        // 30fps 시뮬레이션
        std::this_thread::sleep_for(std::chrono::milliseconds(33));
    }
    
    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
    
    capture.printStats();
    std::cout << "  - 소요 시간: " << duration << " ms" << std::endl;
    std::cout << "  - 실제 FPS: " << (num_frames * 1000.0 / duration) << std::endl;
}

#ifdef USE_IO_URING
void benchmarkIoUring() {
    std::cout << "\n🔬 io_uring 벤치마크 시작\n" << std::endl;
    
    OptimizedCapture capture;
    const size_t frame_size = 640 * 480 * 3 / 2;  // YUV420
    const size_t num_frames = 300;  // 10초 @ 30fps
    
    // 더미 프레임 데이터 (페이지 정렬 필요)
    void* frame_data;
    if (posix_memalign(&frame_data, 4096, frame_size) != 0) {
        std::cerr << "메모리 정렬 실패" << std::endl;
        return;
    }
    memset(frame_data, 0x80, frame_size);
    
    // io_uring 설정
    if (!capture.setupIoUring("benchmark_iouring.yuv")) {
        free(frame_data);
        return;
    }
    
    auto start = std::chrono::high_resolution_clock::now();
    
    // 비동기 프레임 쓰기
    for (size_t i = 0; i < num_frames; i++) {
        off_t offset = i * frame_size;
        if (!capture.writeFrameAsync(frame_data, frame_size, offset)) {
            break;
        }
        
        // 주기적으로 완료 처리
        if (i % 10 == 0) {
            capture.processCompletions(10);
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(33));
    }
    
    // 남은 작업 완료 대기
    capture.processCompletions(num_frames);
    
    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
    
    capture.printStats();
    std::cout << "  - 소요 시간: " << duration << " ms" << std::endl;
    std::cout << "  - 실제 FPS: " << (num_frames * 1000.0 / duration) << std::endl;
    
    free(frame_data);
}
#endif

int main(int argc, char* argv[]) {
    std::cout << "🚀 최적화된 영상 캡처 시스템\n" << std::endl;
    std::cout << "라즈베리파이 5 CPU 부하 감소 기법 데모\n" << std::endl;
    
    // mmap 벤치마크
    benchmarkMmap();
    
#ifdef USE_IO_URING
    // io_uring 벤치마크 (커널 5.15+ 필요)
    benchmarkIoUring();
#else
    std::cout << "\n⚠️  io_uring은 Linux 5.15+ 커널과 liburing이 필요합니다." << std::endl;
    std::cout << "   현재 커널 버전을 확인하세요: uname -r" << std::endl;
#endif
    
    std::cout << "\n✅ 벤치마크 완료" << std::endl;
    return 0;
}