#!/bin/bash

# HD DMA 캡처 테스트 스크립트
# 1920x1080 해상도 DMA 캡처 성능 테스트

echo "========================================"
echo "  HD DMA Capture Test Suite (1920x1080)"
echo "========================================"

# 색상 코드 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 빌드 확인
check_build() {
    echo -e "${BLUE}1. Checking build requirements...${NC}"
    
    # Makefile.dma 확인
    if [ ! -f "Makefile.dma" ]; then
        echo -e "${RED}✗ Makefile.dma not found${NC}"
        return 1
    fi
    
    # 빌드 실행
    echo "Building HD DMA capture..."
    if make -f Makefile.dma dma_capture_hd 2>/dev/null; then
        echo -e "${GREEN}✓ Build successful${NC}"
        return 0
    else
        echo -e "${RED}✗ Build failed${NC}"
        echo "Attempting to build with verbose output:"
        make -f Makefile.dma dma_capture_hd
        return 1
    fi
}

# 카메라 존재 확인
check_cameras() {
    echo -e "\n${BLUE}2. Checking camera availability...${NC}"
    
    cameras_found=0
    for i in 0 1; do
        if [ -e "/dev/video$i" ]; then
            echo -e "${GREEN}✓ Camera $i found: /dev/video$i${NC}"
            cameras_found=$((cameras_found + 1))
        else
            echo -e "${YELLOW}⚠ Camera $i not found${NC}"
        fi
    done
    
    if [ $cameras_found -eq 0 ]; then
        echo -e "${RED}✗ No cameras found${NC}"
        return 1
    fi
    
    return 0
}

# HD 지원 확인
check_hd_support() {
    echo -e "\n${BLUE}3. Checking HD format support...${NC}"
    
    echo "Querying camera capabilities..."
    if command -v rpicam-hello >/dev/null 2>&1; then
        echo "Available cameras and resolutions:"
        rpicam-hello --list-cameras | grep -E "(1920x1080|1296x972|2592x1944)" || {
            echo -e "${YELLOW}⚠ HD resolutions may not be available${NC}"
        }
    else
        echo -e "${YELLOW}⚠ rpicam-hello not found, skipping capability check${NC}"
    fi
}

# 메모리 확인
check_memory() {
    echo -e "\n${BLUE}4. Checking available memory...${NC}"
    
    # 현재 메모리 사용량
    total_mem=$(free -m | awk '/^Mem:/{print $2}')
    available_mem=$(free -m | awk '/^Mem:/{print $7}')
    
    echo "Total memory: ${total_mem} MB"
    echo "Available memory: ${available_mem} MB"
    
    # HD DMA에 필요한 메모리 계산 (6 buffers × 3MB + overhead)
    required_mem=20  # 약 20MB 필요
    
    if [ $available_mem -gt $required_mem ]; then
        echo -e "${GREEN}✓ Sufficient memory for HD DMA capture${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Limited memory available (${available_mem} MB < ${required_mem} MB)${NC}"
        return 1
    fi
}

# 기본 HD DMA 테스트
test_basic_hd() {
    echo -e "\n${BLUE}5. Basic HD DMA test...${NC}"
    
    if [ ! -x "./dma_capture_hd" ]; then
        echo -e "${RED}✗ dma_capture_hd executable not found${NC}"
        return 1
    fi
    
    echo "Testing HD capture with camera 0..."
    timeout 10 ./dma_capture_hd -c0 -t 3 > hd_test_output.log 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Basic HD test successful${NC}"
        
        # 결과 파일 확인
        if [ -f "hd_frame_0.yuv" ]; then
            file_size=$(stat -c%s "hd_frame_0.yuv")
            expected_size=3110400  # 1920x1080 YUV420
            
            echo "  Captured frame size: $file_size bytes"
            echo "  Expected size: $expected_size bytes"
            
            if [ $file_size -gt $((expected_size - 100000)) ] && [ $file_size -lt $((expected_size + 100000)) ]; then
                echo -e "${GREEN}✓ Frame size looks correct${NC}"
            else
                echo -e "${YELLOW}⚠ Frame size unexpected${NC}"
            fi
        fi
        
        return 0
    else
        echo -e "${RED}✗ Basic HD test failed${NC}"
        echo "Error output:"
        tail -n 10 hd_test_output.log
        return 1
    fi
}

# 성능 벤치마크
test_performance() {
    echo -e "\n${BLUE}6. HD DMA performance benchmark...${NC}"
    
    echo "Running 10-second HD performance test..."
    timeout 15 ./dma_capture_hd -c0 -b > hd_benchmark.log 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Performance test completed${NC}"
        
        # FPS 추출
        fps=$(grep "Average FPS:" hd_benchmark.log | awk '{print $3}' | head -1)
        if [ ! -z "$fps" ]; then
            echo "  Average FPS: $fps"
            
            # FPS 기준 평가
            if (( $(echo "$fps >= 25.0" | bc -l) )); then
                echo -e "${GREEN}✓ Excellent HD performance (≥25 FPS)${NC}"
            elif (( $(echo "$fps >= 20.0" | bc -l) )); then
                echo -e "${YELLOW}⚠ Acceptable HD performance (20-25 FPS)${NC}"
            else
                echo -e "${RED}✗ Poor HD performance (<20 FPS)${NC}"
            fi
        fi
        
        return 0
    else
        echo -e "${RED}✗ Performance test failed or timed out${NC}"
        return 1
    fi
}

# 듀얼 카메라 테스트 (가능한 경우)
test_dual_camera() {
    echo -e "\n${BLUE}7. Dual camera HD test (if available)...${NC}"
    
    if [ ! -e "/dev/video1" ]; then
        echo -e "${YELLOW}⚠ Camera 1 not available, skipping dual test${NC}"
        return 0
    fi
    
    echo "Testing HD capture with camera 1..."
    timeout 10 ./dma_capture_hd -c1 -t 2 > hd_camera1_test.log 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Camera 1 HD test successful${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Camera 1 HD test failed${NC}"
        return 1
    fi
}

# CPU 사용률 모니터링
monitor_cpu_usage() {
    echo -e "\n${BLUE}8. CPU usage monitoring during HD capture...${NC}"
    
    echo "Starting CPU monitoring (5 seconds)..."
    
    # 백그라운드에서 HD 캡처 실행
    timeout 8 ./dma_capture_hd -c0 -t 10 > /dev/null 2>&1 &
    capture_pid=$!
    
    # CPU 사용률 모니터링
    sleep 2  # 캡처가 안정화될 시간
    
    cpu_usage=0
    for i in {1..3}; do
        current_cpu=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
        cpu_usage=$(echo "$cpu_usage + $current_cpu" | bc -l)
        sleep 1
    done
    
    # 평균 계산
    avg_cpu=$(echo "scale=1; $cpu_usage / 3" | bc -l)
    echo "Average CPU usage during HD capture: ${avg_cpu}%"
    
    # CPU 사용률 평가
    if (( $(echo "$avg_cpu <= 30.0" | bc -l) )); then
        echo -e "${GREEN}✓ Low CPU usage for HD${NC}"
    elif (( $(echo "$avg_cpu <= 50.0" | bc -l) )); then
        echo -e "${YELLOW}⚠ Moderate CPU usage${NC}"
    else
        echo -e "${RED}✗ High CPU usage${NC}"
    fi
    
    # 캡처 프로세스 정리
    kill $capture_pid 2>/dev/null || true
    wait $capture_pid 2>/dev/null || true
}

# 파일 정리
cleanup_files() {
    echo -e "\n${BLUE}9. Cleaning up test files...${NC}"
    
    # 테스트 결과 파일들
    test_files=("hd_frame_*.yuv" "hd_test_output.log" "hd_benchmark.log" "hd_camera1_test.log")
    
    for pattern in "${test_files[@]}"; do
        if ls $pattern 1> /dev/null 2>&1; then
            echo "  Removing $pattern..."
            rm -f $pattern
        fi
    done
    
    echo -e "${GREEN}✓ Cleanup completed${NC}"
}

# 테스트 결과 요약
print_summary() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}           HD DMA Test Summary          ${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    echo "Test Date: $(date)"
    echo "Resolution: 1920x1080 (Full HD)"
    echo "DMA Method: V4L2 MMAP (Zero-copy)"
    echo "Expected Frame Size: 3,110,400 bytes (3MB)"
    echo "Buffer Count: 6 buffers (~18MB total)"
    
    if [ -f "hd_benchmark.log" ]; then
        echo -e "\n${GREEN}Performance Results:${NC}"
        grep -E "(Average FPS|Data rate|Total data)" hd_benchmark.log | while IFS= read -r line; do
            echo "  $line"
        done
    fi
}

# 메인 실행
main() {
    echo "Starting HD DMA capture test suite..."
    echo "Time: $(date)"
    echo ""
    
    # 테스트 실행
    check_build || exit 1
    check_cameras || exit 1
    check_hd_support
    check_memory
    test_basic_hd
    test_performance
    test_dual_camera
    monitor_cpu_usage
    print_summary
    
    echo -e "\n${GREEN}HD DMA test suite completed!${NC}"
    
    # 정리 여부 묻기
    echo -e "\nDo you want to clean up test files? [y/N]"
    read -t 10 -n 1 cleanup_choice
    if [[ $cleanup_choice =~ ^[Yy]$ ]]; then
        cleanup_files
    else
        echo -e "\n${YELLOW}Test files preserved for inspection${NC}"
    fi
}

# 스크립트 실행
main "$@"