#!/bin/bash

echo "=== 카메라 0번, 1번 테스트 영상 캡처 및 변환 ==="
echo ""

# 카메라 0번 캡처
echo "1. 카메라 0번 영상 캡처 중... (5초)"
rpicam-vid --camera 0 --codec yuv420 --width 640 --height 480 --timeout 5000 --output camera0_test.yuv --nopreview 2>&1 | grep -v "fps"
echo "   ✓ camera0_test.yuv 생성 완료"

# 카메라 1번 캡처  
echo ""
echo "2. 카메라 1번 영상 캡처 중... (5초)"
rpicam-vid --camera 1 --codec yuv420 --width 640 --height 480 --timeout 5000 --output camera1_test.yuv --nopreview 2>&1 | grep -v "fps"
echo "   ✓ camera1_test.yuv 생성 완료"

# YUV를 MP4로 변환
echo ""
echo "3. YUV 영상을 MP4로 변환 중..."

echo "   카메라 0번 변환..."
ffmpeg -f rawvideo -pix_fmt yuv420p -s:v 640x480 -r 30 -i camera0_test.yuv -c:v libx264 -preset fast camera0_test.mp4 -y 2>/dev/null
echo "   ✓ camera0_test.mp4 생성 완료"

echo "   카메라 1번 변환..."
ffmpeg -f rawvideo -pix_fmt yuv420p -s:v 640x480 -r 30 -i camera1_test.yuv -c:v libx264 -preset fast camera1_test.mp4 -y 2>/dev/null
echo "   ✓ camera1_test.mp4 생성 완료"

# 파일 정보 표시
echo ""
echo "4. 생성된 파일 정보:"
echo "----------------------------------------"
ls -lh camera*.yuv camera*.mp4 2>/dev/null | awk '{print "   " $9 ": " $5}'

echo ""
echo "5. 영상 확인 방법:"
echo "----------------------------------------"
echo "로컬에서 재생 (라즈베리파이에서):"
echo "   ffplay camera0_test.mp4  # 카메라 0번"
echo "   ffplay camera1_test.mp4  # 카메라 1번"
echo ""
echo "원격에서 재생 (SSH 환경):"
echo "   1) 파일 다운로드:"
echo "      scp shinho@raspberrypi:~/shinho/livecam/camera0_test.mp4 ."
echo "      scp shinho@raspberrypi:~/shinho/livecam/camera1_test.mp4 ."
echo "   2) 로컬 PC에서 재생"
echo ""
echo "두 영상 동시 재생:"
echo "   ffplay camera0_test.mp4 & ffplay camera1_test.mp4 &"

# 선택적 원본 파일 삭제
echo ""
echo "원본 YUV 파일을 삭제하시겠습니까? (y/n)"
read -r answer
if [ "$answer" = "y" ]; then
    rm -f camera*.yuv
    echo "YUV 파일이 삭제되었습니다."
fi