from __future__ import annotations

import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from price_fetcher import PriceFetcher, PriceInfo
import httpx


@dataclass
class ScheduledPriceCheck:
    """스케줄된 가격 체크 작업"""
    token_symbol: str
    listing_time: datetime  # UTC
    bot_token: str
    chat_id: int
    message_id: int
    reward_str: str  # "150 $WAL"
    current_html: str  # 현재 메시지 HTML
    
    # 상태
    price_found: bool = False
    check_count: int = 0
    last_check: Optional[datetime] = None


class PriceScheduler:
    """상장 전후 가격 모니터링 스케줄러"""
    
    def __init__(self, price_fetcher: PriceFetcher, http_timeout_s: int = 10):
        self.fetcher = price_fetcher
        self.http_timeout_s = http_timeout_s
        self.tasks: dict[int, ScheduledPriceCheck] = {}  # message_id -> task
        self.running = False
    
    def schedule(
        self,
        token_symbol: str,
        listing_time_str: str,  # "10/14 16:00 KST"
        bot_token: str,
        chat_id: int,
        message_id: int,
        reward_str: str,
        current_html: str,
    ) -> bool:
        """상장 시간 기준으로 가격 체크 스케줄링"""
        
        # 상장 시간 파싱 (KST -> UTC)
        listing_utc = self._parse_listing_time(listing_time_str)
        if not listing_utc:
            logging.warning("failed to parse listing time: %s", listing_time_str)
            return False
        
        # 이미 상장 후 5분 지났으면 스킵
        now = datetime.utcnow()
        if now > listing_utc + timedelta(minutes=5):
            logging.info("listing already passed: %s", listing_time_str)
            return False
        
        task = ScheduledPriceCheck(
            token_symbol=token_symbol,
            listing_time=listing_utc,
            bot_token=bot_token,
            chat_id=chat_id,
            message_id=message_id,
            reward_str=reward_str,
            current_html=current_html,
        )
        
        self.tasks[message_id] = task
        
        logging.info(
            "scheduled price check: token=%s listing=%s msg_id=%s",
            token_symbol,
            listing_time_str,
            message_id,
        )
        
        return True
    
    def _parse_listing_time(self, time_str: str) -> Optional[datetime]:
        """KST 시간 문자열을 UTC datetime으로 변환
        
        예: "10/14 16:00 KST" -> datetime(2025, 10, 14, 7, 0, 0, UTC)
        """
        import re
        
        # "M/D HH:mm KST" 패턴
        match = re.search(r"(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})\s+KST", time_str)
        if not match:
            return None
        
        month = int(match.group(1))
        day = int(match.group(2))
        hour = int(match.group(3))
        minute = int(match.group(4))
        
        # 현재 연도 사용
        year = datetime.utcnow().year
        
        # KST (UTC+9) -> UTC
        try:
            kst_time = datetime(year, month, day, hour, minute)
            utc_time = kst_time - timedelta(hours=9)
            return utc_time
        except Exception:
            logging.exception("failed to parse time: %s", time_str)
            return None
    
    async def _check_price_and_update(self, task: ScheduledPriceCheck) -> bool:
        """가격 체크 후 메시지 업데이트
        
        Returns:
            True if price found and message updated
        """
        task.check_count += 1
        task.last_check = datetime.utcnow()
        
        # 가격 조회 (캐시 사용 안 함)
        price_info = self.fetcher.fetch_price(task.token_symbol, use_cache=False)
        
        if not price_info:
            logging.debug(
                "price not found yet: %s (attempt %d)",
                task.token_symbol,
                task.check_count,
            )
            return False
        
        # 가격 발견!
        task.price_found = True
        
        # 총 가치 계산
        total_value = self.fetcher.calculate_value(task.reward_str, price_info)
        
        # HTML 업데이트
        new_html = self._inject_price_to_html(
            task.current_html,
            price_info,
            total_value,
        )
        
        # 메시지 수정
        success = update_message_text(
            task.bot_token,
            task.chat_id,
            task.message_id,
            new_html,
            self.http_timeout_s,
        )
        
        if success:
            logging.info(
                "price updated: %s = $%.4f (msg_id=%s, value=%.2f USDT)",
                task.token_symbol,
                price_info.price_usd,
                task.message_id,
                total_value or 0,
            )
        else:
            logging.error("failed to update message: msg_id=%s", task.message_id)
        
        return success
    
    def _inject_price_to_html(
        self,
        original_html: str,
        price_info: PriceInfo,
        total_value: Optional[float],
    ) -> str:
        """HTML에 가격 정보 주입
        
        "⭐ <b>title</b>" 다음에 가격 라인 추가
        """
        import re
        
        # 가격 라인 생성
        if total_value:
            price_line = f'\n💰 <b><a href="{price_info.coingecko_url}">예상 가치: {total_value:.2f} USDT</a></b>'
        else:
            price_line = f'\n💰 <b><a href="{price_info.coingecko_url}">가격: ${price_info.price_usd:.4f}</a></b>'
        
        # "⭐ <b>..." 패턴 찾아서 다음에 삽입
        pattern = r"(⭐\s*<b>.*?</b>)"
        
        def replacer(match):
            return match.group(1) + price_line
        
        new_html = re.sub(pattern, replacer, original_html, count=1)
        
        # 패턴 못 찾으면 맨 앞에 추가
        if new_html == original_html:
            new_html = price_line.lstrip() + "\n\n" + original_html
        
        return new_html
    
    async def _monitor_task(self, message_id: int) -> None:
        """개별 태스크 모니터링 루프"""
        task = self.tasks.get(message_id)
        if not task:
            return
        
        now = datetime.utcnow()
        
        # 시작 시간: 상장 5분 전
        start_time = task.listing_time - timedelta(minutes=5)
        
        # 종료 시간: 상장 후 5분
        end_time = task.listing_time + timedelta(minutes=5)
        
        # 아직 시작 전이면 대기
        if now < start_time:
            wait_seconds = (start_time - now).total_seconds()
            
            # 10분 이상 남았으면 로그를 5분마다만 출력
            # 10분 이내면 1분마다 출력
            if wait_seconds > 600:
                log_interval = 300  # 5분
            else:
                log_interval = 60   # 1분
            
            # 마지막 로그가 없거나 충분한 시간이 지났으면 로그 출력
            if not hasattr(task, '_last_wait_log') or \
               (now - task._last_wait_log).total_seconds() >= log_interval:
                logging.info(
                    "waiting for price check start: token=%s listing_time=%s wait=%.0fm",
                    task.token_symbol,
                    task.listing_time.strftime("%Y-%m-%d %H:%M UTC"),
                    wait_seconds / 60,
                )
                task._last_wait_log = now
            
            # 실제 대기는 최대 1분씩
            await asyncio.sleep(min(wait_seconds, 60))
            return
        
        # 종료 시간 지났으면 제거
        if now > end_time:
            logging.info(
                "price check ended: token=%s (not found)",
                task.token_symbol,
            )
            del self.tasks[message_id]
            return
        
        # 이미 가격 찾았으면 제거
        if task.price_found:
            del self.tasks[message_id]
            return
        
        # 가격 체크
        try:
            await self._check_price_and_update(task)
        except Exception:
            logging.exception("price check error: msg_id=%s", message_id)
        
        # 다음 체크까지 대기
        # 상장 전: 15초, 상장 후: 30초 (API 부담 줄이기)
        if now < task.listing_time:
            await asyncio.sleep(15)
        else:
            await asyncio.sleep(30)
    
    async def run(self) -> None:
        """스케줄러 메인 루프"""
        self.running = True
        logging.info("price scheduler started")
        
        while self.running:
            try:
                # 모든 태스크 체크 (복사본으로 순회 - 중간 삭제 대응)
                message_ids = list(self.tasks.keys())
                
                for msg_id in message_ids:
                    await self._monitor_task(msg_id)
                
                # 태스크 없으면 길게 대기
                if not self.tasks:
                    await asyncio.sleep(30)
                else:
                    await asyncio.sleep(1)
                    
            except Exception:
                logging.exception("scheduler loop error")
                await asyncio.sleep(5)
        
        logging.info("price scheduler stopped")
    
    def stop(self) -> None:
        """스케줄러 중지"""
        self.running = False