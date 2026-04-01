import aiohttp
import logging
from typing import Optional
from config import CHANGENOW_API_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://api.changenow.io/v2"


class ChangeNowService:
    def __init__(self):
        self.api_key = CHANGENOW_API_KEY
        self.headers = {"x-changenow-api-key": self.api_key}

    async def _request(self, method: str, endpoint: str, params: dict = None, json_data: dict = None) -> dict:
        """Generic request handler with error handling."""
        url = f"{BASE_URL}{endpoint}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=self.headers, params=params, json=json_data) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        logger.error(f"ChangeNow API error: {resp.status} - {data}")
                        return {"error": data.get("message", f"API error {resp.status}"), "status_code": resp.status}
                    return data
        except aiohttp.ClientError as e:
            logger.error(f"ChangeNow API connection error: {e}")
            return {"error": f"Connection error: {str(e)}"}
        except Exception as e:
            logger.error(f"ChangeNow API unexpected error: {e}")
            return {"error": f"Unexpected error: {str(e)}"}

    async def get_estimated_amount(
        self,
        from_currency: str,
        from_network: str,
        to_currency: str,
        to_network: str,
        amount: float,
    ) -> dict:
        """
        Get estimated exchange amount.
        GET /exchange/estimated-amount
        Returns: {"estimatedAmount": 1.234, "transactionSpeedForecast": "10-60", ...} or {"error": "..."}
        """
        params = {
            "fromCurrency": from_currency,
            "toCurrency": to_currency,
            "fromAmount": str(amount),
            "fromNetwork": from_network,
            "toNetwork": to_network,
            "flow": "standard",
            "type": "direct",
        }
        return await self._request("GET", "/exchange/estimated-amount", params=params)

    async def get_min_amount(
        self,
        from_currency: str,
        from_network: str,
        to_currency: str,
        to_network: str,
    ) -> dict:
        """
        Get minimum exchange amount.
        GET /exchange/min-amount
        Returns: {"minAmount": 0.001, ...} or {"error": "..."}
        """
        params = {
            "fromCurrency": from_currency,
            "toCurrency": to_currency,
            "fromNetwork": from_network,
            "toNetwork": to_network,
            "flow": "standard",
        }
        return await self._request("GET", "/exchange/min-amount", params=params)

    async def create_exchange(
        self,
        from_currency: str,
        from_network: str,
        to_currency: str,
        to_network: str,
        amount: float,
        address: str,
        extra_id: str = None,
    ) -> dict:
        """
        Create an exchange transaction.
        POST /exchange
        Returns: {"id": "abc123", "payinAddress": "bc1q...", "payoutAddress": "0x...", ...} or {"error": "..."}
        """
        payload = {
            "fromCurrency": from_currency,
            "toCurrency": to_currency,
            "fromAmount": str(amount),
            "address": address,
            "fromNetwork": from_network,
            "toNetwork": to_network,
            "flow": "standard",
            "type": "direct",
        }
        if extra_id:
            payload["extraId"] = extra_id
        return await self._request("POST", "/exchange", json_data=payload)

    async def get_transaction_status(self, transaction_id: str) -> dict:
        """
        Get transaction status by ChangeNow ID.
        GET /exchange/by-id/{id}
        Returns: {"id": "abc123", "status": "waiting", "payinHash": "...", "payoutHash": "...", "amountTo": 1.5, ...} or {"error": "..."}
        """
        return await self._request("GET", f"/exchange/by-id/{transaction_id}")

    async def get_currencies(self) -> dict:
        """
        Get list of available currencies.
        GET /exchange/currencies?active=true
        Returns: list of currency objects or {"error": "..."}
        """
        return await self._request("GET", "/exchange/currencies", params={"active": "true"})


# Singleton instance
changenow = ChangeNowService()