#!/bin/bash

# 🎥 스트리밍 서버 시작 스크립트
# 사용법: ./start_streaming.sh [single|multi]

set -e  # 오류 시 즉시 중단

# 기본 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"
SRC_PATH="$SCRIPT_DIR/src/streaming"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 헬프 함수
show_help() {
    echo -e "${BLUE}🎥 라즈베리파이 5 스트리밍 서버${NC}"
    echo
    echo -e "${GREEN}사용법:${NC}"
    echo "  ./start_streaming.sh single    # 단일 클라이언트 고품질 스트리밍"
    echo "  ./start_streaming.sh multi     # 다중 클라이언트 스트리밍"
    echo
    echo -e "${GREEN}설명:${NC}"
    echo "  single - 고품질 90% MJPEG, 25fps, 1명만 접속 가능"
    echo "  multi  - 최적화 70% MJPEG, 20fps, 다중 접속 가능"
    echo
    echo -e "${YELLOW}접속 URL: http://라즈베리파이IP:8000/${NC}"
}

# 가상환경 확인
check_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        echo -e "${RED}❌ 가상환경이 없습니다. 설치 중...${NC}"
        python3 -m venv "$VENV_PATH"
        source "$VENV_PATH/bin/activate"
        pip install fastapi uvicorn
    fi
}

# 포트 확인 및 정리
check_port() {
    if lsof -ti:8000 >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️ 포트 8000이 사용 중입니다. 기존 프로세스를 종료합니다.${NC}"
        lsof -ti:8000 | xargs -r kill -9 2>/dev/null || true
        sleep 2
    fi
}

# 메인 실행
main() {
    local mode="${1:-}"
    
    # 인자 확인
    if [ -z "$mode" ] || [ "$mode" = "help" ] || [ "$mode" = "-h" ] || [ "$mode" = "--help" ]; then
        show_help
        exit 0
    fi
    
    if [ "$mode" != "single" ] && [ "$mode" != "multi" ]; then
        echo -e "${RED}❌ 잘못된 모드입니다. single 또는 multi를 선택하세요.${NC}"
        show_help
        exit 1
    fi
    
    echo -e "${BLUE}🚀 스트리밍 서버 시작${NC}"
    
    # 환경 준비
    check_venv
    check_port
    
    # 가상환경 활성화
    source "$VENV_PATH/bin/activate"
    
    # 서버 실행
    if [ "$mode" = "single" ]; then
        echo -e "${GREEN}📱 단일 클라이언트 고품질 서버 시작...${NC}"
        echo -e "${YELLOW}   - MJPEG 90% 고품질${NC}"
        echo -e "${YELLOW}   - 25fps 스트리밍${NC}"
        echo -e "${YELLOW}   - 1명만 동시 접속 가능${NC}"
        python "$SRC_PATH/stream_server.py"
    else
        echo -e "${GREEN}👥 다중 클라이언트 서버 시작...${NC}"
        echo -e "${YELLOW}   - MJPEG 70% 최적화${NC}"
        echo -e "${YELLOW}   - 20fps 스트리밍${NC}"
        echo -e "${YELLOW}   - 다중 접속 지원${NC}"
        python "$SRC_PATH/stream_multi.py"
    fi
}

# 종료 처리
cleanup() {
    echo -e "\n${YELLOW}🛑 서버를 종료합니다...${NC}"
    exit 0
}

trap cleanup INT

# 스크립트 실행
main "$@"