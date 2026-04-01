import asyncio
import logging
import os

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import init_db, reset_db
from handlers import start, exchange, history, settings
from utils.poller import poll_transactions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Initialize and start the bot."""
    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Register routers (order matters — first registered gets priority)
    dp.include_router(start.router)
    dp.include_router(exchange.router)
    dp.include_router(history.router)
    dp.include_router(settings.router)
    
    # Initialize database (reset tables if RESET_DB=true)
    if os.getenv("RESET_DB", "false").lower() == "true":
        logger.warning("⚠️ Resetting database tables...")
        await reset_db()
        logger.info("Database tables reset successfully")
    else:
        await init_db()
        logger.info("Database initialized")
    
    # Start background transaction poller
    poller_task = asyncio.create_task(poll_transactions(bot))
    logger.info("Transaction poller started")
    
    # Start polling for Telegram updates
    logger.info("Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())