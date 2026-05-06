import logging
from decimal import Decimal

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from config import BOT_USERNAME
from database import async_session, User
from keyboards.builders import get_referral_keyboard, get_start_keyboard
from locales.texts import get_text

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "referrals")
async def show_referrals(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Show user's referral stats and link."""
    await state.clear()
    user_id = callback_query.from_user.id

    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

    if not user:
        await callback_query.message.edit_text(
            get_text("referral_user_not_found", "en"),
            reply_markup=get_start_keyboard(user_id=user_id),
        )
        await callback_query.answer()
        return

    lang = user.language or "en"
    referral_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    referral_count = user.referral_count or 0
    referral_earnings = user.referral_earnings or Decimal("0")

    # Format earnings nicely
    earnings_str = f"{referral_earnings:.6f}".rstrip("0").rstrip(".")
    if earnings_str == "" or earnings_str == "0":
        earnings_str = "0"

    await callback_query.message.edit_text(
        get_text("referral_title", lang,
                 referral_link=referral_link,
                 referral_count=referral_count,
                 earnings_str=earnings_str),
        reply_markup=get_referral_keyboard(user_id, lang=lang),
        parse_mode="Markdown",
    )
    await callback_query.answer()