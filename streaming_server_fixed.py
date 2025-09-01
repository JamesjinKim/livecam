#!/usr/bin/env python3
"""
수정된 MJPEG 스트리밍 서버
화면 깨짐 문제 해결
"""

import asyncio
import os
import subprocess
import signal
from pathlib import Path
from datetime import datetime
from typing import Generator
import threading
import time
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# CORS 미들웨어는 lifespan 이후에 추가

# 전역 변수
BASE_DIR = Path("/home/shinho/shinho/livecam")
VIDEO_DIR = BASE_DIR / "videos"
recording_processes = {}
streaming_processes = {}

# 스트리머 인스턴스 (전역으로 이동)
streamers = {}

class FixedMJPEGStreamer:
    """수정된 MJPEG 스트리밍 클래스"""
    
    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self.process = None
        self.is_streaming = False
        
    def start_stream(self):
        """개선된 MJPEG 스트리밍 시작"""
        if self.is_streaming:
            return
            
        # 더 안정적인 rpicam-vid 명령 (녹화 지원)
        cmd = [
            "rpicam-vid",
            "--camera", str(self.camera_id),
            "--width", "640",
            "--height", "480", 
            "--timeout", "0",
            "--nopreview",
            "--codec", "mjpeg",
            "--quality", "85",
            "--framerate", "25", 
            "--bitrate", "0",
            "--denoise", "cdn_off",
            "--sharpness", "1.0",
            "--contrast", "1.0",
            "--saturation", "1.0",
            "--ev", "0",
            "--awb", "auto", 
            "--metering", "centre",
            "--flush", "1",
            "--output", "-"
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0  # 버퍼링 비활성화
        )
        self.is_streaming = True
        streaming_processes[self.camera_id] = self.process.pid
        print(f"✅ Camera {self.camera_id} streaming started (PID: {self.process.pid})")
        
    def get_fixed_frames(self) -> Generator[bytes, None, None]:
        """수정된 MJPEG 프레임 생성기"""
        if not self.is_streaming or not self.process:
            print(f"Starting stream for camera {self.camera_id}")
            self.start_stream()
            time.sleep(2)  # 초기화 대기
            
        if not self.process or self.process.poll() is not None:
            print(f"Process failed for camera {self.camera_id}")
            return
            
        buffer = bytearray()
        frame_count = 0
        
        try:
            while self.is_streaming and self.process and self.process.poll() is None:
                # 데이터 읽기
                chunk = self.process.stdout.read(16384)  # 16KB 청크
                if not chunk:
                    print(f"No data from camera {self.camera_id}")
                    time.sleep(0.1)
                    continue
                    
                buffer.extend(chunk)
                
                # 프레임 추출
                while True:
                    start_idx = buffer.find(b'\xff\xd8')
                    if start_idx == -1:
                        # 버퍼 크기 제한
                        if len(buffer) > 100000:
                            buffer = buffer[-50000:]
                        break
                        
                    end_idx = buffer.find(b'\xff\xd9', start_idx + 2)
                    if end_idx == -1:
                        if len(buffer) > 200000:  # 200KB 제한
                            buffer = buffer[start_idx:]
                            if len(buffer) > 100000:
                                buffer = buffer[:100000]
                        break
                        
                    # 완전한 프레임 추출
                    frame = bytes(buffer[start_idx:end_idx + 2])
                    buffer = buffer[end_idx + 2:]
                    
                    # 최소 프레임 크기 체크
                    if len(frame) < 1024:  # 1KB 미만은 스킵
                        continue
                        
                    frame_count += 1
                    
                    # MJPEG 멀티파트 응답 생성
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n'
                        b'Content-Length: ' + str(len(frame)).encode() + b'\r\n'
                        b'\r\n' + frame + b'\r\n'
                    )
                    
        except Exception as e:
            print(f"Error in camera {self.camera_id}: {e}")
        finally:
            print(f"Stream ended for camera {self.camera_id}")
                
    def stop_stream(self):
        """스트리밍 중지"""
        self.is_streaming = False
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
    # Startup
    print("🚀 Fixed Streaming Server Started")
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    
    # 스트리머 초기화
    streamers[0] = FixedMJPEGStreamer(0)
    streamers[1] = FixedMJPEGStreamer(1)
    
    # 스트리밍 시작 (순차적으로)
    for cam_id, streamer in streamers.items():
        try:
            streamer.start_stream()
            await asyncio.sleep(1.0)  # 충분한 간격
        except Exception as e:
            print(f"❌ Failed to start camera {cam_id}: {e}")
    
    yield  # 서버 실행 중
    
    # Shutdown
    for streamer in streamers.values():
        streamer.stop_stream()
    
    for pid in recording_processes.values():
        try:
            os.kill(pid, signal.SIGINT)
        except:
            pass
    print("👋 Server stopped")

# FastAPI 앱 생성 (lifespan 적용)
app = FastAPI(title="Fixed Blackbox Streaming Server", lifespan=lifespan)

# CORS 설정
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
        <title>Fixed Blackbox Streaming</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #0f0f0f 0%, #1a1a1a 100%);
                color: #fff;
                padding: 20px;
            }
            .container { max-width: 1400px; margin: 0 auto; }
            h1 {
                text-align: center;
                margin-bottom: 30px;
                font-size: 2rem;
                background: linear-gradient(90deg, #4CAF50, #45a049);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .camera-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
                gap: 20px;
            }
            .camera-box {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 12px;
                padding: 15px;
                backdrop-filter: blur(10px);
            }
            .camera-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }
            .camera-title { 
                font-size: 1.2rem;
                font-weight: 600;
            }
            .status-badge {
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.85rem;
                background: rgba(76, 175, 80, 0.2);
                color: #4CAF50;
                border: 1px solid #4CAF50;
            }
            .video-container {
                position: relative;
                width: 100%;
                padding-bottom: 75%;
                background: #000;
                border-radius: 8px;
                overflow: hidden;
            }
            .video-stream {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                object-fit: contain;
            }
            .controls {
                margin-top: 15px;
                display: flex;
                gap: 10px;
            }
            button {
                flex: 1;
                padding: 10px;
                background: linear-gradient(135deg, #4CAF50, #45a049);
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 600;
                transition: transform 0.2s;
            }
            button:hover { transform: translateY(-2px); }
            button:active { transform: translateY(0); }
            button.stop {
                background: linear-gradient(135deg, #f44336, #da190b);
            }
            .info {
                margin-top: 10px;
                padding: 10px;
                background: rgba(255,255,255,0.03);
                border-radius: 6px;
                font-size: 0.9rem;
                color: #aaa;
            }
            .loading {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: #4CAF50;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Fixed Blackbox Streaming System</h1>
            
            <div class="camera-grid">
                <div class="camera-box">
                    <div class="camera-header">
                        <div class="camera-title">📹 Camera 0</div>
                        <div class="status-badge" id="status0">Streaming</div>
                    </div>
                    <div class="video-container">
                        <img class="video-stream" id="stream0" alt="Camera 0">
                        <div class="loading" id="loading0">Loading...</div>
                    </div>
                    <div class="controls">
                        <button onclick="startRecording(0)">▶️ Record</button>
                        <button class="stop" onclick="stopRecording(0)">⏹️ Stop</button>
                        <button onclick="reconnect(0)">🔄 Reconnect</button>
                    </div>
                    <div class="info">640×480 @ 25fps | MJPEG 85% Quality</div>
                </div>
                
                <div class="camera-box">
                    <div class="camera-header">
                        <div class="camera-title">📹 Camera 1</div>
                        <div class="status-badge" id="status1">Streaming</div>
                    </div>
                    <div class="video-container">
                        <img class="video-stream" id="stream1" alt="Camera 1">
                        <div class="loading" id="loading1">Loading...</div>
                    </div>
                    <div class="controls">
                        <button onclick="startRecording(1)">▶️ Record</button>
                        <button class="stop" onclick="stopRecording(1)">⏹️ Stop</button>
                        <button onclick="reconnect(1)">🔄 Reconnect</button>
                    </div>
                    <div class="info">640×480 @ 25fps | MJPEG 85% Quality</div>
                </div>
            </div>
        </div>
        
        <script>
            let reconnectAttempts = {};
            
            // 스트림 초기화
            function initStream(camId) {
                const img = document.getElementById(`stream${camId}`);
                const loading = document.getElementById(`loading${camId}`);
                
                reconnectAttempts[camId] = 0;
                
                img.src = `/stream/${camId}?t=${Date.now()}`;
                
                img.onload = () => {
                    loading.style.display = 'none';
                    reconnectAttempts[camId] = 0;
                };
                
                img.onerror = () => {
                    loading.style.display = 'block';
                    loading.textContent = 'Connection lost. Retrying...';
                    
                    // 자동 재연결 (최대 5회)
                    if (reconnectAttempts[camId] < 5) {
                        reconnectAttempts[camId]++;
                        setTimeout(() => reconnect(camId), 3000);
                    } else {
                        loading.textContent = 'Connection failed. Click Reconnect.';
                    }
                };
            }
            
            // 재연결
            function reconnect(camId) {
                const img = document.getElementById(`stream${camId}`);
                const loading = document.getElementById(`loading${camId}`);
                loading.style.display = 'block';
                loading.textContent = 'Reconnecting...';
                
                img.src = '';
                setTimeout(() => {
                    img.src = `/stream/${camId}?t=${Date.now()}`;
                }, 500);
            }
            
            // 녹화 제어
            async function startRecording(camId) {
                try {
                    const response = await fetch(`/record/start/${camId}`, {method: 'POST'});
                    const data = await response.json();
                    document.getElementById(`status${camId}`).textContent = 'Recording';
                    document.getElementById(`status${camId}`).style.background = 'rgba(244, 67, 54, 0.2)';
                    document.getElementById(`status${camId}`).style.color = '#f44336';
                    document.getElementById(`status${camId}`).style.borderColor = '#f44336';
                } catch (e) {
                    console.error('Recording start failed:', e);
                }
            }
            
            async function stopRecording(camId) {
                try {
                    const response = await fetch(`/record/stop/${camId}`, {method: 'POST'});
                    const data = await response.json();
                    document.getElementById(`status${camId}`).textContent = 'Streaming';
                    document.getElementById(`status${camId}`).style.background = 'rgba(76, 175, 80, 0.2)';
                    document.getElementById(`status${camId}`).style.color = '#4CAF50';
                    document.getElementById(`status${camId}`).style.borderColor = '#4CAF50';
                } catch (e) {
                    console.error('Recording stop failed:', e);
                }
            }
            
            // 자동 재연결 타이머 (5분마다)
            setInterval(() => {
                for (let i = 0; i <= 1; i++) {
                    const img = document.getElementById(`stream${i}`);
                    if (img && img.complete && img.naturalWidth === 0) {
                        reconnect(i);
                    }
                }
            }, 300000);
            
            // 초기 로드
            window.onload = () => {
                setTimeout(() => initStream(0), 100);
                setTimeout(() => initStream(1), 500);
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/stream/{camera_id}")
async def stream_camera(camera_id: int):
    """수정된 MJPEG 스트리밍 엔드포인트"""
    if camera_id not in streamers:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    return StreamingResponse(
        streamers[camera_id].get_fixed_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/record/start/{camera_id}")
async def start_recording(camera_id: int):
    """녹화 시작 - 스트리밍과 카메라 충돌로 현재 불가능"""
    return {
        "status": "Error: Camera resource conflict", 
        "camera": camera_id,
        "message": "스트리밍 중에는 별도 녹화 불가능. 스트리밍을 중단하고 start_blackbox.sh를 사용하거나, 향후 tee 방식 구현 예정"
    }

@app.post("/record/stop/{camera_id}")
async def stop_recording(camera_id: int):
    """녹화 중지"""
    if camera_id not in recording_processes:
        return {"status": "Not recording", "camera": camera_id}
    
    pid = recording_processes[camera_id]
    try:
        os.kill(pid, signal.SIGINT)
        del recording_processes[camera_id]
        return {"status": "Recording stopped", "camera": camera_id}
    except Exception as e:
        return {"status": f"Error: {e}", "camera": camera_id}

@app.get("/status")
async def system_status():
    """시스템 상태"""
    return {
        "streaming": list(streaming_processes.keys()),
        "recording": list(recording_processes.keys()),
        "pids": {
            "streaming": streaming_processes,
            "recording": recording_processes
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")