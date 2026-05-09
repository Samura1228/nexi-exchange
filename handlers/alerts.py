import logging
from decimal import Decimal, InvalidOperation

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func

from config import BETA_TEST_USER_IDS
from database import async_session, User, PriceAlert
from keyboards.builders import (
    get_alerts_menu_keyboard,
    get_alert_currency_keyboard,
    get_alert_direction_keyboard,
    get_alert_cancel_keyboard,
    get_alert_list_keyboard,
)
from locales.texts import get_text
from services.price_service import get_crypto_price_usd
from utils.states import AlertState

logger = logging.getLogger(__name__)
router = Router()

MAX_ALERTS_PER_USER = 10


async def _get_user_lang(user_id: int) -> str:
    """Get user language from DB."""
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        return user.language if user else "en"


async def _get_user_db_id(telegram_id: int) -> int | None:
    """Get internal user ID from telegram_id."""
    async with async_session() as session:
        stmt = select(User.id).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return row


# ── Main alerts menu ──────────────────────────────────────────────────


@router.callback_query(F.data == "price_alerts")
async def alerts_menu(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Show the price alerts main menu."""
    user_id = callback_query.from_user.id
    if user_id not in BETA_TEST_USER_IDS:
        await callback_query.answer("Feature not available.", show_alert=True)
        return

    await state.clear()
    lang = await _get_user_lang(user_id)

    await callback_query.message.edit_text(
        get_text("alerts_menu", lang),
        reply_markup=get_alerts_menu_keyboard(lang),
        parse_mode="Markdown",
    )
    await callback_query.answer()


# ── New alert flow ────────────────────────────────────────────────────


@router.callback_query(F.data == "alert_new")
async def alert_new(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Start new alert: select currency."""
    user_id = callback_query.from_user.id
    if user_id not in BETA_TEST_USER_IDS:
        await callback_query.answer("Feature not available.", show_alert=True)
        return

    lang = await _get_user_lang(user_id)

    # Check alert limit
    db_user_id = await _get_user_db_id(user_id)
    if db_user_id:
        async with async_session() as session:
            count_stmt = select(func.count()).select_from(PriceAlert).where(
                PriceAlert.user_id == db_user_id,
                PriceAlert.is_active == True,
            )
            result = await session.execute(count_stmt)
            count = result.scalar()
            if count >= MAX_ALERTS_PER_USER:
                await callback_query.message.edit_text(
                    get_text("alert_limit_reached", lang),
                    reply_markup=get_alerts_menu_keyboard(lang),
                    parse_mode="Markdown",
                )
                await callback_query.answer()
                return

    await state.set_state(AlertState.select_currency)
    await callback_query.message.edit_text(
        get_text("alert_select_currency", lang),
        reply_markup=get_alert_currency_keyboard(lang),
        parse_mode="Markdown",
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("alert_cur:"), AlertState.select_currency)
async def alert_select_currency(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Currency selected — show direction choice."""
    user_id = callback_query.from_user.id
    if user_id not in BETA_TEST_USER_IDS:
        await callback_query.answer("Feature not available.", show_alert=True)
        return

    lang = await _get_user_lang(user_id)
    currency = callback_query.data.split(":")[1]  # e.g., "btc"

    # Fetch current price
    current_price = await get_crypto_price_usd(currency)
    if current_price is None:
        await callback_query.message.edit_text(
            get_text("alert_error_price_fetch", lang),
            reply_markup=get_alerts_menu_keyboard(lang),
            parse_mode="Markdown",
        )
        await callback_query.answer()
        return

    await state.update_data(currency=currency, current_price=current_price)
    await state.set_state(AlertState.select_direction)

    await callback_query.message.edit_text(
        get_text("alert_select_direction", lang, currency=currency.upper(), current_price=current_price),
        reply_markup=get_alert_direction_keyboard(currency, lang),
        parse_mode="Markdown",
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("alert_dir:"), AlertState.select_direction)
async def alert_select_direction(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Direction selected — ask for target price."""
    user_id = callback_query.from_user.id
    if user_id not in BETA_TEST_USER_IDS:
        await callback_query.answer("Feature not available.", show_alert=True)
        return

    lang = await _get_user_lang(user_id)
    parts = callback_query.data.split(":")  # alert_dir:btc:above
    currency = parts[1]
    direction = parts[2]

    data = await state.get_data()
    current_price = data.get("current_price", 0)

    await state.update_data(direction=direction)
    await state.set_state(AlertState.enter_price)

    direction_label = "above" if direction == "above" else "below"
    if lang == "ru":
        direction_label = "выше" if direction == "above" else "ниже"

    await callback_query.message.edit_text(
        get_text("alert_enter_price", lang, currency=currency.upper(), direction=direction_label, current_price=current_price),
        reply_markup=get_alert_cancel_keyboard(lang),
        parse_mode="Markdown",
    )
    await callback_query.answer()


@router.message(AlertState.enter_price)
async def alert_enter_price(message: types.Message, state: FSMContext) -> None:
    """User entered target price — validate and save alert."""
    user_id = message.from_user.id
    if user_id not in BETA_TEST_USER_IDS:
        return

    lang = await _get_user_lang(user_id)
    data = await state.get_data()
    currency = data.get("currency", "btc")
    direction = data.get("direction", "below")
    current_price = data.get("current_price", 0)

    # Parse price
    try:
        price_text = message.text.strip().replace(",", "").replace("$", "")
        target_price = Decimal(price_text)
        if target_price <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError, AttributeError):
        await message.answer(
            get_text("alert_invalid_price", lang),
            reply_markup=get_alert_cancel_keyboard(lang),
            parse_mode="Markdown",
        )
        return

    # Validate direction makes sense
    target_float = float(target_price)
    if direction == "above" and target_float <= current_price:
        direction_label = "above" if lang != "ru" else "выше"
        await message.answer(
            get_text("alert_price_wrong_direction", lang, direction=direction_label, current_price=current_price),
            reply_markup=get_alert_cancel_keyboard(lang),
            parse_mode="Markdown",
        )
        return
    if direction == "below" and target_float >= current_price:
        direction_label = "below" if lang != "ru" else "ниже"
        await message.answer(
            get_text("alert_price_wrong_direction", lang, direction=direction_label, current_price=current_price),
            reply_markup=get_alert_cancel_keyboard(lang),
            parse_mode="Markdown",
        )
        return

    # Save alert to DB
    db_user_id = await _get_user_db_id(user_id)
    if not db_user_id:
        await message.answer(get_text("error_generic", lang), parse_mode="Markdown")
        await state.clear()
        return

    async with async_session() as session:
        # Double-check limit
        count_stmt = select(func.count()).select_from(PriceAlert).where(
            PriceAlert.user_id == db_user_id,
            PriceAlert.is_active == True,
        )
        result = await session.execute(count_stmt)
        count = result.scalar()
        if count >= MAX_ALERTS_PER_USER:
            await message.answer(
                get_text("alert_limit_reached", lang),
                reply_markup=get_alerts_menu_keyboard(lang),
                parse_mode="Markdown",
            )
            await state.clear()
            return

        alert = PriceAlert(
            user_id=db_user_id,
            telegram_id=user_id,
            currency=currency,
            direction=direction,
            target_price=target_price,
        )
        session.add(alert)
        await session.commit()

    direction_emoji = "📈" if direction == "above" else "📉"
    direction_label = direction if lang != "ru" else ("выше" if direction == "above" else "ниже")

    await message.answer(
        get_text("alert_created", lang,
                 currency=currency.upper(),
                 direction_emoji=direction_emoji,
                 direction=direction_label,
                 target_price=target_float),
        reply_markup=get_alerts_menu_keyboard(lang),
        parse_mode="Markdown",
    )
    await state.clear()


# ── List alerts ───────────────────────────────────────────────────────


@router.callback_query(F.data == "alert_list")
async def alert_list(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Show user's active alerts."""
    user_id = callback_query.from_user.id
    if user_id not in BETA_TEST_USER_IDS:
        await callback_query.answer("Feature not available.", show_alert=True)
        return

    lang = await _get_user_lang(user_id)
    db_user_id = await _get_user_db_id(user_id)

    if not db_user_id:
        await callback_query.message.edit_text(
            get_text("alert_list_empty", lang),
            reply_markup=get_alerts_menu_keyboard(lang),
            parse_mode="Markdown",
        )
        await callback_query.answer()
        return

    async with async_session() as session:
        stmt = select(PriceAlert).where(
            PriceAlert.user_id == db_user_id,
            PriceAlert.is_active == True,
        ).order_by(PriceAlert.created_at)
        result = await session.execute(stmt)
        alerts = result.scalars().all()

    if not alerts:
        await callback_query.message.edit_text(
            get_text("alert_list_empty", lang),
            reply_markup=get_alerts_menu_keyboard(lang),
            parse_mode="Markdown",
        )
        await callback_query.answer()
        return

    # Build list text
    text = get_text("alert_list_title", lang)
    for i, alert in enumerate(alerts, 1):
        direction_emoji = "📈" if alert.direction == "above" else "📉"
        direction_label = alert.direction if lang != "ru" else ("выше" if alert.direction == "above" else "ниже")
        text += get_text("alert_list_item", lang,
                         i=i,
                         currency=alert.currency.upper(),
                         direction_emoji=direction_emoji,
                         direction=direction_label,
                         target_price=float(alert.target_price))

    text += "\n_Tap an alert to delete it:_" if lang != "ru" else "\n_Нажмите на оповещение, чтобы удалить:_"

    await callback_query.message.edit_text(
        text,
        reply_markup=get_alert_list_keyboard(alerts, lang),
        parse_mode="Markdown",
    )
    await callback_query.answer()


# ── Delete alert ──────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("alert_del:"))
async def alert_delete(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Delete an alert."""
    user_id = callback_query.from_user.id
    if user_id not in BETA_TEST_USER_IDS:
        await callback_query.answer("Feature not available.", show_alert=True)
        return

    lang = await _get_user_lang(user_id)
    alert_id = int(callback_query.data.split(":")[1])

    async with async_session() as session:
        stmt = select(PriceAlert).where(
            PriceAlert.id == alert_id,
            PriceAlert.telegram_id == user_id,
        )
        result = await session.execute(stmt)
        alert = result.scalar_one_or_none()
        if alert:
            alert.is_active = False
            await session.commit()

    await callback_query.answer(get_text("alert_deleted", lang), show_alert=True)

    # Refresh the list
    await alert_list(callback_query, state)