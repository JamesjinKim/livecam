#!/bin/bash

echo "=== YUV420 영상 재생 방법 ==="
echo ""

# 파일 확인
if [ ! -f "test_640x480.yuv" ]; then
    echo "먼저 영상을 캡처하세요:"
    echo "  rpicam-vid --camera 0 --codec yuv420 --width 640 --height 480 --timeout 3000 --output test_640x480.yuv --nopreview"
    exit 1
fi

echo "캡처된 영상 정보:"
ls -lh test_640x480.yuv

echo ""
echo "----------------------------------------"
echo "재생 방법 1: ffplay (권장)"
echo "----------------------------------------"
echo "설치: sudo apt install ffmpeg"
echo "재생 명령어:"
echo "  ffplay -f rawvideo -pix_fmt yuv420p -video_size 640x480 test_640x480.yuv"
echo ""

echo "----------------------------------------"
echo "재생 방법 2: VLC"
echo "----------------------------------------"
echo "설치: sudo apt install vlc"
echo "재생 명령어:"
echo "  vlc --demux rawvideo --rawvid-width 640 --rawvid-height 480 --rawvid-chroma I420 test_640x480.yuv"
echo ""

echo "----------------------------------------"
echo "재생 방법 3: MP4로 변환 후 재생"
echo "----------------------------------------"
echo "변환 명령어:"
echo "  ffmpeg -f rawvideo -pix_fmt yuv420p -s:v 640x480 -r 30 -i test_640x480.yuv -c:v libx264 output.mp4"
echo "재생:"
echo "  vlc output.mp4"
echo ""

echo "----------------------------------------"
echo "재생 방법 4: 원격 재생 (SSH 환경)"
echo "----------------------------------------"
echo "1. 파일을 로컬로 복사:"
echo "   scp shinho@raspberrypi:~/shinho/livecam/test_640x480.yuv ."
echo "2. 로컬에서 ffplay로 재생"
echo ""

# ffplay가 설치되어 있으면 바로 재생
if command -v ffplay &> /dev/null; then
    echo "ffplay가 설치되어 있습니다. 재생하시겠습니까? (y/n)"
    read -r answer
    if [ "$answer" = "y" ]; then
        ffplay -f rawvideo -pix_fmt yuv420p -video_size 640x480 test_640x480.yuv
    fi
else
    echo "ffplay가 설치되어 있지 않습니다."
    echo "설치하려면: sudo apt install ffmpeg"
fi