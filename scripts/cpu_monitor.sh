#!/bin/bash

# CPU 사용률 모니터링 스크립트
# rpicam HD 캡처 중 실제 CPU 사용률 측정

echo "======================================"
echo "  rpicam HD 캡처 CPU 사용률 테스트"
echo "======================================"

# 1. 대기 상태 CPU 측정 (5초)
echo ""
echo "1단계: 기본 CPU 사용률 측정 (5초)..."
idle_cpu=0
for i in {1..5}; do
    cpu=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    idle_cpu=$(echo "$idle_cpu + $cpu" | bc -l)
    echo -n "."
    sleep 1
done
idle_avg=$(echo "scale=1; $idle_cpu / 5" | bc -l)
echo ""
echo "대기 상태 CPU 사용률: ${idle_avg}%"

# 2. HD 캡처 중 CPU 측정
echo ""
echo "2단계: HD 캡처 중 CPU 사용률 측정..."
echo "rpicam으로 HD 1920x1080 YUV420 캡처 시작"

# 백그라운드로 HD 캡처 실행
rpicam-vid --camera 0 --width 1920 --height 1080 --codec yuv420 --timeout 15000 --output cpu_test.yuv --nopreview > /dev/null 2>&1 &
capture_pid=$!

sleep 2  # 캡처 안정화 대기

# CPU 사용률 모니터링 (10초)
capture_cpu=0
echo "CPU 모니터링 중..."
for i in {1..10}; do
    cpu=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    capture_cpu=$(echo "$capture_cpu + $cpu" | bc -l)
    
    # rpicam 프로세스 CPU 사용률도 확인
    rpicam_cpu=$(top -bn1 | grep -E "rpicam|libcamera" | head -1 | awk '{print $9}' | cut -d'.' -f1)
    if [ ! -z "$rpicam_cpu" ]; then
        echo "  ${i}초: 전체 CPU ${cpu}% | rpicam 프로세스: ${rpicam_cpu}%"
    else
        echo "  ${i}초: 전체 CPU ${cpu}%"
    fi
    sleep 1
done

capture_avg=$(echo "scale=1; $capture_cpu / 10" | bc -l)

# 캡처 프로세스 정리
wait $capture_pid 2>/dev/null

# 3. 결과 분석
echo ""
echo "======================================"
echo "         CPU 사용률 분석 결과"
echo "======================================"
echo "대기 상태 평균 CPU: ${idle_avg}%"
echo "HD 캡처 중 평균 CPU: ${capture_avg}%"

cpu_increase=$(echo "scale=1; $capture_avg - $idle_avg" | bc -l)
echo "순수 캡처 CPU 사용량: ${cpu_increase}%"

# 파일 크기 확인
if [ -f "cpu_test.yuv" ]; then
    filesize=$(stat -c%s "cpu_test.yuv")
    frames=$((filesize / 3110400))
    echo ""
    echo "캡처 정보:"
    echo "  파일 크기: $(echo "scale=1; $filesize / 1024 / 1024" | bc) MB"
    echo "  캡처된 프레임: ${frames}"
    echo "  예상 FPS: $(echo "scale=1; $frames / 15" | bc)"
fi

# 4. DMA 사용 여부 확인
echo ""
echo "======================================"
echo "      메모리 전송 방식 분석"
echo "======================================"

echo "커널 모듈 확인:"
if lsmod | grep -q "videobuf2_dma_contig"; then
    echo "✓ videobuf2_dma_contig 로드됨 - DMA 지원"
fi

if lsmod | grep -q "rp1_cfe"; then
    echo "✓ rp1_cfe (Camera Front End) 로드됨"
fi

if lsmod | grep -q "pisp_be"; then
    echo "✓ pisp_be (ISP Backend) 로드됨"
fi

# 5. 분석 결론
echo ""
echo "======================================"
echo "           분석 결론"
echo "======================================"

if (( $(echo "$cpu_increase < 10" | bc -l) )); then
    echo "📊 판정: DMA 사용 중 (CPU 사용률 10% 미만)"
    echo "✓ rpicam은 DMA를 통해 효율적으로 데이터를 전송합니다"
    echo "✓ ISP 파이프라인이 하드웨어 가속을 제공합니다"
elif (( $(echo "$cpu_increase < 30" | bc -l) )); then
    echo "📊 판정: 부분적 DMA/하드웨어 가속"
    echo "⚠ 일부 처리는 CPU를 사용하지만 DMA도 활용됩니다"
else
    echo "📊 판정: 주로 CPU 처리"
    echo "✗ 대부분의 처리가 CPU에서 수행됩니다"
fi

echo ""
echo "핵심 정보:"
echo "• videobuf2_dma_contig: V4L2 DMA 연속 버퍼 지원"
echo "• rp1_cfe: 카메라 프론트엔드 DMA 전송"
echo "• pisp_be: ISP 백엔드 하드웨어 처리"
echo "• YUV420 변환: ISP 하드웨어에서 수행"

# 정리
rm -f cpu_test.yuv 2>/dev/null

echo ""
echo "테스트 완료!"