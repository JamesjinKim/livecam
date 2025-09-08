#!/usr/bin/env python3
"""
듀얼 카메라 토글 스트리밍 서버
"""

import subprocess
import signal
import asyncio
import time
import atexit
import sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
import uvicorn

app = FastAPI()

# 전역 변수
current_camera = 0
current_resolution = "640x480"  # 기본 해상도
camera_processes = {}
stream_stats = {
    0: {"frame_count": 0, "avg_frame_size": 0, "fps": 0, "last_update": 0},
    1: {"frame_count": 0, "avg_frame_size": 0, "fps": 0, "last_update": 0}
}

# 단일 클라이언트 제한
active_clients = set()  # 활성 클라이언트 IP 집합
MAX_CLIENTS = 1  # 최대 1개 클라이언트

# 해상도 설정
RESOLUTIONS = {
    "640x480": {"width": 640, "height": 480, "name": "480p"},
    "1280x720": {"width": 1280, "height": 720, "name": "720p"}
}

def start_camera_stream(camera_id: int, resolution: str = None):
    """카메라 스트리밍 시작"""
    if camera_id in camera_processes:
        stop_camera_stream(camera_id)
    
    # 해상도 설정
    if resolution is None:
        resolution = current_resolution
    
    res_config = RESOLUTIONS.get(resolution, RESOLUTIONS["640x480"])
    width = res_config["width"]
    height = res_config["height"]
    
    cmd = [
        "rpicam-vid",
        "--camera", str(camera_id),
        "--width", str(width), "--height", str(height),
        "--framerate", "30",
        "--timeout", "0",
        "--nopreview",
        "--codec", "mjpeg",
        "--quality", "80",
        "--flush", "1",
        "--hflip",  # 좌우 반전 (거울모드)
        "--output", "-"
    ]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        camera_processes[camera_id] = process
        print(f"✅ Camera {camera_id} started at {resolution} (PID: {process.pid})")
        return True
    except Exception as e:
        print(f"❌ Failed to start camera {camera_id}: {e}")
        return False

def stop_camera_stream(camera_id: int):
    """카메라 스트리밍 중지"""
    if camera_id in camera_processes:
        try:
            process = camera_processes[camera_id]
            # 프로세스 완전 종료
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=5)  # 더 긴 대기 시간
            except subprocess.TimeoutExpired:
                print(f"⚠️ Force killing camera {camera_id}")
                process.kill()
                process.wait(timeout=2)
            
            # stdout/stderr 버퍼 정리
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()
                
            del camera_processes[camera_id]
            # 통계 초기화
            stream_stats[camera_id] = {"frame_count": 0, "avg_frame_size": 0, "fps": 0, "last_update": 0}
            print(f"🛑 Camera {camera_id} stopped and cleaned")
        except Exception as e:
            print(f"⚠️ Error stopping camera {camera_id}: {e}")

def cleanup_all_processes():
    """모든 카메라 프로세스 정리"""
    print("🧹 Cleanup: Stopping all camera processes...")
    for camera_id in list(camera_processes.keys()):
        stop_camera_stream(camera_id)
    print("✅ All camera processes cleaned up")

def signal_handler(signum, frame):
    """신호 핸들러 - SIGINT/SIGTERM 처리"""
    print(f"\n🛑 Received signal {signum} (Ctrl+C), cleaning up...")
    cleanup_all_processes()
    print("👋 Server shutdown complete")
    sys.exit(0)

def generate_mjpeg_stream(camera_id: int, client_ip: str = None):
    """해상도별 최적화된 MJPEG 스트림 생성"""
    if camera_id not in camera_processes:
        return
    
    process = camera_processes[camera_id]
    
    # 현재 해상도에 따른 동적 설정
    is_720p = current_resolution == "1280x720"
    
    # 해상도별 최적화 파라미터
    if is_720p:
        chunk_size = 32768  # 32KB 청크 (720p용)
        buffer_limit = 2 * 1024 * 1024  # 2MB 버퍼
        buffer_keep = 1024 * 1024  # 1MB 유지
        frame_min_size = 5000  # 5KB
        frame_max_size = 500000  # 500KB
        cleanup_threshold = 100000  # 100KB
        cleanup_keep = 20000  # 20KB
    else:
        chunk_size = 16384  # 16KB 청크 (480p용)
        buffer_limit = 512 * 1024  # 512KB 버퍼
        buffer_keep = 256 * 1024  # 256KB 유지
        frame_min_size = 2000  # 2KB
        frame_max_size = 200000  # 200KB
        cleanup_threshold = 50000  # 50KB
        cleanup_keep = 10000  # 10KB
    
    buffer = bytearray()
    frame_count = 0
    total_frame_size = 0
    start_time = time.time()
    last_fps_update = start_time
    
    print(f"🎬 Starting {current_resolution} stream for camera {camera_id}")
    print(f"📊 Buffer config: {buffer_limit//1024}KB limit, {chunk_size//1024}KB chunks")
    
    # 클라이언트 등록
    if client_ip:
        active_clients.add(client_ip)
        print(f"👥 Client connected: {client_ip} (Total: {len(active_clients)})")
    
    try:
        while True:
            try:
                chunk = process.stdout.read(chunk_size)
                if not chunk:
                    print(f"⚠️ No data from camera {camera_id}, stream ending")
                    break
            except Exception as e:
                print(f"❌ Read error from camera {camera_id}: {e}")
                break
                
            buffer.extend(chunk)
            
            # 동적 버퍼 크기 제한
            if len(buffer) > buffer_limit:
                buffer = buffer[-buffer_keep:]
            
            # JPEG 프레임 찾기
            while True:
                start_idx = buffer.find(b'\xff\xd8')
                if start_idx == -1:
                    if len(buffer) > cleanup_threshold:
                        buffer = buffer[-cleanup_keep:]
                    break
                    
                end_idx = buffer.find(b'\xff\xd9', start_idx + 2)
                if end_idx == -1:
                    if start_idx > 0:
                        buffer = buffer[start_idx:]
                    break
                
                # 완전한 프레임 추출
                frame = buffer[start_idx:end_idx + 2]
                buffer = buffer[end_idx + 2:]
                
                # 해상도별 프레임 크기 검증
                frame_size = len(frame)
                if frame_min_size < frame_size < frame_max_size:
                    try:
                        yield b'--frame\r\n'
                        yield b'Content-Type: image/jpeg\r\n'
                        yield f'Content-Length: {frame_size}\r\n\r\n'.encode()
                        yield bytes(frame)
                        yield b'\r\n'
                        
                        frame_count += 1
                        total_frame_size += frame_size
                        
                        # FPS 및 통계 업데이트 (매초마다)
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
                        
                        if frame_count % 150 == 0:  # 150프레임마다 로그
                            print(f"📊 Camera {camera_id} ({current_resolution}): {frame_count} frames, {stream_stats[camera_id]['fps']} fps, avg {frame_size//1024}KB")
                    
                    except Exception as e:
                        print(f"⚠️ Frame yield error for camera {camera_id}: {e}")
                        break
                else:
                    if frame_count % 100 == 0 and frame_size > 0:  # 가끔 로그
                        print(f"⚠️ Frame size {frame_size//1024}KB out of range ({frame_min_size//1024}-{frame_max_size//1024}KB)")
                        
    except Exception as e:
        print(f"❌ Stream error for camera {camera_id}: {e}")
    finally:
        # 클라이언트 연결 종료
        if client_ip and client_ip in active_clients:
            active_clients.remove(client_ip)
            print(f"🚫 Client disconnected: {client_ip} (Remaining: {len(active_clients)})")
        print(f"⏹️ Camera {camera_id} ({current_resolution}) stream ended (total: {frame_count} frames)")
        # 스트림 종료 시 통계 초기화
        if camera_id in stream_stats:
            stream_stats[camera_id]["last_update"] = 0

@app.get("/")
async def root():
    """메인 페이지"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>듀얼 카메라 토글</title>
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
            .shutdown-btn {
                background: #dc3545;
                color: white;
                border: 1px solid #dc3545;
                font-weight: bold;
            }
            .shutdown-btn:hover {
                background: #c82333;
                border: 1px solid #c82333;
            }
            .video-container {
                margin: 20px 0;
                border: 2px solid #ddd;
                border-radius: 8px;
                overflow: hidden;
                background: #f8f9fa;
            }
            .video-container img { 
                width: 100%; 
                height: auto;
                display: block;
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
        </style>
    </head>
    <body>
        <div class="container">
            <h1>듀얼 카메라 토글 스트리밍</h1>
            
            <div class="status">
                <div class="status-grid">
                    <div class="status-item">
                        <strong>활성 카메라:</strong> <span id="current-camera">0</span>
                    </div>
                    <div class="status-item">
                        <strong>해상도:</strong> <span id="resolution">640×480</span>
                    </div>
                    <div class="status-item">
                        <strong>코덱:</strong> <span id="codec">MJPEG</span>
                    </div>
                    <div class="status-item">
                        <strong>품질:</strong> <span id="quality">80%</span>
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
                    <button class="shutdown-btn" onclick="shutdownSystem()">
                        🛑 서비스 종료
                    </button>
                </div>
            </div>
            
            <div class="video-container resolution-640" id="video-container">
                <img id="video-stream" src="/stream" alt="Live Stream">
            </div>
            
            <p>카메라 전환기능으로 시스템 부하를 줄입니다</p>
        </div>
        
        <script>
            let currentCamera = 0;
            
            function switchCamera(cameraId) {
                fetch(`/switch/${cameraId}`, { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            currentCamera = cameraId;
                            updateUI();
                            // 스트림 새로고침
                            const img = document.getElementById('video-stream');
                            img.src = `/stream?t=${Date.now()}`;
                        }
                    })
                    .catch(error => console.error('Error:', error));
            }
            
            function updateUI() {
                // 버튼 상태 업데이트
                document.getElementById('cam0-btn').classList.toggle('active', currentCamera === 0);
                document.getElementById('cam1-btn').classList.toggle('active', currentCamera === 1);
                
                // 현재 카메라 표시
                document.getElementById('current-camera').textContent = currentCamera;
            }
            
            function changeResolution(resolution) {
                fetch(`/api/resolution/${resolution}`, { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // 해상도 버튼 상태 업데이트
                            document.getElementById('res-640-btn').classList.toggle('active', resolution === '640x480');
                            document.getElementById('res-720-btn').classList.toggle('active', resolution === '1280x720');
                            
                            // 비디오 컨테이너 클래스 업데이트
                            const videoContainer = document.getElementById('video-container');
                            videoContainer.className = 'video-container ' + (resolution === '640x480' ? 'resolution-640' : 'resolution-720');
                            
                            // 스트림 새로고침
                            const img = document.getElementById('video-stream');
                            img.src = `/stream?t=${Date.now()}`;
                            
                            console.log(`Resolution changed to ${resolution}`);
                        }
                    })
                    .catch(error => {
                        console.error('Resolution change error:', error);
                        alert(`해상도 변경 실패: ${error.message}`);
                    });
            }
            
            function shutdownSystem() {
                if (confirm('🛑 서비스를 종료하시겠습니까?\n\n모든 카메라 스트림이 중지되고 서버가 종료됩니다.')) {
                    document.getElementById('stream-status').textContent = '서비스 종료 중...';
                    
                    fetch('/api/shutdown', { method: 'POST' })
                        .then(response => {
                            if (response.ok) {
                                alert('✅ 서비스가 정상 종료되었습니다.\n브라우저를 닫으셔도 됩니다.');
                                document.body.innerHTML = '<div style="text-align:center;padding:50px;font-size:18px;">🛑 서비스 종료 완료<br><br>브라우저를 닫으셔도 됩니다.</div>';
                            } else {
                                throw new Error('서버 응답 오류');
                            }
                        })
                        .catch(error => {
                            console.error('Shutdown error:', error);
                            alert('⚠️ 종료 요청 실패. 터미널에서 Ctrl+C로 종료해주세요.');
                        });
                }
            }
            
            function updateStats() {
                fetch('/api/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('current-camera').textContent = data.current_camera;
                        document.getElementById('resolution').textContent = data.resolution;
                        document.getElementById('codec').textContent = data.codec;
                        document.getElementById('quality').textContent = data.quality;
                        
                        // 해상도 버튼 상태 업데이트
                        document.getElementById('res-640-btn').classList.toggle('active', data.resolution === '640x480');
                        document.getElementById('res-720-btn').classList.toggle('active', data.resolution === '1280x720');
                        
                        // 비디오 컨테이너 클래스도 업데이트
                        const videoContainer = document.getElementById('video-container');
                        if (videoContainer) {
                            videoContainer.className = 'video-container ' + (data.resolution === '640x480' ? 'resolution-640' : 'resolution-720');
                        }
                        
                        const stats = data.stats;
                        if (stats && Object.keys(stats).length > 0) {
                            document.getElementById('fps').textContent = stats.fps || '0.0';
                            document.getElementById('frame-count').textContent = stats.frame_count || '0';
                            document.getElementById('frame-size').textContent = 
                                stats.avg_frame_size ? Math.round(stats.avg_frame_size / 1024) + ' KB' : '0 KB';
                            
                            // 상태 표시
                            const now = Date.now() / 1000;
                            const lastUpdate = stats.last_update || 0;
                            const isActive = (now - lastUpdate) < 3; // 3초 이내 업데이트면 활성
                            
                            document.getElementById('stream-status').textContent = 
                                isActive ? '스트리밍 중' : '연결 끊김';
                            document.getElementById('stream-status').style.color = 
                                isActive ? '#28a745' : '#dc3545';
                        } else {
                            // 통계가 없으면 기본값
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
            
            // 스트림 오류 시 재시도
            document.getElementById('video-stream').onerror = function() {
                console.log('Stream error occurred, retrying...');
                setTimeout(() => {
                    this.src = `/stream?t=${Date.now()}`;
                }, 2000);
            };
            
            // 스트림 로드 오류 처리 (423 Locked 등)
            document.getElementById('video-stream').onload = function() {
                document.getElementById('stream-status').style.display = 'block';
            };
            
            // 스트림 연결 상태 체크
            function checkStreamConnection() {
                const img = document.getElementById('video-stream');
                const status = document.getElementById('stream-status');
                
                if (img.complete && img.naturalHeight !== 0) {
                    status.textContent = '스트리밍 중';
                    status.style.color = '#28a745';
                } else {
                    // 423 에러 체크
                    fetch('/stream', { method: 'HEAD' })
                        .then(response => {
                            if (response.status === 423) {
                                status.textContent = '❌ 다른 사용자가 스트리밍 중입니다';
                                status.style.color = '#dc3545';
                            } else {
                                status.textContent = '연결 대기 중';
                                status.style.color = '#6c757d';
                            }
                        })
                        .catch(() => {
                            status.textContent = '연결 오류';
                            status.style.color = '#dc3545';
                        });
                }
            }
            
            // 3초마다 연결 상태 체크
            setInterval(checkStreamConnection, 3000);
            
            // 페이지 로드 시 통계 업데이트 시작
            document.addEventListener('DOMContentLoaded', function() {
                updateStats(); // 즉시 한 번 실행
                setInterval(updateStats, 1000); // 1초마다 업데이트
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/switch/{camera_id}")
async def switch_camera(camera_id: int):
    """카메라 전환"""
    global current_camera
    
    if camera_id not in [0, 1]:
        raise HTTPException(status_code=400, detail="Invalid camera ID")
    
    if camera_id == current_camera:
        return {"success": True, "message": f"Camera {camera_id} already active"}
    
    print(f"🔄 Switching from camera {current_camera} to camera {camera_id}")
    
    # 기존 카메라 정지
    stop_camera_stream(current_camera)
    await asyncio.sleep(0.5)  # 잠시 대기
    
    # 새 카메라 시작
    success = start_camera_stream(camera_id)
    
    if success:
        current_camera = camera_id
        print(f"✅ Successfully switched to camera {camera_id}")
        return {"success": True, "message": f"Switched to camera {camera_id}"}
    else:
        # 실패 시 기존 카메라 다시 시작
        start_camera_stream(current_camera)
        raise HTTPException(status_code=500, detail="Failed to switch camera")

@app.get("/stream")
async def stream():
    """현재 활성 카메라 스트림"""
    print(f"🌐 Stream request for camera {current_camera}")
    
    if current_camera not in camera_processes:
        # 카메라가 시작되지 않았으면 시작
        if not start_camera_stream(current_camera):
            raise HTTPException(status_code=500, detail="Failed to start camera")
        await asyncio.sleep(1)  # 카메라 초기화 대기
    
    return StreamingResponse(
        generate_mjpeg_stream(current_camera),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive"
        }
    )

@app.get("/api/stats")
async def get_stream_stats():
    """스트리밍 통계 조회"""
    return {
        "current_camera": current_camera,
        "resolution": current_resolution,
        "codec": "MJPEG",
        "quality": "80%",
        "stats": stream_stats[current_camera] if current_camera in stream_stats else {}
    }

@app.post("/api/resolution/{resolution}")
async def change_resolution(resolution: str):
    """해상도 변경"""
    global current_resolution
    
    if resolution not in RESOLUTIONS:
        raise HTTPException(status_code=400, detail="Invalid resolution")
    
    print(f"🔄 Changing resolution to {resolution}")
    
    # 현재 해상도와 같으면 변경하지 않음
    if resolution == current_resolution:
        return {"success": True, "message": f"Resolution already set to {resolution}"}
    
    old_resolution = current_resolution
    current_resolution = resolution
    
    # 현재 스트리밍 중인 카메라가 있으면 재시작
    if current_camera in camera_processes:
        print(f"🔄 Stopping current camera {current_camera} for resolution change...")
        stop_camera_stream(current_camera)
        
        # 충분한 대기 시간으로 완전한 정리 보장
        await asyncio.sleep(2.0)  # 2초 대기
        
        print(f"🚀 Starting camera {current_camera} with {resolution}...")
        success = start_camera_stream(current_camera, resolution)
        
        if success:
            # 카메라 시작 후 추가 안정화 대기
            await asyncio.sleep(1.0)
            print(f"✅ Successfully changed resolution to {resolution}")
            return {"success": True, "message": f"Resolution changed to {resolution}"}
        else:
            # 실패 시 이전 해상도로 복원
            print(f"❌ Failed to start with {resolution}, reverting to {old_resolution}")
            current_resolution = old_resolution
            await asyncio.sleep(1.0)
            start_camera_stream(current_camera, old_resolution)
            raise HTTPException(status_code=500, detail="Failed to change resolution")
    else:
        print(f"✅ Resolution set to {resolution} (will apply when camera starts)")
        return {"success": True, "message": f"Resolution set to {resolution}"}

@app.get("/stream")
async def video_stream(request: Request):
    """비디오 스트림 - 단일 클라이언트 제한"""
    client_ip = request.client.host
    
    # 단일 클라이언트 제한 확인
    if len(active_clients) >= MAX_CLIENTS and client_ip not in active_clients:
        print(f"🚫 Stream request rejected: {client_ip} (Max clients: {MAX_CLIENTS})")
        raise HTTPException(
            status_code=423,  # Locked
            detail=f"Maximum {MAX_CLIENTS} client(s) allowed. Another client is currently streaming."
        )
    
    print(f"🌐 Stream request for camera {current_camera}")
    
    # 현재 카메라가 시작되지 않았으면 시작
    if current_camera not in camera_processes:
        success = start_camera_stream(current_camera)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to start camera")
    
    return StreamingResponse(
        generate_mjpeg_stream(current_camera, client_ip),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.post("/api/shutdown")
async def shutdown_system():
    """시스템 안전 종료"""
    print("🛑 System shutdown requested via web interface")
    
    # 모든 카메라 프로세스 정리
    for camera_id in list(camera_processes.keys()):
        print(f"🧹 Stopping camera {camera_id}...")
        stop_camera_stream(camera_id)
    
    print("✅ All cameras stopped. Server will shutdown...")
    
    # 비동기적으로 서버 종료 (응답 후에 종료)
    import threading
    def delayed_shutdown():
        import time
        time.sleep(1)  # 응답 전송 대기
        import os
        os._exit(0)  # 강제 종료
    
    threading.Thread(target=delayed_shutdown, daemon=True).start()
    
    return {"success": True, "message": "System shutting down..."}

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    print("🎬 Server startup complete - camera will start on first stream request")

@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 모든 카메라 정리"""
    print("🧹 Cleaning up cameras...")
    for camera_id in list(camera_processes.keys()):
        stop_camera_stream(camera_id)

if __name__ == "__main__":
    # 신호 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # 종료 신호
    
    # atexit 핸들러 등록 (추가 안전장치)
    atexit.register(cleanup_all_processes)
    
    print("🚀 Starting simple toggle camera server on port 8001")
    print("🎯 Access web interface at: http://<your-pi-ip>:8001")
    print("🛡️ Signal handlers registered for clean shutdown")
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8001,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received")
        cleanup_all_processes()
    except Exception as e:
        print(f"❌ Server error: {e}")
        cleanup_all_processes()
    finally:
        print("👋 Server shutdown complete")
