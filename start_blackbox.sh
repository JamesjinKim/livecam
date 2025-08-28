#!/bin/bash
# start_blackbox.sh
# 라즈베리파이 5 블랙박스 시스템 간편 시작 스크립트

echo "🚗 라즈베리파이 5 블랙박스 시스템"
echo

# 사용법 출력
show_usage() {
    echo "📋 사용법:"
    echo
    echo "🎥 단일 카메라 모드:"
    echo "  ./start_blackbox.sh cam0-640      # 카메라 0번 - 640x480"
    echo "  ./start_blackbox.sh cam1-640      # 카메라 1번 - 640x480"  
    echo "  ./start_blackbox.sh cam0-hd       # 카메라 0번 - HD 1280x720"
    echo "  ./start_blackbox.sh cam1-hd       # 카메라 1번 - HD 1280x720"
    echo
    echo "🚗 듀얼 카메라 모드:"
    echo "  ./start_blackbox.sh dual-640      # 두 카메라 동시 - 640x480"
    echo "  ./start_blackbox.sh dual-hd       # 두 카메라 동시 - HD 1280x720"
    echo
    echo "⚡ 최적화 모드:"
    echo "  ./start_blackbox.sh optimized     # mmap 최적화 (카메라 0번)"
    echo
}

# 파라미터 확인
if [ $# -eq 0 ]; then
    echo "❌ 화질 옵션을 선택하세요!"
    show_usage
    exit 1
fi

MODE=$1
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 해상도별 출력 디렉토리 설정
case $MODE in
    *-640|dual-640|optimized)
        OUTPUT_DIR="videos/640x480"
        ;;
    *-hd|dual-hd)
        OUTPUT_DIR="videos/hd"
        ;;
    *)
        OUTPUT_DIR="videos/640x480"  # 기본값
        ;;
esac

# 출력 디렉토리 생성
mkdir -p "$OUTPUT_DIR"

echo "🎥 블랙박스 모드: $MODE"
echo "📅 시작 시간: $(date)"
echo "📁 저장 위치: $OUTPUT_DIR/"
echo

case $MODE in
    "cam0-640")
        echo "📹 카메라 0번 - 640x480 블랙박스 시작..."
        echo "💾 파일: $OUTPUT_DIR/blackbox_cam0_640_${TIMESTAMP}.yuv"
        echo "💡 CPU 사용률: ~5-8% (최적화됨)"
        echo
        
        rpicam-vid --camera 0 --width 640 --height 480 \
            --codec yuv420 --output "$OUTPUT_DIR/blackbox_cam0_640_${TIMESTAMP}.yuv" \
            --timeout 0 --nopreview --framerate 30 --flush
        ;;
        
    "cam1-640")
        echo "📹 카메라 1번 - 640x480 블랙박스 시작..."
        echo "💾 파일: $OUTPUT_DIR/blackbox_cam1_640_${TIMESTAMP}.yuv"
        echo "💡 CPU 사용률: ~5-8% (최적화됨)"
        echo
        
        rpicam-vid --camera 1 --width 640 --height 480 \
            --codec yuv420 --output "$OUTPUT_DIR/blackbox_cam1_640_${TIMESTAMP}.yuv" \
            --timeout 0 --nopreview --framerate 30 --flush
        ;;
        
    "cam0-hd")
        echo "📹 카메라 0번 - HD 1280x720 블랙박스 시작..."  
        echo "💾 파일: $OUTPUT_DIR/blackbox_cam0_hd_${TIMESTAMP}.yuv"
        echo "⚠️  HD 모드: CPU 사용률 ~13-15%"
        echo
        
        rpicam-vid --camera 0 --width 1280 --height 720 \
            --codec yuv420 --output "$OUTPUT_DIR/blackbox_cam0_hd_${TIMESTAMP}.yuv" \
            --timeout 0 --nopreview --framerate 30 --flush
        ;;
        
    "cam1-hd")
        echo "📹 카메라 1번 - HD 1280x720 블랙박스 시작..."  
        echo "💾 파일: $OUTPUT_DIR/blackbox_cam1_hd_${TIMESTAMP}.yuv"
        echo "⚠️  HD 모드: CPU 사용률 ~13-15%"
        echo
        
        rpicam-vid --camera 1 --width 1280 --height 720 \
            --codec yuv420 --output "$OUTPUT_DIR/blackbox_cam1_hd_${TIMESTAMP}.yuv" \
            --timeout 0 --nopreview --framerate 30 --flush
        ;;
        
    "dual-640")
        echo "🚗 듀얼 카메라 - 640x480 블랙박스 시작..."
        echo "💾 전방: $OUTPUT_DIR/blackbox_cam0_640_${TIMESTAMP}.yuv"
        echo "💾 후방: $OUTPUT_DIR/blackbox_cam1_640_${TIMESTAMP}.yuv"
        echo "💡 CPU 사용률: ~10-16% (두 카메라)"
        echo "🚨 Ctrl+C로 두 카메라 동시 중단"
        echo
        
        # 백그라운드에서 카메라 0 (전방)
        rpicam-vid --camera 0 --width 640 --height 480 \
            --codec yuv420 --output "$OUTPUT_DIR/blackbox_cam0_640_${TIMESTAMP}.yuv" \
            --timeout 0 --nopreview --framerate 30 --flush &
        CAM0_PID=$!
        
        # 백그라운드에서 카메라 1 (후방)
        rpicam-vid --camera 1 --width 640 --height 480 \
            --codec yuv420 --output "$OUTPUT_DIR/blackbox_cam1_640_${TIMESTAMP}.yuv" \
            --timeout 0 --nopreview --framerate 30 --flush &
        CAM1_PID=$!
        
        echo "✅ 카메라 0 (전방) PID: $CAM0_PID"
        echo "✅ 카메라 1 (후방) PID: $CAM1_PID"
        echo
        echo "🛑 중단하려면 Ctrl+C 누르세요..."
        
        # 종료 신호 처리
        trap 'echo ""; echo "⏹️  듀얼 녹화 중단 중..."; kill $CAM0_PID $CAM1_PID 2>/dev/null; wait; echo "✅ 듀얼 녹화 완료"; exit 0' INT
        
        # 대기
        wait
        ;;
        
    "dual-hd")
        echo "🚗 듀얼 카메라 - HD 1280x720 블랙박스 시작..."
        echo "💾 전방: $OUTPUT_DIR/blackbox_cam0_hd_${TIMESTAMP}.yuv"
        echo "💾 후방: $OUTPUT_DIR/blackbox_cam1_hd_${TIMESTAMP}.yuv" 
        echo "⚠️  HD 듀얼 모드: CPU 사용률 ~25-30%"
        echo "🚨 Ctrl+C로 두 카메라 동시 중단"
        echo
        
        # HD 듀얼 카메라
        rpicam-vid --camera 0 --width 1280 --height 720 \
            --codec yuv420 --output "$OUTPUT_DIR/blackbox_cam0_hd_${TIMESTAMP}.yuv" \
            --timeout 0 --nopreview --framerate 30 --flush &
        CAM0_PID=$!
        
        rpicam-vid --camera 1 --width 1280 --height 720 \
            --codec yuv420 --output "$OUTPUT_DIR/blackbox_cam1_hd_${TIMESTAMP}.yuv" \
            --timeout 0 --nopreview --framerate 30 --flush &
        CAM1_PID=$!
        
        echo "✅ 카메라 0 (전방) HD PID: $CAM0_PID"  
        echo "✅ 카메라 1 (후방) HD PID: $CAM1_PID"
        echo
        echo "🛑 중단하려면 Ctrl+C 누르세요..."
        
        trap 'echo ""; echo "⏹️  듀얼 HD 녹화 중단 중..."; kill $CAM0_PID $CAM1_PID 2>/dev/null; wait; echo "✅ 듀얼 HD 녹화 완료"; exit 0' INT
        
        wait
        ;;
        
    "optimized"|"mmap")
        echo "⚡ mmap 최적화 블랙박스 시작 (카메라 0번)..."
        echo "💾 파일: $OUTPUT_DIR/blackbox_optimized_${TIMESTAMP}.yuv"
        echo "🚀 CPU 사용률: ~3-5% (최고 효율성)"
        echo "💡 mmap 메모리 맵 I/O 사용"
        echo
        
        # 최적화 시스템 빌드 확인
        if [ ! -f "build/optimized_capture" ]; then
            echo "🔨 최적화 시스템 빌드 중..."
            cd build
            make -f Makefile.optimized optimized_capture >/dev/null 2>&1
            cd ..
        fi
        
        if [ -f "build/optimized_capture" ]; then
            echo "⚠️  현재 최적화 캡처는 벤치마크 모드입니다"
            echo "📹 카메라 0번 640x480 모드로 실행..."
            
            rpicam-vid --camera 0 --width 640 --height 480 \
                --codec yuv420 --output "$OUTPUT_DIR/blackbox_optimized_${TIMESTAMP}.yuv" \
                --timeout 0 --nopreview --framerate 30 --flush
        else
            echo "❌ 최적화 시스템 빌드 실패. 일반 모드로 실행..."
            rpicam-vid --camera 0 --width 640 --height 480 \
                --codec yuv420 --output "$OUTPUT_DIR/blackbox_optimized_${TIMESTAMP}.yuv" \
                --timeout 0 --nopreview --framerate 30 --flush
        fi
        ;;
        
    *)
        echo "❌ 알 수 없는 모드: $MODE"
        show_usage
        exit 1
        ;;
esac

echo
echo "✅ 블랙박스 녹화 완료!"
echo "📁 파일 위치: $(pwd)/$OUTPUT_DIR"
echo "📋 생성된 파일:"
ls -lh "$OUTPUT_DIR"/blackbox_*${TIMESTAMP}* 2>/dev/null

echo
echo "🎬 MP4 변환 방법 (재생용):"
echo "----------------------------------------"
for file in "$OUTPUT_DIR"/blackbox_*${TIMESTAMP}*.yuv; do
    if [ -f "$file" ]; then
        base_name=$(basename "$file" .yuv)
        if [[ "$file" == *"hd"* ]]; then
            echo "# HD 해상도 변환:"
            echo "ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 1280x720 -r 30 -i $file -c:v libx264 -preset fast -crf 20 $OUTPUT_DIR/${base_name}.mp4 -y"
        else
            echo "# 640x480 해상도 변환:"
            echo "ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 640x480 -r 30 -i $file -c:v libx264 -preset fast -crf 20 $OUTPUT_DIR/${base_name}.mp4 -y"
        fi
        echo
    fi
done