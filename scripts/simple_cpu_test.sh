#!/bin/bash
echo "=== rpicam HD 캡처 중 리소스 모니터링 ==="
echo ""
echo "1. 캡처 시작 전 상태:"
echo "CPU 사용률:"
top -bn1 | head -5

echo ""
echo "2. HD 캡처 시작 (백그라운드)..."
rpicam-vid --camera 0 --width 1920 --height 1080 --codec yuv420 --timeout 10000 --output /dev/null --nopreview > /dev/null 2>&1 &
PID=$!

sleep 3

echo ""
echo "3. 캡처 중 상태:"
echo "rpicam 프로세스 정보:"
ps aux | grep $PID | grep -v grep

echo ""
echo "CPU 사용률:"
top -bn1 | head -5

echo ""
echo "4. rpicam 프로세스 CPU 사용률:"
top -bn1 -p $PID | tail -2 | head -1

wait $PID 2>/dev/null
echo ""
echo "=== 테스트 완료 ==="
