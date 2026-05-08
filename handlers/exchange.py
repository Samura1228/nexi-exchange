import logging
from decimal import Decimal
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from config import SUPPORTED_CURRENCIES, MARKUP_PERCENT, REFERRAL_PERCENT, EXCHANGE_TIMEOUT_MINUTES, CHANGENOW_API_KEY
from database import async_session, User, Transaction
from services.swapzone import swapzone
from services.changenow import changenow
from services.supabase_client import supabase
from utils import format_amount
from utils.states import ExchangeState
from keyboards.builders import (
    get_currency_keyboard,
    get_confirm_keyboard,
    get_cancel_keyboard,
    get_start_keyboard,
)
from locales.texts import get_text

logger = logging.getLogger(__name__)
router = Router()


def find_display_name(ticker: str, network: str) -> str:
    """Find display name for a currency from SUPPORTED_CURRENCIES."""
    for display, t, n in SUPPORTED_CURRENCIES:
        if t == ticker and n == network:
            return display
    return f"{ticker.upper()}"


async def _get_user_lang(user_id: int) -> str:
    """Helper to get user language from DB."""
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        return user.language if user else "en"


@router.callback_query(F.data == "start_exchange")
async def start_exchange(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Start the exchange flow — show FROM currency selection."""
    await state.clear()
    user_id = callback_query.from_user.id
    lang = await _get_user_lang(user_id)

    await state.update_data(lang=lang)
    await state.set_state(ExchangeState.select_from)
    logger.info(f"[exchange] User {user_id}: state set to ExchangeState.select_from")
    await callback_query.message.edit_text(
        get_text("select_from", lang),
        reply_markup=get_currency_keyboard("from", lang=lang),
        parse_mode="Markdown"
    )
    await callback_query.answer()


@router.callback_query(ExchangeState.select_from, F.data.startswith("sel:from:"))
async def process_from_selection(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Process FROM currency selection, show TO currency keyboard."""
    logger.info(f"[exchange] User {callback_query.from_user.id}: process_from_selection triggered, data={callback_query.data}")
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
    
    data = await state.get_data()
    lang = data.get("lang", "en")
    
    exclude_key = f"{ticker}:{network}"
    await callback_query.message.edit_text(
        get_text("select_to", lang, from_display=display),
        reply_markup=get_currency_keyboard("to", exclude=exclude_key, lang=lang),
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
    lang = data.get("lang", "en")
    from_display = data['from_display']
    from_ticker = data['from_ticker']
    from_network = data['from_network']
    
    # Fetch minimum amount — try Swapzone first, fall back to ChangeNow
    await callback_query.message.edit_text(
        get_text("fetching_details", lang, from_display=from_display, to_display=display),
        parse_mode="Markdown"
    )
    
    provider = "swapzone"  # Track which provider we'll use
    min_data = await swapzone.get_min_amount(from_ticker, from_network, ticker, network)
    
    # If Swapzone fails, try ChangeNow as fallback
    if "error" in min_data and CHANGENOW_API_KEY:
        logger.info(f"Swapzone get_min_amount failed, trying ChangeNow fallback")
        min_data = await changenow.get_min_amount(from_ticker, from_network, ticker, network)
        if "error" not in min_data:
            provider = "changenow"
    
    if "error" in min_data:
        await callback_query.message.edit_text(
            get_text("pair_unavailable", lang, error=min_data['error']),
            reply_markup=get_start_keyboard(user_id=callback_query.from_user.id, lang=lang),
            parse_mode="Markdown"
        )
        await state.clear()
        await callback_query.answer()
        return
    
    min_amount = min_data.get("minAmount", 0)
    await state.update_data(min_amount=min_amount, provider=provider)
    
    await callback_query.message.edit_text(
        get_text("enter_amount", lang, from_display=from_display, to_display=display, min_amount=format_amount(min_amount)),
        reply_markup=get_cancel_keyboard(lang=lang),
        parse_mode="Markdown"
    )
    await state.set_state(ExchangeState.enter_amount)
    await callback_query.answer()


@router.message(ExchangeState.enter_amount)
async def process_amount(message: types.Message, state: FSMContext) -> None:
    """Process amount input, fetch estimated amount, ask for address."""
    data = await state.get_data()
    lang = data.get("lang", "en")

    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except (ValueError, TypeError):
        await message.answer(
            get_text("invalid_amount", lang),
            reply_markup=get_cancel_keyboard(lang=lang)
        )
        return
    
    min_amount = data.get('min_amount', 0)
    
    if amount < min_amount:
        await message.answer(
            get_text("amount_below_min", lang, min_amount=format_amount(min_amount), from_display=data['from_display']),
            reply_markup=get_cancel_keyboard(lang=lang)
        )
        return
    
    from_ticker = data['from_ticker']
    from_network = data['from_network']
    to_ticker = data['to_ticker']
    to_network = data['to_network']
    from_display = data['from_display']
    to_display = data['to_display']
    
    # Fetch estimated amount — use stored provider or try Swapzone with ChangeNow fallback
    loading_msg = await message.answer(
        get_text("getting_rate", lang, amount=amount, from_display=from_display, to_display=to_display)
    )
    
    provider = data.get("provider", "swapzone")
    
    if provider == "changenow":
        estimate = await changenow.get_estimated_amount(from_ticker, from_network, to_ticker, to_network, amount)
        logger.info(f"ChangeNow estimate response: {estimate}")
    else:
        estimate = await swapzone.get_estimated_amount(from_ticker, from_network, to_ticker, to_network, amount)
        logger.info(f"Swapzone estimate response: {estimate}")
        
        # If Swapzone fails, try ChangeNow as fallback
        if "error" in estimate and CHANGENOW_API_KEY:
            logger.info("Swapzone estimate failed, trying ChangeNow fallback")
            estimate = await changenow.get_estimated_amount(from_ticker, from_network, to_ticker, to_network, amount)
            if "error" not in estimate:
                provider = "changenow"
                await state.update_data(provider=provider)
    
    if "error" in estimate:
        await loading_msg.edit_text(
            get_text("rate_error", lang, error=estimate['error']),
            reply_markup=get_start_keyboard(user_id=message.from_user.id, lang=lang)
        )
        await state.clear()
        return
    
    estimated_amount = float(estimate.get("estimatedAmount") or 0)
    quota_id = estimate.get("quotaId", "")
    
    if estimated_amount <= 0:
        await loading_msg.edit_text(
            get_text("estimate_too_small", lang),
            reply_markup=get_start_keyboard(user_id=message.from_user.id, lang=lang)
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
        quota_id=quota_id,
    )
    
    await loading_msg.edit_text(
        get_text("exchange_quote", lang,
                 amount=format_amount(amount), from_display=from_display,
                 displayed_estimate=format_amount(displayed_estimate), to_display=to_display),
        reply_markup=get_cancel_keyboard(lang=lang),
        parse_mode="Markdown"
    )
    await state.set_state(ExchangeState.enter_address)


@router.message(ExchangeState.enter_address)
async def process_address(message: types.Message, state: FSMContext) -> None:
    """Process destination address, show confirmation."""
    address = message.text.strip()
    data = await state.get_data()
    lang = data.get("lang", "en")
    
    if len(address) < 10:
        await message.answer(
            get_text("invalid_address", lang),
            reply_markup=get_cancel_keyboard(lang=lang)
        )
        return
    
    await state.update_data(address=address)
    data = await state.get_data()
    
    from_display = data['from_display']
    to_display = data['to_display']
    amount = data['amount']
    displayed_estimate = data['displayed_estimate']
    
    await message.answer(
        get_text("confirm_exchange", lang,
                 amount=format_amount(amount), from_display=from_display,
                 displayed_estimate=format_amount(displayed_estimate), to_display=to_display,
                 address=address),
        reply_markup=get_confirm_keyboard(lang=lang),
        parse_mode="Markdown"
    )
    await state.set_state(ExchangeState.confirm)


@router.callback_query(ExchangeState.confirm, F.data == "confirm_exchange")
async def confirm_exchange(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Confirm and create the exchange via Swapzone or ChangeNow (fallback)."""
    data = await state.get_data()
    lang = data.get("lang", "en")
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
    quota_id = data.get('quota_id', '')
    provider = data.get('provider', 'swapzone')
    
    await callback_query.message.edit_text(get_text("creating_exchange", lang))
    
    # Create exchange via the selected provider
    if provider == "changenow":
        result = await changenow.create_exchange(
            from_currency=from_ticker,
            from_network=from_network,
            to_currency=to_ticker,
            to_network=to_network,
            amount=amount,
            address=address,
        )
    else:
        result = await swapzone.create_exchange(
            from_currency=from_ticker,
            from_network=from_network,
            to_currency=to_ticker,
            to_network=to_network,
            amount=amount,
            address=address,
            quota_id=quota_id,
        )
        # If Swapzone fails, try ChangeNow as last resort
        if "error" in result and CHANGENOW_API_KEY:
            logger.info(f"Swapzone create_exchange failed, trying ChangeNow fallback")
            result = await changenow.create_exchange(
                from_currency=from_ticker,
                from_network=from_network,
                to_currency=to_ticker,
                to_network=to_network,
                amount=amount,
                address=address,
            )
            if "error" not in result:
                provider = "changenow"
    
    if "error" in result:
        await callback_query.message.edit_text(
            get_text("exchange_create_error", lang, error=result['error']),
            reply_markup=get_start_keyboard(user_id=callback_query.from_user.id, lang=lang)
        )
        await state.clear()
        await callback_query.answer()
        return
    
    changenow_id = result.get("id")
    deposit_address = result.get("payinAddress", "")
    payin_extra_id = result.get("payinExtraId", "")
    
    if not changenow_id or not deposit_address:
        await callback_query.message.edit_text(
            get_text("exchange_unexpected_error", lang),
            reply_markup=get_start_keyboard(user_id=callback_query.from_user.id, lang=lang)
        )
        await state.clear()
        await callback_query.answer()
        return
    
    # Build the deposit message with initial timer
    extra_id_text = get_text("exchange_memo", lang, memo=payin_extra_id) if payin_extra_id else ""
    initial_timer = f"{EXCHANGE_TIMEOUT_MINUTES}:00"
    
    deposit_msg = await callback_query.message.edit_text(
        get_text("exchange_created", lang,
                 amount=format_amount(amount), from_display=from_display,
                 deposit_address=deposit_address, extra_id_text=extra_id_text,
                 displayed_estimate=format_amount(displayed_estimate), to_display=to_display,
                 address=address, changenow_id=changenow_id, timer=initial_timer),
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
            provider=provider,
            message_id=deposit_msg.message_id,
            chat_id=callback_query.message.chat.id,
        )
        session.add(transaction)
        await session.commit()
    
    # ── Referral commission ──────────────────────────────────────────
    # Credit the referrer with a percentage of the bot's markup
    logger.info(f"[referral] Checking referral commission for user {user_id}")
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result_user = await session.execute(stmt)
        exchange_user = result_user.scalar_one_or_none()

        if exchange_user and exchange_user.referred_by:
            logger.info(f"[referral] User {user_id} was referred by {exchange_user.referred_by}, calculating commission")
            # Commission = amount * (MARKUP_PERCENT/100) * (REFERRAL_PERCENT/100)
            referrer_commission = Decimal(str(amount)) * (Decimal(str(MARKUP_PERCENT)) / Decimal("100")) * (Decimal(str(REFERRAL_PERCENT)) / Decimal("100"))

            referrer_stmt = select(User).where(User.telegram_id == exchange_user.referred_by)
            referrer_result = await session.execute(referrer_stmt)
            referrer = referrer_result.scalar_one_or_none()

            if referrer:
                referrer.referral_earnings = (referrer.referral_earnings or Decimal("0")) + referrer_commission
                await session.commit()
                logger.info(f"[referral] Commission {referrer_commission} credited to referrer {referrer.telegram_id}, total={referrer.referral_earnings}")

                # Notify referrer about the commission
                referrer_lang = referrer.language or "en"
                try:
                    await bot.send_message(
                        referrer.telegram_id,
                        get_text("referral_earned", referrer_lang,
                                 amount=format_amount(referrer_commission), currency=from_display,
                                 total=format_amount(referrer.referral_earnings)),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.warning(f"[referral] Could not notify referrer {referrer.telegram_id}: {e}")
            else:
                logger.warning(f"[referral] Referrer {exchange_user.referred_by} not found in database")
        else:
            logger.info(f"[referral] User {user_id} has no referrer (referred_by={getattr(exchange_user, 'referred_by', 'N/A')})")

    await supabase.log_exchange(user_id, from_display, to_display, float(amount), float(displayed_estimate), "created", changenow_id)
    await supabase.log_event("exchange_created", user_id, username, f"{format_amount(amount)} {from_display} → ~{format_amount(displayed_estimate)} {to_display} | ID: {changenow_id}")
    
    await state.clear()
    await callback_query.answer()


@router.callback_query(F.data == "cancel_exchange")
async def cancel_exchange(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Cancel the exchange at any point."""
    data = await state.get_data()
    lang = data.get("lang", None)

    # If lang not in state, fetch from DB
    if not lang:
        lang = await _get_user_lang(callback_query.from_user.id)

    await state.clear()
    await callback_query.message.edit_text(
        get_text("exchange_cancelled", lang),
        reply_markup=get_start_keyboard(user_id=callback_query.from_user.id, lang=lang),
        parse_mode="Markdown"
    )
    await callback_query.answer()