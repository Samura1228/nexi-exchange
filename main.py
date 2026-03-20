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
from keyboards import get_main_keyboard, get_exchange_keyboard, get_exchange_to_keyboard, get_deposit_assets_keyboard, get_settings_keyboard, get_deposit_method_keyboard, get_usdt_network_keyboard, get_withdraw_asset_keyboard
from aiocryptopay import AioCryptoPay, Networks

class WithdrawState(StatesGroup):
    asset = State()
    address = State()
    amount = State()

class ExchangeState(StatesGroup):
    from_asset = State()
    to_asset = State()
    amount = State()

class DepositState(StatesGroup):
    method = State()
    asset = State()
    network = State()
    amount = State()

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in the environment variables.")

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Initialize NowPayments
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
if not NOWPAYMENTS_API_KEY:
    raise ValueError("NOWPAYMENTS_API_KEY is not set in the environment variables.")

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
        "What do you want to exchange FROM?",
        reply_markup=get_exchange_keyboard()
    )
    await state.set_state(ExchangeState.from_asset)

@dp.callback_query(ExchangeState.from_asset, F.data.startswith("exch_from_"))
async def process_from_asset_selection(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    from_asset = callback_query.data.split("_")[2].upper()
    await state.update_data(from_asset=from_asset)
    
    await callback_query.message.answer(
        f"What do you want to exchange {from_asset} TO?",
        reply_markup=get_exchange_to_keyboard(from_asset)
    )
    await state.set_state(ExchangeState.to_asset)
    await callback_query.answer()

@dp.callback_query(ExchangeState.to_asset, F.data.startswith("exch_to_"))
async def process_to_asset_selection(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    to_asset = callback_query.data.split("_")[2].upper()
    await state.update_data(to_asset=to_asset)
    
    data = await state.get_data()
    from_asset = data['from_asset']
    
    await callback_query.message.answer(f"How much {from_asset} do you want to swap for {to_asset}?")
    await state.set_state(ExchangeState.amount)
    await callback_query.answer()

@dp.message(ExchangeState.amount)
async def process_exchange_amount(message: types.Message, state: FSMContext) -> None:
    try:
        amount_from = float(message.text)
        if amount_from <= 0:
            raise ValueError("Amount must be positive.")
    except ValueError:
        await message.answer("Please enter a valid positive number.")
        return

    data = await state.get_data()
    from_asset = data['from_asset']
    to_asset = data['to_asset']
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

        # Check from_asset balance
        stmt = select(Balance).where(Balance.user_id == user.id, Balance.asset == from_asset)
        result = await session.execute(stmt)
        from_balance = result.scalar_one_or_none()

        if not from_balance or from_balance.amount < amount_from:
            await message.answer(f"Insufficient {from_asset} balance.")
            await state.clear()
            return

        # Fetch price
        await message.answer(f"Fetching current prices for {from_asset} and {to_asset}...")
        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(f'https://min-api.cryptocompare.com/data/pricemulti?fsyms={from_asset},{to_asset}&tsyms=USDT') as resp:
                    price_data = await resp.json()
                    
                    from_price_usdt = price_data.get(from_asset, {}).get('USDT')
                    to_price_usdt = price_data.get(to_asset, {}).get('USDT')
                    
                    if not from_price_usdt or not to_price_usdt:
                        raise ValueError(f"Could not get prices for {from_asset} or {to_asset}")
        except Exception as e:
            logging.error(f"Error fetching prices for {from_asset} and {to_asset}: {e}")
            await message.answer("Error fetching prices. Please try again later.")
            await state.clear()
            return

        # Calculate exchange rate and target amount
        exchange_rate = from_price_usdt / to_price_usdt
        amount_to = amount_from * exchange_rate

        # Update balances
        try:
            from_balance.amount -= amount_from
            
            stmt = select(Balance).where(Balance.user_id == user.id, Balance.asset == to_asset)
            result = await session.execute(stmt)
            to_balance = result.scalar_one_or_none()

            if to_balance:
                to_balance.amount += amount_to
            else:
                new_balance = Balance(user_id=user.id, asset=to_asset, amount=amount_to)
                session.add(new_balance)

            await session.commit()
            
            await message.answer(
                f"Successfully swapped {amount_from:,.8f} {from_asset} for {amount_to:,.8f} {to_asset}!\n"
                f"Rate: 1 {from_asset} = {exchange_rate:,.8f} {to_asset}"
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
        "Select a deposit method:",
        reply_markup=get_deposit_method_keyboard()
    )
    await state.set_state(DepositState.method)

@dp.callback_query(DepositState.method, F.data.startswith("dep_method_"))
async def process_deposit_method_selection(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    method = callback_query.data.split("_")[2]
    await state.update_data(method=method)
    
    await callback_query.message.answer(
        "Select an asset to deposit:",
        reply_markup=get_deposit_assets_keyboard()
    )
    await state.set_state(DepositState.asset)
    await callback_query.answer()

@dp.callback_query(DepositState.asset, F.data.startswith("deposit_asset_"))
async def process_deposit_asset_selection(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    asset = callback_query.data.split("_")[2].upper()
    await state.update_data(asset=asset)
    
    data = await state.get_data()
    method = data.get('method')
    
    if method == 'np' and asset == 'USDT':
        await callback_query.message.answer(
            "Select the network for your USDT deposit:",
            reply_markup=get_usdt_network_keyboard()
        )
        await state.set_state(DepositState.network)
    else:
        await state.update_data(network=None)
        if method == 'np':
            currency = asset.lower()
            headers = {"x-api-key": NOWPAYMENTS_API_KEY}
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f'https://api.nowpayments.io/v1/min-amount?currency_from={currency}&currency_to={currency}', headers=headers) as resp:
                        resp_data = await resp.json()
                        min_amount = resp_data.get('min_amount')
                if min_amount:
                    await callback_query.message.answer(f"How much {asset} do you want to deposit?\n\n*(Minimum: {min_amount} {asset})*", parse_mode="Markdown")
                else:
                    await callback_query.message.answer(f"How much {asset} do you want to deposit?")
            except Exception as e:
                logging.error(f"Error fetching min amount: {e}")
                await callback_query.message.answer(f"How much {asset} do you want to deposit?")
        else:
            await callback_query.message.answer(f"How much {asset} do you want to deposit?")
        await state.set_state(DepositState.amount)
        
    await callback_query.answer()

@dp.callback_query(DepositState.network, F.data.startswith("net_"))
async def process_deposit_network_selection(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    network = callback_query.data.split("_")[1]
    await state.update_data(network=network)
    
    data = await state.get_data()
    asset = data.get('asset')
    method = data.get('method')
    
    if method == 'np':
        currency = network.lower()
        headers = {"x-api-key": NOWPAYMENTS_API_KEY}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://api.nowpayments.io/v1/min-amount?currency_from={currency}&currency_to={currency}', headers=headers) as resp:
                    resp_data = await resp.json()
                    min_amount = resp_data.get('min_amount')
            if min_amount:
                await callback_query.message.answer(f"How much {asset} do you want to deposit?\n\n*(Minimum: {min_amount} {asset})*", parse_mode="Markdown")
            else:
                await callback_query.message.answer(f"How much {asset} do you want to deposit?")
        except Exception as e:
            logging.error(f"Error fetching min amount: {e}")
            await callback_query.message.answer(f"How much {asset} do you want to deposit?")
    else:
        await callback_query.message.answer(f"How much {asset} do you want to deposit?")
        
    await state.set_state(DepositState.amount)
    await callback_query.answer()

@dp.message(DepositState.amount)
async def process_deposit_amount(message: types.Message, state: FSMContext) -> None:
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError("Amount must be positive.")
    except ValueError:
        await message.answer("Please enter a valid positive number.")
        return

    data = await state.get_data()
    asset = data['asset']
    method = data['method']
    network = data.get('network')
    
    if method == 'cp':
        try:
            invoice = await crypto.create_invoice(asset=asset, amount=amount)
            
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="Pay", url=invoice.bot_invoice_url)],
                    [types.InlineKeyboardButton(text="✅ Check Payment", callback_data=f"check_cp_{invoice.invoice_id}")]
                ]
            )
            
            await message.answer(
                f"Please pay {amount} {asset} using the link below:",
                reply_markup=keyboard
            )
            await state.clear()
        except Exception as e:
            logging.error(f"Error creating invoice: {e}")
            await message.answer("An error occurred while creating the invoice. Please try again later.")
            await state.clear()
    elif method == 'np':
        try:
            headers = {
                "x-api-key": NOWPAYMENTS_API_KEY,
                "Content-Type": "application/json"
            }
            pay_currency = network if network else asset.lower()
            price_currency = "usdt" if asset == "USDT" else asset.lower()
            
            payload = {
                "price_amount": amount,
                "price_currency": price_currency,
                "pay_currency": pay_currency,
                "order_id": str(message.from_user.id)
            }
            async with aiohttp.ClientSession() as session:
                async with session.post('https://api.nowpayments.io/v1/payment', headers=headers, json=payload) as resp:
                    resp_data = await resp.json()
                    
            if 'payment_id' not in resp_data:
                if resp_data.get('error') == 'AMOUNT_MINIMAL_ERROR':
                    error_msg = resp_data.get('message', '')
                    import re
                    match = re.search(r'Minimal amount is ([\d.]+)', error_msg)
                    min_amount = match.group(1) if match else "the required minimum"
                    await message.answer(f"❌ The amount you entered is too low. The minimum deposit is {min_amount} {asset}. Please try again.")
                    return
                
                logging.error(f"NowPayments API error: {resp_data}")
                await message.answer("An error occurred while creating the payment. Please try again later.")
                await state.clear()
                return

            payment_id = resp_data['payment_id']
            pay_address = resp_data['pay_address']
            pay_amount = resp_data['pay_amount']
            
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="✅ Check Payment", callback_data=f"check_np_{payment_id}")]
                ]
            )
            
            await message.answer(
                f"Please send EXACTLY `{pay_amount}` {asset} to this address:\n\n`{pay_address}`\n\n*(Tap the address to copy it)*",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            await state.clear()
        except Exception as e:
            logging.error(f"Error creating NowPayments invoice: {e}")
            await message.answer("An error occurred while creating the invoice. Please try again later.")
            await state.clear()

@dp.callback_query(F.data.startswith("check_cp_"))
async def check_cp_payment_handler(callback_query: types.CallbackQuery) -> None:
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

@dp.callback_query(F.data.startswith("check_np_"))
async def check_np_payment_handler(callback_query: types.CallbackQuery) -> None:
    payment_id = callback_query.data.split("_")[2]
    user_id = callback_query.from_user.id
    
    try:
        headers = {
            "x-api-key": NOWPAYMENTS_API_KEY
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.nowpayments.io/v1/payment/{payment_id}', headers=headers) as resp:
                resp_data = await resp.json()
                
        if 'payment_status' not in resp_data:
            await callback_query.answer("Payment not found.", show_alert=True)
            return
            
        status = resp_data['payment_status']
        
        if status in ['finished', 'confirmed']:
            asset = resp_data['pay_currency'].upper()
            amount = float(resp_data['pay_amount'])
            
            async with async_session() as session:
                stmt = select(User).where(User.telegram_id == user_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if user:
                    stmt = select(Balance).where(Balance.user_id == user.id, Balance.asset == asset)
                    result = await session.execute(stmt)
                    balance = result.scalar_one_or_none()
                    
                    if balance:
                        balance.amount += amount
                    else:
                        new_balance = Balance(user_id=user.id, asset=asset, amount=amount)
                        session.add(new_balance)
                        
                    await session.commit()
                    await callback_query.message.edit_text(f"✅ Payment of {amount} {asset} received! Your balance has been updated.")
                else:
                    await callback_query.answer("User not found in database.", show_alert=True)
        else:
            await callback_query.answer(f"Payment is still pending. Status: {status}", show_alert=True)
    except Exception as e:
        logging.error(f"Error checking NowPayments payment: {e}")
        await callback_query.answer("An error occurred while checking the payment.", show_alert=True)

@dp.message(F.text == "📤 Withdraw")
async def withdraw_handler(message: types.Message, state: FSMContext) -> None:
    """
    This handler receives messages with "📤 Withdraw" text
    """
    await message.answer(
        "Select an asset to withdraw:",
        reply_markup=get_withdraw_asset_keyboard()
    )
    await state.set_state(WithdrawState.asset)

@dp.callback_query(WithdrawState.asset, F.data.startswith("with_asset_"))
async def process_withdraw_asset_selection(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    asset = callback_query.data.split("_")[2].upper()
    await state.update_data(asset=asset)
    
    await callback_query.message.answer(f"Please enter your {asset} wallet address:")
    await state.set_state(WithdrawState.address)
    await callback_query.answer()

@dp.message(WithdrawState.address)
async def process_withdraw_address(message: types.Message, state: FSMContext) -> None:
    address = message.text
    await state.update_data(address=address)
    
    data = await state.get_data()
    asset = data['asset']
    
    await message.answer(f"How much {asset} do you want to withdraw?")
    await state.set_state(WithdrawState.amount)

@dp.message(WithdrawState.amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext) -> None:
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError("Amount must be positive.")
    except ValueError:
        await message.answer("Please enter a valid positive number.")
        return

    data = await state.get_data()
    asset = data['asset']
    address = data['address']
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

        # Check balance
        stmt = select(Balance).where(Balance.user_id == user.id, Balance.asset == asset)
        result = await session.execute(stmt)
        balance = result.scalar_one_or_none()

        if not balance or balance.amount < amount:
            await message.answer(f"Insufficient {asset} balance.")
            await state.clear()
            return

        # Deduct balance
        try:
            balance.amount -= amount
            await session.commit()
            
            await message.answer(
                f"✅ Withdrawal request submitted!\n\n"
                f"Amount: {amount} {asset}\n"
                f"Address: {address}\n\n"
                f"*Note: Withdrawals are processed manually by admins.*",
                parse_mode="Markdown"
            )
        except Exception as e:
            await session.rollback()
            logging.error(f"Database error during withdrawal: {e}")
            await message.answer("An error occurred during the withdrawal. Please try again.")
        finally:
            await state.clear()

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