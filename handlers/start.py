import asyncio
import logging
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from database import async_session, User
from keyboards.builders import get_start_keyboard
from sheets import log_action

logger = logging.getLogger(__name__)
router = Router()

@router.message(CommandStart())
async def command_start(message: types.Message, state: FSMContext) -> None:
    """Handle /start command. Register user if new, show main menu."""
    await state.clear()  # Clear any active FSM state
    
    user_id = message.from_user.id
    username = message.from_user.username

    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            new_user = User(telegram_id=user_id, username=username)
            session.add(new_user)
            await session.commit()
            logger.info(f"New user registered: {user_id} (@{username})")

    await asyncio.to_thread(log_action, user_id, username, "Start Bot", "User started the bot")

    await message.answer(
        "🟢 **Welcome to Nexi Exchange!**\n\n"
        "Swap cryptocurrencies instantly — non-custodial, fast, and secure.\n\n"
        "Choose an option below:",
        reply_markup=get_start_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Handle back to start menu."""
    await state.clear()
    await callback_query.message.edit_text(
        "🟢 **Welcome to Nexi Exchange!**\n\n"
        "Swap cryptocurrencies instantly — non-custodial, fast, and secure.\n\n"
        "Choose an option below:",
        reply_markup=get_start_keyboard(),
        parse_mode="Markdown"
    )
    await callback_query.answer()