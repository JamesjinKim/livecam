# 📷 카메라별 사용법 가이드

## 🎥 블랙박스 명령어 구분

### 단일 카메라 모드

| 명령어 | 카메라 | 해상도 | CPU 사용률 | 용도 |
|--------|--------|--------|-----------|------|
| `cam0-640` | 카메라 0번 | 640×480 | 5-8% | **전방 블랙박스 (권장)** |
| `cam1-640` | 카메라 1번 | 640×480 | 5-8% | **후방 블랙박스 (권장)** |
| `cam0-hd` | 카메라 0번 | 1280×720 | 13-15% | 전방 고화질 |
| `cam1-hd` | 카메라 1번 | 1280×720 | 13-15% | 후방 고화질 |

### 듀얼 카메라 모드

| 명령어 | 카메라 | 해상도 | CPU 사용률 | 용도 |
|--------|--------|--------|-----------|------|
| `dual-640` | 0번 + 1번 | 640×480 | 10-16% | **전후방 동시 (권장)** |
| `dual-hd` | 0번 + 1번 | 1280×720 | 25-30% | 전후방 고화질 |

### 최적화 모드

| 명령어 | 카메라 | 기술 | CPU 사용률 | 용도 |
|--------|--------|------|-----------|------|
| `optimized` | 카메라 0번 | mmap I/O | 3-5% | **최고 효율성** |

## 🚗 실제 사용 시나리오

### 1. 일반 블랙박스 (전방만)
```bash
./start_blackbox.sh cam0-640
```
- **파일**: `blackbox_cam0_640_20240828_143022.yuv`
- **사용량**: CPU 5-8%, ~12MB/분
- **용도**: 기본 전방 블랙박스

### 2. 후방 카메라만
```bash  
./start_blackbox.sh cam1-640
```
- **파일**: `blackbox_cam1_640_20240828_143022.yuv`
- **사용량**: CPU 5-8%, ~12MB/분
- **용도**: 주차 감시, 후방 전용

### 3. 완전 블랙박스 (전후방)
```bash
./start_blackbox.sh dual-640
```
- **파일**: 
  - `blackbox_cam0_640_20240828_143022.yuv` (전방)
  - `blackbox_cam1_640_20240828_143022.yuv` (후방)
- **사용량**: CPU 10-16%, ~24MB/분 (2개 파일)
- **용도**: 완전한 블랙박스 시스템

### 4. 고화질 블랙박스
```bash
./start_blackbox.sh dual-hd
```
- **파일**: HD 해상도 2개 파일
- **사용량**: CPU 25-30%, ~54MB/분
- **용도**: 고화질 증거 영상

### 5. 최고 효율성 모드
```bash
./start_blackbox.sh optimized
```
- **파일**: `blackbox_optimized_20240828_143022.yuv`
- **사용량**: CPU 3-5%, ~12MB/분
- **용도**: 배터리 절약, 장시간 녹화

## 📁 파일 명명 규칙

### 단일 카메라
- `blackbox_cam0_640_YYYYMMDD_HHMMSS.yuv` - 카메라 0번 640x480
- `blackbox_cam1_640_YYYYMMDD_HHMMSS.yuv` - 카메라 1번 640x480  
- `blackbox_cam0_hd_YYYYMMDD_HHMMSS.yuv` - 카메라 0번 HD
- `blackbox_cam1_hd_YYYYMMDD_HHMMSS.yuv` - 카메라 1번 HD

### 듀얼 카메라
- `blackbox_cam0_640_YYYYMMDD_HHMMSS.yuv` - 전방 카메라
- `blackbox_cam1_640_YYYYMMDD_HHMMSS.yuv` - 후방 카메라
- (동일 타임스탬프로 구분)

### 최적화 모드
- `blackbox_optimized_YYYYMMDD_HHMMSS.yuv` - mmap 최적화

## 🎬 MP4 변환 가이드

### 스크립트 자동 생성
블랙박스 종료 후 자동으로 변환 명령어가 표시됩니다:

```bash
# 640x480 변환
ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 640x480 -r 30 -i blackbox_cam0_640_20240828_143022.yuv -c:v libx264 -preset fast -crf 20 blackbox_cam0_640_20240828_143022.mp4 -y

# HD 변환
ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 1280x720 -r 30 -i blackbox_cam0_hd_20240828_143022.yuv -c:v libx264 -preset fast -crf 20 blackbox_cam0_hd_20240828_143022.mp4 -y
```

## ⚙️ 카메라 확인 방법

### 1. 연결된 카메라 목록
```bash
rpicam-hello --list-cameras
```

### 2. 카메라별 테스트
```bash  
# 카메라 0번 테스트 (2초)
rpicam-hello --camera 0 --timeout 2000

# 카메라 1번 테스트 (2초) 
rpicam-hello --camera 1 --timeout 2000
```

### 3. 카메라 상태 확인
```bash
# I2C 주소 확인
ls /sys/class/video4linux/

# 카메라 모듈 정보
dmesg | grep -i camera
```

## 🔧 문제 해결

### 카메라 0번만 작동할 때
```bash
# 카메라 1번 연결 확인
rpicam-hello --camera 1 --timeout 1000

# 에러 발생 시 → 카메라 1번 미연결 또는 불량
```

### 듀얼 모드에서 한쪽만 녹화될 때
```bash
# 개별 테스트로 확인
./start_blackbox.sh cam0-640  # 10초 테스트
./start_blackbox.sh cam1-640  # 10초 테스트

# 둘 다 정상이면 듀얼 모드 재시도
./start_blackbox.sh dual-640
```

### CPU 사용률이 높을 때
1. **640x480 사용**: HD 대신 일반 해상도
2. **단일 카메라**: 듀얼 대신 필요한 카메라만
3. **최적화 모드**: `optimized` 사용

## 💡 권장 설정

### 일반 사용자
```bash
./start_blackbox.sh cam0-640    # 전방 카메라만 충분
```

### 완전 블랙박스
```bash
./start_blackbox.sh dual-640    # 전후방 동시, 안정적
```

### 배터리 중요시
```bash  
./start_blackbox.sh optimized   # 최소 CPU, 최대 효율
```

### 고화질 증거용
```bash
./start_blackbox.sh dual-hd     # 전후방 HD (충분한 전력 필요)
```