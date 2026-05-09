"""
Promo codes handler — allows beta test users to enter and manage promo codes.

Promo codes give users discounted exchange fees for a limited number of exchanges.

HOW TO CREATE PROMO CODES:
  Promo codes are stored in the "promo_codes" table. Create them via Supabase dashboard:
  
  INSERT INTO promo_codes (code, discount_percent, max_uses, uses_per_user, is_active)
  VALUES ('WELCOME', 50, 1000, 3, true);
  
  Fields:
    - code: The promo code string (e.g., "WELCOME", "FIRST50")
    - discount_percent: Percentage off the exchange markup (e.g., 50 = 50% off fees)
    - max_uses: Total number of times this code can be used across all users
    - uses_per_user: How many exchanges each user gets with this code
    - is_active: Whether the code is currently active
    - expires_at: Optional expiry timestamp (NULL = no expiry)
"""

import logging
from datetime import datetime, timezone

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

from config import BETA_TEST_USER_IDS
from database import async_session, User, PromoCode, UserPromo
from utils.states import PromoState
from keyboards.builders import (
    get_promo_menu_keyboard,
    get_promo_cancel_keyboard,
    get_promo_back_keyboard,
    get_start_keyboard,
)
from locales.texts import get_text

logger = logging.getLogger(__name__)
router = Router()


async def _get_user_lang(user_id: int) -> str:
    """Helper to get user language from DB."""
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        return user.language if user else "en"


@router.callback_query(F.data == "promo_menu")
async def promo_menu(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Show promo codes menu — only for beta test users."""
    user_id = callback_query.from_user.id
    if user_id not in BETA_TEST_USER_IDS:
        await callback_query.answer("Feature not available.", show_alert=True)
        return

    await state.clear()
    lang = await _get_user_lang(user_id)

    await callback_query.message.edit_text(
        get_text("promo_menu", lang),
        reply_markup=get_promo_menu_keyboard(lang=lang),
        parse_mode="Markdown"
    )
    await callback_query.answer()


@router.callback_query(F.data == "promo_enter")
async def promo_enter(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Ask user to enter a promo code."""
    user_id = callback_query.from_user.id
    if user_id not in BETA_TEST_USER_IDS:
        await callback_query.answer("Feature not available.", show_alert=True)
        return

    lang = await _get_user_lang(user_id)
    await state.update_data(lang=lang)
    await state.set_state(PromoState.enter_code)

    await callback_query.message.edit_text(
        get_text("promo_enter", lang),
        reply_markup=get_promo_cancel_keyboard(lang=lang),
        parse_mode="Markdown"
    )
    await callback_query.answer()


@router.message(PromoState.enter_code)
async def process_promo_code(message: types.Message, state: FSMContext) -> None:
    """Validate and activate the promo code."""
    data = await state.get_data()
    lang = data.get("lang", "en")
    user_id = message.from_user.id
    code_input = message.text.strip().upper()

    async with async_session() as session:
        # Find the promo code
        stmt = select(PromoCode).where(
            and_(
                PromoCode.code == code_input,
                PromoCode.is_active == True,
            )
        )
        result = await session.execute(stmt)
        promo = result.scalar_one_or_none()

        if not promo:
            await message.answer(
                get_text("promo_invalid", lang),
                reply_markup=get_promo_back_keyboard(lang=lang),
                parse_mode="Markdown"
            )
            await state.clear()
            return

        # Check expiry
        if promo.expires_at and promo.expires_at < datetime.now(timezone.utc):
            await message.answer(
                get_text("promo_invalid", lang),
                reply_markup=get_promo_back_keyboard(lang=lang),
                parse_mode="Markdown"
            )
            await state.clear()
            return

        # Check max total uses
        if promo.current_uses >= promo.max_uses:
            await message.answer(
                get_text("promo_max_reached", lang),
                reply_markup=get_promo_back_keyboard(lang=lang),
                parse_mode="Markdown"
            )
            await state.clear()
            return

        # Check if user already has this promo (active or not)
        user_promo_stmt = select(UserPromo).where(
            and_(
                UserPromo.telegram_id == user_id,
                UserPromo.promo_code_id == promo.id,
            )
        )
        user_promo_result = await session.execute(user_promo_stmt)
        existing = user_promo_result.scalar_one_or_none()

        if existing:
            await message.answer(
                get_text("promo_already_used", lang),
                reply_markup=get_promo_back_keyboard(lang=lang),
                parse_mode="Markdown"
            )
            await state.clear()
            return

        # Activate the promo for this user
        user_promo = UserPromo(
            telegram_id=user_id,
            promo_code_id=promo.id,
            uses_remaining=promo.uses_per_user,
            discount_percent=promo.discount_percent,
        )
        session.add(user_promo)

        # Increment total uses
        promo.current_uses += 1
        await session.commit()

        logger.info(f"[promo] User {user_id} activated promo '{code_input}': {promo.discount_percent}% off for {promo.uses_per_user} exchanges")

    await message.answer(
        get_text("promo_activated", lang, discount=promo.discount_percent, uses=promo.uses_per_user),
        reply_markup=get_promo_back_keyboard(lang=lang),
        parse_mode="Markdown"
    )
    await state.clear()


@router.callback_query(F.data == "promo_my")
async def promo_my(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Show user's active promo codes."""
    user_id = callback_query.from_user.id
    if user_id not in BETA_TEST_USER_IDS:
        await callback_query.answer("Feature not available.", show_alert=True)
        return

    lang = await _get_user_lang(user_id)

    async with async_session() as session:
        stmt = select(UserPromo, PromoCode).join(
            PromoCode, UserPromo.promo_code_id == PromoCode.id
        ).where(
            and_(
                UserPromo.telegram_id == user_id,
                UserPromo.uses_remaining > 0,
            )
        )
        result = await session.execute(stmt)
        rows = result.all()

    if not rows:
        await callback_query.message.edit_text(
            get_text("promo_none", lang),
            reply_markup=get_promo_back_keyboard(lang=lang),
            parse_mode="Markdown"
        )
        await callback_query.answer()
        return

    text = get_text("promo_list_title", lang)
    for user_promo, promo_code in rows:
        text += get_text("promo_active", lang,
                         code=promo_code.code,
                         discount=user_promo.discount_percent,
                         remaining=user_promo.uses_remaining) + "\n\n"

    await callback_query.message.edit_text(
        text,
        reply_markup=get_promo_back_keyboard(lang=lang),
        parse_mode="Markdown"
    )
    await callback_query.answer()