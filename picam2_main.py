#!/usr/bin/env python3
"""
cctv_main.py 구조 기반 + Picamera2 교체 버전
기존 안정적인 구조 유지, rpicam-vid만 Picamera2로 교체
"""

import asyncio
import signal
import sys
import time
import threading
import atexit
from typing import Optional, Dict, Any
import io
from collections import deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, Response
import uvicorn

# Picamera2 imports
try:
    from picamera2 import Picamera2
except ImportError as e:
    print(f"[ERROR] Picamera2 not installed: {e}")
    print("[INSTALL] Run: sudo apt install -y python3-picamera2")
    sys.exit(1)

# 간단한 로깅
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def log_execution_time(name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            logger.info(f"[TIMING] {name}: {elapsed:.3f}s")
            return result
        return wrapper
    return decorator

app = FastAPI()

# 전역 변수 (기존 cctv_main.py와 동일)
current_camera = 0
current_resolution = "640x480"  # 기본 해상도
camera_instances = {}  # rpicam-vid 프로세스 → Picamera2 인스턴스
stream_stats = {
    0: {"frame_count": 0, "avg_frame_size": 0, "fps": 0, "last_update": 0},
    1: {"frame_count": 0, "avg_frame_size": 0, "fps": 0, "last_update": 0}
}

# 단일 클라이언트 제한
active_clients = set()
MAX_CLIENTS = 1

# 해상도 설정
RESOLUTIONS = {
    "640x480": {"width": 640, "height": 480, "name": "480p"},
    "1280x720": {"width": 1280, "height": 720, "name": "720p"}
}

@log_execution_time("카메라_스트림_시작")
def start_camera_stream(camera_id: int, resolution: str = None):
    """카메라 스트리밍 시작 - Picamera2 버전"""
    logger.info(f"[START] 카메라 {camera_id} 스트리밍 시작 요청 (해상도: {resolution or current_resolution})")
    
    if camera_id in camera_instances:
        logger.info(f"기존 카메라 {camera_id} 인스턴스 종료 중...")
        stop_camera_stream(camera_id)
    
    # 해상도 설정
    if resolution is None:
        resolution = current_resolution
    
    res_config = RESOLUTIONS.get(resolution, RESOLUTIONS["640x480"])
    width = res_config["width"]
    height = res_config["height"]
    
    try:
        # Picamera2 인스턴스 생성
        picam2 = Picamera2(camera_num=camera_id)
        
        # Pi5 최적화 설정
        config = picam2.create_video_configuration(
            main={
                "size": (width, height),
                "format": "YUV420"  # Pi5 GPU 최적화 포맷
            },
            buffer_count=4,  # Pi5 메모리 대역폭 활용
            queue=False      # 레이턴시 최소화
        )
        
        # Pi5 PiSP 설정
        picam2.set_controls({
            "AwbEnable": True,           # 자동 화이트밸런스
            "AeEnable": True,            # 자동 노출
            "NoiseReductionMode": 2,     # 하드웨어 노이즈 감소
            "Saturation": 1.1,           # 색상 포화도
            "Brightness": 0.0,           # 기본 밝기
            "Contrast": 1.0,             # 기본 대비
        })
        
        picam2.configure(config)
        picam2.start()
        
        # 안정화 대기
        time.sleep(0.5)
        
        camera_instances[camera_id] = picam2
        logger.info(f"[OK] Camera {camera_id} started at {resolution} (Picamera2)")
        print(f"[OK] Camera {camera_id} started at {resolution} (Picamera2)")
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to start camera {camera_id}: {e}")
        print(f"[ERROR] Failed to start camera {camera_id}: {e}")
        return False

@log_execution_time("카메라_스트림_중지")
def stop_camera_stream(camera_id: int):
    """카메라 스트리밍 중지 - Picamera2 버전"""
    if camera_id in camera_instances:
        logger.info(f"[STOP] 카메라 {camera_id} 스트림 중지 시작")
        try:
            picam2 = camera_instances[camera_id]
            
            # Picamera2 정리
            if picam2.started:
                picam2.stop()
            picam2.close()
            
            # 인스턴스 제거
            del camera_instances[camera_id]
            
            # 통계 초기화
            stream_stats[camera_id] = {"frame_count": 0, "avg_frame_size": 0, "fps": 0, "last_update": 0}
            
            # 가비지 컬렉션
            import gc
            gc.collect()
            
            logger.info(f"[STOP] Camera {camera_id} stopped and cleaned (Picamera2)")
            print(f"[STOP] Camera {camera_id} stopped and cleaned (Picamera2)")
            
        except Exception as e:
            logger.error(f"[ERROR] Error stopping camera {camera_id}: {e}")
            print(f"[ERROR] Error stopping camera {camera_id}: {e}")
    else:
        logger.warning(f"카메라 {camera_id} 인스턴스가 존재하지 않음")

def generate_mjpeg_stream(camera_id: int, client_ip: str = None):
    """최적화된 MJPEG 스트림 생성 - Picamera2 버전"""
    if camera_id not in camera_instances:
        if not start_camera_stream(camera_id):
            return
    
    picam2 = camera_instances[camera_id]
    
    if not picam2 or not picam2.started:
        logger.error(f"[STREAM] Camera {camera_id} not ready")
        return
    
    # 현재 해상도에 따른 동적 설정 (기존과 동일)
    is_720p = current_resolution == "1280x720"
    
    if is_720p:
        frame_min_size = 5000
        frame_max_size = 500000
        quality = 85
    else:
        frame_min_size = 2000
        frame_max_size = 200000
        quality = 80
    
    frame_count = 0
    total_frame_size = 0
    start_time = time.time()
    last_fps_update = start_time
    last_gc_time = start_time
    
    logger.info(f"[STREAM] Starting {current_resolution} stream for camera {camera_id} (Picamera2)")
    print(f"[STREAM] Starting {current_resolution} stream for camera {camera_id} (Picamera2)")
    
    # 클라이언트 등록
    if client_ip:
        active_clients.add(client_ip)
        logger.info(f"[CLIENT] Client connected: {client_ip} (Total: {len(active_clients)})")
        print(f"[CLIENT] Client connected: {client_ip} (Total: {len(active_clients)})")
    
    try:
        while True:
            try:
                # Picamera2로 JPEG 프레임 캡처 (quality 파라미터 제거)
                stream = io.BytesIO()
                picam2.capture_file(stream, format='jpeg')
                frame_data = stream.getvalue()
                stream.close()
                
                if not frame_data:
                    print(f"[WARN] No data from camera {camera_id}, stream ending")
                    break
                
                frame_size = len(frame_data)
                
                # 프레임 크기 검증 (기존과 동일)
                if frame_min_size < frame_size < frame_max_size:
                    try:
                        yield b'--frame\r\n'
                        yield b'Content-Type: image/jpeg\r\n'
                        yield f'Content-Length: {frame_size}\r\n\r\n'.encode()
                        yield frame_data
                        yield b'\r\n'
                        
                        frame_count += 1
                        total_frame_size += frame_size
                        
                        # 프레임 카운터 자동 리셋 (기존과 동일)
                        if frame_count >= 100000:
                            print(f"[RESET] Auto-reset: Frame counter reached 100K, resetting for memory stability")
                            frame_count = 1
                            total_frame_size = frame_size
                            start_time = time.time()
                            last_fps_update = start_time
                            last_gc_time = start_time
                            stream_stats[camera_id] = {"frame_count": 1, "avg_frame_size": frame_size, "fps": 30.0, "last_update": start_time}
                        
                        # FPS 및 통계 업데이트 (기존과 동일)
                        current_time = time.time()
                        if current_time - last_fps_update >= 1.0:
                            elapsed = current_time - start_time
                            fps = frame_count / elapsed if elapsed > 0 else 0
                            avg_size = total_frame_size // frame_count if frame_count > 0 else 0
                            
                            stream_stats[camera_id].update({
                                "frame_count": frame_count,
                                "avg_frame_size": avg_size,
                                "fps": round(fps, 1),
                                "last_update": current_time
                            })
                            last_fps_update = current_time
                        
                        # 주기적 가비지 컬렉션 (기존과 동일)
                        if current_time - last_gc_time > 30:
                            import gc
                            gc.collect()
                            last_gc_time = current_time
                        
                        if frame_count % 150 == 0:  # 150프레임마다 로그
                            print(f"[STATS] Camera {camera_id} ({current_resolution}): {frame_count} frames, {stream_stats[camera_id]['fps']} fps, avg {frame_size//1024}KB")
                    
                    except Exception as e:
                        print(f"[ERROR] Frame yield error for camera {camera_id}: {e}")
                        break
                else:
                    if frame_count % 100 == 0 and frame_size > 0:
                        print(f"[WARN] Frame size {frame_size//1024}KB out of range ({frame_min_size//1024}-{frame_max_size//1024}KB)")
                        
            except Exception as e:
                print(f"[ERROR] Frame capture error for camera {camera_id}: {e}")
                break
                
    except Exception as e:
        print(f"[ERROR] Stream error for camera {camera_id}: {e}")
    finally:
        # 클라이언트 연결 종료
        if client_ip and client_ip in active_clients:
            active_clients.remove(client_ip)
            print(f"[CLIENT] Client disconnected: {client_ip} (Remaining: {len(active_clients)})")
        print(f"[END] Camera {camera_id} ({current_resolution}) stream ended (total: {frame_count} frames)")
        # 스트림 종료 시 통계 초기화
        if camera_id in stream_stats:
            stream_stats[camera_id]["last_update"] = 0

# 기존 cctv_main.py의 웹 인터페이스 그대로 사용
@app.get("/")
async def root():
    """메인 페이지 - 기존 인터페이스 + Picamera2 표시"""
    # 기존 HTML에서 제목만 수정
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Picamera2 듀얼 카메라 토글</title>
        <meta charset="UTF-8">
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 0; padding: 0;
                background: #f5f5f5;
                text-align: center;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
            }
            .container {
                flex: 1;
                display: flex;
                flex-direction: column;
                background: white;
                padding: 15px;
                height: 100vh;
                box-sizing: border-box;
            }
            h1 { color: #333; margin-bottom: 20px; }
            .badge {
                background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 0.8em;
                font-weight: bold;
                margin-left: 10px;
                display: inline-block;
            }
            .video-container {
                flex: 1;
                display: flex;
                justify-content: center;
                align-items: center;
                border: 2px solid #ddd;
                border-radius: 8px;
                overflow: hidden;
                margin: 10px 0;
                min-height: 60vh;
            }
            .video-container.resolution-640 {
                max-height: 55vh;
                max-width: 70%;
                margin: 10px auto;
            }
            .video-container.resolution-720 {
                max-height: 75vh;
                max-width: 95%;
                margin: 10px auto;
            }
            img { 
                width: 100%; 
                height: 100%;
                object-fit: contain;
                display: block;
            }
            .controls {
                margin: 10px 0;
                display: flex;
                gap: 20px;
                justify-content: center;
                flex-wrap: wrap;
                flex-shrink: 0;
            }
            .control-section {
                text-align: center;
            }
            .control-section h3 {
                margin: 0 0 10px 0;
                color: #495057;
                font-size: 16px;
            }
            button {
                font-size: 14px;
                padding: 10px 20px;
                margin: 0 5px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                transition: all 0.3s;
                display: inline-block;
            }
            .camera-btn, .resolution-btn {
                background: #f8f9fa;
                color: #495057;
                border: 1px solid #dee2e6;
            }
            .camera-btn:hover, .resolution-btn:hover {
                background: #e9ecef;
            }
            .camera-btn.active, .resolution-btn.active {
                background: #28a745;
                color: white;
                border: 1px solid #28a745;
            }
            .exit-btn {
                font-size: 14px;
                padding: 10px 20px;
                margin: 0 5px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                transition: all 0.3s;
                display: inline-block;
                text-decoration: none;
                background: #dc3545;
                color: white;
                border: 1px solid #dc3545;
                font-weight: bold;
            }
            .exit-btn:hover {
                background: #c82333;
                border: 1px solid #c82333;
                color: white;
                text-decoration: none;
            }
            .status {
                margin: 10px 0;
                padding: 10px;
                background: #e9ecef;
                border-radius: 8px;
                font-size: 12px;
                flex-shrink: 0;
            }
            .status-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 10px;
            }
            .status-item {
                padding: 8px;
                background: white;
                border-radius: 4px;
                border-left: 3px solid #007bff;
            }
            .status-item strong {
                color: #495057;
            }
            .status-item span {
                color: #007bff;
                font-weight: bold;
            }
            
            /* 하트비트 인디케이터 스타일 */
            .heartbeat-container {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                margin-left: 20px;
                vertical-align: middle;
            }
            
            .heartbeat-indicator {
                width: 20px;
                height: 20px;
                border-radius: 50%;
                margin-right: 8px;
                position: relative;
            }
            
            .heartbeat-indicator.green {
                background: #28a745;
                animation: pulse-green 1s infinite;
                box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7);
            }
            
            .heartbeat-indicator.yellow {
                background: #ffc107;
                animation: pulse-yellow 2s infinite;
                box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.7);
            }
            
            .heartbeat-indicator.red {
                background: #dc3545;
                animation: none;
            }
            
            .heartbeat-indicator.black {
                background: #6c757d;
                animation: none;
            }
            
            @keyframes pulse-green {
                0% {
                    transform: scale(0.95);
                    box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7);
                }
                70% {
                    transform: scale(1);
                    box-shadow: 0 0 0 10px rgba(40, 167, 69, 0);
                }
                100% {
                    transform: scale(0.95);
                    box-shadow: 0 0 0 0 rgba(40, 167, 69, 0);
                }
            }
            
            @keyframes pulse-yellow {
                0% {
                    transform: scale(0.95);
                    box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.7);
                }
                70% {
                    transform: scale(1);
                    box-shadow: 0 0 0 10px rgba(255, 193, 7, 0);
                }
                100% {
                    transform: scale(0.95);
                    box-shadow: 0 0 0 0 rgba(255, 193, 7, 0);
                }
            }
            
            .heartbeat-text {
                font-size: 12px;
                color: #495057;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Picamera2 듀얼 카메라 토글 <span class="badge">Pi5 GPU 가속</span></h1>
            
            <div class="status">
                <div class="status-grid">
                    <div class="status-item">
                        <strong>활성 카메라:</strong> <span id="current-camera">0</span>
                    </div>
                    <div class="status-item">
                        <strong>해상도:</strong> <span id="resolution">640×480</span>
                    </div>
                    <div class="status-item">
                        <strong>엔진:</strong> <span id="engine">Picamera2</span>
                    </div>
                    <div class="status-item">
                        <strong>GPU:</strong> <span id="gpu">VideoCore VII</span>
                    </div>
                    <div class="status-item">
                        <strong>FPS:</strong> <span id="fps">0.0</span>
                    </div>
                    <div class="status-item">
                        <strong>프레임 수:</strong> <span id="frame-count">0</span>
                    </div>
                    <div class="status-item">
                        <strong>평균 프레임 크기:</strong> <span id="frame-size">0 KB</span>
                    </div>
                    <div class="status-item">
                        <strong>상태:</strong> <span id="stream-status">준비 중</span>
                    </div>
                </div>
            </div>
            
            <div class="controls">
                <div class="control-section">
                    <h3>카메라 선택</h3>
                    <button class="camera-btn active" id="cam0-btn" onclick="switchCamera(0)">
                        카메라 0
                    </button>
                    <button class="camera-btn" id="cam1-btn" onclick="switchCamera(1)">
                        카메라 1
                    </button>
                </div>
                
                <div class="control-section">
                    <h3>해상도 선택</h3>
                    <button class="resolution-btn active" id="res-640-btn" onclick="changeResolution('640x480')">
                        📺 480p (640×480)
                    </button>
                    <button class="resolution-btn" id="res-720-btn" onclick="changeResolution('1280x720')">
                        📺 720p (1280×720)
                    </button>
                </div>
                
                <div class="control-section">
                    <h3>시스템 제어</h3>
                    <div style="display: flex; align-items: center; justify-content: center;">
                        <a href="/exit" class="exit-btn">
                            🛑  CCTV 종료
                        </a>
                        <!-- 하트비트 인디케이터 -->
                        <div class="heartbeat-container">
                            <div class="heartbeat-indicator green" id="heartbeat-indicator"></div>
                            <span class="heartbeat-text" id="heartbeat-text">LIVE</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="video-container resolution-640" id="video-container">
                <img id="video-stream" src="/stream" alt="Picamera2 Live Stream">
            </div>
            
            <p>🚀 Picamera2 + Pi5 VideoCore VII GPU 하드웨어 가속</p>
        </div>
        
        <script>
            let currentCamera = 0;
            let lastFrameTime = Date.now();
            let streamQuality = 100;
            
            function switchCamera(cameraId) {
                fetch(`/switch/${cameraId}`, { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            currentCamera = cameraId;
                            updateUI();
                            const img = document.getElementById('video-stream');
                            img.src = `/stream?t=${Date.now()}`;
                        }
                    })
                    .catch(error => console.error('Error:', error));
            }
            
            function updateUI() {
                document.getElementById('cam0-btn').classList.toggle('active', currentCamera === 0);
                document.getElementById('cam1-btn').classList.toggle('active', currentCamera === 1);
                document.getElementById('current-camera').textContent = currentCamera;
            }
            
            function changeResolution(resolution) {
                fetch(`/api/resolution/${resolution}`, { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            document.getElementById('res-640-btn').classList.toggle('active', resolution === '640x480');
                            document.getElementById('res-720-btn').classList.toggle('active', resolution === '1280x720');
                            
                            const videoContainer = document.getElementById('video-container');
                            videoContainer.className = 'video-container ' + (resolution === '640x480' ? 'resolution-640' : 'resolution-720');
                            
                            const img = document.getElementById('video-stream');
                            img.src = `/stream?t=${Date.now()}`;
                        }
                    })
                    .catch(error => console.error('Resolution change error:', error));
            }
            
            function updateStats() {
                fetch('/api/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('current-camera').textContent = data.current_camera;
                        document.getElementById('resolution').textContent = data.resolution;
                        
                        const stats = data.stats;
                        if (stats && Object.keys(stats).length > 0) {
                            document.getElementById('fps').textContent = stats.fps || '0.0';
                            document.getElementById('frame-count').textContent = stats.frame_count || '0';
                            document.getElementById('frame-size').textContent = 
                                stats.avg_frame_size ? Math.round(stats.avg_frame_size / 1024) + ' KB' : '0 KB';
                            
                            const now = Date.now() / 1000;
                            const lastUpdate = stats.last_update || 0;
                            const isActive = (now - lastUpdate) < 3;
                            
                            document.getElementById('stream-status').textContent = 
                                isActive ? '스트리밍 중' : '연결 끊김';
                            document.getElementById('stream-status').style.color = 
                                isActive ? '#28a745' : '#dc3545';
                        } else {
                            document.getElementById('fps').textContent = '0.0';
                            document.getElementById('frame-count').textContent = '0';
                            document.getElementById('frame-size').textContent = '0 KB';
                            document.getElementById('stream-status').textContent = '대기 중';
                            document.getElementById('stream-status').style.color = '#6c757d';
                        }
                    })
                    .catch(error => {
                        console.error('Stats update error:', error);
                        document.getElementById('stream-status').textContent = '오류';
                        document.getElementById('stream-status').style.color = '#dc3545';
                    });
            }
            
            // 스트림 모니터링 시스템
            function initStreamMonitoring() {
                const videoStream = document.getElementById('video-stream');
                
                // MJPEG 스트림을 위한 대체 방법 - 이미지 크기 변화 감지
                let lastImageSize = 0;
                function checkStreamActivity() {
                    // 스트림 연결 상태 체크
                    fetch('/stream', { 
                        method: 'HEAD',
                        signal: AbortSignal.timeout(1000) // 1초 타임아웃
                    })
                    .then(response => {
                        if (response.ok) {
                            lastFrameTime = Date.now();
                            updateStreamQuality(true);
                        } else {
                            updateStreamQuality(false);
                        }
                    })
                    .catch(() => {
                        updateStreamQuality(false);
                    });
                }
                
                // 에러 감지
                videoStream.addEventListener('error', function() {
                    updateStreamQuality(false);
                    setTimeout(() => {
                        this.src = `/stream?t=${Date.now()}`;
                    }, 2000);
                });
                
                // 스트림 로드 감지 (이미지가 변경될 때)
                videoStream.addEventListener('load', function() {
                    lastFrameTime = Date.now();
                    updateStreamQuality(true);
                });
                
                // 정기적으로 스트림 활성화 체크 (2초마다)
                setInterval(checkStreamActivity, 2000);
                
                // 0.5초마다 하트비트 상태 체크
                setInterval(checkHeartbeat, 500);
                
                // 초기 하트비트 설정
                lastFrameTime = Date.now();
            }
            
            function checkHeartbeat() {
                const now = Date.now();
                const elapsed = (now - lastFrameTime) / 1000;
                const indicator = document.getElementById('heartbeat-indicator');
                const text = document.getElementById('heartbeat-text');
                
                // 하트비트 상태 업데이트
                indicator.className = 'heartbeat-indicator';
                
                if (elapsed < 1) {
                    indicator.classList.add('green');
                    text.textContent = 'LIVE';
                } else if (elapsed < 3) {
                    indicator.classList.add('yellow');
                    text.textContent = 'DELAY';
                } else if (elapsed < 5) {
                    indicator.classList.add('red');
                    text.textContent = 'ERROR';
                } else {
                    indicator.classList.add('black');
                    text.textContent = 'OFFLINE';
                }
            }
            
            function updateStreamQuality(frameReceived) {
                const now = Date.now();
                const elapsed = (now - lastFrameTime) / 1000;
                
                if (frameReceived) {
                    streamQuality = Math.min(100, streamQuality + 5);
                } else if (elapsed > 3) {
                    streamQuality = Math.max(0, streamQuality - 20);
                } else if (elapsed > 1) {
                    streamQuality = Math.max(30, streamQuality - 5);
                }
            }
            
            // 페이지 로드 시 모니터링 시스템 시작
            document.addEventListener('DOMContentLoaded', function() {
                initStreamMonitoring(); // 스트림 모니터링 시작
                updateStats(); // 즉시 한 번 실행
                setInterval(updateStats, 1000); // 1초마다 업데이트
            });
            
            updateStats();
            setInterval(updateStats, 1000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# 기존 API 엔드포인트들 그대로 유지
@app.post("/switch/{camera_id}")
async def switch_camera(camera_id: int):
    """카메라 전환"""
    global current_camera
    
    if camera_id not in [0, 1]:
        raise HTTPException(status_code=400, detail="Invalid camera ID")
    
    if camera_id == current_camera:
        return {"success": True, "message": f"Camera {camera_id} already active"}
    
    print(f"[SWITCH] Switching from camera {current_camera} to camera {camera_id}")
    
    # 기존 카메라 정지
    stop_camera_stream(current_camera)
    await asyncio.sleep(0.5)
    
    # 새 카메라 시작
    success = start_camera_stream(camera_id)
    
    if success:
        current_camera = camera_id
        print(f"[OK] Successfully switched to camera {camera_id}")
        return {"success": True, "message": f"Switched to camera {camera_id}"}
    else:
        # 실패 시 기존 카메라 다시 시작
        start_camera_stream(current_camera)
        raise HTTPException(status_code=500, detail="Failed to switch camera")

@app.api_route("/stream", methods=["GET", "HEAD"])
async def video_stream(request: Request):
    """비디오 스트림"""
    client_ip = request.client.host
    
    # 단일 클라이언트 제한 확인
    if len(active_clients) >= MAX_CLIENTS and client_ip not in active_clients:
        print(f"[REJECT] Stream request rejected: {client_ip} (Max clients: {MAX_CLIENTS})")
        raise HTTPException(
            status_code=423,
            detail=f"Maximum {MAX_CLIENTS} client(s) allowed. Another client is currently streaming."
        )
    
    # HEAD 요청 처리 (하트비트 체크용)
    if request.method == "HEAD":
        # 카메라 상태만 확인하고 헤더만 반환
        if current_camera in camera_instances:
            return Response(status_code=200, headers={"Content-Type": "multipart/x-mixed-replace; boundary=frame"})
        else:
            return Response(status_code=503, headers={"Content-Type": "text/plain"})
    
    print(f"[REQUEST] Stream request for camera {current_camera} (Picamera2)")
    
    # 현재 카메라가 시작되지 않았으면 시작
    if current_camera not in camera_instances:
        success = start_camera_stream(current_camera)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to start camera")
    
    return StreamingResponse(
        generate_mjpeg_stream(current_camera, client_ip),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/api/stats")
async def get_stream_stats():
    """스트리밍 통계 조회"""
    return {
        "current_camera": current_camera,
        "resolution": current_resolution,
        "codec": "MJPEG",
        "quality": "80-85%",
        "engine": "Picamera2",
        "stats": stream_stats[current_camera] if current_camera in stream_stats else {}
    }

@app.post("/api/resolution/{resolution}")
async def change_resolution(resolution: str):
    """해상도 변경"""
    global current_resolution
    
    if resolution not in RESOLUTIONS:
        raise HTTPException(status_code=400, detail="Invalid resolution")
    
    print(f"[RESOLUTION] Changing resolution to {resolution}")
    
    if resolution == current_resolution:
        return {"success": True, "message": f"Resolution already set to {resolution}"}
    
    old_resolution = current_resolution
    current_resolution = resolution
    
    # 현재 스트리밍 중인 카메라가 있으면 재시작
    if current_camera in camera_instances:
        print(f"[RESOLUTION] Stopping current camera {current_camera} for resolution change...")
        stop_camera_stream(current_camera)
        
        await asyncio.sleep(2.0)
        
        print(f"[START] Starting camera {current_camera} with {resolution}...")
        success = start_camera_stream(current_camera, resolution)
        
        if success:
            await asyncio.sleep(1.0)
            print(f"[OK] Successfully changed resolution to {resolution}")
            return {"success": True, "message": f"Resolution changed to {resolution}"}
        else:
            print(f"[ERROR] Failed to start with {resolution}, reverting to {old_resolution}")
            current_resolution = old_resolution
            await asyncio.sleep(1.0)
            start_camera_stream(current_camera, old_resolution)
            raise HTTPException(status_code=500, detail="Failed to change resolution")
    else:
        print(f"[OK] Resolution set to {resolution} (will apply when camera starts)")
        return {"success": True, "message": f"Resolution set to {resolution}"}

@app.get("/exit")
async def exit_system():
    """시스템 종료 페이지"""
    html_content = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Picamera2 CCTV 종료</title>
        <meta charset="UTF-8">
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            .container {
                text-align: center;
                background: white;
                padding: 50px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .emoji {
                font-size: 60px;
                margin: 20px 0;
            }
            h1 {
                color: #333;
                margin-bottom: 20px;
            }
            .message {
                color: #666;
                font-size: 18px;
                line-height: 1.6;
            }
            .success {
                color: #28a745;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="emoji">🚀</div>
            <h1>Picamera2 CCTV 서비스 종료 중...</h1>
            <p class="message">
                <span class="success">✅ Pi5 VideoCore VII GPU 가속 시스템이 안전하게 종료되었습니다.</span><br><br>
                이제 모션 감지 시스템을 실행할 수 있습니다.<br>
                브라우저를 닫으셔도 됩니다.
            </p>
        </div>
        <script>
            setTimeout(() => {
                fetch('/api/shutdown', { method: 'POST' })
                    .catch(() => {});
            }, 1000);
        </script>
    </body>
    </html>
    '''
    return HTMLResponse(content=html_content)

@app.post("/api/shutdown")
async def shutdown_system():
    """시스템 안전 종료"""
    print("[SHUTDOWN] System shutdown requested via web interface")
    
    # 모든 카메라 인스턴스 정리
    for camera_id in list(camera_instances.keys()):
        print(f"[SHUTDOWN] Stopping camera {camera_id}...")
        stop_camera_stream(camera_id)
    
    print("[SHUTDOWN] All cameras stopped. Server will shutdown...")
    
    # 비동기적으로 서버 종료
    import threading
    def delayed_shutdown():
        import time
        time.sleep(1)
        import os
        os._exit(0)
    
    threading.Thread(target=delayed_shutdown, daemon=True).start()
    
    return {"success": True, "message": "Picamera2 system shutting down..."}

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    logger.info("[START] Picamera2 CCTV 서버 시작 완료 - 첫 스트림 요청 시 카메라 활성화")
    print("[START] Picamera2 server startup complete - camera will start on first stream request")

@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 모든 카메라 정리"""
    logger.info("[SHUTDOWN] Picamera2 CCTV 서버 종료 중 - 카메라 정리 시작")
    print("[SHUTDOWN] Cleaning up cameras...")
    for camera_id in list(camera_instances.keys()):
        stop_camera_stream(camera_id)

def cleanup_all_cameras():
    """모든 카메라 인스턴스 정리"""
    logger.info("[CLEANUP] 긴급 정리: 모든 카메라 인스턴스 중지")
    print("[CLEANUP] Cleanup: Stopping all camera instances...")
    for camera_id in list(camera_instances.keys()):
        stop_camera_stream(camera_id)
    logger.info("[CLEANUP] All camera instances cleaned up")
    print("[CLEANUP] All camera instances cleaned up")

def signal_handler(signum, frame):
    """신호 핸들러 - SIGINT/SIGTERM 처리"""
    logger.warning(f"[SIGNAL] 시스템 종료 신호 수신: {signum} (Ctrl+C)")
    print(f"\n[SIGNAL] Received signal {signum} (Ctrl+C), cleaning up...")
    cleanup_all_cameras()
    logger.info("[EXIT] Picamera2 CCTV 서버 완전 종료")
    print("[EXIT] Picamera2 server shutdown complete")
    sys.exit(0)

if __name__ == "__main__":
    # 신호 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # atexit 핸들러 등록
    atexit.register(cleanup_all_cameras)
    
    print("=" * 60)
    print("🚀 Picamera2 CCTV System (cctv_main.py 구조 기반)")
    print("=" * 60)
    print("[INFO] Starting Picamera2-powered camera server on port 8001")
    print("[INFO] Hardware: Raspberry Pi 5 + VideoCore VII GPU")
    print("[INFO] Engine: Picamera2 (rpicam-vid 교체)")
    print("[INFO] Features: Zero subprocess, Direct GPU access")
    print("[INFO] Access web interface at: http://<your-pi-ip>:8001")
    print("=" * 60)
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8001,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Keyboard interrupt received")
        cleanup_all_cameras()
    except Exception as e:
        print(f"[ERROR] Server error: {e}")
        cleanup_all_cameras()
    finally:
        print("[EXIT] Picamera2 server shutdown complete")