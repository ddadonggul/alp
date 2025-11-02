# AWS EC2 배포 완벽 가이드 (보안 강화 버전)

> ⚠️ **이 가이드는 해킹 경험이 있거나 보안을 최우선으로 고려하는 분들을 위한 상세 가이드입니다.**

## 📋 목차

1. [사전 준비](#1-사전-준비)
2. [EC2 인스턴스 생성 또는 재사용](#2-ec2-인스턴스-생성-또는-재사용)
3. [보안 그룹 설정 (매우 중요!)](#3-보안-그룹-설정-매우-중요)
4. [SSH 접속 설정](#4-ssh-접속-설정)
5. [서버 초기 설정 및 보안 강화](#5-서버-초기-설정-및-보안-강화)
6. [프로젝트 코드 배포](#6-프로젝트-코드-배포)
7. [환경 변수 설정 (보안 강화 버전)](#7-환경-변수-설정-보안-강화-버전)
8. [Session 파일 안전하게 전송](#8-session-파일-안전하게-전송)
9. [systemd 서비스 설정 (보안 강화)](#9-systemd-서비스-설정-보안-강화)
10. [최종 보안 점검](#10-최종-보안-점검)
11. [모니터링 및 유지보수](#11-모니터링-및-유지보수)
12. [문제 해결](#12-문제-해결)

---

## 1. 사전 준비

### 1-1. 로컬에서 확인할 것들

```powershell
# PowerShell에서 확인

# 1) session 파일이 있는지 확인
dir session_user*

# 2) Git에 민감 파일이 안 올라갔는지 최종 확인
git status
git ls-files | findstr /i "session"  # 아무것도 안 나와야 정상
git ls-files | findstr /i ".env"     # 아무것도 안 나와야 정상

# 3) .gitignore 확인
type .gitignore
```

**확인 체크리스트**:
- [ ] `session_user.session` 파일이 로컬에 있다
- [ ] `.env` 파일이 Git에 포함되지 않았다
- [ ] `*.session` 파일이 Git에 포함되지 않았다
- [ ] `.gitignore`에 민감 파일들이 포함되어 있다

### 1-2. 준비물 확인

- [ ] AWS 계정 (있음)
- [ ] AWS Console 접속 가능
- [ ] 내 현재 IP 주소 확인 (https://ip.me)
- [ ] `session_user.session` 파일
- [ ] 모든 API 키 준비 (메모장 등에 미리 복사)

---

## 2. EC2 인스턴스 생성 또는 재사용

### 2-1. 기존 EC2가 있다면 (재사용)

**AWS Console → EC2 → 인스턴스**

기존 인스턴스가 있고 재사용하려면:

1. **인스턴스 상태 확인**
   - 실행 중이어야 함
   - 중지됨: "인스턴스 시작" 클릭

2. **인스턴스 정보 확인**
   - 인스턴스 ID 복사
   - 퍼블릭 IPv4 주소 복사 (나중에 필요)
   - 키 페어 이름 확인 (`.pem` 파일이 있어야 함)

3. **스토리지 확인**
   - 최소 8GB 이상 (10GB 권장)

### 2-2. 새로 EC2 생성하기 (권장)

**Step 1: AWS Console → EC2 → "인스턴스 시작"**

**Step 2: 이름 및 태그**
```
이름: telebot-production
```

**Step 3: 애플리케이션 및 OS 이미지**
- **AMI**: Ubuntu Server 22.04 LTS (프리티어 사용 가능)
- 아키텍처: 64비트(x86)

**Step 4: 인스턴스 유형**
- **t2.micro** (프리티어: 1 vCPU, 1GB RAM)
- 또는 **t3.micro** (조금 더 나음)

**Step 5: 키 페어** ⚠️ **매우 중요!**

**새 키 페어 생성 (권장)**:
1. "새 키 페어 생성" 클릭
2. 키 페어 이름: `telebot-key-2025`
3. 키 페어 유형: **RSA**
4. 프라이빗 키 파일 형식: **.pem**
5. "키 페어 생성" 클릭
6. ⚠️ **다운로드된 `.pem` 파일을 안전한 곳에 보관!**
   - 예: `C:\Users\장상빈\.ssh\telebot-key-2025.pem`
   - **이 파일이 없으면 EC2 접속 불가!**

**기존 키 페어 사용**:
- 예전에 만든 `.pem` 파일이 있다면 선택

**Step 6: 네트워크 설정** ⚠️ **보안의 핵심!**

"편집" 클릭 후:

**방화벽(보안 그룹)**:
- [ ] 새 보안 그룹 생성
- 보안 그룹 이름: `telebot-sg`
- 설명: `Telegram bot security group`

**인바운드 보안 그룹 규칙**:

| 유형 | 프로토콜 | 포트 범위 | 소스 유형 | 소스 |
|------|----------|-----------|-----------|------|
| SSH | TCP | 22 | **내 IP** | (자동 입력됨) |

⚠️ **절대로 "위치 무관(0.0.0.0/0)"을 선택하지 마세요!** → 전 세계 모든 IP가 SSH 시도 가능

**Step 7: 스토리지 구성**
- **크기**: 10 GiB (권장)
- 볼륨 유형: gp3 (프리티어는 gp2)
- 프리티어: 최대 30GB까지 무료

**Step 8: 고급 세부 정보**
- 대부분 기본값 사용

**Step 9: 요약 확인 후 "인스턴스 시작"**

---

## 3. 보안 그룹 설정 (매우 중요!)

### 3-1. 보안 그룹 규칙 최종 확인

**EC2 → 보안 그룹 → telebot-sg (또는 기존 그룹)**

#### 인바운드 규칙 ✅
```
유형: SSH
프로토콜: TCP
포트: 22
소스: <내 IP>/32  (예: 123.456.789.012/32)
```

⚠️ **중요 체크**:
- [ ] SSH만 허용 (다른 포트 없음)
- [ ] 소스가 내 IP 또는 회사 IP로 제한됨
- [ ] `0.0.0.0/0` (전체 공개) 없음

#### 아웃바운드 규칙 ✅
```
유형: 모든 트래픽
프로토콜: 모두
포트: 모두
대상: 0.0.0.0/0
```
(봇이 Telegram/OpenAI API와 통신해야 하므로 필요)

### 3-2. IP 변경 시 대응

집과 회사 IP가 다르면 두 개 추가:

1. **보안 그룹 → 인바운드 규칙 편집**
2. **규칙 추가**:
   ```
   SSH | TCP | 22 | <집 IP>/32
   SSH | TCP | 22 | <회사 IP>/32
   ```

### 3-3. 동적 IP 사용 시 (IP가 자주 바뀌는 경우)

**방법 1: AWS Session Manager 사용 (권장)**
- SSH 없이 브라우저로 접속
- 나중에 SSH 포트를 완전히 닫을 수 있음
- (고급 주제이므로 여기서는 생략)

**방법 2: VPN 고정 IP 사용**

---

## 4. SSH 접속 설정

### 4-1. .pem 파일 권한 설정 (Windows)

```powershell
# .pem 파일 위치로 이동
cd C:\Users\장상빈\.ssh

# 권한 확인 (Windows는 기본적으로 OK)
icacls telebot-key-2025.pem
```

### 4-2. SSH 접속 테스트

```powershell
# EC2 퍼블릭 IP를 여기에 입력 (예: 13.125.123.45)
ssh -i "*telebot-key-2025.pem" ubuntu@ip

```

**처음 접속 시**:
```
The authenticity of host '13.125.123.45' can't be established.
ED25519 key fingerprint is SHA256:...
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```
→ **`yes`** 입력

**성공 시**:
```
Welcome to Ubuntu 22.04.3 LTS
ubuntu@ip-172-31-xx-xx:~$
```

### 4-3. SSH 접속 실패 시

**오류 1: Permission denied (publickey)**
- `.pem` 파일 경로 확인
- 키 페어가 인스턴스와 일치하는지 확인

**오류 2: Connection timed out**
- 보안 그룹에 내 IP가 있는지 확인
- EC2가 실행 중인지 확인
- 퍼블릭 IP가 맞는지 확인

**오류 3: Access denied**
- 사용자명이 `ubuntu`인지 확인 (Amazon Linux는 `ec2-user`)

---

## 5. 서버 초기 설정 및 보안 강화

### 5-1. 시스템 업데이트

```bash
# 시스템 패키지 업데이트
sudo apt update && sudo apt upgrade -y

# 재부팅 필요 시
sudo reboot
```

재부팅 후 다시 SSH 접속.

### 5-2. 기본 패키지 설치

```bash
# 필수 패키지 설치
sudo apt install -y \
  python3 \
  python3-pip \
  python3-venv \
  git \
  htop \
  curl \
  wget \
  unzip

# Python 버전 확인
python3 --version  # Python 3.10.x 이상이어야 함
```

### 5-3. 자동 보안 업데이트 설정

```bash
# unattended-upgrades 설치
sudo apt install unattended-upgrades -y

# 자동 업데이트 활성화
sudo dpkg-reconfigure -plow unattended-upgrades
# → "Yes" 선택
```

### 5-4. Fail2Ban 설치 (무차별 대입 공격 방지)

```bash
# Fail2Ban 설치
sudo apt install fail2ban -y

# 설정 파일 복사
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local

# 설정 편집
sudo nano /etc/fail2ban/jail.local
```

**주요 설정 확인** (기본값으로도 충분):
```ini
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600
```

저장 후:
```bash
# Fail2Ban 시작
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# 상태 확인
sudo fail2ban-client status
```

### 5-5. 방화벽 설정 (UFW)

```bash
# UFW 설치 (보통 이미 설치됨)
sudo apt install ufw -y

# SSH 허용 (끄기 전에 반드시!)
sudo ufw allow 22/tcp

# 방화벽 활성화
sudo ufw enable
# → "y" 입력

# 상태 확인
sudo ufw status verbose
```

출력 예시:
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
```

### 5-6. SSH 보안 강화 (선택사항, 권장)

```bash
# SSH 설정 백업
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# SSH 설정 편집
sudo nano /etc/ssh/sshd_config
```

**다음 항목 확인/수정**:
```bash
# 비밀번호 로그인 완전 차단 (키만 허용)
PasswordAuthentication no

# Root 로그인 금지
PermitRootLogin no

# 빈 비밀번호 금지
PermitEmptyPasswords no

# X11 포워딩 끄기 (불필요)
X11Forwarding no

# 로그인 시간 제한
LoginGraceTime 60

# 최대 인증 시도 횟수
MaxAuthTries 3
```

저장 후:
```bash
# SSH 재시작
sudo systemctl restart sshd

# ⚠️ 재시작 전에 새 터미널에서 SSH 테스트!
# (설정 오류 시 접속 불가 방지)
```

---

## 6. 프로젝트 코드 배포

### 6-1. Git 저장소 클론

```bash
# 홈 디렉토리로 이동
cd ~

# 프로젝트 디렉토리 생성
mkdir -p ~/telebot
cd ~/telebot

# Git 저장소 클론
git clone https://github.com/your-username/your-repo.git

# 프로젝트 디렉토리로 이동
cd your-repo  # 실제 폴더명으로 변경
```

**Git 저장소가 없다면**:
```bash
# 로컬 PC에서 먼저 Git에 푸시 후 클론
# 또는 SCP로 파일 전송:

# PowerShell (로컬에서)
scp -i "C:\Users\장상빈\.ssh\telebot-key-2025.pem" -r C:\Users\장상빈\Desktop\project\telebot\telebottest2_clean ubuntu@<EC2-IP>:~/telebot/
```

### 6-2. Python 가상환경 설정

```bash
# 프로젝트 디렉토리 안에서
cd ~/telebot/telebottest2_clean  # 실제 경로

# 가상환경 생성
python3 -m venv .venv

# 가상환경 활성화
source .venv/bin/activate

# 프롬프트가 (.venv)로 바뀌면 성공
(.venv) ubuntu@ip-xxx:~/telebot/telebottest2_clean$

# 의존성 설치
pip install --upgrade pip
pip install -r requirements.txt
```

**설치 확인**:
```bash
pip list
# telethon, openai, httpx, pydantic 등이 보여야 함
```

---

## 7. 환경 변수 설정 (보안 강화 버전)

### 7-1. 민감 파일 저장 디렉토리 생성

```bash
# 시스템 전역 디렉토리에 안전하게 저장
sudo mkdir -p /var/lib/telebot
sudo chown ubuntu:ubuntu /var/lib/telebot
sudo chmod 700 /var/lib/telebot  # 소유자만 읽기/쓰기/실행
```

### 7-2. 환경 변수 파일 생성

```bash
# 환경 변수 파일 생성
sudo nano /etc/telebot.env
```

**내용 입력** (실제 값으로 변경):
```bash
TG_API_ID=12345678
TG_API_HASH=your_api_hash_here
TG_SESSION=/var/lib/telebot/session_user.session
SOURCE_CHANNELS=@your_channel1,@your_channel2
TG_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TARGET_CHAT_ID=-1001234567890
OPENAI_API_KEY=sk-proj-your_openai_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TWO_STAGE=false
LOG_LEVEL=INFO
RETRY_MAX=5
HTTP_TIMEOUT_SECONDS=10
```

**저장**: `Ctrl+X` → `Y` → `Enter`

### 7-3. 환경 변수 파일 권한 설정

```bash
# 소유자를 ubuntu로 설정
sudo chown ubuntu:ubuntu /etc/telebot.env

# 소유자만 읽기 가능 (600)
sudo chmod 600 /etc/telebot.env

# 권한 확인
ls -la /etc/telebot.env
# 출력: -rw------- 1 ubuntu ubuntu ... /etc/telebot.env
```

⚠️ **절대로 chmod 644, 755 등으로 설정하지 마세요!** (다른 사용자가 읽을 수 있음)

---

## 8. Session 파일 안전하게 전송

### 8-1. 로컬에서 EC2로 Session 파일 전송

**PowerShell (로컬 PC에서)**:
```powershell
# 프로젝트 디렉토리로 이동
cd C:\Users\장상빈\Desktop\project\telebot\telebottest2_clean

# Session 파일 전송 (임시 위치로)
scp -i "C:\Users\장상빈\.ssh\telebot-key-2025.pem" session_user.session* ubuntu@<EC2-IP>:~/
```

### 8-2. EC2에서 안전한 위치로 이동

```bash
# EC2에서
# Session 파일을 안전한 위치로 이동
sudo mv ~/session_user.session /var/lib/telebot/
sudo mv ~/session_user.session-journal /var/lib/telebot/  # 있으면

# 소유자 설정
sudo chown ubuntu:ubuntu /var/lib/telebot/session_user*

# 권한 설정 (소유자만 읽기/쓰기)
sudo chmod 600 /var/lib/telebot/session_user*

# 권한 확인
ls -la /var/lib/telebot/
# 출력: -rw------- 1 ubuntu ubuntu ... session_user.session
```

### 8-3. 홈 디렉토리에 남은 파일 삭제

```bash
# 혹시 남아있을 수 있는 민감 파일 확인
ls -la ~/ | grep -E "session|\.env"

# 있다면 삭제
rm -f ~/.env
rm -f ~/session_user*
```

---

## 9. systemd 서비스 설정 (보안 강화)

### 9-1. 서비스 파일 생성

```bash
sudo nano /etc/systemd/system/telebot.service
```

**내용 입력**:
```ini
[Unit]
Description=Telegram Bot Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/telebot/telebottest2_clean
Environment="PATH=/home/ubuntu/telebot/telebottest2_clean/.venv/bin"
EnvironmentFile=/etc/telebot.env
ExecStart=/home/ubuntu/telebot/telebottest2_clean/.venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# 보안 강화 옵션
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/telebot

[Install]
WantedBy=multi-user.target
```

⚠️ **경로 확인**:
- `WorkingDirectory`: 프로젝트 실제 경로
- `Environment`: 가상환경 bin 경로
- `EnvironmentFile`: 환경 변수 파일 경로
- `ExecStart`: Python 실행 파일 경로

**저장**: `Ctrl+X` → `Y` → `Enter`

### 9-2. 서비스 등록 및 시작

```bash
# systemd에 새 서비스 등록
sudo systemctl daemon-reload

# 서비스 시작
sudo systemctl start telebot

# 서비스 상태 확인
sudo systemctl status telebot
```

**성공 시 출력**:
```
● telebot.service - Telegram Bot Service
     Loaded: loaded (/etc/systemd/system/telebot.service; disabled; vendor preset: enabled)
     Active: active (running) since ...
```

### 9-3. 부팅 시 자동 시작 설정

```bash
# 부팅 시 자동 시작
sudo systemctl enable telebot

# 확인
sudo systemctl is-enabled telebot
# 출력: enabled
```

### 9-4. 로그 확인

```bash
# 실시간 로그 확인
sudo journalctl -u telebot -f

# 최근 100줄 로그
sudo journalctl -u telebot -n 100

# 오늘 로그만
sudo journalctl -u telebot --since today

# 특정 시간 이후
sudo journalctl -u telebot --since "1 hour ago"
```

**Ctrl+C**로 로그 보기 종료.

---

## 10. 최종 보안 점검

### 10-1. 파일 권한 최종 확인

```bash
# 환경 변수 파일
ls -la /etc/telebot.env
# 예상: -rw------- 1 ubuntu ubuntu

# Session 파일
ls -la /var/lib/telebot/
# 예상: -rw------- 1 ubuntu ubuntu ... session_user.session

# 프로젝트 폴더에 민감 파일 없는지 확인
find ~/telebot -name "*.env" -o -name "*.session"
# 아무것도 안 나와야 정상
```

### 10-2. 프로세스 확인

```bash
# 봇이 실행 중인지 확인
ps aux | grep python
# ubuntu ... python main.py

# 포트 사용 확인 (없어야 정상, 봇은 아웃바운드만 사용)
sudo netstat -tlnp | grep LISTEN
```

### 10-3. 로그에서 민감 정보 노출 확인

```bash
# 로그에서 API 키/토큰이 노출되는지 확인
sudo journalctl -u telebot -n 200 | grep -iE "api_key|token|hash"
```

⚠️ **만약 API 키가 로그에 나온다면**:
- 코드를 수정해서 로그에 민감 정보가 출력되지 않도록 해야 함

### 10-4. 보안 점검 체크리스트

- [ ] SSH는 내 IP만 허용 (`0.0.0.0/0` 없음)
- [ ] 비밀번호 로그인 비활성화 (`PasswordAuthentication no`)
- [ ] `/etc/telebot.env` 권한이 `600`
- [ ] `/var/lib/telebot/session_user.session` 권한이 `600`
- [ ] 프로젝트 폴더에 `.env`, `*.session` 파일 없음
- [ ] Git 저장소에 민감 파일이 없음
- [ ] Fail2Ban이 실행 중 (`sudo systemctl status fail2ban`)
- [ ] UFW 방화벽이 활성화 (`sudo ufw status`)
- [ ] 로그에 API 키 노출 없음

---

## 11. 모니터링 및 유지보수

### 11-1. 서비스 관리 명령어

```bash
# 서비스 상태 확인
sudo systemctl status telebot

# 서비스 시작
sudo systemctl start telebot

# 서비스 중지
sudo systemctl stop telebot

# 서비스 재시작
sudo systemctl restart telebot

# 서비스 로그 (실시간)
sudo journalctl -u telebot -f
```

### 11-2. 서버 리소스 모니터링

```bash
# CPU/메모리 사용량 확인
htop
# (q로 종료)

# 디스크 사용량
df -h

# 메모리 사용량
free -h
```

### 11-3. 코드 업데이트

```bash
# 프로젝트 디렉토리로 이동
cd ~/telebot/telebottest2_clean

# Git pull로 최신 코드 받기
git pull

# 가상환경 활성화
source .venv/bin/activate

# 의존성 업데이트 (필요시)
pip install -r requirements.txt --upgrade

# 서비스 재시작
sudo systemctl restart telebot

# 로그 확인
sudo journalctl -u telebot -f
```

### 11-4. 로그 로테이션 (오래된 로그 자동 삭제)

```bash
# journald 로그 크기 제한
sudo nano /etc/systemd/journald.conf
```

다음 줄 수정:
```ini
SystemMaxUse=500M
MaxRetentionSec=1week
```

저장 후:
```bash
sudo systemctl restart systemd-journald
```

### 11-5. 정기적인 보안 업데이트

**매주 또는 매월 실행**:
```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 불필요한 패키지 제거
sudo apt autoremove -y

# 재부팅 필요 시
sudo reboot
```

---

## 12. 문제 해결

### 12-1. 봇이 시작되지 않을 때

```bash
# 서비스 상태 확인
sudo systemctl status telebot

# 상세 로그 확인
sudo journalctl -u telebot -n 100

# 수동 실행으로 에러 확인
cd ~/telebot/telebottest2_clean
source .venv/bin/activate
python main.py
```

**일반적인 원인**:
- 환경 변수 오타 (`/etc/telebot.env` 확인)
- Session 파일 경로 오류
- Python 의존성 누락 (`pip install -r requirements.txt`)

### 12-2. SSH 접속이 안 될 때

**원인 1: IP 변경됨**
```bash
# 현재 내 IP 확인
# https://ip.me

# AWS Console → EC2 → 보안 그룹 → 인바운드 규칙 편집
# 새 IP 추가
```

**원인 2: 키 파일 분실**
- `.pem` 파일 없으면 접속 불가
- 새 인스턴스 생성해야 함 (데이터 백업 중요)

**원인 3: EC2 인스턴스 중지됨**
- AWS Console에서 인스턴스 시작

### 12-3. 메모리 부족 (t2.micro는 1GB만)

```bash
# 스왑 메모리 추가
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 설정
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 확인
free -h
```

### 12-4. Session 파일 오류

```bash
# 로컬에서 session 파일 재전송
scp -i "C:\Users\장상빈\.ssh\telebot-key-2025.pem" session_user.session* ubuntu@<EC2-IP>:~/

# EC2에서
sudo mv ~/session_user.session* /var/lib/telebot/
sudo chown ubuntu:ubuntu /var/lib/telebot/session_user*
sudo chmod 600 /var/lib/telebot/session_user*

# 서비스 재시작
sudo systemctl restart telebot
```

### 12-5. 로그에 API 키가 노출되는 경우

**임시 해결**:
```bash
# 로그 삭제
sudo journalctl --vacuum-time=1s
```

**근본 해결**:
- 코드에서 `logging.info`에 API 키를 출력하지 않도록 수정
- `config.py`나 다른 파일에서 민감 정보 로깅 제거

### 12-6. Fail2Ban이 나를 차단한 경우

```bash
# 자신의 IP 차단 해제
sudo fail2ban-client set sshd unbanip <내-IP>

# 모든 차단 해제 (주의!)
sudo fail2ban-client unban --all
```

---

## 13. 비용 관리

### 13-1. 프리티어 한도 확인

**AWS Console → Billing → Free Tier**

- **EC2**: 월 750시간 (t2.micro)
- **EBS**: 30GB 스토리지
- **데이터 전송**: 15GB 아웃바운드

### 13-2. 비용 알림 설정 (중요!)

**AWS Console → Billing → Billing Preferences**

1. "Receive Billing Alerts" 체크
2. 이메일 주소 확인
3. **CloudWatch 알림 생성**:
   - 임계값: $10 (또는 원하는 금액)
   - 초과 시 이메일 알림

### 13-3. 예상 비용 (프리티어 이후)

**서울 리전 기준**:
- EC2 t2.micro: 약 $10/월
- EBS 10GB: 약 $1/월
- 데이터 전송: 사용량에 따라
- **총**: 약 $11/월

**OpenAI API 비용은 별도** (사용량에 따라 다름)

---

## 14. 추가 보안 강화 (선택사항)

### 14-1. SSH 포트 변경

```bash
sudo nano /etc/ssh/sshd_config
```

```bash
# Port 22 → Port 2222로 변경
Port 2222
```

저장 후:
```bash
# UFW에 새 포트 허용
sudo ufw allow 2222/tcp
sudo ufw delete allow 22/tcp

# AWS 보안 그룹도 수정 (22 → 2222)

# SSH 재시작
sudo systemctl restart sshd

# 새 포트로 접속 테스트 (새 터미널에서!)
ssh -i "key.pem" -p 2222 ubuntu@<EC2-IP>
```

### 14-2. AWS Secrets Manager 사용 (고급)

**나중에 여유 있을 때 적용 가능**:
- `/etc/telebot.env` 대신 AWS Secrets Manager에 저장
- IAM 역할로 EC2가 Secrets에 접근
- 비용: $0.40/월 (시크릿 1개)

### 14-3. CloudWatch 모니터링

- CPU/메모리/디스크 사용량 모니터링
- 알림 설정 (CPU 80% 초과 시 등)

---

## 15. 최종 점검 및 완료

### 15-1. 배포 완료 체크리스트

- [ ] EC2 인스턴스 생성 완료
- [ ] 보안 그룹 설정 (SSH는 내 IP만)
- [ ] SSH 접속 성공
- [ ] 서버 보안 강화 (Fail2Ban, UFW, SSH 설정)
- [ ] 프로젝트 코드 배포
- [ ] `/etc/telebot.env` 생성 및 권한 설정 (600)
- [ ] Session 파일을 `/var/lib/telebot/`로 이동 및 권한 설정 (600)
- [ ] systemd 서비스 생성 및 시작
- [ ] 봇 정상 작동 확인 (로그)
- [ ] 부팅 시 자동 시작 설정
- [ ] 프로젝트 폴더에 민감 파일 없음
- [ ] 비용 알림 설정

### 15-2. 테스트

1. **봇 작동 테스트**:
   - 모니터링 중인 채널에 테스트 메시지 전송
   - 대상 채널에 메시지가 오는지 확인

2. **재부팅 테스트**:
   ```bash
   sudo reboot
   ```
   재부팅 후 SSH 재접속 → 봇이 자동으로 시작되는지 확인

3. **로그 확인**:
   ```bash
   sudo journalctl -u telebot -f
   ```

---

## 16. 요약: 가장 중요한 보안 3가지

### 🔒 1. SSH 접근 제한
```bash
# AWS 보안 그룹: SSH는 내 IP만
# UFW 방화벽 활성화
# Fail2Ban으로 무차별 대입 공격 차단
```

### 🔒 2. 민감 파일 격리 및 권한 제한
```bash
# /etc/telebot.env → 600 (소유자만 읽기)
# /var/lib/telebot/session_user.session → 600
# 프로젝트 폴더에는 민감 파일 없음
```

### 🔒 3. systemd EnvironmentFile 사용
```bash
# 서비스 파일에 API 키 하드코딩 금지
# EnvironmentFile=/etc/telebot.env로 안전하게 주입
```

---

## 📞 도움이 필요하면

- 각 단계에서 막히면 로그 확인: `sudo journalctl -u telebot -n 100`
- SSH 접속 안 되면: 보안 그룹 / IP / 키 파일 확인
- 봇 작동 안 되면: 환경 변수 / Session 파일 경로 확인

**배포 완료!** 🎉

이제 봇이 24/7 안전하게 실행됩니다.

