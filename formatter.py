from __future__ import annotations

from typing import Dict, Optional
import re


def _normalize_points_text(text: str) -> str:
    if not text:
        return text
    patterns = [
        r"\bBinance\s+Alpha\s+Points?\b",
        r"\bAlpha\s+Points?\b",
    ]
    normalized = text
    for pat in patterns:
        normalized = re.sub(pat, "포인트", normalized, flags=re.IGNORECASE)
    return normalized


def _format_price_block(price_info, total_value: Optional[float]) -> str:
    """제목 다음 줄에 표시할 가격/가치 블록 생성 (링크 앵커 사용)"""
    # <--- 수정: \n\n (줄바꿈 2번)을 \n (줄바꿈 1번)으로 변경
    if not price_info:
        return "\n💰 <b>가격 추정 중</b>"
    if total_value:
        return f"\n💰 <b><a href=\"{price_info.coingecko_url}\">예상 가치: {total_value:.2f} USDT</a></b>"
    return f"\n💰 <b><a href=\"{price_info.coingecko_url}\">가격: ${price_info.price_usd:.4f}</a></b>"
    # <--- 수정: \n\n (줄바꿈 2번)을 \n (줄바꿈 1번)으로 변경


def format_html(
    data: Dict[str, str],
    source_link: str,
    price_info=None,  # PriceInfo or None
    total_value: Optional[float] = None,
) -> str:
    post_type = data.get("postType", "irrelevant")
    title = _normalize_points_text(data.get("title", ""))

    # 제목에서 "바이낸스 알파" 제거
    title = re.sub(r"바이낸스\s*알파\s*", "", title, flags=re.IGNORECASE).strip()

    # 가격/가치 블록 생성 (이제 \n이 1개만 포함됨)
    price_block = _format_price_block(price_info, total_value)

    if post_type == "pre-announcement":
        disclaimer = _normalize_points_text(data.get('disclaimer', ''))

        parts = [
            f"<b>🔔 {title} [예고]</b> | <a href=\"{source_link}\">출처</a>",
            price_block, # 원본 코드와 동일하게 유지
            "",
            f"<blockquote>상장/이벤트 예정일: {data.get('gtd_date','N/A')}</blockquote>",
        ]

        if disclaimer and disclaimer != 'N/A':
            parts.extend([
                "",
                f"<i>{disclaimer}</i>",
            ])

        return "\n".join(parts)

    if post_type == "detailed-announcement":
        gtd_date = data.get('gtd_date', 'N/A')
        gtd_reward = _normalize_points_text(data.get('gtd_reward', 'N/A'))
        gtd_points = _normalize_points_text(data.get('gtd_points', 'N/A'))
        gtd_claim_cost = _normalize_points_text(data.get('gtd_claim_cost', 'N/A'))

        fcfs_date = data.get('fcfs_date', 'N/A')
        fcfs_reward = _normalize_points_text(data.get('fcfs_reward', 'N/A'))
        fcfs_points = _normalize_points_text(data.get('fcfs_points', 'N/A'))
        fcfs_claim_cost = _normalize_points_text(data.get('fcfs_claim_cost', 'N/A'))

        disclaimer = _normalize_points_text(data.get('disclaimer', ''))

        include_gtd = not all(v == 'N/A' for v in [gtd_date, gtd_reward, gtd_points, gtd_claim_cost])

        parts = [
            f"⭐️ <b>{title}</b> | <a href=\"{source_link}\">출처</a>",
            price_block, # 원본 코드와 동일하게 유지
        ]

        if include_gtd:
            parts.extend([
                "",
                f"<blockquote><b>확정 에어드랍(Priority)</b></blockquote>",
                f"* 일정 : {gtd_date}",
                f"* 보상 : {gtd_reward}",
                f"* 필요 점수 : {gtd_points}",
                f"* 클레임 비용 : {gtd_claim_cost}",
            ])

        parts.extend([
            "",
            f"<blockquote><b>선착순 에어드랍(FCFS)</b></blockquote>",
            f"* 일정 : {fcfs_date}",
            f"* 보상 : {fcfs_reward}",
            f"* 필요 점수 : {fcfs_points}",
            f"* 클레임 비용 : {fcfs_claim_cost}",
        ])

        if disclaimer and disclaimer != 'N/A':
            parts.extend([
                "",
                f"<i>유의사항 : {disclaimer}</i>",
            ])

        return "\n".join(parts)

    if post_type == "pre-tge-campaign":
        parts = [
            f"<b>{title}</b> | <a href=\"{source_link}\">출처</a>",
            price_block, # 원본 코드와 동일하게 유지
            "",
            f"<blockquote><b>캠페인 요약</b></blockquote>",
            f"- 커밋/참여 비용 : {_normalize_points_text(data.get('commit_amount','N/A'))}",
            f"- 유의사항 : {_normalize_points_text(data.get('disclaimer','N/A'))}",
        ]
        return "\n".join(parts)

    return ""