#!/usr/bin/env python3
"""
장기 서비스 최적화 스트리밍 서버
메모리 누수 방지 및 안정성 개선
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
import gc
from collections import deque

# 전역 변수
BASE_DIR = Path("/home/shinho/shinho/livecam")
VIDEO_DIR = BASE_DIR / "videos"
streaming_processes = {}
streamers = {}

class OptimizedStreamer:
    """장기 서비스 최적화 스트리밍 클래스"""
    
    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self.process = None
        self.is_streaming = False
        self.client_lock = threading.Lock()
        
        # 메모리 관리 설정
        self.max_buffer_size = 512 * 1024  # 최대 512KB (메모리 누수 방지)
        self.chunk_size = 16384  # 16KB 청크 (CPU 효율성)
        self.frame_count = 0
        self.gc_interval = 1000  # 1000프레임마다 GC
        
    def start_stream(self):
        """스트리밍 시작"""
        if self.is_streaming:
            return
            
        # 장기 서비스용 안정화 설정
        cmd = [
            "rpicam-vid",
            "--camera", str(self.camera_id),
            "--width", "640", "--height", "480", 
            "--timeout", "0", "--nopreview",
            "--codec", "mjpeg", 
            "--quality", "75",       # 품질 vs 안정성 밸런스
            "--framerate", "15",     # 안정적인 프레임레이트
            "--bitrate", "0",
            "--denoise", "off",      # CPU 절약
            "--sharpness", "0.8",
            "--contrast", "1.0",
            "--saturation", "0.9",
            "--ev", "0", "--awb", "auto", 
            "--metering", "centre",
            "--flush", "1",          # 버퍼 플러시로 지연 최소화
            "--output", "-"
        ]
        
        # 카메라 1번 지연 시작
        if self.camera_id == 1:
            time.sleep(1)
        
        print(f"🚀 Starting optimized camera {self.camera_id}")
        
        self.process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0
        )
        
        # 시작 확인
        time.sleep(0.5)
        if self.process.poll() is not None:
            stdout, stderr = self.process.communicate()
            print(f"❌ Camera {self.camera_id} failed: {stderr.decode('utf-8')}")
            return
            
        self.is_streaming = True
        streaming_processes[self.camera_id] = self.process.pid
        print(f"✅ Camera {self.camera_id} optimized streaming (PID: {self.process.pid})")
        
    def get_optimized_frames(self) -> Generator[bytes, None, None]:
        """메모리 누수 방지 최적화 프레임 생성기"""
        if not self.is_streaming:
            self.start_stream()
            time.sleep(2)
            
        if not self.process or self.process.poll() is not None:
            return
            
        # 고정 크기 순환 버퍼 (메모리 누수 방지)
        buffer = bytearray(self.max_buffer_size)
        buffer_pos = 0
        
        # 프레임 헤더 상수 (GC 압박 감소)
        JPEG_START = b'\xff\xd8'
        JPEG_END = b'\xff\xd9'
        HEADER_PREFIX = b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
        HEADER_SUFFIX = b'\r\n\r\n'
        FRAME_SUFFIX = b'\r\n'
        
        try:
            while self.is_streaming and self.process and self.process.poll() is None:
                # 작은 청크로 안정적 읽기
                chunk = self.process.stdout.read(self.chunk_size)
                if not chunk:
                    time.sleep(0.01)
                    continue
                
                # 버퍼 오버플로우 방지 (순환 버퍼)
                if buffer_pos + len(chunk) > self.max_buffer_size:
                    # 버퍼 앞부분 제거하여 공간 확보
                    keep_size = self.max_buffer_size // 2
                    buffer[:keep_size] = buffer[buffer_pos - keep_size:buffer_pos]
                    buffer_pos = keep_size
                    print(f"📦 Camera {self.camera_id}: Buffer reset to prevent overflow")
                
                # 데이터 추가
                end_pos = buffer_pos + len(chunk)
                buffer[buffer_pos:end_pos] = chunk
                buffer_pos = end_pos
                
                # 효율적인 프레임 검색 (메모리 뷰 직접 사용)
                search_pos = 0
                while search_pos < buffer_pos - 10:  # 최소 헤더 크기 확보
                    # JPEG 시작 찾기 (메모리 뷰로 복사 없이)
                    start_found = False
                    for i in range(search_pos, buffer_pos - 1):
                        if buffer[i] == 0xFF and buffer[i + 1] == 0xD8:
                            start_idx = i
                            start_found = True
                            break
                    
                    if not start_found:
                        break
                    
                    # JPEG 끝 찾기
                    end_found = False
                    for i in range(start_idx + 2, buffer_pos - 1):
                        if buffer[i] == 0xFF and buffer[i + 1] == 0xD9:
                            end_idx = i + 1
                            end_found = True
                            break
                    
                    if not end_found:
                        # 버퍼 정리 (시작점부터 유지)
                        remaining = buffer_pos - start_idx
                        if remaining > 0 and start_idx > 0:
                            buffer[:remaining] = buffer[start_idx:buffer_pos]
                            buffer_pos = remaining
                        break
                    
                    # 완전한 프레임 추출
                    frame_size = end_idx - start_idx + 1
                    if frame_size >= 1024:  # 최소 프레임 크기 검증
                        frame = bytes(buffer[start_idx:end_idx + 1])
                        
                        # HTTP 멀티파트 응답
                        yield HEADER_PREFIX
                        yield str(frame_size).encode()
                        yield HEADER_SUFFIX
                        yield frame
                        yield FRAME_SUFFIX
                        
                        self.frame_count += 1
                        
                        # 주기적 가비지 컬렉션
                        if self.frame_count % self.gc_interval == 0:
                            gc.collect()
                            print(f"🧹 Camera {self.camera_id}: GC performed at frame {self.frame_count}")
                    
                    # 처리된 부분 제거
                    remaining = buffer_pos - (end_idx + 1)
                    if remaining > 0:
                        buffer[:remaining] = buffer[end_idx + 1:buffer_pos]
                        buffer_pos = remaining
                        search_pos = 0
                    else:
                        buffer_pos = 0
                        search_pos = 0
                        break
                        
        except Exception as e:
            print(f"❌ Streaming error for camera {self.camera_id}: {e}")
        finally:
            print(f"⏹️ Camera {self.camera_id} streaming ended after {self.frame_count} frames")
            
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
            
        # 강제 가비지 컬렉션
        gc.collect()
        print(f"🛑 Camera {self.camera_id} stopped and cleaned up")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 라이프사이클 관리"""
    print("🚀 Long-term Optimized Streaming Server Started")
    print("💾 Memory leak prevention and stability improvements enabled")
    
    # 가비지 컬렉션 최적화
    gc.set_threshold(700, 10, 10)
    
    streamers[0] = OptimizedStreamer(0)
    streamers[1] = OptimizedStreamer(1)
    
    yield
    
    # 정리
    for streamer in streamers.values():
        streamer.stop_stream()
    
    # 최종 메모리 정리
    gc.collect()
    print("👋 Optimized server stopped with full cleanup")

# FastAPI 앱
app = FastAPI(title="Optimized Long-term Streaming Server", lifespan=lifespan)

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
        <title>장기 서비스 최적화 스트리밍</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: 'SF Pro Display', Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; padding: 20px; margin: 0; }
            .container { max-width: 1400px; margin: 0 auto; }
            h1 { text-align: center; font-size: 2.5em; margin-bottom: 20px; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }
            .tech-info { background: rgba(255,255,255,0.1); padding: 20px; border-radius: 15px; margin-bottom: 30px; backdrop-filter: blur(10px); }
            .tech-info h3 { margin: 0 0 15px 0; color: #4ecdc4; }
            .camera-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(650px, 1fr)); gap: 30px; }
            .camera-box { background: rgba(255,255,255,0.05); border-radius: 20px; padding: 25px; box-shadow: 0 10px 40px rgba(0,0,0,0.4); }
            .video-container { background: #000; border-radius: 15px; overflow: hidden; border: 2px solid rgba(255,255,255,0.1); }
            .video-stream { width: 100%; height: auto; display: block; }
            .status { padding: 12px; border-radius: 8px; margin-top: 15px; text-align: center; font-weight: bold; }
            .status-online { background: linear-gradient(135deg, #2ecc71, #27ae60); color: #fff; }
            .status-offline { background: linear-gradient(135deg, #e74c3c, #c0392b); color: #fff; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔧 장기 서비스 최적화 스트리밍</h1>
            
            <div class="tech-info">
                <h3>🛡️ 안정성 개선 사항</h3>
                <ul>
                    <li><strong>메모리 누수 방지:</strong> 최대 512KB 고정 버퍼, 순환 관리</li>
                    <li><strong>가비지 컬렉션:</strong> 1000프레임마다 자동 메모리 정리</li>
                    <li><strong>CPU 최적화:</strong> 16KB 청크, 직접 메모리 검색</li>
                    <li><strong>버퍼 오버플로우 방지:</strong> 동적 크기 조정 제거</li>
                </ul>
            </div>
            
            <div class="camera-grid">
                <div class="camera-box">
                    <h3>📹 카메라 0번 (최적화)</h3>
                    <div class="video-container">
                        <img class="video-stream" id="cam0" src="/stream/0" 
                             onload="setStatus(0, 'online')" onerror="setStatus(0, 'offline')">
                    </div>
                    <div class="status" id="status0">🔄 연결 중...</div>
                </div>
                
                <div class="camera-box">
                    <h3>📹 카메라 1번 (최적화)</h3>
                    <div class="video-container">
                        <img class="video-stream" id="cam1" src="/stream/1"
                             onload="setStatus(1, 'online')" onerror="setStatus(1, 'offline')">
                    </div>
                    <div class="status" id="status1">🔄 연결 중...</div>
                </div>
            </div>
        </div>
        
        <script>
            function setStatus(id, status) {
                const statusDiv = document.getElementById('status' + id);
                if (status === 'online') {
                    statusDiv.className = 'status status-online';
                    statusDiv.innerHTML = '✅ 안정적 스트리밍 중';
                } else {
                    statusDiv.className = 'status status-offline';
                    statusDiv.innerHTML = '❌ 재연결 중...';
                    setTimeout(() => {
                        document.getElementById('cam' + id).src = '/stream/' + id + '?t=' + Date.now();
                    }, 5000);
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/stream/{camera_id}")
async def stream_camera(camera_id: int):
    """최적화된 MJPEG 스트리밍"""
    if camera_id not in streamers:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    return StreamingResponse(
        streamers[camera_id].get_optimized_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache", "Expires": "0", "Connection": "keep-alive"
        }
    )

@app.get("/status")
async def status():
    return {
        "cameras": {str(k): v.is_streaming for k, v in streamers.items()},
        "pids": streaming_processes,
        "optimization": "memory-leak-prevention-enabled"
    }

@app.get("/memory")
async def memory_info():
    """메모리 사용량 정보"""
    import psutil
    process = psutil.Process()
    return {
        "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
        "cpu_percent": process.cpu_percent(),
        "frame_counts": {str(k): v.frame_count for k, v in streamers.items()}
    }

if __name__ == "__main__":
    try:
        os.nice(-5)
    except PermissionError:
        pass
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")