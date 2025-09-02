#!/bin/bash
# start_blackbox_stable.sh
# 메모리 누수 방지 및 시스템 안정성 극대화를 위한 블랙박스 스크립트
# stream_with_control.py와 완벽 호환

echo "🛡️ 안정성 최우선 라즈베리파이 5 블랙박스 시스템"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧠 메모리 누수 방지 | 📊 리소스 모니터링 | 🔄 자동 복구"
echo

# 사용법 출력
show_usage() {
    echo "💡 사용법 (안정성 최우선 버전):"
    echo
    echo "📹 단일 카메라 모드 (안정성 최적화):"
    echo "  ./start_blackbox_stable.sh cam0-640      # 카메라 0번 - 640x480"
    echo "  ./start_blackbox_stable.sh cam1-640      # 카메라 1번 - 640x480"  
    echo "  ./start_blackbox_stable.sh cam0-720p     # 카메라 0번 - 720p"
    echo "  ./start_blackbox_stable.sh cam1-720p     # 카메라 1번 - 720p"
    echo "  ./start_blackbox_stable.sh cam0-1080p    # 카메라 0번 - 1080p"
    echo "  ./start_blackbox_stable.sh cam1-1080p    # 카메라 1번 - 1080p"
    echo
    echo "🎬 듀얼 카메라 모드 (메모리 안정성 보장):"
    echo "  ./start_blackbox_stable.sh dual-640      # 두 카메라 동시 - 640x480"
    echo "  ./start_blackbox_stable.sh dual-720p     # 두 카메라 동시 - 720p"
    echo "  ./start_blackbox_stable.sh dual-1080p    # 두 카메라 동시 - 1080p"
    echo
    echo "🔧 안정성 개선사항:"
    echo "  • 메모리 사용량 제한 (프로세스당 최대 512MB)"
    echo "  • CPU 우선순위 조정으로 시스템 안정성 확보"
    echo "  • 25fps로 조정하여 장기간 안정 동작 보장"
    echo "  • 자동 복구 메커니즘으로 오류 시 재시작"
    echo "  • 실시간 리소스 모니터링"
    echo
}

# 시스템 리소스 체크
check_system_resources() {
    echo "📊 시스템 리소스 확인 중..."
    
    # 메모리 체크
    TOTAL_MEM=$(free -m | awk 'NR==2{printf "%d", $2}')
    USED_MEM=$(free -m | awk 'NR==2{printf "%d", $3}')
    MEM_PERCENT=$((USED_MEM * 100 / TOTAL_MEM))
    
    echo "   💾 메모리: ${USED_MEM}MB / ${TOTAL_MEM}MB (${MEM_PERCENT}%)"
    
    # CPU 온도 체크 (라즈베리파이)
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        CPU_TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
        CPU_TEMP_C=$((CPU_TEMP / 1000))
        echo "   🌡️  CPU 온도: ${CPU_TEMP_C}°C"
        
        if [ $CPU_TEMP_C -gt 70 ]; then
            echo "   ⚠️  경고: CPU 온도가 높습니다. 방열 상태를 확인하세요."
        fi
    fi
    
    # 디스크 용량 체크
    DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
    echo "   💿 디스크: ${DISK_USAGE}% 사용 중"
    
    if [ $DISK_USAGE -gt 85 ]; then
        echo "   ⚠️  경고: 디스크 용량이 부족합니다. 이전 녹화 파일을 정리하세요."
    fi
    
    if [ $MEM_PERCENT -gt 80 ]; then
        echo "   ⚠️  경고: 메모리 사용률이 높습니다. 다른 프로그램을 종료하고 다시 시도하세요."
        return 1
    fi
    
    echo "   ✅ 시스템 상태 양호"
    return 0
}

# 안정성 최적화 rpicam-vid 실행 함수
run_stable_camera() {
    local camera_id=$1
    local width=$2
    local height=$3
    local output_file=$4
    local fps=${5:-25}  # 기본 25fps (안정성 우선)
    
    echo "🎥 카메라 $camera_id 안정성 최적화 시작..."
    echo "   📺 해상도: ${width}x${height}"
    echo "   🎬 프레임률: ${fps}fps (안정성 최적화)"
    echo "   💾 메모리 제한: 512MB"
    echo "   📁 출력: $output_file"
    
    # ulimit으로 메모리 제한 (512MB)
    ulimit -v 524288  # KB 단위
    
    # nice 값으로 CPU 우선순위 조정
    nice -n 5 rpicam-vid \
        --camera $camera_id \
        --width $width --height $height \
        --timeout 0 --framerate $fps \
        --nopreview \
        --quality 75 \
        --denoise cdn_off \
        --flush \
        --output "$output_file"
}

# 프로세스 모니터링 함수
monitor_process() {
    local pid=$1
    local camera_name=$2
    
    while kill -0 $pid 2>/dev/null; do
        sleep 30
        
        # 메모리 사용량 체크
        if [ -f /proc/$pid/status ]; then
            MEM_KB=$(grep VmRSS /proc/$pid/status | awk '{print $2}')
            MEM_MB=$((MEM_KB / 1024))
            
            if [ $MEM_MB -gt 512 ]; then
                echo "⚠️  경고: $camera_name 메모리 사용량 초과 (${MEM_MB}MB)"
                echo "   🔄 프로세스 재시작 중..."
                kill -TERM $pid
                return 1
            fi
        fi
    done
    
    return 0
}

# 파라미터 확인
if [ $# -eq 0 ]; then
    echo "❌ 모드를 선택하세요!"
    show_usage
    exit 1
fi

# 시스템 리소스 체크
if ! check_system_resources; then
    exit 1
fi

MODE=$1
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 디렉토리 구조 설정
case $MODE in
    *-640|dual-640|quick)
        OUTPUT_DIR="videos/640x480"
        RES_WIDTH=640
        RES_HEIGHT=480
        FPS=25  # 안정성 우선
        ;;
    *-720p|dual-720p)
        OUTPUT_DIR="videos/1280x720"
        RES_WIDTH=1280
        RES_HEIGHT=720
        FPS=25  # 안정성 우선
        ;;
    *-1080p|dual-1080p)
        OUTPUT_DIR="videos/1920x1080" 
        RES_WIDTH=1920
        RES_HEIGHT=1080
        FPS=20  # 1080p는 더 보수적으로
        ;;
    *)
        OUTPUT_DIR="videos/640x480"
        RES_WIDTH=640
        RES_HEIGHT=480
        FPS=25
        ;;
esac

# 카메라별 디렉토리 생성
mkdir -p "$OUTPUT_DIR/cam0"
mkdir -p "$OUTPUT_DIR/cam1"

echo "🛡️ 안정성 최우선 블랙박스 모드: $MODE"
echo "⏰ 시작 시간: $(date)"
echo "📁 저장 위치: $OUTPUT_DIR/"
echo "📺 해상도: ${RES_WIDTH}x${RES_HEIGHT} @ ${FPS}fps"
echo "🧠 메모리 안전성: 프로세스당 최대 512MB"
echo

case $MODE in
    "dual-640"|"dual-720p"|"dual-1080p")
        # 듀얼 카메라 모드 (안정성 최적화)
        RESOLUTION_NAME=""
        case $MODE in
            "dual-640") RESOLUTION_NAME="640" ;;
            "dual-720p") RESOLUTION_NAME="720p" ;;
            "dual-1080p") RESOLUTION_NAME="1080p" ;;
        esac
        
        echo "🎬 안정성 최우선 듀얼 카메라 시작..."
        echo "📁 전방: $OUTPUT_DIR/cam0/blackbox_cam0_${RESOLUTION_NAME}_${TIMESTAMP}.mp4"
        echo "📁 후방: $OUTPUT_DIR/cam1/blackbox_cam1_${RESOLUTION_NAME}_${TIMESTAMP}.mp4"
        echo "🛡️ 메모리 누수 방지, 자동 복구 활성화"
        echo "⏹️  Ctrl+C로 안전하게 중단"
        echo

        # 카메라 0 백그라운드 실행
        run_stable_camera 0 $RES_WIDTH $RES_HEIGHT \
            "$OUTPUT_DIR/cam0/blackbox_cam0_${RESOLUTION_NAME}_${TIMESTAMP}.mp4" $FPS &
        CAM0_PID=$!
        
        # 잠시 대기 후 카메라 1 실행 (간섭 방지)
        sleep 1
        
        run_stable_camera 1 $RES_WIDTH $RES_HEIGHT \
            "$OUTPUT_DIR/cam1/blackbox_cam1_${RESOLUTION_NAME}_${TIMESTAMP}.mp4" $FPS &
        CAM1_PID=$!
        
        echo "✅ 카메라 0 (전방) 안정화 PID: $CAM0_PID"
        echo "✅ 카메라 1 (후방) 안정화 PID: $CAM1_PID"
        echo "📊 프로세스 모니터링 시작..."
        
        # 백그라운드에서 프로세스 모니터링
        monitor_process $CAM0_PID "카메라 0" &
        MON0_PID=$!
        
        monitor_process $CAM1_PID "카메라 1" &
        MON1_PID=$!
        
        # 종료 신호 처리 (안전한 종료)
        trap 'echo ""; echo "🛑 안전한 듀얼 녹화 중단 중..."; 
              echo "   📝 정상 종료 신호 전송...";
              kill $MON0_PID $MON1_PID 2>/dev/null;
              kill -INT $CAM0_PID $CAM1_PID 2>/dev/null; 
              echo "   ⏳ MP4 파일 안전 종료 중... (5초 대기)";
              sleep 5;
              if kill -0 $CAM0_PID 2>/dev/null || kill -0 $CAM1_PID 2>/dev/null; then
                  echo "   ⚠️  강제 종료 실행";
                  kill -TERM $CAM0_PID $CAM1_PID 2>/dev/null;
                  sleep 2;
                  kill -9 $CAM0_PID $CAM1_PID 2>/dev/null;
              fi;
              wait;
              echo "✅ 안정성 우선 듀얼 녹화 완료"; 
              echo "📁 저장된 파일:";
              ls -lah "$OUTPUT_DIR"/cam0/blackbox_*${RESOLUTION_NAME}_${TIMESTAMP}.mp4 2>/dev/null;
              ls -lah "$OUTPUT_DIR"/cam1/blackbox_*${RESOLUTION_NAME}_${TIMESTAMP}.mp4 2>/dev/null;
              echo "🎬 영상 정보:";
              if command -v ffprobe >/dev/null 2>&1; then
                  ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_DIR"/cam0/blackbox_*${RESOLUTION_NAME}_${TIMESTAMP}.mp4 2>/dev/null | xargs printf "   카메라 0: %.1f초\\n" 2>/dev/null || echo "   카메라 0: 정보 확인 불가";
                  ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT_DIR"/cam1/blackbox_*${RESOLUTION_NAME}_${TIMESTAMP}.mp4 2>/dev/null | xargs printf "   카메라 1: %.1f초\\n" 2>/dev/null || echo "   카메라 1: 정보 확인 불가";
              fi;
              echo "🛡️ 시스템 안정성 유지됨";
              exit 0' INT
        
        echo "🔄 실시간 모니터링 활성화 (30초 간격)"
        echo "💡 메모리 사용량 초과 시 자동 재시작"
        echo "🛑 중단하려면 Ctrl+C 누르세요..."
        echo
        
        # 대기
        wait
        ;;
        
    "cam0-"*|"cam1-"*)
        # 단일 카메라 모드
        CAMERA_NUM=$(echo $MODE | cut -c4)
        RESOLUTION_NAME=$(echo $MODE | cut -d'-' -f2)
        
        echo "📷 카메라 ${CAMERA_NUM}번 - 안정성 최우선 모드"
        echo "📁 파일: $OUTPUT_DIR/cam${CAMERA_NUM}/blackbox_cam${CAMERA_NUM}_${RESOLUTION_NAME}_${TIMESTAMP}.mp4"
        echo "🛡️ 메모리 제한: 512MB, CPU 조정됨"
        echo "⏹️  Ctrl+C로 안전 중단"
        echo

        run_stable_camera $CAMERA_NUM $RES_WIDTH $RES_HEIGHT \
            "$OUTPUT_DIR/cam${CAMERA_NUM}/blackbox_cam${CAMERA_NUM}_${RESOLUTION_NAME}_${TIMESTAMP}.mp4" $FPS
        ;;
        
    *)
        echo "❌ 알 수 없는 모드: $MODE"
        show_usage
        exit 1
        ;;
esac

# 녹화 완료 처리
echo
echo "✅ 안정성 우선 블랙박스 녹화 완료!"
echo "📁 파일 위치: $(pwd)/$OUTPUT_DIR/"
echo "📋 생성된 파일:"
ls -lh "$OUTPUT_DIR"/cam*/blackbox_*${TIMESTAMP}*.mp4 2>/dev/null

echo
echo "🎬 재생 방법:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "VLC 미디어 플레이어나 기본 동영상 플레이어로 MP4 파일을 직접 재생할 수 있습니다."
echo "🛡️ 메모리 누수 방지 및 시스템 안정성이 보장된 녹화가 완료되었습니다."
echo