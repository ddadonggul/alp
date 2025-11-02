from __future__ import annotations

import asyncio
import logging
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.types import Message, MessageMediaPhoto
from telethon.tl.functions.channels import GetFullChannelRequest

from config import load_config, AppConfig
from utils.logging_utils import setup_logging
from utils.text_utils import normalize_text
from filters import passes_local_filters
from gpt_client import call_openai_structured
from formatter import format_html
from bot_sender import send_html_message, check_bot_access
from price_fetcher import PriceFetcher
from price_scheduler import PriceScheduler


def _extract_message_text(msg: Message) -> str:
    text = msg.message or ""
    if hasattr(msg, "raw_text") and msg.raw_text:
        text = msg.raw_text
    if not text and msg.media and getattr(msg, "caption", None):
        text = msg.caption
    return normalize_text(text)


def _build_source_link(msg: Message, chat_username: Optional[str], chat_id: int) -> str:
    try:
        link = msg.message_link
        if link:
            return link
    except Exception:
        pass

    try:
        msg_id = getattr(msg, "id", None)
        if chat_username and msg_id:
            return f"https://t.me/{chat_username}/{msg_id}"
    except Exception:
        pass

    try:
        msg_id = getattr(msg, "id", None)
        if chat_id and msg_id:
            s = str(chat_id)
            if s.startswith("-100"):
                internal_id = s[4:]
            else:
                internal_id = s.lstrip("-")
            if internal_id:
                return f"https://t.me/c/{internal_id}/{msg_id}"
    except Exception:
        pass

    return "N/A"


async def _get_photo(msg: Message, client: TelegramClient) -> Optional[bytes]:
    """메시지에서 사진을 바이트로 다운로드"""
    if not msg.media or not isinstance(msg.media, MessageMediaPhoto):
        return None
    
    try:
        photo_bytes = await client.download_media(msg.media, file=bytes)
        return photo_bytes
    except Exception:
        logging.exception("failed to download photo")
        return None


def _extract_listing_time(data: dict) -> Optional[str]:
    """GTD 또는 FCFS 날짜에서 상장 시간 추출
    
    Returns:
        "10/14 16:00 KST" 형식 또는 None
    """
    import re
    
    # GTD 우선 체크
    gtd_date = data.get("gtd_date", "N/A")
    if gtd_date != "N/A":
        # "10/14 16:00~10/15 10:00 KST" -> "10/14 16:00 KST"
        match = re.search(r"(\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})", gtd_date)
        if match:
            return match.group(1) + " KST"
    
    # FCFS 체크
    fcfs_date = data.get("fcfs_date", "N/A")
    if fcfs_date != "N/A":
        match = re.search(r"(\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})", fcfs_date)
        if match:
            return match.group(1) + " KST"
    
    return None


async def handle_message(
    cfg: AppConfig,
    client: TelegramClient,
    msg: Message,
    price_fetcher: PriceFetcher,
    price_scheduler: PriceScheduler,
) -> None:
    if not msg:
        logging.debug("drop: empty message event")
        return

    chat = await msg.get_chat()
    chat_id = getattr(chat, "id", 0)
    username = getattr(chat, "username", None)

    if not cfg.is_allowed_channel(chat_id, username):
        logging.warning(
            "🔴 SKIPPED MESSAGE | chat_username=%s (@%s) | chat_id=%s | configured_channels=%s",
            getattr(chat, "title", "N/A"),
            username if username else "None",
            chat_id,
            cfg.source_channels,
        )
        return
    
    logging.info(
        "✅ ACCEPTED MESSAGE | chat_username=%s (@%s) | chat_id=%s",
        getattr(chat, "title", "N/A"),
        username if username else "None",
        chat_id,
    )

    text = _extract_message_text(msg)
    if not passes_local_filters(cfg, text):
        logging.info(
            "dropped by local filters | chat=%s id=%s text_len=%d allow=%s block=%s",
            username or chat_id,
            chat_id,
            len(text),
            cfg.allow_keywords,
            cfg.block_keywords,
        )
        return

    if not cfg.openai_api_key:
        logging.warning("dropped: OPENAI_API_KEY missing")
        return

    data = call_openai_structured(cfg, text, cfg.http_timeout_seconds)
    if not data:
        logging.info(
            "dropped: gpt parse fail | chat=%s id=%s model=%s", 
            username or chat_id,
            chat_id,
            cfg.openai_model,
        )
        return

    import json
    logging.info("GPT JSON: %s", json.dumps(data, ensure_ascii=False, indent=2))

    post_type = data.get("postType")
    if post_type in ["irrelevant", "pre-announcement"]:
        logging.info("dropped: postType=%s | chat=%s", post_type, username or chat_id)
        return

    # 가격 정보 조회 (1차 시도)
    token_symbol = data.get("tokenSymbol", "N/A")
    price_info = None
    total_value = None
    
    if token_symbol and token_symbol != "N/A":
        price_info = price_fetcher.fetch_price(token_symbol)
        
        if price_info:
            # GTD 또는 FCFS 보상으로 총 가치 계산
            reward = data.get("gtd_reward", "N/A")
            if reward == "N/A":
                reward = data.get("fcfs_reward", "N/A")
            if reward != "N/A":
                total_value = price_fetcher.calculate_value(reward, price_info)
            
            logging.info(
                "price found: %s = $%.4f (value=%.2f USDT)",
                token_symbol,
                price_info.price_usd,
                total_value or 0,
            )
        else:
            logging.info("price not found yet: %s (will schedule)", token_symbol)

    source_link = _build_source_link(msg, username, chat_id)
    html = format_html(data, source_link, price_info, total_value)
    if not html:
        logging.info("dropped: empty html | chat=%s", username or chat_id)
        return

    # 이미지 다운로드
    photo_bytes = await _get_photo(msg, client)

    # 메시지 발송
    result = send_html_message(
        cfg.bot_token, 
        cfg.target_chat_id, 
        html, 
        cfg.http_timeout_seconds,
        photo_bytes=photo_bytes,
        return_message_id=True,  # message_id 반환 요청
    )
    
    if not result:
        logging.error("failed to send message")
        return
    
    sent_message_id = result.get("message_id") if isinstance(result, dict) else None
    
    logging.info(
        "sent=%s | chat=%s | id=%s | msg_id=%s | postType=%s | has_photo=%s | sent_msg_id=%s",
        bool(result),
        username or chat_id,
        chat_id,
        getattr(msg, "id", None),
        data.get("postType"),
        photo_bytes is not None,
        sent_message_id,
    )
    
    # 가격을 못 찾았고, 상장 시간이 있으면 스케줄링
    if not price_info and sent_message_id:
        listing_time = _extract_listing_time(data)
        if listing_time:
            reward = data.get("gtd_reward", "N/A")
            if reward == "N/A":
                reward = data.get("fcfs_reward", "N/A")
            
            scheduled = price_scheduler.schedule(
                token_symbol=token_symbol,
                listing_time_str=listing_time,
                bot_token=cfg.bot_token,
                chat_id=cfg.target_chat_id,
                message_id=sent_message_id,
                reward_str=reward,
                current_html=html,
            )
            
            if scheduled:
                logging.info(
                    "price check scheduled: token=%s listing=%s",
                    token_symbol,
                    listing_time,
                )


async def main_async() -> None:
    cfg = load_config()
    setup_logging(cfg.log_level)
    logging.info("starting telebot | log_level=%s", cfg.log_level)
    logging.info("source_channels=%s target_chat_id=%s", cfg.source_channels, cfg.target_chat_id)

    # 가격 조회 및 스케줄러 초기화
    price_fetcher = PriceFetcher(timeout_s=cfg.http_timeout_seconds)
    price_scheduler = PriceScheduler(price_fetcher, http_timeout_s=cfg.http_timeout_seconds)

    client = TelegramClient(cfg.session_name, cfg.api_id, cfg.api_hash)

    async def resolve_source_chats() -> list:
        resolved = []
        for src in cfg.source_channels:
            try:
                ent = await client.get_entity(src)
                resolved.append(ent)
                try:
                    full = await client(GetFullChannelRequest(ent))
                    linked_id = getattr(full.full_chat, "linked_chat_id", None)
                    if linked_id:
                        linked_ent = await client.get_entity(linked_id)
                        resolved.append(linked_ent)
                except Exception:
                    pass
                tname = ent.__class__.__name__
                uname = getattr(ent, "username", None)
                eid = getattr(ent, "id", None)
                title = getattr(ent, "title", None)
                broadcast = getattr(ent, "broadcast", None)
                megagroup = getattr(ent, "megagroup", None)
                logging.info(
                    "resolved: type=%s username=%s id=%s title=%s broadcast=%s megagroup=%s",
                    tname,
                    uname,
                    eid,
                    title,
                    broadcast,
                    megagroup,
                )
                if tname.lower() == "user":
                    logging.warning(
                        "entity is a User, not a Channel/Chat. Make sure SOURCE_CHANNELS points to a channel username (@...) or -100... id"
                    )
            except Exception:
                logging.warning("failed to resolve source channel: %s", src)
        printable = [getattr(e, "username", None) or getattr(e, "id", None) for e in resolved]
        logging.info("resolved sources=%s", printable)
        return resolved

    async with client:
        await client.start()
        try:
            me = await client.get_me()
            logging.info(
                "authorized account | username=%s id=%s is_bot=%s",
                getattr(me, "username", None),
                getattr(me, "id", None),
                getattr(me, "bot", None),
            )
        except Exception:
            logging.warning("could not fetch self account info")
        
        sources = await resolve_source_chats()
        
        if cfg.bot_token and cfg.target_chat_id:
            check_bot_access(cfg.bot_token, cfg.target_chat_id, cfg.http_timeout_seconds)

        async def _on_message(event: events.newmessage.NewMessage.Event) -> None:
            try:
                chat = await event.get_chat()
                logging.info(
                    "📨 NEW MESSAGE EVENT | chat_id=%s | username=@%s | title=%s | msg_id=%s",
                    event.chat_id,
                    getattr(chat, "username", "None"),
                    getattr(chat, "title", "N/A"),
                    event.message.id if event.message else "None",
                )
                await handle_message(cfg, client, event.message, price_fetcher, price_scheduler)
            except Exception:
                logging.exception("handle_message error")

        if sources:
            client.add_event_handler(_on_message, events.NewMessage(chats=sources))
        else:
            client.add_event_handler(_on_message, events.NewMessage())

        # 가격 스케줄러를 백그라운드에서 실행
        scheduler_task = asyncio.create_task(price_scheduler.run())

        try:
            await client.run_until_disconnected()
        finally:
            # 종료 시 스케줄러 정리
            price_scheduler.stop()
            await scheduler_task


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()