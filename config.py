import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANGENOW_API_KEY = os.getenv("CHANGENOW_API_KEY", "")
SWAPZONE_API_KEY = os.getenv("SWAPZONE_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
MARKUP_PERCENT = float(os.getenv("MARKUP_PERCENT", "0.5"))  # 0.5% default markup on exchange rates

# Referral system
REFERRAL_PERCENT = float(os.getenv("REFERRAL_PERCENT", "20"))  # 20% of bot's markup goes to referrer

# Exchange timeout (minutes) — auto-cancel if no deposit received
EXCHANGE_TIMEOUT_MINUTES = int(os.getenv("EXCHANGE_TIMEOUT_MINUTES", "60"))

# Supabase (Admin Dashboard)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")  # e.g., https://xxxxx.supabase.co
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")  # anon/service_role key
BOT_USERNAME = os.getenv("BOT_USERNAME", "your_bot")  # For generating referral links

# CS2 Skins feature (DMarket integration) — test mode
DMARKET_API_KEY = os.getenv("DMARKET_API_KEY", "")
DMARKET_API_SECRET = os.getenv("DMARKET_API_SECRET", "")
DMARKET_API_URL = "https://api.dmarket.com"

# Users who can access CS2 skins feature (test mode)
SKINS_TEST_USER_IDS = [int(x.strip()) for x in os.getenv("SKINS_TEST_USER_IDS", "6840070959").split(",") if x.strip()]

# Users who can access beta features (price alerts, etc.)
BETA_TEST_USER_IDS = [int(x) for x in os.getenv("BETA_TEST_USER_IDS", "6840070959").split(",") if x.strip()]

# Markup on skin prices (percentage)
SKINS_MARKUP_PERCENT = float(os.getenv("SKINS_MARKUP_PERCENT", "7.0"))

# Supported currencies: (display_name, ticker, network)
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
if not SWAPZONE_API_KEY:
    raise ValueError("SWAPZONE_API_KEY is not set")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")