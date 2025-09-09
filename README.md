# 🎥 라즈베리파이 통합 CCTV 시스템

라즈베리파이 5 기반 듀얼 카메라 CCTV 스트리밍 및 모션 감지 블랙박스 시스템

## 📋 시스템 구성

### 🔴 Part 1: 실시간 CCTV 스트리밍 (picam2_main.py)
웹 브라우저를 통한 실시간 영상 모니터링 및 카메라 제어

### ⚫ Part 2: 모션 감지 블랙박스 (detection_cam0.py, detection_cam1.py)
OpenCV 기반 지능형 모션 감지 및 이벤트 녹화 시스템

---

## 🚀 빠른 시작

### 필수 요구사항
- **하드웨어**: Raspberry Pi 5, OV5647 카메라 모듈 ×2
- **OS**: Raspberry Pi OS (64-bit)
- **Python**: 3.11+

### 설치

#### 🚀 자동 설치 (권장)
```bash
# 저장소 클론
git clone https://github.com/JamesjinKim/livecam.git
cd livecam

# 자동 설치 스크립트 실행
./install.sh
```

#### 🔧 수동 설치
```bash
# 시스템 패키지 설치
sudo apt update
sudo apt install -y rpicam-apps ffmpeg python3-pip

# Python 의존성 설치
pip3 install -r requirements.txt --break-system-packages

# 사용자 권한 설정
sudo usermod -a -G video $USER
# 재로그인 필요
```

---

## 🔴 Part 1: CCTV 실시간 스트리밍

### ✨ 주요 기능
- 🎯 **단일 클라이언트 제한**: 안정적인 30fps 스트리밍
- 🔄 **듀얼 카메라 토글**: 실시간 카메라 전환 (< 3초)
- 📺 **동적 해상도**: 480p/720p 선택
- 📊 **실시간 통계**: FPS, 프레임 수, 데이터 크기
- 🌐 **웹 인터페이스**: 브라우저 기반 제어

### 🎮 사용 방법

#### 1. CCTV 스트리밍 시작
```bash
python3 picam2_main.py
```

#### 2. 웹 접속
```
브라우저에서 접속: http://라즈베리파이_IP:8001
```

#### 3. 인터페이스 사용
- **카메라 전환**: Camera 0 ↔ Camera 1 버튼 클릭
- **해상도 변경**: 480p / 720p 버튼 선택
- **상태 확인**: 실시간 통계 패널 모니터링

### 📱 웹 인터페이스 미리보기
```
┌─────────────────────────────────────────┐
│  📹 라즈베리파이 CCTV 시스템             │
├─────────────────────────────────────────┤
│  [Camera 0] [Camera 1]  현재: Camera 0  │
│  [480p] [720p]         해상도: 640×480   │
├─────────────────────────────────────────┤
│  ████████ 실시간 영상 ████████           │
│  ████████████████████████████           │
│  ████████████████████████████           │
├─────────────────────────────────────────┤
│  📊 FPS: 30.0 | 프레임: 1250 | 31KB     │
│  🟢 스트리밍 중                          │
└─────────────────────────────────────────┘
```

### ⚙️ 설정 최적화

#### 성능 튜닝
```python
# main.py 내 설정값 수정
RESOLUTIONS = {
    "640x480": {"width": 640, "height": 480},    # 30fps, ~31KB/frame
    "1280x720": {"width": 1280, "height": 720}  # 25fps, ~109KB/frame
}

MAX_CLIENTS = 1  # 단일 클라이언트 제한
```

#### 네트워크 최적화
- **내부 네트워크**: 최상의 성능
- **WiFi**: 480p 권장
- **유선 연결**: 720p 고품질

### 🔧 문제 해결

#### 카메라 인식 오류
```bash
# 카메라 확인
rpicam-hello --list-cameras

# 카메라 테스트
rpicam-hello --camera 0 --timeout 2000
```

#### 스트리밍 불안정
- 다른 클라이언트 연결 여부 확인
- 네트워크 대역폭 확인
- 라즈베리파이 온도 체크

---

## ⚫ Part 2: 모션 감지 블랙박스

### ✨ 주요 기능
- 🎯 **스마트 모션 감지**: OpenCV 기반 지능형 알고리즘
- ⏰ **프리버퍼 시스템**: 모션 5초 전부터 녹화
- 📹 **30초 고정 녹화**: 5초 프리 + 25초 포스트
- 📁 **자동 분류**: 날짜별 폴더 정리 (YYMMDD)
- 🔧 **민감도 조절**: 5단계 감도 설정

### 🎮 사용 방법

#### 1. 모션 감지 시작
```bash
# Camera 0 모니터링
python3 detection_cam0.py

# Camera 1 모니터링 (별도 터미널)
python3 detection_cam1.py
```

#### 2. 실시간 로그 확인
```
Motion Detection System - Camera 0
========================================
   민감도: LOW | 임계값: 10000px | 쿨다운: 12s
   Pre-buffer: 5s | Post-buffer: 25s | Total: 30s
   
🎬 Motion Event Recording Started
  Pre-buffer: 5s (from circular buffer)  
  Post-buffer: 25s (new recording)
  
✅ Video merged successfully: 250908/motion_event_cam0_20250908_143025.mp4
  - Final duration: 30.0s (expected: 30s, diff: 0.0s)
  ✓ Pre-buffer successfully included in final video
```

#### 3. 녹화 영상 확인
```
videos/motion_events/
├── cam0/
│   └── 250908/  # 오늘 날짜
│       ├── motion_event_cam0_20250908_143025.mp4  (5.6MB)
│       └── motion_event_cam0_20250908_151200.mp4  (5.8MB)
└── cam1/
    └── 250908/
        └── motion_event_cam1_20250908_144530.mp4  (5.4MB)
```

### ⚙️ 민감도 설정

#### 감도 레벨 선택
```python
# detection_cam0.py 또는 detection_cam1.py에서 수정
CURRENT_SENSITIVITY = 'low'  # 기본 권장값
```

| 레벨 | 임계값 | 쿨다운 | 적용 상황 |
|------|--------|--------|-----------|
| `very_low` | 15000px | 15s | 사람이 지나갈 때만 |
| `low` | 10000px | 12s | **팔을 크게 흔들 때** (권장) |
| `medium` | 6000px | 8s | 손 전체 움직임 |
| `high` | 3000px | 5s | 작은 움직임도 감지 |
| `very_high` | 1000px | 3s | 매우 민감 (노이즈 포함) |

### 📊 성능 모니터링

#### 실시간 상태
```
Buffer: 5.0s (50 frames @ 10fps)
Background stabilized with 60 frames - motion detection active
Simple Debug: 0 changed pixels
Motion detected: 21701 changed pixels  ← 감지!
```

#### 시스템 리소스
- **CPU 사용률**: ~15-20% (단일 카메라)
- **메모리**: ~50-60MB
- **디스크**: ~5-6MB per 30초 영상

### 🔧 설정 최적화

#### 녹화 품질 조정
```python
# 해상도 변경 (detection_cam0.py)
RECORDING_WIDTH = 1280     # 가로 해상도
RECORDING_HEIGHT = 720     # 세로 해상도

# 버퍼 시간 조정
PRE_BUFFER_DURATION = 5    # 프리버퍼 (5초 권장)
POST_BUFFER_DURATION = 25  # 포스트버퍼 (25초)
```

#### 저장 공간 관리
```bash
# 용량 확인
du -h videos/motion_events/

# 오래된 파일 정리 (30일 이상)
find videos/motion_events/ -name "*.mp4" -mtime +30 -delete
```

---

## 🔄 통합 운영 가이드

### 동시 실행 권장 방법

#### 터미널 1: CCTV 실시간 모니터링
```bash
python3 picam2_main.py
# → http://라즈베리파이_IP:8001 접속
```

#### 터미널 2: 카메라 0 모션 감지
```bash
python3 detection_cam0.py
# → videos/motion_events/cam0/ 저장
```

#### 터미널 3: 카메라 1 모션 감지
```bash
python3 detection_cam1.py  
# → videos/motion_events/cam1/ 저장
```

### 💡 운영 팁

#### 일반 모니터링
- CCTV 스트리밍만 상시 실행
- 웹 브라우저로 실시간 확인

#### 보안 강화 모드
- 야간 또는 외출 시 모션 감지 추가 실행
- 이벤트 발생 시 자동 30초 영상 저장

#### 리소스 관리
- 두 시스템 동시 실행 시 CPU ~40-50% 사용
- 라즈베리파이 5 권장 (충분한 성능)

---

## ❓ 자주 묻는 질문

### Q: 여러 명이 동시에 CCTV에 접속할 수 있나요?
**A**: 아니요. 성능 안정성을 위해 **1명만** 접속 가능합니다. 추가 접속 시 "다른 사용자가 스트리밍 중입니다" 메시지가 표시됩니다.

### Q: 모션 감지가 너무 자주/적게 작동해요
**A**: `CURRENT_SENSITIVITY` 설정을 조정하세요. `low`(기본) → `medium`(더 민감) 또는 `very_low`(덜 민감)

### Q: 녹화 영상이 30초가 아니에요
**A**: ffmpeg 병합 과정에서 발생할 수 있습니다. 로그에서 "Final duration" 확인하고, 프레임레이트가 통일되었는지 체크하세요.

### Q: 저장 공간이 부족해요
**A**: 하루 100회 모션 감지 시 약 500MB 사용됩니다. 정기적으로 오래된 영상을 삭제하거나 외장 저장소를 사용하세요.

### Q: 카메라가 인식되지 않아요 (Picamera2 대응) ⚡
**A**: 
```bash
# 카메라 연결 확인
rpicam-hello --list-cameras

# Picamera2 라이브러리 확인
python3 -c "from picamera2 import Picamera2; print('Picamera2 OK')"

# GPU 메모리 할당 확인 (256MB 권장)
vcgencmd get_mem gpu

# 권한 확인
sudo usermod -a -G video $USER
# 재로그인 필요
```

### Q: Picamera2와 rpicam-vid 차이점이 뭐예요?
**A**: 
- **rpicam-vid** (구버전): 서브프로세스 방식, 장기 스트리밍 시 멈춤 문제
- **Picamera2** (신버전): GPU 직접 액세스, 안정성 대폭 향상, CPU 20-30% 절약 ⚡

---

## 🛠️ 고급 설정

### systemd 자동 시작 설정
```bash
# /etc/systemd/system/cctv.service
[Unit]
Description=CCTV Streaming System
After=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/livecam
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable cctv.service
sudo systemctl start cctv.service
```

### 방화벽 설정
```bash
# 포트 8001 열기
sudo ufw allow 8001
```

### 성능 최적화
```bash
# GPU 메모리 할당 증가
sudo raspi-config
# Advanced Options → Memory Split → 128
```

---

🔧 라즈베리파이 부팅 시 자동 시작 구현 방법
방법 1: systemd 서비스 (권장)
Write(smart-security.service)
write to smart-security.service

 [Unit]
 Description=Smart Security System - Integrated Controller
 After=multi-user.target network.target
 Wants=network.target
 
 [Service]
 Type=simple
 User=shinho
 Group=shinho
 WorkingDirectory=/home/shinho/shinho/livecam
 ExecStart=/usr/bin/python3 
/home/shinho/shinho/livecam/integrated_controller.py
 Restart=always
 RestartSec=10
 
 # 환경 변수 설정
 Environment=HOME=/home/shinho
 Environment=USER=shinho
 
 # 로그 설정
 StandardOutput=journal
 StandardError=journal
 SyslogIdentifier=smart-security
 
 [Install]
 WantedBy=multi-user.target


### 문서 참조 (2025.09 업데이트)
- **PRD.md**: 상세 기술 명세 (Picamera2 버전 2.0 반영)
- **CLAUDE.md**: 개발자 기술 문서 (Picamera2 마이그레이션 상세 정보)
- **로그 분석**: 콘솔 출력 + PiSP 하드웨어 로그 디버깅

### 일반적인 문제 (Picamera2 기반)
1. **스트리밍 끊김**: 네트워크 확인 / Picamera2 인스턴스 충돌
2. **모션 오감지**: 민감도 조정
3. **저장 실패**: 디스크 공간 확인
4. **카메라 오류**: 하드웨어 연결 / GPU 메모리 설정 (256MB) 점검
5. **"Pipeline handler in use" 에러**: 다른 카메라 어플리케이션 종료 필요

### 버전 정보
- **v1.0**: 초기 듀얼 카메라 CCTV + 모션 감지 시스템 (rpicam-vid 방식)
- ⚡ **v2.0**: Picamera2 기반 GPU 직접 액세스 마이그레이션 (2025-09-09)
- **마지막 업데이트**: 2025-09-09 (Picamera2 완전 대체)
- **호환성**: Raspberry Pi 5, Python 3.11+, Picamera2 0.3.12+