import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import BOT_TOKEN
from database import init_db, migrate_db
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
    
    # Initialize database (migrate schema if MIGRATE_DB=true)
    if os.getenv("MIGRATE_DB", "false").lower() == "true":
        logger.warning("⚠️ Migrating database schema (adding missing columns)...")
        await migrate_db()
        logger.info("Database migration completed — all data preserved")
    else:
        await init_db()
        logger.info("Database initialized")
    
    # Start background transaction poller
    poller_task = asyncio.create_task(poll_transactions(bot))
    logger.info("Transaction poller started")
    
    # Clear old bot commands and set new ones
    await bot.delete_my_commands()
    await bot.set_my_commands([
        BotCommand(command="start", description="Start the bot"),
    ])
    logger.info("Bot commands updated")
    
    # Start polling for Telegram updates
    logger.info("Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())