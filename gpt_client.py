from __future__ import annotations

from typing import Any, Dict, Optional
import json
import httpx
import re
import logging

from config import AppConfig
from utils.text_utils import extract_points_and_cost
from utils.retry_utils import run_with_retries


# 바이낸스 알파 에어드랍 분석 프롬프트
PROMPT_STAGE1 = (
    """당신은 바이낸스 알파 에어드랍 공지를 분석하고 한글로 변환하는 전문가입니다.

## ⚠️ 핵심 규칙 (반드시 준수!)

1. **"Phase 1"이 명시되면 → GTD 필드에 저장 (절대 빠뜨리지 말 것!)**
2. **"Phase 2"가 명시되면 → FCFS 필드에 저장**
3. **Phase 1 + Phase 2 둘 다 있으면 → 둘 다 반드시 채워야 함**
4. **Phase 구분 없이 "first-come" 키워드만 있으면 → FCFS만 채움, GTD는 "N/A"**
5. **Alpha Points를 사용하지 않는 공지 → irrelevant**
6. **Pre-TGE 참여자만 해당하는 공지 → irrelevant**
7. **단순 토큰 거래 시작 공지 → irrelevant**

## 🚫 Irrelevant 판정 기준 (매우 중요!)

다음 경우는 **반드시 irrelevant**로 분류:

1. **Alpha Points 미사용**
   - "Alpha Points" 또는 "Binance Alpha Points" 언급 없음
   - 예: "Users who participated in Pre-TGE can start trading"
   
2. **Pre-TGE 참여자 전용**
   - "participated in Pre-TGE"
   - "Winners of Pre-TGE"
   - "Pre-TGE participants"
   
3. **단순 거래/상장 공지**
   - "Token Circulation Starts" (에어드랍 언급 없이)
   - "trading opens" (에어드랍 언급 없이)
   - "start trading" (에어드랍 언급 없이)
   
4. **리워드 프로그램 (에어드랍 아님)**
   - "Booster Program"
   - "Trading rewards"
   - "Competition"

## ✅ Airdrop 판정 기준

다음 **모두** 충족해야 에어드랍:

1. ✅ "airdrop" 또는 "claim" 명시적 언급
2. ✅ "Alpha Points" 사용 언급
3. ✅ 보상 수량 또는 조건 명시

## 📋 출력 JSON 스키마
```json
{
  "postType": "pre-announcement | detailed-announcement | irrelevant",
  "eventType": "airdrop",
  "title": "바이낸스 알파 [토큰명($심볼)] 에어드랍",
  "tokenSymbol": "$XXX",
  "gtd_date": "확정 에어드랍 일정 (KST)",
  "gtd_reward": "확정 보상",
  "gtd_points": "확정 필요 점수",
  "gtd_claim_cost": "확정 클레임 비용",
  "fcfs_date": "선착순 일정 (KST)",
  "fcfs_reward": "선착순 보상",
  "fcfs_points": "선착순 필요 점수",
  "fcfs_claim_cost": "선착순 클레임 비용",
  "disclaimer": "유의사항"
}
```

## 🎯 Phase 구분 (매우 중요!)

### ✅ Phase 1 = 확정 에어드랍 (GTD)
**키워드:** "Phase 1", "first X hours", "First X Hours"
**의미:** 점수만 충족하면 **확정으로** 받을 수 있는 구간

**⚠️ 절대 규칙: Phase 1이 있으면 gtd_* 필드를 반드시 모두 채울 것!**

예시:
```
Phase 1 (First 18 Hours): Users with at least 210 Points can claim 150 WAL.
```
→ 
```json
{
  "gtd_date": "거래 시작~18시간 후 (시각 미공개)",
  "gtd_reward": "150 $WAL",
  "gtd_points": "210점 이상",
  "gtd_claim_cost": "15점 차감"
}
```

### ✅ Phase 2 = 선착순 에어드랍 (FCFS)
**키워드:** "Phase 2", "last X hours", "Last X Hours", "first-come, first-served"
**의미:** 선착순 경쟁으로 받는 구간

예시:
```
Phase 2 (Last 6 Hours): Users with at least 195 Points participate on first-come, first-served basis.
```
→
```json
{
  "fcfs_date": "18시간 후~24시간 후 (시각 미공개)",
  "fcfs_reward": "150 $WAL",
  "fcfs_points": "195점 이상",
  "fcfs_claim_cost": "15점 차감"
}
```

### ⚠️ 절대 규칙
- **Phase 1과 Phase 2가 모두 있으면**: GTD와 FCFS 필드를 **모두 반드시** 채워야 함
- **Phase 2만 있으면**: FCFS만 채우고 GTD는 모두 `"N/A"`
- **Phase 1만 있으면**: GTD만 채우고 FCFS는 모두 `"N/A"`

## 🕐 시간 변환 규칙

### UTC → KST 변환 (UTC+9)
- `07:00 (UTC)` → `16:00 KST`
- `14:00 (UTC)` → `23:00 KST`

### 시각이 명시되지 않은 경우

**"now live", "is live", "when trading starts" 등:**
- 정확한 시각을 알 수 없음
- → 날짜/시간 필드에 `"시각 미공개"` 또는 상대 시간 표기

**예시:**
```
Input: "CDL is now live!"
Output: fcfs_date: "즉시 진행 중 (시각 미공개)"
```
```
Input: "when trading starts" + "within 24 hours"
Phase 1 (First 18 Hours)
Phase 2 (Last 6 Hours)
Output: 
gtd_date: "거래 시작~18시간 (시각 미공개)"
fcfs_date: "18시간 후~24시간 (시각 미공개)"
```

### 날짜/시간 형식
- **구체적 시각 있음**: `M/D HH:mm KST` 또는 `M/D HH:mm~M/D HH:mm KST`
- **시각 미공개**: `"즉시 진행 중 (시각 미공개)"` 또는 `"거래 시작~X시간 (시각 미공개)"`

### 기간 계산 예시

**예시 1: 구체적 시각 있음**
```
시작: October 14, 2025, at 07:00 (UTC) = 10/14 16:00 KST
24시간 이벤트

Phase 1 (first 18 hours):
→ gtd_date: "10/14 16:00~10/15 10:00 KST"

Phase 2 (last 6 hours):
→ fcfs_date: "10/15 10:00~10/15 16:00 KST"
```

**예시 2: 시각 미공개**
```
"when trading starts" + "within 24 hours"
Phase 1 (First 18 Hours)
Phase 2 (Last 6 Hours)

→ gtd_date: "거래 시작~18시간 (시각 미공개)"
→ fcfs_date: "18시간 후~24시간 (시각 미공개)"
```

## 💎 토큰 정보 추출

### 토큰명 패턴
- `Walrus (WAL)` → title: `바이낸스 알파 Walrus($WAL) 에어드랍`, tokenSymbol: `$WAL`
- `Enso (ENSO)` → title: `바이낸스 알파 Enso($ENSO) 에어드랍`, tokenSymbol: `$ENSO`
- **토큰명 없음** → title: `바이낸스 알파 에어드랍 - 토큰명 미공개`, tokenSymbol: `"N/A"`

### 보상 표기
- `150 WAL tokens` → `150 $WAL`
- `640 CDL tokens` → `640 $CDL`

## 📝 완벽한 예시

### 예시 1: Phase 1 + Phase 2 (시각 미공개)
**입력:**
```
Walrus (WAL) is Now on Binance Alpha!
Eligible users can claim 150 WAL tokens when trading starts within 24 hours. Claiming consumes 15 Binance Alpha Points.
Phase 1 (First 18 Hours): Users with at least 210 Points can claim.
Phase 2 (Last 6 Hours): Users with at least 195 Points participate on first-come, first-served basis. If rewards aren't distributed, threshold decreases by 15 points every hour.
```

**올바른 JSON 출력:**
```json
{
  "postType": "detailed-announcement",
  "eventType": "airdrop",
  "title": "바이낸스 알파 Walrus($WAL) 에어드랍",
  "tokenSymbol": "$WAL",
  "gtd_date": "거래 시작~18시간 (시각 미공개)",
  "gtd_reward": "150 $WAL",
  "gtd_points": "210점 이상",
  "gtd_claim_cost": "15점 차감",
  "fcfs_date": "18시간 후~24시간 (시각 미공개)",
  "fcfs_reward": "150 $WAL",
  "fcfs_points": "195점 이상",
  "fcfs_claim_cost": "15점 차감",
  "disclaimer": "보상 미완료 시 매시간 15점씩 임계치 자동 하락"
}
```

### 예시 2: FCFS만 (now live)
**입력:**
```
Creditlink (CDL) is now live on Binance Alpha!
Users with at least 200 Points can claim 640 CDL on first-come, first-served basis.
Claim within 24 hours. Claiming consumes 15 Points.
If rewards not distributed, threshold decreases by 15 points every hour.
```

**출력:**
```json
{
  "postType": "detailed-announcement",
  "eventType": "airdrop",
  "title": "바이낸스 알파 Creditlink($CDL) 에어드랍",
  "tokenSymbol": "$CDL",
  "gtd_date": "N/A",
  "gtd_reward": "N/A",
  "gtd_points": "N/A",
  "gtd_claim_cost": "N/A",
  "fcfs_date": "즉시 진행 중 (시각 미공개)",
  "fcfs_reward": "640 $CDL",
  "fcfs_points": "200점 이상",
  "fcfs_claim_cost": "15점 차감",
  "disclaimer": "24시간 이내 클레임 필요. 보상 미완료 시 매시간 15점씩 임계치 자동 하락"
}
```

### 예시 3: Irrelevant (Pre-TGE 참여자 전용)
**입력:**
```
Astra Nova(RVV) Token Circulation
Starts: 2025-10-18 13:00 (UTC)
Users who participated in the Astra Nova Pre-TGE can start trading RVV tokens once trading opens.
Winners of Booster Program Phase 1 will receive partial RVV reward.
```

**출력:**
```json
{
  "postType": "irrelevant"
}
```

**이유:** Pre-TGE 참여자 전용, Alpha Points 미사용, 에어드랍 아님

### 예시 4: Phase 1 + Phase 2 (구체적 시각)
**입력:**
```
Binance Alpha features Enso (ENSO), trading opening October 14, 2025, at 07:00 (UTC).
Eligible users can claim 10 ENSO tokens using Binance Alpha Points.
Phase 1 (first 18 hours): Users with at least 245 Points can claim.
Phase 2 (last 6 hours): Users with at least 225 Points participate on first-come, first-served basis.
Claiming consumes 15 Points. If rewards not distributed, threshold decreases by 15 points every hour.
```

**출력:**
```json
{
  "postType": "detailed-announcement",
  "eventType": "airdrop",
  "title": "바이낸스 알파 Enso($ENSO) 에어드랍",
  "tokenSymbol": "$ENSO",
  "gtd_date": "10/14 16:00~10/15 10:00 KST",
  "gtd_reward": "10 $ENSO",
  "gtd_points": "245점 이상",
  "gtd_claim_cost": "15점 차감",
  "fcfs_date": "10/15 10:00~10/15 16:00 KST",
  "fcfs_reward": "10 $ENSO",
  "fcfs_points": "225점 이상",
  "fcfs_claim_cost": "15점 차감",
  "disclaimer": "보상 미완료 시 매시간 15점씩 임계치 자동 하락"
}
```

## ⚠️ 절대 주의사항
1. **Phase 1이 있으면 gtd_* 필드를 반드시 모두 채울 것 (절대 빠뜨리지 말 것!)**
2. Phase 2가 있으면 fcfs_* 필드를 반드시 채울 것
3. 둘 다 있으면 모두 채울 것
4. 시각이 명시되면 UTC → KST 변환, 없으면 "시각 미공개" 표기
5. 점수는 "XXX점 이상" 형식
6. 클레임 비용은 "XX점 차감" 형식
7. 토큰 심볼은 항상 `$` 포함 (예: `$WAL`)
"""
).strip()

# Single-stage 모드용 (기본값)
PROMPT_SINGLE_JSON = PROMPT_STAGE1


def _openai_chat(api_key: str, model: str, system_prompt: str, user_content: str, http_timeout_s: int, force_json: bool) -> Any:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }
    if force_json:
        payload["response_format"] = {"type": "json_object"}

    with httpx.Client(timeout=http_timeout_s) as client:
        resp = client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"openai http {resp.status_code}")
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        if not force_json:
            return text
        # JSON 파싱 폴백 로직
        try:
            return json.loads(text)
        except Exception:
            # 코드블럭/설명 섞인 경우 중괄호 블록만 추출 시도
            try:
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    candidate = text[start:end+1]
                    return json.loads(candidate)
            except Exception:
                pass
            # 최종 실패 시 예외
            raise


def call_openai_structured(cfg: AppConfig, content: str, http_timeout_s: int) -> Optional[Dict[str, Any]]:
    def _do_request() -> Optional[Dict[str, Any]]:
        try:
            logging.debug("calling openai with content length: %d", len(content))
            
            # 단일 단계 실행
            obj = _openai_chat(cfg.openai_api_key, cfg.openai_model, PROMPT_SINGLE_JSON, content, http_timeout_s, force_json=True)
            
            if not isinstance(obj, dict):
                logging.error("openai returned non-dict: type=%s", type(obj))
                raise ValueError("non-dict json")
            
            logging.debug("openai raw response: %s", json.dumps(obj, ensure_ascii=False))
            
            # 규칙 기반 보강: 포인트 임계치/소모 비용 자동 채움(없을 때만)
            try:
                hints = extract_points_and_cost(content)
                if isinstance(hints, dict):
                    if not obj.get("fcfs_points") or obj.get("fcfs_points") == "N/A":
                        if "points" in hints:
                            obj["fcfs_points"] = hints["points"]
                    if not obj.get("fcfs_claim_cost") or obj.get("fcfs_claim_cost") == "N/A":
                        if "claim_cost" in hints:
                            obj["fcfs_claim_cost"] = hints["claim_cost"]
                    # 포인트 임계치가 매우 낮은 경우 리워드성으로 간주
                    try:
                        pt = obj.get("fcfs_points")
                        if isinstance(pt, str) and pt.endswith(" 포인트"):
                            num = int(pt.split()[0])
                            if num <= 20 and not obj.get("fcfs_reward"):
                                obj["postType"] = "irrelevant"
                    except Exception:
                        pass
                
                # 토큰 심볼/이름 보강 추출
                title = obj.get("title") or ""
                token_symbol = obj.get("tokenSymbol") or ""

                def _ensure_dollar(sym: str) -> str:
                    if not sym:
                        return sym
                    s = sym.strip()
                    if s.startswith("$"):
                        return s
                    return "$" + s

                name_ticker = re.search(r"([A-Za-z][A-Za-z0-9\-\s]{1,60})\s*\(([A-Z]{2,10})\)", content)
                
                # 일반 영어 단어 제외 필터 추가
                common_words = {"THE", "TOKEN", "TOKENS", "AIRDROP", "CLAIM", "USER", "USERS", "POINTS", "AND", "FOR", "WITH"}
                ticker_match = re.search(r"\b([A-Z]{3,10})\s+tokens?\b", content)
                ticker_only = None
                if ticker_match:
                    potential_ticker = ticker_match.group(1).upper()
                    if potential_ticker not in common_words:
                        ticker_only = ticker_match

                # 심볼이 없거나 제목이 '토큰명 미공개'로 되어 있으면 본문 기준으로 강제 보정
                title_indicates_unknown = "토큰명 미공개" in title
                if (not token_symbol or token_symbol == "N/A") or title_indicates_unknown:
                    if name_ticker:
                        name = name_ticker.group(1).strip()
                        ticker = name_ticker.group(2).strip()
                        obj["tokenSymbol"] = _ensure_dollar(ticker)
                        obj["title"] = f"바이낸스 알파 {name}({obj['tokenSymbol']}) 에어드랍"
                    elif ticker_only:
                        ticker = ticker_only.group(1).strip()
                        obj["tokenSymbol"] = _ensure_dollar(ticker)
                        if title_indicates_unknown or not title:
                            obj["title"] = f"바이낸스 알파 {obj['tokenSymbol']} 에어드랍 - 토큰명 미공개"
                    else:
                        # 아무 토큰도 찾지 못한 경우
                        obj["title"] = "바이낸스 알파 $미공개 에어드랍 - 토큰명 미공개"
                        obj["tokenSymbol"] = "$미공개"
                else:
                    # 심볼은 있는데 $가 빠진 경우 보정
                    obj["tokenSymbol"] = _ensure_dollar(token_symbol)

                # 리워드 문자열 정규화: "500 CORL tokens" → "500 $CORL"
                def _normalize_reward(reward: Optional[str]) -> Optional[str]:
                    if not reward or reward == "N/A":
                        return reward
                    r = reward
                    # 패턴: 수량 + (선택)티커 + tokens
                    m = re.search(r"(\d[\d,\.]*)\s+\$?([A-Z]{2,10})(?:\s+tokens?)?", r, flags=re.IGNORECASE)
                    if m:
                        amount = m.group(1)
                        ticker = m.group(2).upper()
                        return f"{amount} ${ticker}"
                    # 패턴이 없고, tokens만 있을 때 심볼이 있으면 붙여주기
                    if re.search(r"tokens?", r, flags=re.IGNORECASE):
                        sym = obj.get("tokenSymbol")
                        if sym and sym != "N/A":
                            amt = re.search(r"(\d[\d,\.]*)", r)
                            if amt:
                                return f"{amt.group(1)} {sym}"
                    return r

                # 본문에서 airdrop of X TICKER tokens 패턴으로 보강 (필드가 비었을 때)
                if (not obj.get("fcfs_reward") or obj.get("fcfs_reward") == "N/A"):
                    m_body = re.search(r"(?:an\s+)?airdrop\s+of\s+(\d[\d,\.]*)\s+\$?([A-Z]{2,10})\s+tokens?", content, flags=re.IGNORECASE)
                    if m_body:
                        obj["fcfs_reward"] = f"{m_body.group(1)} ${m_body.group(2).upper()}"

                obj["fcfs_reward"] = _normalize_reward(obj.get("fcfs_reward"))
                obj["gtd_reward"] = _normalize_reward(obj.get("gtd_reward"))

                # Phase 구분이 명확한 경우에만 체크
                lower = content.lower()
                has_phase1 = "phase 1" in lower
                has_phase2 = "phase 2" in lower
                has_fcfs_keyword = any(k in lower for k in ["first-come", "first come", "fcfs"])
                
                # Phase 구분이 없고 FCFS 키워드만 있으면 GTD 제거
                if has_fcfs_keyword and not has_phase1 and not has_phase2:
                    for k in ["gtd_date", "gtd_reward", "gtd_points", "gtd_claim_cost"]:
                        obj[k] = "N/A"
                
                # GTD와 FCFS가 동일 값이면 GTD 제거 (중복 방지)
                try:
                    if obj.get("gtd_date") == obj.get("fcfs_date") and obj.get("gtd_reward") == obj.get("fcfs_reward"):
                        for k in ["gtd_date", "gtd_reward", "gtd_points", "gtd_claim_cost"]:
                            obj[k] = "N/A"
                except Exception:
                    pass
            except Exception as e:
                logging.warning("post-processing failed: %s", e)
            
            return obj
            
        except Exception as e:
            logging.error("openai request failed: %s", e, exc_info=True)
            raise

    try:
        return run_with_retries(
            _do_request,
            attempts=max(1, cfg.retry_max),
            base_delay_s=0.5,
            backoff_factor=2.0,
            max_delay_s=8.0,
        )
    except Exception as e:
        logging.error("call_openai_structured failed after retries: %s", e)
        return None