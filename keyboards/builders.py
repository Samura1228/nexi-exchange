from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPPORTED_CURRENCIES


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Main start menu with Start Exchange and My Exchanges buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Start Exchange", callback_data="start_exchange")],
            [InlineKeyboardButton(text="📋 My Exchanges", callback_data="my_exchanges")],
            [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")],
        ]
    )


def get_currency_keyboard(action: str, exclude: str = None) -> InlineKeyboardMarkup:
    """
    Build currency selection keyboard.
    action: "from" or "to" — used in callback_data prefix
    exclude: currency key to exclude (e.g., "btc:btc" for the FROM selection when choosing TO)

    Each button callback_data format: "sel:{action}:{ticker}:{network}"
    Example: "sel:from:btc:btc", "sel:to:usdt:trx"
    """
    buttons = []
    for display_name, ticker, network in SUPPORTED_CURRENCIES:
        key = f"{ticker}:{network}"
        if exclude and key == exclude:
            continue
        buttons.append(
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"sel:{action}:{ticker}:{network}"
            )
        )

    # Arrange in rows of 3
    rows = []
    for i in range(0, len(buttons), 3):
        rows.append(buttons[i:i+3])

    # Add cancel button
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_exchange")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirmation keyboard with Confirm and Cancel buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm Exchange", callback_data="confirm_exchange"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_exchange"),
            ]
        ]
    )


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Simple cancel button keyboard (used during text input states)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_exchange")]
        ]
    )


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Settings menu keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆔 My Account ID", callback_data="settings_my_id")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_start")],
        ]
    )


def get_back_to_start_keyboard() -> InlineKeyboardMarkup:
    """Simple back button to return to start menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_start")]
        ]
    )