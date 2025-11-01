# Telegram Bot - 텔레그램 채널 모니터링 봇

텔레그램 채널의 메시지를 모니터링하고, GPT로 분석하여 필터링된 정보를 자동으로 전송하는 봇입니다.

## ⚠️ 보안 주의사항

**절대로 다음 파일들을 Git에 올리지 마세요:**
- `.env` - 실제 API 키와 토큰이 포함된 환경 변수 파일
- `.env.local` - 로컬 환경 설정 파일
- `*.session` - 텔레그램 세션 파일
- `*.session-journal` - 텔레그램 세션 저널 파일
- 이 파일들은 `.gitignore`에 이미 포함되어 있습니다.

## 🚀 설치 및 설정

### 1. 저장소 클론

```bash
git clone <your-repo-url>
cd telebottest2
```

### 2. Python 가상환경 생성 (권장)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

1. `.env.example` 파일을 `.env`로 복사:
```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

2. `.env` 파일을 열어 실제 값으로 수정:

#### Telegram API 정보 발급받기
1. https://my.telegram.org/apps 에 접속
2. 전화번호로 로그인
3. 'API development tools' 클릭
4. 앱 정보 입력 후 `api_id`와 `api_hash` 발급
5. `.env` 파일의 `TG_API_ID`와 `TG_API_HASH`에 입력

#### Bot Token 발급받기
1. 텔레그램에서 [@BotFather](https://t.me/BotFather) 검색
2. `/newbot` 명령어로 봇 생성
3. 발급된 토큰을 `.env`의 `TG_BOT_TOKEN`에 입력

#### Chat ID 확인하기
1. 봇을 대상 채널/그룹에 관리자로 추가
2. [@userinfobot](https://t.me/userinfobot) 등을 이용해 Chat ID 확인
3. `.env`의 `TARGET_CHAT_ID`에 입력

#### OpenAI API Key 발급받기
1. https://platform.openai.com/api-keys 에 접속
2. API Key 생성
3. `.env`의 `OPENAI_API_KEY`에 입력

### 5. 봇 실행

```bash
python main.py
```

처음 실행 시 텔레그램 계정 인증이 필요합니다:
1. 전화번호 입력
2. 받은 인증 코드 입력
3. 2단계 인증이 설정된 경우 비밀번호 입력

## 📁 프로젝트 구조

```
telebottest2/
├── main.py              # 메인 실행 파일
├── config.py            # 환경 변수 로드 및 설정 관리
├── filters.py           # 로컬 키워드 필터링
├── gpt_client.py        # OpenAI GPT API 클라이언트
├── formatter.py         # 메시지 포맷팅
├── bot_sender.py        # 텔레그램 봇 메시지 전송
├── price_fetcher.py     # 가격 정보 조회
├── price_scheduler.py   # 가격 업데이트 스케줄러
├── utils/
│   ├── logging_utils.py # 로깅 설정
│   ├── retry_utils.py   # 재시도 로직
│   └── text_utils.py    # 텍스트 처리 유틸
├── requirements.txt     # Python 의존성
├── .env.example         # 환경 변수 예시 (Git에 포함)
├── .env                 # 실제 환경 변수 (Git에서 제외)
└── .gitignore          # Git 무시 파일 목록
```

## 🔧 주요 기능

1. **채널 모니터링**: 지정된 텔레그램 채널의 새 메시지 실시간 감지
2. **키워드 필터링**: 허용/차단 키워드 기반 1차 필터링
3. **GPT 분석**: OpenAI GPT를 이용한 메시지 구조화 및 분류
4. **가격 정보 조회**: CoinGecko API를 통한 토큰 가격 조회
5. **자동 메시지 전송**: 분석된 정보를 포맷팅하여 대상 채널로 전송
6. **가격 업데이트 스케줄링**: 상장 시간 기반 자동 가격 업데이트

## 🔒 보안 체크리스트

새 저장소에 올리기 전 반드시 확인하세요:

- [ ] `.env` 파일이 **절대** 포함되지 않았는지 확인
- [ ] `.env.example` 파일에 실제 값이 아닌 예시 값만 있는지 확인
- [ ] `*.session` 파일이 포함되지 않았는지 확인
- [ ] `.gitignore` 파일이 올바르게 설정되어 있는지 확인
- [ ] 코드에 하드코딩된 API 키나 토큰이 없는지 확인

### Git에 올리기 전 최종 확인

```bash
# Git이 추적할 파일 목록 확인
git status

# .env 파일이 목록에 없는지 확인
# session 파일이 목록에 없는지 확인
```

## 📝 환경 변수 설명

| 변수명 | 필수 | 설명 | 예시 |
|--------|------|------|------|
| `TG_API_ID` | ✅ | 텔레그램 API ID | `12345678` |
| `TG_API_HASH` | ✅ | 텔레그램 API Hash | `abc123...` |
| `TG_SESSION` | ✅ | 세션 파일명 | `session_user` |
| `SOURCE_CHANNELS` | ✅ | 모니터링 채널 목록 | `@channel1,@channel2` |
| `TG_BOT_TOKEN` | ✅ | 봇 토큰 | `1234567890:ABC...` |
| `TARGET_CHAT_ID` | ✅ | 대상 채널 ID | `-1001234567890` |
| `OPENAI_API_KEY` | ✅ | OpenAI API 키 | `sk-proj-...` |
| `OPENAI_MODEL` | ❌ | GPT 모델 | `gpt-4o-mini` |
| `OPENAI_TWO_STAGE` | ❌ | 2단계 분석 여부 | `false` |
| `ALLOW_KEYWORDS` | ❌ | 허용 키워드 | `airdrop,event` |
| `BLOCK_KEYWORDS` | ❌ | 차단 키워드 | `spam,scam` |
| `ONLY_NEW_POSTS` | ❌ | 새 메시지만 처리 | `true` |
| `LOG_LEVEL` | ❌ | 로그 레벨 | `INFO` |
| `RETRY_MAX` | ❌ | 재시도 횟수 | `5` |
| `HTTP_TIMEOUT_SECONDS` | ❌ | HTTP 타임아웃 | `10` |

## 🐛 문제 해결

### 세션 파일 오류
세션 파일이 손상된 경우, 해당 파일을 삭제하고 다시 로그인하세요:
```bash
del session_user*  # Windows
rm session_user*   # Linux/Mac
```

### API 키 오류
`.env` 파일의 모든 필수 값이 올바르게 설정되어 있는지 확인하세요.

## 📄 라이선스

이 프로젝트는 개인 용도로 제작되었습니다.

## ⚠️ 면책 조항

이 봇은 개인적인 용도로 제작되었으며, 텔레그램 이용 약관을 준수하여 사용해야 합니다.
과도한 요청이나 스팸 행위는 계정 제재의 원인이 될 수 있습니다.

