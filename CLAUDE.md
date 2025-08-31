# CLAUDE.md - 개발자 기술 문서

## 🎯 프로젝트 개요

라즈베리파이 5 기반 듀얼 카메라 블랙박스 시스템
- **목적**: 실시간 영상 녹화 및 웹 스트리밍 시스템
- **핵심**: rpicam-vid 기반 MP4 직접 저장 및 MJPEG 스트리밍
- **특징**: 듀얼 카메라 지원, H.264 하드웨어 인코딩, 실시간 웹 스트리밍

## 🏗️ 시스템 아키텍처

### 기술 스택
- **하드웨어**: Raspberry Pi 5 (BCM2712), OV5647 카메라 모듈 × 2
- **영상 캡처**: rpicam-vid (라즈베리파이 공식 도구)
- **영상 포맷**: MP4 (H.264 하드웨어 인코딩)
- **저장 방식**: 직접 MP4 저장, 실시간 파일 쓰기 with flush

### 주요 구성 요소

```
livecam/
├── start_blackbox.sh       # 메인 실행 스크립트
├── src/                    # C++ 소스 코드 (레거시)
│   ├── core/              # 핵심 캡처 시스템
│   ├── optimized/         # 최적화 구현
│   └── legacy/            # DMA 직접 접근 시도
├── scripts/               # 유틸리티 스크립트
└── videos/                # 영상 저장 디렉토리
    ├── 640x480/          # 640x480 해상도
    │   ├── cam0/         # 카메라 0번
    │   └── cam1/         # 카메라 1번
    ├── 1280x720/         # 720p 해상도
    │   ├── cam0/         # 카메라 0번
    │   └── cam1/         # 카메라 1번
    └── 1920x1080/        # 1080p 해상도
        ├── cam0/         # 카메라 0번
        └── cam1/         # 카메라 1번
```

## 💻 개발 환경 설정

### 필수 패키지 설치
```bash
sudo apt update
sudo apt install -y rpicam-apps ffmpeg
```

### 카메라 확인
```bash
# 연결된 카메라 목록
rpicam-hello --list-cameras

# 카메라 0번 테스트
rpicam-hello --camera 0 --timeout 2000

# 카메라 1번 테스트  
rpicam-hello --camera 1 --timeout 2000
```

## 🔧 핵심 기술 구현

### 1. rpicam-vid 기반 MP4 직접 저장
```bash
rpicam-vid --camera 0 \
  --width 640 --height 480 \
  --output blackbox_cam0.mp4 \
  --timeout 0 \
  --nopreview \
  --framerate 30 \
  --flush
```

**주요 파라미터 설명**:
- MP4 직접 출력 (H.264 하드웨어 인코딩)
- `--timeout 0`: 무한 녹화 (SIGINT로 정상 종료)
- `--nopreview`: 미리보기 비활성화로 리소스 절약
- `--flush`: 실시간 파일 쓰기 보장

### 2. 듀얼 카메라 동시 처리
```bash
# start_blackbox.sh 내부 구현
rpicam-vid --camera 0 ... &  # 백그라운드 실행
CAM0_PID=$!

rpicam-vid --camera 1 ... &  # 백그라운드 실행
CAM1_PID=$!

# 종료 신호 처리 (MP4 정상 마무리)
trap 'kill -INT $CAM0_PID $CAM1_PID; sleep 3; wait' INT
```

### 3. 성능 최적화 전략

#### MP4 직접 저장 방식
- **H.264 하드웨어 인코딩**: 라즈베리파이 5 지원
- **CPU 부하**: H.264 하드웨어 (10-20%) vs 소프트웨어 (100%)
- **저장 효율**: 직접 MP4 저장으로 즉시 재생 가능

#### 메모리 및 I/O 최적화
- DMA 채널 활용 (18개 채널 중 자동 할당)
- 17GB/s 메모리 대역폭 활용
- 실시간 flush로 데이터 무결성 보장

## 📊 성능 지표

### CPU 사용률 (MP4 직접 저장)
| 모드 | 해상도 | CPU 사용률 |
|------|--------|-----------|
| 단일 카메라 | 640×480 | ~10% |
| 단일 카메라 | 1280×720 | ~15% |
| 단일 카메라 | 1920×1080 | ~20% |
| 듀얼 카메라 | 640×480 | ~20% |
| 듀얼 카메라 | 1280×720 | ~30% |
| 듀얼 카메라 | 1920×1080 | ~40% |

### 저장 용량 (MP4 형식)
- 640×480: 약 1.5MB/10초 (9MB/분)
- 1280×720: 약 12MB/10초 (72MB/분)
- 1920×1080: 약 25MB/10초 (150MB/분)

## 🛠️ 개발 및 디버깅

### 실시간 모니터링
```bash
# CPU 사용률 모니터링
top -d 1

# 프로세스 확인
ps aux | grep rpicam

# 디스크 사용량
df -h

# 실시간 로그
journalctl -f
```

### 문제 해결

#### 카메라 인식 오류
```bash
# 카메라 모듈 재연결 후
sudo modprobe -r bcm2835-v4l2
sudo modprobe bcm2835-v4l2
```

#### 권한 문제
```bash
sudo usermod -a -G video $USER
# 로그아웃 후 재로그인 필요
```

## 🔄 지속 통합/배포

### 자동 시작 설정 (systemd)
```ini
[Unit]
Description=Industrial CCTV Blackbox System
After=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/livecam
ExecStart=/home/pi/livecam/start_blackbox.sh dual-640
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 로그 로테이션
```bash
# /etc/logrotate.d/blackbox
/home/pi/livecam/videos/**/*.mp4 {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

## 📝 코드 컨벤션

### 파일 명명 규칙
- MP4 파일: `blackbox_cam[N]_[resolution]_YYYYMMDD_HHMMSS.mp4`
- 예시: `blackbox_cam0_640_20241231_143025.mp4`

### 스크립트 작성 가이드
- 명확한 오류 메시지
- 사용자 친화적 출력 (이모지 사용)
- 종료 시 정리 작업 (trap 사용)

## 🚀 향후 개발 계획

### 단기 (1-2주)
- [x] MP4 직접 저장 시스템 구현
- [ ] 웹 인터페이스 (실시간 모니터링)
- [ ] 순환 녹화 (디스크 공간 관리)

### 중기 (1-2개월)
- [ ] AI 기반 이벤트 감지
- [ ] 클라우드 백업 시스템
- [ ] 원격 제어 API

### 장기 (3-6개월)
- [ ] 다중 라즈베리파이 연동
- [ ] 중앙 관제 시스템
- [ ] 빅데이터 분석 플랫폼

## ⚠️ 주의사항

### 하드웨어 제약
- 라즈베리파이 5는 H.264 하드웨어 인코딩 지원
- VideoCore VII GPU를 통한 효율적 인코딩
- 듀얼 1080p 동시 녹화 시 CPU ~40% 사용

### 안정성 고려사항
- 24/7 운영 시 방열 필수
- SD 카드 수명 관리 (산업용 SD 권장)
- 정기적인 시스템 재시작 권장 (주 1회)

## 📚 참고 자료

- [Raspberry Pi Camera Documentation](https://www.raspberrypi.com/documentation/computers/camera_software.html)
- [rpicam-apps GitHub](https://github.com/raspberrypi/rpicam-apps)
- [V4L2 API Documentation](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/v4l2.html)

## 🤝 기여 가이드

### 코드 기여
1. 기능 브랜치 생성: `feature/기능명`
2. 커밋 메시지: `[타입] 설명` (feat, fix, docs, refactor)
3. PR 생성 시 상세 설명 필수

### 문서 기여
- 기술 문서는 CLAUDE.md에 추가
- 사용자 가이드는 README.md에 추가
- 예제 코드와 실행 결과 포함
- 아래 4개의 문서 외에 새로운 문서 작성 금지!
├── README.md             # 사용자 가이드 (현재 문서)
├── CLAUDE.md             # 개발자 기술 문서
├── PRD.md                # 제품 요구사항 문서
├── QUICK_START.md        # 빠른 시작 가이드

## 📞 문의 및 지원

- 기술 문의: 이 문서 참조
- 버그 리포트: GitHub Issues 활용
- 긴급 지원: 시스템 관리자 연락