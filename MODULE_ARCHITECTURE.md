# 분산 CCTV 시스템 모듈 아키텍처 설계

## 아키텍처 개요

### 설계 원칙
- **마이크로서비스**: 각 기능을 독립된 서비스로 분리
- **느슨한 결합**: 메시지 기반 통신으로 의존성 최소화
- **높은 응집도**: 관련 기능을 하나의 모듈로 그룹화
- **확장 가능**: 수평적 확장이 용이한 구조
- **장애 격리**: 한 모듈 장애가 전체 시스템에 영향 최소화

## 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────┐
│                    Client Layer                          │
│  [Web UI] [Mobile App] [API Client] [RTSP Client]       │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                    Gateway Layer                         │
│         [API Gateway]  [Load Balancer]  [Auth]          │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                    Service Layer                         │
│  [Stream Manager] [Storage Service] [Event Processor]    │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                     Node Layer                           │
│    [Camera Node 1]  [Camera Node 2]  [Camera Node N]    │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                    Storage Layer                         │
│         [NAS]  [Database]  [Cache]  [Queue]             │
└─────────────────────────────────────────────────────────┘
```

## 핵심 모듈 상세 설계

### 1. Camera Module (카메라 모듈)

```python
# modules/camera/camera_base.py
from abc import ABC, abstractmethod
import asyncio
from typing import Optional, AsyncGenerator

class CameraBase(ABC):
    """카메라 추상 기본 클래스"""

    def __init__(self, camera_id: str, config: dict):
        self.camera_id = camera_id
        self.config = config
        self.is_running = False
        self._frame_queue = asyncio.Queue(maxsize=10)

    @abstractmethod
    async def initialize(self) -> bool:
        """카메라 초기화"""
        pass

    @abstractmethod
    async def capture_frame(self) -> bytes:
        """프레임 캡처"""
        pass

    @abstractmethod
    async def release(self):
        """리소스 해제"""
        pass

# modules/camera/picamera_impl.py
from picamera2 import Picamera2
import libcamera

class PiCameraImpl(CameraBase):
    """라즈베리파이 카메라 구현"""

    async def initialize(self) -> bool:
        self.picam2 = Picamera2(self.config['camera_index'])
        config = self.picam2.create_video_configuration(
            main={"size": self.config['resolution']},
            transform=libcamera.Transform(
                hflip=self.config.get('mirror', False)
            )
        )
        self.picam2.configure(config)
        self.picam2.start()
        self.is_running = True
        return True

    async def capture_frame(self) -> bytes:
        if not self.is_running:
            raise RuntimeError("Camera not initialized")
        return self.picam2.capture_array()
```

### 2. Stream Module (스트리밍 모듈)

```python
# modules/stream/stream_manager.py
class StreamManager:
    """스트림 관리자"""

    def __init__(self):
        self.streams = {}
        self.clients = {}
        self.encoder_pool = EncoderPool()

    async def create_stream(
        self,
        camera_id: str,
        quality: str = "720p"
    ) -> str:
        """새 스트림 생성"""
        stream_id = f"{camera_id}_{quality}_{uuid.uuid4()}"

        encoder = await self.encoder_pool.get_encoder(quality)
        self.streams[stream_id] = {
            "camera_id": camera_id,
            "encoder": encoder,
            "clients": set(),
            "created_at": datetime.now()
        }

        return stream_id

    async def add_client(self, stream_id: str, client_id: str):
        """클라이언트 추가"""
        if stream_id in self.streams:
            self.streams[stream_id]["clients"].add(client_id)
            await self.optimize_encoding(stream_id)

# modules/stream/encoder.py
class AdaptiveEncoder:
    """적응형 인코더"""

    def __init__(self):
        self.bitrate_controller = BitrateController()
        self.quality_presets = {
            "1080p": {"width": 1920, "height": 1080, "bitrate": 8000},
            "720p": {"width": 1280, "height": 720, "bitrate": 4000},
            "480p": {"width": 854, "height": 480, "bitrate": 2000}
        }

    async def encode_frame(
        self,
        frame: np.ndarray,
        network_stats: dict
    ) -> bytes:
        """네트워크 상태에 따른 적응형 인코딩"""

        # 네트워크 상태 기반 품질 조정
        quality = self.bitrate_controller.get_optimal_quality(
            network_stats
        )

        # H.264/H.265 인코딩
        encoded = await self._hardware_encode(frame, quality)
        return encoded
```

### 3. Storage Module (저장 모듈)

```python
# modules/storage/storage_manager.py
class StorageManager:
    """저장소 관리자"""

    def __init__(self):
        self.primary_storage = NASStorage()
        self.buffer_storage = LocalBuffer()
        self.metadata_db = MetadataDB()

    async def save_segment(
        self,
        stream_id: str,
        segment_data: bytes,
        timestamp: datetime
    ):
        """세그먼트 저장 (HLS 방식)"""

        # 1. 메타데이터 저장
        metadata = {
            "stream_id": stream_id,
            "timestamp": timestamp,
            "size": len(segment_data),
            "duration": 30  # 30초 세그먼트
        }
        await self.metadata_db.insert(metadata)

        # 2. 로컬 버퍼에 저장
        buffer_path = await self.buffer_storage.save(
            segment_data,
            timestamp
        )

        # 3. NAS로 비동기 업로드
        asyncio.create_task(
            self._upload_to_nas(buffer_path, metadata)
        )

    async def _upload_to_nas(self, buffer_path: str, metadata: dict):
        """NAS 업로드 (재시도 로직 포함)"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self.primary_storage.upload(
                    buffer_path,
                    metadata
                )
                await self.buffer_storage.delete(buffer_path)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to upload: {e}")
                await asyncio.sleep(2 ** attempt)
```

### 4. Event Module (이벤트 처리 모듈)

```python
# modules/event/event_processor.py
class EventProcessor:
    """이벤트 처리기"""

    def __init__(self):
        self.detectors = {
            "motion": MotionDetector(),
            "person": PersonDetector(),
            "vehicle": VehicleDetector()
        }
        self.notification_service = NotificationService()

    async def process_frame(
        self,
        frame: np.ndarray,
        camera_id: str
    ):
        """프레임 분석 및 이벤트 감지"""

        events = []

        # 동작 감지
        if await self.detectors["motion"].detect(frame):
            events.append({
                "type": "motion",
                "camera_id": camera_id,
                "timestamp": datetime.now()
            })

        # 사람 감지 (YOLO 기반)
        persons = await self.detectors["person"].detect(frame)
        if persons:
            events.append({
                "type": "person_detected",
                "camera_id": camera_id,
                "count": len(persons),
                "timestamp": datetime.now()
            })

        # 이벤트 발생 시 알림
        for event in events:
            await self.notification_service.send(event)

        return events
```

### 5. Node Manager Module (노드 관리 모듈)

```python
# modules/node/node_manager.py
class NodeManager:
    """분산 노드 관리자"""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.cameras = {}
        self.health_checker = HealthChecker()
        self.message_broker = MessageBroker()

    async def register_node(self):
        """마스터 노드에 등록"""

        node_info = {
            "node_id": self.node_id,
            "ip": self._get_ip(),
            "cameras": list(self.cameras.keys()),
            "capacity": self._get_capacity(),
            "status": "online"
        }

        await self.message_broker.publish(
            "node:register",
            node_info
        )

        # 하트비트 시작
        asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """하트비트 전송"""
        while True:
            stats = await self.health_checker.get_stats()
            await self.message_broker.publish(
                f"node:{self.node_id}:heartbeat",
                stats
            )
            await asyncio.sleep(5)

# modules/node/load_balancer.py
class LoadBalancer:
    """부하 분산기"""

    def __init__(self):
        self.nodes = {}
        self.algorithm = "round_robin"  # or "least_connections"

    def select_node(self, request_type: str) -> str:
        """최적 노드 선택"""

        available_nodes = [
            node for node in self.nodes.values()
            if node["status"] == "online"
        ]

        if not available_nodes:
            raise NoAvailableNodeError()

        if self.algorithm == "round_robin":
            return self._round_robin_select(available_nodes)
        elif self.algorithm == "least_connections":
            return self._least_connections_select(available_nodes)
```

### 6. API Gateway Module

```python
# modules/gateway/api_gateway.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

class APIGateway:
    """API 게이트웨이"""

    def __init__(self):
        self.app = FastAPI(title="CCTV API Gateway")
        self.auth_service = AuthService()
        self.rate_limiter = RateLimiter()
        self.setup_routes()

    def setup_routes(self):
        """라우트 설정"""

        @self.app.get("/api/cameras")
        @self.rate_limiter.limit("10/minute")
        async def list_cameras(token: str = Depends(oauth2_scheme)):
            user = await self.auth_service.verify_token(token)
            cameras = await self.get_available_cameras()
            return cameras

        @self.app.websocket("/ws/stream/{camera_id}")
        async def stream_websocket(
            websocket: WebSocket,
            camera_id: str
        ):
            await websocket.accept()
            stream = await self.get_stream(camera_id)

            try:
                while True:
                    frame = await stream.get_frame()
                    await websocket.send_bytes(frame)
            except WebSocketDisconnect:
                await stream.remove_client(websocket)

# modules/gateway/auth.py
class AuthService:
    """인증 서비스"""

    def __init__(self):
        self.jwt_secret = config.JWT_SECRET
        self.redis = Redis()

    async def authenticate(
        self,
        username: str,
        password: str
    ) -> dict:
        """사용자 인증"""

        user = await self.verify_credentials(username, password)
        if not user:
            raise AuthenticationError()

        # JWT 토큰 생성
        token = jwt.encode(
            {
                "user_id": user.id,
                "exp": datetime.utcnow() + timedelta(hours=24)
            },
            self.jwt_secret,
            algorithm="HS256"
        )

        # Redis에 세션 저장
        await self.redis.set(
            f"session:{token}",
            user.id,
            ex=86400
        )

        return {"access_token": token, "token_type": "bearer"}
```

## 통신 프로토콜

### 내부 통신 (노드 간)
```yaml
Protocol: gRPC / MessagePack
Transport: TCP
Port Range: 5000-5100

Messages:
  - NodeRegister
  - NodeHeartbeat
  - StreamRequest
  - StreamData
  - EventNotification
```

### 외부 통신 (클라이언트)
```yaml
Protocol: HTTP/2, WebSocket
Transport: TLS 1.3
Port: 443

Endpoints:
  REST API: /api/v1/*
  WebSocket: /ws/*
  HLS Stream: /hls/*
  WebRTC: /webrtc/*
```

## 데이터 플로우

### 실시간 스트리밍 플로우
```
Camera → Encoder → Stream Buffer → Client
         ↓
    Event Detector → Notification
         ↓
    Storage Queue → NAS
```

### 녹화 재생 플로우
```
Client Request → API Gateway → Storage Service
                                      ↓
                               Metadata DB
                                      ↓
                                NAS Storage
                                      ↓
                               Stream Builder
                                      ↓
                                   Client
```

## 배포 구조

### Docker Compose 구성
```yaml
version: '3.8'

services:
  # 인프라 서비스
  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: cctv_metadata
    volumes:
      - postgres-data:/var/lib/postgresql/data

  # 노드 서비스 (확장 가능)
  camera-node-1:
    build: ./modules/node
    environment:
      NODE_ID: node-1
      REDIS_URL: redis://redis:6379
    devices:
      - /dev/video0:/dev/video0
      - /dev/video1:/dev/video1

  camera-node-2:
    build: ./modules/node
    environment:
      NODE_ID: node-2
    scale: 3  # 3개 인스턴스

  # 코어 서비스
  api-gateway:
    build: ./modules/gateway
    ports:
      - "443:443"
    depends_on:
      - redis
      - postgres

  storage-service:
    build: ./modules/storage
    volumes:
      - /mnt/nas:/storage

  event-processor:
    build: ./modules/event

volumes:
  redis-data:
  postgres-data:
```

### Kubernetes 구성 (선택적)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: camera-node
spec:
  replicas: 3
  selector:
    matchLabels:
      app: camera-node
  template:
    metadata:
      labels:
        app: camera-node
    spec:
      containers:
      - name: camera-node
        image: cctv/camera-node:latest
        resources:
          limits:
            memory: "512Mi"
            cpu: "500m"
        env:
        - name: NODE_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
```

## 모니터링 및 로깅

### 메트릭 수집
```python
# modules/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

class MetricsCollector:
    """메트릭 수집기"""

    # 카운터
    frames_processed = Counter(
        'frames_processed_total',
        'Total frames processed',
        ['camera_id']
    )

    # 히스토그램
    encoding_duration = Histogram(
        'encoding_duration_seconds',
        'Frame encoding duration'
    )

    # 게이지
    active_streams = Gauge(
        'active_streams',
        'Number of active streams'
    )
```

### 로깅 전략
```python
# modules/logging/logger.py
import structlog

logger = structlog.get_logger()

# 구조화된 로깅
logger.info(
    "stream_started",
    camera_id="cam-1",
    client_ip="192.168.1.100",
    quality="720p"
)
```

## 보안 고려사항

### 보안 모듈
```python
# modules/security/security.py
class SecurityManager:
    """보안 관리자"""

    def __init__(self):
        self.encryptor = AESEncryption()
        self.firewall = IPFirewall()
        self.audit_logger = AuditLogger()

    async def validate_request(self, request: Request):
        """요청 검증"""

        # IP 화이트리스트 체크
        if not self.firewall.is_allowed(request.client.host):
            self.audit_logger.log_blocked_attempt(request)
            raise SecurityException("IP not allowed")

        # 토큰 검증
        token = request.headers.get("Authorization")
        if not await self.validate_token(token):
            raise SecurityException("Invalid token")
```

---
**작성일**: 2025-09-19
**버전**: 1.0