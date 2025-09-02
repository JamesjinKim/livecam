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
- **영상 포맷**: MP4 (H.264 하드웨어 인코딩), MJPEG (실시간 스트리밍)
- **저장 방식**: 직접 MP4 저장, 실시간 파일 쓰기 with flush
- **웹 스트리밍**: FastAPI 기반 MJPEG 스트리밍 서버 (30fps 최적화)

### 주요 구성 요소

```
livecam/
├── start_blackbox.sh       # MP4 녹화 실행 스크립트
├── start_streaming.sh      # 웹 스트리밍 실행 스크립트 (30fps)
├── src/                    # 소스 코드
│   ├── core/              # 핵심 캡처 시스템 (레거시)
│   ├── optimized/         # 최적화 구현 (레거시)
│   ├── legacy/            # DMA 직접 접근 시도 (레거시)
│   └── streaming/         # 웹 스트리밍 서버
│       ├── stream_optimized.py         # 15fps 안정화 버전
│       ├── stream_optimized_30fps.py   # 30fps 고성능 버전
│       ├── stream_fixed.py             # 메모리 버퍼 수정 버전
│       ├── stream_dma.py               # DMA 시뮬레이션 (분석됨)
│       └── stream_zerocopy.py          # Zero-copy 시뮬레이션 (분석됨)
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
sudo apt install -y rpicam-apps ffmpeg python3-venv
```

### 웹 스트리밍 환경 설정
```bash
# 가상환경 생성 및 패키지 설치
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn psutil
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

### 3. 웹 스트리밍 서버 구현

#### 30fps 고성능 스트리밍 서버 (`stream_optimized_30fps.py`)
```python
# 30fps 최적화 설정
rpicam-vid --camera 0 --width 640 --height 480 \
  --timeout 0 --nopreview --codec mjpeg \
  --quality 80 --framerate 30 --bitrate 0 \
  --denoise cdn_fast --flush 1 --output -
```

**핵심 최적화 기술**:
- **768KB 고정 버퍼**: 메모리 누수 방지 및 30fps 처리량 보장
- **3단계 버퍼 풀**: 순환 버퍼 관리로 지연 최소화
- **적응형 청크 읽기**: 32KB 청크로 프레임 드롭 방지
- **인라인 JPEG 검색**: memoryview 직접 사용으로 복사 오버헤드 제거
- **하드웨어 디노이징**: `cdn_fast`로 품질 향상

#### 웹 UI 특징
- **전체 화면 활용**: 브라우저 창 전체를 활용한 최대 영상 크기
- **심플한 그레이 디자인**: 밝은 회색 톤의 모던 UI
- **부드러운 블루 액센트**: 파란색 배지와 인디케이터
- **반응형 레이아웃**: 2분할 그리드로 듀얼 카메라 동시 표시

### 4. 성능 최적화 전략

#### MP4 직접 저장 방식
- **H.264 하드웨어 인코딩**: 라즈베리파이 5 지원
- **CPU 부하**: H.264 하드웨어 (10-20%) vs 소프트웨어 (100%)
- **저장 효율**: 직접 MP4 저장으로 즉시 재생 가능

#### 메모리 및 I/O 최적화
- DMA 채널 활용 (18개 채널 중 자동 할당)
- 17GB/s 메모리 대역폭 활용
- 실시간 flush로 데이터 무결성 보장

## 📊 성능 지표

### CPU 사용률 비교

#### MP4 직접 저장
| 모드 | 해상도 | CPU 사용률 |
|------|--------|-----------|
| 단일 카메라 | 640×480 | ~10% |
| 단일 카메라 | 1280×720 | ~15% |
| 단일 카메라 | 1920×1080 | ~20% |
| 듀얼 카메라 | 640×480 | ~20% |
| 듀얼 카메라 | 1280×720 | ~30% |
| 듀얼 카메라 | 1920×1080 | ~40% |

#### 웹 스트리밍 서버
| 버전 | FPS | 메모리 사용량 | CPU 사용률 |
|------|-----|-------------|-----------|
| stream_optimized.py | 15fps | ~50MB | ~0.3% |
| stream_optimized_30fps.py | 30fps | ~52MB | ~0.3% |

### 저장 용량 (MP4 형식)
- 640×480: 약 1.5MB/10초 (9MB/분)
- 1280×720: 약 12MB/10초 (72MB/분)
- 1920×1080: 약 25MB/10초 (150MB/분)

## 🚀 실행 방법

### MP4 녹화 실행
```bash
# 듀얼 카메라 640x480 해상도로 녹화
./start_blackbox.sh dual-640
```

### 웹 스트리밍 실행
```bash
# 30fps 고성능 스트리밍 서버
./start_streaming.sh

# 접속 URL: http://라즈베리파이_IP:8000
```

## 🔬 스트리밍 기술 분석

### DMA 및 Zero-copy 구현 분석

#### `stream_dma.py` - "가짜 DMA" 분석 결과
- **실제**: 일반적인 파일 I/O를 사용하는 표준 구현
- **문제점**: DMA 레지스터 직접 접근 없이 `/dev/shm` 공유 메모리만 사용
- **성능**: 일반적인 파일 읽기와 동일한 성능

#### `stream_zerocopy.py` - "가짜 Zero-copy" 분석 결과
- **실제**: named pipes + mmap 사용하지만 `bytes()` 복사 발생
- **문제점**: `chunk = bytes(view[...])` 코드로 메모리 복사 수행
- **성능**: Zero-copy 목적과 반대되는 다중 메모리 복사 발생

### 메모리 최적화 기법

#### 검증된 최적화 방식 (`stream_optimized_30fps.py`)
- **고정 크기 순환 버퍼**: 768KB 고정 할당으로 동적 할당 제거
- **직접 바이트 검색**: memoryview로 JPEG 헤더 검색
- **가비지 컬렉션 제어**: 1500프레임마다 자동 실행
- **프레임 드롭 방지**: 적응형 32KB 청크 읽기

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
- [x] 웹 스트리밍 인터페이스 (30fps 최적화)
- [x] 메모리 누수 방지 및 안정성 최적화
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