# 보안 가이드

## 🔐 중요 보안 규칙

### 절대 Git에 올리면 안 되는 파일들

다음 파일들은 **절대로** Git에 커밋하거나 푸시하면 안 됩니다:

1. **`.env`** - 실제 API 키와 토큰
2. **`.env.local`** - 로컬 환경 설정
3. **`*.session`** - 텔레그램 세션 파일 (사용자 인증 정보)
4. **`*.session-journal`** - 텔레그램 세션 저널 파일
5. **`__pycache__/`** - Python 캐시 파일
6. **`*.log`** - 로그 파일 (민감한 정보 포함 가능)

### ✅ Git에 올려도 되는 파일들

1. **`.env.example`** - 환경 변수 예시 (실제 값 없음)
2. **`.gitignore`** - Git 무시 파일 목록
3. **소스 코드 파일들** (`.py`)
4. **`requirements.txt`** - 의존성 목록
5. **`README.md`**, **`SECURITY.md`** - 문서 파일

---

## 🚨 보안 사고 발생 시 대응

### 만약 민감한 정보를 Git에 올렸다면?

#### 1단계: 즉시 API 키와 토큰 재발급

**Telegram API**
1. https://my.telegram.org/apps 접속
2. 기존 앱 삭제 후 새로 생성
3. 새로운 API ID와 Hash 발급

**Telegram Bot Token**
1. [@BotFather](https://t.me/BotFather) 접속
2. `/mybots` 선택
3. 해당 봇 선택 → `API Token` → `Revoke current token`
4. 새 토큰 발급

**OpenAI API Key**
1. https://platform.openai.com/api-keys 접속
2. 기존 키 삭제 (`Revoke`)
3. 새 키 생성

#### 2단계: Git 히스토리에서 민감한 정보 완전 삭제

**⚠️ 경고: 아래 명령어는 Git 히스토리를 변경합니다. 신중하게 사용하세요.**

```bash
# 방법 1: BFG Repo-Cleaner 사용 (권장)
# https://rtyley.github.io/bfg-repo-cleaner/
java -jar bfg.jar --delete-files .env
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 방법 2: git-filter-repo 사용
pip install git-filter-repo
git filter-repo --path .env --invert-paths
git filter-repo --path session_user.session --invert-paths

# 방법 3: 새 저장소로 이전 (가장 안전)
# 1. 민감한 파일 확인 및 삭제
# 2. 새 저장소 생성
# 3. 깨끗한 코드만 새 저장소에 커밋
```

#### 3단계: 강제 푸시 (협업 중이라면 팀원에게 알림 필수)

```bash
# 원격 저장소 강제 업데이트 (주의!)
git push origin --force --all
```

#### 4단계: 텔레그램 세션 초기화

```bash
# 세션 파일 삭제
del session_user*  # Windows
rm session_user*   # Linux/Mac

# 봇 재시작 시 다시 로그인 필요
```

---

## 🛡️ 예방 조치

### 1. Git에 커밋하기 전 확인

```bash
# 스테이징된 파일 확인
git status

# 실제 변경 내용 확인
git diff --staged

# .env 파일이 없는지 확인
git ls-files | grep "\.env$"

# 세션 파일이 없는지 확인
git ls-files | grep "\.session"
```

### 2. Pre-commit Hook 설정 (자동 검사)

`.git/hooks/pre-commit` 파일 생성 (Linux/Mac):

```bash
#!/bin/bash

# .env 파일 커밋 방지
if git diff --cached --name-only | grep -E "^\.env$|\.session"; then
    echo "❌ 오류: .env 또는 .session 파일은 커밋할 수 없습니다!"
    echo "민감한 정보가 포함된 파일입니다."
    exit 1
fi

# API 키 패턴 검사
if git diff --cached | grep -E "sk-[a-zA-Z0-9]{32,}|[0-9]{8,10}:[A-Za-z0-9_-]{35}"; then
    echo "❌ 경고: API 키나 토큰이 코드에 포함된 것 같습니다!"
    echo "환경 변수를 사용하세요."
    exit 1
fi

exit 0
```

실행 권한 부여:
```bash
chmod +x .git/hooks/pre-commit
```

### 3. GitHub Secret Scanning 활성화

GitHub에서 자동으로 민감한 정보를 탐지합니다:
1. Repository Settings → Security → Secret scanning 활성화
2. Push protection 활성화 (민감 정보 푸시 시 차단)

### 4. .gitignore 정기 점검

```bash
# .gitignore가 제대로 작동하는지 확인
git check-ignore -v .env
git check-ignore -v session_user.session
```

---

## 📋 보안 체크리스트

Git에 올리기 전 반드시 확인:

- [ ] `.env` 파일이 `.gitignore`에 포함되어 있는가?
- [ ] `.env.example` 파일에 실제 값이 아닌 예시만 있는가?
- [ ] `*.session` 파일이 `.gitignore`에 포함되어 있는가?
- [ ] 코드에 하드코딩된 API 키가 없는가?
- [ ] `git status`로 민감한 파일이 스테이징되지 않았는가?
- [ ] `git log`로 이전 커밋에 민감한 정보가 없는가?

---

## 🔍 코드 감사 (Audit)

### 민감한 정보 검색

```bash
# API 키 패턴 검색
grep -r "sk-proj-" .
grep -r "TG_API_HASH.*=" .
grep -r "[0-9]\{9,\}:[A-Za-z0-9_-]\{35\}" .

# 환경 변수 대신 하드코딩된 값 검색
grep -r "api_id\s*=\s*[0-9]" .
grep -r "api_hash\s*=\s*['\"]" .
```

### 의존성 보안 취약점 검사

```bash
# pip-audit 설치
pip install pip-audit

# 보안 취약점 검사
pip-audit

# Safety 사용
pip install safety
safety check
```

---

## 📞 보안 사고 보고

보안 취약점을 발견하셨다면:
1. **공개적으로 이슈를 올리지 마세요** (악용 가능)
2. 저장소 관리자에게 개인 메시지로 연락
3. 가능하면 암호화된 채널 사용

---

## 🎓 추가 학습 자료

- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [Git Credentials Storage](https://git-scm.com/book/en/v2/Git-Tools-Credential-Storage)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

---

**기억하세요**: 한 번 인터넷에 유출된 정보는 완전히 삭제할 수 없습니다. 
예방이 최선의 보안입니다! 🔒

