from __future__ import annotations

import httpx
import logging
import re
from typing import Optional, Dict
from datetime import datetime, timedelta
from utils.retry_utils import run_with_retries


class PriceInfo:
    """토큰 가격 정보"""
    def __init__(self, symbol: str, price_usd: float, coingecko_url: str):
        self.symbol = symbol
        self.price_usd = price_usd
        self.coingecko_url = coingecko_url
        self.fetched_at = datetime.utcnow()


class PriceFetcher:
    """CoinGecko API를 통한 토큰 가격 조회"""
    
    def __init__(self, timeout_s: int = 10):
        self.timeout_s = timeout_s
        self.cache: Dict[str, PriceInfo] = {}
        self.cache_ttl_seconds = 60  # 1분 캐시
    
    def _clean_symbol(self, symbol: str) -> str:
        """$ENSO -> enso"""
        if not symbol:
            return ""
        cleaned = symbol.strip().upper()
        if cleaned.startswith("$"):
            cleaned = cleaned[1:]
        return cleaned.lower()
    
    def _search_coingecko(self, symbol: str) -> Optional[Dict]:
        """CoinGecko에서 토큰 검색"""
        url = "https://api.coingecko.com/api/v3/search"
        params = {"query": symbol}
        
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                r = client.get(url, params=params)
                if r.status_code != 200:
                    logging.warning("coingecko search failed: http=%s", r.status_code)
                    return None
                
                data = r.json()
                coins = data.get("coins", [])
                
                # 심볼이 정확히 일치하는 첫 번째 결과 찾기
                for coin in coins:
                    if coin.get("symbol", "").lower() == symbol.lower():
                        # <--- 수정: [ ] 가 아니라 { } (딕셔너리)여야 합니다.
                        return {
                            "id": coin.get("id"),
                            "symbol": coin.get("symbol"),
                            "name": coin.get("name"),
                        }
                
                # 정확한 일치가 없으면 첫 번째 결과 사용
                if coins:
                    return {
                        "id": coins[0].get("id"),
                        "symbol": coins[0].get("symbol"),
                        "name": coins[0].get("name"),
                    }
                
                return None
        except Exception:
            logging.exception("coingecko search exception")
            return None
    
    def _get_price(self, coin_id: str) -> Optional[float]:
        """CoinGecko에서 가격 조회"""
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": "usd"
        }
        
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                r = client.get(url, params=params)
                if r.status_code != 200:
                    logging.warning("coingecko price failed: http=%s", r.status_code)
                    return None
                
                data = r.json()
                price = data.get(coin_id, {}).get("usd")
                return float(price) if price else None
        except Exception:
            logging.exception("coingecko price exception")
            return None
    
    def fetch_price(self, token_symbol: str, use_cache: bool = True) -> Optional[PriceInfo]:
        """토큰 가격 조회 (캐시 지원)"""
        if not token_symbol or token_symbol == "N/A":
            return None
        
        symbol = self._clean_symbol(token_symbol)
        
        # 캐시 체크
        if use_cache and symbol in self.cache:
            cached = self.cache[symbol]
            age = (datetime.utcnow() - cached.fetched_at).total_seconds()
            if age < self.cache_ttl_seconds:
                logging.debug("price cache hit: %s (age=%ds)", symbol, age)
                return cached
        
        # API 조회
        def _do_fetch() -> Optional[PriceInfo]:
            # 1. 토큰 검색
            coin_info = self._search_coingecko(symbol)
            if not coin_info:
                logging.info("token not found on coingecko: %s", symbol)
                return None
            
            coin_id = coin_info["id"]
            
            # 2. 가격 조회
            price = self._get_price(coin_id)
            if price is None:
                logging.info("price not available: %s (id=%s)", symbol, coin_id)
                return None
            
            # 3. CoinGecko URL 생성
            coingecko_url = f"https://www.coingecko.com/en/coins/{coin_id}"
            
            price_info = PriceInfo(
                symbol=symbol,
                price_usd=price,
                coingecko_url=coingecko_url
            )
            
            # 캐시 저장
            self.cache[symbol] = price_info
            
            logging.info(
                "price fetched: %s = $%.4f (url=%s)",
                symbol,
                price,
                coingecko_url
            )
            
            return price_info
        
        try:
            return run_with_retries(_do_fetch, attempts=2, base_delay_s=1.0)
        except Exception:
            logging.exception("fetch_price failed: %s", symbol)
            return None
    
    def calculate_value(self, reward_str: str, price_info: Optional[PriceInfo]) -> Optional[float]:
        """보상 문자열에서 총 가치 계산
        
        예: "150 $WAL" + price_info -> 150 * price_usd
        """
        if not reward_str or not price_info or reward_str == "N/A":
            return None
        
        # <--- 수정: 문자열에서 발견되는 "첫 번째 숫자 그룹"을 찾도록 수정
        # (공백, $ 기호 등에 관계없이 "320 $CLO" -> "320" 추출)
        match = re.search(r"([\d,\.]+)", reward_str)
        if not match:
            # 매칭 실패 시 로그 추가
            logging.warning("calculate_value regex failed: reward=%s", reward_str)
            return None
        
        try:
            amount_str = match.group(1).replace(",", "")
            amount = float(amount_str)
            
            if amount <= 0:
                logging.warning("calculate_value found non-positive amount: %s", amount_str)
                return None
                
            return amount * price_info.price_usd
        except Exception:
            logging.exception("calculate_value failed: reward=%s", reward_str)
            return None