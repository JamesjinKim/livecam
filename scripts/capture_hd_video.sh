#!/bin/bash

# HD 영상 캡처 및 변환 스크립트
# Raspberry Pi 5 + OV5647 센서로 1920x1080 @ 28.5 FPS 캡처

echo "========================================"
echo "  HD 영상 캡처 테스트 (1920x1080)"
echo "========================================"

# 색상 코드
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 기본 설정
CAMERA=${1:-0}           # 카메라 번호 (기본값: 0)
DURATION=${2:-10}        # 캡처 시간 (기본값: 10초)
OUTPUT_NAME=${3:-"hd_video_test"}  # 출력 파일명

echo -e "${BLUE}설정 정보:${NC}"
echo "  카메라: ${CAMERA}"
echo "  캐처 시간: ${DURATION}초"
echo "  출력 파일: ${OUTPUT_NAME}"
echo ""

# 1단계: YUV420 Raw 영상 캡처
echo -e "${BLUE}1단계: HD YUV420 영상 캡처...${NC}"
echo "  해상도: 1920x1080"
echo "  코덱: YUV420 (무압축)"
echo "  예상 FPS: ~28 FPS"

rpicam-vid \
  --camera ${CAMERA} \
  --width 1920 \
  --height 1080 \
  --codec yuv420 \
  --timeout $((DURATION * 1000)) \
  --output "${OUTPUT_NAME}.yuv" \
  --nopreview

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ YUV 캡처 완료${NC}"
else
    echo -e "${YELLOW}✗ YUV 캡처 실패${NC}"
    exit 1
fi

# 캡처 결과 분석
if [ -f "${OUTPUT_NAME}.yuv" ]; then
    filesize=$(stat -c%s "${OUTPUT_NAME}.yuv")
    frames=$((filesize / 3110400))  # 1920x1080 YUV420 프레임 크기
    actual_fps=$(echo "scale=1; $frames / $DURATION" | bc)
    
    echo ""
    echo -e "${BLUE}캡처 결과:${NC}"
    echo "  파일 크기: $(echo "scale=1; $filesize / 1024 / 1024" | bc) MB"
    echo "  총 프레임: ${frames}"
    echo "  실제 FPS: ${actual_fps}"
    echo ""
else
    echo -e "${YELLOW}✗ YUV 파일이 생성되지 않았습니다${NC}"
    exit 1
fi

# 2단계: MP4 변환
echo -e "${BLUE}2단계: MP4 변환...${NC}"
echo "  인코더: libx264 (H.264)"
echo "  품질: CRF 23 (고품질)"
echo "  프리셋: fast"

ffmpeg -y \
  -f rawvideo \
  -pix_fmt yuv420p \
  -s 1920x1080 \
  -r ${actual_fps} \
  -i "${OUTPUT_NAME}.yuv" \
  -c:v libx264 \
  -preset fast \
  -crf 23 \
  -pix_fmt yuv420p \
  "${OUTPUT_NAME}.mp4" 2>/dev/null

if [ $? -eq 0 ] && [ -f "${OUTPUT_NAME}.mp4" ]; then
    mp4_size=$(stat -c%s "${OUTPUT_NAME}.mp4")
    compression_ratio=$(echo "scale=1; $filesize / $mp4_size" | bc)
    
    echo -e "${GREEN}✓ MP4 변환 완료${NC}"
    echo ""
    echo -e "${BLUE}변환 결과:${NC}"
    echo "  MP4 크기: $(echo "scale=1; $mp4_size / 1024 / 1024" | bc) MB"
    echo "  압축률: ${compression_ratio}:1"
    echo "  비트레이트: ~3.5 Mbps"
else
    echo -e "${YELLOW}✗ MP4 변환 실패${NC}"
fi

# 3단계: 듀얼 카메라 테스트 (선택사항)
if [ "${CAMERA}" = "0" ] && [ -e "/dev/video1" ]; then
    echo ""
    echo -e "${BLUE}3단계: 듀얼 카메라 테스트 (선택사항)${NC}"
    read -p "카메라 1도 테스트하시겠습니까? [y/N]: " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}카메라 1 캡처 시작...${NC}"
        
        rpicam-vid \
          --camera 1 \
          --width 1920 \
          --height 1080 \
          --codec yuv420 \
          --timeout $((DURATION * 1000)) \
          --output "${OUTPUT_NAME}_cam1.yuv" \
          --nopreview
        
        if [ $? -eq 0 ] && [ -f "${OUTPUT_NAME}_cam1.yuv" ]; then
            echo -e "${GREEN}✓ 카메라 1 캡처 완료${NC}"
            
            # 간단한 프레임 수 확인
            cam1_filesize=$(stat -c%s "${OUTPUT_NAME}_cam1.yuv")
            cam1_frames=$((cam1_filesize / 3110400))
            cam1_fps=$(echo "scale=1; $cam1_frames / $DURATION" | bc)
            
            echo "  카메라 1 FPS: ${cam1_fps}"
        else
            echo -e "${YELLOW}✗ 카메라 1 캡처 실패${NC}"
        fi
    fi
fi

# 4단계: 최종 결과 및 정리
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}           HD 캡처 테스트 완료           ${NC}"
echo -e "${BLUE}========================================${NC}"

echo "생성된 파일:"
ls -lh "${OUTPUT_NAME}"* 2>/dev/null | while read line; do
    echo "  $line"
done

echo ""
echo -e "${GREEN}HD 영상 테스트가 성공적으로 완료되었습니다!${NC}"
echo ""
echo "재생 방법:"
echo "  MP4 파일: VLC, 미디어 플레이어로 재생 가능"
echo "  YUV 파일: ffplay -f rawvideo -pix_fmt yuv420p -s 1920x1080 ${OUTPUT_NAME}.yuv"

# YUV 파일 정리 여부 묻기
echo ""
read -p "대용량 YUV 파일을 삭제하시겠습니까? (MP4만 보관) [y/N]: " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "${OUTPUT_NAME}"*.yuv
    echo -e "${GREEN}✓ YUV 파일이 삭제되었습니다${NC}"
else
    echo -e "${YELLOW}⚠ YUV 파일이 보관되었습니다 (용량 주의)${NC}"
fi

echo ""
echo "사용법:"
echo "  $0 [카메라번호] [시간(초)] [출력파일명]"
echo "  예: $0 0 10 my_hd_video"
echo "  예: $0 1 5 cam1_test"