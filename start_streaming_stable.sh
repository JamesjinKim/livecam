#!/bin/bash
# start_streaming_stable.sh
# 안정성 최우선 스트리밍 서버 실행 스크립트
# stream_with_control.py 전용

echo "🛡️ 안정성 최우선 스트리밍 서버"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧠 메모리 풀 관리 | 📊 시스템 모니터링 | 🔄 자동 복구"
echo

# 현재 위치 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 필요한 파일 확인
if [ ! -f "src/streaming/stream_with_control.py" ]; then
    echo "❌ stream_with_control.py 파일을 찾을 수 없습니다."
    echo "   경로: src/streaming/stream_with_control.py"
    exit 1
fi

# Python 가상환경 확인 및 활성화
if [ -d "venv" ]; then
    echo "🐍 Python 가상환경 활성화..."
    source venv/bin/activate
else
    echo "⚠️  가상환경이 없습니다. 시스템 Python을 사용합니다."
fi

# 필요한 패키지 확인
echo "📦 필요한 패키지 확인 중..."
python3 -c "
import sys
missing = []
try:
    import fastapi
    import uvicorn
    import psutil
except ImportError as e:
    missing.append(str(e).split()[-1])

if missing:
    print('❌ 누락된 패키지:', ', '.join(missing))
    print('   설치 명령: pip install fastapi uvicorn psutil')
    sys.exit(1)
else:
    print('✅ 모든 패키지가 설치되어 있습니다.')
"

if [ $? -ne 0 ]; then
    echo
    echo "📦 패키지 자동 설치를 시도합니다..."
    pip install fastapi uvicorn psutil
    if [ $? -ne 0 ]; then
        echo "❌ 패키지 설치 실패. 수동으로 설치하세요:"
        echo "   pip install fastapi uvicorn psutil"
        exit 1
    fi
fi

# 카메라 확인
echo
echo "📷 카메라 상태 확인 중..."
CAMERA_COUNT=0

if timeout 3 rpicam-hello --camera 0 --timeout 100 >/dev/null 2>&1; then
    echo "   ✅ 카메라 0 정상"
    CAMERA_COUNT=$((CAMERA_COUNT + 1))
else
    echo "   ❌ 카메라 0 오류"
fi

if timeout 3 rpicam-hello --camera 1 --timeout 100 >/dev/null 2>&1; then
    echo "   ✅ 카메라 1 정상"
    CAMERA_COUNT=$((CAMERA_COUNT + 1))
else
    echo "   ❌ 카메라 1 오류"
fi

if [ $CAMERA_COUNT -eq 0 ]; then
    echo "❌ 사용 가능한 카메라가 없습니다. 카메라 연결 상태를 확인하세요."
    exit 1
fi

echo "   📊 사용 가능한 카메라: $CAMERA_COUNT 개"

# 시스템 리소스 확인
echo
echo "📊 시스템 리소스 확인..."
TOTAL_MEM=$(free -m | awk 'NR==2{printf "%d", $2}')
USED_MEM=$(free -m | awk 'NR==2{printf "%d", $3}')
MEM_PERCENT=$((USED_MEM * 100 / TOTAL_MEM))

echo "   💾 메모리: ${USED_MEM}MB / ${TOTAL_MEM}MB (${MEM_PERCENT}%)"

if [ $MEM_PERCENT -gt 80 ]; then
    echo "   ⚠️  경고: 메모리 사용률이 높습니다. 다른 프로그램을 종료하세요."
fi

# CPU 온도 확인 (라즈베리파이)
if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
    CPU_TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
    CPU_TEMP_C=$((CPU_TEMP / 1000))
    echo "   🌡️  CPU 온도: ${CPU_TEMP_C}°C"
    
    if [ $CPU_TEMP_C -gt 70 ]; then
        echo "   ⚠️  경고: CPU 온도가 높습니다. 방열을 확인하세요."
    fi
fi

# 포트 확인
PORT=8000
if netstat -tuln 2>/dev/null | grep ":$PORT " > /dev/null; then
    echo "   ⚠️  포트 $PORT 이미 사용 중입니다."
    echo "   🔄 기존 프로세스를 종료하거나 다른 포트를 사용하세요."
    
    # 기존 프로세스 찾기
    PID=$(lsof -ti :$PORT 2>/dev/null)
    if [ ! -z "$PID" ]; then
        echo "   📋 포트를 사용 중인 프로세스: PID $PID"
        echo "   💀 종료 명령: kill $PID"
    fi
else
    echo "   ✅ 포트 $PORT 사용 가능"
fi

# 로그 디렉토리 생성
mkdir -p logs
LOG_FILE="logs/streaming_$(date +%Y%m%d_%H%M%S).log"

echo
echo "🚀 안정성 최우선 스트리밍 서버 시작..."
echo "   📁 로그 파일: $LOG_FILE"
echo "   🌐 접속 주소: http://$(hostname -I | awk '{print $1}'):$PORT"
echo "   🌐 로컬 접속: http://localhost:$PORT"
echo "   🛡️ 메모리 풀 관리 활성화"
echo "   📊 실시간 시스템 모니터링 활성화"
echo
echo "🔧 안정성 기능:"
echo "   • 메모리 누수 방지 (고정 크기 메모리 풀)"
echo "   • 자동 가비지 컬렉션 (1000/20/20 임계점)"
echo "   • 프로세스 리소스 제한 (512MB/프로세스)"
echo "   • 25fps 안정화 스트리밍"
echo "   • 자동 오류 복구 시스템"
echo
echo "⏹️  중단: Ctrl+C"
echo "📊 상태확인: http://localhost:$PORT/api/health"
echo "🧹 수동정리: curl -X POST http://localhost:$PORT/api/cleanup"
echo

# 종료 신호 처리
cleanup() {
    echo
    echo "🛑 안전한 서버 종료 중..."
    
    # Python 프로세스에 SIGINT 전송
    if [ ! -z "$SERVER_PID" ]; then
        kill -INT $SERVER_PID 2>/dev/null
        echo "   📝 서버에 종료 신호 전송..."
        
        # 정상 종료 대기 (10초)
        for i in {1..10}; do
            if ! kill -0 $SERVER_PID 2>/dev/null; then
                echo "   ✅ 서버가 정상적으로 종료되었습니다."
                break
            fi
            echo "   ⏳ 정상 종료 대기 중... ($i/10)"
            sleep 1
        done
        
        # 강제 종료 (필요시)
        if kill -0 $SERVER_PID 2>/dev/null; then
            echo "   ⚠️  강제 종료 실행..."
            kill -9 $SERVER_PID 2>/dev/null
        fi
    fi
    
    # 메모리 정리
    echo "   🧹 시스템 메모리 정리 중..."
    sync
    
    # 카메라 프로세스 정리
    pkill -f "rpicam-vid" 2>/dev/null
    
    echo "   ✅ 안전한 종료 완료"
    echo "   📊 로그 파일: $LOG_FILE"
    
    exit 0
}

trap cleanup INT TERM

# 서버 실행
echo "🎬 서버 시작..."
python3 src/streaming/stream_with_control.py 2>&1 | tee "$LOG_FILE" &
SERVER_PID=$!

echo "   📋 서버 PID: $SERVER_PID"
echo

# 서버 상태 확인
sleep 2
if kill -0 $SERVER_PID 2>/dev/null; then
    echo "✅ 안정성 최우선 스트리밍 서버가 성공적으로 시작되었습니다!"
    echo
    echo "🌐 웹 브라우저에서 접속하세요:"
    echo "   http://$(hostname -I | awk '{print $1}'):$PORT"
    echo
    echo "📊 실시간 모니터링:"
    echo "   • 메모리 사용량: /api/system/info"
    echo "   • 서버 상태: /api/health"
    echo "   • 카메라 상태: /api/blackbox/status"
    echo
    echo "🎮 제어 기능:"
    echo "   • 실시간 스트리밍 (25fps 안정화)"
    echo "   • 블랙박스 녹화 시작/중지"
    echo "   • 시스템 리소스 모니터링"
    echo "   • 수동 메모리 정리"
    echo
    echo "⏳ 서버가 실행 중입니다... (Ctrl+C로 안전 종료)"
    
    # 서버 프로세스 대기
    wait $SERVER_PID
else
    echo "❌ 서버 시작 실패!"
    echo "📋 로그를 확인하세요: $LOG_FILE"
    exit 1
fi