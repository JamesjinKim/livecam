# RPi5 녹화 저장 방식 분석 및 권장사항

## 1. 두 가지 접근 방식 비교

### 방식 A: 로컬 저장 → 후 전송 (권장)
```
Camera → GPU Recorder → Local Storage → Background Uploader → NAS
                           ↓
                    Immediate Available
```

### 방식 B: 직접 NAS 쓰기
```
Camera → GPU Recorder → Mounted NAS → Direct Write
                           ↓
                    Network Dependent
```

## 2. 상세 비교 분석

|       항목          |     로컬 저장 → 전송                |   직접 NAS 쓰기             |
|--------------------|----------------------------------|--------------------------|
| **녹화 안정성**       | 🟢 **높음** - 네트워크와 무관          | 🔴 **낮음** - 네트워크 의존 |
| **네트워크 장애 대응** | 🟢 **우수** - 로컬 저장 후 복구 시 전송  | 🔴 **취약** - 녹화 중단 위험 |
| **저장 공간 효율성**   | 🟡 **보통** - 임시 이중 저장          | 🟢 **우수** - 단일 저장 |
| **I/O 성능**        | 🟢 **빠름** - 로컬 SSD/SD           | 🟡 **변동** - 네트워크 속도 의존 |
| **실시간성**         | 🟡 **지연** - 전송 시간 필요           | 🟢 **즉시** - 실시간 저장 |
| **구현 복잡도**       | 🟡 **보통** - 전송 로직 필요           | 🟢 **단순** - 직접 쓰기 |
| **장애 복구**         | 🟢 **용이** - 재전송 가능             | 🔴 **어려움** - 데이터 손실 위험 |

## 3. RPi5 환경 특성 분석

### 3.1 하드웨어 제약사항
```
라즈베리파이 5 사양:
├── CPU: ARM Cortex-A76 (4코어, 2.4GHz)
├── RAM: 4/8GB LPDDR4X
├── 저장장치: microSD / NVMe SSD
├── 네트워크: Gigabit Ethernet, WiFi 6
└── 비디오: H.264/H.265 하드웨어 인코딩

성능 특성:
├── 로컬 I/O: ~100MB/s (SSD), ~20MB/s (SD카드)
├── 네트워크: ~900Mbps (유선), ~300Mbps (WiFi)
├── 동시 녹화: 2개 카메라 (720p@30fps) = ~10MB/s
└── GPU 인코딩: CPU 부하 최소화
```

### 3.2 현재 시스템 분석 (webmain.py)
```python
# 현재 구현: 로컬 저장 방식
class GPURecorder:
    def _record_single_video(self, duration: int = None):
        # 로컬 경로에 직접 저장
        output_path = self.save_dir / f"cam{self.camera_id}_{timestamp}.mp4"
        self.current_output = FfmpegOutput(str(output_path))
        
        # H.264 GPU 인코딩으로 로컬 저장
        self.picam2.start_encoder(self.encoder)
```

## 4. PRD 요구사항 검토

### 4.1 핵심 요구사항
```
FR-4: 네트워크 연결이 일시적으로 끊겼을 경우, 
      로컬에 임시 저장 후 연결이 복구되면 전송을 재개해야 한다.

NFR-3: 특정 라즈베리파이의 장애가 전체 시스템 또는 
       다른 카메라의 녹화에 영향을 주지 않아야 한다.
```

➡️ **PRD가 명시적으로 로컬 저장 → 전송 방식을 요구**

## 5. 권장 구현 방식: 하이브리드 접근

### 5.1 3단계 저장 전략
```
1단계: 로컬 버퍼 저장 (Primary)
├── 목적: 안정적인 녹화 보장
├── 위치: /tmp/recording_buffer/ (RAM 디스크)
├── 용량: 30초~2분 분량 (약 100-200MB)
└── 형식: H.264 MP4

2단계: 로컬 안정 저장 (Secondary)  
├── 목적: 전송 실패 시 백업
├── 위치: /videos/local_backup/
├── 용량: 1-2시간 분량 (약 2-4GB)
└── 정책: 전송 완료 후 삭제

3단계: NAS 전송 (Final)
├── 목적: 중앙 집중 저장
├── 프로토콜: NFS/SMB/rsync
├── 방식: 백그라운드 비동기 전송
└── 재시도: 지수 백오프 전략
```

### 5.2 구현 아키텍처
```python
# 권장 구현 구조
class HybridRecorder:
    def __init__(self):
        self.local_buffer = LocalBuffer()      # RAM 디스크 버퍼
        self.local_storage = LocalStorage()    # 로컬 백업
        self.nas_uploader = NASUploader()      # 백그라운드 업로드
        
    def record_workflow(self):
        # 1단계: 로컬 버퍼에 녹화
        buffer_file = self.local_buffer.record()
        
        # 2단계: 로컬 저장소로 이동
        local_file = self.local_storage.move_from_buffer(buffer_file)
        
        # 3단계: 백그라운드 NAS 업로드
        self.nas_uploader.queue_upload(local_file)
```

## 6. 네트워크 프로토콜 선택

### 6.1 프로토콜 비교
|  프로토콜       | 성능    | 안정성  | 구현 복잡도 | 권장도 |
|----------    |------  |--------|--------|--------|
| **NFS**      | 🟢 높음 | 🟡 보통 | 🟢 단순 | ⭐⭐⭐⭐ |
| **SMB/CIFS** | 🟡 보통 | 🟢 높음 | 🟡 보통 | ⭐⭐⭐ |
| **SFTP**     | 🟡 보통 | 🟢 높음 | 🟡 보통 | ⭐⭐⭐ |
| **rsync**    | 🟢 높음 | 🟢 높음 | 🔴 복잡 | ⭐⭐⭐⭐⭐ |

### 6.2 권장 프로토콜: rsync
```bash
# rsync 전송 예시
rsync -avz --progress --remove-source-files \
  /videos/cam0/ \
  user@nas:/volume1/livecam/node01/cam0/

장점:
├── 중단된 전송 재개 가능
├── 체크섬 기반 무결성 검증
├── 압축 전송으로 대역폭 절약
├── 전송 완료 후 자동 로컬 파일 삭제
└── 네트워크 오류 시 자동 재시도
rsync는 "remote sync"의 줄임말로, 파일을 효율적으로 동기화하고 전송하는 도구입니다.
```

## 7. 구현 예시 코드 구조

### 7.1 확장된 GPURecorder
```python
class EnhancedGPURecorder(GPURecorder):
    def __init__(self, camera_id: int, picam2_instance):
        super().__init__(camera_id, picam2_instance)
        self.uploader = BackgroundUploader()
        
    def _record_single_video(self, duration: int = None):
        # 기존 로컬 녹화 로직 유지
        local_file = super()._record_single_video(duration)
        
        # 백그라운드 업로드 큐에 추가
        if local_file:
            self.uploader.queue_upload(local_file)
            
        return local_file
```

### 7.2 백그라운드 업로더
```python
class BackgroundUploader:
    def __init__(self):
        self.upload_queue = Queue()
        self.worker_thread = Thread(target=self._upload_worker)
        self.worker_thread.start()
        
    def queue_upload(self, file_path: str):
        self.upload_queue.put(file_path)
        
    def _upload_worker(self):
        while True:
            file_path = self.upload_queue.get()
            try:
                self._upload_file(file_path)
                os.remove(file_path)  # 전송 완료 후 삭제
            except Exception as e:
                self._handle_upload_error(file_path, e)
```

## 8. 성능 및 용량 계산

### 8.1 저장 용량 요구사항
```
단일 카메라 (720p@30fps, H.264):
├── 비트레이트: 5Mbps
├── 30초 파일: ~19MB
├── 1시간: ~2.25GB
└── 24시간: ~54GB

듀얼 카메라:
├── 1시간: ~4.5GB
├── 24시간: ~108GB
└── 7일: ~756GB

로컬 버퍼 요구사항:
├── RAM 디스크: 200MB (30초×2카메라×4버퍼)
├── 로컬 백업: 10GB (2시간 분량)
└── 네트워크 대역폭: 평균 10Mbps
```

### 8.2 네트워크 대역폭 분석
```
업로드 시나리오:
├── 실시간 업로드: 10Mbps (듀얼 카메라)
├── 네트워크 여유도: 50% (20Mbps 권장)
├── 장애 복구 시: 100Mbps (일괄 업로드)
└── WiFi 환경: 300Mbps (충분한 여유)
```

## 9. 최종 권장사항

### ✅ 채택할 방식: 로컬 저장 → rsync 전송

**근거:**
1. **PRD 요구사항 완벽 충족** - FR-4, NFR-3 만족
2. **기존 코드 최대 활용** - GPURecorder 95% 재사용
3. **안정성 우선** - 네트워크 장애와 무관한 녹화
4. **확장성 보장** - 다중 Node 환경에 적합
5. **운영 편의성** - 장애 상황 대응 용이

**구현 복잡도:** 중간 (백그라운드 업로더 추가)
**개발 기간:** 1-2주 (기존 시스템 확장)
**안정성:** 높음 (네트워크 독립적)

이 방식을 통해 **기존 시스템의 안정성을 유지하면서 PRD 요구사항을 효과적으로 충족**할 수 있습니다.
