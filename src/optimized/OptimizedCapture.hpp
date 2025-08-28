/**
 * OptimizedCapture.hpp
 * 최적화된 영상 캡처를 위한 헤더
 */

#ifndef OPTIMIZED_CAPTURE_HPP
#define OPTIMIZED_CAPTURE_HPP

#include <string>
#include <memory>
#include <functional>

// 캡처 최적화 방법
enum class OptimizationMethod {
    STANDARD_IO,    // 기본 write() 시스템 콜
    MMAP_IO,        // 메모리 맵 I/O
    IO_URING,       // 비동기 I/O (Linux 5.15+)
    RAM_DISK        // tmpfs 활용
};

// 프레임 버퍼 구조체
struct FrameBuffer {
    void* data;
    size_t size;
    size_t offset;
    uint64_t timestamp;
};

// 최적화된 캡처 인터페이스
class IOptimizedCapture {
public:
    virtual ~IOptimizedCapture() = default;
    
    // 초기화
    virtual bool initialize(const std::string& output_path, 
                          size_t estimated_size,
                          OptimizationMethod method) = 0;
    
    // 프레임 쓰기
    virtual bool writeFrame(const FrameBuffer& frame) = 0;
    
    // 비동기 작업 완료 확인
    virtual int processCompletions() = 0;
    
    // 성능 통계
    virtual void getStats(size_t& frames, size_t& bytes, double& cpu_usage) = 0;
    
    // 정리
    virtual void cleanup() = 0;
};

// 팩토리 함수
std::unique_ptr<IOptimizedCapture> createOptimizedCapture(OptimizationMethod method);

// CPU 사용률 모니터링
class CpuMonitor {
private:
    long prev_idle = 0;
    long prev_total = 0;
    
public:
    double getCpuUsage();
    double getProcessCpuUsage(pid_t pid);
};

// 성능 비교 도구
class PerformanceComparator {
public:
    struct Result {
        OptimizationMethod method;
        double avg_cpu_usage;
        double avg_fps;
        double avg_latency_ms;
        size_t total_frames;
    };
    
    // 각 방법별 성능 테스트
    Result testMethod(OptimizationMethod method, 
                     size_t frame_count,
                     size_t frame_size);
    
    // 모든 방법 비교
    void compareAll(size_t frame_count = 300);
    
    // 결과 출력
    void printResults(const std::vector<Result>& results);
};

#endif // OPTIMIZED_CAPTURE_HPP