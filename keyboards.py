from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📈 Prices"),
                KeyboardButton(text="💼 Wallet"),
            ],
            [
                KeyboardButton(text="💱 Exchange"),
                KeyboardButton(text="📥 Deposit"),
            ],
            [
                KeyboardButton(text="📤 Withdraw"),
                KeyboardButton(text="⚙️ Settings"),
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose an option..."
    )
    return keyboard

def get_deposit_method_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔵 Telegram Wallet (Crypto Bot)", callback_data="dep_method_cp"),
            ],
            [
                InlineKeyboardButton(text="🦊 External Wallet (Other wallets)", callback_data="dep_method_np"),
            ]
        ]
    )
    return keyboard
def get_deposit_assets_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="USDT", callback_data="deposit_asset_USDT"),
                InlineKeyboardButton(text="BTC", callback_data="deposit_asset_BTC"),
            ],
            [
                InlineKeyboardButton(text="ETH", callback_data="deposit_asset_ETH"),
                InlineKeyboardButton(text="TON", callback_data="deposit_asset_TON"),
            ]
        ]
    )
    return keyboard
def get_usdt_network_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Tron (TRC20)", callback_data="net_usdttx"),
            ],
            [
                InlineKeyboardButton(text="Ethereum (ERC20)", callback_data="net_usdt"),
            ],
            [
                InlineKeyboardButton(text="Binance Smart Chain (BEP20)", callback_data="net_usdtbsc"),
            ]
        ]
    )
    return keyboard

def get_exchange_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="USDT", callback_data="exch_from_usdt"),
                InlineKeyboardButton(text="BTC", callback_data="exch_from_btc"),
            ],
            [
                InlineKeyboardButton(text="ETH", callback_data="exch_from_eth"),
                InlineKeyboardButton(text="TON", callback_data="exch_from_ton"),
            ]
        ]
    )
    return keyboard

def get_exchange_to_keyboard(from_asset: str) -> InlineKeyboardMarkup:
    assets = ["usdt", "btc", "eth", "ton"]
    if from_asset.lower() in assets:
        assets.remove(from_asset.lower())
    
    buttons = []
    for asset in assets:
        buttons.append(InlineKeyboardButton(text=asset.upper(), callback_data=f"exch_to_{asset}"))
    
    inline_keyboard = []
    for i in range(0, len(buttons), 2):
        inline_keyboard.append(buttons[i:i+2])
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return keyboard
def get_settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🆔 My Account ID", callback_data="settings_my_id"),
            ],
            [
                InlineKeyboardButton(text="🌐 Language", callback_data="settings_language"),
            ]
        ]
    )
    return keyboard

def get_withdraw_asset_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="USDT", callback_data="with_asset_usdt"),
                InlineKeyboardButton(text="BTC", callback_data="with_asset_btc"),
            ],
            [
                InlineKeyboardButton(text="ETH", callback_data="with_asset_eth"),
                InlineKeyboardButton(text="TON", callback_data="with_asset_ton"),
            ]
        ]
    )
    return keyboard
def get_admin_withdraw_keyboard(user_id: int, asset: str, amount: float) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Paid", callback_data=f"admin_paid_{user_id}_{asset}_{amount}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"admin_rej_{user_id}_{asset}_{amount}"),
            ]
        ]
    )
    return keyboard