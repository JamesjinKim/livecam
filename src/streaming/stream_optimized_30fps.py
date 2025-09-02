#!/usr/bin/env python3
"""
30fps 고성능 최적화 스트리밍 서버
메모리 누수 방지 + 부드러운 영상을 위한 30fps 최적화
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

class HighPerformance30FpsStreamer:
    """30fps 고성능 최적화 스트리밍 클래스"""
    
    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self.process = None
        self.is_streaming = False
        self.client_lock = threading.Lock()
        
        # 30fps용 최적화된 메모리 관리
        self.max_buffer_size = 768 * 1024  # 768KB (30fps용 증가)
        self.chunk_size = 32768  # 32KB 청크 (30fps 대응)
        self.frame_count = 0
        self.gc_interval = 1500  # 1500프레임마다 GC (30fps 고려)
        
        # 프레임 스킵 방지용 버퍼
        self.frame_buffer_pool = deque(maxlen=3)  # 3개 버퍼 풀
        for _ in range(3):
            self.frame_buffer_pool.append(bytearray(self.max_buffer_size))
        
    def start_stream(self):
        """30fps 최적화 스트리밍 시작"""
        if self.is_streaming:
            return
            
        # 30fps 고성능 설정 (라즈베리파이 5 최적화)
        cmd = [
            "rpicam-vid",
            "--camera", str(self.camera_id),
            "--width", "640", "--height", "480", 
            "--timeout", "0", "--nopreview",
            "--codec", "mjpeg", 
            "--quality", "80",       # 30fps용 품질 상향 조정
            "--framerate", "30",     # 🎯 30fps 부드러운 영상
            "--bitrate", "0",
            "--denoise", "cdn_fast", # 빠른 하드웨어 노이즈 제거
            "--sharpness", "1.0",    # 30fps용 선명도 향상
            "--contrast", "1.1",     # 약간의 대비 향상
            "--saturation", "1.0",   # 자연스러운 채도
            "--ev", "0", "--awb", "auto", 
            "--metering", "centre",
            "--flush", "1",          # 실시간 플러시
            "--output", "-"
        ]
        
        # 카메라 1번 짧은 지연 (30fps에서는 빠른 시작 필요)
        if self.camera_id == 1:
            time.sleep(0.5)  # 1초 → 0.5초로 단축
        
        print(f"🎬 Starting 30fps high-performance camera {self.camera_id}")
        
        self.process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0
        )
        
        # 시작 확인
        time.sleep(0.3)  # 빠른 시작 확인
        if self.process.poll() is not None:
            stdout, stderr = self.process.communicate()
            print(f"❌ Camera {self.camera_id} failed: {stderr.decode('utf-8')}")
            return
            
        self.is_streaming = True
        streaming_processes[self.camera_id] = self.process.pid
        print(f"✅ Camera {self.camera_id} 30fps streaming (PID: {self.process.pid})")
        
    def get_optimized_30fps_frames(self) -> Generator[bytes, None, None]:
        """30fps 메모리 누수 방지 최적화 프레임 생성기"""
        if not self.is_streaming:
            self.start_stream()
            time.sleep(1.5)  # 30fps용 빠른 초기화
            
        if not self.process or self.process.poll() is not None:
            return
            
        # 버퍼 풀에서 버퍼 가져오기
        buffer = self.frame_buffer_pool.popleft()
        self.frame_buffer_pool.append(buffer)  # 순환 사용
        buffer_pos = 0
        
        # 30fps 최적화 상수
        JPEG_START = b'\xff\xd8'
        JPEG_END = b'\xff\xd9'
        HEADER_PREFIX = b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
        HEADER_SUFFIX = b'\r\n\r\n'
        FRAME_SUFFIX = b'\r\n'
        
        # 30fps용 성능 카운터
        frame_skip_count = 0
        last_frame_time = time.time()
        
        try:
            while self.is_streaming and self.process and self.process.poll() is None:
                # 30fps용 적응적 청크 읽기
                current_time = time.time()
                time_since_last_frame = current_time - last_frame_time
                
                # 프레임 간격 기반 청크 크기 조정
                if time_since_last_frame > 0.05:  # 20fps 이하로 떨어지면
                    chunk_size = self.chunk_size * 2  # 청크 크기 증가
                else:
                    chunk_size = self.chunk_size
                
                chunk = self.process.stdout.read(chunk_size)
                if not chunk:
                    time.sleep(0.005)  # 30fps용 짧은 대기
                    continue
                
                # 버퍼 오버플로우 방지 (30fps 최적화)
                if buffer_pos + len(chunk) > self.max_buffer_size:
                    # 앞쪽 1/3 제거하여 공간 확보
                    keep_size = self.max_buffer_size * 2 // 3
                    buffer[:keep_size] = buffer[buffer_pos - keep_size:buffer_pos]
                    buffer_pos = keep_size
                    # print(f"📦 Camera {self.camera_id}: 30fps buffer optimized")
                
                # 데이터 추가
                end_pos = buffer_pos + len(chunk)
                buffer[buffer_pos:end_pos] = chunk
                buffer_pos = end_pos
                
                # 30fps 최적화된 프레임 검색 (인라인 최적화)
                search_pos = 0
                frames_found_in_chunk = 0
                
                while search_pos < buffer_pos - 10:
                    # JPEG 시작 찾기 (30fps 최적화 - 메모리 뷰 사용)
                    start_found = False
                    start_idx = search_pos
                    
                    # 빠른 바이트 스캔
                    for i in range(search_pos, buffer_pos - 1):
                        if buffer[i] == 0xFF and buffer[i + 1] == 0xD8:
                            start_idx = i
                            start_found = True
                            break
                    
                    if not start_found:
                        break
                    
                    # JPEG 끝 찾기
                    end_found = False
                    end_idx = start_idx + 2
                    
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
                    
                    # 완전한 프레임 추출 (30fps 최적화)
                    frame_size = end_idx - start_idx + 1
                    if frame_size >= 2048:  # 최소 프레임 크기 검증
                        frame = bytes(buffer[start_idx:end_idx + 1])
                        frames_found_in_chunk += 1
                        
                        # 30fps 품질 확인
                        current_time = time.time()
                        frame_interval = current_time - last_frame_time
                        
                        # 프레임 스킵 방지 (30fps = 33.3ms 간격)
                        if frame_interval >= 0.020:  # 20ms 이상 간격이면 전송
                            # HTTP 멀티파트 응답
                            yield HEADER_PREFIX
                            yield str(frame_size).encode()
                            yield HEADER_SUFFIX
                            yield frame
                            yield FRAME_SUFFIX
                            
                            self.frame_count += 1
                            last_frame_time = current_time
                            
                            # 30fps용 주기적 가비지 컬렉션
                            if self.frame_count % self.gc_interval == 0:
                                gc.collect()
                                print(f"🧹 Camera {self.camera_id}: 30fps GC at frame {self.frame_count}")
                        else:
                            frame_skip_count += 1
                    
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
                
                # 30fps 성능 모니터링
                if self.frame_count > 0 and self.frame_count % 300 == 0:  # 10초마다
                    skip_rate = frame_skip_count / self.frame_count * 100
                    print(f"📊 Camera {self.camera_id}: 30fps stats - Frames: {self.frame_count}, Skip rate: {skip_rate:.1f}%")
                        
        except Exception as e:
            print(f"❌ 30fps streaming error for camera {self.camera_id}: {e}")
        finally:
            print(f"⏹️ Camera {self.camera_id} 30fps streaming ended after {self.frame_count} frames")
            
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
        print(f"🛑 Camera {self.camera_id} 30fps stopped and cleaned up")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 라이프사이클 관리"""
    print("🚀 30fps High-Performance Streaming Server Started")
    print("🎬 Smooth 30fps dual camera streaming with memory leak prevention")
    
    # 30fps용 가비지 컬렉션 최적화
    gc.set_threshold(800, 15, 15)  # 30fps용 조정
    
    streamers[0] = HighPerformance30FpsStreamer(0)
    streamers[1] = HighPerformance30FpsStreamer(1)
    
    yield
    
    # 정리
    for streamer in streamers.values():
        streamer.stop_stream()
    
    # 최종 메모리 정리
    gc.collect()
    print("👋 30fps optimized server stopped with full cleanup")

# FastAPI 앱
app = FastAPI(title="30fps High-Performance Streaming Server", lifespan=lifespan)

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
        <title>듀얼 카메라 스트리밍</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: 'SF Pro Display', Arial, sans-serif; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); color: #343a40; padding: 10px; margin: 0; min-height: 100vh; }
            .container { width: 100%; height: 100vh; margin: 0; padding: 0; display: flex; flex-direction: column; }
            h1 { text-align: center; font-size: 2.2em; margin: 10px 0; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); background: linear-gradient(45deg, #495057, #6c757d); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .fps-info { background: rgba(255,255,255,0.7); padding: 15px; border-radius: 10px; margin-bottom: 15px; backdrop-filter: blur(10px); text-align: center; border: 1px solid rgba(108, 117, 125, 0.2); }
            .fps-badge { display: inline-block; background: linear-gradient(135deg, #74b9ff, #0984e3); padding: 8px 20px; border-radius: 50px; font-size: 1em; font-weight: bold; margin: 0 8px; color: #fff; box-shadow: 0 4px 15px rgba(116, 185, 255, 0.4); }
            .camera-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; flex: 1; height: calc(100vh - 200px); }
            .camera-box { background: rgba(255,255,255,0.8); border-radius: 15px; padding: 15px; box-shadow: 0 8px 25px rgba(0,0,0,0.1); backdrop-filter: blur(15px); border: 1px solid rgba(108, 117, 125, 0.2); transition: transform 0.3s ease; display: flex; flex-direction: column; height: 100%; }
            .camera-box:hover { transform: translateY(-3px); box-shadow: 0 12px 35px rgba(0,0,0,0.15); }
            .video-container { background: #000; border-radius: 10px; overflow: hidden; border: 2px solid rgba(108, 117, 125, 0.3); position: relative; flex: 1; min-height: 0; }
            .video-stream { width: 100%; height: 100%; object-fit: cover; display: block; }
            .info { margin-top: 10px; text-align: center; font-size: 0.85em; opacity: 0.7; color: #6c757d; }
            .status { padding: 8px; border-radius: 6px; margin-top: 10px; text-align: center; font-weight: bold; font-size: 0.9em; }
            .status-online { background: linear-gradient(135deg, #2ecc71, #27ae60); color: #fff; box-shadow: 0 4px 15px rgba(46, 204, 113, 0.4); }
            .status-offline { background: linear-gradient(135deg, #e74c3c, #c0392b); color: #fff; box-shadow: 0 4px 15px rgba(231, 76, 60, 0.4); }
            .performance-info { background: rgba(255,255,255,0.6); padding: 10px; border-radius: 8px; margin-top: 10px; font-size: 0.8em; border: 1px solid rgba(108, 117, 125, 0.2); color: #495057; }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
            .loading { animation: pulse 1.5s infinite; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>듀얼 카메라</h1>
            
            <div class="fps-info">
                <div class="fps-badge">30 FPS</div>
                <div class="fps-badge">카메라0,1 영상</div>
                <div class="fps-badge">메모리 최적화</div>
            </div>
            
            <div class="camera-grid">
                <div class="camera-box">
                    <h3>📹 카메라 0번 (30fps)</h3>
                    <div class="video-container">
                        <img class="video-stream" id="cam0" src="/stream/0" alt="카메라 0번"
                             onload="setStatus(0, 'online')" onerror="setStatus(0, 'offline')">
                    </div>
                    <div class="info">640×480 @ 30fps | MJPEG 80% | 부드러운 영상</div>
                    <div class="status loading" id="status0">🔄 30fps 스트림 연결 중...</div>
                </div>
                
                <div class="camera-box">
                    <h3>📹 카메라 1번 (30fps)</h3>
                    <div class="video-container">
                        <img class="video-stream" id="cam1" src="/stream/1" alt="카메라 1번"
                             onload="setStatus(1, 'online')" onerror="setStatus(1, 'offline')">
                    </div>
                    <div class="info">640×480 @ 30fps | MJPEG 80% | 부드러운 영상</div>
                    <div class="status loading" id="status1">🔄 30fps 스트림 연결 중...</div>
                </div>
            </div>
            
            <div class="performance-info">
                <strong>🚀 30fps 고성능 최적화:</strong><br>
                • 적응적 청크 읽기로 프레임 드롭 방지<br>
                • 768KB 고정 버퍼 + 3개 버퍼 풀 순환 사용<br>
                • 인라인 JPEG 검색으로 지연 시간 최소화<br>
                • 1500프레임마다 자동 가비지 컬렉션
            </div>
        </div>
        
        <script>
            function setStatus(id, status) {
                const statusDiv = document.getElementById('status' + id);
                statusDiv.classList.remove('loading');
                
                if (status === 'online') {
                    statusDiv.className = 'status status-online';
                    statusDiv.innerHTML = '✅ 30fps 부드러운 스트리밍 중';
                } else {
                    statusDiv.className = 'status status-offline';
                    statusDiv.innerHTML = '❌ 재연결 중... (30fps 복구 중)';
                    
                    setTimeout(() => {
                        const img = document.getElementById('cam' + id);
                        img.src = '/stream/' + id + '?t=' + Date.now();
                        statusDiv.className = 'status loading';
                        statusDiv.innerHTML = '🔄 30fps 재연결 중...';
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
    """30fps 최적화된 MJPEG 스트리밍"""
    if camera_id not in streamers:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    return StreamingResponse(
        streamers[camera_id].get_optimized_30fps_frames(),
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
        "fps": "30",
        "optimization": "30fps-memory-leak-prevention-enabled"
    }

@app.get("/memory")
async def memory_info():
    """메모리 사용량 정보"""
    import psutil
    process = psutil.Process()
    return {
        "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
        "cpu_percent": process.cpu_percent(),
        "fps": "30",
        "frame_counts": {str(k): v.frame_count for k, v in streamers.items()},
        "optimization": "30fps-high-performance"
    }

if __name__ == "__main__":
    try:
        os.nice(-5)
    except PermissionError:
        pass
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")