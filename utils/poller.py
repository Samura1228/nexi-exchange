import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from aiogram import Bot
from sqlalchemy import select, not_

from database import async_session, Transaction
from services.changenow import changenow

logger = logging.getLogger(__name__)

# Status emoji mapping for message updates
STATUS_EMOJI = {
    "waiting": "⏳ Waiting for deposit",
    "confirming": "🔍 Confirming transaction",
    "exchanging": "🔄 Exchanging",
    "sending": "📤 Sending to your wallet",
    "finished": "✅ Exchange complete!",
    "failed": "❌ Exchange failed",
    "refunded": "↩️ Refunded",
    "expired": "⏰ Expired",
}

TERMINAL_STATUSES = {"finished", "failed", "refunded", "expired"}
EXPIRY_HOURS = 24


async def poll_transactions(bot: Bot) -> None:
    """Background task that polls ChangeNow for transaction status updates."""
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
    
    # Check for expiry (waiting for more than 24 hours)
    if tx.status == "waiting" and tx.created_at:
        now = datetime.now(timezone.utc)
        # Handle timezone-naive created_at
        created = tx.created_at if tx.created_at.tzinfo else tx.created_at.replace(tzinfo=timezone.utc)
        if now - created > timedelta(hours=EXPIRY_HOURS):
            await _update_transaction_status(bot, tx, "expired", None)
            return
    
    # Query ChangeNow for current status
    status_data = await changenow.get_transaction_status(tx.changenow_id)
    
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
    
    # Edit Telegram message if we have message_id and chat_id
    if tx.message_id and tx.chat_id:
        try:
            status_text = STATUS_EMOJI.get(new_status, f"❓ {new_status}")
            
            # Build updated message
            from_currency = tx.from_currency.upper()
            to_currency = tx.to_currency.upper()
            
            if new_status == "finished" and amount_to:
                amount_line = f"📥 **Received:** {amount_to} {to_currency}"
            else:
                amount_line = f"📥 **Expected:** ~{tx.amount_expected:.8g} {to_currency}"
            
            text = (
                f"{'✅' if new_status == 'finished' else '🔄'} **Exchange Update**\n\n"
                f"📤 **Sent:** {tx.amount_from:.8g} {from_currency}\n"
                f"{amount_line}\n"
                f"📬 **To:** `{tx.destination_address}`\n\n"
                f"🔄 **Status:** {status_text}\n"
                f"🆔 **Exchange ID:** `{tx.changenow_id}`"
            )
            
            await bot.edit_message_text(
                text=text,
                chat_id=tx.chat_id,
                message_id=tx.message_id,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not edit message for {tx.changenow_id}: {e}")