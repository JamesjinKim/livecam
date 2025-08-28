#!/bin/bash
# comprehensive_camera_test.sh
# 듀얼 카메라 + 다양한 해상도 + 색상 테스트

echo "🎥 라즈베리파이 5 종합 카메라 테스트"
echo

# 카메라 감지
echo "1️⃣ 카메라 감지..."
rpicam-hello --list-cameras

echo
echo "2️⃣ 카메라별 테스트 시작"
echo "========================================"

# 카메라 0 테스트 (다양한 해상도)
echo
echo "📷 카메라 0 테스트:"
echo "--------------------"

# 640x480 @ 30fps
echo "  🔹 640x480 캡처 (5초)..."
rpicam-vid --camera 0 --width 640 --height 480 --timeout 5000 \
    --codec yuv420 --output cam0_640x480.yuv --nopreview --framerate 30

if [ $? -eq 0 ]; then
    echo "  ✅ 카메라 0 - 640x480 캡처 완료"
    
    # YUV to MP4 변환
    ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 640x480 -r 30 \
        -i cam0_640x480.yuv -c:v libx264 -preset fast -crf 18 \
        cam0_640x480.mp4 -y -loglevel quiet
    
    echo "  ✅ cam0_640x480.mp4 생성 완료"
else
    echo "  ❌ 카메라 0 - 640x480 실패"
fi

# HD 1280x720 @ 30fps  
echo "  🔹 HD (1280x720) 캡처 (3초)..."
rpicam-vid --camera 0 --width 1280 --height 720 --timeout 3000 \
    --codec yuv420 --output cam0_hd.yuv --nopreview --framerate 30

if [ $? -eq 0 ]; then
    echo "  ✅ 카메라 0 - HD 캡처 완료"
    
    # HD YUV to MP4 (처음 90프레임만 = 3초)
    ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 1280x720 -r 30 \
        -i cam0_hd.yuv -c:v libx264 -preset fast -crf 18 \
        -t 3 cam0_hd.mp4 -y -loglevel quiet
        
    echo "  ✅ cam0_hd.mp4 생성 완료"
else
    echo "  ❌ 카메라 0 - HD 실패"
fi

echo
echo "📷 카메라 1 테스트:"
echo "--------------------"

# 카메라 1 - 640x480
echo "  🔹 640x480 캡처 (5초)..."
rpicam-vid --camera 1 --width 640 --height 480 --timeout 5000 \
    --codec yuv420 --output cam1_640x480.yuv --nopreview --framerate 30

if [ $? -eq 0 ]; then
    echo "  ✅ 카메라 1 - 640x480 캡처 완료"
    
    ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 640x480 -r 30 \
        -i cam1_640x480.yuv -c:v libx264 -preset fast -crf 18 \
        cam1_640x480.mp4 -y -loglevel quiet
        
    echo "  ✅ cam1_640x480.mp4 생성 완료"
else
    echo "  ❌ 카메라 1 - 640x480 실패"
fi

# 카메라 1 - HD
echo "  🔹 HD (1280x720) 캡처 (3초)..."
rpicam-vid --camera 1 --width 1280 --height 720 --timeout 3000 \
    --codec yuv420 --output cam1_hd.yuv --nopreview --framerate 30

if [ $? -eq 0 ]; then
    echo "  ✅ 카메라 1 - HD 캡처 완료"
    
    ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 1280x720 -r 30 \
        -i cam1_hd.yuv -c:v libx264 -preset fast -crf 18 \
        -t 3 cam1_hd.mp4 -y -loglevel quiet
        
    echo "  ✅ cam1_hd.mp4 생성 완료"
else
    echo "  ❌ 카메라 1 - HD 실패"
fi

echo
echo "3️⃣ 색상 테스트 (MJPEG)"
echo "========================================"

# MJPEG로 색상 확인 (더 나은 색상 재현)
echo "  🎨 카메라 0 - MJPEG 색상 테스트..."
rpicam-vid --camera 0 --width 640 --height 480 --timeout 3000 \
    --codec mjpeg --output cam0_color.mjpeg --nopreview

if [ $? -eq 0 ]; then
    # MJPEG를 MP4로 변환
    ffmpeg -i cam0_color.mjpeg -c:v libx264 -preset fast -crf 18 \
        cam0_color.mp4 -y -loglevel quiet
    echo "  ✅ cam0_color.mp4 (MJPEG 원본) 생성 완료"
fi

echo "  🎨 카메라 1 - MJPEG 색상 테스트..."
rpicam-vid --camera 1 --width 640 --height 480 --timeout 3000 \
    --codec mjpeg --output cam1_color.mjpeg --nopreview

if [ $? -eq 0 ]; then
    ffmpeg -i cam1_color.mjpeg -c:v libx264 -preset fast -crf 18 \
        cam1_color.mp4 -y -loglevel quiet
    echo "  ✅ cam1_color.mp4 (MJPEG 원본) 생성 완료"
fi

echo
echo "4️⃣ 듀얼 카메라 동시 캡처 테스트"
echo "========================================"

echo "  📹 두 카메라 동시 캡처 시작..."

# 백그라운드에서 카메라 0
rpicam-vid --camera 0 --width 640 --height 480 --timeout 5000 \
    --codec yuv420 --output dual_cam0.yuv --nopreview &
PID0=$!

# 백그라운드에서 카메라 1  
rpicam-vid --camera 1 --width 640 --height 480 --timeout 5000 \
    --codec yuv420 --output dual_cam1.yuv --nopreview &
PID1=$!

echo "  ⏳ 두 카메라 캡처 대기 중..."
wait $PID0
wait $PID1

# 변환
if [ -f "dual_cam0.yuv" ]; then
    ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 640x480 -r 30 \
        -i dual_cam0.yuv -c:v libx264 -preset fast -crf 18 \
        dual_cam0.mp4 -y -loglevel quiet
    echo "  ✅ dual_cam0.mp4 완료"
fi

if [ -f "dual_cam1.yuv" ]; then
    ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 640x480 -r 30 \
        -i dual_cam1.yuv -c:v libx264 -preset fast -crf 18 \
        dual_cam1.mp4 -y -loglevel quiet
    echo "  ✅ dual_cam1.mp4 완료"
fi

echo
echo "📊 생성된 영상 파일들:"
echo "========================================"

for file in cam0_640x480.mp4 cam0_hd.mp4 cam1_640x480.mp4 cam1_hd.mp4 \
            cam0_color.mp4 cam1_color.mp4 dual_cam0.mp4 dual_cam1.mp4; do
    if [ -f "$file" ]; then
        size=$(ls -lh "$file" | awk '{print $5}')
        duration=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$file" 2>/dev/null | cut -d. -f1)
        echo "✅ $file ($size, ${duration}초)"
    else
        echo "❌ $file - 생성 실패"
    fi
done

echo
echo "🎯 해상도별 비교:"
echo "----------------------------------------"
echo "640x480 (SD):  더 빠른 처리, 낮은 CPU"
echo "1280x720 (HD): 더 선명한 화질, 높은 CPU"
echo 
echo "📷 카메라별 비교:"
echo "----------------------------------------"
echo "카메라 0: /base/axi/pcie@1000120000/rp1/i2c@88000"
echo "카메라 1: /base/axi/pcie@1000120000/rp1/i2c@80000"

echo
echo "🎨 색상 향상 팁:"
echo "----------------------------------------"
echo "YUV420: 무압축, 큰 파일, 때때로 색상 이상"
echo "MJPEG: 압축됨, 좋은 색상, 높은 CPU"
echo "H.264: 최고 압축, 하드웨어 지원 없음"

echo
echo "✅ 종합 카메라 테스트 완료!"