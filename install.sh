#!/bin/bash

# SHT 듀얼 LIVE 카메라 설치 스크립트
# Raspberry Pi 5용 시스템 패키지 설치

echo "=================================="
echo "SHT 듀얼 LIVE 카메라 설치 시작"
echo "=================================="
echo ""

# 시스템 패키지 업데이트
echo "[1/3] 시스템 패키지 업데이트 중..."
sudo apt update

# 필수 의존성 설치
echo ""
echo "[2/3] 필수 패키지 설치 중..."
sudo apt install -y \
    python3-picamera2 \
    python3-uvicorn \
    python3-fastapi \
    python3-numpy \
    python3-opencv \
    python3-psutil \
    python3-libcamera \
    ffmpeg

# 설치 확인
echo ""
echo "[3/3] 설치 확인 중..."

# Python 버전 확인
python3 --version

# Picamera2 확인
if python3 -c "from picamera2 import Picamera2" 2>/dev/null; then
    echo "✓ Picamera2 설치 완료"
else
    echo "✗ Picamera2 설치 실패"
    exit 1
fi

# FastAPI 확인
if python3 -c "import fastapi" 2>/dev/null; then
    echo "✓ FastAPI 설치 완료"
else
    echo "✗ FastAPI 설치 실패"
    exit 1
fi

# Uvicorn 확인
if python3 -c "import uvicorn" 2>/dev/null; then
    echo "✓ Uvicorn 설치 완료"
else
    echo "✗ Uvicorn 설치 실패"
    exit 1
fi

# 디렉토리 생성
echo ""
echo "녹화 디렉토리 생성 중..."
mkdir -p videos/cam0
mkdir -p videos/cam1

echo ""
echo "=================================="
echo "설치 완료!"
echo "=================================="
echo ""
echo "시스템 시작:"
echo "  python3 webmain.py"
echo ""
echo "웹 접속:"
echo "  http://$(hostname -I | awk '{print $1}'):8001"git commit -m "feat: Add automated installation script for system dependencies
echo ""