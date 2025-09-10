# CLAUDE.md - 개발자 기술 문서

## 🎯 프로젝트 개요

라즈베리파이 5 기반 통합 CCTV 및 모션 감지 블랙박스 시스템
- **목적**: 실시간 CCTV 스트리밍 + 지능형 모션 감지 블랙박스
- **핵심**: FastAPI 웹 서버 + OpenCV 모션 감지 + Picamera2 GPU 가속 인코딩 ⚡
- **특징**: 다중 클라이언트 CCTV (최대 2명), 프리버퍼 블랙박스, 날짜별 자동 분류
- **2025년 9월**: **rpicam-vid → Picamera2 마이그레이션 완료** (안정성 대폭 향상)

## 🏗️ 시스템 아키텍처

### 기술 스택
- **하드웨어**: Raspberry Pi 5 (BCM2712), OV5647 카메라 모듈 × 2
- **CCTV**: FastAPI + MJPEG 스트리밍 (최대 2명 동시 접속)
- **모션 감지**: OpenCV BackgroundSubtractorMOG2
- **영상 처리**: ⚡ **Picamera2 라이브러리 + VideoCore VII GPU 직접 액세스** (2025.09 업그레이드)
- **프론트엔드**: Vanilla JavaScript, 반응형 웹 UI + 실시간 하트비트 모니터링

### 시스템 구성

```
livecam/
├── picam2_main.py             # 🔴 메인 CCTV 서버 (Picamera2 기반) ⚡ 현재 운영중
├── cctv_main.py               # 🔴 구버전 
감지 블랙박스  
├── detection_cam0.py           # ⚫ 카메라 0 모션 ├── detection_cam1.py           # ⚫ 카메라 1 모션 감지 블랙박스
├── picam2_simple.py            # 🧪 Picamera2 테스트 도구
├── PRD.md                      # 📋 제품 요구사항 문서
├── README.md                   # 📖 사용자 가이드
├── CLAUDE.md                   # 🔧 개발자 기술 문서 (현재 파일)
└── videos/                     # 영상 저장소
    └── motion_events/          # 모션 감지 이벤트 저장
        ├── cam0/
        │   ├── 250908/         # YYMMDD 날짜별 폴더
        │   └── 250909/
        └── cam1/
            ├── 250908/
            └── 250909/
```

---
## Python code 내에서 이모지 사용 금지!

## 🔴 Part 1: CCTV 실시간 스트리밍 시스템 (picam2_main.py)

### 🚀 2025년 9월 Picamera2 마이그레이션 완료

**마이그레이션 배경**:
- rpicam-vid 서브프로세스 방식의 장기 스트리밍 중 멈춤 현상 해결
- "Pipeline handler in use by another process" 에러 근본 해결
- Pi5 VideoCore VII GPU 직접 액세스로 성능 향상

**주요 개선사항**:
- ✅ 서브프로세스 → 직접 라이브러리 호출로 안정성 대폭 향상
- ✅ 기존 cctv_main.py UI/UX 100% 보존
- ✅ 하트비트 모니터링 시스템 완전 통합
- ✅ Pi5 PiSP BCM2712_D0 하드웨어 가속 활용

### 📅 2025년 9월 10일 추가 개선사항

**다중 클라이언트 지원 (2025.09.10)**:
- ✅ 해상도별 최대 2명 동시 접속 지원
- ✅ 웹 UI에 실시간 접속자 수 표시 (예: "1/2")
- ✅ 접속 제한 초과 시 HTTP 423 상태 코드 반환

**종료 처리 개선 (2025.09.10)**:
- ✅ Graceful shutdown 구현
- ✅ 시그널 핸들러 단순화 (sys.exit 사용)
- ✅ uvicorn 종료 시 asyncio.CancelledError 정상 처리

**하트비트 안정화 (2025.09.10)**:
- ✅ HEAD 요청 제거, stats API 기반 상태 감지
- ✅ CSS 레이아웃 개선 (절대 위치 사용)
- ✅ LIVE/DELAY 깜빡임 현상 해결

### 핵심 기술 구현

#### 1. 다중 클라이언트 제한 시스템 (2025.09.10 업데이트)
```python
# 해상도별 클라이언트 제한 설정
active_clients = set()  # IP 기반 클라이언트 추적

RESOLUTIONS = {
    "640x480": {"width": 640, "height": 480, "name": "480p", "max_clients": 2},
    "1280x720": {"width": 1280, "height": 720, "name": "720p", "max_clients": 2}
}

def get_max_clients():
    return RESOLUTIONS.get(current_resolution, {}).get("max_clients", 1)

@app.get("/stream")
async def video_stream(request: Request):
    client_ip = request.client.host
    max_clients = get_max_clients()
    
    # 해상도별 클라이언트 제한 확인
    if len(active_clients) >= max_clients and client_ip not in active_clients:
        raise HTTPException(status_code=423, 
            detail=f"Maximum {max_clients} client(s) allowed for {current_resolution}")
```

**장점**:
- 안정적인 30fps 스트리밍 보장 (최대 2명)
- 리소스 경합 방지
- 네트워크 대역폭 최적화
- 실시간 접속자 수 모니터링

#### 2. Picamera2 기반 MJPEG 스트리밍 ⚡
```python
def generate_mjpeg_stream(camera_id: int, client_ip: str = None):
    # Picamera2 직접 캡처 (서브프로세스 제거)
    stream = io.BytesIO()
    picam2.capture_file(stream, format='jpeg')  # GPU 가속 JPEG 인코딩
    frame_data = stream.getvalue()
    stream.close()
    
    # MJPEG 멀티파트 스트림 출력
    yield b'--frame\r\n'
    yield b'Content-Type: image/jpeg\r\n'
    yield f'Content-Length: {len(frame_data)}\r\n\r\n'.encode()
    yield frame_data
    yield b'\r\n'
```

**최적화 기법**:
- 해상도별 차별화된 버퍼 크기
- 동적 메모리 관리 (순환 버퍼)
- 프레임 크기 검증 및 필터링

#### 3. Picamera2 카메라 관리 시스템 ⚡
```python
def start_camera_stream(camera_id: int, resolution: str = None):
    # Picamera2 인스턴스 직접 생성 (서브프로세스 제거)
    picam2 = Picamera2(camera_num=camera_id)
    
    # GPU 최적화 설정
    config = picam2.create_video_configuration(
        main={"size": (width, height), "format": "YUV420"},
        buffer_count=4, queue=False  # 버퍼 최적화
    )
    
    picam2.configure(config)
    picam2.start()  # 즉시 GPU 가속 시작
    
    camera_instances[camera_id] = picam2
```

**Picamera2 인스턴스 관리** ⚡:
- 서브프로세스 완전 제거로 좀비 프로세스 원천 차단
- GPU 메모리 직접 관리로 안정성 향상
- Pi5 PiSP (Image Signal Processor) BCM2712_D0 하드웨어 가속

#### 4. 실시간 통계 시스템
```python
# 매초 업데이트되는 스트리밍 통계
stream_stats = {
    0: {"frame_count": 0, "avg_frame_size": 0, "fps": 0, "last_update": 0},
    1: {"frame_count": 0, "avg_frame_size": 0, "fps": 0, "last_update": 0}
}

@app.get("/api/stats")
async def get_stats():
    return {
        "camera": current_camera,
        "resolution": current_resolution,
        "stats": stream_stats[current_camera]
    }
```

### 웹 인터페이스 기술

#### 하트비트 모니터링 시스템 ❤️
```javascript
// 2초마다 스트림 활성 상태 체크
function checkStreamActivity() {
    fetch('/stream', { method: 'HEAD' })
        .then(response => {
            const indicator = document.getElementById('heartbeat-indicator');
            const text = document.getElementById('heartbeat-text');
            
            if (response.status === 200) {
                indicator.className = 'heartbeat-indicator green';
                text.textContent = 'LIVE';
            } else if (response.status === 503) {
                indicator.className = 'heartbeat-indicator red';
                text.textContent = 'OFFLINE';
            }
        });
}
setInterval(checkStreamActivity, 2000);  // Picamera2 실시간 모니터링
```

**UI 특징** (2025.09 업그레이드):
- 전체 화면 활용 영상 표시
- ❤️ **실시간 하트비트 인디케이터**: LIVE/DELAY/ERROR/OFFLINE 상태 표시
- 실시간 통계 업데이트 (FPS, 프레임 수, 데이터 크기)
- 연결 제한 상태 자동 감지 및 표시
- 일관된 버튼 디자인 (종료/해상도 버튼 통일)

#### CSS 디자인 시스템
- **색상 팔레트**: 그레이 톤 + 파란색 액센트
- **레이아웃**: Flexbox 기반 반응형
- **인터랙션**: 호버 효과 + 활성 상태 표시

### 성능 최적화 전략

#### 메모리 관리 (Picamera2 최적화) ⚡
- **GPU 직접 액세스**: 서브프로세스 메모리 오버헤드 제거
- **Zero-copy 스트림**: Picamera2 → BytesIO 직접 전송
- **자동 버퍼 관리**: Pi5 하드웨어 버퍼링 활용
- **메모리 누수 방지**: 인스턴스 기반 리소스 관리

#### 네트워크 최적화
- **HTTP Keep-Alive**: 연결 재사용
- **MJPEG 품질**: 80% 압축 품질
- **프레임 드롭 방지**: 버퍼 임계값 관리

---

## ⚫ Part 2: 모션 감지 블랙박스 시스템

### 아키텍처 패턴

#### 1. 단일 책임 원칙 적용
```python
# 각 기능별 독립 클래스 설계
├── MotionDetectionSystem      # 메인 조정자
├── CameraStreamManager        # 카메라 스트림 전담
├── SimpleMotionDetector       # 모션 감지 알고리즘  
├── VideoRecorder             # 프리버퍼 + 녹화 시스템
├── EventManager              # 이벤트 로깅
└── Config                    # 설정 관리
```

#### 2. 프리버퍼 시스템 설계
```python
class VideoRecorder:
    def __init__(self, pre_buffer=5, post_buffer=25):
        # skip_frames를 고려한 실제 fps 계산
        self.actual_buffer_fps = FRAMERATE // SKIP_FRAME  # 30 / 3 = 10fps
        self.frame_buffer = deque(maxlen=pre_buffer * self.actual_buffer_fps)  # 50 프레임
        
    def add_frame_to_buffer(self, frame):
        # JPEG 압축으로 메모리 효율성 확보
        _, jpeg_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        self.frame_buffer.append(jpeg_data)
```

**핵심 설계 원리**:
- 메모리 효율: JPEG 압축 저장
- 정확한 시간: 프레임 복제로 30fps 보장
- 순환 버퍼: 고정 메모리 사용량

#### 3. 모션 감지 알고리즘
```python
class SimpleMotionDetector:
    def __init__(self, threshold=10000, cooldown=12):
        self.background_subtractor = cv2.BackgroundSubtractorMOG2()
        self.background_frames = deque(maxlen=60)  # 60프레임 배경 학습
        
    def detect(self, frame):
        # 그레이스케일 + 가우시안 블러
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (11, 11), 0)
        
        # 배경 차분 및 임계값 적용
        frame_delta = cv2.absdiff(self.background_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        
        # 변화된 픽셀 수 계산
        changed_pixels = cv2.countNonZero(thresh)
        return changed_pixels > self.threshold
```

**알고리즘 최적화**:
- 배경 안정화: 60프레임 학습으로 false positive 감소
- 적응형 업데이트: 느린 배경 변화 대응
- 형태학적 연산: 노이즈 제거

#### 4. 영상 병합 시스템
```python
def _merge_video_files(self, input_files, output_file):
    merge_cmd = [
        "ffmpeg",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:v", "libx264",      # H.264 코덱
        "-preset", "fast",      # 인코딩 속도 향상
        "-t", "30",            # 정확히 30초
        "-r", "30",            # 30fps 통일
        "-pix_fmt", "yuv420p", # 호환성 향상
        "-y", str(output_file)
    ]
```

**품질 보장 메커니즘**:
- Duration 검증: ffprobe로 실제 길이 확인
- 프레임레이트 통일: 모든 구간 30fps
- 에러 복구: 60초 타임아웃 + 재시도

### 고급 기능 구현

#### 1. 날짜별 자동 분류
```python
def start_recording(self, camera_id):
    # YYMMDD 형식 날짜 폴더 생성
    now = datetime.now()
    date_folder = now.strftime("%y%m%d")  # 250908
    daily_dir = self.output_dir / date_folder
    daily_dir.mkdir(parents=True, exist_ok=True)
```

#### 2. 스레드 안전성
```python
class VideoRecorder:
    def __init__(self):
        self.buffer_lock = threading.Lock()
        self.merge_thread = None
        self.merge_thread_stop = threading.Event()
        
    def stop_recording(self):
        # 병합 스레드 안전한 종료
        if self.merge_thread and self.merge_thread.is_alive():
            self.merge_thread_stop.set()
            self.merge_thread.join(timeout=3)
```

#### 3. 리소스 정리 시스템
```python
def cleanup_temp_files(self):
    # 모든 임시 파일 체계적 정리
    for date_folder in self.output_dir.glob("[0-9][0-9][0-9][0-9][0-9][0-9]"):
        for temp_file in date_folder.glob("temp_*.h264"):
            temp_file.unlink()
        for list_file in date_folder.glob("concat_*.txt"):
            list_file.unlink()
```

---

## 🔧 개발 도구 및 디버깅

### 로깅 시스템

#### CCTV 시스템 로그
```python
# 클라이언트 연결/해제
👥 Client connected: 192.168.0.21 (Total: 1)
🚫 Stream request rejected: 192.168.0.20 (Max clients: 1)

# 성능 통계
📊 Camera 0 (640x480): 150 frames, 31.0 fps, avg 31KB
🔄 Switching from camera 0 to camera 1
```

#### 모션 감지 시스템 로그
```python
# 모션 감지 과정
Background stabilized with 60 frames - motion detection active
Motion detected: 21701 changed pixels

# 녹화 과정
🎬 Motion Event Recording Started
Pre-buffer saved: buffer_20250908_143025.mp4
  - Frames: 50 frames @ 10fps capture
  - Duration: 5.0s (expected: 5.0s)

# 병합 완료
✅ Video merged successfully: 250908/motion_event_cam0_20250908_143025.mp4
  - Final duration: 30.0s (expected: 30s, diff: 0.0s)
  ✓ Pre-buffer successfully included in final video
```

### 성능 모니터링

#### 리소스 사용량
```bash
# 실시간 모니터링 명령어 (Picamera2)
top -d 1                           # CPU 사용률
ps aux | grep picam2_main_fixed    # Picamera2 프로세스 상태
ps aux | grep rpicam               # 레거시 rpicam 프로세스 (없어야 정상)
df -h                              # 디스크 사용량
du -h videos/motion_events/        # 저장 용량
```

#### 성능 벤치마크 (2025.09 Picamera2 기준) ⚡
| 시스템 | CPU 사용률 | 메모리 | 디스크 I/O | 비고 |
|--------|------------|--------|------------|------|
| **Picamera2 CCTV (480p)** | ~**7%** | **40MB** | 1-2MB/s | 🚀 30% CPU 절약 |
| **Picamera2 CCTV (720p)** | ~**11%** | **50MB** | 3-4MB/s | 🚀 27% CPU 절약 |
| 모션감지 (단일) | ~20% | 60MB | 6MB/30s | 변화없음 |
| **통합 실행 (Picamera2)** | ~**32%** | **100MB** | 8-10MB/s | 🚀 20% 리소스 절약 |

### 문제 해결 가이드

#### 1. Picamera2 CCTV 스트리밍 문제 ⚡
```bash
# 카메라 하드웨어 확인
rpicam-hello --list-cameras
rpicam-hello --camera 0 --timeout 2000

# Picamera2 라이브러리 확인
python3 -c "from picamera2 import Picamera2; print('Picamera2 OK')"

# 권한 문제 해결
sudo usermod -a -G video $USER

# GPU 메모리 확인
vcgencmd get_mem gpu
```

#### 2. 모션 감지 정확도 문제
```python
# 민감도 조정 (detection_cam0.py)
CURRENT_SENSITIVITY = 'medium'  # low → medium으로 증가

# 쿨다운 시간 조정
SENSITIVITY_LEVELS['low']['cooldown'] = 8  # 12초 → 8초
```

#### 3. 영상 병합 오류
```bash
# ffmpeg 설치 확인
which ffmpeg
ffmpeg -version

# 디스크 공간 확인
df -h /home/pi
```

#### 4. 메모리 부족 문제
```python
# 프리버퍼 크기 감소
PRE_BUFFER_DURATION = 3  # 5초 → 3초

# 해상도 낮춤
RECORDING_WIDTH = 960   # 1280 → 960
RECORDING_HEIGHT = 540  # 720 → 540
```

---

## 🚀 배포 및 운영

### 자동 시작 설정 (systemd)
```ini
# /etc/systemd/system/cctv-stream.service
[Unit]
Description=CCTV Streaming System
After=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/livecam
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/motion-cam0.service
[Unit]
Description=Motion Detection Camera 0
After=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/livecam
ExecStart=/usr/bin/python3 detection_cam0.py
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
```

### 로그 로테이션
```bash
# /etc/logrotate.d/motion-events
/home/pi/livecam/videos/motion_events/**/*.mp4 {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
```

### 백업 스크립트
```bash
#!/bin/bash
# backup_videos.sh

SOURCE="/home/pi/livecam/videos/motion_events/"
DEST="/mnt/external/backup/"
DATE=$(date +%Y%m%d)

# 7일 이상된 파일만 백업 후 삭제
find $SOURCE -name "*.mp4" -mtime +7 -exec cp {} $DEST \;
find $SOURCE -name "*.mp4" -mtime +7 -delete

echo "Backup completed: $DATE"
```

---

## 🔮 향후 개발 계획

### 단기 개선사항 (1-2주)
- [ ] 통합 웹 대시보드 (CCTV + 모션감지 상태)
- [ ] 모바일 반응형 UI 개선
- [ ] 알림 시스템 (이메일, 웹훅)
- [ ] 영상 썸네일 생성

### 중기 개발 (1-2개월)
- [ ] AI 기반 객체 감지 (사람/동물 구분)
- [ ] 클라우드 백업 연동
- [ ] 다중 클라이언트 지원 (읽기 전용)
- [ ] REST API 확장

### 장기 비전 (3-6개월)
- [ ] 다중 라즈베리파이 클러스터
- [ ] 중앙 관제 시스템
- [ ] 머신러닝 기반 이상 행동 감지
- [ ] 음성/소음 감지 추가

---

## 📚 참고 자료 및 의존성

### 외부 라이브러리 (2025.09 업데이트)
```python
# requirements.txt
fastapi>=0.104.0
uvicorn>=0.24.0
picamera2>=0.3.12          # ⚡ 새로 추가 (핵심 라이브러리)
opencv-python>=4.8.0
numpy>=1.24.0
pillow>=10.0.0
psutil>=5.9.0
```

### 시스템 패키지 (2025.09 업데이트)
```bash
# 기본 패키지
sudo apt install -y rpicam-apps ffmpeg python3-opencv

# Picamera2 관련 패키지
sudo apt install -y python3-picamera2 python3-libcamera

# GPU 메모리 설정 (권장: 256MB)
sudo raspi-config  # Advanced Options → Memory Split → 256
```

### 참고 문서
- [Raspberry Pi Camera Documentation](https://www.raspberrypi.com/documentation/computers/camera_software.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenCV Python Tutorials](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)
- [ffmpeg Documentation](https://ffmpeg.org/documentation.html)

### 코딩 컨벤션
- **Python**: PEP 8 준수
- **함수명**: snake_case
- **클래스명**: PascalCase
- **상수**: UPPER_CASE
- **주석**: 한국어 + 영어 혼용

### Git 워크플로우
```bash
# 기능 브랜치
git checkout -b feature/new-detection-algorithm
git commit -m "feat: implement advanced motion detection"
git push origin feature/new-detection-algorithm
```

---

## 🤝 기여 가이드

### 코드 기여
1. 이슈 생성 및 논의
2. 기능 브랜치 생성
3. 코드 작성 및 테스트
4. 문서 업데이트
5. Pull Request 생성

### 문서 기여
- **PRD.md**: 제품 요구사항 및 아키텍처
- **README.md**: 사용자 가이드 및 설치 방법
- **CLAUDE.md**: 개발자 기술 문서 (현재 파일)

### 테스트 가이드 (2025.09 Picamera2 기준)
```bash
# Picamera2 CCTV 시스템 테스트
curl -I http://localhost:8001/stream  # 스트림 응답 확인 (HEAD 지원)
curl http://localhost:8001/api/stats  # 통계 API 테스트

# Picamera2 하드웨어 테스트
python3 picam2_simple.py              # 간단한 테스트 서버

# 모션 감지 테스트  
python3 -c "
import detection_cam0
config = detection_cam0.Config()
print(config.get_sensitivity_info())
"

# GPU 가속 확인
dmesg | grep -i pisp                   # PiSP 하드웨어 가속 로그
```

이 문서는 지속적으로 업데이트되며, 최신 버전은 항상 Git 저장소의 main 브랜치에서 확인할 수 있습니다.