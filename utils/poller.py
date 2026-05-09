import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from aiogram import Bot
from sqlalchemy import select, not_

from config import EXCHANGE_TIMEOUT_MINUTES, BETA_TEST_USER_IDS
from database import async_session, Transaction, User
from services.swapzone import swapzone
from services.changenow import changenow
from services.supabase_client import supabase
from locales.texts import get_text
from utils import format_amount
from keyboards.builders import get_repeat_exchange_keyboard

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"finished", "failed", "refunded", "expired"}
EXCHANGE_TIMEOUT_SECONDS = EXCHANGE_TIMEOUT_MINUTES * 60


async def _get_user_lang_by_user_id(db_user_id: int) -> str:
    """Get user language by internal user ID (not telegram_id)."""
    async with async_session() as session:
        stmt = select(User).where(User.id == db_user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        return user.language if user else "en"


async def _get_user_info_by_user_id(db_user_id: int) -> tuple[str, int]:
    """Get user language and telegram_id by internal user ID."""
    async with async_session() as session:
        stmt = select(User).where(User.id == db_user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            return user.language or "en", user.telegram_id
        return "en", 0


async def poll_transactions(bot: Bot) -> None:
    """Background task that polls Swapzone for transaction status updates."""
    logger.info("Transaction poller started")
    
    while True:
        try:
            await _check_pending_transactions(bot)
        except Exception as e:
            logger.error(f"Error in transaction poller loop: {e}")
        
        await asyncio.sleep(30)


async def _check_pending_transactions(bot: Bot) -> None:
    """Check all pending transactions and update their status."""
    async with async_session() as session:
        stmt = select(Transaction).where(
            not_(Transaction.status.in_(TERMINAL_STATUSES))
        )
        result = await session.execute(stmt)
        transactions = result.scalars().all()
    
    if not transactions:
        return
    
    logger.info(f"Checking {len(transactions)} pending transactions")
    
    for tx in transactions:
        try:
            await _process_transaction(bot, tx)
        except Exception as e:
            logger.error(f"Error processing transaction {tx.changenow_id}: {e}")


async def _process_transaction(bot: Bot, tx: Transaction) -> None:
    """Process a single transaction — check status and update if changed."""
    
    # Check for expiry (waiting for more than EXCHANGE_TIMEOUT_MINUTES)
    if tx.status == "waiting" and tx.created_at:
        now = datetime.now(timezone.utc)
        # Handle timezone-naive created_at
        created = tx.created_at if tx.created_at.tzinfo else tx.created_at.replace(tzinfo=timezone.utc)
        elapsed = (now - created).total_seconds()
        
        if elapsed >= EXCHANGE_TIMEOUT_SECONDS:
            # Exchange expired — update status and notify user
            await _expire_transaction(bot, tx)
            return
        else:
            # Update the countdown timer in the message
            await _update_waiting_timer(bot, tx, elapsed)
    
    # Query the appropriate provider for current status
    if getattr(tx, "provider", "swapzone") == "changenow":
        status_data = await changenow.get_transaction_status(tx.changenow_id)
    else:
        status_data = await swapzone.get_transaction_status(tx.changenow_id)
    
    if "error" in status_data:
        logger.warning(f"Could not get status for {tx.changenow_id}: {status_data['error']}")
        return
    
    new_status = status_data.get("status", "").lower()
    amount_to = status_data.get("amountTo")
    
    if not new_status:
        return
    
    # Only update if status actually changed
    if new_status != tx.status:
        await _update_transaction_status(bot, tx, new_status, amount_to)


async def _expire_transaction(bot: Bot, tx: Transaction) -> None:
    """Mark a transaction as expired and notify the user."""
    # Update database
    async with async_session() as session:
        stmt = select(Transaction).where(Transaction.id == tx.id)
        result = await session.execute(stmt)
        db_tx = result.scalar_one_or_none()
        
        if not db_tx:
            return
        
        db_tx.status = "expired"
        await session.commit()
    
    logger.info(f"Transaction {tx.changenow_id}: waiting → expired (timeout)")
    
    # Update Supabase status to "incomplete"
    await supabase.update_exchange_status(tx.changenow_id, "incomplete")
    
    # Edit Telegram message
    if tx.message_id and tx.chat_id:
        try:
            lang = await _get_user_lang_by_user_id(tx.user_id)
            text = get_text("timer_expired", lang)
            
            await bot.edit_message_text(
                text=text,
                chat_id=tx.chat_id,
                message_id=tx.message_id,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not edit expired message for {tx.changenow_id}: {e}")


async def _update_waiting_timer(bot: Bot, tx: Transaction, elapsed: float) -> None:
    """Update the deposit message with the remaining countdown timer."""
    if not tx.message_id or not tx.chat_id:
        return
    
    remaining_seconds = max(0, EXCHANGE_TIMEOUT_SECONDS - int(elapsed))
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    timer_str = f"{minutes}:{seconds:02d}"
    
    try:
        lang = await _get_user_lang_by_user_id(tx.user_id)
        
        from_currency = tx.from_currency.upper()
        to_currency = tx.to_currency.upper()
        
        # Rebuild the waiting message with updated timer
        text = (
            f"✅ **Exchange Created!**\n\n"
            f"📤 **Send exactly** `{format_amount(tx.amount_from)}` **{from_currency}** to:\n\n"
            f"📬 `{tx.deposit_address}`\n\n"
            f"📥 **Expected:** ~{format_amount(tx.amount_expected)} {to_currency}\n"
            f"📬 **To:** `{tx.destination_address}`\n\n"
            f"🔄 **Status:** ⏳ {get_text('status_waiting', lang)}\n"
            f"🆔 **Exchange ID:** `{tx.changenow_id}`\n\n"
            f"{get_text('timer_remaining', lang, minutes=minutes, seconds=seconds)}"
            f"{get_text('timer_warning', lang)}"
        )
        
        await bot.edit_message_text(
            text=text,
            chat_id=tx.chat_id,
            message_id=tx.message_id,
            parse_mode="Markdown"
        )
    except Exception as e:
        # Suppress "message is not modified" errors which happen if timer text hasn't changed
        if "message is not modified" not in str(e).lower():
            logger.warning(f"Could not update timer for {tx.changenow_id}: {e}")


async def _update_transaction_status(bot: Bot, tx: Transaction, new_status: str, amount_to=None) -> None:
    """Update transaction status in DB and edit the Telegram message."""
    old_status = tx.status
    
    # Update database
    async with async_session() as session:
        stmt = select(Transaction).where(Transaction.id == tx.id)
        result = await session.execute(stmt)
        db_tx = result.scalar_one_or_none()
        
        if not db_tx:
            return
        
        db_tx.status = new_status
        if amount_to is not None and new_status == "finished":
            db_tx.amount_to = Decimal(str(amount_to))
        
        await session.commit()
    
    logger.info(f"Transaction {tx.changenow_id}: {old_status} → {new_status}")
    
    # Update Supabase status
    if new_status == "finished":
        await supabase.update_exchange_status(tx.changenow_id, "complete", amount_to)
    elif new_status in ("failed", "refunded"):
        await supabase.update_exchange_status(tx.changenow_id, new_status)
    
    # Edit Telegram message if we have message_id and chat_id
    if tx.message_id and tx.chat_id:
        try:
            # Get user's language and telegram_id
            lang, telegram_id = await _get_user_info_by_user_id(tx.user_id)
            
            # Build updated message
            from_currency = tx.from_currency.upper()
            to_currency = tx.to_currency.upper()
            
            if new_status == "finished" and amount_to:
                received_amount = format_amount(amount_to)
                status_text = get_text(f"status_{new_status}", lang, amount=received_amount, currency=to_currency)
                amount_line = f"📥 **Received:** {received_amount} {to_currency}"
            else:
                status_text = get_text(f"status_{new_status}", lang)
                amount_line = f"📥 **Expected:** ~{format_amount(tx.amount_expected)} {to_currency}"
            
            text = (
                f"{'✅' if new_status == 'finished' else '🔄'} **{'Exchange Complete!' if new_status == 'finished' else 'Exchange Update'}**\n\n"
                f"📤 **Sent:** {format_amount(tx.amount_from)} {from_currency}\n"
                f"{amount_line}\n"
                f"📬 **To:** `{tx.destination_address}`\n\n"
                f"🔄 **Status:** {status_text}\n"
                f"🆔 **Exchange ID:** `{tx.changenow_id}`"
            )
            
            # Show repeat exchange button for beta test users on finished exchanges
            reply_markup = None
            if new_status == "finished" and telegram_id in BETA_TEST_USER_IDS:
                reply_markup = get_repeat_exchange_keyboard(tx.id, lang=lang)
            
            await bot.edit_message_text(
                text=text,
                chat_id=tx.chat_id,
                message_id=tx.message_id,
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
        except Exception as e:
            logger.warning(f"Could not edit message for {tx.changenow_id}: {e}")