#!/bin/bash
# start_blackbox.sh
# 라즈베리파이 5 블랙박스 시스템 간편 시작 스크립트
# 현재 시스템과 통합된 실시간 테스트 가능한 블랙박스

echo "🎥 라즈베리파이 5 블랙박스 시스템"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# 사용법 출력
show_usage() {
    echo "💡 사용법:"
    echo
    echo "📹 단일 카메라 모드 (MP4 직접 녹화):"
    echo "  ./start_blackbox.sh cam0-640      # 카메라 0번 - 640x480"
    echo "  ./start_blackbox.sh cam1-640      # 카메라 1번 - 640x480"  
    echo "  ./start_blackbox.sh cam0-720p     # 카메라 0번 - 1280x720"
    echo "  ./start_blackbox.sh cam1-720p     # 카메라 1번 - 1280x720"
    echo "  ./start_blackbox.sh cam0-1080p    # 카메라 0번 - 1920x1080"
    echo "  ./start_blackbox.sh cam1-1080p    # 카메라 1번 - 1920x1080"
    echo
    echo "🎬 듀얼 카메라 모드:"
    echo "  ./start_blackbox.sh dual-640      # 두 카메라 동시 - 640x480"
    echo "  ./start_blackbox.sh dual-720p     # 두 카메라 동시 - 1280x720"
    echo "  ./start_blackbox.sh dual-1080p    # 두 카메라 동시 - 1920x1080"
    echo
    echo
}

# 파라미터 확인
if [ $# -eq 0 ]; then
    echo "❌ 모드를 선택하세요!"
    show_usage
    exit 1
fi

MODE=$1
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 현재 시스템과 통합된 디렉토리 구조 사용
case $MODE in
    *-640|dual-640|quick)
        OUTPUT_DIR="videos/640x480"
        RES_WIDTH=640
        RES_HEIGHT=480
        ;;
    *-720p|dual-720p)
        OUTPUT_DIR="videos/1280x720"
        RES_WIDTH=1280
        RES_HEIGHT=720
        ;;
    *-1080p|dual-1080p)
        OUTPUT_DIR="videos/1920x1080" 
        RES_WIDTH=1920
        RES_HEIGHT=1080
        ;;
    *)
        OUTPUT_DIR="videos/640x480"  # 기본값
        RES_WIDTH=640
        RES_HEIGHT=480
        ;;
esac

# 카메라별 디렉토리 생성
mkdir -p "$OUTPUT_DIR/cam0"
mkdir -p "$OUTPUT_DIR/cam1"

echo "🎬 블랙박스 모드: $MODE"
echo "⏰ 시작 시간: $(date)"
echo "📁 저장 위치: $OUTPUT_DIR/"
echo "📺 해상도: ${RES_WIDTH}x${RES_HEIGHT}"
echo

case $MODE in
    "cam0-640")
        echo "📷 카메라 0번 - 640x480 MP4 블랙박스 시작..."
        echo "📁 파일: $OUTPUT_DIR/cam0/blackbox_cam0_640_${TIMESTAMP}.mp4"
        echo "🚀 30fps, H.264 인코딩"
        echo "⏹️  Ctrl+C로 중단"
        echo
        
        rpicam-vid --camera 0 --width 640 --height 480 \
            --timeout 0 --framerate 30 --nopreview \
            --output "$OUTPUT_DIR/cam0/blackbox_cam0_640_${TIMESTAMP}.mp4"
        ;;
        
    "cam1-640")
        echo "📷 카메라 1번 - 640x480 MP4 블랙박스 시작..."
        echo "📁 파일: $OUTPUT_DIR/cam1/blackbox_cam1_640_${TIMESTAMP}.mp4"
        echo "🚀 30fps, H.264 인코딩"
        echo "⏹️  Ctrl+C로 중단"
        echo
        
        rpicam-vid --camera 1 --width 640 --height 480 \
            --timeout 0 --framerate 30 --nopreview \
            --output "$OUTPUT_DIR/cam1/blackbox_cam1_640_${TIMESTAMP}.mp4"
        ;;
        
    "cam0-720p")
        echo "📷 카메라 0번 - 720p MP4 블랙박스 시작..."  
        echo "📁 파일: $OUTPUT_DIR/cam0/blackbox_cam0_720p_${TIMESTAMP}.mp4"
        echo "🚀 30fps, H.264 인코딩"
        echo "⏹️  Ctrl+C로 중단"
        echo
        
        rpicam-vid --camera 0 --width 1280 --height 720 \
            --timeout 0 --framerate 30 --nopreview \
            --output "$OUTPUT_DIR/cam0/blackbox_cam0_720p_${TIMESTAMP}.mp4"
        ;;
        
    "cam1-720p")
        echo "📷 카메라 1번 - 720p MP4 블랙박스 시작..."  
        echo "📁 파일: $OUTPUT_DIR/cam1/blackbox_cam1_720p_${TIMESTAMP}.mp4"
        echo "🚀 30fps, H.264 인코딩"
        echo "⏹️  Ctrl+C로 중단"
        echo
        
        rpicam-vid --camera 1 --width 1280 --height 720 \
            --timeout 0 --framerate 30 --nopreview \
            --output "$OUTPUT_DIR/cam1/blackbox_cam1_720p_${TIMESTAMP}.mp4"
        ;;

    "cam0-1080p")
        echo "📷 카메라 0번 - 1080p MP4 블랙박스 시작..."  
        echo "📁 파일: $OUTPUT_DIR/cam0/blackbox_cam0_1080p_${TIMESTAMP}.mp4"
        echo "🚀 30fps, H.264 인코딩"
        echo "⏹️  Ctrl+C로 중단"
        echo
        
        rpicam-vid --camera 0 --width 1920 --height 1080 \
            --timeout 0 --framerate 30 --nopreview \
            --output "$OUTPUT_DIR/cam0/blackbox_cam0_1080p_${TIMESTAMP}.mp4"
        ;;
        
    "cam1-1080p")
        echo "📷 카메라 1번 - 1080p MP4 블랙박스 시작..."  
        echo "📁 파일: $OUTPUT_DIR/cam1/blackbox_cam1_1080p_${TIMESTAMP}.mp4"
        echo "🚀 30fps, H.264 인코딩"
        echo "⏹️  Ctrl+C로 중단"
        echo
        
        rpicam-vid --camera 1 --width 1920 --height 1080 \
            --timeout 0 --framerate 30 --nopreview \
            --output "$OUTPUT_DIR/cam1/blackbox_cam1_1080p_${TIMESTAMP}.mp4"
        ;;
        
    "dual-640")
        echo "🎬 듀얼 카메라 - 640x480 MP4 블랙박스 시작..."
        echo "📁 전방: $OUTPUT_DIR/cam0/blackbox_cam0_640_${TIMESTAMP}.mp4"
        echo "📁 후방: $OUTPUT_DIR/cam1/blackbox_cam1_640_${TIMESTAMP}.mp4"
        echo "🚀 30fps, 듀얼 H.264 인코딩"
        echo "⏹️  Ctrl+C로 두 카메라 동시 중단"
        echo "💡 직접 MP4로 저장"
        echo
        
        # 백그라운드에서 카메라 0 (전방) - 직접 MP4로 저장
        rpicam-vid --camera 0 --width 640 --height 480 \
            --timeout 0 --framerate 30 --nopreview --flush \
            --output "$OUTPUT_DIR/cam0/blackbox_cam0_640_${TIMESTAMP}.mp4" &
        CAM0_PID=$!
        
        # 백그라운드에서 카메라 1 (후방) - 직접 MP4로 저장
        rpicam-vid --camera 1 --width 640 --height 480 \
            --timeout 0 --framerate 30 --nopreview --flush \
            --output "$OUTPUT_DIR/cam1/blackbox_cam1_640_${TIMESTAMP}.mp4" &
        CAM1_PID=$!
        
        echo "✅ 카메라 0 (전방) PID: $CAM0_PID"
        echo "✅ 카메라 1 (후방) PID: $CAM1_PID"
        echo
        echo "🛑 중단하려면 Ctrl+C 누르세요..."
        
        # 종료 신호 처리 - SIGINT 전달로 정상 종료
        trap 'echo ""; echo "⏹️  듀얼 녹화 중단 중..."; 
              echo "   📝 정상 종료 신호 전송 중...";
              kill -INT $CAM0_PID $CAM1_PID 2>/dev/null; 
              echo "   ⏳ MP4 파일 마무리 중... (3초 대기)";
              sleep 3;
              if kill -0 $CAM0_PID 2>/dev/null || kill -0 $CAM1_PID 2>/dev/null; then
                  echo "   ⚠️  강제 종료 실행";
                  kill -TERM $CAM0_PID $CAM1_PID 2>/dev/null;
                  sleep 1;
                  kill -9 $CAM0_PID $CAM1_PID 2>/dev/null;
              fi;
              wait;
              echo "✅ 듀얼 녹화 완료"; 
              echo "📁 저장된 파일:";
              ls -lah "$OUTPUT_DIR"/cam0/blackbox_*640_${TIMESTAMP}.mp4 2>/dev/null;
              ls -lah "$OUTPUT_DIR"/cam1/blackbox_*640_${TIMESTAMP}.mp4 2>/dev/null;
              echo "🎬 영상 정보:";
              ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_DIR"/cam0/blackbox_*640_${TIMESTAMP}.mp4 2>/dev/null | xargs printf "   카메라 0: %.1f초\\n";
              ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_DIR"/cam1/blackbox_*640_${TIMESTAMP}.mp4 2>/dev/null | xargs printf "   카메라 1: %.1f초\\n";
              exit 0' INT
        
        # 대기
        wait
        ;;
        
    "dual-720p")
        echo "🎬 듀얼 카메라 - 720p MP4 블랙박스 시작..."
        echo "📁 전방: $OUTPUT_DIR/cam0/blackbox_cam0_720p_${TIMESTAMP}.mp4"
        echo "📁 후방: $OUTPUT_DIR/cam1/blackbox_cam1_720p_${TIMESTAMP}.mp4" 
        echo "🚀 30fps, 듀얼 H.264 인코딩"
        echo "⏹️  Ctrl+C로 두 카메라 동시 중단"
        echo "💡 직접 MP4로 저장"
        echo
        
        # 720p 듀얼 카메라 - 직접 MP4로 저장
        rpicam-vid --camera 0 --width 1280 --height 720 \
            --timeout 0 --framerate 30 --nopreview --flush \
            --output "$OUTPUT_DIR/cam0/blackbox_cam0_720p_${TIMESTAMP}.mp4" &
        CAM0_PID=$!
        
        rpicam-vid --camera 1 --width 1280 --height 720 \
            --timeout 0 --framerate 30 --nopreview --flush \
            --output "$OUTPUT_DIR/cam1/blackbox_cam1_720p_${TIMESTAMP}.mp4" &
        CAM1_PID=$!
        
        echo "✅ 카메라 0 (전방) 720p PID: $CAM0_PID"  
        echo "✅ 카메라 1 (후방) 720p PID: $CAM1_PID"
        echo
        echo "🛑 중단하려면 Ctrl+C 누르세요..."
        
        trap 'echo ""; echo "⏹️  듀얼 720p 녹화 중단 중..."; 
              echo "   📝 정상 종료 신호 전송 중...";
              kill -INT $CAM0_PID $CAM1_PID 2>/dev/null; 
              echo "   ⏳ MP4 파일 마무리 중... (3초 대기)";
              sleep 3;
              if kill -0 $CAM0_PID 2>/dev/null || kill -0 $CAM1_PID 2>/dev/null; then
                  echo "   ⚠️  강제 종료 실행";
                  kill -TERM $CAM0_PID $CAM1_PID 2>/dev/null;
                  sleep 1;
                  kill -9 $CAM0_PID $CAM1_PID 2>/dev/null;
              fi;
              wait;
              echo "✅ 듀얼 720p 녹화 완료"; 
              echo "📁 저장된 파일:";
              ls -lah "$OUTPUT_DIR"/cam0/blackbox_*720p_${TIMESTAMP}.mp4 2>/dev/null;
              ls -lah "$OUTPUT_DIR"/cam1/blackbox_*720p_${TIMESTAMP}.mp4 2>/dev/null;
              echo "🎬 영상 정보:";
              ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_DIR"/cam0/blackbox_*720p_${TIMESTAMP}.mp4 2>/dev/null | xargs printf "   카메라 0: %.1f초\\n";
              ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_DIR"/cam1/blackbox_*720p_${TIMESTAMP}.mp4 2>/dev/null | xargs printf "   카메라 1: %.1f초\\n";
              exit 0' INT
        
        wait
        ;;

    "dual-1080p")
        echo "🎬 듀얼 카메라 - 1080p MP4 블랙박스 시작..."
        echo "📁 전방: $OUTPUT_DIR/cam0/blackbox_cam0_1080p_${TIMESTAMP}.mp4"
        echo "📁 후방: $OUTPUT_DIR/cam1/blackbox_cam1_1080p_${TIMESTAMP}.mp4" 
        echo "🚀 30fps, 듀얼 H.264 인코딩"
        echo "⏹️  Ctrl+C로 두 카메라 동시 중단"
        echo "💡 직접 MP4로 저장"
        echo
        
        # 1080p 듀얼 카메라 - 직접 MP4로 저장
        rpicam-vid --camera 0 --width 1920 --height 1080 \
            --timeout 0 --framerate 30 --nopreview --flush \
            --output "$OUTPUT_DIR/cam0/blackbox_cam0_1080p_${TIMESTAMP}.mp4" &
        CAM0_PID=$!
        
        rpicam-vid --camera 1 --width 1920 --height 1080 \
            --timeout 0 --framerate 30 --nopreview --flush \
            --output "$OUTPUT_DIR/cam1/blackbox_cam1_1080p_${TIMESTAMP}.mp4" &
        CAM1_PID=$!
        
        echo "✅ 카메라 0 (전방) 1080p PID: $CAM0_PID"  
        echo "✅ 카메라 1 (후방) 1080p PID: $CAM1_PID"
        echo
        echo "🛑 중단하려면 Ctrl+C 누르세요..."
        
        trap 'echo ""; echo "⏹️  듀얼 1080p 녹화 중단 중..."; 
              echo "   📝 정상 종료 신호 전송 중...";
              kill -INT $CAM0_PID $CAM1_PID 2>/dev/null; 
              echo "   ⏳ MP4 파일 마무리 중... (3초 대기)";
              sleep 3;
              if kill -0 $CAM0_PID 2>/dev/null || kill -0 $CAM1_PID 2>/dev/null; then
                  echo "   ⚠️  강제 종료 실행";
                  kill -TERM $CAM0_PID $CAM1_PID 2>/dev/null;
                  sleep 1;
                  kill -9 $CAM0_PID $CAM1_PID 2>/dev/null;
              fi;
              wait;
              echo "✅ 듀얼 1080p 녹화 완료"; 
              echo "📁 저장된 파일:";
              ls -lah "$OUTPUT_DIR"/cam0/blackbox_*1080p_${TIMESTAMP}.mp4 2>/dev/null;
              ls -lah "$OUTPUT_DIR"/cam1/blackbox_*1080p_${TIMESTAMP}.mp4 2>/dev/null;
              echo "🎬 영상 정보:";
              ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_DIR"/cam0/blackbox_*1080p_${TIMESTAMP}.mp4 2>/dev/null | xargs printf "   카메라 0: %.1f초\\n";
              ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_DIR"/cam1/blackbox_*1080p_${TIMESTAMP}.mp4 2>/dev/null | xargs printf "   카메라 1: %.1f초\\n";
              exit 0' INT
        
        wait
        ;;
        
    # stream 모드 제거됨 - 필요한 파일이 없음
        
    # quick 모드 제거됨 - Makefile이 없음
        
    # demo 모드 제거됨 - Makefile이 없음
        
    *)
        echo "❌ 알 수 없는 모드: $MODE"
        show_usage
        exit 1
        ;;
esac

# 녹화 완료 처리
if [[ "$MODE" != "unused_mode" ]]; then
    echo
    echo "✅ 블랙박스 녹화 완료!"
    echo "📁 파일 위치: $(pwd)/$OUTPUT_DIR/"
    echo "📋 생성된 파일:"
    ls -lh "$OUTPUT_DIR"/cam*/blackbox_*${TIMESTAMP}*.mp4 2>/dev/null
    
    echo
    echo "🎬 재생 방법:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "VLC 미디어 플레이어나 기본 동영상 플레이어로 MP4 파일을 직접 재생할 수 있습니다."
    echo
    echo
fi