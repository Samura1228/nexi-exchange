import asyncio
import logging
from decimal import Decimal

import aiohttp
from aiogram import Bot
from sqlalchemy import select

from database import async_session, PriceAlert
from services.price_service import TICKER_TO_COINGECKO

logger = logging.getLogger(__name__)

# Reverse mapping: coingecko_id -> ticker
COINGECKO_TO_TICKER = {v: k for k, v in TICKER_TO_COINGECKO.items()}

# All CoinGecko IDs we need for alerts (exclude usdt — not useful for alerts)
ALERT_COINGECKO_IDS = [
    "bitcoin", "ethereum", "solana", "the-open-network", "ripple", "tron", "litecoin"
]


async def _fetch_all_prices() -> dict[str, float]:
    """Fetch prices for all alert-supported currencies in a single API call.
    
    Returns: dict mapping ticker (e.g. "btc") to USD price.
    """
    ids_param = ",".join(ALERT_COINGECKO_IDS)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_param}&vs_currencies=usd"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.error(f"CoinGecko API error in price checker: {resp.status}")
                    return {}
                data = await resp.json()

        prices = {}
        for cg_id, price_data in data.items():
            ticker = COINGECKO_TO_TICKER.get(cg_id)
            if ticker and "usd" in price_data:
                prices[ticker] = float(price_data["usd"])
        return prices
    except Exception as e:
        logger.error(f"Price checker fetch error: {e}")
        return {}


async def check_price_alerts(bot: Bot) -> None:
    """Background task: check all active price alerts every 60 seconds.
    
    When a price crosses the threshold, send a notification and deactivate the alert.
    """
    logger.info("Price alert checker started")

    while True:
        await asyncio.sleep(60)
        try:
            # 1. Fetch current prices (single API call)
            prices = await _fetch_all_prices()
            if not prices:
                continue

            # 2. Query all active alerts
            async with async_session() as session:
                stmt = select(PriceAlert).where(PriceAlert.is_active == True)
                result = await session.execute(stmt)
                alerts = result.scalars().all()

                if not alerts:
                    continue

                triggered_count = 0
                for alert in alerts:
                    current_price = prices.get(alert.currency)
                    if current_price is None:
                        continue

                    # Check if threshold crossed
                    target = float(alert.target_price)
                    triggered = False

                    if alert.direction == "above" and current_price >= target:
                        triggered = True
                    elif alert.direction == "below" and current_price <= target:
                        triggered = True

                    if triggered:
                        # Deactivate alert
                        alert.is_active = False
                        triggered_count += 1

                        # Send notification
                        direction_emoji = "📈" if alert.direction == "above" else "📉"
                        notification_text = (
                            f"🔔 **Price Alert Triggered!**\n\n"
                            f"{direction_emoji} **{alert.currency.upper()}** is now {alert.direction} "
                            f"**${target:,.2f}**!\n"
                            f"Current price: **${current_price:,.2f}**\n\n"
                            f"Your alert for {alert.currency.upper()} {alert.direction} "
                            f"${target:,.2f} has been triggered and removed."
                        )

                        try:
                            await bot.send_message(
                                alert.telegram_id,
                                notification_text,
                                parse_mode="Markdown",
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to send alert notification to {alert.telegram_id}: {e}"
                            )

                if triggered_count > 0:
                    await session.commit()
                    logger.info(f"Price checker: {triggered_count} alert(s) triggered")

        except Exception as e:
            logger.error(f"Price checker error: {e}")