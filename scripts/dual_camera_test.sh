#!/bin/bash

echo "=== 듀얼 카메라 DMA 최적화 테스트 ==="
echo "카메라 0번, 1번 동시 작동 테스트"
echo ""

echo "1. 640x480 듀얼 카메라 동시 실행 (YUV420 - DMA 최적화)"
echo "--------------------------------------------------------"

# 카메라 0번 백그라운드 실행
rpicam-vid --camera 0 --codec yuv420 --width 640 --height 480 --timeout 10000 --output front_640.yuv --nopreview --info-text "fps" 2>&1 | sed 's/^/[CAM0] /' &
PID0=$!

# 카메라 1번 백그라운드 실행
rpicam-vid --camera 1 --codec yuv420 --width 640 --height 480 --timeout 10000 --output rear_640.yuv --nopreview --info-text "fps" 2>&1 | sed 's/^/[CAM1] /' &
PID1=$!

# CPU 사용률 모니터링
echo ""
echo "CPU 사용률 모니터링 (640x480 듀얼):"
sleep 2
for i in {1..3}; do
    echo "측정 $i/3:"
    ps aux | grep rpicam-vid | grep -v grep | awk '{printf "  PID %s: CPU %s%% MEM %s%%\n", $2, $3, $4}'
    sleep 2
done

# 프로세스 완료 대기
wait $PID0 $PID1

echo ""
echo "2. HD (1920x1080) 듀얼 카메라 동시 실행 (MJPEG)"
echo "--------------------------------------------------------"

# HD 카메라 0번 백그라운드 실행
rpicam-vid --camera 0 --codec mjpeg --width 1920 --height 1080 --timeout 10000 --output front_hd.mjpeg --nopreview --info-text "fps" 2>&1 | sed 's/^/[CAM0-HD] /' &
PID0=$!

# HD 카메라 1번 백그라운드 실행
rpicam-vid --camera 1 --codec mjpeg --width 1920 --height 1080 --timeout 10000 --output rear_hd.mjpeg --nopreview --info-text "fps" 2>&1 | sed 's/^/[CAM1-HD] /' &
PID1=$!

# CPU 사용률 모니터링
echo ""
echo "CPU 사용률 모니터링 (HD 듀얼):"
sleep 2
for i in {1..3}; do
    echo "측정 $i/3:"
    ps aux | grep rpicam-vid | grep -v grep | awk '{printf "  PID %s: CPU %s%% MEM %s%%\n", $2, $3, $4}'
    sleep 2
done

# 프로세스 완료 대기
wait $PID0 $PID1

echo ""
echo "3. 캡처된 파일 정보"
echo "--------------------------------------------------------"
echo "640x480 파일:"
ls -lh front_640.yuv rear_640.yuv 2>/dev/null | awk '{print "  " $9 ": " $5}'
echo ""
echo "HD 파일:"
ls -lh front_hd.mjpeg rear_hd.mjpeg 2>/dev/null | awk '{print "  " $9 ": " $5}'

echo ""
echo "4. 프레임 수 계산"
echo "--------------------------------------------------------"
if [ -f front_640.yuv ]; then
    SIZE_640=$(stat -c%s front_640.yuv)
    FRAME_SIZE_640=$((640 * 480 * 3 / 2))  # YUV420
    FRAMES_640=$((SIZE_640 / FRAME_SIZE_640))
    echo "640x480 캡처 프레임 수: $FRAMES_640 프레임 (10초간)"
    echo "평균 FPS: $((FRAMES_640 / 10)) fps"
fi

echo ""
echo "듀얼 카메라 테스트 완료!"