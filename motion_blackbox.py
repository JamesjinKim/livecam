#!/usr/bin/env python3
"""
스마트 모션 감지 블랙박스 시스템 - rpicam-vid 기반
카메라 0번, 1번 동시 모션 감지 - PipeWire 호환
"""

import cv2
import time
import subprocess
import threading
import signal
import sys
import os
import shutil
import glob
import numpy as np
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
import io
from PIL import Image


class RPiCameraCapture:
    """rpicam-vid 기반 카메라 캡처 클래스"""
    
    def __init__(self, camera_id, resolution=(640, 480), fps=30):
        """
        Args:
            camera_id (int): 카메라 ID
            resolution (tuple): 해상도 (width, height)
            fps (int): 프레임레이트
        """
        self.camera_id = camera_id
        self.width, self.height = resolution
        self.fps = fps
        self.process = None
        self.running = False
        self.frame_queue = deque(maxlen=5)  # 최대 5프레임 버퍼
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        print(f"📹 rpicam 캡처 초기화: 카메라 {camera_id}, {self.width}x{self.height}")
    
    def start(self):
        """카메라 스트림 시작"""
        if self.running:
            return
        
        cmd = [
            "rpicam-vid",
            "--camera", str(self.camera_id),
            "--width", str(self.width),
            "--height", str(self.height),
            "--framerate", str(self.fps),
            "--timeout", "0",  # 무한 실행
            "--nopreview",
            "--codec", "mjpeg",
            "--quality", "80",
            "--flush", "1",
            "--output", "-"  # stdout으로 출력
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            self.running = True
            
            # 프레임 읽기 스레드 시작
            self.capture_thread = threading.Thread(target=self._capture_frames, daemon=True)
            self.capture_thread.start()
            
            print(f"✅ 카메라 {self.camera_id} 스트림 시작됨")
            return True
            
        except Exception as e:
            print(f"❌ 카메라 {self.camera_id} 시작 실패: {e}")
            return False
    
    def _capture_frames(self):
        """MJPEG 스트림에서 프레임 추출"""
        buffer = b""
        
        while self.running and self.process:
            try:
                # 데이터 읽기 (4KB 청크)
                chunk = self.process.stdout.read(4096)
                if not chunk:
                    break
                
                buffer += chunk
                
                # JPEG 프레임 찾기
                while b'\xff\xd8' in buffer and b'\xff\xd9' in buffer:
                    # JPEG 시작과 끝 찾기
                    start_idx = buffer.find(b'\xff\xd8')
                    end_idx = buffer.find(b'\xff\xd9', start_idx) + 2
                    
                    if start_idx != -1 and end_idx > start_idx:
                        # JPEG 프레임 추출
                        jpeg_frame = buffer[start_idx:end_idx]
                        buffer = buffer[end_idx:]
                        
                        # JPEG를 OpenCV 프레임으로 변환
                        try:
                            frame = cv2.imdecode(
                                np.frombuffer(jpeg_frame, dtype=np.uint8),
                                cv2.IMREAD_COLOR
                            )
                            
                            if frame is not None:
                                with self.frame_lock:
                                    self.current_frame = frame.copy()
                        
                        except Exception as e:
                            continue
                    else:
                        break
            
            except Exception as e:
                if self.running:
                    print(f"⚠️ 카메라 {self.camera_id} 프레임 읽기 오류: {e}")
                break
        
        print(f"📹 카메라 {self.camera_id} 캡처 스레드 종료")
    
    def read(self):
        """프레임 읽기 (OpenCV VideoCapture 호환)"""
        with self.frame_lock:
            if self.current_frame is not None:
                return True, self.current_frame.copy()
            else:
                return False, None
    
    def isOpened(self):
        """카메라 상태 확인"""
        return self.running and self.process is not None
    
    def release(self):
        """카메라 해제"""
        print(f"📹 카메라 {self.camera_id} 해제 중...")
        self.running = False
        
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            except Exception:
                pass
            
            self.process = None
        
        print(f"✅ 카메라 {self.camera_id} 해제 완료")


class CircularVideoBuffer:
    """1.5분 순환 버퍼 (모션 감지 전 구간 보관)"""
    
    def __init__(self, duration=90, fps=30):
        """
        Args:
            duration (int): 버퍼 지속시간 (초) - 기본 90초 (1.5분)
            fps (int): 프레임레이트 - 기본 30fps
        """
        self.buffer_size = duration * fps  # 90초 × 30fps = 2700프레임
        self.fps = fps
        self.duration = duration
        
        # 프레임과 타임스탬프 순환 버퍼
        self.frame_buffer = deque(maxlen=self.buffer_size)
        self.timestamp_buffer = deque(maxlen=self.buffer_size)
        
        print(f"📹 순환 버퍼 초기화: {duration}초 ({self.buffer_size}프레임)")
    
    def add_frame(self, frame, timestamp=None):
        """프레임을 순환 버퍼에 추가"""
        if timestamp is None:
            timestamp = time.time()
            
        self.frame_buffer.append(frame.copy())
        self.timestamp_buffer.append(timestamp)
    
    def get_buffered_frames(self):
        """현재 버퍼의 모든 프레임 반환 (모션 감지 시 사용)"""
        return list(self.frame_buffer), list(self.timestamp_buffer)
    
    def get_buffer_info(self):
        """버퍼 상태 정보"""
        return {
            "frame_count": len(self.frame_buffer),
            "duration_sec": len(self.frame_buffer) / self.fps,
            "is_full": len(self.frame_buffer) == self.buffer_size
        }


class AdvancedMotionDetector:
    """OpenCV BackgroundSubtractorMOG2 기반 모션 감지"""
    
    def __init__(self, sensitivity='medium'):
        """
        Args:
            sensitivity (str): 'low', 'medium', 'high' - 감도 설정
        """
        # 감도별 파라미터 설정
        sensitivity_params = {
            'low': {'threshold': 70, 'min_area': 8000, 'history': 200},
            'medium': {'threshold': 50, 'min_area': 5000, 'history': 500}, 
            'high': {'threshold': 30, 'min_area': 2000, 'history': 1000}
        }
        
        params = sensitivity_params.get(sensitivity, sensitivity_params['medium'])
        
        # MOG2 배경 차분 알고리즘 초기화
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=False,        # 그림자 감지 비활성화 (성능 향상)
            varThreshold=params['threshold'],  # 변화 감지 임계값
            history=params['history']          # 배경 학습 히스토리
        )
        
        # 모션 감지 파라미터
        self.min_contour_area = params['min_area']  # 최소 윤곽 면적
        self.motion_detected_time = 0
        self.motion_cooldown = 5  # 5초 쿨다운 (연속 감지 방지)
        
        # 형태학적 연산용 커널
        self.morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        
        print(f"🎯 모션 감지 초기화: {sensitivity} 감도")
        print(f"   임계값: {params['threshold']}, 최소면적: {params['min_area']}")
    
    def detect_motion(self, frame):
        """
        프레임에서 모션 감지 수행
        
        Args:
            frame (numpy.ndarray): 입력 프레임
            
        Returns:
            tuple: (motion_detected: bool, debug_info: dict)
        """
        current_time = time.time()
        
        # 쿨다운 중이면 감지하지 않음
        if current_time - self.motion_detected_time < self.motion_cooldown:
            return False, {"status": "cooldown", "remaining": self.motion_cooldown - (current_time - self.motion_detected_time)}
        
        # 그레이스케일 변환 (성능 최적화)
        if len(frame.shape) == 3:
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray_frame = frame
        
        # 배경 차분 적용
        fg_mask = self.bg_subtractor.apply(gray_frame)
        
        # 노이즈 제거 (형태학적 연산)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.morph_kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.morph_kernel)
        
        # 윤곽 검출
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 임계값 이상의 윤곽 검사
        significant_contours = []
        total_motion_area = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > self.min_contour_area:
                significant_contours.append(contour)
                total_motion_area += area
        
        # 모션 감지 여부 결정
        motion_detected = len(significant_contours) > 0
        
        if motion_detected:
            self.motion_detected_time = current_time
            print(f"🚨 모션 감지됨! 윤곽 수: {len(significant_contours)}, 총 면적: {total_motion_area}")
        
        debug_info = {
            "contour_count": len(significant_contours),
            "total_area": total_motion_area,
            "threshold_area": self.min_contour_area,
            "status": "detected" if motion_detected else "no_motion"
        }
        
        return motion_detected, debug_info


class MP4EventRecorder:
    """모션 이벤트 MP4 녹화 클래스 (rpicam-vid 기반)"""
    
    def __init__(self, camera_id=1, resolution=(640, 480), quality=80):
        """
        Args:
            camera_id (int): 카메라 ID
            resolution (tuple): 해상도 (width, height)
            quality (int): MJPEG 품질 (0-100)
        """
        self.camera_id = camera_id
        self.width, self.height = resolution
        self.quality = quality
        self.fps = 30
        
        # 저장 디렉터리 설정
        self.base_dir = Path("videos/events")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📹 MP4 레코더 초기화: 카메라 {camera_id}, {self.width}x{self.height}")
    
    def record_motion_event(self, pre_frames, pre_timestamps):
        """
        모션 이벤트 녹화 (rpicam-vid 직접 사용하여 180초 녹화)
        
        Args:
            pre_frames (list): 모션 감지 전 프레임들 (표시용)
            pre_timestamps (list): 해당 타임스탬프들 (표시용)
            
        Returns:
            str: 저장된 파일 경로
        """
        # 이벤트 시간 기반 파일명 생성 (카메라 ID 포함) - MP4 형식으로 변경
        event_time = datetime.now()
        filename = f"motion_event_cam{self.camera_id}_{event_time:%Y%m%d_%H%M%S}.mp4"
        
        # 월별 폴더 생성
        month_dir = self.base_dir / f"{event_time:%Y-%m}"
        month_dir.mkdir(exist_ok=True)
        
        filepath = month_dir / filename
        
        print(f"🎬 모션 이벤트 녹화 시작: {filepath}")
        print(f"   rpicam-vid 직접 녹화: 180초 (3분) 예정")
        
        try:
            # rpicam-vid로 직접 3분(180초) MP4 녹화
            cmd = [
                "rpicam-vid",
                "--camera", str(self.camera_id),
                "--width", str(self.width),
                "--height", str(self.height),
                "--framerate", str(self.fps),
                "--timeout", str(180 * 1000),  # 180초 = 3분
                "--nopreview",
                "--codec", "h264",  # H.264 하드웨어 인코딩
                "--output", str(filepath)
            ]
            
            print(f"🎥 rpicam-vid 3분 녹화 시작...")
            start_time = time.time()
            
            # rpicam-vid 실행 (블로킹 방식)
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=190)  # 여유시간 10초
            
            elapsed = time.time() - start_time
            
            if result.returncode == 0:
                # 파일 정보 출력
                if filepath.exists():
                    file_size = filepath.stat().st_size / (1024 * 1024)  # MB
                    print(f"✅ 모션 이벤트 녹화 완료: {file_size:.1f}MB ({elapsed:.1f}초)")
                    return str(filepath)
                else:
                    print("❌ 파일이 생성되지 않았습니다")
                    return None
            else:
                print(f"⚠️ rpicam-vid 실행 오류: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print(f"⏰ 녹화 타임아웃 (정상 완료 가능성 있음)")
            if filepath.exists():
                file_size = filepath.stat().st_size / (1024 * 1024)
                print(f"✅ 타임아웃 후 파일 확인됨: {file_size:.1f}MB")
                return str(filepath)
            return None
        except Exception as e:
            print(f"❌ 녹화 실패: {e}")
            return None
    


class StorageManager:
    """자동 저장 관리 시스템"""
    
    def __init__(self, base_path="videos/events", max_storage_gb=25):
        """
        Args:
            base_path (str): 기본 저장 경로
            max_storage_gb (int): 최대 저장 용량 (GB)
        """
        self.base_path = Path(base_path)
        self.max_storage_bytes = max_storage_gb * 1024 * 1024 * 1024
        
        # 보관 정책 설정
        self.retention_policy = {
            "daily_events": 7,      # 일반 이벤트: 7일 보관
            "important_events": 30,  # 중요 이벤트: 30일 보관 (향후 기능)
            "emergency_cleanup": 3   # 비상시: 3일만 보관
        }
        
        print(f"💾 저장 관리자 초기화: 최대 {max_storage_gb}GB")
        
    def check_and_cleanup(self):
        """저장 공간 확인 및 정리 실행"""
        print("🧹 저장 공간 관리 시작...")
        
        # 1. 현재 사용량 확인
        current_usage = self._calculate_directory_size()
        free_space = self._get_free_space()
        
        print(f"   현재 사용량: {current_usage / (1024**3):.1f}GB")
        print(f"   남은 공간: {free_space / (1024**3):.1f}GB")
        
        # 2. 정리 필요 여부 판단
        cleanup_needed = (
            current_usage > self.max_storage_bytes * 0.8 or  # 80% 이상 사용
            free_space < 1 * 1024**3  # 1GB 미만 남음
        )
        
        if cleanup_needed:
            print("⚠️ 저장 공간 부족! 자동 정리 시작...")
            self._perform_cleanup()
        else:
            # 일반적인 보관 정책 적용
            self._apply_retention_policy()
        
        print("✅ 저장 공간 관리 완료")
    
    def _calculate_directory_size(self):
        """디렉터리 총 사용량 계산"""
        total_size = 0
        if self.base_path.exists():
            for file_path in self.base_path.rglob("*.mjpeg"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        return total_size
    
    def _get_free_space(self):
        """사용 가능한 디스크 공간 확인"""
        total, used, free = shutil.disk_usage(self.base_path)
        return free
    
    def _apply_retention_policy(self):
        """일반 보관 정책 적용"""
        current_time = datetime.now()
        cutoff_date = current_time - timedelta(days=self.retention_policy["daily_events"])
        
        removed_count = 0
        removed_size = 0
        
        print(f"📅 보관 정책 적용: {self.retention_policy['daily_events']}일 이전 파일 삭제")
        
        if self.base_path.exists():
            for file_path in self.base_path.rglob("*.mjpeg"):
                if file_path.is_file():
                    # 파일 생성 시간 확인
                    file_time = datetime.fromtimestamp(file_path.stat().st_ctime)
                    
                    if file_time < cutoff_date:
                        file_size = file_path.stat().st_size
                        
                        try:
                            file_path.unlink()
                            removed_count += 1
                            removed_size += file_size
                            
                            print(f"🗑️ 삭제됨: {file_path.name}")
                        except Exception as e:
                            print(f"❌ 삭제 실패 {file_path.name}: {e}")
        
        if removed_count > 0:
            print(f"📊 정리 완료: {removed_count}개 파일, {removed_size/(1024**2):.1f}MB 확보")
        else:
            print("📋 삭제할 파일 없음")
        
        # 빈 폴더 정리
        self._cleanup_empty_directories()
    
    def _perform_cleanup(self):
        """비상 정리 수행 (오래된 파일부터 삭제)"""
        print("🚨 비상 정리 모드 실행")
        
        # 모든 파일을 생성시간순으로 정렬
        all_files = []
        if self.base_path.exists():
            for file_path in self.base_path.rglob("*.mjpeg"):
                if file_path.is_file():
                    stat = file_path.stat()
                    all_files.append((stat.st_ctime, stat.st_size, file_path))
        
        # 생성시간순 정렬 (오래된 것부터)
        all_files.sort(key=lambda x: x[0])
        
        # 전체 파일의 30%를 삭제 (비상 정리)
        files_to_delete = len(all_files) // 3
        total_freed = 0
        
        print(f"🗑️ {files_to_delete}개 파일 삭제 예정")
        
        for i in range(min(files_to_delete, len(all_files))):
            _, file_size, file_path = all_files[i]
            
            try:
                file_path.unlink()
                total_freed += file_size
                print(f"🗑️ 비상삭제: {file_path.name}")
            except Exception as e:
                print(f"❌ 삭제 실패 {file_path.name}: {e}")
        
        print(f"✅ 비상 정리 완료: {total_freed/(1024**2):.1f}MB 확보")
        
        self._cleanup_empty_directories()
    
    def _cleanup_empty_directories(self):
        """빈 디렉터리 정리"""
        if self.base_path.exists():
            for dir_path in sorted(self.base_path.rglob("*"), reverse=True):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    try:
                        dir_path.rmdir()
                        print(f"📁 빈 폴더 삭제: {dir_path.name}")
                    except Exception:
                        pass  # 삭제 실패는 무시
    
    def get_storage_stats(self):
        """저장 공간 통계 반환"""
        current_usage = self._calculate_directory_size()
        free_space = self._get_free_space()
        
        # 파일 개수 계산
        file_count = 0
        if self.base_path.exists():
            file_count = len(list(self.base_path.rglob("*.mjpeg")))
        
        return {
            "used_bytes": current_usage,
            "used_gb": current_usage / (1024**3),
            "free_bytes": free_space,
            "free_gb": free_space / (1024**3),
            "file_count": file_count,
            "usage_percent": (current_usage / (self.max_storage_bytes)) * 100
        }


class DualCameraMotionBlackbox:
    """듀얼 카메라 동시 모션 감지 블랙박스 시스템 - rpicam-vid 기반"""
    
    def __init__(self, resolution=(640, 480), sensitivity='medium'):
        """
        Args:
            resolution (tuple): 해상도
            sensitivity (str): 모션 감지 감도
        """
        print("🚀 듀얼 카메라 모션 블랙박스 초기화...")
        
        self.resolution = resolution
        self.running = False
        
        # 듀얼 카메라 설정
        self.cameras = {}
        self.circular_buffers = {}
        self.motion_detectors = {}
        
        # 각 카메라별 초기화
        for cam_id in [0, 1]:
            print(f"📹 카메라 {cam_id} 초기화 중...")
            
            # rpicam-vid 기반 카메라 초기화
            camera = RPiCameraCapture(cam_id, resolution, fps=30)
            if not camera.start():
                print(f"⚠️ 카메라 {cam_id}을 열 수 없습니다. 건너뜀.")
                continue
            
            self.cameras[cam_id] = camera
            self.circular_buffers[cam_id] = CircularVideoBuffer(duration=90, fps=30)
            self.motion_detectors[cam_id] = AdvancedMotionDetector(sensitivity=sensitivity)
            
            # 배경 학습을 위한 초기 대기
            time.sleep(1)
            
            print(f"✅ 카메라 {cam_id} 준비 완료")
        
        if not self.cameras:
            raise RuntimeError("사용 가능한 카메라가 없습니다")
        
        # 공통 구성 요소
        self.storage_manager = StorageManager()
        
        # 통계 변수
        self.stats = {
            "total_frames": {cam_id: 0 for cam_id in self.cameras.keys()},
            "motion_events": {cam_id: 0 for cam_id in self.cameras.keys()},
            "last_motion_time": {cam_id: None for cam_id in self.cameras.keys()},
            "start_time": time.time()
        }
        
        # 신호 처리 설정
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("✅ 듀얼 카메라 시스템 초기화 완료")
        print(f"   활성 카메라: {list(self.cameras.keys())}")
        print(f"   해상도: {resolution[0]}x{resolution[1]}")
        print(f"   감도: {sensitivity}")
        print(f"   버퍼: 1.5분 (2700프레임) × {len(self.cameras)}대")
    
    def start(self):
        """메인 루프 시작"""
        print("🎬 스마트 블랙박스 시작!")
        print("   모션 감지 대기 중... (Ctrl+C로 종료)")
        
        self.running = True
        
        # 백그라운드 작업 시작
        storage_thread = threading.Thread(target=self._storage_management_loop, daemon=True)
        storage_thread.start()
        
        try:
            self._main_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()
    
    def _main_loop(self):
        """듀얼 카메라 메인 처리 루프"""
        last_status_time = time.time()
        frame_count = 0
        
        while self.running:
            current_time = time.time()
            
            # 각 카메라별로 프레임 처리
            for cam_id, camera in self.cameras.items():
                try:
                    # 프레임 읽기
                    ret, frame = camera.read()
                    if not ret or frame is None:
                        continue
                    
                    self.stats["total_frames"][cam_id] += 1
                    frame_count += 1
                    
                    # 순환 버퍼에 프레임 추가
                    self.circular_buffers[cam_id].add_frame(frame, current_time)
                    
                    # 모션 감지 수행 (매 10프레임마다 - 성능 최적화)
                    if frame_count % 10 == 0:
                        motion_detected, debug_info = self.motion_detectors[cam_id].detect_motion(frame)
                        
                        # 모션 이벤트 처리
                        if motion_detected:
                            self._handle_motion_event(cam_id)
                        
                except Exception as e:
                    print(f"❌ 카메라 {cam_id} 처리 오류: {e}")
                    continue
            
            # 주기적 상태 출력 (30초마다)
            if current_time - last_status_time > 30:
                self._print_status()
                last_status_time = current_time
            
            # CPU 부하 조절
            time.sleep(0.1)  # 100ms 대기 (rpicam 스트림 처리를 위해 조정)
    
    def _handle_motion_event(self, cam_id):
        """모션 이벤트 처리"""
        print(f"🚨 카메라 {cam_id}에서 모션 감지! 이벤트 녹화 시작...")
        
        # 해당 카메라 버퍼의 프레임들 가져오기
        pre_frames, pre_timestamps = self.circular_buffers[cam_id].get_buffered_frames()
        
        # 백그라운드에서 녹화 수행 (메인 루프 블로킹 방지)
        recording_thread = threading.Thread(
            target=self._record_event,
            args=(cam_id, pre_frames, pre_timestamps),
            daemon=True
        )
        recording_thread.start()
        
        # 활성 녹화 스레드 추적
        if not hasattr(self, 'active_recordings'):
            self.active_recordings = []
        self.active_recordings.append(recording_thread)
        
        # 통계 업데이트
        self.stats["motion_events"][cam_id] += 1
        self.stats["last_motion_time"][cam_id] = time.time()
    
    def _record_event(self, cam_id, pre_frames, pre_timestamps):
        """이벤트 녹화 (별도 스레드에서 실행)"""
        try:
            print(f"🔄 카메라 {cam_id} 모션 감지 스트림 임시 중단...")
            
            # 해당 카메라 스트림 임시 중단
            camera_capture = self.cameras.get(cam_id)
            if camera_capture:
                camera_capture.release()
                time.sleep(2)  # 카메라 해제 대기
            
            # 카메라별 이벤트 레코더 생성
            event_recorder = MP4EventRecorder(cam_id, self.resolution)
            
            # 녹화 시작
            filepath = event_recorder.record_motion_event(pre_frames, pre_timestamps)
            
            # 모션 감지용 카메라 재시작
            print(f"🔄 카메라 {cam_id} 모션 감지 스트림 재시작...")
            new_camera = RPiCameraCapture(cam_id, self.resolution, fps=30)
            if new_camera.start():
                self.cameras[cam_id] = new_camera
                print(f"✅ 카메라 {cam_id} 재시작 완료")
            else:
                print(f"❌ 카메라 {cam_id} 재시작 실패")
            
            if filepath:
                print(f"📁 카메라 {cam_id} 이벤트 녹화 완료: {Path(filepath).name}")
            else:
                print(f"❌ 카메라 {cam_id} 이벤트 녹화 실패")
                
        except Exception as e:
            print(f"❌ 카메라 {cam_id} 녹화 오류: {e}")
            # 오류 발생 시에도 카메라 재시작 시도
            try:
                print(f"🔄 오류 복구: 카메라 {cam_id} 재시작 시도...")
                new_camera = RPiCameraCapture(cam_id, self.resolution, fps=30)
                if new_camera.start():
                    self.cameras[cam_id] = new_camera
                    print(f"✅ 오류 복구 완료: 카메라 {cam_id}")
            except Exception as recovery_error:
                print(f"❌ 카메라 {cam_id} 복구 실패: {recovery_error}")
    
    def _storage_management_loop(self):
        """저장 공간 관리 백그라운드 작업"""
        while self.running:
            try:
                self.storage_manager.check_and_cleanup()
                
                # 1시간마다 실행
                for _ in range(3600):  # 3600초 = 1시간
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"❌ 저장 관리 오류: {e}")
                time.sleep(60)  # 오류 시 1분 대기
    
    def _print_status(self):
        """듀얼 카메라 시스템 상태 출력"""
        uptime = time.time() - self.stats["start_time"]
        storage_stats = self.storage_manager.get_storage_stats()
        
        print("\n" + "="*60)
        print("📊 듀얼 카메라 모션 블랙박스 상태")
        print("="*60)
        print(f"⏱️  가동 시간: {uptime/3600:.1f}시간")
        
        # 각 카메라별 상태 출력
        total_frames = 0
        total_events = 0
        
        for cam_id in sorted(self.cameras.keys()):
            frames = self.stats['total_frames'][cam_id]
            events = self.stats['motion_events'][cam_id]
            total_frames += frames
            total_events += events
            
            buffer_info = self.circular_buffers[cam_id].get_buffer_info()
            
            print(f"📹 카메라 {cam_id}: 프레임 {frames:,}개, 이벤트 {events}회, 버퍼 {buffer_info['frame_count']}/{self.circular_buffers[cam_id].buffer_size}")
            
            if self.stats['last_motion_time'][cam_id]:
                last_motion_ago = time.time() - self.stats['last_motion_time'][cam_id]
                print(f"   🕒 마지막 모션: {last_motion_ago/60:.1f}분 전")
        
        print(f"📊 전체 합계: 프레임 {total_frames:,}개, 이벤트 {total_events}회")
        print(f"💾 저장 사용량: {storage_stats['used_gb']:.1f}GB ({storage_stats['usage_percent']:.1f}%)")
        print(f"📁 이벤트 파일: {storage_stats['file_count']}개")
        
        print("="*60 + "\n")
    
    def _signal_handler(self, signum, frame):
        """시그널 처리 (Ctrl+C 등)"""
        print(f"\n📡 종료 신호 수신 ({signum})")
        self.running = False
    
    def _shutdown(self):
        """듀얼 카메라 시스템 종료 처리"""
        print("🛑 듀얼 카메라 시스템 종료 중...")
        
        self.running = False
        
        # 활성 녹화 스레드 완료 대기
        if hasattr(self, 'active_recordings') and self.active_recordings:
            print(f"⏳ {len(self.active_recordings)}개 녹화 작업 완료 대기 중...")
            for i, thread in enumerate(self.active_recordings):
                if thread.is_alive():
                    print(f"   녹화 작업 {i+1} 대기 중...")
                    thread.join(timeout=10)  # 최대 10초 대기
                    if thread.is_alive():
                        print(f"   ⚠️ 녹화 작업 {i+1} 시간 초과")
                    else:
                        print(f"   ✅ 녹화 작업 {i+1} 완료")
        
        # 모든 카메라 해제
        for cam_id, camera in self.cameras.items():
            try:
                camera.release()
                print(f"📹 카메라 {cam_id} 해제 완료")
            except Exception as e:
                print(f"⚠️ 카메라 {cam_id} 해제 오류: {e}")
        
        # 최종 상태 출력
        self._print_status()
        
        print("✅ 듀얼 카메라 블랙박스 종료 완료")


# 메인 실행부
if __name__ == "__main__":
    try:
        # 설정값
        RESOLUTION = (640, 480)  # 640x480 해상도
        SENSITIVITY = 'medium'  # 모션 감지 감도
        
        print("🎥 듀얼 카메라 모션 블랙박스 시스템")
        print("   카메라 0번, 1번 동시 모션 감지")
        print("   기존 토글 스트리밍과 독립 동작\n")
        
        # 시스템 시작
        blackbox = DualCameraMotionBlackbox(
            resolution=RESOLUTION,
            sensitivity=SENSITIVITY
        )
        
        blackbox.start()
        
    except Exception as e:
        print(f"❌ 듀얼 카메라 시스템 시작 실패: {e}")
        sys.exit(1)