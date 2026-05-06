import logging
from aiogram import Router, types, F
from sqlalchemy import select

from database import async_session, User, Transaction
from keyboards.builders import get_back_to_start_keyboard
from locales.texts import get_text

logger = logging.getLogger(__name__)
router = Router()

# Status emoji mapping
STATUS_EMOJI = {
    "waiting": "⏳",
    "confirming": "🔍",
    "exchanging": "🔄",
    "sending": "📤",
    "finished": "✅",
    "failed": "❌",
    "refunded": "↩️",
    "expired": "⏰",
}

@router.callback_query(F.data == "my_exchanges")
async def my_exchanges(callback_query: types.CallbackQuery) -> None:
    """Show user's recent exchange history (last 10 transactions)."""
    user_id = callback_query.from_user.id
    
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            await callback_query.message.edit_text(
                get_text("history_empty", "en"),
                reply_markup=get_back_to_start_keyboard(),
                parse_mode="Markdown"
            )
            await callback_query.answer()
            return
        
        lang = user.language or "en"
        
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        transactions = result.scalars().all()
    
    if not transactions:
        await callback_query.message.edit_text(
            get_text("history_empty", lang),
            reply_markup=get_back_to_start_keyboard(lang=lang),
            parse_mode="Markdown"
        )
        await callback_query.answer()
        return
    
    text = get_text("history_title", lang)
    for tx in transactions:
        emoji = STATUS_EMOJI.get(tx.status, "❓")
        amount_to_str = f"{tx.amount_to:.8g}" if tx.amount_to else f"~{tx.amount_expected:.8g}"
        date_str = tx.created_at.strftime("%Y-%m-%d %H:%M") if tx.created_at else "N/A"
        text += (
            f"{emoji} `{tx.changenow_id[:8]}...` | "
            f"{tx.amount_from:.8g} {tx.from_currency.upper()} → "
            f"{amount_to_str} {tx.to_currency.upper()} | "
            f"{tx.status.capitalize()} | {date_str}\n"
        )
    
    await callback_query.message.edit_text(
        text,
        reply_markup=get_back_to_start_keyboard(lang=lang),
        parse_mode="Markdown"
    )
    await callback_query.answer()