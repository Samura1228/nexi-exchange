from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPPORTED_CURRENCIES, SKINS_TEST_USER_IDS


def get_start_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    """Main start menu with Start Exchange and My Exchanges buttons.
    Shows 'Buy CS2 Skins' button ONLY if user_id is in SKINS_TEST_USER_IDS.
    """
    buttons = [
        [InlineKeyboardButton(text="🟢 Start Exchange", callback_data="start_exchange")],
        [InlineKeyboardButton(text="📋 My Exchanges", callback_data="my_exchanges")],
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")],
    ]
    if user_id in SKINS_TEST_USER_IDS:
        buttons.append([InlineKeyboardButton(text="🔫 Buy CS2 Skins", callback_data="start_skins")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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


# ── CS2 Skins keyboards ──────────────────────────────────────────────


def get_skin_search_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown during skin search with cancel option."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_skins")],
    ])


def get_skin_results_keyboard(items: list, offset: int = 0, total: int = 0, limit: int = 5) -> InlineKeyboardMarkup:
    """
    Keyboard for browsing skin search results.
    Each item gets a button with its name and price.
    Plus pagination (Prev/Next) and Cancel.

    Args:
        items: List of dicts with keys: offer_id, title, price_usd (float in dollars)
        offset: Current pagination offset
        total: Total number of results
        limit: Items per page
    """
    buttons = []
    for item in items:
        price_str = f"${item['price_usd']:.2f}"
        btn_text = f"🔫 {item['title'][:35]} — {price_str}"
        buttons.append([InlineKeyboardButton(
            text=btn_text,
            callback_data=f"skin_view:{item['offer_id']}"
        )])

    # Pagination row
    nav_buttons = []
    if offset > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"skin_page:{offset - limit}"))
    if offset + limit < total:
        nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"skin_page:{offset + limit}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(text="🔍 New Search", callback_data="skin_new_search")])
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_skins")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_skin_item_keyboard(offer_id: str) -> InlineKeyboardMarkup:
    """
    Keyboard for viewing a specific skin item.
    Shows payment crypto options.
    """
    buttons = []
    # Show crypto payment options (use SUPPORTED_CURRENCIES)
    for display_name, ticker, network in SUPPORTED_CURRENCIES:
        buttons.append([InlineKeyboardButton(
            text=f"💰 Pay with {display_name}",
            callback_data=f"skin_pay:{offer_id}:{ticker}:{network}"
        )])

    buttons.append([InlineKeyboardButton(text="⬅️ Back to Results", callback_data="skin_back_results")])
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_skins")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_skin_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirmation keyboard for skin purchase."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Confirm Purchase", callback_data="skin_confirm"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_skins"),
        ]
    ])