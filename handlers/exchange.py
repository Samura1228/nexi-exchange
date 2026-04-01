import asyncio
import logging
from decimal import Decimal
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from config import SUPPORTED_CURRENCIES, MARKUP_PERCENT
from database import async_session, User, Transaction
from services.changenow import changenow
from utils.states import ExchangeState
from keyboards.builders import (
    get_currency_keyboard,
    get_confirm_keyboard,
    get_cancel_keyboard,
    get_start_keyboard,
)
from sheets import log_action

logger = logging.getLogger(__name__)
router = Router()


def find_display_name(ticker: str, network: str) -> str:
    """Find display name for a currency from SUPPORTED_CURRENCIES."""
    for display, t, n in SUPPORTED_CURRENCIES:
        if t == ticker and n == network:
            return display
    return f"{ticker.upper()}"


@router.callback_query(F.data == "start_exchange")
async def start_exchange(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Start the exchange flow — show FROM currency selection."""
    await state.clear()
    await callback_query.message.edit_text(
        "💱 **Select the currency you want to send (FROM):**",
        reply_markup=get_currency_keyboard("from"),
        parse_mode="Markdown"
    )
    await state.set_state(ExchangeState.select_from)
    await callback_query.answer()


@router.callback_query(ExchangeState.select_from, F.data.startswith("sel:from:"))
async def process_from_selection(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Process FROM currency selection, show TO currency keyboard."""
    # Parse callback: "sel:from:{ticker}:{network}"
    parts = callback_query.data.split(":")
    ticker = parts[2]
    network = parts[3]
    display = find_display_name(ticker, network)
    
    await state.update_data(
        from_ticker=ticker,
        from_network=network,
        from_display=display,
    )
    
    exclude_key = f"{ticker}:{network}"
    await callback_query.message.edit_text(
        f"💱 **Sending:** {display}\n\n"
        f"**Select the currency you want to receive (TO):**",
        reply_markup=get_currency_keyboard("to", exclude=exclude_key),
        parse_mode="Markdown"
    )
    await state.set_state(ExchangeState.select_to)
    await callback_query.answer()


@router.callback_query(ExchangeState.select_to, F.data.startswith("sel:to:"))
async def process_to_selection(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Process TO currency selection, fetch min amount, ask for amount."""
    parts = callback_query.data.split(":")
    ticker = parts[2]
    network = parts[3]
    display = find_display_name(ticker, network)
    
    await state.update_data(
        to_ticker=ticker,
        to_network=network,
        to_display=display,
    )
    
    data = await state.get_data()
    from_display = data['from_display']
    from_ticker = data['from_ticker']
    from_network = data['from_network']
    
    # Fetch minimum amount from ChangeNow
    await callback_query.message.edit_text(
        f"⏳ Fetching exchange details for {from_display} → {display}...",
        parse_mode="Markdown"
    )
    
    min_data = await changenow.get_min_amount(from_ticker, from_network, ticker, network)
    
    if "error" in min_data:
        await callback_query.message.edit_text(
            f"❌ This exchange pair is currently unavailable.\n\nError: {min_data['error']}\n\nPlease try a different pair.",
            reply_markup=get_start_keyboard(),
            parse_mode="Markdown"
        )
        await state.clear()
        await callback_query.answer()
        return
    
    min_amount = min_data.get("minAmount", 0)
    await state.update_data(min_amount=min_amount)
    
    await callback_query.message.edit_text(
        f"💱 **{from_display} → {display}**\n\n"
        f"Enter the amount of **{from_display}** you want to exchange:\n\n"
        f"_(Minimum: {min_amount} {from_display})_",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(ExchangeState.enter_amount)
    await callback_query.answer()


@router.message(ExchangeState.enter_amount)
async def process_amount(message: types.Message, state: FSMContext) -> None:
    """Process amount input, fetch estimated amount, ask for address."""
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except (ValueError, TypeError):
        await message.answer(
            "❌ Please enter a valid positive number.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    data = await state.get_data()
    min_amount = data.get('min_amount', 0)
    
    if amount < min_amount:
        await message.answer(
            f"❌ Amount is below the minimum of {min_amount} {data['from_display']}.\n"
            f"Please enter a larger amount.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    from_ticker = data['from_ticker']
    from_network = data['from_network']
    to_ticker = data['to_ticker']
    to_network = data['to_network']
    from_display = data['from_display']
    to_display = data['to_display']
    
    # Fetch estimated amount
    loading_msg = await message.answer(f"⏳ Getting exchange rate for {amount} {from_display} → {to_display}...")
    
    estimate = await changenow.get_estimated_amount(from_ticker, from_network, to_ticker, to_network, amount)
    
    if "error" in estimate:
        await loading_msg.edit_text(
            f"❌ Could not get exchange rate.\n\nError: {estimate['error']}\n\nPlease try again.",
            reply_markup=get_start_keyboard()
        )
        await state.clear()
        return
    
    estimated_amount = float(estimate.get("estimatedAmount", 0))
    
    if estimated_amount <= 0:
        await loading_msg.edit_text(
            "❌ The estimated amount is too small. Please try a larger amount.",
            reply_markup=get_start_keyboard()
        )
        await state.clear()
        return
    
    # Apply markup (reduce estimated amount by MARKUP_PERCENT so bot owner earns the difference)
    markup_factor = 1 - (MARKUP_PERCENT / 100)
    displayed_estimate = estimated_amount * markup_factor
    
    await state.update_data(
        amount=amount,
        estimated_amount=estimated_amount,
        displayed_estimate=displayed_estimate,
    )
    
    await loading_msg.edit_text(
        f"💱 **Exchange Quote:**\n\n"
        f"📤 **You send:** {amount} {from_display}\n"
        f"📥 **You get:** ~{displayed_estimate:.8g} {to_display}\n\n"
        f"Now enter your **{to_display}** destination wallet address:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(ExchangeState.enter_address)


@router.message(ExchangeState.enter_address)
async def process_address(message: types.Message, state: FSMContext) -> None:
    """Process destination address, show confirmation."""
    address = message.text.strip()
    
    if len(address) < 10:
        await message.answer(
            "❌ That doesn't look like a valid wallet address. Please try again.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await state.update_data(address=address)
    data = await state.get_data()
    
    from_display = data['from_display']
    to_display = data['to_display']
    amount = data['amount']
    displayed_estimate = data['displayed_estimate']
    
    await message.answer(
        f"📋 **Exchange Confirmation:**\n\n"
        f"📤 **Send:** {amount} {from_display}\n"
        f"📥 **Receive:** ~{displayed_estimate:.8g} {to_display}\n"
        f"📬 **To address:** `{address}`\n\n"
        f"⚠️ Please verify the address carefully. Transactions cannot be reversed.\n\n"
        f"Press **Confirm** to proceed or **Cancel** to abort.",
        reply_markup=get_confirm_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(ExchangeState.confirm)


@router.callback_query(ExchangeState.confirm, F.data == "confirm_exchange")
async def confirm_exchange(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Confirm and create the exchange via ChangeNow API."""
    data = await state.get_data()
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username
    
    from_ticker = data['from_ticker']
    from_network = data['from_network']
    to_ticker = data['to_ticker']
    to_network = data['to_network']
    from_display = data['from_display']
    to_display = data['to_display']
    amount = data['amount']
    displayed_estimate = data['displayed_estimate']
    estimated_amount = data['estimated_amount']
    address = data['address']
    
    await callback_query.message.edit_text("⏳ Creating your exchange...")
    
    # Create exchange via ChangeNow
    result = await changenow.create_exchange(
        from_currency=from_ticker,
        from_network=from_network,
        to_currency=to_ticker,
        to_network=to_network,
        amount=amount,
        address=address,
    )
    
    if "error" in result:
        await callback_query.message.edit_text(
            f"❌ Failed to create exchange.\n\nError: {result['error']}\n\nPlease try again.",
            reply_markup=get_start_keyboard()
        )
        await state.clear()
        await callback_query.answer()
        return
    
    changenow_id = result.get("id")
    deposit_address = result.get("payinAddress", "")
    payin_extra_id = result.get("payinExtraId", "")
    
    if not changenow_id or not deposit_address:
        await callback_query.message.edit_text(
            "❌ Unexpected response from exchange service. Please try again.",
            reply_markup=get_start_keyboard()
        )
        await state.clear()
        await callback_query.answer()
        return
    
    # Build the deposit message
    extra_id_text = f"\n🏷️ **Memo/Tag:** `{payin_extra_id}`" if payin_extra_id else ""
    
    deposit_msg = await callback_query.message.edit_text(
        f"✅ **Exchange Created!**\n\n"
        f"📤 **Send exactly** `{amount}` **{from_display}** to:\n\n"
        f"📬 `{deposit_address}`{extra_id_text}\n\n"
        f"📥 **You will receive:** ~{displayed_estimate:.8g} {to_display}\n"
        f"📬 **To:** `{address}`\n\n"
        f"🔄 **Status:** ⏳ Waiting for deposit\n"
        f"🆔 **Exchange ID:** `{changenow_id}`\n\n"
        f"_The status will update automatically._",
        parse_mode="Markdown"
    )
    
    # Save transaction to database
    async with async_session() as session:
        # Get or create user
        stmt = select(User).where(User.telegram_id == user_id)
        result_db = await session.execute(stmt)
        user = result_db.scalar_one_or_none()
        
        if not user:
            user = User(telegram_id=user_id, username=username)
            session.add(user)
            await session.flush()
        
        transaction = Transaction(
            user_id=user.id,
            changenow_id=changenow_id,
            from_currency=from_ticker,
            from_network=from_network,
            to_currency=to_ticker,
            to_network=to_network,
            amount_from=Decimal(str(amount)),
            amount_expected=Decimal(str(estimated_amount)),
            destination_address=address,
            deposit_address=deposit_address,
            status="waiting",
            message_id=deposit_msg.message_id,
            chat_id=callback_query.message.chat.id,
        )
        session.add(transaction)
        await session.commit()
    
    await asyncio.to_thread(log_action, user_id, username, "Exchange Created",
                            f"{amount} {from_display} → ~{displayed_estimate:.8g} {to_display} | ID: {changenow_id}")
    
    await state.clear()
    await callback_query.answer()


@router.callback_query(F.data == "cancel_exchange")
async def cancel_exchange(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Cancel the exchange at any point."""
    await state.clear()
    await callback_query.message.edit_text(
        "❌ Exchange cancelled.\n\n"
        "🟢 **Welcome to Nexi Exchange!**\n\n"
        "Choose an option below:",
        reply_markup=get_start_keyboard(),
        parse_mode="Markdown"
    )
    await callback_query.answer()