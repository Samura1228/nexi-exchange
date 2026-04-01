# Implementation Plan: Non-Custodial Crypto Exchange Bot Rewrite

> **Project:** exi_exchange  
> **Date:** 2026-04-01  
> **Status:** Approved for implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [New Architecture Overview](#3-new-architecture-overview)
4. [File Structure](#4-file-structure)
5. [Database Schema](#5-database-schema)
6. [Configuration & Environment](#6-configuration--environment)
7. [ChangeNow API Service](#7-changenow-api-service)
8. [Supported Currencies](#8-supported-currencies)
9. [User Flow & Handlers](#9-user-flow--handlers)
10. [Background Transaction Poller](#10-background-transaction-poller)
11. [Keyboard Builders](#11-keyboard-builders)
12. [Google Sheets Logging](#12-google-sheets-logging)
13. [Revenue Model](#13-revenue-model)
14. [Error Handling Strategy](#14-error-handling-strategy)
15. [Security Requirements](#15-security-requirements)
16. [Dependencies](#16-dependencies)
17. [Implementation Order](#17-implementation-order)
18. [File-by-File Specifications](#18-file-by-file-specifications)

---

## 1. Executive Summary

Rewrite the existing broken custodial exchange bot into a **non-custodial exchange** powered by the **ChangeNow API**. The bot will act purely as a frontend — it never holds user funds. Users select a currency pair, get a quote, provide a destination address, and receive a deposit address from ChangeNow. The bot tracks transaction status automatically via a background poller.

### Key Principles
- **Non-custodial**: Bot never holds crypto. ChangeNow handles all swaps.
- **No wallets/balances**: Remove the `Balance` model entirely. No deposit/withdraw flows.
- **Automated tracking**: Background poller monitors transaction status and updates users in real-time.
- **Clean architecture**: Modular file structure with separated concerns.

---

## 2. Current State Analysis

### Files to Rewrite Completely
| File | Lines | Issues |
|------|-------|--------|
| [`main.py`](main.py:1) | 791 | Monolithic; all handlers in one file; custodial exchange logic; hardcoded admin ID `6840070959` on line 668; double-credit vulnerability in payment check handlers; float precision for financial data |
| [`database.py`](database.py:1) | 39 | Exposed DB credentials on line 10; `Balance` model uses `Float` type; no `Transaction` model |
| [`keyboards.py`](keyboards.py:1) | 132 | Only supports 4 assets; custodial-specific keyboards (deposit method, withdraw, admin) |
| [`requirements.txt`](requirements.txt:1) | 8 | Includes `aiocryptopay` (no longer needed) |

### Files to Keep (with minor updates)
| File | Lines | Notes |
|------|-------|-------|
| [`sheets.py`](sheets.py:1) | 54 | Works fine. Keep as-is. |
| [`Procfile`](Procfile:1) | 1 | Keep as-is: `worker: python main.py` |

### What Gets Removed
- **`Balance` model** — no more custodial balances
- **Deposit flow** — no more CryptoPay/NowPayments deposits
- **Withdraw flow** — no more manual admin withdrawals
- **Wallet view** — no internal wallet to display
- **Prices view** — replaced by real-time ChangeNow quotes
- **`aiocryptopay` dependency** — removed entirely

---

## 3. New Architecture Overview

```mermaid
sequenceDiagram
    participant U as User (Telegram)
    participant B as Bot (aiogram)
    participant DB as PostgreSQL
    participant CN as ChangeNow API

    U->>B: /start
    B->>U: Welcome + "Start Exchange" button

    U->>B: Tap "Start Exchange"
    B->>U: Show FROM currency grid

    U->>B: Select BTC
    B->>U: Show TO currency grid (excludes BTC)

    U->>B: Select ETH
    B->>CN: GET /exchange/min-amount?fromCurrency=btc&toCurrency=eth&fromNetwork=btc&toNetwork=eth
    CN->>B: { minAmount: 0.0001 }
    B->>U: "Enter amount (min: 0.0001 BTC)"

    U->>B: "0.05"
    B->>CN: GET /exchange/estimated-amount?fromCurrency=btc&toCurrency=eth&fromAmount=0.05&fromNetwork=btc&toNetwork=eth
    CN->>B: { estimatedAmount: 0.82 }
    B->>U: "You send 0.05 BTC → You get ~0.82 ETH. Enter your ETH address:"

    U->>B: "0xABC123..."
    B->>U: Confirmation summary + ✅ Confirm / ❌ Cancel

    U->>B: Tap ✅ Confirm
    B->>CN: POST /exchange { fromCurrency, toCurrency, fromAmount, address, fromNetwork, toNetwork }
    CN->>B: { id: "abc123", depositAddress: "bc1q...", status: "waiting" }
    B->>DB: INSERT Transaction (changenow_id, status, deposit_address, ...)
    B->>U: "Send exactly 0.05 BTC to bc1q... Status: ⏳ Waiting for deposit"

    loop Every 30 seconds (Background Poller)
        B->>DB: SELECT transactions WHERE status NOT IN (finished, failed, refunded, expired)
        B->>CN: GET /exchange/by-id/{id}
        CN->>B: { status: "exchanging" }
        B->>DB: UPDATE transaction SET status = "exchanging"
        B->>U: Edit message: "Status: 🔄 Exchanging..."
    end

    Note over B,CN: When status = "finished"
    B->>U: Edit message: "✅ Complete! You received 0.82 ETH"
```

---

## 4. File Structure

```
exi_exchange/
├── main.py                  # Entry point: bot init, register routers, start polling + background tasks
├── config.py                # Environment config loader (all settings from .env)
├── database.py              # SQLAlchemy models: User, Transaction (no Balance)
├── services/
│   └── changenow.py         # ChangeNow API wrapper (all HTTP calls)
├── handlers/
│   ├── start.py             # /start command handler
│   ├── exchange.py          # Exchange FSM flow (the main feature)
│   ├── history.py           # /history command - view past transactions
│   └── settings.py          # Settings menu (ID, language placeholder)
├── keyboards/
│   └── builders.py          # All keyboard builders (inline + reply)
├── utils/
│   ├── states.py            # FSM state definitions (ExchangeState)
│   └── poller.py            # Background transaction status poller
├── sheets.py                # Google Sheets logging (keep existing, no changes)
├── requirements.txt         # Updated dependencies
├── Procfile                 # Keep as-is: worker: python main.py
└── .env.example             # Example environment variables
```

### Files to Delete
- None of the old files need to be deleted — they will all be **overwritten** with new content (except [`sheets.py`](sheets.py:1) and [`Procfile`](Procfile:1) which stay the same).

### New Files to Create
- [`config.py`](config.py) — new
- [`services/changenow.py`](services/changenow.py) — new
- [`handlers/start.py`](handlers/start.py) — new
- [`handlers/exchange.py`](handlers/exchange.py) — new
- [`handlers/history.py`](handlers/history.py) — new
- [`handlers/settings.py`](handlers/settings.py) — new
- [`keyboards/builders.py`](keyboards/builders.py) — new
- [`utils/states.py`](utils/states.py) — new
- [`utils/poller.py`](utils/poller.py) — new
- [`.env.example`](.env.example) — new
- `services/__init__.py` — empty init
- `handlers/__init__.py` — empty init
- `keyboards/__init__.py` — empty init
- `utils/__init__.py` — empty init

---

## 5. Database Schema

### Remove
- **`Balance` model** — delete entirely. The bot is non-custodial; there are no internal balances.

### `User` Model (updated)

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transactions: Mapped[List["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
```

**Changes from current:**
- Added `created_at` column with server default
- Added index on `telegram_id` for faster lookups
- Changed relationship from `balances` to `transactions`
- Added `String(255)` length constraint on `username`

### `Transaction` Model (new)

```python
class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    changenow_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    from_currency: Mapped[str] = mapped_column(String(20), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(20), nullable=False)
    from_network: Mapped[str] = mapped_column(String(20), nullable=False)
    to_network: Mapped[str] = mapped_column(String(20), nullable=False)
    
    amount_from: Mapped[Decimal] = mapped_column(Numeric(precision=28, scale=18), nullable=False)
    amount_expected: Mapped[Decimal] = mapped_column(Numeric(precision=28, scale=18), nullable=False)
    amount_to: Mapped[Decimal | None] = mapped_column(Numeric(precision=28, scale=18), nullable=True)  # filled when finished
    
    destination_address: Mapped[str] = mapped_column(String(512), nullable=False)
    deposit_address: Mapped[str] = mapped_column(String(512), nullable=False)
    
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="waiting",
        index=True
    )
    # Possible statuses: waiting, confirming, exchanging, sending, finished, failed, refunded, expired
    
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # Telegram message ID to edit
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)     # Telegram chat ID
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="transactions")
```

**Key design decisions:**
- Use `Numeric(precision=28, scale=18)` instead of `Float` to avoid precision issues with financial data
- `changenow_id` is unique and indexed for fast lookups by the poller
- `status` is indexed because the poller queries by status every 30 seconds
- `message_id` and `chat_id` stored so the poller can edit the user's status message
- `amount_to` is nullable — only filled when the exchange completes (`status = 'finished'`)

### Database Initialization

The [`database.py`](database.py) `init_db()` function stays the same pattern (using `Base.metadata.create_all`), but now creates the new schema. The old `balances` table will remain in the DB but won't be used. A manual `DROP TABLE balances;` can be run after migration if desired.

---

## 6. Configuration & Environment

### `config.py` — New File

```python
import os
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

# Bot
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Database
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# ChangeNow
CHANGENOW_API_KEY: str = os.getenv("CHANGENOW_API_KEY", "")
CHANGENOW_BASE_URL: str = "https://api.changenow.io/v2"

# Admin
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# Revenue: markup percentage added on top of ChangeNow's estimated amount
# e.g., 1.0 means 1% markup (user gets 1% less than ChangeNow quote)
MARKUP_PERCENT: Decimal = Decimal(os.getenv("MARKUP_PERCENT", "1.0"))

# Poller
POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
TRANSACTION_EXPIRY_HOURS: int = int(os.getenv("TRANSACTION_EXPIRY_HOURS", "24"))

# Rate limiting
EXCHANGE_COOLDOWN_SECONDS: int = int(os.getenv("EXCHANGE_COOLDOWN_SECONDS", "30"))

# Google Sheets
SPREADSHEET_ID: str = os.getenv("SPREADSHEET_ID", "")
```

### `.env.example` — New File

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token

# PostgreSQL (asyncpg format)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname

# ChangeNow API
CHANGENOW_API_KEY=your_changenow_api_key

# Admin Telegram IDs (comma-separated)
ADMIN_IDS=123456789,987654321

# Revenue markup percentage (e.g., 1.0 = 1%)
MARKUP_PERCENT=1.0

# Poller settings
POLL_INTERVAL_SECONDS=30
TRANSACTION_EXPIRY_HOURS=24

# Rate limiting
EXCHANGE_COOLDOWN_SECONDS=30

# Google Sheets
SPREADSHEET_ID=your_spreadsheet_id
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
```

**Security improvements over current code:**
- No hardcoded credentials (current [`database.py`](database.py:10) has exposed DB URL)
- No hardcoded admin ID (current [`main.py`](main.py:668) has `admin_id = 6840070959`)
- All secrets loaded from environment variables
- `.env.example` provided as template (actual `.env` is in `.gitignore`)

---

## 7. ChangeNow API Service

### `services/changenow.py` — New File

This module wraps all ChangeNow v2 API calls using `aiohttp`.

**Base URL:** `https://api.changenow.io/v2`  
**Auth Header:** `x-changenow-api-key: {CHANGENOW_API_KEY}`

#### Class: `ChangeNowService`

```python
class ChangeNowService:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazy-create a reusable aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"x-changenow-api-key": self.api_key}
            )
        return self._session

    async def close(self):
        """Close the HTTP session. Call on bot shutdown."""
        if self._session and not self._session.closed:
            await self._session.close()
```

#### Methods to Implement

| Method | API Endpoint | HTTP | Purpose |
|--------|-------------|------|---------|
| `get_available_currencies()` | `/exchange/currencies?active=true` | GET | List all active currencies (used for validation) |
| `get_min_amount(from_currency, to_currency, from_network, to_network)` | `/exchange/min-amount` | GET | Get minimum exchange amount for a pair |
| `get_estimated_amount(from_currency, to_currency, from_amount, from_network, to_network)` | `/exchange/estimated-amount` | GET | Get estimated output amount for a given input |
| `create_exchange(from_currency, to_currency, from_amount, address, from_network, to_network)` | `/exchange` | POST | Create an exchange transaction; returns deposit address |
| `get_transaction_status(transaction_id)` | `/exchange/by-id/{id}` | GET | Get current status of a transaction |

#### Method Signatures & Return Types

```python
async def get_min_amount(
    self,
    from_currency: str,
    to_currency: str,
    from_network: str,
    to_network: str,
) -> Decimal | None:
    """
    Returns the minimum exchange amount, or None on error.
    
    GET /exchange/min-amount?fromCurrency=btc&toCurrency=eth&fromNetwork=btc&toNetwork=eth
    Response: { "minAmount": 0.0001 }
    """

async def get_estimated_amount(
    self,
    from_currency: str,
    to_currency: str,
    from_amount: Decimal,
    from_network: str,
    to_network: str,
) -> Decimal | None:
    """
    Returns the estimated output amount, or None on error.
    
    GET /exchange/estimated-amount?fromCurrency=btc&toCurrency=eth&fromAmount=0.1&fromNetwork=btc&toNetwork=eth
    Response: { "estimatedAmount": 1.234 }
    """

async def create_exchange(
    self,
    from_currency: str,
    to_currency: str,
    from_amount: Decimal,
    address: str,
    from_network: str,
    to_network: str,
) -> dict | None:
    """
    Creates an exchange. Returns the full response dict or None on error.
    
    POST /exchange
    Body: { "fromCurrency": "btc", "toCurrency": "eth", "fromAmount": "0.1",
            "address": "0x...", "fromNetwork": "btc", "toNetwork": "eth", "flow": "standard" }
    Response: { "id": "abc123", "depositAddress": "bc1q...", "fromAmount": 0.1, ... }
    """

async def get_transaction_status(self, transaction_id: str) -> dict | None:
    """
    Returns transaction status dict or None on error.
    
    GET /exchange/by-id/{id}
    Response: { "id": "abc123", "status": "exchanging", "amountTo": 1.23, ... }
    """
```

#### Error Handling Pattern

Every method should follow this pattern:

```python
async def some_method(self, ...) -> SomeType | None:
    try:
        session = await self._get_session()
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                body = await resp.text()
                logging.error(f"ChangeNow API error {resp.status}: {body}")
                return None
            data = await resp.json()
            return process(data)
    except aiohttp.ClientError as e:
        logging.error(f"ChangeNow network error: {e}")
        return None
    except Exception as e:
        logging.error(f"ChangeNow unexpected error: {e}")
        return None
```

---

## 8. Supported Currencies

Define a constant dictionary in [`config.py`](config.py) (or a separate constants file) mapping display names to ChangeNow tickers and networks:

```python
SUPPORTED_CURRENCIES: dict[str, dict[str, str]] = {
    "BTC": {"ticker": "btc", "network": "btc"},
    "ETH": {"ticker": "eth", "network": "eth"},
    "SOL": {"ticker": "sol", "network": "sol"},
    "TON": {"ticker": "ton", "network": "ton"},
    "USDT-TRC20": {"ticker": "usdt", "network": "trx"},
    "USDT-ERC20": {"ticker": "usdt", "network": "eth"},
    "LTC": {"ticker": "ltc", "network": "ltc"},
    "XRP": {"ticker": "xrp", "network": "xrp"},
    "TRX": {"ticker": "trx", "network": "trx"},
}
```

**Important:** USDT appears twice with different networks. The display name includes the network suffix (e.g., "USDT-TRC20") to disambiguate. The callback data will use the display name as the key.

---

## 9. User Flow & Handlers

### FSM States (`utils/states.py`)

```python
from aiogram.fsm.state import State, StatesGroup

class ExchangeState(StatesGroup):
    select_from = State()       # Waiting for FROM currency selection
    select_to = State()         # Waiting for TO currency selection
    enter_amount = State()      # Waiting for amount input
    enter_address = State()     # Waiting for destination address
    confirm = State()           # Waiting for confirm/cancel
```

### Handler: `/start` (`handlers/start.py`)

**Trigger:** `/start` command  
**Action:**
1. Upsert user in DB (create if not exists, update username if changed)
2. Log to Google Sheets: "Start Bot"
3. Send welcome message with reply keyboard:
   - "🟢 Start Exchange"
   - "📋 My Exchanges"
   - "⚙️ Settings"

**Reply Keyboard Layout:**
```
[ 🟢 Start Exchange ]
[ 📋 My Exchanges ] [ ⚙️ Settings ]
```

### Handler: Exchange Flow (`handlers/exchange.py`)

This is the main feature. It's an FSM-driven conversation flow.

#### Step 1: Start Exchange
**Trigger:** Reply keyboard button "🟢 Start Exchange"  
**Action:**
1. Check rate limit: if user created an exchange in the last `EXCHANGE_COOLDOWN_SECONDS`, show error
2. Send inline keyboard with FROM currency grid
3. Set state to `ExchangeState.select_from`

#### Step 2: Select FROM Currency
**Trigger:** Callback `exch_from_{currency_key}` in state `ExchangeState.select_from`  
**Action:**
1. Store `from_currency` key in FSM data
2. Send inline keyboard with TO currency grid (excluding the selected FROM currency)
3. Set state to `ExchangeState.select_to`

#### Step 3: Select TO Currency
**Trigger:** Callback `exch_to_{currency_key}` in state `ExchangeState.select_to`  
**Action:**
1. Store `to_currency` key in FSM data
2. Call `ChangeNowService.get_min_amount()` with the pair's tickers/networks
3. If API fails → show error, clear state
4. Store `min_amount` in FSM data
5. Send message: `"Enter the amount of {FROM} to exchange (minimum: {min_amount} {FROM}):"`
6. Set state to `ExchangeState.enter_amount`

#### Step 4: Enter Amount
**Trigger:** Text message in state `ExchangeState.enter_amount`  
**Action:**
1. Parse input as `Decimal`. If invalid → ask again
2. If amount < `min_amount` → show error with minimum, ask again
3. Call `ChangeNowService.get_estimated_amount()` with the amount
4. If API fails → show error, clear state
5. Apply markup: `display_amount = estimated_amount * (1 - MARKUP_PERCENT / 100)`
6. Store `amount_from`, `amount_expected` (the display amount after markup) in FSM data
7. Send message:
   ```
   💱 Exchange Quote:
   
   You send: 0.05 BTC
   You get: ~0.82 ETH
   
   Enter your ETH destination address:
   ```
8. Set state to `ExchangeState.enter_address`

#### Step 5: Enter Destination Address
**Trigger:** Text message in state `ExchangeState.enter_address`  
**Action:**
1. Basic validation: non-empty, reasonable length (5-512 chars), no spaces
2. Store `destination_address` in FSM data
3. Send confirmation summary with inline buttons:
   ```
   📋 Exchange Summary:
   
   Send: 0.05 BTC
   Receive: ~0.82 ETH
   To address: 0xABC123...
   
   [✅ Confirm Exchange]  [❌ Cancel]
   ```
4. Set state to `ExchangeState.confirm`

#### Step 6: Confirm or Cancel
**Trigger:** Callback `exchange_confirm` or `exchange_cancel` in state `ExchangeState.confirm`

**On Cancel:**
1. Edit message to "❌ Exchange cancelled."
2. Clear FSM state

**On Confirm:**
1. Call `ChangeNowService.create_exchange()` with all stored data
2. If API fails → edit message to error, clear state
3. Create `Transaction` record in DB with:
   - All exchange details from ChangeNow response
   - `changenow_id` = response `id`
   - `deposit_address` = response `depositAddress`
   - `status` = "waiting"
   - `message_id` and `chat_id` = will be set after sending the status message
4. Edit the confirmation message (or send new message) with deposit instructions:
   ```
   ✅ Exchange created!
   
   Send exactly 0.05 BTC to:
   `bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh`
   
   ⏳ Status: Waiting for deposit
   
   This will update automatically. You can also check /history
   ```
5. Save the `message_id` of this sent message to the Transaction record (so the poller can edit it)
6. Log to Google Sheets: "Exchange Created"
7. Clear FSM state

### Handler: History (`handlers/history.py`)

**Trigger:** Reply keyboard button "📋 My Exchanges" OR `/history` command  
**Action:**
1. Query DB for user's transactions, ordered by `created_at DESC`, limit 10
2. If no transactions → "You haven't made any exchanges yet."
3. For each transaction, show:
   ```
   🔄 0.05 BTC → ETH
   Status: ✅ Finished (0.82 ETH received)
   Date: 2026-04-01 14:30
   ID: abc123
   ```
4. Status emojis:
   - `waiting` → ⏳
   - `confirming` → 🔍
   - `exchanging` → 🔄
   - `sending` → 📤
   - `finished` → ✅
   - `failed` → ❌
   - `refunded` → ↩️
   - `expired` → ⏰

### Handler: Settings (`handlers/settings.py`)

**Trigger:** Reply keyboard button "⚙️ Settings"  
**Action:**
1. Show inline keyboard:
   - "🆔 My Account ID" → shows Telegram ID
   - "🌐 Language" → "Coming soon!" alert

Keep the same logic as current [`main.py`](main.py:764) settings handlers.

---

## 10. Background Transaction Poller

### `utils/poller.py` — New File

#### Function: `start_poller(bot, session_factory, changenow_service)`

This is an `asyncio` background task that runs alongside the bot's polling.

```python
async def poll_transactions(
    bot: Bot,
    session_factory: async_sessionmaker,
    changenow: ChangeNowService,
):
    """
    Runs every POLL_INTERVAL_SECONDS.
    Checks all active transactions and updates their status.
    """
    while True:
        try:
            await _check_active_transactions(bot, session_factory, changenow)
        except Exception as e:
            logging.error(f"Poller error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
```

#### Logic: `_check_active_transactions()`

1. Open a DB session
2. Query all transactions where `status NOT IN ('finished', 'failed', 'refunded', 'expired')`
3. Also check for expired transactions: if `created_at` is older than `TRANSACTION_EXPIRY_HOURS` hours and status is still `waiting`, mark as `expired`
4. For each active transaction:
   a. Call `ChangeNowService.get_transaction_status(changenow_id)`
   b. If API call fails → skip (will retry next cycle). Log warning.
   c. If status changed from what's in DB:
      - Update `status` in DB
      - If new status is `finished`, also update `amount_to` from the API response
      - Try to edit the Telegram message using stored `chat_id` and `message_id`
      - Log status change to Google Sheets
   d. If status unchanged → do nothing

#### Message Editing Format

When the poller detects a status change, it edits the original deposit message:

```
✅ Exchange created!

Send exactly 0.05 BTC to:
`bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh`

{status_emoji} Status: {status_text}
{extra_info}
```

Status text mapping:
| Status | Emoji | Text | Extra Info |
|--------|-------|------|------------|
| waiting | ⏳ | Waiting for deposit | — |
| confirming | 🔍 | Confirming transaction | Deposit received, waiting for confirmations |
| exchanging | 🔄 | Exchanging | Your funds are being exchanged |
| sending | 📤 | Sending to you | Sending {to_currency} to your address |
| finished | ✅ | Complete! | You received {amount_to} {to_currency} |
| failed | ❌ | Failed | Please contact support |
| refunded | ↩️ | Refunded | Funds returned to sender |
| expired | ⏰ | Expired | No deposit received within 24h |

#### Error Resilience
- If editing a message fails (e.g., message too old, chat not found), log the error but don't crash
- If the ChangeNow API is temporarily down, the poller skips and retries next cycle
- Use `try/except` around each individual transaction check so one failure doesn't block others

---

## 11. Keyboard Builders

### `keyboards/builders.py` — New File

#### Reply Keyboards

```python
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main menu after /start"""
    # Row 1: [ 🟢 Start Exchange ]
    # Row 2: [ 📋 My Exchanges ] [ ⚙️ Settings ]
```

#### Inline Keyboards

```python
def get_currency_keyboard(prefix: str, exclude: str | None = None) -> InlineKeyboardMarkup:
    """
    Builds a grid of currency buttons.
    prefix: "exch_from" or "exch_to" — used in callback_data
    exclude: currency key to exclude (e.g., "BTC" when selecting TO after FROM=BTC)
    
    Layout: 3 columns grid
    [ BTC ] [ ETH ] [ SOL ]
    [ TON ] [ USDT-TRC20 ] [ USDT-ERC20 ]
    [ LTC ] [ XRP ] [ TRX ]
    
    Callback data format: {prefix}_{currency_key}
    e.g., exch_from_BTC, exch_to_USDT-TRC20
    """

def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Confirmation buttons for exchange.
    [ ✅ Confirm Exchange ] [ ❌ Cancel ]
    Callback data: exchange_confirm, exchange_cancel
    """

def get_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Settings menu (same as current).
    [ 🆔 My Account ID ]
    [ 🌐 Language ]
    """
```

---

## 12. Google Sheets Logging

**No changes to [`sheets.py`](sheets.py:1).** Keep the existing implementation as-is.

The following actions should be logged throughout the new code:

| Action Type | Details | Where |
|-------------|---------|-------|
| Start Bot | User started the bot | `handlers/start.py` |
| Exchange Created | Created exchange: 0.05 BTC → ETH, CN ID: abc123 | `handlers/exchange.py` |
| Exchange Status Update | Transaction abc123: waiting → confirming | `utils/poller.py` |
| Exchange Completed | Transaction abc123 completed: received 0.82 ETH | `utils/poller.py` |
| Exchange Failed | Transaction abc123 failed | `utils/poller.py` |

---

## 13. Revenue Model

The bot owner earns revenue by adding a configurable markup to ChangeNow's estimated amounts.

### How It Works

1. ChangeNow returns an estimated output amount (e.g., 0.83 ETH for 0.05 BTC)
2. ChangeNow already includes their own fee in this estimate
3. The bot applies an additional markup: `displayed_amount = estimated * (1 - MARKUP_PERCENT / 100)`
4. With `MARKUP_PERCENT=1.0`: user sees 0.8217 ETH instead of 0.83 ETH
5. When the exchange completes, ChangeNow sends the full ~0.83 ETH to the user's address
6. The difference (0.83 - 0.8217 = ~0.0083 ETH) is the bot owner's profit

**Wait — this doesn't work with non-custodial!** Since ChangeNow sends directly to the user's address, the bot can't skim a fee.

### Corrected Revenue Approach

**Option A: Display markup only (psychological pricing)**
- Show the user a slightly lower estimate so they're pleasantly surprised when they receive more
- No actual revenue — just better UX

**Option B: Use ChangeNow's affiliate/referral program**
- ChangeNow offers a revenue share program for API partners
- Sign up at https://changenow.io/affiliate
- Revenue is earned per transaction automatically

**Option C: Adjust the `fromAmount` sent to ChangeNow**
- User wants to send 0.05 BTC
- Bot tells ChangeNow the `fromAmount` is 0.0495 BTC (after 1% fee)
- Bot shows deposit address and tells user to send 0.05 BTC
- The extra 0.0005 BTC stays at the deposit address (but ChangeNow controls it, so this doesn't work either)

**Recommendation:** Use **Option B** (ChangeNow affiliate program) for real revenue. Implement **Option A** as a configurable display markup for now. The `MARKUP_PERCENT` config controls the display estimate reduction. Document this clearly in the code.

---

## 14. Error Handling Strategy

### API Failures

```python
# In handlers/exchange.py — when fetching min amount or estimate
result = await changenow.get_min_amount(...)
if result is None:
    await callback_query.message.edit_text(
        "⚠️ Unable to fetch exchange rate. Please try again in a moment."
    )
    await state.clear()
    return
```

### User Input Validation

| Input | Validation | Error Message |
|-------|-----------|---------------|
| Amount | Must be valid Decimal, positive, ≥ min_amount | "Please enter a valid number." / "Minimum amount is X {currency}." |
| Address | Non-empty, 5-512 chars, no whitespace | "Please enter a valid {currency} address." |
| Currency selection | Must be in `SUPPORTED_CURRENCIES` | (shouldn't happen with inline keyboards, but validate anyway) |

### Poller Resilience

```python
# In utils/poller.py
for transaction in active_transactions:
    try:
        await _process_single_transaction(transaction, bot, session, changenow)
    except Exception as e:
        logging.error(f"Error processing transaction {transaction.changenow_id}: {e}")
        continue  # Don't let one failure stop others
```

### Transaction Expiry

In the poller, check for stale transactions:

```python
expiry_cutoff = datetime.utcnow() - timedelta(hours=TRANSACTION_EXPIRY_HOURS)
expired_transactions = await session.execute(
    select(Transaction).where(
        Transaction.status == "waiting",
        Transaction.created_at < expiry_cutoff,
    )
)
for txn in expired_transactions.scalars():
    txn.status = "expired"
    # Edit Telegram message to show expired status
```

---

## 15. Security Requirements

### Secrets Management
- ✅ All secrets in `.env` (BOT_TOKEN, DATABASE_URL, CHANGENOW_API_KEY, etc.)
- ✅ `.env` is in `.gitignore` (already present in current [`.gitignore`](.gitignore))
- ✅ `.env.example` provided with placeholder values
- ✅ No hardcoded credentials anywhere

### Admin Access
- `ADMIN_IDS` loaded from env as comma-separated list
- Admin-only features (if any added later) check `message.from_user.id in ADMIN_IDS`

### Rate Limiting
- Max 1 exchange creation per `EXCHANGE_COOLDOWN_SECONDS` (default: 30s) per user
- Implementation: store `last_exchange_time` in FSM data or check DB for most recent transaction `created_at`
- Recommended approach: check DB — `SELECT created_at FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1`

### Input Sanitization
- All user text inputs are validated before use
- Addresses are passed directly to ChangeNow (they validate on their end too)
- Amount parsing uses `Decimal` (not `float`) to prevent precision issues

---

## 16. Dependencies

### Updated `requirements.txt`

```
aiogram>=3.0.0
sqlalchemy>=2.0.0
python-dotenv
asyncpg
aiohttp
gspread
google-auth
```

### Changes from Current
- **Removed:** `aiocryptopay` — no longer needed (was used for CryptoPay deposits)
- **No new dependencies** — `aiohttp` (already present) handles ChangeNow API calls
- `Decimal` and `datetime` are stdlib — no extra packages needed

---

## 17. Implementation Order

Execute in this exact order. Each step should be a complete, testable unit.

```mermaid
graph TD
    A["Step 1: config.py + .env.example"] --> B["Step 2: database.py (new schema)"]
    B --> C["Step 3: services/changenow.py"]
    C --> D["Step 4: utils/states.py"]
    D --> E["Step 5: keyboards/builders.py"]
    E --> F["Step 6: handlers/start.py"]
    F --> G["Step 7: handlers/exchange.py"]
    G --> H["Step 8: handlers/history.py"]
    H --> I["Step 9: handlers/settings.py"]
    I --> J["Step 10: utils/poller.py"]
    J --> K["Step 11: main.py (entry point)"]
    K --> L["Step 12: requirements.txt"]
    L --> M["Step 13: __init__.py files"]
```

### Step 1: `config.py` + `.env.example`
- Create config loader with all environment variables
- Create `.env.example` template
- **Test:** Import config, verify defaults work

### Step 2: `database.py`
- Rewrite with `User` (updated) and `Transaction` (new) models
- Remove `Balance` model
- Use `Numeric` instead of `Float` for financial fields
- Load `DATABASE_URL` from `config.py`
- **Test:** Run `init_db()`, verify tables created

### Step 3: `services/changenow.py`
- Implement `ChangeNowService` class with all 5 methods
- Proper error handling, logging, session management
- **Test:** Call `get_min_amount("btc", "eth", "btc", "eth")` with real API key

### Step 4: `utils/states.py`
- Define `ExchangeState` StatesGroup
- **Test:** Import succeeds

### Step 5: `keyboards/builders.py`
- Implement all keyboard builders
- Currency grid with 9 currencies in 3-column layout
- **Test:** Call each builder, verify structure

### Step 6: `handlers/start.py`
- `/start` handler with user upsert
- Google Sheets logging
- **Test:** Send /start, verify user created in DB

### Step 7: `handlers/exchange.py`
- Full FSM exchange flow (6 steps)
- Rate limiting check
- ChangeNow API integration
- Transaction creation in DB
- **Test:** Complete full exchange flow end-to-end

### Step 8: `handlers/history.py`
- Transaction history display
- **Test:** View history after creating a transaction

### Step 9: `handlers/settings.py`
- Settings menu (same as current, minimal)
- **Test:** Tap settings, verify ID shown

### Step 10: `utils/poller.py`
- Background poller implementation
- Status update logic
- Message editing
- Transaction expiry
- **Test:** Create a transaction, verify poller updates status

### Step 11: `main.py`
- Wire everything together
- Register all routers
- Start polling + background poller task
- Graceful shutdown (close ChangeNow session)
- **Test:** Bot starts, all commands work

### Step 12: `requirements.txt`
- Remove `aiocryptopay`, verify all deps listed

### Step 13: `__init__.py` files
- Create empty `__init__.py` in `services/`, `handlers/`, `keyboards/`, `utils/`

---

## 18. File-by-File Specifications

### `main.py` — Entry Point

```python
"""
Entry point for the exchange bot.
- Initializes bot, dispatcher, database, and ChangeNow service
- Registers all handler routers
- Starts polling and background poller concurrently
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, DATABASE_URL
from database import init_db, async_session
from services.changenow import ChangeNowService
from config import CHANGENOW_API_KEY, CHANGENOW_BASE_URL
from handlers import start, exchange, history, settings
from utils.poller import poll_transactions
from sheets import log_action  # keep existing

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Init
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    await init_db()
    changenow = ChangeNowService(api_key=CHANGENOW_API_KEY, base_url=CHANGENOW_BASE_URL)
    
    # Register routers
    dp.include_router(start.router)
    dp.include_router(exchange.router)
    dp.include_router(history.router)
    dp.include_router(settings.router)
    
    # Make changenow service available to handlers via bot instance or middleware
    # Option: store on bot object
    bot["changenow"] = changenow
    bot["session_factory"] = async_session
    
    # Start background poller
    poller_task = asyncio.create_task(
        poll_transactions(bot, async_session, changenow)
    )
    
    try:
        await dp.start_polling(bot)
    finally:
        poller_task.cancel()
        await changenow.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Handler Router Pattern

Each handler file uses aiogram's `Router`:

```python
# handlers/start.py
from aiogram import Router
router = Router()

@router.message(CommandStart())
async def command_start_handler(message: types.Message):
    ...
```

### Accessing Services in Handlers

Handlers access the ChangeNow service and DB session factory through the bot object:

```python
# In any handler
changenow: ChangeNowService = message.bot["changenow"]
session_factory = message.bot["session_factory"]
```

---

## Summary of Changes

| Aspect | Before (Current) | After (New) |
|--------|------------------|-------------|
| Architecture | Custodial (internal balances) | Non-custodial (ChangeNow API) |
| Exchange | Fake (modifies DB numbers) | Real (ChangeNow swap) |
| Deposits | CryptoPay + NowPayments | Not needed (user sends to ChangeNow) |
| Withdrawals | Manual (admin sends by hand) | Not needed (ChangeNow sends to user) |
| Balances | Internal DB balances | None (removed) |
| Transaction tracking | None | Full tracking with background poller |
| File structure | 1 monolithic main.py | 13+ modular files |
| Financial precision | Python float | SQLAlchemy Numeric / Python Decimal |
| Credentials | Hardcoded in source | All from .env |
| Admin ID | Hardcoded `6840070959` | From `ADMIN_IDS` env var |
| Currencies | 4 (USDT, BTC, ETH, TON) | 9 (+ SOL, LTC, XRP, TRX, USDT variants) |
| Dependencies | aiocryptopay, aiohttp, etc. | aiohttp only (for API calls) |