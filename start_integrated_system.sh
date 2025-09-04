#!/bin/bash

# 통합 시스템 시작 스크립트
echo "🚀 라즈베리파이 통합 시스템 시작 중..."

# 프로세스 정리 함수
cleanup() {
    echo ""
    echo "🛑 통합 시스템 종료 중..."
    
    # 모든 관련 프로세스 종료
    pkill -f "integrated_controller.py" 2>/dev/null
    pkill -f "main.py" 2>/dev/null
    pkill -f "motion_blackbox.py" 2>/dev/null  
    pkill -f "rpicam-vid" 2>/dev/null
    
    sleep 2
    echo "✅ 통합 시스템 종료 완료"
    exit 0
}

# 신호 처리 설정
trap cleanup SIGINT SIGTERM

# 현재 디렉터리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 필수 의존성 확인
echo "🔍 의존성 확인 중..."

# Python 모듈 확인
python3 -c "import cv2" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ OpenCV 모듈이 설치되지 않았습니다"
    echo "   ./install_dependencies.sh 명령으로 설치하세요"
    exit 1
fi

python3 -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ FastAPI 모듈이 설치되지 않았습니다"
    echo "   ./install_dependencies.sh 명령으로 설치하세요"
    exit 1
fi

# rpicam-vid 확인
which rpicam-vid >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ rpicam-vid가 설치되지 않았습니다"
    echo "   sudo apt install rpicam-apps 명령으로 설치하세요"
    exit 1
fi

echo "✅ 모든 의존성 확인 완료"

# 카메라 연결 확인
echo "📹 카메라 연결 확인 중..."
rpicam-hello --list-cameras 2>/dev/null | grep -q "Available cameras"
if [ $? -ne 0 ]; then
    echo "⚠️ 카메라 연결을 확인할 수 없습니다. 계속 진행합니다..."
else
    camera_count=$(rpicam-hello --list-cameras 2>/dev/null | grep -c "imx")
    echo "✅ 감지된 카메라: ${camera_count}개"
fi

# 디렉터리 생성
echo "📁 디렉터리 생성 중..."
mkdir -p videos/events
echo "✅ 저장 디렉터리 준비 완료"

# 기존 프로세스 정리
echo "🧹 기존 프로세스 정리 중..."
pkill -f "integrated_controller.py" 2>/dev/null
pkill -f "main.py" 2>/dev/null
pkill -f "motion_blackbox.py" 2>/dev/null
pkill -f "rpicam-vid" 2>/dev/null
sleep 2

# 통합 제어 서버 시작
echo "🎛️ 통합 제어 서버 시작 중..."
python3 "$SCRIPT_DIR/integrated_controller.py" &
CONTROLLER_PID=$!

# 잠시 대기 (서버 초기화)
sleep 3

# 시스템 정보 출력
echo ""
echo "="*70
echo "🎥 라즈베리파이 통합 시스템 시작 완료"
echo "="*70
echo "🎛️  통합 제어판: http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "📋 구성 시스템:"
echo "   1️⃣ 토글 스트리밍 (기존 main.py)"
echo "      • 카메라 0번 ↔ 카메라 1번 교차 스트리밍"
echo "      • 포트: 8001"
echo "      • 제어: 통합 제어판에서 시작/중지 가능"
echo ""
echo "   2️⃣ 모션 감지 블랙박스 (새로운 motion_blackbox.py)"
echo "      • 카메라 0번, 1번 동시 모션 감지"
echo "      • 모션 시 전후 1.5분씩 총 3분 녹화"
echo "      • 자동 시작됨 (기본 활성화)"
echo ""
echo "🔄 독립 동작:"
echo "   • 두 시스템은 서로 간섭 없이 동시 실행 가능"
echo "   • 기존 토글 스트리밍: 사용자 필요시 수동 시작"
echo "   • 새로운 모션 블랙박스: 24/7 자동 감시"
echo ""
echo "⚠️  중요: Ctrl+C로 통합 시스템 전체 종료"
echo "="*70

# 무한 대기 (사용자가 Ctrl+C 할 때까지)
while true; do
    # 제어 서버 상태 확인
    if ! kill -0 $CONTROLLER_PID 2>/dev/null; then
        echo "❌ 통합 제어 서버가 중단되었습니다. 재시작 중..."
        python3 "$SCRIPT_DIR/integrated_controller.py" &
        CONTROLLER_PID=$!
    fi
    
    sleep 5
done