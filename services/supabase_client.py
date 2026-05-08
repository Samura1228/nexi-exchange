"""
Supabase client for admin dashboard / analytics logging.

Run this SQL in Supabase SQL Editor to create the dashboard tables:

-- ============================================================
-- Run this in Supabase SQL Editor to create the dashboard tables
-- ============================================================

CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    username TEXT DEFAULT '',
    details TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE exchanges (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    from_currency TEXT NOT NULL,
    to_currency TEXT NOT NULL,
    amount_from NUMERIC(28,18),
    amount_to NUMERIC(28,18),
    status TEXT DEFAULT 'created',
    tx_id TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE users_dashboard (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    username TEXT DEFAULT '',
    language TEXT DEFAULT 'en',
    referred_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for fast queries
CREATE INDEX idx_events_user_id ON events(user_id);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_exchanges_user_id ON exchanges(user_id);
CREATE INDEX idx_exchanges_status ON exchanges(status);

-- ============================================================
"""

import aiohttp
import logging
from datetime import datetime
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Async Supabase REST API client for logging events and syncing data."""

    def __init__(self):
        self.url = SUPABASE_URL
        self.key = SUPABASE_KEY
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

    async def _post(self, table: str, data: dict) -> bool:
        """Insert a row into a Supabase table."""
        if not self.url or not self.key:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.url}/rest/v1/{table}"
                async with session.post(url, json=data, headers=self.headers) as resp:
                    if resp.status in (200, 201):
                        return True
                    else:
                        text = await resp.text()
                        logger.error(f"Supabase insert to {table} failed: {resp.status} {text}")
                        return False
        except Exception as e:
            logger.error(f"Supabase error: {e}")
            return False

    async def log_event(self, event_type: str, user_id: int, username: str = "", details: str = ""):
        """Log an event to the 'events' table."""
        await self._post("events", {
            "event_type": event_type,
            "user_id": user_id,
            "username": username or "",
            "details": details,
            "created_at": datetime.utcnow().isoformat()
        })

    async def log_exchange(self, user_id: int, from_currency: str, to_currency: str,
                           amount_from: float, amount_to: float, status: str, tx_id: str = ""):
        """Log an exchange to the 'exchanges' table."""
        await self._post("exchanges", {
            "user_id": user_id,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "amount_from": round(float(amount_from), 10),
            "amount_to": round(float(amount_to), 10),
            "status": status,
            "tx_id": tx_id,
            "created_at": datetime.utcnow().isoformat()
        })

    async def update_exchange_status(self, tx_id: str, status: str, amount_to: float = None) -> bool:
        """Update an exchange's status in Supabase by tx_id."""
        if not self.url or not self.key:
            return False
        data = {"status": status}
        if amount_to is not None:
            data["amount_to"] = round(float(amount_to), 10)
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.url}/rest/v1/exchanges?tx_id=eq.{tx_id}"
                headers = {**self.headers, "Prefer": "return=minimal"}
                async with session.patch(url, json=data, headers=headers) as resp:
                    if resp.status in (200, 204):
                        return True
                    else:
                        text = await resp.text()
                        logger.error(f"Supabase update for {tx_id} failed: {resp.status} {text}")
                        return False
        except Exception as e:
            logger.error(f"Supabase update error: {e}")
            return False

    async def log_user(self, user_id: int, username: str = "", language: str = "en",
                       referred_by: int = None):
        """Log/upsert a user to the 'users_dashboard' table."""
        data = {
            "user_id": user_id,
            "username": username or "",
            "language": language,
            "created_at": datetime.utcnow().isoformat()
        }
        if referred_by:
            data["referred_by"] = referred_by
        await self._post("users_dashboard", data)


supabase = SupabaseClient()