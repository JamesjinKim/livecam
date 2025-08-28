#!/bin/bash

echo "=== DMA 최적화 테스트 스크립트 ==="
echo "OV5647 센서 (카메라 0, 1) 성능 측정"
echo ""

# 640x480 테스트
echo "1. 640x480 해상도 테스트 (YUV420 - DMA 최적화)"
echo "----------------------------------------"
echo "카메라 0번:"
rpicam-vid --camera 0 --codec yuv420 --width 640 --height 480 --timeout 5000 --output cam0_640.yuv --nopreview --info-text "fps" 2>&1 | grep -E "fps|wrote"

echo ""
echo "카메라 1번:"
rpicam-vid --camera 1 --codec yuv420 --width 640 --height 480 --timeout 5000 --output cam1_640.yuv --nopreview --info-text "fps" 2>&1 | grep -E "fps|wrote"

echo ""
echo "2. HD (1920x1080) 해상도 테스트"
echo "----------------------------------------"
echo "카메라 0번 (MJPEG 압축):"
rpicam-vid --camera 0 --codec mjpeg --width 1920 --height 1080 --timeout 5000 --output cam0_hd.mjpeg --nopreview --info-text "fps" 2>&1 | grep -E "fps|wrote"

echo ""
echo "카메라 1번 (MJPEG 압축):"
rpicam-vid --camera 1 --codec mjpeg --width 1920 --height 1080 --timeout 5000 --output cam1_hd.mjpeg --nopreview --info-text "fps" 2>&1 | grep -E "fps|wrote"

echo ""
echo "3. 파일 크기 확인"
echo "----------------------------------------"
ls -lh cam*.yuv cam*.mjpeg 2>/dev/null | awk '{print $9 ": " $5}'

echo ""
echo "4. CPU 사용률 측정 (동시 실행)"
echo "----------------------------------------"
rpicam-vid --camera 0 --codec yuv420 --width 640 --height 480 --timeout 10000 --output front_640.yuv --nopreview &
PID1=$!

rpicam-vid --camera 1 --codec yuv420 --width 640 --height 480 --timeout 10000 --output rear_640.yuv --nopreview &
PID2=$!

sleep 2
echo "CPU 사용률 (640x480 듀얼):"
top -b -n 1 | grep rpicam-vid

wait $PID1 $PID2

echo ""
echo "테스트 완료!"
rm -f cam*.yuv cam*.mjpeg front_640.yuv rear_640.yuv