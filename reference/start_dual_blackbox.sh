#!/bin/bash

# 완전 독립적 듀얼 카메라 모션 블랙박스 시스템 시작 스크립트
# 카메라 0번과 카메라 1번을 완전히 분리된 프로세스로 실행

set -e  # 오류 시 즉시 종료

echo "🚀 완전 독립적 듀얼 카메라 블랙박스 시스템 시작 중..."

# 기존 프로세스 정리
cleanup_existing_processes() {
    echo "🧹 기존 블랙박스 프로세스 정리 중..."
    
    # 기존 motion_blackbox 프로세스들 종료
    pkill -f "python3.*motion_blackbox" 2>/dev/null || true
    pkill -f "motion_blackbox_cam" 2>/dev/null || true
    
    # rpicam-vid 프로세스들 정리 (블랙박스 관련)
    pkill -f "rpicam-vid.*motion_event" 2>/dev/null || true
    
    sleep 2
    echo "✅ 기존 프로세스 정리 완료"
}

# 카메라 연결 확인
check_cameras() {
    echo "📹 카메라 연결 확인 중..."
    
    # 카메라 목록 가져오기
    camera_output=$(rpicam-hello --list-cameras 2>&1)
    
    # 카메라 0번 확인
    if echo "$camera_output" | grep -q "^0 :"; then
        echo "✅ 카메라 0번 감지됨"
        CAMERA0_AVAILABLE=true
    else
        echo "❌ 카메라 0번 미감지"
        CAMERA0_AVAILABLE=false
    fi
    
    # 카메라 1번 확인
    if echo "$camera_output" | grep -q "^1 :"; then
        echo "✅ 카메라 1번 감지됨"
        CAMERA1_AVAILABLE=true
    else
        echo "❌ 카메라 1번 미감지"
        CAMERA1_AVAILABLE=false
    fi
    
    if [ "$CAMERA0_AVAILABLE" = false ] && [ "$CAMERA1_AVAILABLE" = false ]; then
        echo "❌ 사용 가능한 카메라가 없습니다!"
        exit 1
    fi
}

# 디렉터리 준비
prepare_directories() {
    echo "📁 디렉터리 생성 중..."
    
    # 카메라별 이벤트 저장 디렉터리 생성 (일별 폴더)
    current_date=$(date +%Y_%m_%d)
    
    if [ "$CAMERA0_AVAILABLE" = true ]; then
        mkdir -p videos/events/cam0/$current_date
        echo "✅ 카메라 0번 저장 디렉터리: videos/events/cam0/$current_date"
    fi
    
    if [ "$CAMERA1_AVAILABLE" = true ]; then
        mkdir -p videos/events/cam1/$current_date
        echo "✅ 카메라 1번 저장 디렉터리: videos/events/cam1/$current_date"
    fi
    
    # 연속 녹화용 디렉터리도 준비 (레거시 지원)
    mkdir -p videos/captures/{640x480,1280x720,1920x1080}/{cam0,cam1}
    
    echo "✅ 저장 디렉터리 준비 완료"
}

# PID 파일 관리
PID_DIR="/tmp/dual_blackbox"
mkdir -p "$PID_DIR"

CAM0_PID_FILE="$PID_DIR/cam0.pid"
CAM1_PID_FILE="$PID_DIR/cam1.pid"

# 종료 신호 처리
cleanup_and_exit() {
    echo ""
    echo "📡 종료 신호 수신 - 듀얼 카메라 시스템 정리 중..."
    
    # 카메라 0번 프로세스 종료
    if [ -f "$CAM0_PID_FILE" ]; then
        CAM0_PID=$(cat "$CAM0_PID_FILE")
        if kill -0 "$CAM0_PID" 2>/dev/null; then
            echo "🛑 카메라 0번 프로세스 종료 중... (PID: $CAM0_PID)"
            kill -INT "$CAM0_PID" 2>/dev/null || true
            
            # 정상 종료 대기 (10초)
            for i in {1..10}; do
                if ! kill -0 "$CAM0_PID" 2>/dev/null; then
                    echo "✅ 카메라 0번 정상 종료"
                    break
                fi
                sleep 1
            done
            
            # 여전히 실행 중이면 강제 종료
            if kill -0 "$CAM0_PID" 2>/dev/null; then
                echo "⚠️ 카메라 0번 강제 종료"
                kill -KILL "$CAM0_PID" 2>/dev/null || true
            fi
        fi
        rm -f "$CAM0_PID_FILE"
    fi
    
    # 카메라 1번 프로세스 종료
    if [ -f "$CAM1_PID_FILE" ]; then
        CAM1_PID=$(cat "$CAM1_PID_FILE")
        if kill -0 "$CAM1_PID" 2>/dev/null; then
            echo "🛑 카메라 1번 프로세스 종료 중... (PID: $CAM1_PID)"
            kill -INT "$CAM1_PID" 2>/dev/null || true
            
            # 정상 종료 대기 (10초)
            for i in {1..10}; do
                if ! kill -0 "$CAM1_PID" 2>/dev/null; then
                    echo "✅ 카메라 1번 정상 종료"
                    break
                fi
                sleep 1
            done
            
            # 여전히 실행 중이면 강제 종료
            if kill -0 "$CAM1_PID" 2>/dev/null; then
                echo "⚠️ 카메라 1번 강제 종료"
                kill -KILL "$CAM1_PID" 2>/dev/null || true
            fi
        fi
        rm -f "$CAM1_PID_FILE"
    fi
    
    # PID 디렉터리 정리
    rmdir "$PID_DIR" 2>/dev/null || true
    
    echo "✅ 완전 독립적 듀얼 카메라 블랙박스 시스템 종료 완료"
    exit 0
}

# 신호 처리 등록
trap cleanup_and_exit INT TERM

# 메인 실행
main() {
    # 초기 설정
    cleanup_existing_processes
    check_cameras
    prepare_directories
    
    echo ""
    echo "🎬 완전 독립적 듀얼 카메라 블랙박스 시작!"
    echo "   각 카메라는 완전히 독립적인 프로세스로 실행됩니다"
    echo ""
    
    # 카메라 0번 시작 (사용 가능한 경우)
    if [ "$CAMERA0_AVAILABLE" = true ]; then
        echo "🚀 카메라 0번 독립 블랙박스 시작 중..."
        python3 motion_blackbox_cam0.py &
        CAM0_PID=$!
        echo $CAM0_PID > "$CAM0_PID_FILE"
        echo "✅ 카메라 0번 시작됨 (PID: $CAM0_PID)"
        
        # 카메라 0번 시작 대기
        sleep 3
    else
        echo "⚠️ 카메라 0번 건너뜀 (미감지)"
        CAM0_PID=""
    fi
    
    # 카메라 1번 시작 (사용 가능한 경우)
    if [ "$CAMERA1_AVAILABLE" = true ]; then
        echo "🚀 카메라 1번 독립 블랙박스 시작 중..."
        python3 motion_blackbox_cam1.py &
        CAM1_PID=$!
        echo $CAM1_PID > "$CAM1_PID_FILE"
        echo "✅ 카메라 1번 시작됨 (PID: $CAM1_PID)"
        
        # 카메라 1번 시작 대기
        sleep 3
    else
        echo "⚠️ 카메라 1번 건너뜀 (미감지)"
        CAM1_PID=""
    fi
    
    echo ""
    echo "="*70
    echo "🎥 완전 독립적 듀얼 카메라 블랙박스 시작 완료"
    echo "="*70
    
    # 실행 중인 카메라 확인
    ACTIVE_CAMERAS=0
    if [ "$CAMERA0_AVAILABLE" = true ] && [ -n "$CAM0_PID" ]; then
        echo "📹 카메라 0번: 독립 실행 중 (PID: $CAM0_PID)"
        ACTIVE_CAMERAS=$((ACTIVE_CAMERAS + 1))
    fi
    
    if [ "$CAMERA1_AVAILABLE" = true ] && [ -n "$CAM1_PID" ]; then
        echo "📹 카메라 1번: 독립 실행 중 (PID: $CAM1_PID)"
        ACTIVE_CAMERAS=$((ACTIVE_CAMERAS + 1))
    fi
    
    echo ""
    echo "🔄 운영 방식:"
    echo "   • 각 카메라는 완전히 독립적으로 모션 감지"
    echo "   • 개별 쿨다운 관리 (카메라별 5초)"
    echo "   • 동일 초(초 단위)에 감지된 경우 자연스럽게 페어링"
    echo "   • 한 카메라 장애 시에도 다른 카메라 계속 동작"
    echo ""
    echo "📁 저장 위치: videos/events/cam0,cam1/$(date +%Y_%m_%d)/"
    echo "   • motion_event_cam0_YYYYMMDD_HHMMSS.mp4"
    echo "   • motion_event_cam1_YYYYMMDD_HHMMSS.mp4"
    echo ""
    echo "⚠️ 중요: Ctrl+C로 전체 시스템 안전 종료"
    echo "="*70
    
    if [ $ACTIVE_CAMERAS -eq 0 ]; then
        echo "❌ 활성화된 카메라가 없습니다!"
        exit 1
    fi
    
    echo ""
    echo "🎯 활성 카메라: ${ACTIVE_CAMERAS}대"
    echo "📊 실시간 모니터링을 위해 개별 터미널에서 확인 가능:"
    if [ "$CAMERA0_AVAILABLE" = true ]; then
        echo "   tail -f /dev/null # 카메라 0번 로그는 해당 프로세스에서 직접 출력"
    fi
    if [ "$CAMERA1_AVAILABLE" = true ]; then
        echo "   tail -f /dev/null # 카메라 1번 로그는 해당 프로세스에서 직접 출력"
    fi
    echo ""
    
    # 메인 프로세스는 자식 프로세스들을 모니터링
    while true; do
        # 카메라 0번 상태 확인
        if [ "$CAMERA0_AVAILABLE" = true ] && [ -n "$CAM0_PID" ]; then
            if ! kill -0 "$CAM0_PID" 2>/dev/null; then
                echo "⚠️ 카메라 0번 프로세스 종료됨"
                rm -f "$CAM0_PID_FILE"
                CAM0_PID=""
                CAMERA0_AVAILABLE=false
                ACTIVE_CAMERAS=$((ACTIVE_CAMERAS - 1))
            fi
        fi
        
        # 카메라 1번 상태 확인
        if [ "$CAMERA1_AVAILABLE" = true ] && [ -n "$CAM1_PID" ]; then
            if ! kill -0 "$CAM1_PID" 2>/dev/null; then
                echo "⚠️ 카메라 1번 프로세스 종료됨"
                rm -f "$CAM1_PID_FILE"
                CAM1_PID=""
                CAMERA1_AVAILABLE=false
                ACTIVE_CAMERAS=$((ACTIVE_CAMERAS - 1))
            fi
        fi
        
        # 모든 카메라가 종료되면 메인 프로세스도 종료
        if [ $ACTIVE_CAMERAS -eq 0 ]; then
            echo "❌ 모든 카메라 프로세스가 종료되었습니다"
            break
        fi
        
        # 60초마다 상태 확인
        sleep 60
    done
    
    echo "🛑 듀얼 카메라 블랙박스 시스템 종료"
}

# 스크립트가 직접 실행될 때만 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi