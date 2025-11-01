from __future__ import annotations

from typing import Optional

from config import AppConfig
from utils.text_utils import normalize_text, contains_any


def passes_local_filters(cfg: AppConfig, text: Optional[str]) -> bool:
    normalized = normalize_text(text)
    if not normalized or len(normalized) < 10:
        return False

    # BLOCK 우선 차단
    if contains_any(normalized, cfg.block_keywords):
        return False

    # ALLOW 존재 시 허용된 키워드 포함 필요
    if cfg.allow_keywords and not contains_any(normalized, cfg.allow_keywords):
        return False

    return True

