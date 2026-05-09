import logging
from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func

from config import BETA_TEST_USER_IDS
from database import async_session, User, Transaction
from keyboards.builders import get_start_keyboard, get_language_keyboard
from locales.texts import get_text
from services.supabase_client import supabase

logger = logging.getLogger(__name__)
router = Router()


async def _get_volume_badge(lang: str) -> str:
    """Get volume badge text showing total completed exchanges and unique users."""
    async with async_session() as session:
        # Count completed exchanges
        exchange_count_stmt = select(func.count(Transaction.id)).where(
            Transaction.status == "finished"
        )
        exchange_result = await session.execute(exchange_count_stmt)
        exchange_count = exchange_result.scalar() or 0

        # Count unique users who completed exchanges
        user_count_stmt = select(func.count(func.distinct(Transaction.user_id))).where(
            Transaction.status == "finished"
        )
        user_result = await session.execute(user_count_stmt)
        user_count = user_result.scalar() or 0

    if exchange_count == 0:
        return ""

    return get_text("volume_badge", lang, exchanges=exchange_count, users=user_count)


@router.message(CommandStart())
async def command_start(message: types.Message, state: FSMContext, command: CommandObject, bot: Bot) -> None:
    """Handle /start command. Register user if new, process referral links, show main menu."""
    await state.clear()  # Clear any active FSM state
    
    user_id = message.from_user.id
    username = message.from_user.username

    # Parse deep link parameter (e.g. /start ref_123456)
    referrer_id = None
    logger.info(f"[referral] /start from user {user_id}, command.args={command.args!r}")
    if command.args and command.args.startswith("ref_"):
        try:
            referrer_id = int(command.args[4:])
            logger.info(f"[referral] Parsed referrer_id={referrer_id} for user {user_id}")
            # Don't let users refer themselves
            if referrer_id == user_id:
                referrer_id = None
                logger.info(f"[referral] Self-referral blocked for user {user_id}")
        except (ValueError, IndexError):
            logger.warning(f"[referral] Failed to parse referrer from args: {command.args!r}")
            referrer_id = None

    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # New user — create with referral info (language will be set after selection)
            new_user = User(
                telegram_id=user_id,
                username=username,
                referral_code=f"ref_{user_id}",
                referred_by=referrer_id,
            )
            session.add(new_user)
            await session.commit()
            logger.info(f"[referral] New user registered: {user_id} (@{username}), referred_by={referrer_id}")

            # If referred by someone, update referrer's count and notify them
            if referrer_id:
                logger.info(f"[referral] Processing referral: user {user_id} referred by {referrer_id}")
                referrer_stmt = select(User).where(User.telegram_id == referrer_id)
                referrer_result = await session.execute(referrer_stmt)
                referrer = referrer_result.scalar_one_or_none()
                if referrer:
                    referrer.referral_count += 1
                    await session.commit()
                    logger.info(f"[referral] Referrer {referrer_id} count incremented to {referrer.referral_count}")
                    referrer_lang = referrer.language or "en"
                    # Notify the referrer
                    try:
                        await bot.send_message(
                            referrer_id,
                            get_text("referral_new", referrer_lang, count=referrer.referral_count),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"[referral] Could not notify referrer {referrer_id}: {e}")
                else:
                    logger.warning(f"[referral] Referrer {referrer_id} not found in database")

            # Show language selection for new users
            await message.answer(
                "🌐 **Choose your language / Выберите язык:**",
                reply_markup=get_language_keyboard(),
                parse_mode="Markdown"
            )
            # Store referrer_id in state for after language selection
            await state.update_data(is_new_user=True)
            await supabase.log_event("user_start", user_id, username, "New user - language selection")
            await supabase.log_user(user_id, username, referred_by=referrer_id)
            return
        else:
            # Existing user — update username if changed
            if user.username != username:
                user.username = username
                await session.commit()
            # Set referral_code if missing (for existing users before this feature)
            if not user.referral_code:
                user.referral_code = f"ref_{user_id}"
                await session.commit()
            lang = user.language or "en"
            referred_by = user.referred_by

    await supabase.log_event("user_start", user_id, username, "User started the bot")
    await supabase.log_user(
        user_id=user_id,
        username=username or "",
        language=lang,
        referred_by=referred_by
    )

    welcome_text = get_text("welcome_back", lang)

    # Volume badge for beta test users
    if user_id in BETA_TEST_USER_IDS:
        volume_badge = await _get_volume_badge(lang)
        welcome_text += volume_badge

    await message.answer(
        welcome_text,
        reply_markup=get_start_keyboard(user_id=message.from_user.id, lang=lang),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("lang:"))
async def language_selected(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Handle language selection callback (both for new users and settings)."""
    lang = callback_query.data.split(":")[1]  # "en" or "ru"
    user_id = callback_query.from_user.id

    # Save language to database
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            user.language = lang
            await session.commit()

    # Check if this is from settings or new user flow
    data = await state.get_data()
    is_new_user = data.get("is_new_user", False)
    from_settings = data.get("from_settings", False)

    await state.clear()

    # Update Supabase with the new language
    username = callback_query.from_user.username or ""
    referred_by = user.referred_by if user else None
    await supabase.log_user(
        user_id=user_id,
        username=username,
        language=lang,
        referred_by=referred_by
    )

    if from_settings:
        # Coming from settings — show confirmation and go back to settings
        await callback_query.message.edit_text(
            get_text("language_changed", lang),
            reply_markup=get_start_keyboard(user_id=user_id, lang=lang),
            parse_mode="Markdown"
        )
    else:
        # New user or /start — show welcome message
        await callback_query.message.edit_text(
            get_text("welcome", lang),
            reply_markup=get_start_keyboard(user_id=user_id, lang=lang),
            parse_mode="Markdown"
        )

    await callback_query.answer()


@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Handle back to start menu."""
    await state.clear()
    user_id = callback_query.from_user.id

    # Get user language
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        lang = user.language if user else "en"

    welcome_text = get_text("welcome_back", lang)

    # Volume badge for beta test users
    if user_id in BETA_TEST_USER_IDS:
        volume_badge = await _get_volume_badge(lang)
        welcome_text += volume_badge

    await callback_query.message.edit_text(
        welcome_text,
        reply_markup=get_start_keyboard(user_id=user_id, lang=lang),
        parse_mode="Markdown"
    )
    await callback_query.answer()