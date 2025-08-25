#!/bin/bash

echo "=== Simple Camera Hardware Test ==="
echo "Testing both cameras with basic capture"
echo

# Test Camera 0 with minimal settings
echo "Testing Camera 0 with basic settings..."
rpicam-still --camera 0 --output /tmp/test_cam0.jpg --width 320 --height 240 --timeout 1000 --immediate --nopreview 2>/tmp/cam0_error.log &
CAM0_PID=$!

# Test Camera 1 with minimal settings  
echo "Testing Camera 1 with basic settings..."
rpicam-still --camera 1 --output /tmp/test_cam1.jpg --width 320 --height 240 --timeout 1000 --immediate --nopreview 2>/tmp/cam1_error.log &
CAM1_PID=$!

# Wait for both processes
echo "Waiting for capture processes (5 seconds max)..."
sleep 5

# Kill processes if still running
kill $CAM0_PID 2>/dev/null
kill $CAM1_PID 2>/dev/null

echo
echo "=== Results ==="

# Check Camera 0 results
if [ -f "/tmp/test_cam0.jpg" ] && [ -s "/tmp/test_cam0.jpg" ]; then
    echo "✓ Camera 0: SUCCESS - Image captured ($(stat -c%s /tmp/test_cam0.jpg) bytes)"
else
    echo "✗ Camera 0: FAILED"
    echo "Error log:"
    cat /tmp/cam0_error.log | head -10
fi

echo

# Check Camera 1 results  
if [ -f "/tmp/test_cam1.jpg" ] && [ -s "/tmp/test_cam1.jpg" ]; then
    echo "✓ Camera 1: SUCCESS - Image captured ($(stat -c%s /tmp/test_cam1.jpg) bytes)"
else
    echo "✗ Camera 1: FAILED"
    echo "Error log:"
    cat /tmp/cam1_error.log | head -10
fi

echo
echo "=== Hardware Detection ==="
rpicam-hello --list-cameras

echo
echo "=== Available Video Devices ==="
ls -la /dev/video* | head -10

# Cleanup
rm -f /tmp/test_cam*.jpg /tmp/cam*_error.log