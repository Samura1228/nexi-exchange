from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPPORTED_CURRENCIES, SKINS_TEST_USER_IDS, BETA_TEST_USER_IDS, BOT_USERNAME
from locales.texts import get_text


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard with English and Russian options."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        ]
    ])


def get_start_keyboard(user_id: int = 0, lang: str = "en") -> InlineKeyboardMarkup:
    """Main start menu with Start Exchange and My Exchanges buttons.
    Shows 'Buy CS2 Skins' button ONLY if user_id is in SKINS_TEST_USER_IDS.
    """
    buttons = [
        [InlineKeyboardButton(text=get_text("btn_exchange", lang), callback_data="start_exchange")],
        [InlineKeyboardButton(text=get_text("btn_history", lang), callback_data="my_exchanges")],
        [InlineKeyboardButton(text=get_text("btn_referrals", lang), callback_data="referrals")],
        [InlineKeyboardButton(text=get_text("btn_support", lang), callback_data="support"),
         InlineKeyboardButton(text=get_text("btn_settings", lang), callback_data="settings")],
    ]
    if user_id in SKINS_TEST_USER_IDS:
        buttons.append([InlineKeyboardButton(text=get_text("btn_skins", lang), callback_data="start_skins")])
    if user_id in BETA_TEST_USER_IDS:
        buttons.append([InlineKeyboardButton(text=get_text("btn_alerts", lang), callback_data="price_alerts")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_currency_keyboard(action: str, exclude: str = None, lang: str = "en") -> InlineKeyboardMarkup:
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
    rows.append([InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="cancel_exchange")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_confirm_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Confirmation keyboard with Confirm and Cancel buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text("btn_confirm", lang), callback_data="confirm_exchange"),
                InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="cancel_exchange"),
            ]
        ]
    )


def get_cancel_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Simple cancel button keyboard (used during text input states)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="cancel_exchange")]
        ]
    )


def get_settings_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Settings menu keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_my_id", lang), callback_data="settings_my_id")],
            [InlineKeyboardButton(text=get_text("btn_language", lang), callback_data="settings_language")],
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_start")],
        ]
    )


def get_back_to_start_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Simple back button to return to start menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_start")]
        ]
    )


# ── Referral keyboards ────────────────────────────────────────────────


def get_referral_keyboard(user_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    """Referral stats keyboard with share button."""
    referral_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    share_text = get_text("referral_share_text", lang, referral_link=referral_link)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text("btn_share_referral", lang),
            switch_inline_query=share_text,
        )],
        [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_start")],
    ])


# ── CS2 Skins keyboards ──────────────────────────────────────────────


def get_skin_search_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard shown during skin search with cancel option."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="cancel_skins")],
    ])


def get_skin_results_keyboard(items: list, offset: int = 0, total: int = 0, limit: int = 5, lang: str = "en") -> InlineKeyboardMarkup:
    """
    Keyboard for browsing skin search results.
    Each item gets a button with its name and price.
    Plus pagination (Prev/Next) and Cancel.

    Args:
        items: List of dicts with keys: offer_id, title, price_usd (float in dollars)
        offset: Current pagination offset
        total: Total number of results
        limit: Items per page
        lang: User language
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

    buttons.append([InlineKeyboardButton(text=get_text("btn_new_search", lang), callback_data="skin_new_search")])
    buttons.append([InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="cancel_skins")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_skin_item_keyboard(offer_id: str, lang: str = "en") -> InlineKeyboardMarkup:
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

    buttons.append([InlineKeyboardButton(text=get_text("btn_back_results", lang), callback_data="skin_back_results")])
    buttons.append([InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="cancel_skins")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_skin_confirm_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Confirmation keyboard for skin purchase."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text("btn_confirm_purchase", lang), callback_data="skin_confirm"),
            InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="cancel_skins"),
        ]
    ])


# ── Price Alert keyboards ─────────────────────────────────────────────


ALERT_CURRENCIES = [
    ("BTC", "btc"),
    ("ETH", "eth"),
    ("SOL", "sol"),
    ("TON", "ton"),
    ("XRP", "xrp"),
    ("TRX", "trx"),
    ("LTC", "ltc"),
]


def get_alerts_menu_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Main alerts menu keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("btn_new_alert", lang), callback_data="alert_new")],
        [InlineKeyboardButton(text=get_text("btn_my_alerts", lang), callback_data="alert_list")],
        [InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="back_to_start")],
    ])


def get_alert_currency_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Currency selection keyboard for alerts."""
    buttons = []
    row = []
    for display, ticker in ALERT_CURRENCIES:
        row.append(InlineKeyboardButton(text=display, callback_data=f"alert_cur:{ticker}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text=get_text("btn_back_alerts", lang), callback_data="price_alerts")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_alert_direction_keyboard(currency: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Above/below direction keyboard for alerts."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 Above", callback_data=f"alert_dir:{currency}:above"),
            InlineKeyboardButton(text="📉 Below", callback_data=f"alert_dir:{currency}:below"),
        ],
        [InlineKeyboardButton(text=get_text("btn_back_alerts", lang), callback_data="price_alerts")],
    ])


def get_alert_cancel_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Cancel keyboard during alert price entry."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("btn_back_alerts", lang), callback_data="price_alerts")],
    ])


def get_alert_list_keyboard(alerts: list, lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard for listing alerts with delete buttons."""
    buttons = []
    for i, alert in enumerate(alerts, 1):
        currency = alert.currency.upper()
        direction_emoji = "📈" if alert.direction == "above" else "📉"
        btn_text = f"🗑️ {i}. {currency} {direction_emoji} ${alert.target_price:,.2f}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"alert_del:{alert.id}")])
    buttons.append([InlineKeyboardButton(text=get_text("btn_back_alerts", lang), callback_data="price_alerts")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Support keyboards ─────────────────────────────────────────────────


def get_support_cancel_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Cancel button keyboard for support state."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("btn_cancel_support", lang), callback_data="cancel_support")]
    ])