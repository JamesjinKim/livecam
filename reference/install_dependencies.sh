#!/bin/bash

# 스마트 블랙박스 시스템 의존성 설치 스크립트
echo "📦 스마트 블랙박스 시스템 의존성 설치 중..."

# 시스템 패키지 업데이트
echo "🔄 시스템 패키지 업데이트 중..."
sudo apt update -y

# 필수 시스템 패키지 설치
echo "📥 필수 시스템 패키지 설치 중..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-opencv \
    rpicam-apps \
    ffmpeg \
    build-essential \
    pkg-config

# Python 가상환경 생성 (선택사항)
if [ ! -d "venv" ]; then
    echo "🐍 Python 가상환경 생성 중..."
    python3 -m venv venv
fi

# 가상환경 활성화 (있는 경우)
if [ -d "venv" ]; then
    echo "✨ 가상환경 활성화..."
    source venv/bin/activate
fi

# Python 패키지 설치
echo "📦 Python 패키지 설치 중..."
pip install --upgrade pip
pip install fastapi uvicorn psutil

# 설치 확인
echo "🔍 설치 확인 중..."

# OpenCV 확인
python3 -c "import cv2; print(f'✅ OpenCV 버전: {cv2.__version__}')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ OpenCV 설치 실패 - 다시 시도합니다..."
    sudo apt install -y python3-opencv python3-numpy
fi

# FastAPI 확인  
python3 -c "import fastapi; print('✅ FastAPI 설치 완료')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ FastAPI 설치 실패 - 다시 시도합니다..."
    pip install fastapi uvicorn
fi

# psutil 확인
python3 -c "import psutil; print('✅ psutil 설치 완료')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ psutil 설치 실패 - 다시 시도합니다..."
    pip install psutil
fi

# rpicam-vid 확인
which rpicam-vid >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ rpicam-vid 설치 완료"
else
    echo "❌ rpicam-vid 설치 실패"
    echo "   수동 설치: sudo apt install rpicam-apps"
fi

# FFmpeg 확인
which ffmpeg >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ FFmpeg 설치 완료"
else
    echo "❌ FFmpeg 설치 실패"
    echo "   수동 설치: sudo apt install ffmpeg"
fi

echo ""
echo "="*50
echo "📦 의존성 설치 완료!"
echo "="*50
echo "🚀 이제 다음 명령으로 시스템을 시작할 수 있습니다:"
echo "   ./start_blackbox_system.sh"
echo ""
echo "📋 설치된 구성 요소:"
echo "   • Python OpenCV (영상 처리)"
echo "   • FastAPI + Uvicorn (웹 서버)"  
echo "   • psutil (프로세스 관리)"
echo "   • rpicam-apps (카메라 제어)"
echo "   • FFmpeg (영상 변환)"
echo "="*50