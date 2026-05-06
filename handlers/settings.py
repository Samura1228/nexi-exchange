import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from database import async_session, User
from keyboards.builders import get_settings_keyboard, get_language_keyboard
from locales.texts import get_text

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "settings")
async def settings_menu(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Show settings menu."""
    user_id = callback_query.from_user.id

    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        lang = user.language if user else "en"

    lang_display = "🇬🇧 English" if lang == "en" else "🇷🇺 Русский"

    await callback_query.message.edit_text(
        get_text("settings_title", lang, user_id=user_id, language=lang_display),
        reply_markup=get_settings_keyboard(lang=lang),
        parse_mode="Markdown"
    )
    await callback_query.answer()


@router.callback_query(F.data == "settings_my_id")
async def settings_my_id(callback_query: types.CallbackQuery) -> None:
    """Show user's Telegram ID."""
    await callback_query.answer(
        f"Your Telegram ID: {callback_query.from_user.id}",
        show_alert=True
    )


@router.callback_query(F.data == "settings_language")
async def settings_language(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Show language selection from settings."""
    user_id = callback_query.from_user.id

    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        lang = user.language if user else "en"

    # Mark that we're coming from settings
    await state.update_data(from_settings=True)

    await callback_query.message.edit_text(
        get_text("choose_language", lang),
        reply_markup=get_language_keyboard(),
        parse_mode="Markdown"
    )
    await callback_query.answer()