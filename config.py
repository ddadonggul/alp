from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel
import os
from dotenv import load_dotenv


class AppConfig(BaseModel):
    api_id: int
    api_hash: str
    session_name: str

    source_channels_raw: str
    source_channels: List[object]

    bot_token: str
    target_chat_id: int

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    allow_keywords_raw: Optional[str] = None
    allow_keywords: List[str] = []
    block_keywords_raw: Optional[str] = None
    block_keywords: List[str] = []

    only_new_posts: bool = True
    log_level: str = "INFO"
    retry_max: int = 5
    http_timeout_seconds: int = 10
    openai_two_stage: bool = False

    def is_allowed_channel(self, chat_id: int, username: Optional[str]) -> bool:
        if username:
            handle = f"@{username.lower()}"
            if handle in self.source_channels:
                return True
        return chat_id in self.source_channels


def _parse_comma_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_source_channels(raw: str) -> List[object]:
    channels: List[object] = []
    for item in _parse_comma_list(raw):
        if item.startswith("@"):
            channels.append(item.lower())
            continue
        try:
            channels.append(int(item))
        except ValueError:
            # ignore invalid token silently
            continue
    return channels


def _lower_list(values: List[str]) -> List[str]:
    return [v.lower() for v in values]


def load_config() -> AppConfig:
    # .env → .env.local 순으로 로드하며, 파일 값이 OS 환경변수를 덮어쓰도록 설정
    try:
        load_dotenv(override=True)
        if os.path.exists(".env.local"):
            load_dotenv(".env.local", override=True)
    except Exception:
        pass

    api_id = int(os.getenv("TG_API_ID", "0"))
    api_hash = os.getenv("TG_API_HASH", "")
    session_name = os.getenv("TG_SESSION", "session_user")

    source_channels_raw = os.getenv("SOURCE_CHANNELS", "")
    source_channels = _normalize_source_channels(source_channels_raw)

    bot_token = os.getenv("TG_BOT_TOKEN", "")
    target_chat_id = int(os.getenv("TARGET_CHAT_ID", "0"))

    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_two_stage = os.getenv("OPENAI_TWO_STAGE", "false").lower() == "true"

    allow_keywords_raw = os.getenv("ALLOW_KEYWORDS")
    block_keywords_raw = os.getenv("BLOCK_KEYWORDS")
    allow_keywords = _lower_list(_parse_comma_list(allow_keywords_raw))
    block_keywords = _lower_list(_parse_comma_list(block_keywords_raw))

    only_new_posts = os.getenv("ONLY_NEW_POSTS", "true").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "INFO")
    retry_max = int(os.getenv("RETRY_MAX", "5"))
    http_timeout_seconds = int(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))

    return AppConfig(
        api_id=api_id,
        api_hash=api_hash,
        session_name=session_name,
        source_channels_raw=source_channels_raw,
        source_channels=source_channels,
        bot_token=bot_token,
        target_chat_id=target_chat_id,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        allow_keywords_raw=allow_keywords_raw,
        allow_keywords=allow_keywords,
        block_keywords_raw=block_keywords_raw,
        block_keywords=block_keywords,
        only_new_posts=only_new_posts,
        log_level=log_level,
        retry_max=retry_max,
        http_timeout_seconds=http_timeout_seconds,
        openai_two_stage=openai_two_stage,
    )

