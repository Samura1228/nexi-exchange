import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANGENOW_API_KEY = os.getenv("CHANGENOW_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
MARKUP_PERCENT = float(os.getenv("MARKUP_PERCENT", "0.5"))  # 0.5% default markup on exchange rates

# Supported currencies: (display_name, changenow_ticker, changenow_network)
SUPPORTED_CURRENCIES = [
    ("BTC", "btc", "btc"),
    ("ETH", "eth", "eth"),
    ("SOL", "sol", "sol"),
    ("TON", "ton", "ton"),
    ("USDT (TRC20)", "usdt", "trx"),
    ("USDT (ERC20)", "usdt", "eth"),
    ("LTC", "ltc", "ltc"),
    ("XRP", "xrp", "xrp"),
    ("TRX", "trx", "trx"),
]

# Validate required config
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set")
if not CHANGENOW_API_KEY:
    raise ValueError("CHANGENOW_API_KEY is not set")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")