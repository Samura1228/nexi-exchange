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
                KeyboardButton(text="⚙️ Settings"),
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose an option..."
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
def get_exchange_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="USDT to BTC", callback_data="swap_usdt_btc"),
            ],
            [
                InlineKeyboardButton(text="USDT to ETH", callback_data="swap_usdt_eth"),
            ],
            [
                InlineKeyboardButton(text="USDT to TON", callback_data="swap_usdt_ton"),
            ]
        ]
    )
    return keyboard