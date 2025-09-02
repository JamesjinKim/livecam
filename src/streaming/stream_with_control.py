#!/usr/bin/env python3
"""
메모리 누수 방지 및 시스템 안정성 극대화 스트리밍 서버
- 제로 카피 설계
- 메모리 풀 관리
- 프로세스 라이프사이클 관리
- 시스템 리소스 모니터링
"""

import asyncio
import os
import subprocess
import signal
from pathlib import Path
from datetime import datetime
from typing import Generator, Optional, Dict, Any
import time
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import gc
from collections import deque
import json
import psutil
import mmap
import weakref
import resource

# 전역 변수
BASE_DIR = Path("/home/shinho/shinho/livecam")
VIDEO_DIR = BASE_DIR / "videos"
BLACKBOX_SCRIPT = BASE_DIR / "start_blackbox.sh"

# 스트리밍 관련
streaming_processes = {}
streamers = {}

# 블랙박스 관련
blackbox_processes = {}
blackbox_status = {
    "recording": False,
    "mode": None,
    "start_time": None,
    "pid": None,
    "scheduled_duration": None
}

# 시스템 모니터
system_monitor = None

class BlackboxConfig(BaseModel):
    """블랙박스 설정 모델"""
    mode: str = "dual-640"  # 기본값
    duration: Optional[int] = None  # 초 단위, None이면 무제한
    resolution: str = "640x480"
    cameras: str = "dual"  # single-cam0, single-cam1, dual

class RecordingStatus(BaseModel):
    """녹화 상태 모델"""
    is_recording: bool
    mode: Optional[str] = None
    start_time: Optional[str] = None
    duration_seconds: Optional[int] = None
    elapsed_seconds: Optional[int] = None
    files: list = []

class MemoryPool:
    """고정 크기 메모리 풀 - 메모리 누수 방지"""
    
    def __init__(self, buffer_size: int = 512 * 1024, pool_size: int = 4):
        self.buffer_size = buffer_size
        self.pool_size = pool_size
        self.available_buffers: deque = deque()
        self.used_buffers = set()
        
        # 사전 할당된 메모리 풀 생성
        self.master_buffer = bytearray(buffer_size * pool_size)
        for i in range(pool_size):
            start = i * buffer_size
            end = start + buffer_size
            buffer_view = memoryview(self.master_buffer[start:end])
            self.available_buffers.append(buffer_view)
        
        print(f"🏊 Memory pool initialized: {pool_size} buffers × {buffer_size//1024}KB")
    
    def get_buffer(self) -> memoryview:
        """버퍼 가져오기"""
        if self.available_buffers:
            buffer = self.available_buffers.popleft()
            self.used_buffers.add(id(buffer))
            return buffer
        else:
            # 풀이 고갈되면 강제 회수
            gc.collect()
            if self.available_buffers:
                buffer = self.available_buffers.popleft()
                self.used_buffers.add(id(buffer))
                return buffer
            else:
                raise MemoryError("Memory pool exhausted")
    
    def return_buffer(self, buffer: memoryview):
        """버퍼 반납"""
        buffer_id = id(buffer)
        if buffer_id in self.used_buffers:
            self.used_buffers.remove(buffer_id)
            self.available_buffers.append(buffer)
            # 버퍼 초기화 (보안)
            buffer[:] = b'\x00' * len(buffer)

class SystemMonitor:
    """시스템 리소스 모니터링"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss
        self.peak_memory = self.initial_memory
        self.oom_threshold = psutil.virtual_memory().total * 0.8  # 80% 임계점
        
    def check_memory_pressure(self) -> bool:
        """메모리 압박 상태 확인"""
        current_memory = self.process.memory_info().rss
        self.peak_memory = max(self.peak_memory, current_memory)
        
        # 시스템 메모리 사용률 확인
        system_memory = psutil.virtual_memory()
        if system_memory.used > self.oom_threshold:
            print(f"⚠️ Memory pressure detected: {system_memory.percent:.1f}%")
            return True
        return False
    
    def force_cleanup(self):
        """강제 메모리 정리"""
        gc.collect()
        # 메모리 압축 (Linux)
        try:
            with open('/proc/sys/vm/drop_caches', 'w') as f:
                f.write('1')
        except (PermissionError, FileNotFoundError):
            pass

class StableStreamer:
    """안정성 최우선 스트리밍 클래스"""
    
    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self.process = None
        self.is_streaming = False
        self.client_lock = threading.RLock()  # 재진입 가능 락
        
        # 메모리 풀 (부드러운 스트리밍을 위해 확장)
        self.memory_pool = MemoryPool(768 * 1024, 8)  # 8개 버퍼 × 768KB로 성능 최적화
        self.current_buffer = None
        self.buffer_pos = 0
        
        # 통계 (성능 최적화)
        self.frame_count = 0
        self.error_count = 0
        self.last_cleanup = time.time()
        self.cleanup_interval = 60.0  # 60초마다 정리 (빈도 감소)
        self.last_memory_check = time.time()
        self.memory_check_interval = 5.0  # 5초마다 메모리 체크
        
        # 프레임 검증
        self.min_frame_size = 1024  # 최소 프레임 크기
        self.max_frame_size = 256 * 1024  # 최대 프레임 크기
        
        # 프레임 타이밍
        self.min_frame_interval = 1.0 / 30.0  # 30fps 기준 최소 간격
        self.last_successful_frame = 0.0
        
        # 약한 참조로 순환 참조 방지
        self._weak_self = weakref.ref(self)
    
    def start_stream(self):
        """안정성 최우선 스트리밍 시작"""
        if self.is_streaming:
            return
        
        with self.client_lock:
            # 부드러운 스트리밍 최적화 설정 (시스템 부하 고려)
            cmd = [
                "rpicam-vid",
                "--camera", str(self.camera_id),
                "--width", "640", "--height", "480",
                "--timeout", "0", "--nopreview",
                "--codec", "mjpeg",
                "--quality", "80",  # 원래 품질로 복원
                "--framerate", "30",  # 원래 프레임레이트로 복원
                "--bitrate", "0",
                "--denoise", "cdn_fast",  # 안전한 디노이징 설정
                "--buffer-count", "4",  # 버퍼 최적화
                "--flush", "1",
                "--inline",  # 스트리밍 안정성 향상
                "--output", "-"
            ]
            
            # 프로세스 리소스 제한 (성능 최적화)
            def preexec():
                # 메모리 제한 (768MB로 확장)
                resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
                # CPU 우선순위 기본값 (더 높은 성능)
                os.nice(0)
            
            print(f"🎥 Starting stable camera {self.camera_id}")
            
            try:
                self.process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, 
                    bufsize=0,
                    preexec_fn=preexec
                )
                
                # 시작 검증
                time.sleep(1.0)
                if self.process.poll() is not None:
                    stdout, stderr = self.process.communicate()
                    print(f"❌ Camera {self.camera_id} failed: {stderr.decode('utf-8')}")
                    return
                
                self.is_streaming = True
                streaming_processes[self.camera_id] = self.process.pid
                print(f"✅ Camera {self.camera_id} stable streaming (PID: {self.process.pid})")
                
            except Exception as e:
                print(f"❌ Failed to start camera {self.camera_id}: {e}")
                self.error_count += 1
    
    def get_stable_frames(self) -> Generator[bytes, None, None]:
        """안정성 최우선 프레임 생성기"""
        if not self.is_streaming:
            self.start_stream()
            time.sleep(2.0)  # 충분한 초기화 시간
        
        if not self.process or self.process.poll() is not None:
            return
        
        # 메모리 풀에서 버퍼 할당
        try:
            self.current_buffer = self.memory_pool.get_buffer()
        except MemoryError:
            print(f"❌ Camera {self.camera_id}: Memory pool exhausted")
            return
        
        self.buffer_pos = 0
        
        # 상수 (끌김 방지 최적화)
        CHUNK_SIZE = 65536  # 64KB 청크로 증가 (끊김 방지)
        MIN_FRAME_INTERVAL = 1.0 / 30.0  # 30fps 기준 최소 간격
        frame_drop_prevention_time = time.time()
        last_successful_frame = time.time()
        
        try:
            while self.is_streaming and self.process and self.process.poll() is None:
                # 메모리 압박 확인 (빈도 최적화)
                current_time = time.time()
                if current_time - self.last_memory_check > self.memory_check_interval:
                    if system_monitor and system_monitor.check_memory_pressure():
                        system_monitor.force_cleanup()
                        time.sleep(0.05)  # 더 짧은 휴식
                    self.last_memory_check = current_time
                
                # 주기적 정리 (빈도 최적화)
                if current_time - self.last_cleanup > self.cleanup_interval:
                    self._periodic_cleanup()
                    self.last_cleanup = current_time
                
                # 데이터 읽기
                try:
                    chunk = self.process.stdout.read(CHUNK_SIZE)
                    if not chunk:
                        # 적응적 대기 - CPU 부하에 따라 조정
                        wait_time = 0.01 if current_time - last_successful_frame > 0.1 else 0.005
                        time.sleep(wait_time)
                        continue
                    last_successful_frame = current_time
                except (BrokenPipeError, OSError) as e:
                    print(f"❌ Camera {self.camera_id}: Pipe error - {e}")
                    break
                
                # 버퍼 오버플로우 방지
                if self.buffer_pos + len(chunk) > len(self.current_buffer):
                    # 앞쪽 절반 제거
                    keep_size = len(self.current_buffer) // 2
                    if self.buffer_pos > keep_size:
                        self.current_buffer[:keep_size] = self.current_buffer[self.buffer_pos - keep_size:self.buffer_pos]
                        self.buffer_pos = keep_size
                    else:
                        # 버퍼 전체 초기화
                        self.buffer_pos = 0
                
                # 데이터 추가 (제로 카피)
                end_pos = min(self.buffer_pos + len(chunk), len(self.current_buffer))
                actual_size = end_pos - self.buffer_pos
                self.current_buffer[self.buffer_pos:end_pos] = chunk[:actual_size]
                self.buffer_pos = end_pos
                
                # 프레임 검색 (제로 카피)
                yield from self._extract_frames()
                
        except Exception as e:
            print(f"❌ Stable streaming error for camera {self.camera_id}: {e}")
            self.error_count += 1
        finally:
            # 메모리 풀에 버퍼 반납
            if self.current_buffer:
                self.memory_pool.return_buffer(self.current_buffer)
                self.current_buffer = None
            print(f"⏹️ Camera {self.camera_id} streaming ended (frames: {self.frame_count}, errors: {self.error_count})")
    
    def _extract_frames(self) -> Generator[bytes, None, None]:
        """제로 카피 프레임 추출"""
        search_pos = 0
        
        while search_pos < self.buffer_pos - 10:
            # JPEG 시작 찾기
            start_idx = -1
            for i in range(search_pos, self.buffer_pos - 1):
                if self.current_buffer[i] == 0xFF and self.current_buffer[i + 1] == 0xD8:
                    start_idx = i
                    break
            
            if start_idx == -1:
                break
            
            # JPEG 끝 찾기
            end_idx = -1
            for i in range(start_idx + 2, self.buffer_pos - 1):
                if self.current_buffer[i] == 0xFF and self.current_buffer[i + 1] == 0xD9:
                    end_idx = i + 1
                    break
            
            if end_idx == -1:
                # 불완전한 프레임 - 다음 청크 대기
                if start_idx > 0:
                    remaining = self.buffer_pos - start_idx
                    self.current_buffer[:remaining] = self.current_buffer[start_idx:self.buffer_pos]
                    self.buffer_pos = remaining
                break
            
            # 프레임 크기 검증
            frame_size = end_idx - start_idx + 1
            if self.min_frame_size <= frame_size <= self.max_frame_size:
                # 제로 카피 프레임 추출
                frame_view = self.current_buffer[start_idx:end_idx + 1]
                frame = bytes(frame_view)  # 필요시에만 복사
                
                # HTTP 멀티파트 응답 (끌김 방지 최적화)
                frame_time = time.time()
                if frame_time - self.last_successful_frame >= self.min_frame_interval:
                    yield b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
                    yield str(frame_size).encode()
                    yield b'\r\n\r\n'
                    yield frame
                    yield b'\r\n'
                    self.last_successful_frame = frame_time
                    self.frame_count += 1
                
                self.frame_count += 1
            
            # 처리된 부분 제거
            remaining = self.buffer_pos - (end_idx + 1)
            if remaining > 0:
                self.current_buffer[:remaining] = self.current_buffer[end_idx + 1:self.buffer_pos]
                self.buffer_pos = remaining
                search_pos = 0
            else:
                self.buffer_pos = 0
                break
    
    def _periodic_cleanup(self):
        """주기적 정리 작업"""
        gc.collect()
        if self.frame_count % 1500 == 0:  # 빈도 조정
            fps_estimate = self.frame_count / max((time.time() - self.last_cleanup + 60), 1) * 60
            print(f"🧹 Camera {self.camera_id}: Cleanup (frames: {self.frame_count}, ~{fps_estimate:.1f}fps)")
    
    def stop_stream(self):
        """안전한 스트리밍 중지"""
        self.is_streaming = False
        
        with self.client_lock:
            if self.process:
                try:
                    # 정중한 종료 시도
                    self.process.send_signal(signal.SIGTERM)
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 강제 종료
                    self.process.kill()
                    self.process.wait(timeout=2)
                except Exception as e:
                    print(f"⚠️ Error stopping camera {self.camera_id}: {e}")
                finally:
                    self.process = None
            
            if self.camera_id in streaming_processes:
                del streaming_processes[self.camera_id]
            
            # 메모리 정리
            if self.current_buffer:
                self.memory_pool.return_buffer(self.current_buffer)
                self.current_buffer = None
            
            gc.collect()
            print(f"🛑 Camera {self.camera_id} safely stopped")

# 블랙박스 제어 함수들
def start_blackbox_recording(config: BlackboxConfig) -> Dict[str, Any]:
    """블랙박스 녹화 시작"""
    global blackbox_status, blackbox_processes
    
    if blackbox_status["recording"]:
        return {"error": "Already recording"}
    
    # 모드 결정
    if config.cameras == "dual":
        if config.resolution == "640x480":
            mode = "dual-640"
        elif config.resolution == "1280x720":
            mode = "dual-720p"
        elif config.resolution == "1920x1080":
            mode = "dual-1080p"
        else:
            mode = "dual-640"
    else:
        cam_num = "0" if "cam0" in config.cameras else "1"
        if config.resolution == "640x480":
            mode = f"cam{cam_num}-640"
        elif config.resolution == "1280x720":
            mode = f"cam{cam_num}-720p"
        elif config.resolution == "1920x1080":
            mode = f"cam{cam_num}-1080p"
        else:
            mode = f"cam{cam_num}-640"
    
    # 블랙박스 스크립트 실행
    try:
        process = subprocess.Popen(
            [str(BLACKBOX_SCRIPT), mode],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # 프로세스 그룹 생성
        )
        
        blackbox_processes["main"] = process
        blackbox_status.update({
            "recording": True,
            "mode": mode,
            "start_time": datetime.now().isoformat(),
            "pid": process.pid,
            "scheduled_duration": config.duration
        })
        
        # 시간 제한이 있으면 타이머 설정
        if config.duration:
            def stop_after_duration():
                time.sleep(config.duration)
                if blackbox_status["recording"]:
                    stop_blackbox_recording()
            
            timer_thread = threading.Thread(target=stop_after_duration)
            timer_thread.daemon = True
            timer_thread.start()
        
        return {
            "success": True,
            "mode": mode,
            "pid": process.pid,
            "duration": config.duration
        }
        
    except Exception as e:
        return {"error": str(e)}

def stop_blackbox_recording() -> Dict[str, Any]:
    """블랙박스 녹화 중지"""
    global blackbox_status, blackbox_processes
    
    if not blackbox_status["recording"]:
        return {"error": "Not recording"}
    
    try:
        if "main" in blackbox_processes:
            process = blackbox_processes["main"]
            # SIGINT 전송 (정상 종료)
            os.killpg(os.getpgid(process.pid), signal.SIGINT)
            
            # 종료 대기
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # 강제 종료
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            
            del blackbox_processes["main"]
        
        # 상태 초기화
        end_time = datetime.now()
        start_time = datetime.fromisoformat(blackbox_status["start_time"])
        duration = (end_time - start_time).total_seconds()
        
        blackbox_status.update({
            "recording": False,
            "mode": None,
            "start_time": None,
            "pid": None,
            "scheduled_duration": None
        })
        
        return {
            "success": True,
            "duration_seconds": int(duration)
        }
        
    except Exception as e:
        return {"error": str(e)}

def get_recording_status() -> RecordingStatus:
    """현재 녹화 상태 조회"""
    global blackbox_status
    
    status = RecordingStatus(
        is_recording=blackbox_status["recording"],
        mode=blackbox_status["mode"],
        start_time=blackbox_status["start_time"],
        duration_seconds=blackbox_status["scheduled_duration"]
    )
    
    if blackbox_status["recording"] and blackbox_status["start_time"]:
        start_time = datetime.fromisoformat(blackbox_status["start_time"])
        elapsed = (datetime.now() - start_time).total_seconds()
        status.elapsed_seconds = int(elapsed)
    
    # 최근 녹화 파일 목록
    try:
        video_files = []
        for resolution_dir in VIDEO_DIR.glob("*"):
            if resolution_dir.is_dir():
                for cam_dir in resolution_dir.glob("cam*"):
                    if cam_dir.is_dir():
                        for video_file in sorted(cam_dir.glob("*.mp4"), 
                                                key=lambda x: x.stat().st_mtime, 
                                                reverse=True)[:5]:
                            video_files.append({
                                "path": str(video_file.relative_to(BASE_DIR)),
                                "size": video_file.stat().st_size,
                                "modified": datetime.fromtimestamp(
                                    video_file.stat().st_mtime
                                ).isoformat()
                            })
        status.files = video_files[:10]  # 최근 10개만
    except Exception as e:
        print(f"Error getting video files: {e}")
    
    return status

# FastAPI 앱 설정
@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 라이프사이클 관리"""
    global system_monitor
    
    print("🚀 Stable Streaming Server Started")
    print("🛡️ Memory leak prevention and system stability optimized")
    
    # 시스템 모니터 시작
    system_monitor = SystemMonitor()
    
    # 가비지 컬렉션 튜닝 (성능 최적화)
    gc.set_threshold(1200, 15, 15)  # 더 효율적인 임계점
    
    # 스트리머 생성
    streamers[0] = StableStreamer(0)
    streamers[1] = StableStreamer(1)
    
    yield
    
    # 정리
    if blackbox_status["recording"]:
        stop_blackbox_recording()
    
    for streamer in streamers.values():
        streamer.stop_stream()
    
    # 최종 정리
    gc.collect()
    system_monitor = None
    print("👋 Stable server stopped with complete cleanup")

app = FastAPI(
    title="Blackbox Control & Streaming Server",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 엔드포인트
@app.post("/api/blackbox/start")
async def start_recording(config: BlackboxConfig):
    """블랙박스 녹화 시작"""
    result = start_blackbox_recording(config)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/blackbox/stop")
async def stop_recording():
    """블랙박스 녹화 중지"""
    result = stop_blackbox_recording()
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/api/blackbox/status")
async def get_status():
    """녹화 상태 조회"""
    return get_recording_status()

@app.get("/api/system/info")
async def get_system_info():
    """시스템 정보 조회"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2)
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/stream/{camera_id}")
async def stream_camera(camera_id: int):
    """카메라 스트리밍"""
    if camera_id not in streamers:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    return StreamingResponse(
        streamers[camera_id].get_stable_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache", 
            "Expires": "0", 
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx 버퍼링 방지
        }
    )

@app.get("/")
async def root():
    """메인 웹 UI"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>블랙박스 제어 시스템</title>
        <meta charset="UTF-8">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            .header {
                background: white;
                border-radius: 15px;
                padding: 20px 30px;
                margin-bottom: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            .header h1 {
                color: #333;
                font-size: 28px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .control-panel {
                background: white;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            .controls {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }
            .control-group {
                display: flex;
                flex-direction: column;
                gap: 5px;
            }
            .control-group label {
                font-size: 12px;
                color: #666;
                font-weight: 600;
                text-transform: uppercase;
            }
            .control-group select, .control-group input {
                padding: 10px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 14px;
                transition: all 0.3s;
            }
            .control-group select:focus, .control-group input:focus {
                outline: none;
                border-color: #667eea;
            }
            .button-group {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }
            .btn {
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .btn-start {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .btn-start:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            .btn-stop {
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                color: white;
            }
            .btn-stop:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(245, 87, 108, 0.4);
            }
            .btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none !important;
            }
            .status-panel {
                background: white;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            .status-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
            }
            .status-item {
                padding: 15px;
                background: #f8f9fa;
                border-radius: 10px;
                border-left: 4px solid #667eea;
            }
            .status-item h3 {
                font-size: 12px;
                color: #666;
                margin-bottom: 5px;
                text-transform: uppercase;
            }
            .status-item .value {
                font-size: 20px;
                font-weight: bold;
                color: #333;
            }
            .recording {
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            .video-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
                gap: 20px;
            }
            .video-container {
                background: white;
                border-radius: 15px;
                padding: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            .video-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
                padding: 10px;
                background: #f8f9fa;
                border-radius: 8px;
            }
            .video-title {
                font-weight: 600;
                color: #333;
            }
            .status-badge {
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
                background: #10b981;
                color: white;
            }
            video, img {
                width: 100%;
                border-radius: 10px;
                background: #000;
                transform: scaleX(-1);  /* 좌우 반전 */
            }
            .files-panel {
                background: white;
                border-radius: 15px;
                padding: 25px;
                margin-top: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                max-height: 300px;
                overflow-y: auto;
            }
            .file-list {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .file-item {
                padding: 12px;
                background: #f8f9fa;
                border-radius: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                transition: all 0.3s;
            }
            .file-item:hover {
                background: #e9ecef;
            }
            .file-name {
                font-size: 14px;
                color: #333;
                font-weight: 500;
            }
            .file-size {
                font-size: 12px;
                color: #666;
            }
            .system-info {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 10px;
                margin-top: 15px;
            }
            .system-stat {
                text-align: center;
            }
            .system-stat .label {
                font-size: 11px;
                color: #666;
                text-transform: uppercase;
                margin-bottom: 5px;
            }
            .system-stat .value {
                font-size: 18px;
                font-weight: bold;
                color: #333;
            }
            .progress-bar {
                width: 100%;
                height: 4px;
                background: #e0e0e0;
                border-radius: 2px;
                margin-top: 5px;
                overflow: hidden;
            }
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea, #764ba2);
                transition: width 0.3s;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎥 라즈베리파이 5 블랙박스 제어 시스템</h1>
            </div>
            
            <div class="control-panel">
                <h2 style="margin-bottom: 20px; color: #333;">녹화 제어</h2>
                <div class="controls">
                    <div class="control-group">
                        <label>카메라 선택</label>
                        <select id="cameras">
                            <option value="dual">듀얼 카메라</option>
                            <option value="single-cam0">카메라 0번만</option>
                            <option value="single-cam1">카메라 1번만</option>
                        </select>
                    </div>
                    <div class="control-group">
                        <label>해상도</label>
                        <select id="resolution">
                            <option value="640x480">640x480 (VGA)</option>
                            <option value="1280x720">1280x720 (HD)</option>
                            <option value="1920x1080">1920x1080 (Full HD)</option>
                        </select>
                    </div>
                    <div class="control-group">
                        <label>녹화 시간 (초, 0=무제한)</label>
                        <input type="number" id="duration" min="0" value="0" placeholder="0">
                    </div>
                </div>
                <div class="button-group">
                    <button id="startBtn" class="btn btn-start" onclick="startRecording()">
                        ▶️ 녹화 시작
                    </button>
                    <button id="stopBtn" class="btn btn-stop" onclick="stopRecording()" disabled>
                        ⏹️ 녹화 중지
                    </button>
                </div>
            </div>
            
            <div class="status-panel">
                <h2 style="margin-bottom: 20px; color: #333;">상태 정보</h2>
                <div class="status-grid">
                    <div class="status-item">
                        <h3>녹화 상태</h3>
                        <div class="value" id="recordingStatus">대기중</div>
                    </div>
                    <div class="status-item">
                        <h3>녹화 모드</h3>
                        <div class="value" id="recordingMode">-</div>
                    </div>
                    <div class="status-item">
                        <h3>경과 시간</h3>
                        <div class="value" id="elapsedTime">00:00:00</div>
                    </div>
                    <div class="status-item">
                        <h3>예정 시간</h3>
                        <div class="value" id="scheduledDuration">무제한</div>
                    </div>
                </div>
                
                <div class="system-info" id="systemInfo">
                    <div class="system-stat">
                        <div class="label">CPU</div>
                        <div class="value" id="cpuUsage">0%</div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="cpuBar" style="width: 0%"></div>
                        </div>
                    </div>
                    <div class="system-stat">
                        <div class="label">메모리</div>
                        <div class="value" id="memUsage">0%</div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="memBar" style="width: 0%"></div>
                        </div>
                    </div>
                    <div class="system-stat">
                        <div class="label">디스크</div>
                        <div class="value" id="diskUsage">0%</div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="diskBar" style="width: 0%"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="video-grid">
                <div class="video-container">
                    <div class="video-header">
                        <span class="video-title">📷 카메라 0 (전방)</span>
                        <span class="status-badge">LIVE</span>
                    </div>
                    <img src="/stream/0" alt="Camera 0" id="cam0Stream" onload="handleStreamLoad(0)" onerror="handleStreamError(0)">
                </div>
                <div class="video-container">
                    <div class="video-header">
                        <span class="video-title">📷 카메라 1 (후방)</span>
                        <span class="status-badge">LIVE</span>
                    </div>
                    <img src="/stream/1" alt="Camera 1" id="cam1Stream" onload="handleStreamLoad(1)" onerror="handleStreamError(1)">
                </div>
            </div>
            
            <div class="files-panel">
                <h2 style="margin-bottom: 15px; color: #333;">최근 녹화 파일</h2>
                <div class="file-list" id="fileList">
                    <div class="file-item">
                        <span class="file-name">파일 목록을 불러오는 중...</span>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            let isRecording = false;
            let statusInterval = null;
            let systemInterval = null;
            
            async function startRecording() {
                const config = {
                    cameras: document.getElementById('cameras').value,
                    resolution: document.getElementById('resolution').value,
                    duration: parseInt(document.getElementById('duration').value) || 0
                };
                
                if (config.duration > 0) {
                    config.duration = config.duration;
                } else {
                    config.duration = null;
                }
                
                try {
                    const response = await fetch('/api/blackbox/start', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(config)
                    });
                    
                    if (response.ok) {
                        const result = await response.json();
                        isRecording = true;
                        updateUI();
                        updateStatus();
                    } else {
                        const error = await response.json();
                        alert('녹화 시작 실패: ' + error.detail);
                    }
                } catch (error) {
                    alert('오류 발생: ' + error);
                }
            }
            
            async function stopRecording() {
                try {
                    const response = await fetch('/api/blackbox/stop', {
                        method: 'POST'
                    });
                    
                    if (response.ok) {
                        const result = await response.json();
                        isRecording = false;
                        updateUI();
                        updateStatus();
                        alert(`녹화 중지됨 (${result.duration_seconds}초 녹화)`);
                    } else {
                        const error = await response.json();
                        alert('녹화 중지 실패: ' + error.detail);
                    }
                } catch (error) {
                    alert('오류 발생: ' + error);
                }
            }
            
            async function updateStatus() {
                try {
                    const response = await fetch('/api/blackbox/status');
                    const status = await response.json();
                    
                    isRecording = status.is_recording;
                    
                    document.getElementById('recordingStatus').textContent = 
                        status.is_recording ? '🔴 녹화중' : '⚪ 대기중';
                    document.getElementById('recordingStatus').className = 
                        status.is_recording ? 'value recording' : 'value';
                    
                    document.getElementById('recordingMode').textContent = 
                        status.mode || '-';
                    
                    if (status.elapsed_seconds) {
                        const hours = Math.floor(status.elapsed_seconds / 3600);
                        const minutes = Math.floor((status.elapsed_seconds % 3600) / 60);
                        const seconds = status.elapsed_seconds % 60;
                        document.getElementById('elapsedTime').textContent = 
                            `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
                    } else {
                        document.getElementById('elapsedTime').textContent = '00:00:00';
                    }
                    
                    document.getElementById('scheduledDuration').textContent = 
                        status.duration_seconds ? `${status.duration_seconds}초` : '무제한';
                    
                    // 파일 목록 업데이트
                    if (status.files && status.files.length > 0) {
                        const fileList = document.getElementById('fileList');
                        fileList.innerHTML = status.files.map(file => `
                            <div class="file-item">
                                <span class="file-name">${file.path.split('/').pop()}</span>
                                <span class="file-size">${(file.size / 1024 / 1024).toFixed(2)} MB</span>
                            </div>
                        `).join('');
                    }
                    
                    updateUI();
                } catch (error) {
                    console.error('상태 업데이트 오류:', error);
                }
            }
            
            async function updateSystemInfo() {
                try {
                    const response = await fetch('/api/system/info');
                    const info = await response.json();
                    
                    document.getElementById('cpuUsage').textContent = `${info.cpu_percent.toFixed(1)}%`;
                    document.getElementById('cpuBar').style.width = `${info.cpu_percent}%`;
                    
                    document.getElementById('memUsage').textContent = `${info.memory_percent.toFixed(1)}%`;
                    document.getElementById('memBar').style.width = `${info.memory_percent}%`;
                    
                    document.getElementById('diskUsage').textContent = `${info.disk_percent.toFixed(1)}%`;
                    document.getElementById('diskBar').style.width = `${info.disk_percent}%`;
                } catch (error) {
                    console.error('시스템 정보 업데이트 오류:', error);
                }
            }
            
            function updateUI() {
                document.getElementById('startBtn').disabled = isRecording;
                document.getElementById('stopBtn').disabled = !isRecording;
                document.getElementById('cameras').disabled = isRecording;
                document.getElementById('resolution').disabled = isRecording;
                document.getElementById('duration').disabled = isRecording;
            }
            
            // 초기화
            window.onload = function() {
                updateStatus();
                updateSystemInfo();
                
                // 주기적 업데이트
                statusInterval = setInterval(updateStatus, 2000);
                systemInterval = setInterval(updateSystemInfo, 5000);
            }
            
            // 스트리밍 끊김 방지 함수들
            let streamRetryCount = { 0: 0, 1: 0 };
            let lastStreamUpdate = { 0: Date.now(), 1: Date.now() };
            
            function handleStreamLoad(cameraId) {
                streamRetryCount[cameraId] = 0;
                lastStreamUpdate[cameraId] = Date.now();
                console.log(`Camera ${cameraId} stream loaded successfully`);
            }
            
            function handleStreamError(cameraId) {
                streamRetryCount[cameraId]++;
                console.log(`Camera ${cameraId} stream error, retry count: ${streamRetryCount[cameraId]}`);
                
                if (streamRetryCount[cameraId] < 5) {
                    setTimeout(() => {
                        const img = document.getElementById(`cam${cameraId}Stream`);
                        if (img) {
                            img.src = `/stream/${cameraId}?t=${Date.now()}`;
                        }
                    }, Math.min(1000 * streamRetryCount[cameraId], 5000));
                }
            }
            
            // 스트리밍 건강성 체크 (10초마다)
            function checkStreamHealth() {
                const now = Date.now();
                [0, 1].forEach(cameraId => {
                    const timeSinceUpdate = now - lastStreamUpdate[cameraId];
                    if (timeSinceUpdate > 15000) { // 15초 이상 업데이트 없음
                        console.log(`Camera ${cameraId} stream seems stuck, refreshing...`);
                        const img = document.getElementById(`cam${cameraId}Stream`);
                        if (img) {
                            img.src = `/stream/${cameraId}?t=${now}`;
                            lastStreamUpdate[cameraId] = now;
                        }
                    }
                });
            }
            
            window.onbeforeunload = function() {
                if (statusInterval) clearInterval(statusInterval);
                if (systemInterval) clearInterval(systemInterval);
            }
            
            // 스트림 건강성 체크 시작
            setInterval(checkStreamHealth, 10000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/api/cleanup")
async def manual_cleanup(background_tasks: BackgroundTasks):
    """수동 메모리 정리"""
    def cleanup():
        if system_monitor:
            system_monitor.force_cleanup()
        gc.collect()
    
    background_tasks.add_task(cleanup)
    return {"status": "cleanup_scheduled"}

@app.get("/api/health")
async def health_check():
    """헬스 체크"""
    if system_monitor:
        memory_pressure = system_monitor.check_memory_pressure()
        cpu_percent = system_monitor.process.cpu_percent()
        
        return {
            "status": "healthy" if not memory_pressure and cpu_percent < 80 else "warning",
            "memory_pressure": memory_pressure,
            "cpu_percent": cpu_percent,
            "uptime": time.time() - system_monitor.process.create_time()
        }
    return {"status": "unknown"}

if __name__ == "__main__":
    # 프로세스 우선순위 설정
    try:
        os.nice(0)  # 기본 우선순위
    except PermissionError:
        pass
    
    uvicorn.run(app, host="192.168.0.34", port=8000, log_level="warning")