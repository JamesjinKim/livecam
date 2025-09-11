// SHT CCTV System JavaScript
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
                
                // 해상도 변경 시 스테이터스 업데이트
                setTimeout(updateStats, 500);
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
            
            // 클라이언트 수 업데이트
            if (data.active_clients !== undefined && data.max_clients !== undefined) {
                document.getElementById('client-count').textContent = `${data.active_clients}/${data.max_clients}`;
            }
            
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
                
                // 스트리밍 중이면 lastFrameTime 업데이트
                if (isActive) {
                    lastFrameTime = Date.now();
                    updateStreamQuality(true);
                }
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
    
    // 프레임 로드 감지
    videoStream.addEventListener('load', function() {
        lastFrameTime = Date.now();
        updateStreamQuality(true);
    });
    
    // 에러 감지
    videoStream.addEventListener('error', function() {
        updateStreamQuality(false);
    });
    
    // 0.5초마다 하트비트 상태 체크
    setInterval(checkHeartbeat, 500);
    
    // 2초마다 네트워크 품질 업데이트
    setInterval(updateNetworkQuality, 2000);
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

function updateNetworkQuality() {
    // 품질 바 생성
    const filled = Math.floor(streamQuality / 10);
    const empty = 10 - filled;
    const bar = '[' + '█'.repeat(filled) + '░'.repeat(empty) + '] ' + streamQuality + '%';
    
    // 콘솔에만 표시 (필요한 경우)
    console.log('Network Quality: ' + bar);
}

// 페이지 로드 시 모니터링 시스템 시작
document.addEventListener('DOMContentLoaded', function() {
    initStreamMonitoring(); // 스트림 모니터링 시작
    updateStats(); // 즉시 한 번 실행
    setInterval(updateStats, 1000); // 1초마다 업데이트
});