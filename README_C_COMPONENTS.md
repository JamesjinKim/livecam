# Raspberry Pi Camera Capture - C Components

라즈베리파이 5 기반 블랙박스 시스템을 위한 C 언어 구현입니다.

## 주요 기능

✅ **V4L2 API를 통한 카메라 접근**
- 라즈베리파이 카메라 모듈 지원 (`/dev/video0`)
- YUYV 4:2:2 포맷 지원
- 다양한 해상도 지원 (기본: 1920x1080)

✅ **DMA 버퍼 관리**
- 메모리 매핑을 통한 고성능 데이터 전송
- 멀티버퍼링으로 프레임 드롭 최소화
- 자동 메모리 정리

✅ **JPEG 압축**
- YUYV to RGB 변환
- libjpeg을 사용한 고품질 압축
- 압축 품질 조절 가능

✅ **파일 저장 시스템**
- RAW 데이터 및 JPEG 저장
- 자동 디렉토리 생성
- 타임스탬프 기반 파일명

## 파일 구조

```
.
├── camera_capture.h      # 헤더 파일
├── camera_capture.c      # 메인 구현
├── test_camera.c         # 테스트 프로그램
├── debug_utils.c         # 디버깅 유틸리티
├── Makefile             # 빌드 시스템
└── README_C_COMPONENTS.md
```

## 의존성 설치

```bash
sudo apt update
sudo apt install build-essential libjpeg-dev linux-headers-$(uname -r)
```

## 컴파일 및 테스트

### 1. 의존성 확인
```bash
make check-deps
```

### 2. 빌드
```bash
make all
```

### 3. 기본 테스트
```bash
make test
```

### 4. 프레임 캡처 테스트
```bash
make capture-test
```

### 5. 성능 벤치마크
```bash
make benchmark
```

## 사용 방법

### 테스트 프로그램 사용법

```bash
# 기본 카메라 테스트
./test_camera -v

# 5프레임 캡처 (JPEG 품질 85%)
./test_camera -t -f 5 -q 85

# 해상도 640x480, 10프레임 캡처
./test_camera -t -w 640 -h 480 -f 10

# 성능 벤치마크 (10초)
./test_camera -b

# 도움말
./test_camera --help
```

### 디버그 유틸리티 사용법

```bash
# 전체 디버그 정보
./debug_utils

# 특정 디바이스 분석
./debug_utils /dev/video1

# 도움말
./debug_utils --help
```

## API 사용 예제

```c
#include "camera_capture.h"

int main() {
    camera_t cam;
    frame_t frame;
    
    // 1. 카메라 초기화
    if (camera_init(&cam, "/dev/video0", 1920, 1080) != 0) {
        return -1;
    }
    
    // 2. 스트리밍 시작
    if (camera_start_streaming(&cam) != 0) {
        camera_cleanup(&cam);
        return -1;
    }
    
    // 3. 프레임 캡처
    if (camera_capture_frame(&cam, &frame) > 0) {
        // JPEG 압축
        uint8_t *jpeg_data = NULL;
        size_t jpeg_size = 0;
        
        if (compress_yuyv_to_jpeg(frame.data, cam.width, cam.height, 
                                 &jpeg_data, &jpeg_size, 85) == 0) {
            // 파일 저장
            frame_t jpeg_frame = {
                .data = jpeg_data,
                .size = jpeg_size,
                .timestamp = frame.timestamp
            };
            save_frame_to_file(&jpeg_frame, "capture.jpg");
            free(jpeg_data);
        }
    }
    
    // 4. 정리
    camera_stop_streaming(&cam);
    camera_cleanup(&cam);
    
    return 0;
}
```

## 디버깅 가이드

### 1. 카메라 디바이스 확인
```bash
./debug_utils | grep "Video capture"
```

### 2. 지원 포맷 확인
```bash
v4l2-ctl --device=/dev/video0 --list-formats-ext
```

### 3. 권한 문제 해결
```bash
sudo usermod -a -G video $USER
# 로그아웃 후 다시 로그인
```

### 4. 메모리 사용량 확인
```bash
./debug_utils | grep -A 10 "Memory Usage"
```

## 성능 최적화

### 예상 성능
- **해상도**: 1920x1080
- **프레임레이트**: ~30 FPS
- **데이터 전송률**: ~120 MB/s (RAW YUYV)
- **JPEG 압축률**: ~85% (품질에 따라 가변)

### 최적화 팁
1. **해상도 조절**: 용도에 맞는 해상도 사용
2. **버퍼 수**: 기본 4개, 필요시 조정
3. **JPEG 품질**: 70-90 권장 (파일 크기 vs 품질)
4. **CPU 코어**: 멀티스레딩 고려

## 문제 해결

### 자주 발생하는 오류

1. **Device busy**
   ```bash
   sudo lsof /dev/video0  # 사용 중인 프로세스 확인
   ```

2. **Permission denied**
   ```bash
   sudo chmod 666 /dev/video0
   ```

3. **Memory allocation failed**
   ```bash
   free -m  # 메모리 상태 확인
   ```

4. **JPEG compression failed**
   ```bash
   sudo apt install libjpeg-dev  # 라이브러리 재설치
   ```

## 시스템 요구사항

- **OS**: Raspberry Pi OS (64-bit 권장)
- **하드웨어**: Raspberry Pi 5
- **RAM**: 최소 1GB (4GB 권장)
- **카메라**: 라즈베리파이 공식 카메라 모듈
- **저장**: 충분한 디스크 공간 (JPEG 파일 저장용)

## 설치 및 제거

```bash
# 시스템 전역 설치
make install

# 제거
make uninstall

# 빌드 파일 정리
make clean
```

## 라이센스

이 프로젝트는 교육 및 연구 목적으로 작성되었습니다.