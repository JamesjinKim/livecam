라즈베리 파이 5 기반 블랙박스 시스템 PRD (Product Requirements Document)
1. 제품 개요
본 문서는 라즈베리 파이 5(64bit)를 기반으로 한 고성능 블랙박스 시스템의 개발 요구사항을 정의합니다. 이 시스템은 C 언어의 DMA(Direct Memory Access) 기술을 활용해 효율적으로 영상을 저장하고, Python FastAPI를 통해 웹 UI로 실시간 스트리밍하는 기능을 제공합니다.
2. 목표 및 비전

최소한의 CPU 부하로 고성능 영상 캡처 및 저장 구현
안정적인 장시간 녹화 지원
사용자 친화적인 웹 인터페이스 제공
실시간 영상 스트리밍 기능 구현
C와 Python의 장점을 결합한 효율적인 시스템 아키텍처 구축

3. 기술 스택
3.1 하드웨어

라즈베리 파이 5 (64bit)
호환 카메라 모듈 (V4L2 지원)
충분한 저장 공간을 위한 SD 카드 또는 외장 저장장치

3.2 소프트웨어

C 언어 컴포넌트:

V4L2(Video for Linux 2) API
DMA(Direct Memory Access)
mmap(), ioctl() 등 저수준 시스템 호출
libjpeg (JPEG 압축)
Socket 프로그래밍


Python 컴포넌트:

Python 3.11
FastAPI (웹 프레임워크)
Uvicorn (ASGI 서버)
OpenCV/Numpy (영상 데이터 처리)
Socket (C 프로그램과의 통신)


프론트엔드:

HTML/CSS/JavaScript
MJPEG (Motion JPEG) 스트리밍



4. 시스템 요구사항
4.1 기능적 요구사항

영상 캡처 및 저장

카메라 영상을 DMA를 통해 효율적으로 캡처
설정 가능한 해상도 및 프레임 레이트 지원
영상 파일 자동 저장 및 관리
순환 저장 기능 (오래된 영상 자동 삭제)


실시간 스트리밍

웹 브라우저를 통한 실시간 카메라 영상 스트리밍
MJPEG 포맷 지원
다양한 브라우저 호환성 보장


사용자 인터페이스

녹화 시작/중지 컨트롤
저장된 영상 목록 확인 및 재생
시스템 상태 모니터링 (저장 공간, 카메라 상태 등)
설정 변경 인터페이스 (해상도, 프레임 레이트 등)



4.2 비기능적 요구사항

성능

최소 30 FPS 영상 캡처 및 저장
CPU 사용률 30% 이하 유지
메모리 사용 최적화
빠른 시스템 부팅 및 초기화 시간 (30초 이내)


안정성

24/7 연속 작동 지원
시스템 충돌 시 자동 복구 메커니즘
전원 손실 시 데이터 보호


확장성

다중 카메라 지원 가능성
추가 센서 통합 가능성 (GPS, 가속도계 등)
API를 통한 외부 시스템 연동



5. 시스템 아키텍처
5.1 아키텍처 개요
시스템은 C와 Python의 역할을 명확히 분리하여 각 언어의 장점을 극대화합니다.
+------------------------+        +------------------------+
|                        |        |                        |
|   C 프로세스             |  소켓  |   Python 프로세스      |
|   (카메라 접근 및 DMA)    | -----> |   (FastAPI 웹 서버)   |
|                        |  통신  |                        |
+------------------------+        +------------------------+
        |                                    |
        v                                    v
+------------------------+        +------------------------+
|                        |        |                        |
|   로컬 파일 저장          |        |   웹 브라우저          |
|   (영상 데이터)           |        |   (HTML/CSS/JS)        |
|                        |        |                        |
+------------------------+        +------------------------+
5.2 C 컴포넌트 (블랙박스 영상 저장)

카메라 장치에 대한 독점적 접근
V4L2 API를 통한 카메라 제어
DMA 버퍼 할당 및 관리
영상 데이터 JPEG 압축
영상 파일 저장
소켓을 통한 데이터 전송 (Python 프로세스로)

5.3 Python 컴포넌트 (웹 UI 및 스트리밍)

C 프로세스로부터 소켓을 통해 영상 데이터 수신
FastAPI를 활용한 웹 서버 운영
MJPEG 형식으로 웹 브라우저에 실시간 스트리밍
사용자 인터페이스 제공
시스템 제어 (녹화 시작/중지 등)

6. 구현 상세
6.1 C 언어 구현 (영상 캡처 및 소켓 송신)
6.1.1 개발 환경 설정
bashsudo apt update
sudo apt install build-essential libjpeg-dev
6.1.2 핵심 구현 단계

카메라 장치 접근
c// 카메라 장치 열기
int fd = open("/dev/video0", O_RDWR);
if (fd < 0) {
    perror("Failed to open device");
    return -1;
}

카메라 설정
cstruct v4l2_format fmt = {0};
fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
fmt.fmt.pix.width = 640;
fmt.fmt.pix.height = 480;
fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUYV;

if (ioctl(fd, VIDIOC_S_FMT, &fmt) < 0) {
    perror("Failed to set format");
    return -1;
}

DMA 버퍼 요청 및 매핑
cstruct v4l2_requestbuffers req = {0};
req.count = 4;  // 버퍼 개수
req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
req.memory = V4L2_MEMORY_MMAP;

if (ioctl(fd, VIDIOC_REQBUFS, &req) < 0) {
    perror("Failed to request buffers");
    return -1;
}

// 각 버퍼를 메모리에 매핑
struct buffer *buffers = calloc(req.count, sizeof(*buffers));
for (unsigned int i = 0; i < req.count; ++i) {
    struct v4l2_buffer buf = {0};
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    buf.index = i;
    
    if (ioctl(fd, VIDIOC_QUERYBUF, &buf) < 0) {
        perror("Failed to query buffer");
        return -1;
    }
    
    buffers[i].length = buf.length;
    buffers[i].start = mmap(NULL, buf.length, PROT_READ | PROT_WRITE, 
                           MAP_SHARED, fd, buf.m.offset);
}

영상 캡처 및 JPEG 압축
c// 스트리밍 시작
enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
if (ioctl(fd, VIDIOC_STREAMON, &type) < 0) {
    perror("Failed to start streaming");
    return -1;
}

// 프레임 처리 루프
while (running) {
    struct v4l2_buffer buf = {0};
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    
    // 버퍼 대기열에서 꺼내기
    if (ioctl(fd, VIDIOC_DQBUF, &buf) < 0) {
        perror("Failed to dequeue buffer");
        break;
    }
    
    // JPEG 압축 (libjpeg 사용)
    // ...
    
    // 파일에 저장
    // ...
    
    // 소켓으로 전송
    // ...
    
    // 버퍼 다시 대기열에 넣기
    if (ioctl(fd, VIDIOC_QBUF, &buf) < 0) {
        perror("Failed to queue buffer");
        break;
    }
}

소켓 통신 설정
cint client_socket = socket(AF_INET, SOCK_STREAM, 0);
struct sockaddr_in server_addr = {0};
server_addr.sin_family = AF_INET;
server_addr.sin_port = htons(5000);
server_addr.sin_addr.s_addr = inet_addr("127.0.0.1");

if (connect(client_socket, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
    perror("Failed to connect to server");
    return -1;
}

// 압축된 JPEG 데이터 전송
send(client_socket, jpeg_data, jpeg_size, 0);


6.2 Python FastAPI 구현 (스트리밍 중계)
6.2.1 개발 환경 설정
bashpip install fastapi uvicorn opencv-python numpy
6.2.2 핵심 구현 단계

소켓 서버 구현
pythonimport socket
import threading

class VideoReceiver:
    def __init__(self, host='127.0.0.1', port=5000):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        self.client_socket = None
        self.current_frame = None
        self.running = False
        
    def start(self):
        self.running = True
        threading.Thread(target=self._receive_frames).start()
        
    def _receive_frames(self):
        print(f"Waiting for connection on {self.host}:{self.port}")
        self.client_socket, _ = self.server_socket.accept()
        print("Connection established")
        
        buffer_size = 65536
        while self.running:
            try:
                # JPEG 크기 수신
                size_data = self.client_socket.recv(4)
                if not size_data:
                    break
                
                jpeg_size = int.from_bytes(size_data, byteorder='little')
                
                # JPEG 데이터 수신
                received_data = b''
                remaining = jpeg_size
                
                while remaining > 0:
                    chunk = self.client_socket.recv(min(buffer_size, remaining))
                    if not chunk:
                        break
                    received_data += chunk
                    remaining -= len(chunk)
                
                if len(received_data) == jpeg_size:
                    self.current_frame = received_data
            except Exception as e:
                print(f"Error receiving frame: {e}")
                break
        
        if self.client_socket:
            self.client_socket.close()

# 인스턴스 생성
video_receiver = VideoReceiver()
video_receiver.start()

FastAPI 엔드포인트 구현
pythonfrom fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
import cv2
import numpy as np

app = FastAPI()

def generate_frames():
    """MJPEG 스트림을 위한 프레임 생성기"""
    while True:
        if video_receiver.current_frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + 
                   video_receiver.current_frame + b'\r\n')

@app.get("/")
async def index():
    """메인 페이지"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>라즈베리파이 블랙박스</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; margin: 0; padding: 20px; }
            h1 { color: #333; }
            .video-container { margin: 20px auto; max-width: 800px; }
            img { width: 100%; border: 1px solid #ddd; }
            .controls { margin: 20px 0; }
            button { padding: 10px 20px; margin: 0 10px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>라즈베리파이 블랙박스 시스템</h1>
        <div class="video-container">
            <img src="/video_feed" alt="Video Stream">
        </div>
        <div class="controls">
            <button id="startBtn">녹화 시작</button>
            <button id="stopBtn">녹화 중지</button>
        </div>
        <script>
            document.getElementById('startBtn').addEventListener('click', function() {
                fetch('/start_recording', { method: 'POST' });
            });
            
            document.getElementById('stopBtn').addEventListener('click', function() {
                fetch('/stop_recording', { method: 'POST' });
            });
        </script>
    </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")

@app.get("/video_feed")
async def video_feed():
    """비디오 스트리밍 엔드포인트"""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.post("/start_recording")
async def start_recording():
    """녹화 시작 API"""
    # C 프로그램에 명령 전송 (별도 소켓 또는 파일 사용)
    return {"status": "recording_started"}

@app.post("/stop_recording")
async def stop_recording():
    """녹화 중지 API"""
    # C 프로그램에 명령 전송
    return {"status": "recording_stopped"}

# 서버 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


7. 개발 일정 및 마일스톤
7.1 개발 준비

라즈베리 파이 5 설정 및 OS 설치
개발 환경 구축
필요한 라이브러리 설치 및 테스트

7.2 C 컴포넌트 개발

V4L2 API를 통한 카메라 접근
DMA 버퍼 관리 구현
JPEG 압축 구현
파일 저장 시스템 구현
소켓 통신 구현

7.3 Python 컴포넌트 개발 (2주)

소켓 서버 구현
FastAPI 서버 설정
스트리밍 엔드포인트 구현
웹 UI 설계 및 구현
시스템 제어 API 구현

7.4 통합 및 테스트 (1주)

C와 Python 컴포넌트 통합
성능 테스트 및 최적화
오류 처리 및 안정성 개선

7.5 배포 및 문서화 (1주)

시스템 배포 스크립트 작성
사용자 매뉴얼 작성
API 문서화
최종 테스트 및 검증

8. 테스트 계획
8.1 기능 테스트

카메라 영상 캡처 테스트
영상 저장 및 재생 테스트
웹 스트리밍 기능 테스트
UI 컨트롤 테스트

8.2 성능 테스트

CPU 사용률 모니터링
메모리 사용량 테스트
프레임 레이트 테스트
장시간 안정성 테스트 (24시간 이상)

8.3 보안 테스트

웹 인터페이스 보안 테스트
네트워크 통신 보안 테스트

9. 배포 계획
9.1 시스템 패키징

설치 스크립트 작성
시스템 서비스 구성 (systemd)
자동 시작 설정

9.2 설치 가이드

하드웨어 설정 가이드
소프트웨어 설치 가이드
초기 설정 가이드

9.3 유지보수 계획

로그 관리 전략
디스크 공간 관리
시스템 업데이트 방법

10. 향후 확장 가능성

동작 감지 기능 추가
GPS 통합
클라우드 저장소 연동
다중 카메라 지원
모바일 앱 개발

11. 부록
11.1 용어 설명

DMA (Direct Memory Access): CPU 개입 없이 메모리에 직접 데이터를 전송하는 기술
V4L2 (Video for Linux 2): 리눅스에서 비디오 장치를 제어하기 위한 API
FastAPI: 파이썬 웹 프레임워크
MJPEG (Motion JPEG): 연속적인 JPEG 이미지를 사용하는 비디오 압축 포맷

11.2 참고 자료

V4L2 API 문서: https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/v4l2.html
FastAPI 문서: https://fastapi.tiangolo.com/
Raspberry Pi 카메라 모듈 문서: https://www.raspberrypi.com/documentation/accessories/camera.html