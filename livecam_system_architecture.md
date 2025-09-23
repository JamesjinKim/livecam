# Livecam 중앙 저장 시스템 아키텍처 설계

## 1. 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                        사용자 인터페이스                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │  웹 브라우저 │ │   모바일    │ │    API     │                │
│  │             │ │   앱        │ │   클라이언트 │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │   HTTP/ HUB       │
                    └─────────┬─────────┘
┌─────────────────────────────────────────────────────────────────┐
│                    Livecam Hub Server                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │  Web UI     │ │  API Server │ │ File Server │                │
│  │  Service    │ │             │ │             │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
│                                                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │ Metadata    │ │ Health      │ │ Config      │                │
│  │ Manager     │ │ Monitor     │ │ Manager     │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │   NFS/SMB/HTTP    │
                    └─────────┬─────────┘
┌─────────────────────────────────────────────────────────────────┐
│                      중앙 NAS 저장소                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │ File System │ │ Access      │ │ Retention   │                │
│  │ Manager     │ │ Controller  │ │ Policy      │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
│                                                                 │
│     /videos/cam01/2025-09-23/cam01_20250923_153000.mp4          │
│     /videos/cam02/2025-09-23/cam02_20250923_153000.mp4          │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                    ┌─────────┴─────────┐
                    │   NFS/SMB Upload   │
                    └─────────┬─────────┘
┌─────────────────────────────────────────────────────────────────┐
│                     Edge Node 1 (RPi5)                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │ Camera      │ │ Recorder    │ │ Uploader    │                │
│  │ Controller  │ │ Service     │ │ Service     │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
│                                                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │ Health      │ │ Config      │ │ Local       │                │
│  │ Monitor     │ │ Manager     │ │ Storage     │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     Edge Node 2 (RPi5)                          │
│               (동일한 구조 반복)                                    │
└─────────────────────────────────────────────────────────────────┘
```

## 2. 모듈별 상세 구조

### 2.1 Edge Node (Raspberry Pi) 모듈 구조

| 계층 | 모듈 | 책임 | 의존성 |
|------|------|------|--------|
| **Application Layer** | main.py | 전체 애플리케이션 진입점 및 의존성 조합 | 모든 서비스 |
| | EdgeNodeOrchestrator | 전체 워크플로우 조율 | Camera, Recorder, Uploader |
| **Service Layer** | CameraService | 카메라 제어 및 스트림 관리 | ICameraAdapter |
| | RecorderService | 영상 녹화 및 분할 관리 | IRecorderAdapter, SegmentManager |
| | UploaderService | NAS 업로드 및 재시도 관리 | IUploaderAdapter, RetryManager |
| | HealthService | 시스템 상태 모니터링 | ConfigManager |
| **Domain Layer** | SegmentManager | 녹화 분할 로직 | 없음 |
| | RetryManager | 재시도 전략 관리 | IRetryStrategy |
| | FileManager | 로컬 파일 관리 | 없음 |
| **Infrastructure Layer** | PiCameraAdapter | PiCamera 하드웨어 인터페이스 | picamera2 |
| | NASUploaderAdapter | NFS/SMB 업로드 구현 | pysmb, nfs-utils |
| | ConfigManager | 설정 파일 관리 | json, yaml |

### 2.2 Hub Server 모듈 구조

| 계층 | 모듈 | 책임 | 의존성 |
|------|------|------|--------|
| **Presentation Layer** | WebUI | 사용자 인터페이스 제공 | 정적 파일 |
| | VideoAPI | 영상 관련 API 엔드포인트 | VideoService |
| | HealthAPI | 시스템 상태 API | HealthService |
| **Application Layer** | VideoService | 영상 목록 및 재생 비즈니스 로직 | MetadataManager, FileService |
| | HealthService | 시스템 전체 상태 관리 | NodeHealthManager |
| **Domain Layer** | MetadataManager | 영상 메타데이터 관리 | IMetadataRepository |
| | NodeHealthManager | Edge Node 상태 추적 | 없음 |
| | VideoSearchEngine | 영상 검색 로직 | 없음 |
| **Infrastructure Layer** | NASFileRepository | NAS 파일 시스템 접근 | NAS 연결 |
| | DatabaseRepository | 메타데이터 저장소 | SQLite/PostgreSQL |
| | FileStreamService | 영상 스트리밍 서비스 | HTTP 스트리밍 |

### 2.3 공통 모듈 (Shared) 구조

| 모듈 | 책임 | 사용처 |
|------|------|--------|
| CommonTypes | 공통 데이터 타입 정의 | 모든 모듈 |
| Logger | 통합 로깅 시스템 | 모든 모듈 |
| Exceptions | 커스텀 예외 정의 | 모든 모듈 |
| Validators | 데이터 검증 유틸리티 | 설정, API |
| Constants | 시스템 상수 정의 | 모든 모듈 |

## 3. 핵심 인터페이스 설계

### 3.1 Edge Node 인터페이스

```
ICameraAdapter
├── start_capture() -> None
├── stop_capture() -> None  
├── get_frame() -> bytes
├── configure_settings(resolution, fps) -> None
└── is_healthy() -> bool

IRecorderAdapter  
├── start_recording(output_path: str) -> None
├── stop_recording() -> str
├── pause_recording() -> None
├── resume_recording() -> None
└── get_recording_status() -> RecordingStatus

IUploaderAdapter
├── upload_file(local_path: str, remote_path: str) -> UploadResult
├── check_connection() -> bool
├── get_upload_progress(file_id: str) -> float
└── cancel_upload(file_id: str) -> None

IConfigManager
├── load_config(config_path: str) -> Config
├── get_value(key: str, default: Any) -> Any
├── validate_config() -> bool
└── reload_config() -> None
```

### 3.2 Hub Server 인터페이스

```
IVideoService
├── get_video_list(camera_id: str, date_range: DateRange) -> List[VideoMetadata]
├── get_video_stream_url(video_id: str) -> str
├── search_videos(query: SearchQuery) -> List[VideoMetadata]
└── get_video_thumbnail(video_id: str) -> bytes

IMetadataRepository
├── save_video_metadata(metadata: VideoMetadata) -> None
├── find_videos_by_camera(camera_id: str) -> List[VideoMetadata]
├── find_videos_by_date(date_range: DateRange) -> List[VideoMetadata]
├── update_video_status(video_id: str, status: VideoStatus) -> None
└── delete_video_metadata(video_id: str) -> None

IHealthMonitor
├── get_system_status() -> SystemStatus
├── get_node_status(node_id: str) -> NodeStatus
├── register_node(node_info: NodeInfo) -> None
└── update_node_heartbeat(node_id: str) -> None
```

## 4. 데이터 모델 설계

### 4.1 핵심 도메인 객체

```
VideoMetadata
├── video_id: str
├── camera_id: str  
├── file_path: str
├── file_size: int
├── duration: int
├── created_at: datetime
├── start_time: datetime
├── end_time: datetime
├── resolution: Resolution
├── fps: int
└── status: VideoStatus

NodeInfo
├── node_id: str
├── camera_id: str
├── ip_address: str
├── last_heartbeat: datetime
├── status: NodeStatus
├── system_info: SystemInfo
└── config_version: str

Config
├── camera_settings: CameraSettings
├── recording_settings: RecordingSettings  
├── upload_settings: UploadSettings
├── network_settings: NetworkSettings
└── system_settings: SystemSettings
```

### 4.2 디렉토리 구조 규칙

```
NAS 저장소 구조:
/videos/
├── cam01/
│   ├── 2025-09-23/
│   │   ├── cam01_20250923_000000.mp4
│   │   ├── cam01_20250923_001000.mp4
│   │   └── ...
│   └── 2025-09-24/
├── cam02/
│   └── 2025-09-23/
└── metadata/
    ├── video_index.db
    └── thumbnails/
```

## 5. 통신 프로토콜 설계

### 5.1 Edge Node ↔ NAS
| 프로토콜 | 용도 | 포트 | 인증 |
|----------|------|------|------|
| NFS v4 | 파일 업로드 (기본) | 2049 | Kerberos/None |
| SMB/CIFS | 파일 업로드 (대안) | 445 | Username/Password |
| HTTP POST | 메타데이터 전송 | 8080 | API Key |

### 5.2 Client ↔ Hub Server  
| 엔드포인트 | 메소드 | 용도 | 응답 형식 |
|------------|--------|------|----------|
| /api/videos | GET | 영상 목록 조회 | JSON |
| /api/videos/{id}/stream | GET | 영상 스트리밍 | MP4 Stream |
| /api/videos/search | POST | 영상 검색 | JSON |
| /api/nodes/status | GET | Node 상태 조회 | JSON |
| /api/health | GET | 시스템 상태 | JSON |

## 6. 에러 처리 및 복구 전략

### 6.1 Edge Node 에러 처리
```
카메라 에러
├── 하드웨어 에러 감지
├── 자동 재시작 시도
├── 실패 시 관리자 알림
└── Fallback: Mock 데이터 생성

네트워크 에러  
├── 연결 끊김 감지
├── 로컬 임시 저장
├── 주기적 재연결 시도
└── 연결 복구 시 일괄 업로드

저장소 에러
├── 로컬 디스크 풀 감지
├── 오래된 파일 자동 삭제
├── 압축 저장 모드 전환
└── 임계치 도달 시 녹화 중단
```

### 6.2 Hub Server 에러 처리
```
NAS 연결 에러
├── 연결 상태 모니터링
├── 재연결 시도
├── 캐시된 메타데이터 활용
└── 읽기 전용 모드 전환

스트리밍 에러
├── 파일 무결성 검증
├── 다중 해상도 Fallback
├── 청크 단위 스트리밍
└── 에러 로그 수집
```

## 7. 테스트 전략

### 7.1 단위 테스트 범위
```
Edge Node
├── CameraService: Mock 카메라로 녹화 테스트
├── RecorderService: 파일 분할 로직 테스트  
├── UploaderService: Mock NAS로 업로드 테스트
├── SegmentManager: 분할 규칙 테스트
└── RetryManager: 재시도 로직 테스트

Hub Server  
├── VideoService: 메타데이터 처리 테스트
├── MetadataManager: DB 연산 테스트
├── VideoAPI: API 엔드포인트 테스트
├── HealthService: 상태 모니터링 테스트
└── FileStreamService: 스트리밍 로직 테스트
```

### 7.2 통합 테스트 시나리오
```
시나리오 1: 정상 녹화 및 업로드
├── Edge Node 시작
├── 카메라 영상 녹화
├── 분할 파일 생성
├── NAS 업로드 완료
└── Hub Server에서 조회 가능

시나리오 2: 네트워크 장애 복구
├── 녹화 중 네트워크 끊김
├── 로컬 임시 저장
├── 네트워크 복구
└── 일괄 업로드 완료

시나리오 3: 동시 다중 스트리밍
├── 여러 사용자 동시 접속
├── 다른 영상 동시 재생
├── 성능 모니터링
└── 응답 시간 검증
```

## 8. 배포 및 모니터링

### 8.1 배포 구조
```
Production 환경
├── Edge Nodes: Docker Container (ARM64)
├── Hub Server: Docker Container (x86_64)  
├── NAS: Synology/QNAP/TrueNAS
├── Database: SQLite (Small) / PostgreSQL (Large)
└── Monitoring: Prometheus + Grafana
```

### 8.2 모니터링 지표
```
System Metrics
├── CPU/Memory/Disk Usage
├── Network I/O
├── Temperature (RPi)
└── Storage Capacity

Application Metrics  
├── Recording FPS
├── Upload Success Rate
├── API Response Time
├── Active Streams Count
└── Error Rate by Module
```

이 아키텍처는 SOLID 원칙을 준수하며 확장 가능하고 테스트 가능한 구조로 설계되었습니다.
