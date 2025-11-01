from __future__ import annotations

import httpx
import logging
import os
from typing import Optional, Union, Dict
from utils.retry_utils import run_with_retries


def _verify_option_from_env() -> object:
    no_verify = os.getenv("TELEGRAM_TLS_NO_VERIFY", "false").lower() == "true"
    if no_verify:
        return False
    ca_bundle = os.getenv("TELEGRAM_CA_BUNDLE")
    if ca_bundle:
        return ca_bundle
    return True


def send_html_message(
    bot_token: str,
    chat_id: int,
    text: str,
    timeout_s: int,
    photo_bytes: Optional[bytes] = None,
    return_message_id: bool = False,
) -> Union[bool, Dict]:
    """텔레그램 메시지 전송
    
    Args:
        return_message_id: True면 {"success": bool, "message_id": int} 반환
                          False면 bool만 반환 (기존 동작)
    """
    if not text:
        return True if not return_message_id else {"success": True, "message_id": None}

    base_url = f"https://api.telegram.org/bot{bot_token}"

    def _do_request() -> Union[bool, Dict]:
        if photo_bytes:
            url = f"{base_url}/sendPhoto"
            files = {
                "photo": ("image.jpg", photo_bytes, "image/jpeg")
            }
            data = {
                "chat_id": chat_id,
                "caption": text,
                "parse_mode": "HTML",
            }
            with httpx.Client(timeout=timeout_s, verify=_verify_option_from_env()) as client:
                r = client.post(url, data=data, files=files)
        else:
            url = f"{base_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            with httpx.Client(timeout=timeout_s, verify=_verify_option_from_env()) as client:
                r = client.post(url, json=payload)
        
        if r.status_code != 200:
            try:
                body = r.text
            except Exception:
                body = "<no body>"
            logging.error("telegram send error http=%s body=%s", r.status_code, body)
            raise RuntimeError(f"telegram http {r.status_code}")
        
        try:
            data = r.json()
        except Exception:
            logging.error("telegram send error: invalid json body=%s", r.text)
            if return_message_id:
                return {"success": False, "message_id": None}
            return False
        
        if not data.get("ok"):
            logging.error("telegram send error ok=false desc=%s", data.get("description"))
            if return_message_id:
                return {"success": False, "message_id": None}
            return False
        
        # message_id 추출
        if return_message_id:
            msg_id = data.get("result", {}).get("message_id")
            return {"success": True, "message_id": msg_id}
        
        return True

    try:
        return run_with_retries(_do_request, attempts=3, base_delay_s=0.5, backoff_factor=2.0)
    except Exception:
        logging.exception("telegram send exception")
        if return_message_id:
            return {"success": False, "message_id": None}
        return False


def update_message_text(bot_token: str, chat_id: int, message_id: int, text: str, timeout_s: int) -> bool:
    """텔레그램 메시지 텍스트 수정"""
    if not text:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    def _do_request() -> bool:
        with httpx.Client(timeout=timeout_s, verify=_verify_option_from_env()) as client:
            r = client.post(url, json=payload)
        
        if r.status_code != 200:
            try:
                body = r.text
            except Exception:
                body = "<no body>"
            logging.error("telegram edit error http=%s body=%s", r.status_code, body)
            return False
        
        try:
            data = r.json()
        except Exception:
            logging.error("telegram edit error: invalid json body=%s", r.text)
            return False
        
        if not data.get("ok"):
            logging.error("telegram edit error ok=false desc=%s", data.get("description"))
            return False
        
        return True

    try:
        return run_with_retries(_do_request, attempts=3, base_delay_s=0.5, backoff_factor=2.0)
    except Exception:
        logging.exception("telegram edit exception")
        return False


def check_bot_access(bot_token: str, chat_id: int, timeout_s: int) -> None:
    """Logs chat info via Bot API to verify access/permissions."""
    url = f"https://api.telegram.org/bot{bot_token}/getChat"
    params = {"chat_id": chat_id}
    try:
        with httpx.Client(timeout=timeout_s, verify=_verify_option_from_env()) as client:
            r = client.get(url, params=params)
            if r.status_code != 200:
                logging.error("getChat error http=%s body=%s", r.status_code, r.text)
                return
            data = r.json()
            if not data.get("ok"):
                logging.error("getChat ok=false desc=%s", data.get("description"))
                return
            result = data.get("result", {})
            logging.info(
                "bot access ok | chat_title=%s type=%s id=%s",
                result.get("title"),
                result.get("type"),
                result.get("id"),
            )
    except Exception:
        logging.exception("getChat exception")