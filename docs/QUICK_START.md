# 🚗 블랙박스 빠른 시작 가이드

## 🚀 간단 시작 방법

### 1. 프로젝트 폴더로 이동
```bash
cd /home/shinho/shinho/livecam
```

### 2. 블랙박스 시작 (카메라별 명확 구분)

## 🎥 단일 카메라 모드

#### **카메라 0번 - 640×480** (권장)
```bash
./start_blackbox.sh cam0-640
```
- **CPU**: 5-8%, **용량**: ~12MB/분, **안정성**: 최고

#### **카메라 1번 - 640×480**
```bash
./start_blackbox.sh cam1-640  
```
- **CPU**: 5-8%, **용량**: ~12MB/분, **안정성**: 최고

#### **카메라 0번 - HD 1280×720**
```bash
./start_blackbox.sh cam0-hd
```
- **CPU**: 13-15%, **용량**: ~27MB/분, **화질**: 우수

#### **카메라 1번 - HD 1280×720**  
```bash
./start_blackbox.sh cam1-hd
```
- **CPU**: 13-15%, **용량**: ~27MB/분, **화질**: 우수

## 🚗 듀얼 카메라 모드 (전후방 동시)

#### **듀얼 카메라 - 640×480**
```bash
./start_blackbox.sh dual-640
```
- **CPU**: 10-16%, **용량**: ~24MB/분 (2개 파일)
- **기능**: 카메라 0+1 동시 녹화

#### **듀얼 카메라 - HD**
```bash
./start_blackbox.sh dual-hd  
```
- **CPU**: 25-30%, **용량**: ~54MB/분 (2개 파일)  
- **주의**: 고성능 요구

## ⚡ 최적화 모드

#### **mmap 최적화** (카메라 0번)
```bash
./start_blackbox.sh optimized
```
- **CPU**: 3-5% (최고 효율성), **메모리 맵 I/O 사용**

### 3. 녹화 중단
```bash
Ctrl + C  # 언제든 중단 가능
```

### 4. MP4 변환 (재생용)
```bash
# 스크립트 실행 후 안내되는 명령어 복사하여 실행
ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 640x480 -r 30 \
  -i blackbox_640_20240828_143022.yuv \
  -c:v libx264 -preset fast -crf 20 \
  blackbox_640_20240828_143022.mp4 -y
```

## 📁 생성되는 파일들

### 원본 파일 (YUV420)
- `blackbox_640_YYYYMMDD_HHMMSS.yuv` - 640x480 녹화
- `blackbox_hd_YYYYMMDD_HHMMSS.yuv` - HD 녹화  
- `blackbox_front_YYYYMMDD_HHMMSS.yuv` - 전방 카메라
- `blackbox_rear_YYYYMMDD_HHMMSS.yuv` - 후방 카메라

### MP4 파일 (변환 후)
- 위 파일들을 ffmpeg로 변환한 재생 가능한 형식

## ⚙️ 고급 사용법

### 수동 rpicam 명령어
```bash
# 640x480 연속 녹화
rpicam-vid --camera 0 --width 640 --height 480 --codec yuv420 \
  --output recording.yuv --timeout 0 --nopreview --framerate 30

# HD 연속 녹화  
rpicam-vid --camera 0 --width 1280 --height 720 --codec yuv420 \
  --output recording_hd.yuv --timeout 0 --nopreview --framerate 30

# 특정 시간 녹화 (10분)
rpicam-vid --camera 0 --width 640 --height 480 --codec yuv420 \
  --output recording_10min.yuv --timeout 600000 --nopreview
```

### 실시간 스트리밍 (네트워크)
```bash
# TCP 스트리밍
rpicam-vid --camera 0 --width 640 --height 480 --codec h264 \
  --output tcp://192.168.1.100:8888 --timeout 0 --nopreview

# UDP 스트리밍  
rpicam-vid --camera 0 --width 640 --height 480 --codec h264 \
  --output udp://192.168.1.100:8888 --timeout 0 --nopreview
```

## 🔧 문제 해결

### 카메라 인식 안됨
```bash
# 카메라 확인
rpicam-hello --list-cameras

# 카메라 테스트
rpicam-hello --camera 0 --timeout 2000
```

### 권한 문제
```bash
# 스크립트 실행 권한 확인
chmod +x start_blackbox.sh

# 카메라 권한 확인  
sudo usermod -a -G video $USER
# 로그아웃 후 다시 로그인 필요
```

### 저장공간 부족
```bash
# 디스크 사용량 확인
df -h

# 오래된 녹화 파일 삭제
rm blackbox_*.yuv  # 주의: 필요한 파일 백업 후 삭제
```

## 💡 팁

### 최적 설정
- **일반 사용**: `./start_blackbox.sh 640` (권장)
- **고화질 필요시**: `./start_blackbox.sh hd`  
- **전후방 녹화**: `./start_blackbox.sh dual`
- **최대 효율성**: `./start_blackbox.sh optimized`

### 용량 관리
- 640x480: 약 12MB/분 → 1시간 = 720MB
- HD: 약 27MB/분 → 1시간 = 1.6GB
- 32GB SD 카드 기준: 640x480로 약 44시간 녹화 가능

### 연속 운영
```bash
# 백그라운드 실행
nohup ./start_blackbox.sh 640 > blackbox.log 2>&1 &

# 프로세스 확인
ps aux | grep rpicam

# 중단
pkill rpicam-vid
```

## 🎯 결론

**가장 간단한 시작**:
```bash
cd /home/shinho/shinho/livecam
./start_blackbox.sh 640
```

**Ctrl+C로 중단**, **자동으로 변환 명령어 표시**됩니다! 🚀