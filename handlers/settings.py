import logging
from aiogram import Router, types, F

from keyboards.builders import get_settings_keyboard

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "settings")
async def settings_menu(callback_query: types.CallbackQuery) -> None:
    """Show settings menu."""
    await callback_query.message.edit_text(
        "⚙️ **Settings**\n\nChoose an option:",
        reply_markup=get_settings_keyboard(),
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