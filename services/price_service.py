import aiohttp
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Simple in-memory cache for prices (TTL: 60 seconds)
_price_cache: Dict[str, tuple] = {}  # {coin_id: (price_usd, timestamp)}
CACHE_TTL = 60  # seconds

# Mapping from our ticker symbols to CoinGecko IDs
TICKER_TO_COINGECKO = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "ton": "the-open-network",
    "usdt": "tether",
    "ltc": "litecoin",
    "xrp": "ripple",
    "trx": "tron",
}


async def get_crypto_price_usd(ticker: str) -> Optional[float]:
    """
    Get the current USD price of a cryptocurrency.
    Uses CoinGecko free API with simple caching.
    
    Args:
        ticker: Crypto ticker (e.g., "btc", "eth")
        
    Returns: Price in USD or None if unavailable
    """
    ticker = ticker.lower()
    
    # USDT is always ~$1
    if ticker == "usdt":
        return 1.0
    
    coingecko_id = TICKER_TO_COINGECKO.get(ticker)
    if not coingecko_id:
        logger.warning(f"Unknown ticker for price lookup: {ticker}")
        return None
    
    # Check cache
    now = time.time()
    if coingecko_id in _price_cache:
        cached_price, cached_time = _price_cache[coingecko_id]
        if now - cached_time < CACHE_TTL:
            return cached_price
    
    # Fetch from CoinGecko
    url = f"https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coingecko_id,
        "vs_currencies": "usd",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"CoinGecko API error: {resp.status}")
                    return None
                data = await resp.json()
                price = data.get(coingecko_id, {}).get("usd")
                if price:
                    _price_cache[coingecko_id] = (price, now)
                    return float(price)
                return None
    except Exception as e:
        logger.error(f"CoinGecko price fetch error: {e}")
        # Return cached value even if expired, as fallback
        if coingecko_id in _price_cache:
            return _price_cache[coingecko_id][0]
        return None


def usd_to_crypto(usd_amount: float, crypto_price_usd: float) -> float:
    """Convert USD amount to crypto amount."""
    if crypto_price_usd <= 0:
        return 0.0
    return usd_amount / crypto_price_usd


def crypto_to_usd(crypto_amount: float, crypto_price_usd: float) -> float:
    """Convert crypto amount to USD."""
    return crypto_amount * crypto_price_usd