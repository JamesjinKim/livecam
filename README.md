# 듀얼 카메라 스마트 감시 시스템

> **라즈베리파이 5 기반 실시간 스트리밍 + 모션 감지 블랙박스 통합 시스템**

[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red)](https://www.raspberrypi.org/)
[![Camera](https://img.shields.io/badge/Camera-OV5647%20Dual-blue)](https://www.uctronics.com/)
[![Streaming](https://img.shields.io/badge/Streaming-MJPEG%2030fps-green)](https://en.wikipedia.org/wiki/Motion_JPEG)
[![Motion](https://img.shields.io/badge/Motion-OpenCV%20MOG2-orange)](https://opencv.org/)
[![Storage](https://img.shields.io/badge/Storage-H264%20MP4-blue)](https://en.wikipedia.org/wiki/H.264/MPEG-4_AVC)

## 시스템 개요

라즈베리파이 5 기반 듀얼 카메라 스마트 감시 시스템으로 **실시간 웹 스트리밍**과 **지능형 모션 감지 블랙박스** 기능을 모두 제공합니다.

### 주요 특징
- **실시간 카메라 토글** - 카메라 0번/1번 즉시 전환 스트리밍
- **지능형 모션 감지** - OpenCV MOG2 알고리즘 기반 실시간 모션 감지
- **자동 3분 녹화** - 모션 감지 시 H.264 하드웨어 인코딩으로 고품질 MP4 생성
- **듀얼 카메라 독립 동작** - 두 카메라 모두 독립적 모션 감지 및 녹화
- **통합 제어 인터페이스** - 웹 기반 통합 관제 시스템
- **24/7 무인 운영** - 안정적인 장기간 자동 운영

## 빠른 시작

### 1단계: 의존성 설치
```bash
# 시스템 패키지 설치
sudo apt update
sudo apt install -y rpicam-apps python3-venv python3-pip

# Python 가상환경 설정
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn psutil opencv-python numpy
```

### 2단계: 카메라 확인
```bash
# 연결된 카메라 목록 확인
rpicam-hello --list-cameras

# 카메라 0번 테스트
rpicam-hello --camera 0 --timeout 2000

# 카메라 1번 테스트
rpicam-hello --camera 1 --timeout 2000
```

### 3단계: 통합 시스템 실행
```bash
# 통합 제어 시스템 시작
./start_integrated_system.sh

# 또는 개별 시스템 실행
python main.py              # 토글 스트리밍만
python motion_blackbox.py   # 모션 감지 블랙박스만
```

### 4단계: 웹 접속
```
통합 시스템: http://라즈베리파이_IP:8080
토글 스트리밍: http://라즈베리파이_IP:8001
```

## 시스템 구성

### 1. 토글 스트리밍 시스템 (main.py)

#### 웹 인터페이스 기능
- **카메라 전환**: 카메라 0번/1번 버튼으로 즉시 전환
- **해상도 변경**: 480p(640×480), 720p(1280×720)
- **실시간 모니터링**: FPS, 프레임 수, 스트림 상태
- **반응형 UI**: 전체 화면 활용, 해상도별 최적화

#### 접속 방법
```
http://라즈베리파이_IP:8001
```

### 2. 모션 감지 블랙박스 (motion_blackbox.py)

#### 핵심 기능
- **실시간 모션 감지**: OpenCV MOG2 배경 차분 알고리즘
- **듀얼 카메라 독립 감지**: 두 카메라 동시 모니터링
- **자동 3분 녹화**: 모션 감지 시 H.264 MP4 자동 생성
- **카메라별 파일 구분**: motion_event_cam0_, motion_event_cam1_
- **24/7 무인 운영**: 자동 에러 복구 및 저장 관리

#### 모션 반응 프로세스
```
실시간 모션 감지 → 스트림 중단 → 3분 H.264 녹화 → 스트림 재시작
     ↓                ↓              ↓              ↓
카메라 0,1 MJPEG    rpicam 독점    MP4 파일 생성    모션 감지 복구
30fps 분석         접근 방식      17-18MB 크기     0.1초 반응속도
```

### 3. 통합 제어 시스템 (integrated_controller.py)

#### 통합 관제 기능
- **시스템 상태 모니터링**: 토글 스트리밍 + 모션 감지 상태
- **독립적 시스템 제어**: 각 시스템별 시작/중지
- **통합 웹 인터페이스**: 단일 포트로 모든 기능 접근

#### 접속 방법
```
http://라즈베리파이_IP:8080
```

## 성능 사양

### 시스템 리소스 사용량

| 구성 요소 | CPU 사용률 | 메모리 사용량 | 비고 |
|----------|-----------|-------------|------|
| **토글 스트리밍** | ~0.3% | ~50MB | 480p 30fps |
| **듀얼 모션 감지** | ~24% | ~350MB | 640x480 30fps |
| **H.264 녹화 (일시적)** | ~15% | ~50MB | 녹화 시에만 |
| **순환 버퍼 × 2** | ~1% | ~200MB | 1.5분 × 2대 |
| **총 시스템** | **~25%** | **~410MB** | **안정적 범위** |

### 모션 감지 성능 (실측)

```
전체 합계: 프레임 6,720개, 이벤트 14회
카메라 0: 프레임 3,401개, 이벤트 7회
카메라 1: 프레임 3,319개, 이벤트 7회
반응 속도: 0.1초 이내
녹화 파일: 17-18MB/3분
```

## 저장 및 파일 관리

### 녹화 파일 형식
- **파일 형식**: H.264 MP4, 640x480, 30fps
- **파일 크기**: 평균 17-18MB per 3분 영상
- **명명 규칙**: `motion_event_cam[0|1]_YYYYMMDD_HHMMSS.mp4`
- **저장 위치**: `videos/events/YYYY-MM/`

### 자동 저장 관리
- **보관 기간**: 7일 기본 정책
- **자동 정리**: 오래된 파일 자동 삭제
- **비상시 정리**: 디스크 사용량 90% 초과 시 3일만 보관

### 모션 감지 설정
- **감도 설정**: 5000px 임계값 (조정 가능)
- **배경 차분**: OpenCV MOG2 알고리즘
- **노이즈 제거**: 모폴로지 연산으로 오검출 방지

## 기술 구현 세부사항

### 1. rpicam-vid 기반 카메라 캡처
```python
class RPiCameraCapture:
    """rpicam-vid MJPEG 스트림 기반 캡처"""
    
    def start(self):
        cmd = [
            "rpicam-vid", "--camera", str(self.camera_id),
            "--width", "640", "--height", "480",
            "--framerate", "30", "--timeout", "0",
            "--nopreview", "--codec", "mjpeg",
            "--quality", "80", "--flush", "1", "--output", "-"
        ]
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
```

### 2. OpenCV MOG2 모션 감지
```python
class AdvancedMotionDetector:
    def detect_motion(self, frame):
        # 배경 차분 적용
        fg_mask = self.bg_subtractor.apply(gray_frame)
        
        # 노이즈 제거 및 윤곽 검출
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 5000px 이상 움직임 감지 시 트리거
        significant_contours = [c for c in contours if cv2.contourArea(c) > 5000]
        return len(significant_contours) > 0
```

### 3. H.264 하드웨어 인코딩 녹화
```python
def record_motion_event(self, pre_frames, pre_timestamps):
    cmd = [
        "rpicam-vid", "--camera", str(self.camera_id),
        "--timeout", "180000",  # 180초 = 3분
        "--codec", "h264",      # H.264 하드웨어 인코딩
        "--output", filepath    # 직접 MP4 저장
    ]
    result = subprocess.run(cmd, timeout=190)
```

## 프로젝트 구조

```
livecam/
├── README.md                    # 사용자 가이드
├── CLAUDE.md                   # 개발자 기술 문서
├── BLACKBOX.md                 # 블랙박스 시스템 상세 문서
├── main.py                     # 토글 스트리밍 서버
├── motion_blackbox.py          # 모션 감지 블랙박스
├── integrated_controller.py    # 통합 제어 시스템
├── start_integrated_system.sh  # 통합 시스템 시작 스크립트
├── venv/                       # Python 가상환경
├── scripts/                    # 유틸리티 스크립트
└── videos/                     # 영상 저장 디렉토리
    └── events/
        └── 2025-09/
            ├── motion_event_cam0_*.mp4
            └── motion_event_cam1_*.mp4
```

## 문제 해결

### 카메라 접근 오류
```bash
# 실행 중인 카메라 프로세스 확인
sudo lsof /dev/video*

# rpicam-vid 프로세스 종료
pkill -f rpicam-vid

# 시스템 재시작
sudo reboot
```

### 모션 감지 안됨
```python
# motion_blackbox.py에서 감도 설정 조정
SENSITIVITY = 'high'  # 더 민감하게 설정

# 디버그 모드 활성화
debug_frame = motion_detector.get_debug_frame(frame)
cv2.imshow("Motion Debug", debug_frame)
```

### 저장 공간 부족
```bash
# 수동 정리
rm -f videos/events/2024-*/*.mp4

# 디스크 사용량 확인
df -h
du -sh videos/events/
```

### 포트 충돌 문제
```bash
# 포트 사용 프로세스 확인
sudo lsof -i :8001  # 토글 스트리밍
sudo lsof -i :8080  # 통합 제어

# 프로세스 종료
sudo kill [PID]
```

## 운영 가이드

### 일일 점검
1. 모션 이벤트 발생 여부 확인
2. 저장 공간 사용량 점검  
3. 시스템 부하 모니터링

### 주간 유지보수
1. 시스템 재시작 (메모리 정리)
2. 중요 이벤트 백업
3. 수동 파일 정리

### 성능 모니터링
```bash
# CPU 사용률 확인
top -p $(pgrep -f motion_blackbox.py)

# 메모리 사용량 확인  
ps -o pid,ppid,cmd,%mem,%cpu -p $(pgrep -f motion_blackbox.py)

# 디스크 I/O 확인
iotop -p $(pgrep -f motion_blackbox.py)
```

### 시스템 특징

**완성된 기능들**:
1. 실시간 모션 감지: OpenCV MOG2로 0.1초 이내 반응
2. 자동 3분 녹화: H.264 하드웨어 인코딩으로 고품질 MP4 생성
3. 듀얼 카메라 독립 동작: 동시 감지, 순차적 녹화로 충돌 방지
4. 카메라별 파일 구분: motion_event_cam0_, motion_event_cam1_ 명명
5. 자동 저장 관리: 7일 보관 정책으로 순환 운영
6. 리소스 최적화: CPU 25% 미만, 메모리 410MB로 24/7 운영

## 주의사항

### 시스템 제약
- **카메라 리소스 공유**: 모션 감지와 녹화는 카메라 리소스를 교대로 사용
- **리소스 관리**: 녹화 시 2초 대기 시간으로 안전한 카메라 전환
- **포트 사용**: 8001(토글), 8080(통합) - 충돌 시 변경 가능

### 성능 최적화 권장사항
- **저장장치**: Class 10 이상 고속 SD 카드 또는 SSD 권장
- **전원 공급**: 5V/3A 안정적 전원 (특히 두 카메라 동시 사용 시)
- **방열**: 장시간 24/7 운영 시 적절한 방열 소설 필수
- **네트워크**: 유선 연결 권장 (Wi-Fi 지원하지만 대역폭 제약)

### 운영 안정성
- **24/7 무인 운영 최적화**: 자동 에러 복구, 메모리 누수 방지
- **디스크 관리**: 자동 정리로 무한 운영 가능
- **프로세스 격리**: 녹화 실패가 전체 시스템에 영향 없음

## 지원 및 문의

- **기술 문의**: 이 문서 참조
- **버그 리포트**: GitHub Issues 활용
- **긴급 지원**: 시스템 관리자 연락

---

## 사용법 요약

### 1. 통합 시스템 실행
```bash
./start_integrated_system.sh
```

### 2. 웹 접속
```
통합 제어: http://라즈베리파이_IP:8080
토글 스트리밍: http://라즈베리파이_IP:8001
```

### 3. 기능 사용
- **토글 스트리밍**: 카메라 0/1 전환, 해상도 조정
- **모션 감지**: 자동 모션 감지 및 3분 녹화
- **통합 모니터링**: 실시간 시스템 상태 확인

### 4. 사용 시나리오
- **보안 모니터링**: 실시간 리모트 감시 + 자동 이벤트 녹화
- **스마트 블랙박스**: 모션 반응형 자동 녹화 시스템
- **원격 운영**: 24/7 무인 운영 가능한 안정적 시스템

핵심 장점: 실시간 스트리밍과 지능형 모션 감지를 모두 제공하는 완전한 듀얼 카메라 스마트 감시 시스템입니다!