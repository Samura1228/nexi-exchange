import logging
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from config import ADMIN_IDS
from database import async_session, User
from keyboards.builders import get_start_keyboard, get_support_cancel_keyboard
from locales.texts import get_text
from utils.states import SupportState

logger = logging.getLogger(__name__)
router = Router()

# In-memory mapping: {admin_message_id: user_telegram_id}
# Used to track which forwarded message belongs to which user
_support_messages: dict[int, int] = {}


async def _get_user_lang(user_id: int) -> str:
    """Helper to get user language from DB."""
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        return user.language if user else "en"


@router.callback_query(F.data == "support")
async def support_start(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """User clicked '💬 Support' — enter support state."""
    user_id = callback_query.from_user.id
    lang = await _get_user_lang(user_id)

    await state.set_state(SupportState.waiting_message)
    await state.update_data(lang=lang)
    await callback_query.message.edit_text(
        get_text("support_prompt", lang),
        reply_markup=get_support_cancel_keyboard(lang=lang),
        parse_mode="Markdown"
    )
    await callback_query.answer()


@router.callback_query(F.data == "cancel_support")
async def support_cancel(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """User cancelled support — return to main menu."""
    data = await state.get_data()
    lang = data.get("lang", None)
    if not lang:
        lang = await _get_user_lang(callback_query.from_user.id)

    await state.clear()
    await callback_query.message.edit_text(
        get_text("welcome_back", lang),
        reply_markup=get_start_keyboard(user_id=callback_query.from_user.id, lang=lang),
        parse_mode="Markdown"
    )
    await callback_query.answer()


@router.message(SupportState.waiting_message, F.text)
async def support_receive_text(message: types.Message, state: FSMContext, bot: Bot) -> None:
    """User sent a text message to support — forward to all admins."""
    user = message.from_user
    username_str = f"@{user.username}" if user.username else "No username"
    data = await state.get_data()
    lang = data.get("lang", "en")

    # Admin-facing message stays in English
    header = (
        f"📩 **Support message from:**\n"
        f"👤 {username_str} (ID: `{user.id}`)\n\n"
        f"{message.text}\n\n"
        f"_Reply to this message to respond._"
    )

    for admin_id in ADMIN_IDS:
        try:
            sent = await bot.send_message(admin_id, header, parse_mode="Markdown")
            _support_messages[sent.message_id] = user.id
        except Exception as e:
            logger.warning(f"Could not send support message to admin {admin_id}: {e}")

    await state.clear()
    await message.answer(
        get_text("support_sent", lang),
        reply_markup=get_start_keyboard(user_id=user.id, lang=lang),
        parse_mode="Markdown"
    )


@router.message(SupportState.waiting_message, F.photo)
async def support_receive_photo(message: types.Message, state: FSMContext, bot: Bot) -> None:
    """User sent a photo to support — forward to all admins."""
    user = message.from_user
    username_str = f"@{user.username}" if user.username else "No username"
    caption_text = message.caption or ""
    data = await state.get_data()
    lang = data.get("lang", "en")

    # Admin-facing message stays in English
    header = (
        f"📩 **Support message from:**\n"
        f"👤 {username_str} (ID: `{user.id}`)\n\n"
        f"{caption_text}\n\n"
        f"_Reply to this message to respond._"
    )

    photo = message.photo[-1]  # Highest resolution

    for admin_id in ADMIN_IDS:
        try:
            sent = await bot.send_photo(admin_id, photo=photo.file_id, caption=header, parse_mode="Markdown")
            _support_messages[sent.message_id] = user.id
        except Exception as e:
            logger.warning(f"Could not send support photo to admin {admin_id}: {e}")

    await state.clear()
    await message.answer(
        get_text("support_sent", lang),
        reply_markup=get_start_keyboard(user_id=user.id, lang=lang),
        parse_mode="Markdown"
    )


@router.message(SupportState.waiting_message, F.document)
async def support_receive_document(message: types.Message, state: FSMContext, bot: Bot) -> None:
    """User sent a document to support — forward to all admins."""
    user = message.from_user
    username_str = f"@{user.username}" if user.username else "No username"
    caption_text = message.caption or ""
    data = await state.get_data()
    lang = data.get("lang", "en")

    # Admin-facing message stays in English
    header = (
        f"📩 **Support message from:**\n"
        f"👤 {username_str} (ID: `{user.id}`)\n\n"
        f"{caption_text}\n\n"
        f"_Reply to this message to respond._"
    )

    for admin_id in ADMIN_IDS:
        try:
            sent = await bot.send_document(
                admin_id, document=message.document.file_id, caption=header, parse_mode="Markdown"
            )
            _support_messages[sent.message_id] = user.id
        except Exception as e:
            logger.warning(f"Could not send support document to admin {admin_id}: {e}")

    await state.clear()
    await message.answer(
        get_text("support_sent", lang),
        reply_markup=get_start_keyboard(user_id=user.id, lang=lang),
        parse_mode="Markdown"
    )


@router.message(F.reply_to_message, lambda msg: msg.from_user.id in ADMIN_IDS)
async def admin_reply_to_support(message: types.Message, bot: Bot) -> None:
    """
    Admin replies to a forwarded support message — send the reply back to the user.
    Detects reply by checking if the replied-to message ID is in our tracking dict.
    """
    replied_msg_id = message.reply_to_message.message_id

    user_id = _support_messages.get(replied_msg_id)
    if user_id is None:
        # Not a tracked support message — ignore
        return

    # Get user's language for the reply
    lang = await _get_user_lang(user_id)

    # Send admin's reply to the user
    try:
        if message.text:
            await bot.send_message(
                user_id,
                get_text("support_reply_header", lang, text=message.text),
                parse_mode="Markdown"
            )
        elif message.photo:
            caption = get_text("support_reply_header", lang, text=message.caption or "")
            await bot.send_photo(
                user_id,
                photo=message.photo[-1].file_id,
                caption=caption,
                parse_mode="Markdown"
            )
        elif message.document:
            caption = get_text("support_reply_header", lang, text=message.caption or "")
            await bot.send_document(
                user_id,
                document=message.document.file_id,
                caption=caption,
                parse_mode="Markdown"
            )
        else:
            # Fallback for other message types
            await bot.send_message(
                user_id,
                get_text("support_reply_header", lang, text="_(Unsupported message type)_"),
                parse_mode="Markdown"
            )

        # Confirm to admin (stays in English)
        await message.reply("✅ Reply sent to user.")
    except Exception as e:
        logger.error(f"Failed to send support reply to user {user_id}: {e}")
        await message.reply(f"❌ Failed to send reply to user: {e}")