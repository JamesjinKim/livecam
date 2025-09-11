"""
FastAPI 라우터 모듈
웹 인터페이스와 API 엔드포인트 관리
"""

import asyncio
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
import logging

logger = logging.getLogger(__name__)

class CCTVWebAPI:
    """CCTV 웹 API 관리 클래스"""
    
    def __init__(self, camera_manager):
        """
        Args:
            camera_manager: 카메라 관리 객체 (핵심 로직)
        """
        self.app = FastAPI()
        self.camera_manager = camera_manager
        
        # 정적 파일 서빙 설정
        self.app.mount("/static", StaticFiles(directory="web/static"), name="static")
        
        # 라우트 설정
        self.setup_routes()
    
    def setup_routes(self):
        """라우트 설정"""
        
        @self.app.get("/")
        async def index():
            """메인 페이지"""
            return FileResponse("web/static/index.html")
        
        @self.app.post("/switch/{camera_id}")
        async def switch_camera(camera_id: int):
            """카메라 전환"""
            if camera_id not in [0, 1]:
                raise HTTPException(status_code=400, detail="Invalid camera ID")
            
            success = await self.camera_manager.switch_camera(camera_id)
            
            if success:
                return {"success": True, "message": f"Switched to camera {camera_id}"}
            else:
                raise HTTPException(status_code=500, detail="Failed to switch camera")
        
        @self.app.api_route("/stream", methods=["GET", "HEAD"])
        async def video_stream(request: Request):
            """비디오 스트림"""
            client_ip = request.client.host
            
            # HEAD 요청 처리 (하트비트 체크용)
            if request.method == "HEAD":
                if self.camera_manager.is_camera_active():
                    return Response(
                        status_code=200, 
                        headers={"Content-Type": "multipart/x-mixed-replace; boundary=frame"}
                    )
                else:
                    return Response(status_code=503, headers={"Content-Type": "text/plain"})
            
            # 클라이언트 제한 확인
            if not self.camera_manager.can_accept_client(client_ip):
                max_clients = self.camera_manager.get_max_clients()
                raise HTTPException(
                    status_code=423,
                    detail=f"Maximum {max_clients} client(s) allowed. Server at capacity."
                )
            
            # 스트림 시작
            if not self.camera_manager.ensure_camera_started():
                raise HTTPException(status_code=500, detail="Failed to start camera")
            
            return StreamingResponse(
                self.camera_manager.generate_stream(client_ip),
                media_type="multipart/x-mixed-replace; boundary=frame"
            )
        
        @self.app.get("/api/stats")
        async def get_stream_stats():
            """스트리밍 통계 조회"""
            return self.camera_manager.get_stats()
        
        @self.app.post("/api/resolution/{resolution}")
        async def change_resolution(resolution: str):
            """해상도 변경"""
            success = await self.camera_manager.change_resolution(resolution)
            
            if success:
                return {"success": True, "message": f"Resolution changed to {resolution}"}
            else:
                raise HTTPException(status_code=500, detail="Failed to change resolution")
        
        @self.app.get("/exit")
        async def exit_system():
            """시스템 종료 페이지"""
            return FileResponse("web/static/exit.html")
        
        @self.app.post("/api/shutdown")
        async def shutdown_system():
            """시스템 안전 종료"""
            logger.info("[SHUTDOWN] System shutdown requested via web interface")
            
            # 카메라 관리자를 통해 종료
            await self.camera_manager.shutdown()
            
            # uvicorn 서버 강제 종료
            import os
            import signal
            import threading
            import time
            
            def force_shutdown():
                time.sleep(1)
                os._exit(0)  # 즉시 종료
            
            shutdown_thread = threading.Thread(target=force_shutdown)
            shutdown_thread.daemon = True
            shutdown_thread.start()
            
            return {"success": True, "message": "System shutting down"}