import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
from database import init_db, async_session, User, Balance
from sqlalchemy import select
import aiohttp
from keyboards import get_main_keyboard, get_exchange_keyboard, get_deposit_assets_keyboard, get_settings_keyboard
from aiocryptopay import AioCryptoPay, Networks

class ExchangeState(StatesGroup):
    select_pair = State()
    enter_amount = State()

class DepositState(StatesGroup):
    select_asset = State()
    enter_amount = State()

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in the environment variables.")

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Initialize Crypto Pay
CRYPTOPAY_API_KEY = os.getenv("CRYPTOPAY_API_KEY")
if not CRYPTOPAY_API_KEY:
    raise ValueError("CRYPTOPAY_API_KEY is not set in the environment variables.")
crypto = AioCryptoPay(token=CRYPTOPAY_API_KEY, network=Networks.MAIN_NET)

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
            await session.flush() # Flush to get the new_user.id

            # Create initial balances
            initial_balances = [
                Balance(user_id=new_user.id, asset='USDT', amount=0.0),
                Balance(user_id=new_user.id, asset='BTC', amount=0.0),
                Balance(user_id=new_user.id, asset='ETH', amount=0.0),
                Balance(user_id=new_user.id, asset='TON', amount=0.0),
            ]
            session.add_all(initial_balances)
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
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://min-api.cryptocompare.com/data/pricemulti?fsyms=BTC,ETH,TON&tsyms=USDT') as resp:
                data = await resp.json()
                
        btc_price = data.get('BTC', {}).get('USDT', 0)
        eth_price = data.get('ETH', {}).get('USDT', 0)
        ton_price = data.get('TON', {}).get('USDT', 0)
        
        response = (
            f"📈 **Current Prices:**\n\n"
            f"**BTC/USDT:** ${btc_price:,.2f}\n"
            f"**ETH/USDT:** ${eth_price:,.2f}\n"
            f"**TON/USDT:** ${ton_price:,.2f}"
        )
        await message.answer(response, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error fetching prices: {e}")
        await message.answer("Sorry, I couldn't fetch the prices right now. Please try again later.")

@dp.message(F.text == "💼 Wallet")
async def wallet_handler(message: types.Message) -> None:
    """
    This handler receives messages with "💼 Wallet" text
    """
    user_id = message.from_user.id

    async with async_session() as session:
        # Get the user's internal ID
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("User not found. Please use /start to register.")
            return

        # Get the user's balances
        stmt = select(Balance).where(Balance.user_id == user.id)
        result = await session.execute(stmt)
        balances = result.scalars().all()

    if not balances:
        await message.answer("Your wallet is empty.")
        return

    # Format the response
    response = "💼 **Your Wallet:**\n\n"
    
    # Define emojis for assets
    emojis = {
        'USDT': '💵',
        'BTC': '🪙',
        'ETH': '🔷',
        'TON': '💎'
    }

    for balance in balances:
        emoji = emojis.get(balance.asset, '💰')
        # Format amount: 2 decimal places for USDT, up to 8 for crypto
        if balance.asset == 'USDT':
            formatted_amount = f"{balance.amount:,.2f}"
        else:
            # Remove trailing zeros after decimal point for crypto, but keep at least one zero if it's exactly 0
            formatted_amount = f"{balance.amount:.8f}".rstrip('0').rstrip('.') if balance.amount > 0 else "0.00"
            
        response += f"{emoji} **{balance.asset}:** {formatted_amount}\n"

    await message.answer(response, parse_mode="Markdown")

@dp.message(F.text == "💱 Exchange")
async def exchange_handler(message: types.Message, state: FSMContext) -> None:
    """
    This handler receives messages with "💱 Exchange" text
    """
    await message.answer(
        "Select a trading pair:",
        reply_markup=get_exchange_keyboard()
    )
    await state.set_state(ExchangeState.select_pair)

@dp.callback_query(ExchangeState.select_pair, F.data.startswith("swap_usdt_"))
async def process_pair_selection(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    target_asset = callback_query.data.split("_")[2].upper()
    await state.update_data(target_asset=target_asset)
    
    await callback_query.message.answer(f"How much USDT do you want to swap for {target_asset}?")
    await state.set_state(ExchangeState.enter_amount)
    await callback_query.answer()

@dp.message(ExchangeState.enter_amount)
async def process_amount(message: types.Message, state: FSMContext) -> None:
    try:
        amount_usdt = float(message.text)
        if amount_usdt <= 0:
            raise ValueError("Amount must be positive.")
    except ValueError:
        await message.answer("Please enter a valid positive number.")
        return

    data = await state.get_data()
    target_asset = data['target_asset']
    user_id = message.from_user.id

    async with async_session() as session:
        # Get user
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("User not found. Please use /start to register.")
            await state.clear()
            return

        # Check USDT balance
        stmt = select(Balance).where(Balance.user_id == user.id, Balance.asset == 'USDT')
        result = await session.execute(stmt)
        usdt_balance = result.scalar_one_or_none()

        if not usdt_balance or usdt_balance.amount < amount_usdt:
            await message.answer("Insufficient USDT balance.")
            await state.clear()
            return

        # Fetch price
        await message.answer(f"Fetching current price for {target_asset}/USDT...")
        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(f'https://min-api.cryptocompare.com/data/price?fsym={target_asset}&tsyms=USDT') as resp:
                    data = await resp.json()
                    price = data.get('USDT')
                    if not price:
                        raise ValueError(f"Could not get price for {target_asset}")
        except Exception as e:
            logging.error(f"Error fetching price for {target_asset}: {e}")
            await message.answer("Error fetching price. Please try again later.")
            await state.clear()
            return

        amount_target = amount_usdt / price

        # Update balances
        try:
            usdt_balance.amount -= amount_usdt
            
            stmt = select(Balance).where(Balance.user_id == user.id, Balance.asset == target_asset)
            result = await session.execute(stmt)
            target_balance = result.scalar_one_or_none()

            if target_balance:
                target_balance.amount += amount_target
            else:
                new_balance = Balance(user_id=user.id, asset=target_asset, amount=amount_target)
                session.add(new_balance)

            await session.commit()
            
            await message.answer(
                f"Successfully swapped {amount_usdt:,.2f} USDT for {amount_target:.8f} {target_asset}!\n"
                f"Rate: 1 {target_asset} = {price:,.2f} USDT"
            )
        except Exception as e:
            await session.rollback()
            logging.error(f"Database error during swap: {e}")
            await message.answer("An error occurred during the swap. Please try again.")
        finally:
            await state.clear()

@dp.message(F.text == "📥 Deposit")
async def deposit_handler(message: types.Message, state: FSMContext) -> None:
    """
    This handler receives messages with "📥 Deposit" text
    """
    await message.answer(
        "Select an asset to deposit:",
        reply_markup=get_deposit_assets_keyboard()
    )
    await state.set_state(DepositState.select_asset)

@dp.callback_query(DepositState.select_asset, F.data.startswith("deposit_asset_"))
async def process_deposit_asset_selection(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    asset = callback_query.data.split("_")[2].upper()
    await state.update_data(deposit_asset=asset)
    
    await callback_query.message.answer(f"How much {asset} do you want to deposit?")
    await state.set_state(DepositState.enter_amount)
    await callback_query.answer()

@dp.message(DepositState.enter_amount)
async def process_deposit_amount(message: types.Message, state: FSMContext) -> None:
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError("Amount must be positive.")
    except ValueError:
        await message.answer("Please enter a valid positive number.")
        return

    data = await state.get_data()
    asset = data['deposit_asset']
    
    try:
        invoice = await crypto.create_invoice(asset=asset, amount=amount)
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Pay", url=invoice.bot_invoice_url)],
                [types.InlineKeyboardButton(text="✅ Check Payment", callback_data=f"check_payment_{invoice.invoice_id}")]
            ]
        )
        
        await message.answer(
            f"Please pay {amount} {asset} using the link below:",
            reply_markup=keyboard
        )
    except Exception as e:
        logging.error(f"Error creating invoice: {e}")
        await message.answer("An error occurred while creating the invoice. Please try again later.")
    finally:
        await state.clear()

@dp.callback_query(F.data.startswith("check_payment_"))
async def check_payment_handler(callback_query: types.CallbackQuery) -> None:
    invoice_id = int(callback_query.data.split("_")[2])
    user_id = callback_query.from_user.id
    
    try:
        invoices = await crypto.get_invoices(invoice_ids=invoice_id)
        if not invoices:
            await callback_query.answer("Invoice not found.", show_alert=True)
            return
            
        invoice = invoices[0]
        
        if invoice.status == 'paid':
            async with async_session() as session:
                stmt = select(User).where(User.telegram_id == user_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if user:
                    stmt = select(Balance).where(Balance.user_id == user.id, Balance.asset == invoice.asset)
                    result = await session.execute(stmt)
                    balance = result.scalar_one_or_none()
                    
                    if balance:
                        balance.amount += float(invoice.amount)
                    else:
                        new_balance = Balance(user_id=user.id, asset=invoice.asset, amount=float(invoice.amount))
                        session.add(new_balance)
                        
                    await session.commit()
                    await callback_query.message.edit_text(f"✅ Payment of {invoice.amount} {invoice.asset} received! Your balance has been updated.")
                else:
                    await callback_query.answer("User not found in database.", show_alert=True)
        else:
            await callback_query.answer("Payment is still pending.", show_alert=True)
    except Exception as e:
        logging.error(f"Error checking payment: {e}")
        await callback_query.answer("An error occurred while checking the payment.", show_alert=True)

@dp.message(F.text == "⚙️ Settings")
async def settings_handler(message: types.Message) -> None:
    """
    This handler receives messages with "⚙️ Settings" text
    """
    await message.answer(
        "⚙️ **Settings Menu**\nChoose an option below:",
        reply_markup=get_settings_keyboard()
    )

@dp.callback_query(F.data == "settings_my_id")
async def settings_my_id_handler(callback_query: types.CallbackQuery) -> None:
    await callback_query.message.answer(f"Your Telegram ID is: {callback_query.from_user.id}")
    await callback_query.answer()

@dp.callback_query(F.data == "settings_language")
async def settings_language_handler(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer("Language selection coming soon!", show_alert=True)
async def main() -> None:
    # Initialize database
    await init_db()
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())