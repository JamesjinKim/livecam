# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

라즈베리파이 5 기반 최적화된 블랙박스 시스템. 하드웨어 인코딩 미지원 문제 해결 및 적응형 압축 시스템 구현으로 30+ FPS 안정적 성능 달성.

**⚠️ 중요**: 라즈베리파이 5는 H.264 **하드웨어 인코딩 미지원** 확인됨 → libx264 소프트웨어 인코딩 사용

## Build System

### 라즈베리파이 5 전용 빌드 (rpicam 최적화)
```bash
make -f Makefile.rpi                    # 전체 빌드
make -f Makefile.rpi check-deps         # 의존성 확인  
make -f Makefile.rpi demo               # 코어 기능 테스트
make -f Makefile.rpi test               # 카메라 테스트
make -f Makefile.rpi clean              # 정리
```

**필수 의존성**: `build-essential`, `rpicam-apps`, `libjpeg-dev`, `pkg-config`

### 실행 명령어
```bash
./test_camera_rpi -v                    # 자동 최적화 (권장)
./test_camera_rpi --test -f 5 -v        # 5프레임 캡처
./test_camera_rpi -b -v                 # 성능 벤치마크
./demo_test_rpi all                     # 전체 기능 테스트
```

## Architecture (2025 Optimized)

### 핵심 구성요소
- **RpiCameraCapture**: rpicam-vid 파이프라인 + 적응형 압축
- **메모리 풀**: 8버퍼 재사용으로 할당/해제 최소화  
- **자동 복구**: 카메라 연결 상태 모니터링 및 재연결
- **성능 모니터링**: 실시간 FPS/CPU 부하 추적

### 적응형 압축 시스템
```cpp
format="auto" → 시스템 리소스 분석 → 최적 형식 선택
FPS < 20 감지 → 자동으로 더 가벼운 형식 전환
H.264 선택시 → 자동으로 YUV420 대체 + 경고 표시
```

## Performance Optimization

### 라즈베리파이 5 하드웨어 인코딩 미지원 대응

| 형식 | CPU 사용률 | 상태 | 용도 |
|------|-----------|------|------|
| **yuv420** | ~5% | ✅ 권장 | 기본 최적 성능 |
| **mjpeg** | ~30% | ✅ 허용 | 네트워크 전송시 |  
| **raw** | ~3% | ✅ 허용 | 특수 목적 |
| **h264** | ~100% | ❌ 자동차단 | YUV420 대체 |

### 성능 목표 달성 현황
- ✅ **30+ FPS**: rpicam 최적화로 달성
- ✅ **CPU 5-15%**: 적응형 압축으로 달성  
- ✅ **24/7 운영**: 자동 복구 메커니즘
- ✅ **메모리 최적화**: 메모리 풀 구현

## Key Features

### Camera Configuration  
- **멀티 카메라**: camera 0, 1 동시 지원
- **해상도**: 320x240 ~ 1920x1080 가변
- **형식**: auto, yuv420, mjpeg, raw (h264 제외)
- **자동 최적화**: 시스템 리소스 기반 형식 선택

### 📹 듀얼 카메라 구분 방법
```bash
# 카메라 목록 확인
rpicam-hello --list-cameras

# 카메라별 구분
카메라 0번: i2c@88000 (88000번 I2C 버스) → /dev/media0
카메라 1번: i2c@80000 (80000번 I2C 버스) → /dev/media1
```

### 🎯 카메라별 YUV420 사용법 (최적 성능)
```bash
# 카메라 0번 - 최소 CPU 사용
rpicam-vid --camera 0 --codec yuv420 --width 640 --height 480 --timeout 5000 --output camera0.yuv --nopreview

# 카메라 1번 - 최소 CPU 사용  
rpicam-vid --camera 1 --codec yuv420 --width 640 --height 480 --timeout 5000 --output camera1.yuv --nopreview

# 동시 사용 (권장)
rpicam-vid --camera 0 --codec yuv420 --width 640 --height 480 --timeout 10000 --output front.yuv --nopreview &
rpicam-vid --camera 1 --codec yuv420 --width 640 --height 480 --timeout 10000 --output rear.yuv --nopreview &
wait
```

### Adaptive Compression
- **실시간 모니터링**: FPS/CPU 부하 추적
- **자동 전환**: 부하 감지시 더 가벼운 형식으로 전환  
- **복구 메커니즘**: 카메라 연결 해제시 자동 재연결

### Error Handling
- **H.264 차단**: 선택시 자동으로 YUV420 대체
- **명확한 경고**: 성능 문제 사전 알림
- **복구 로직**: 100초 무응답시 자동 재연결

## Testing Commands

### 기본 테스트
```bash  
./test_camera_rpi -c 0 -v               # 카메라 0 테스트
./test_camera_rpi -c 1 -v               # 카메라 1 테스트
```

### 성능 테스트  
```bash
./test_camera_rpi -b                    # 10초 벤치마크
./test_camera_rpi --test -w 640 -h 480  # 저해상도 테스트
```

### 시스템 테스트
```bash
./simple_camera_test.sh                 # 하드웨어 테스트
./demo_test_rpi system                  # 시스템 정보
```

## File Structure

```
├── RpiCameraCapture.cpp                # 메인 캡처 클래스 (적응형 압축)
├── RpiCameraCapture.hpp                # 헤더 (메모리 풀 포함)  
├── TestCameraRpi.cpp                   # 카메라 테스트 유틸
├── DemoTestRpi.cpp                     # 코어 기능 데모
├── Makefile.rpi                        # 라즈베리파이 5 빌드
├── simple_camera_test.sh               # 하드웨어 테스트
├── README.md                           # 완전한 문서
└── PRD.md                              # 요구사항 (한글)
```

## Important Notes

### H.264 처리 정책
- **완전 금지 아님**: 코드에서 지원하나 자동 차단
- **자동 대체**: H.264 선택시 → YUV420 전환  
- **경고 표시**: 명확한 에러 메시지로 사용자 알림

### 메모리 관리
- **메모리 풀**: 8개 버퍼 재사용으로 GC 부하 최소화
- **동적 크기**: 형식에 따른 버퍼 크기 자동 조절
- **제로카피**: move semantics로 복사 최소화

### 자동 복구 시스템
- **연결 모니터링**: 100초 무응답시 재연결 시도
- **적응형 압축**: FPS < 20시 자동으로 가벼운 형식 전환
- **상세 로깅**: verbose 모드에서 디버그 정보 제공

중요사항
1.응답은 반드시 한글로 할것!