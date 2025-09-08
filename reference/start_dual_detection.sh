#!/bin/bash

# 듀얼 카메라 모션 감지 시스템 시작 스크립트
# 두 개의 독립적인 프로세스로 cam0과 cam1 모션 감지 실행

echo "========================================="
echo "Dual Camera Motion Detection System"
echo "========================================="
echo ""

# 기존 프로세스 종료
echo "Checking for existing processes..."
pkill -f "detection_cam0.py" 2>/dev/null
pkill -f "detection_cam1.py" 2>/dev/null
sleep 2

# Camera 0 시작
echo "Starting Camera 0 motion detection..."
python3 /home/shinho/shinho/livecam/detection_cam0.py &
CAM0_PID=$!
echo "Camera 0 PID: $CAM0_PID"

# 잠시 대기 (카메라 초기화 시간)
sleep 3

# Camera 1 시작
echo "Starting Camera 1 motion detection..."
python3 /home/shinho/shinho/livecam/detection_cam1.py &
CAM1_PID=$!
echo "Camera 1 PID: $CAM1_PID"

echo ""
echo "Both cameras are running."
echo "Press Ctrl+C to stop both cameras..."
echo ""

# Ctrl+C 시그널 처리
trap "echo 'Stopping both cameras...'; kill $CAM0_PID $CAM1_PID 2>/dev/null; exit" INT

# 프로세스 모니터링
while true; do
    # 두 프로세스가 모두 살아있는지 확인
    if ! kill -0 $CAM0_PID 2>/dev/null; then
        echo "Camera 0 process died. Restarting..."
        python3 /home/shinho/shinho/livecam/detection_cam0.py &
        CAM0_PID=$!
    fi
    
    if ! kill -0 $CAM1_PID 2>/dev/null; then
        echo "Camera 1 process died. Restarting..."
        python3 /home/shinho/shinho/livecam/detection_cam1.py &
        CAM1_PID=$!
    fi
    
    sleep 5
done