#!/usr/bin/env python3
"""
단일 클라이언트 스트리밍 서버 (새 접속자 우선)
기존 streaming_server_fixed.py 기반으로 연결 제한 추가
"""

import asyncio
import os
import subprocess
import signal
from pathlib import Path
from datetime import datetime
from typing import Generator, Optional
import time
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import threading

# 전역 변수
BASE_DIR = Path("/home/shinho/shinho/livecam")
VIDEO_DIR = BASE_DIR / "videos"
recording_processes = {}
streaming_processes = {}
streamers = {}

class SingleClientStreamer:
    """단일 클라이언트 스트리밍 클래스 (새 접속자 우선)"""
    
    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self.process = None
        self.is_streaming = False
        self.current_client = None
        self.client_lock = threading.Lock()
        self.disconnect_event = None
        
    def start_stream(self):
        """스트리밍 시작"""
        if self.is_streaming:
            return
            
        # 단일 클라이언트 고품질 rpicam-vid 명령
        cmd = [
            "rpicam-vid",
            "--camera", str(self.camera_id),
            "--width", "640", "--height", "480", 
            "--timeout", "0", "--nopreview",
            "--codec", "mjpeg", "--quality", "90",
            "--framerate", "25", "--bitrate", "0",
            "--denoise", "auto", "--sharpness", "1.0",
            "--contrast", "1.1", "--saturation", "1.0",
            "--ev", "0", "--awb", "auto", 
            "--metering", "centre", "--flush", "1",
            "--output", "-"
        ]
        
        self.process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0
        )
        
        self.is_streaming = True
        streaming_processes[self.camera_id] = self.process.pid
        print(f"✅ Camera {self.camera_id} single-client streaming started")
        
    def connect_client(self, client_id: str):
        """새 클라이언트 연결 (기존 클라이언트 해제)"""
        with self.client_lock:
            if self.current_client and self.current_client != client_id:
                print(f"🔄 Camera {self.camera_id}: Disconnecting existing client, connecting new client {client_id}")
                # 기존 클라이언트에게 연결 해제 신호
                if self.disconnect_event:
                    self.disconnect_event.set()
                    
            self.current_client = client_id
            self.disconnect_event = threading.Event()
            print(f"📱 Camera {self.camera_id}: Client {client_id} connected")
            return self.disconnect_event
            
    def disconnect_client(self, client_id: str):
        """클라이언트 연결 해제"""
        with self.client_lock:
            if self.current_client == client_id:
                self.current_client = None
                self.disconnect_event = None
                print(f"📱 Camera {self.camera_id}: Client {client_id} disconnected")
                
    def get_single_client_frames(self, client_id: str) -> Generator[bytes, None, None]:
        """단일 클라이언트 프레임 생성기"""
        if not self.is_streaming:
            self.start_stream()
            time.sleep(2)
            
        # 클라이언트 연결 등록
        disconnect_event = self.connect_client(client_id)
        
        # 고품질용 큰 버퍼 관리
        buffer = bytearray(131072)  # 128KB로 증가
        buffer_pos = 0
        frame_count = 0
        
        # 프레임 헤더 캐싱
        header_template = (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n'
            b'Content-Length: '
        )
        header_suffix = b'\r\n\r\n'
        frame_suffix = b'\r\n'
        
        try:
            while self.is_streaming and self.process and self.process.poll() is None:
                # 연결 해제 신호 확인
                if disconnect_event and disconnect_event.is_set():
                    print(f"🔄 Camera {self.camera_id}: Client {client_id} disconnected by new connection")
                    break
                    
                # 데이터 읽기
                chunk = self.process.stdout.read(32768)
                if not chunk:
                    time.sleep(0.05)
                    continue
                    
                # 안전한 버퍼 관리 (memoryview 오류 방지)
                if buffer_pos + len(chunk) > len(buffer):
                    # 새로운 큰 버퍼로 교체
                    new_size = max(len(buffer) * 2, buffer_pos + len(chunk))
                    new_buffer = bytearray(new_size)
                    new_buffer[0:buffer_pos] = buffer[0:buffer_pos]
                    buffer = new_buffer
                
                buffer[buffer_pos:buffer_pos + len(chunk)] = chunk
                buffer_pos += len(chunk)
                
                # 프레임 추출
                search_start = 0
                while search_start < buffer_pos:
                    # 연결 해제 재확인
                    if disconnect_event and disconnect_event.is_set():
                        break
                        
                    # 안전한 바이트 검색 (memoryview 없이)
                    buffer_section = bytes(buffer[search_start:buffer_pos])
                    start_idx = buffer_section.find(b'\xff\xd8')
                    if start_idx == -1:
                        break
                    start_idx += search_start
                        
                    end_section = bytes(buffer[start_idx + 2:buffer_pos])
                    end_idx = end_section.find(b'\xff\xd9')
                    if end_idx == -1:
                        if buffer_pos > 262144:  # 256KB 제한
                            remaining = buffer_pos - start_idx
                            buffer[0:remaining] = buffer[start_idx:buffer_pos]
                            buffer_pos = remaining
                        break
                    end_idx += start_idx + 2
                        
                    frame_size = end_idx + 2 - start_idx
                    if frame_size < 2048:
                        search_start = end_idx + 2
                        continue
                        
                    frame = bytes(buffer[start_idx:end_idx + 2])
                    frame_count += 1
                    
                    # HTTP 응답 생성
                    frame_len_bytes = str(frame_size).encode('ascii')
                    yield (header_template + frame_len_bytes + header_suffix + frame + frame_suffix)
                    
                    search_start = end_idx + 2
                
                # 처리된 데이터 제거
                if search_start > 0:
                    remaining = buffer_pos - search_start
                    if remaining > 0:
                        buffer[0:remaining] = buffer[search_start:buffer_pos]
                    buffer_pos = remaining
                
                # CPU 사용률 제한
                if frame_count % 20 == 0:
                    time.sleep(0.001)
                    
        except Exception as e:
            print(f"Error in camera {self.camera_id} client {client_id}: {e}")
        finally:
            self.disconnect_client(client_id)
            
    def stop_stream(self):
        """스트리밍 중지"""
        self.is_streaming = False
        
        # 모든 클라이언트 연결 해제
        with self.client_lock:
            if self.disconnect_event:
                self.disconnect_event.set()
                
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except:
                self.process.kill()
                
        if self.camera_id in streaming_processes:
            del streaming_processes[self.camera_id]
            
        print(f"⏹️ Camera {self.camera_id} streaming stopped")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 라이프사이클 관리"""
    print("🚀 Single Client Streaming Server Started")
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    
    # 스트리머 초기화
    streamers[0] = SingleClientStreamer(0)
    streamers[1] = SingleClientStreamer(1)
    
    yield
    
    # 종료 시 정리
    for streamer in streamers.values():
        streamer.stop_stream()
    
    print("👋 Single Client Server stopped")

# FastAPI 앱 생성
app = FastAPI(title="Single Client Streaming Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """웹 UI"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Single Client Blackbox Streaming</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial; background: #1a1a1a; color: #fff; padding: 20px; }
            .container { max-width: 1400px; margin: 0 auto; }
            h1 { text-align: center; color: #4CAF50; margin-bottom: 10px; }
            .subtitle { text-align: center; color: #ff9800; margin-bottom: 30px; font-size: 16px; }
            .warning { text-align: center; background: rgba(255,152,0,0.1); border: 1px solid #ff9800; border-radius: 8px; padding: 15px; margin: 20px 0; color: #ff9800; }
            .camera-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(600px, 1fr)); gap: 20px; }
            .camera-box { background: rgba(255,255,255,0.05); border: 1px solid #333; border-radius: 8px; padding: 15px; }
            .video-container { position: relative; width: 100%; padding-bottom: 75%; background: #000; border-radius: 8px; overflow: hidden; }
            .video-stream { position: absolute; width: 100%; height: 100%; object-fit: contain; }
            .info { margin-top: 10px; font-size: 14px; color: #aaa; }
            .status { margin-top: 10px; padding: 8px; background: rgba(76,175,80,0.1); border-radius: 4px; font-size: 14px; color: #4CAF50; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Single Client Blackbox Streaming</h1>
            <div class="subtitle">⚠️ 한 번에 1명만 접속 가능 | 새 접속 시 기존 연결 해제</div>
            
            <div class="warning">
                <strong>📢 연결 제한 안내</strong><br>
                • 동시에 1명만 스트리밍 시청 가능합니다<br>
                • 새로운 사용자가 접속하면 기존 연결이 자동으로 해제됩니다<br>
                • 안정적인 화질을 위한 제한입니다
            </div>
            
            <div class="camera-grid">
                <div class="camera-box">
                    <h3>📹 Camera 0</h3>
                    <div class="video-container">
                        <img class="video-stream" src="/stream/0" alt="Camera 0" onerror="this.style.display='none';">
                    </div>
                    <div class="info">640×480 @ 25fps | MJPEG 90% | 고품질 단일 클라이언트</div>
                    <div class="status">🔐 단일 클라이언트 전용</div>
                </div>
                
                <div class="camera-box">
                    <h3>📹 Camera 1</h3>
                    <div class="video-container">
                        <img class="video-stream" src="/stream/1" alt="Camera 1" onerror="this.style.display='none';">
                    </div>
                    <div class="info">640×480 @ 25fps | MJPEG 90% | 고품질 단일 클라이언트</div>
                    <div class="status">🔐 단일 클라이언트 전용</div>
                </div>
            </div>
            
            <script>
                // 연결 상태 모니터링
                let connectionId = Date.now() + Math.random();
                console.log('Connection ID:', connectionId);
                
                // 연결 해제 감지
                window.addEventListener('beforeunload', function() {
                    // 페이지 종료 시 정리 작업
                    console.log('Disconnecting...');
                });
                
                // 주기적 연결 상태 확인
                setInterval(function() {
                    fetch('/status').catch(function() {
                        console.log('Connection lost');
                    });
                }, 30000); // 30초마다
            </script>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/stream/{camera_id}")
async def stream_camera(camera_id: int):
    """단일 클라이언트 MJPEG 스트리밍"""
    if camera_id not in streamers:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # 클라이언트 ID 생성 (IP + 타임스탬프)
    import hashlib
    client_id = hashlib.md5(f"{time.time()}".encode()).hexdigest()[:8]
    
    return StreamingResponse(
        streamers[camera_id].get_single_client_frames(client_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "X-Client-ID": client_id
        }
    )

@app.get("/status")
async def system_status():
    """시스템 상태"""
    status = {
        "streaming": list(streaming_processes.keys()),
        "pids": {"streaming": streaming_processes},
        "clients": {}
    }
    
    for cam_id, streamer in streamers.items():
        if streamer.is_streaming:
            with streamer.client_lock:
                status["clients"][cam_id] = {
                    "current_client": streamer.current_client,
                    "connected": bool(streamer.current_client)
                }
    
    return status

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")