#!/bin/bash
# organize_project.sh
# 프로젝트 최종 정리 스크립트

echo "🗂️ 라즈베리파이 5 livecam 프로젝트 최종 정리"
echo

# 1. 폴더 구조 생성
echo "1️⃣ 폴더 구조 생성..."

mkdir -p src/core src/optimized src/legacy build videos/640x480 videos/hd videos/tests docs scripts

echo "✅ 폴더 구조 생성 완료"

# 2. 최종 핵심 소스코드 분류
echo
echo "2️⃣ 핵심 소스코드 분류..."

# 핵심 소스코드 (최종 버전)
echo "  📁 src/core/ - 핵심 소스코드"
mv RpiCameraCapture.cpp src/core/ 2>/dev/null
mv RpiCameraCapture.hpp src/core/ 2>/dev/null
mv TestCameraRpi.cpp src/core/ 2>/dev/null

# 최적화 소스코드
echo "  📁 src/optimized/ - 최적화 구현"
mv OptimizedCapture.cpp src/optimized/ 2>/dev/null
mv OptimizedCapture.hpp src/optimized/ 2>/dev/null
mv GpuVideoProcessor.cpp src/optimized/ 2>/dev/null
mv IntegratedOptimizer.cpp src/optimized/ 2>/dev/null
mv FixedMmapCapture.cpp src/optimized/ 2>/dev/null

# 레거시 코드 (삭제 예정)
echo "  📁 src/legacy/ - 레거시 코드"
mv DmaCapture640.cpp src/legacy/ 2>/dev/null
mv DmaCaptureHD.cpp src/legacy/ 2>/dev/null
mv RpiCamDirect.cpp src/legacy/ 2>/dev/null
mv V4L2DirectCapture.cpp src/legacy/ 2>/dev/null

# 빌드 시스템
echo "  📁 build/ - 빌드 시스템"
cp Makefile.optimized build/
cp Makefile.rpi build/

echo "✅ 소스코드 분류 완료"

# 3. 영상 파일 분류
echo
echo "3️⃣ 영상 파일 분류..."

# 640x480 영상들
echo "  📁 videos/640x480/ - SD 해상도 영상"
mv cam0_640x480.mp4 videos/640x480/ 2>/dev/null
mv cam1_640x480.mp4 videos/640x480/ 2>/dev/null
mv dual_cam0.mp4 videos/640x480/ 2>/dev/null  
mv dual_cam1.mp4 videos/640x480/ 2>/dev/null
mv basic_capture.mp4 videos/640x480/ 2>/dev/null
mv fixed_mmap_output.mp4 videos/640x480/ 2>/dev/null

# HD 영상들
echo "  📁 videos/hd/ - HD 해상도 영상" 
mv cam0_hd.mp4 videos/hd/ 2>/dev/null
mv cam1_hd.mp4 videos/hd/ 2>/dev/null
mv hd_test_28fps.mp4 videos/hd/ 2>/dev/null

# 테스트 영상들
echo "  📁 videos/tests/ - 테스트 영상"
mv cam0_color.mp4 videos/tests/ 2>/dev/null
mv cam1_color.mp4 videos/tests/ 2>/dev/null
mv test_optimized_demo.mp4 videos/tests/ 2>/dev/null
mv camera0_test.mp4 videos/tests/ 2>/dev/null
mv camera1_test.mp4 videos/tests/ 2>/dev/null
mv test_cam1.mp4 videos/tests/ 2>/dev/null
mv mmap_optimized.mp4 videos/tests/ 2>/dev/null

echo "✅ 영상 파일 분류 완료"

# 4. 스크립트 파일 정리
echo
echo "4️⃣ 스크립트 파일 정리..."
echo "  📁 scripts/ - 유틸리티 스크립트"

mv create_test_video.sh scripts/ 2>/dev/null
mv comprehensive_camera_test.sh scripts/ 2>/dev/null
cp *.sh scripts/ 2>/dev/null

echo "✅ 스크립트 정리 완료"

# 5. 문서 정리
echo
echo "5️⃣ 문서 정리..."
echo "  📁 docs/ - 프로젝트 문서"

mv README.md docs/ 2>/dev/null
mv PRD.md docs/ 2>/dev/null
mv CLAUDE.md docs/ 2>/dev/null
mv DMA.txt docs/ 2>/dev/null

echo "✅ 문서 정리 완료"

# 6. 불필요한 파일 삭제
echo
echo "6️⃣ 불필요한 파일 정리..."

# 임시 파일 삭제
rm -f *.yuv *.mjpeg *.h264 2>/dev/null
rm -f temp_* test_* benchmark_* mmap_3sec.yuv 2>/dev/null
rm -f *.log monitor_cpu.sh 2>/dev/null
rm -f optimized_capture gpu_processor integrated_optimizer fixed_mmap_capture 2>/dev/null
rm -f rpicam_direct v4l2_dma_capture dma_capture_hd 2>/dev/null

# 중복 Makefile 정리
rm -f Makefile.dma Makefile.v4l2 2>/dev/null

echo "✅ 불필요한 파일 정리 완료"

# 7. 최종 프로젝트 구조 출력
echo
echo "📂 최종 프로젝트 구조:"
echo "========================================"
tree -I '__pycache__|*.pyc|.git' || find . -type d | sort

echo
echo "📊 파일 통계:"
echo "----------------------------------------"
echo "핵심 소스코드: $(find src/core -name "*.cpp" -o -name "*.hpp" | wc -l)개"
echo "최적화 코드: $(find src/optimized -name "*.cpp" -o -name "*.hpp" | wc -l)개"  
echo "SD 영상: $(find videos/640x480 -name "*.mp4" | wc -l)개"
echo "HD 영상: $(find videos/hd -name "*.mp4" | wc -l)개"
echo "테스트 영상: $(find videos/tests -name "*.mp4" | wc -l)개"

# 8. 최종 빌드 테스트
echo
echo "7️⃣ 최종 빌드 테스트..."
cd build
if make -f Makefile.optimized optimized_capture >/dev/null 2>&1; then
    echo "✅ 최적화 시스템 빌드 성공"
else
    echo "⚠️  최적화 시스템 빌드 실패 (의존성 확인 필요)"
fi

cd ..

echo
echo "✅ 프로젝트 정리 완료!"
echo
echo "🚀 사용법:"
echo "----------------------------------------"
echo "핵심 시스템 빌드: cd build && make -f Makefile.rpi"
echo "최적화 시스템: cd build && make -f Makefile.optimized"
echo "영상 재생: vlc videos/640x480/*.mp4"
echo "문서 확인: cat docs/README.md"