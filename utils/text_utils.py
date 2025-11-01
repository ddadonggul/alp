from __future__ import annotations

from typing import Optional
import re


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.split())


def contains_any(haystack: str, needles: list[str]) -> bool:
    if not haystack or not needles:
        return False
    lower = haystack.lower()
    return any(token in lower for token in needles)


def extract_points_and_cost(text: str) -> dict:
    """규칙 기반으로 포인트 임계치/소모 비용을 추출.

    반환 예시: {"points": "200 포인트", "claim_cost": "15 포인트"}
    값이 없으면 해당 키는 포함하지 않을 수 있음.
    """
    result: dict = {}
    if not text:
        return result

    lowered = text
    # at least X Points / require X Points → 임계 포인트
    m = re.search(r"(?:at\s+least|require[s]?)\s+(\d+)\s+(?:binance\s+alpha\s+)?points?", lowered, flags=re.IGNORECASE)
    if m:
        result["points"] = f"{m.group(1)} 포인트"

    # consume/cost/spend Y Points → 소모 포인트
    m2 = re.search(r"(?:consume[s]?|cost[s]?|spend[s]?)\s+(\d+)\s+(?:binance\s+alpha\s+)?points?", lowered, flags=re.IGNORECASE)
    if m2:
        result["claim_cost"] = f"{m2.group(1)} 포인트"

    return result

