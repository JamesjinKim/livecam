# 🎥 라즈베리파이 5 블랙박스 시스템

> **듀얼 카메라 기반 실시간 영상 녹화 및 스트리밍 시스템**

[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red)](https://www.raspberrypi.org/)
[![Camera](https://img.shields.io/badge/Camera-OV5647%20Dual-blue)](https://www.uctronics.com/)
[![Video](https://img.shields.io/badge/Format-MP4%20H.264-green)](https://en.wikipedia.org/wiki/H.264)
[![FPS](https://img.shields.io/badge/FPS-30-yellow)](https://en.wikipedia.org/wiki/Frame_rate)

## 📌 시스템 개요

라즈베리파이 5 기반 고성능 블랙박스 시스템으로 **듀얼 카메라 동시 녹화**, **실시간 웹 스트리밍**, **다중 해상도 지원**을 제공합니다.

### ✨ 주요 특징
- 🎬 **듀얼 카메라 동시 녹화** - 전방/후방 독립적 영상 저장
- 📺 **다중 해상도 지원** - 640x480, 1280x720, 1920x1080
- 🎯 **30fps 안정적 녹화** - H.264 하드웨어 인코딩
- 🌐 **실시간 웹 스트리밍** - MJPEG HTTP 서버 내장
- 💾 **MP4 직접 저장** - 변환 없이 바로 재생 가능
- ⚡ **간단한 사용법** - 한 줄 명령으로 즉시 실행

## 🚀 빠른 시작

### 1단계: 카메라 확인
```bash
rpicam-hello --list-cameras
```

### 2단계: 듀얼 카메라 테스트
```bash
cd ~/livecam
./start_blackbox.sh quick
```

### 3단계: 본격 녹화
```bash
# 640x480 듀얼 녹화
./start_blackbox.sh dual-640

# Ctrl+C로 중단하면 자동으로 MP4 저장
```

## 🎮 사용 방법

### 📹 단일 카메라 모드
```bash
./start_blackbox.sh cam0-640      # 카메라 0번 - 640x480
./start_blackbox.sh cam1-640      # 카메라 1번 - 640x480
./start_blackbox.sh cam0-720p     # 카메라 0번 - 1280x720
./start_blackbox.sh cam1-720p     # 카메라 1번 - 1280x720
./start_blackbox.sh cam0-1080p    # 카메라 0번 - 1920x1080
./start_blackbox.sh cam1-1080p    # 카메라 1번 - 1920x1080
```

### 🎬 듀얼 카메라 모드
```bash
./start_blackbox.sh dual-640      # 두 카메라 동시 - 640x480
./start_blackbox.sh dual-720p     # 두 카메라 동시 - 1280x720
./start_blackbox.sh dual-1080p    # 두 카메라 동시 - 1920x1080
```

### 🌐 스트리밍 모드
```bash
./start_blackbox.sh stream        # 실시간 MJPEG 웹 스트리밍 (포트 8080)
# 브라우저에서 http://라즈베리파이IP:8080/ 접속
```

### ⚡ 테스트 모드
```bash
./start_blackbox.sh quick         # 3초 듀얼 카메라 테스트
./start_blackbox.sh demo          # 10초 모든 해상도 데모
```

## 📊 성능 사양

| 모드 | 해상도 | 예상 CPU | 파일크기/10초 | 특징 |
|------|--------|---------|---------------|------|
| **단일 640** | 640×480 | ~10% | ~1.5MB | 기본 모드 |
| **단일 720p** | 1280×720 | ~15% | ~12MB | HD 화질 |
| **단일 1080p** | 1920×1080 | ~20% | ~25MB | 풀HD 화질 |
| **듀얼 640** | 640×480 × 2 | ~20% | ~2.5MB | 듀얼 기본 |
| **듀얼 720p** | 1280×720 × 2 | ~30% | ~25MB | 듀얼 HD |
| **듀얼 1080p** | 1920×1080 × 2 | ~40% | ~50MB | 듀얼 풀HD |
| **스트리밍** | 640×480 | ~15% | - | 실시간 웹 |

## 📁 저장 구조

영상 파일은 해상도와 카메라별로 자동 분류됩니다:

```
videos/
├── 640x480/
│   ├── cam0/          # 카메라 0번 640x480 영상
│   └── cam1/          # 카메라 1번 640x480 영상
├── 1280x720/
│   ├── cam0/          # 카메라 0번 720p 영상
│   └── cam1/          # 카메라 1번 720p 영상
└── 1920x1080/
    ├── cam0/          # 카메라 0번 1080p 영상
    └── cam1/          # 카메라 1번 1080p 영상
```

## 💻 시스템 요구사항

### 하드웨어
- **Raspberry Pi 5** (4GB RAM 이상 권장)
- **OV5647 카메라 모듈** × 1~2개
- **32GB+ microSD 카드** (Class 10)
- **5V/3A 전원 어댑터**

### 소프트웨어
- **Raspberry Pi OS** (64-bit)
- **rpicam-apps** (카메라 소프트웨어)
- **FFmpeg** (영상 분석용)

## 🔧 설치 방법

### 1. 기본 패키지 설치
```bash
sudo apt update
sudo apt install rpicam-apps ffmpeg libjpeg-dev build-essential
```

### 2. 프로젝트 다운로드
```bash
cd ~
git clone [저장소_URL] livecam
cd livecam
chmod +x start_blackbox.sh
```

### 3. 카메라 활성화
```bash
sudo raspi-config
# Interface Options → Camera → Enable
# 재부팅
```

## 🔄 실시간 스트리밍

### 웹 스트리밍 서버 시작
```bash
./start_blackbox.sh stream
```

### 접속 방법
- **웹 브라우저**: `http://라즈베리파이IP:8080/`
- **VLC 플레이어**: 네트워크 스트림으로 URL 입력
- **Python OpenCV**: `cv2.VideoCapture("http://IP:8080/")`

### 스트리밍 특징
- **MJPEG HTTP 스트리밍** (웹 브라우저 호환)
- **최대 10개 클라이언트** 동시 접속
- **640x480 @ 30fps** 실시간 전송
- **적응형 품질 제어**

## 🛠️ 문제 해결

### 카메라 인식 안됨
```bash
# 카메라 상태 확인
rpicam-hello --list-cameras

# 재부팅 후 재시도
sudo reboot
```

### 권한 오류
```bash
# 실행 권한 부여
chmod +x start_blackbox.sh

# video 그룹 추가
sudo usermod -a -G video $USER
```

### 저장 공간 부족
```bash
# 공간 확인
df -h

# 오래된 영상 삭제 (7일 이상)
find videos/ -name "*.mp4" -mtime +7 -delete
```

## 📋 개발자 정보

### 프로젝트 구조
```
livecam/
├── README.md              # 사용자 가이드
├── start_blackbox.sh      # 메인 실행 스크립트 ⭐
├── src/
│   ├── core/             # 카메라 캡처 시스템
│   ├── streaming/        # 실시간 스트리밍 서버
│   └── legacy/          # 실험적 구현
└── videos/              # 영상 저장 디렉토리
```

### 핵심 시스템
- **`src/core/`**: RpiCameraCapture 기반 듀얼 카메라 시스템
- **`src/streaming/`**: MJPEG HTTP 스트리밍 서버
- **`start_blackbox.sh`**: 통합 실행 스크립트 (메인)

## 📞 지원

- **이슈 리포트**: GitHub Issues
- **기능 요청**: GitHub Discussions  
- **기술 문의**: 개발팀 이메일

---

**🎬 라즈베리파이 5로 전문가급 블랙박스를 경험해보세요!**