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
# 개선된 안정적 스트리밍 서버 (화면 깨짐 문제 해결)
source venv/bin/activate && python streaming_server_fixed.py
# 브라우저에서 http://라즈베리파이IP:8000/ 접속
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

**화면 깨짐 문제 해결됨** - 개선된 스트리밍 서버 사용

### 웹 스트리밍 서버 시작
```bash
source venv/bin/activate && python streaming_server_fixed.py
```

### 접속 방법
- **웹 브라우저**: `http://라즈베리파이IP:8000/`

### 주요 개선사항
- **프레임 무결성 보장**: JPEG 마커 기준 안전한 버퍼 처리로 화면 깨짐 완전 해결
- **메모리 최적화**: 200KB 최대 버퍼 사용
- **안정적 품질**: 640x480@25fps, MJPEG 85%

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

### 🌐 스트리밍 문제 해결

#### 화면 깨짐 현상
```bash
# 개선된 서버 사용 (화면 깨짐 문제 해결됨)
source venv/bin/activate && python streaming_server_fixed.py
```

#### 의존성 설치
```bash
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn
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
├── README.md                    # 사용자 가이드
├── CLAUDE.md                    # 개발자 기술 문서  
├── start_blackbox.sh           # 블랙박스 녹화 스크립트 ⭐
├── streaming_server_fixed.py   # 안정화된 스트리밍 서버 ⭐
├── venv/                       # Python 가상환경
├── src/                        # C++ 소스 (실험적)
├── scripts/                    # 유틸리티 스크립트
└── videos/                     # 영상 저장 디렉토리
    ├── 640x480/               # 기본 해상도
    ├── 1280x720/              # HD 해상도  
    └── 1920x1080/             # 풀HD 해상도
```

### 핵심 시스템
- **`start_blackbox.sh`**: 듀얼 카메라 블랙박스 녹화 (메인)
- **`streaming_server_fixed.py`**: 화면 깨짐 해결된 웹 스트리밍

## 📞 지원

- **이슈 리포트**: GitHub Issues
- **기능 요청**: GitHub Discussions  
- **기술 문의**: 개발팀 이메일

---


● MP4 저장과 스트리밍의 관계

  두 가지 독립적 파이프라인:
  1. 녹화 파이프라인: rpicam-vid → H.264 인코딩 → MP4 파일 저장
  2. 스트리밍 파이프라인: rpicam-vid → MJPEG/H.264 → HTTP 스트림
