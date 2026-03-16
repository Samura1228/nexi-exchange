import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from database import init_db, async_session, User
from sqlalchemy import select
import ccxt.async_support as ccxt
from keyboards import get_main_keyboard

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in the environment variables.")

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    user_id = message.from_user.id
    username = message.from_user.username

    # Save user to database if not exists
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            new_user = User(telegram_id=user_id, username=username)
            session.add(new_user)
            await session.commit()

    await message.answer(
        f"Hello, {message.from_user.full_name}! Welcome to the Crypto Exchange Bot.",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "📈 Prices")
async def prices_handler(message: types.Message) -> None:
    """
    This handler receives messages with "📈 Prices" text
    """
    await message.answer("Fetching current prices...")
    
    exchange = ccxt.binance()
    try:
        # Fetch tickers concurrently
        btc_ticker, eth_ticker = await asyncio.gather(
            exchange.fetch_ticker('BTC/USDT'),
            exchange.fetch_ticker('ETH/USDT')
        )
        
        btc_price = btc_ticker['last']
        eth_price = eth_ticker['last']
        
        response = (
            f"📈 **Current Prices:**\n\n"
            f"**BTC/USDT:** ${btc_price:,.2f}\n"
            f"**ETH/USDT:** ${eth_price:,.2f}"
        )
        await message.answer(response, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error fetching prices: {e}")
        await message.answer("Sorry, I couldn't fetch the prices right now. Please try again later.")
    finally:
        await exchange.close()

async def main() -> None:
    # Initialize database
    await init_db()
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())