# 🚀 QUICK START - 빠른 시작 가이드

## 📦 1분 안에 시작하기

### Step 1: 카메라 확인 (10초)
```bash
rpicam-hello --list-cameras
```

### Step 2: 블랙박스 시작 (10초)
```bash
cd ~/livecam
./start_blackbox.sh cam0-640
```

### Step 3: 녹화 중단 (언제든지)
```bash
Ctrl + C
```

끝! 영상이 `videos/640x480/` 폴더에 저장됩니다.

---

## 🎯 사용 목적별 빠른 가이드

### 🏭 "생산 라인 감시용"
```bash
# 전방 카메라만 24시간 녹화
./start_blackbox.sh cam0-640
```

### 🚗 "장비 전후방 동시 감시"
```bash
# 듀얼 카메라 동시 녹화
./start_blackbox.sh dual-640
```

### 📹 "고화질 증거 영상"
```bash
# HD 화질 녹화 (CPU 사용률 높음)
./start_blackbox.sh cam0-hd
```

### 🔋 "저전력 장시간 녹화"
```bash
# 최적화 모드 (CPU 3-5%)
./start_blackbox.sh optimized
```

---

## 📊 모드별 성능 비교

| 용도 | 명령어 | CPU | 용량/시간 | 추천도 |
|------|--------|-----|----------|--------|
| **일반 감시** | `cam0-640` | 5-8% | 720MB | ⭐⭐⭐⭐⭐ |
| **전후방 감시** | `dual-640` | 10-16% | 1.4GB | ⭐⭐⭐⭐ |
| **고화질** | `cam0-hd` | 13-15% | 1.6GB | ⭐⭐⭐ |
| **최대 절전** | `optimized` | 3-5% | 720MB | ⭐⭐⭐⭐ |

---

## 🎬 녹화 영상 재생하기

### YUV → MP4 변환 (재생 가능한 형식으로)
```bash
# 블랙박스 종료 시 자동으로 변환 명령어가 표시됩니다
# 복사해서 실행하면 됩니다

# 예시 (640x480)
ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 640x480 -r 30 \
  -i videos/640x480/blackbox_cam0_640_20241230_143022.yuv \
  -c:v libx264 -preset fast -crf 20 \
  videos/640x480/blackbox_cam0_640_20241230_143022.mp4 -y
```

### 변환된 MP4 재생
```bash
# VLC로 재생 (설치: sudo apt install vlc)
vlc videos/640x480/*.mp4

# 또는 파일 관리자에서 더블클릭
```

---

## 🚨 자주 발생하는 문제 해결

### ❌ "카메라를 찾을 수 없습니다"
```bash
# 1. 카메라 연결 확인
rpicam-hello --list-cameras

# 2. 카메라 케이블 재연결 후 재부팅
sudo reboot
```

### ❌ "Permission denied"
```bash
# 실행 권한 부여
chmod +x start_blackbox.sh

# 카메라 그룹 추가
sudo usermod -a -G video $USER
# 로그아웃 후 다시 로그인
```

### ❌ "디스크 공간 부족"
```bash
# 공간 확인
df -h

# 오래된 영상 삭제
rm videos/640x480/blackbox_*.yuv
```

---

## 🛠️ 초기 설정 (최초 1회만)

### 필수 패키지 설치
```bash
sudo apt update
sudo apt install -y rpicam-apps ffmpeg
```

### 프로젝트 다운로드
```bash
cd ~
git clone [프로젝트 URL] livecam
cd livecam
chmod +x start_blackbox.sh
```

---

## 📱 원격 접속 설정

### SSH 활성화
```bash
sudo raspi-config
# Interface Options → SSH → Enable
```

### 원격 접속
```bash
# 다른 컴퓨터에서
ssh pi@[라즈베리파이_IP]
cd ~/livecam
./start_blackbox.sh cam0-640
```

---

## 🔄 자동 시작 설정

### 부팅 시 자동 실행
```bash
# crontab 편집
crontab -e

# 다음 줄 추가
@reboot /home/pi/livecam/start_blackbox.sh cam0-640 > /home/pi/blackbox.log 2>&1
```

### 서비스로 등록 (고급)
```bash
# 서비스 파일 생성
sudo nano /etc/systemd/system/blackbox.service

# 내용 입력
[Unit]
Description=Industrial CCTV Blackbox
After=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/livecam
ExecStart=/home/pi/livecam/start_blackbox.sh dual-640
Restart=always

[Install]
WantedBy=multi-user.target

# 서비스 활성화
sudo systemctl enable blackbox
sudo systemctl start blackbox
```

---

## 📋 명령어 요약표

### 블랙박스 명령어
| 기능 | 명령어 |
|------|--------|
| 전방 카메라 | `./start_blackbox.sh cam0-640` |
| 후방 카메라 | `./start_blackbox.sh cam1-640` |
| 듀얼 카메라 | `./start_blackbox.sh dual-640` |
| HD 전방 | `./start_blackbox.sh cam0-hd` |
| HD 듀얼 | `./start_blackbox.sh dual-hd` |
| 최적화 모드 | `./start_blackbox.sh optimized` |

### 시스템 명령어
| 기능 | 명령어 |
|------|--------|
| 카메라 확인 | `rpicam-hello --list-cameras` |
| CPU 모니터링 | `top` |
| 디스크 확인 | `df -h` |
| 프로세스 확인 | `ps aux \| grep rpicam` |
| 녹화 중단 | `Ctrl + C` |

---

## 💡 프로 팁

### 1. 최적 설정
- **일반 용도**: `cam0-640` (안정적, 효율적)
- **중요 구역**: `dual-640` (전후방 동시)
- **긴급 상황**: `cam0-hd` (고화질 증거)

### 2. 저장 공간 관리
- 32GB SD 카드 = 약 44시간 녹화 (640×480)
- 매주 오래된 파일 정리 권장
- 중요 영상은 별도 백업

### 3. 시스템 안정성
- 24/7 운영 시 방열판 필수
- 주 1회 재부팅 권장
- UPS 사용 권장 (전원 안정성)

---

## 📞 도움이 필요하신가요?

- **기술 문서**: [CLAUDE.md](./CLAUDE.md)
- **제품 사양**: [PRD.md](./PRD.md)  
- **상세 가이드**: [README.md](./README.md)

---

**🎉 축하합니다! 이제 산업용 CCTV 블랙박스를 사용할 준비가 되었습니다!**