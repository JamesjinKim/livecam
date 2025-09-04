#!/usr/bin/env python3
"""
통합 제어 시스템
기존 토글 스트리밍 (main.py) + 새로운 듀얼 모션 블랙박스 (motion_blackbox.py) 관리
"""

import subprocess
import time
import signal
import threading
import psutil
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI()

# 전역 변수
toggle_streaming_process = None  # 기존 main.py (포트 8001)
motion_blackbox_process = None   # 새로운 motion_blackbox.py

# 프로세스 관리
def start_toggle_streaming():
    """기존 토글 스트리밍 시작 (main.py)"""
    global toggle_streaming_process
    
    if toggle_streaming_process and toggle_streaming_process.poll() is None:
        print("📹 토글 스트리밍 이미 실행 중")
        return True
    
    try:
        # main.py 실행 (포트 8001)
        cmd = ["python3", "/home/shinho/shinho/livecam/main.py"]
        toggle_streaming_process = subprocess.Popen(cmd, 
                                                   stdout=subprocess.PIPE, 
                                                   stderr=subprocess.PIPE)
        print(f"📹 토글 스트리밍 시작 (PID: {toggle_streaming_process.pid}, 포트: 8001)")
        return True
    except Exception as e:
        print(f"❌ 토글 스트리밍 시작 실패: {e}")
        return False

def stop_toggle_streaming():
    """기존 토글 스트리밍 종료"""
    global toggle_streaming_process
    
    if toggle_streaming_process and toggle_streaming_process.poll() is None:
        try:
            # 정상 종료 시도
            toggle_streaming_process.send_signal(signal.SIGINT)
            
            try:
                toggle_streaming_process.wait(timeout=5)
                print("🛑 토글 스트리밍 정상 종료")
            except subprocess.TimeoutExpired:
                # 강제 종료
                toggle_streaming_process.kill()
                toggle_streaming_process.wait(timeout=2)
                print("⚠️ 토글 스트리밍 강제 종료")
            
            toggle_streaming_process = None
            return True
        except Exception as e:
            print(f"❌ 토글 스트리밍 종료 실패: {e}")
            return False
    return True

def start_motion_blackbox():
    """듀얼 카메라 모션 블랙박스 시작"""
    global motion_blackbox_process
    
    if motion_blackbox_process and motion_blackbox_process.poll() is None:
        print("🛡️ 모션 블랙박스 이미 실행 중")
        return True
    
    try:
        # motion_blackbox.py 실행
        cmd = ["python3", "/home/shinho/shinho/livecam/motion_blackbox.py"]
        motion_blackbox_process = subprocess.Popen(cmd, 
                                                  stdout=subprocess.PIPE, 
                                                  stderr=subprocess.PIPE)
        print(f"🛡️ 듀얼 카메라 모션 블랙박스 시작 (PID: {motion_blackbox_process.pid})")
        return True
    except Exception as e:
        print(f"❌ 모션 블랙박스 시작 실패: {e}")
        return False

def stop_motion_blackbox():
    """듀얼 카메라 모션 블랙박스 종료"""
    global motion_blackbox_process
    
    if motion_blackbox_process and motion_blackbox_process.poll() is None:
        try:
            # 정상 종료 시도
            motion_blackbox_process.send_signal(signal.SIGINT)
            
            try:
                motion_blackbox_process.wait(timeout=5)
                print("🛑 모션 블랙박스 정상 종료")
            except subprocess.TimeoutExpired:
                # 강제 종료
                motion_blackbox_process.kill()
                motion_blackbox_process.wait(timeout=2)
                print("⚠️ 모션 블랙박스 강제 종료")
            
            motion_blackbox_process = None
            return True
        except Exception as e:
            print(f"❌ 모션 블랙박스 종료 실패: {e}")
            return False
    return True

def get_system_status():
    """통합 시스템 상태 조회"""
    toggle_running = toggle_streaming_process and toggle_streaming_process.poll() is None
    blackbox_running = motion_blackbox_process and motion_blackbox_process.poll() is None
    
    return {
        "toggle_streaming": {
            "running": toggle_running,
            "pid": toggle_streaming_process.pid if toggle_running else None,
            "port": 8001,
            "description": "기존 카메라 0↔1 토글 스트리밍"
        },
        "motion_blackbox": {
            "running": blackbox_running,
            "pid": motion_blackbox_process.pid if blackbox_running else None,
            "description": "카메라 0,1 동시 모션 감지 블랙박스"
        },
        "integration_controller": {
            "running": True,
            "port": 8080,
            "description": "통합 제어 시스템"
        }
    }

# FastAPI 라우트
@app.get("/")
async def root():
    """통합 제어판 메인 페이지"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>통합 제어 시스템</title>
        <meta charset="UTF-8">
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 0; padding: 20px;
                background: #f5f5f5;
                min-height: 100vh;
            }
            .container {
                max-width: 1000px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            h1 { 
                color: #333; 
                text-align: center; 
                margin-bottom: 30px;
                font-size: 28px;
            }
            .system-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
                margin: 30px 0;
            }
            .system-card {
                border: 2px solid #dee2e6;
                border-radius: 10px;
                padding: 25px;
                background: #f8f9fa;
            }
            .system-card h2 {
                color: #495057;
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .status-indicator {
                display: inline-block;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 8px;
            }
            .status-running {
                background: #28a745;
            }
            .status-stopped {
                background: #dc3545;
            }
            .status-disabled {
                background: #6c757d;
            }
            button {
                font-size: 14px;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                transition: all 0.3s;
                margin: 5px;
                min-width: 120px;
            }
            .btn-primary {
                background: #007bff;
                color: white;
            }
            .btn-primary:hover {
                background: #0056b3;
            }
            .btn-success {
                background: #28a745;
                color: white;
            }
            .btn-success:hover {
                background: #1e7e34;
            }
            .btn-danger {
                background: #dc3545;
                color: white;
            }
            .btn-danger:hover {
                background: #c82333;
            }
            .btn-secondary {
                background: #6c757d;
                color: white;
            }
            .btn-disabled {
                background: #6c757d;
                cursor: not-allowed;
            }
            .description {
                color: #6c757d;
                font-size: 14px;
                margin: 15px 0;
                line-height: 1.4;
            }
            .overall-status {
                text-align: center;
                margin: 20px 0;
                padding: 20px;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
            }
            .status-info {
                background: #d1ecf1;
                color: #0c5460;
                border: 1px solid #bee5eb;
            }
            .button-group {
                margin-top: 15px;
            }
            .access-link {
                display: inline-block;
                margin: 5px;
                padding: 8px 16px;
                background: #17a2b8;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-size: 13px;
                min-width: 100px;
                text-align: center;
            }
            .access-link:hover {
                background: #138496;
                text-decoration: none;
                color: white;
            }
            .access-link:disabled {
                background: #6c757d;
                cursor: not-allowed;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>라즈베리파이 통합 제어 시스템</h1>
            
            <div class="overall-status status-info" id="overall-status">
                시스템 상태 로딩 중...
            </div>
            
            <div class="system-grid">
                <!-- 기존 토글 스트리밍 -->
                <div class="system-card">
                    <h2>
                        토글 스트리밍 시스템
                        <span class="status-indicator" id="toggle-status"></span>
                    </h2>
                    
                    <div class="description">
                        기존 main.py 시스템 (그대로 유지)<br>
                        카메라 0번 ↔ 카메라 1번 교차 스트리밍<br>
                        웹 UI로 카메라 토글 가능<br>
                        포트: 8001<br>
                        <strong>권장: 1개 클라이언트만 접속</strong>
                    </div>
                    
                    <div class="button-group">
                        <button class="btn-success" onclick="controlToggleStreaming('start')">
                            서비스 시작
                        </button>
                        <button class="btn-danger" onclick="controlToggleStreaming('stop')">
                            서비스 중지
                        </button>
                        <a href="#" target="_blank" class="access-link" id="streaming-link">
                            스트리밍 화면
                        </a>
                    </div>
                    
                    <div id="toggle-info" style="margin-top: 15px; font-size: 12px; color: #6c757d;">
                        상태: 확인 중...
                    </div>
                </div>
                
                <!-- 듀얼 모션 블랙박스 -->
                <div class="system-card">
                    <h2>
                        모션 감지 블랙박스
                        <span class="status-indicator" id="blackbox-status"></span>
                    </h2>
                    
                    <div class="description">
                        새로운 motion_blackbox.py 시스템<br>
                        <strong>카메라 0번, 1번 동시 모션 감지</strong><br>
                        모션 감지시 전후 1.5분씩 총 3분 녹화<br>
                        자동 저장 관리 (7일 보관)<br>
                        백그라운드 24/7 자동 감시
                    </div>
                    
                    <div class="button-group">
                        <button class="btn-success" onclick="controlMotionBlackbox('start')">
                            시작
                        </button>
                        <button class="btn-danger" onclick="controlMotionBlackbox('stop')">
                            중지
                        </button>
                    </div>
                    
                    <div id="blackbox-info" style="margin-top: 15px; font-size: 12px; color: #6c757d;">
                        상태: 확인 중...
                    </div>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 40px; color: #6c757d;">
                <p><strong>시스템 구성:</strong></p>
                <p>토글 스트리밍: 기존 main.py 그대로 유지 (카메라 0↔1 교차)</p>
                <p>모션 감지 블랙박스: 새로운 기능 (카메라 0,1 동시 감지)</p>
                <p>독립 실행: 두 시스템은 서로 간섭 없이 동시 동작 가능</p>
                <p>주의사항: 토글 스트리밍은 1개 클라이언트만 접속 권장</p>
            </div>
        </div>
        
        <script>
            let statusInterval;
            
            function controlToggleStreaming(action) {
                const url = `/api/toggle-streaming/${action}`;
                
                fetch(url, { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            console.log(`Toggle streaming ${action} success`);
                            updateStatus();
                        } else {
                            alert(`토글 스트리밍 ${action} 실패: ${data.message}`);
                        }
                    })
                    .catch(error => {
                        console.error('Toggle streaming control error:', error);
                        alert(`토글 스트리밍 제어 오류: ${error.message}`);
                    });
            }
            
            function controlMotionBlackbox(action) {
                const url = `/api/motion-blackbox/${action}`;
                
                fetch(url, { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            console.log(`Motion blackbox ${action} success`);
                            updateStatus();
                        } else {
                            alert(`모션 블랙박스 ${action} 실패: ${data.message}`);
                        }
                    })
                    .catch(error => {
                        console.error('Motion blackbox control error:', error);
                        alert(`모션 블랙박스 제어 오류: ${error.message}`);
                    });
            }
            
            function updateStatus() {
                fetch('/api/status')
                    .then(response => response.json())
                    .then(data => {
                        // 토글 스트리밍 상태 및 링크 업데이트
                        const toggleStatus = document.getElementById('toggle-status');
                        const toggleInfo = document.getElementById('toggle-info');
                        const streamingLink = document.getElementById('streaming-link');
                        
                        if (data.toggle_streaming.running) {
                            toggleStatus.className = 'status-indicator status-running';
                            toggleInfo.innerHTML = `상태: 실행 중 (PID: ${data.toggle_streaming.pid})`;
                            streamingLink.href = `http://${window.location.hostname}:8001`;
                        } else {
                            toggleStatus.className = 'status-indicator status-stopped';
                            toggleInfo.innerHTML = '상태: 중지됨';
                            streamingLink.href = '#';
                        }
                        
                        // 모션 블랙박스 상태
                        const blackboxStatus = document.getElementById('blackbox-status');
                        const blackboxInfo = document.getElementById('blackbox-info');
                        
                        if (data.motion_blackbox.running) {
                            blackboxStatus.className = 'status-indicator status-running';
                            blackboxInfo.innerHTML = `상태: 실행 중 (PID: ${data.motion_blackbox.pid})`;
                        } else {
                            blackboxStatus.className = 'status-indicator status-stopped';
                            blackboxInfo.innerHTML = '상태: 중지됨';
                        }
                        
                        // 전체 상태
                        const overallStatus = document.getElementById('overall-status');
                        const runningServices = [];
                        
                        if (data.toggle_streaming.running) runningServices.push('토글 스트리밍');
                        if (data.motion_blackbox.running) runningServices.push('모션 블랙박스');
                        
                        if (runningServices.length > 0) {
                            overallStatus.textContent = `실행 중인 서비스: ${runningServices.join(', ')}`;
                        } else {
                            overallStatus.textContent = '모든 서비스 중지됨';
                        }
                    })
                    .catch(error => {
                        console.error('Status update error:', error);
                        document.getElementById('overall-status').textContent = '상태 업데이트 오류';
                    });
            }
            
            // 페이지 로드 시 상태 업데이트 시작
            document.addEventListener('DOMContentLoaded', function() {
                updateStatus(); // 즉시 한 번 실행
                statusInterval = setInterval(updateStatus, 3000); // 3초마다 업데이트
            });
            
            // 페이지 언로드 시 정리
            window.addEventListener('beforeunload', function() {
                if (statusInterval) clearInterval(statusInterval);
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/status")
async def get_status():
    """통합 시스템 상태 조회 API"""
    return JSONResponse(get_system_status())

@app.post("/api/toggle-streaming/{action}")
async def control_toggle_streaming(action: str):
    """토글 스트리밍 제어 API"""
    if action not in ["start", "stop"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'start' or 'stop'")
    
    try:
        if action == "start":
            success = start_toggle_streaming()
            message = "토글 스트리밍 시작됨" if success else "토글 스트리밍 시작 실패"
        else:
            success = stop_toggle_streaming()
            message = "토글 스트리밍 중지됨" if success else "토글 스트리밍 중지 실패"
        
        return {"success": success, "message": message}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Toggle streaming control error: {str(e)}")

@app.post("/api/motion-blackbox/{action}")
async def control_motion_blackbox(action: str):
    """모션 블랙박스 제어 API"""
    if action not in ["start", "stop"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'start' or 'stop'")
    
    try:
        if action == "start":
            success = start_motion_blackbox()
            message = "모션 블랙박스 시작됨" if success else "모션 블랙박스 시작 실패"
        else:
            success = stop_motion_blackbox()
            message = "모션 블랙박스 중지됨" if success else "모션 블랙박스 중지 실패"
        
        return {"success": success, "message": message}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Motion blackbox control error: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기 설정"""
    print("🚀 통합 제어 시스템 시작")
    print("   기존 토글 스트리밍 (main.py) + 새로운 모션 블랙박스 (motion_blackbox.py)")
    
    # 기본적으로 모션 블랙박스만 자동 시작
    print("🛡️ 모션 블랙박스 자동 시작...")
    start_motion_blackbox()

@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 모든 프로세스 정리"""
    print("🧹 모든 서비스 정리 중...")
    stop_toggle_streaming()
    stop_motion_blackbox()

if __name__ == "__main__":
    print("🚀 Starting integrated controller on port 8080")
    print("🎯 Control panel: http://<your-pi-ip>:8080")
    print("📹 Toggle streaming: http://<your-pi-ip>:8001 (when started)")
    print("")
    print("🔄 서비스 구성:")
    print("   • 통합 제어: 포트 8080 (이 서버)")
    print("   • 토글 스트리밍: 포트 8001 (main.py - 1 클라이언트 권장)")
    print("   • 모션 블랙박스: 백그라운드 (motion_blackbox.py - 듀얼 카메라 동시 감지)")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )