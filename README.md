# 🎥 산업용 CCTV 블랙박스 시스템

> 라즈베리파이 5 기반 첨단 디스플레이 산업 생산공정용 영상 기록 시스템

[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red)](https://www.raspberrypi.org/)
[![Camera](https://img.shields.io/badge/Camera-OV5647-blue)](https://www.uctronics.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## 📌 프로젝트 소개

첨단 디스플레이 제조 공정에서 발생하는 모든 이벤트를 24/7 기록하는 산업용 CCTV 블랙박스 시스템입니다. 듀얼 카메라를 통한 전후방 동시 녹화를 지원하며, 높은 안정성과 효율성을 제공합니다.

### 주요 특징
- 🎬 **듀얼 카메라**: 전방/후방 동시 녹화
- ⚡ **저전력 설계**: CPU 5-8% (640×480 단일 카메라)
- 🔄 **24/7 운영**: 자동 복구 시스템 내장
- 📊 **실시간 모니터링**: 시스템 상태 확인
- 🎯 **산업 최적화**: 생산 라인 특화 설계

## 🚀 빠른 시작

### 1분 안에 시작하기
```bash
# 1. 카메라 확인
rpicam-hello --list-cameras

# 2. 블랙박스 시작
cd ~/livecam
./start_blackbox.sh cam0-640

# 3. 중단 (Ctrl+C)
```

자세한 내용은 [QUICK_START.md](./QUICK_START.md)를 참조하세요.

## 📋 시스템 요구사항

### 하드웨어
- **필수**
  - Raspberry Pi 5 (4GB+ RAM)
  - OV5647 카메라 모듈 × 1-2개
  - 32GB+ microSD (Class 10)
  - 5V/3A 전원 어댑터

- **권장**
  - Raspberry Pi 5 (8GB RAM)
  - 128GB microSD (A2 등급)
  - 5V/5A 전원 어댑터
  - 방열판 및 쿨링 팬

### 소프트웨어
- Raspberry Pi OS (64-bit)
- rpicam-apps
- FFmpeg

## 💿 설치 방법

### 1. 시스템 업데이트
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. 필수 패키지 설치
```bash
sudo apt install -y rpicam-apps ffmpeg git
```

### 3. 프로젝트 다운로드
```bash
cd ~
git clone [프로젝트_URL] livecam
cd livecam
chmod +x start_blackbox.sh
```

### 4. 카메라 활성화
```bash
sudo raspi-config
# Interface Options → Camera → Enable
# 재부팅 필요
```

## 🎮 사용 방법

### 기본 명령어

#### 단일 카메라 모드
```bash
# 전방 카메라 (640×480)
./start_blackbox.sh cam0-640

# 후방 카메라 (640×480)
./start_blackbox.sh cam1-640

# 전방 카메라 HD (1280×720)
./start_blackbox.sh cam0-hd
```

#### 듀얼 카메라 모드
```bash
# 전후방 동시 (640×480)
./start_blackbox.sh dual-640

# 전후방 동시 HD
./start_blackbox.sh dual-hd
```

#### 최적화 모드
```bash
# 최저 CPU 사용 (3-5%)
./start_blackbox.sh optimized
```

### 녹화 영상 변환

YUV 파일을 MP4로 변환:
```bash
# 640×480 변환
ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 640x480 -r 30 \
  -i videos/640x480/blackbox_cam0_640_20241230_143022.yuv \
  -c:v libx264 -preset fast -crf 20 \
  videos/640x480/output.mp4 -y

# HD 변환
ffmpeg -f rawvideo -pix_fmt yuv420p -video_size 1280x720 -r 30 \
  -i videos/hd/blackbox_cam0_hd_20241230_143022.yuv \
  -c:v libx264 -preset fast -crf 20 \
  videos/hd/output.mp4 -y
```

## 📊 성능 사양

| 구성 | 해상도 | CPU 사용률 | 메모리 | 저장용량/시간 |
|------|--------|-----------|--------|--------------|
| 단일 카메라 | 640×480 | 5-8% | <500MB | 720MB |
| 단일 카메라 | 1280×720 | 13-15% | <800MB | 1.6GB |
| 듀얼 카메라 | 640×480 | 10-16% | <1GB | 1.4GB |
| 듀얼 카메라 | 1280×720 | 25-30% | <1.5GB | 3.2GB |
| 최적화 모드 | 640×480 | 3-5% | <400MB | 720MB |

## 🏭 산업 현장 적용 가이드

### 생산 라인 설치
1. **위치 선정**: 진동이 적고 온도가 안정적인 곳
2. **전원 확보**: UPS 연결 권장
3. **카메라 각도**: 공정 전체가 보이도록 조정
4. **네트워크**: 원격 모니터링용 이더넷 연결

### 운영 모드 선택
- **일반 공정**: `cam0-640` (안정적, 효율적)
- **정밀 공정**: `cam0-hd` (고화질)
- **전체 감시**: `dual-640` (전후방)
- **24/7 운영**: `optimized` (최소 부하)

### 데이터 관리
```bash
# 자동 삭제 설정 (7일 이상 된 파일)
find videos/ -name "*.yuv" -mtime +7 -delete

# 중요 영상 백업
rsync -av videos/ /backup/location/
```

## 🔧 고급 설정

### 자동 시작 설정

#### systemd 서비스 등록
```bash
sudo nano /etc/systemd/system/blackbox.service
```

```ini
[Unit]
Description=Industrial CCTV Blackbox System
After=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/livecam
ExecStart=/home/pi/livecam/start_blackbox.sh dual-640
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable blackbox
sudo systemctl start blackbox
```

### 원격 모니터링

#### SSH 접속
```bash
ssh pi@[라즈베리파이_IP]
```

#### 실시간 로그 확인
```bash
journalctl -u blackbox -f
```

## 🛠️ 문제 해결

### 자주 발생하는 문제

#### 카메라 인식 오류
```bash
# 카메라 연결 상태 확인
rpicam-hello --list-cameras

# 카메라 모듈 재로드
sudo modprobe -r bcm2835-v4l2
sudo modprobe bcm2835-v4l2
```

#### 권한 오류
```bash
# 실행 권한 부여
chmod +x start_blackbox.sh

# 비디오 그룹 추가
sudo usermod -a -G video $USER
```

#### 디스크 공간 부족
```bash
# 공간 확인
df -h

# 오래된 파일 삭제
find videos/ -name "*.yuv" -mtime +30 -delete
```

## 📁 프로젝트 구조

```
livecam/
├── README.md              # 사용자 가이드 (현재 문서)
├── CLAUDE.md             # 개발자 기술 문서
├── PRD.md                # 제품 요구사항 문서
├── QUICK_START.md        # 빠른 시작 가이드
├── start_blackbox.sh     # 메인 실행 스크립트
├── src/                  # 소스 코드 (레거시)
│   ├── core/            # 핵심 시스템
│   ├── optimized/       # 최적화 구현
│   └── legacy/          # 레거시 코드
├── scripts/             # 유틸리티 스크립트
└── videos/              # 녹화 영상 저장
    ├── 640x480/        # SD 해상도
    └── hd/             # HD 해상도
```

## 📈 로드맵

- [x] MVP - 기본 녹화 기능
- [x] 듀얼 카메라 지원
- [x] YUV420 최적화
- [ ] 웹 인터페이스
- [ ] 실시간 스트리밍
- [ ] AI 이벤트 감지
- [ ] 클라우드 백업

## 🤝 기여 방법

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 📞 지원 및 문의

- **기술 문서**: [CLAUDE.md](./CLAUDE.md)
- **제품 사양**: [PRD.md](./PRD.md)
- **빠른 시작**: [QUICK_START.md](./QUICK_START.md)
- **이슈 제보**: GitHub Issues

## 🙏 감사의 말

이 프로젝트는 라즈베리파이 재단과 오픈소스 커뮤니티의 지원으로 만들어졌습니다.

---

**Made with ❤️ for Industrial Innovation**