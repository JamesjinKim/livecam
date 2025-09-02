#!/bin/bash

# 🛡️ Long-term Optimized Streaming Server
# 메모리 누수 방지 및 24/7 서비스 최적화된 듀얼 카메라 스트리밍

set -e

# 기본 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"
STREAMING_FILE="$SCRIPT_DIR/src/streaming/stream_optimized_30fps.py"
LOG_DIR="$SCRIPT_DIR/logs"
PORT=8000

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 로그 디렉토리 생성
mkdir -p "${LOG_DIR}"

# 헤더 출력
show_header() {
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           🎬 30fps High-Performance Server v3.0          ║${NC}"
    echo -e "${CYAN}║         부드러운 30fps + 메모리 누수 방지 서버               ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo
}

# 최적화 정보 출력
show_optimization_info() {
    echo -e "${GREEN}🎬 30fps 고성능 스트리밍 기능:${NC}"
    echo -e "├─ 부드러운 영상: 30fps 실시간 스트리밍 (기존 15fps 대비 2배)"
    echo -e "├─ 향상된 버퍼: 768KB 3단계 버퍼 풀 + 적응형 청크 읽기"
    echo -e "├─ 프레임 보정: 프레임 스킵 방지 + 실시간 FPS 표시"
    echo -e "└─ 메모리 안정성: 누수 방지 + 자동 가비지 컬렉션"
    echo
}

# 가상환경 확인
check_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        echo -e "${YELLOW}⚠️ 가상환경이 없습니다. 생성 중...${NC}"
        python3 -m venv "$VENV_PATH"
        source "$VENV_PATH/bin/activate"
        pip install --quiet fastapi uvicorn psutil
    fi
}

# 포트 확인 및 정리
check_port() {
    if lsof -ti:$PORT >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️ 포트 $PORT 사용 중. 기존 프로세스 종료 중...${NC}"
        lsof -ti:$PORT | xargs -r kill -9 2>/dev/null || true
        sleep 2
    fi
    
    # rpicam 프로세스 정리
    if pgrep rpicam-vid >/dev/null 2>&1; then
        echo -e "${YELLOW}🔧 기존 카메라 프로세스 정리 중...${NC}"
        pkill rpicam-vid 2>/dev/null || true
        sleep 1
    fi
}

# 스크립트 파일 확인
check_script() {
    if [ ! -f "$STREAMING_FILE" ]; then
        echo -e "${RED}❌ $STREAMING_FILE 파일을 찾을 수 없습니다!${NC}"
        exit 1
    fi
}

# 메인 실행
main() {
    show_header
    show_optimization_info
    
    echo -e "${BLUE}🚀 서버 시작 중...${NC}"
    
    check_venv
    check_port  
    check_script
    
    # 가상환경 활성화
    source "$VENV_PATH/bin/activate"
    
    echo -e "${GREEN}✅ 30fps 고성능 스트리밍 서버 시작${NC}"
    echo -e "${CYAN}📡 접속: http://$(hostname -I | awk '{print $1}'):$PORT${NC}"
    echo
    
    # 로그 파일 설정
    LOG_FILE="${LOG_DIR}/optimized_$(date +%Y%m%d_%H%M%S).log"
    
    # 서버 실행
    cd "$SCRIPT_DIR"
    python "$STREAMING_FILE" 2>&1 | tee "$LOG_FILE"
}

# 종료 처리
cleanup() {
    echo -e "\n${YELLOW}🛑 서버를 종료합니다...${NC}"
    pkill rpicam-vid 2>/dev/null || true
    exit 0
}

trap cleanup INT

# 도움말
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo -e "${BLUE}🎬 30fps High-Performance Streaming Server${NC}"
    echo
    echo -e "${GREEN}사용법:${NC}"
    echo "  ./start_streaming.sh      # 30fps 서버 시작"
    echo
    echo -e "${GREEN}30fps 고성능 기능:${NC}"
    echo "  🎬 부드러운 30fps 실시간 스트리밍"
    echo "  🔧 향상된 버퍼 관리 (768KB 3단계)"
    echo "  ⚡ 프레임 스킵 방지 최적화"
    echo "  🛡️ 메모리 누수 완전 방지"
    echo
    echo -e "${GREEN}접속:${NC}"
    echo -e "  ${CYAN}http://$(hostname -I | awk '{print $1}'):8000${NC}"
    exit 0
fi

# 스크립트 실행
main "$@"