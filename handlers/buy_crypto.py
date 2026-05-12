"""
Buy Crypto with Card (Fiat On-Ramp) handler.
Allows users to buy crypto via external widget providers (Onramper, Guardarian, Transak).
Only available to BETA_TEST_USER_IDS.
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from config import BETA_TEST_USER_IDS
from database import async_session, User
from locales.texts import get_text
from utils.states import BuyCryptoState
from keyboards.builders import get_back_to_start_keyboard

logger = logging.getLogger(__name__)

router = Router()

# Crypto mapping for fiat on-ramp providers
FIAT_CRYPTO_MAP = {
    "btc": {"onramper": "btc", "guardarian": "btc", "network": "bitcoin", "display": "BTC"},
    "eth": {"onramper": "eth", "guardarian": "eth", "network": "ethereum", "display": "ETH"},
    "sol": {"onramper": "sol", "guardarian": "sol", "network": "solana", "display": "SOL"},
    "ton": {"onramper": "ton", "guardarian": "ton", "network": "ton", "display": "TON"},
    "usdt": {"onramper": "usdt_trc20", "guardarian": "usdt", "network": "tron", "display": "USDT (TRC20)"},
    "usdt_ton": {"onramper": "usdt_ton", "guardarian": "usdt", "network": "ton", "display": "USDT (TON)"},
    "ltc": {"onramper": "ltc", "guardarian": "ltc", "network": "litecoin", "display": "LTC"},
    "xrp": {"onramper": "xrp", "guardarian": "xrp", "network": "ripple", "display": "XRP"},
    "trx": {"onramper": "trx", "guardarian": "trx", "network": "tron", "display": "TRX"},
}


def generate_buy_links(crypto: str, amount: float, address: str) -> list:
    """Generate buy links for multiple fiat providers."""
    info = FIAT_CRYPTO_MAP.get(crypto, {})
    links = []

    # Onramper
    onramper_crypto = info.get("onramper", crypto)
    links.append({
        "name": "🔵 Onramper",
        "url": f"https://buy.onramper.com/?mode=buy&onlyCryptos={onramper_crypto}&defaultAmount={amount}&defaultFiat=usd&walletAddress={address}"
    })

    # Guardarian
    guardarian_crypto = info.get("guardarian", crypto)
    links.append({
        "name": "🟢 Guardarian",
        "url": f"https://guardarian.com/calculator?default_fiat_currency=usd&default_crypto_currency={guardarian_crypto}&fiat_amount={amount}&crypto_address={address}"
    })

    # Transak
    network = info.get("network", "")
    links.append({
        "name": "🟡 Transak",
        "url": f"https://global.transak.com/?cryptoCurrencyCode={crypto.upper()}&fiatAmount={amount}&fiatCurrency=USD&walletAddress={address}&network={network}"
    })

    return links


def get_buy_crypto_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Crypto selection keyboard for buying."""
    buttons = []
    row = []
    for ticker, info in FIAT_CRYPTO_MAP.items():
        row.append(InlineKeyboardButton(
            text=info["display"],
            callback_data=f"buy_sel:{ticker}"
        ))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_buy_cancel_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Cancel keyboard during buy crypto flow."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="buy_cancel")]
    ])


def get_buy_providers_keyboard(links: list, lang: str = "en") -> InlineKeyboardMarkup:
    """Provider selection keyboard with URL buttons."""
    buttons = []
    for link in links:
        buttons.append([InlineKeyboardButton(text=link["name"], url=link["url"])])
    buttons.append([InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Helpers ────────────────────────────────────────────────────────────


async def _get_user_lang(user_id: int) -> str:
    """Get user language from DB."""
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        return user.language if user else "en"


# ── Handlers ──────────────────────────────────────────────────────────


@router.callback_query(F.data == "buy_crypto")
async def on_buy_crypto(callback: CallbackQuery, state: FSMContext):
    """Entry point: show crypto selection."""
    user_id = callback.from_user.id
    if user_id not in BETA_TEST_USER_IDS:
        await callback.answer("Feature not available.", show_alert=True)
        return

    lang = await _get_user_lang(user_id)

    await state.set_state(BuyCryptoState.select_crypto)
    await callback.message.edit_text(
        f"**{get_text('buy_crypto_title', lang)}**\n\n{get_text('buy_select_crypto', lang)}",
        reply_markup=get_buy_crypto_keyboard(lang),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy_sel:"), BuyCryptoState.select_crypto)
async def on_buy_select_crypto(callback: CallbackQuery, state: FSMContext):
    """User selected a crypto to buy."""
    crypto = callback.data.split(":")[1]
    lang = await _get_user_lang(callback.from_user.id)

    info = FIAT_CRYPTO_MAP.get(crypto)
    if not info:
        await callback.answer("Invalid selection.", show_alert=True)
        return

    await state.update_data(buy_crypto=crypto)
    await state.set_state(BuyCryptoState.enter_amount)

    await callback.message.edit_text(
        f"**{get_text('buy_crypto_title', lang)}**\n\n"
        f"💰 **{info['display']}**\n\n"
        f"{get_text('buy_enter_amount', lang)}",
        reply_markup=get_buy_cancel_keyboard(lang),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(BuyCryptoState.enter_amount)
async def on_buy_enter_amount(message: Message, state: FSMContext):
    """User entered USD amount."""
    lang = await _get_user_lang(message.from_user.id)
    data = await state.get_data()
    crypto = data.get("buy_crypto", "btc")
    info = FIAT_CRYPTO_MAP.get(crypto, {})

    try:
        amount = float(message.text.strip().replace("$", "").replace(",", ""))
        if amount < 30:
            raise ValueError("Below minimum")
    except (ValueError, TypeError):
        await message.answer(
            get_text("buy_invalid_amount", lang),
            reply_markup=get_buy_cancel_keyboard(lang),
            parse_mode="Markdown"
        )
        return

    await state.update_data(buy_amount=amount)
    await state.set_state(BuyCryptoState.enter_address)

    await message.answer(
        f"**{get_text('buy_crypto_title', lang)}**\n\n"
        f"💰 **{info.get('display', crypto.upper())}** — ${amount:.0f}\n\n"
        f"{get_text('buy_enter_address', lang, crypto=info.get('display', crypto.upper()))}",
        reply_markup=get_buy_cancel_keyboard(lang),
        parse_mode="Markdown"
    )


@router.message(BuyCryptoState.enter_address)
async def on_buy_enter_address(message: Message, state: FSMContext):
    """User entered wallet address — show provider links."""
    lang = await _get_user_lang(message.from_user.id)
    data = await state.get_data()
    crypto = data.get("buy_crypto", "btc")
    amount = data.get("buy_amount", 30)
    info = FIAT_CRYPTO_MAP.get(crypto, {})

    address = message.text.strip()

    # Basic address validation (at least 10 chars, no spaces)
    if len(address) < 10 or " " in address:
        await message.answer(
            "❌ That doesn't look like a valid wallet address. Please try again.",
            reply_markup=get_buy_cancel_keyboard(lang),
            parse_mode="Markdown"
        )
        return

    # Generate provider links
    links = generate_buy_links(crypto, amount, address)

    # Build the final message
    text = (
        get_text("buy_providers", lang,
                 amount=f"{amount:.0f}",
                 crypto=info.get("display", crypto.upper()),
                 address=address)
        + get_text("buy_note", lang)
    )

    await message.answer(
        text,
        reply_markup=get_buy_providers_keyboard(links, lang),
        parse_mode="Markdown"
    )

    # Clear state after showing providers
    await state.clear()


@router.callback_query(F.data == "buy_cancel")
async def on_buy_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel buy crypto flow."""
    lang = await _get_user_lang(callback.from_user.id)

    await state.clear()
    await callback.message.edit_text(
        get_text("buy_cancelled", lang),
        reply_markup=get_back_to_start_keyboard(lang),
        parse_mode="Markdown"
    )
    await callback.answer()