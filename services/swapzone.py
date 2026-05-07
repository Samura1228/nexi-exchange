import asyncio
import json
import re
import aiohttp
import logging
from typing import Optional

from config import SWAPZONE_API_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://api.swapzone.io/v1"

# Max retries for transient errors
MAX_RETRIES = 2
RETRY_DELAY = 1.5  # seconds

# Regex pattern to detect provider-level JSON parsing errors (JavaScript-style)
_PROVIDER_ERROR_RE = re.compile(
    r"(Unexpected token .? in JSON at position \d+|"
    r"SyntaxError.*JSON|"
    r"ECONNREFUSED|ETIMEDOUT|ENOTFOUND|"
    r"socket hang up|"
    r"network error|"
    r"upstream connect error|"
    r"502 Bad Gateway|503 Service Unavailable)",
    re.IGNORECASE,
)

# User-friendly message for transient provider errors
TRANSIENT_ERROR_MSG = "Exchange rate temporarily unavailable. Please try again in a moment."

# Mapping from our internal (ticker, network) format to Swapzone currency tickers.
# Swapzone uses specific ticker strings for tokens on different networks.
CURRENCY_MAP = {
    ("btc", "btc"): "btc",
    ("eth", "eth"): "eth",
    ("sol", "sol"): "sol",
    ("ton", "ton"): "ton",
    ("usdt", "trx"): "usdttrc20",
    ("usdt", "eth"): "usdterc20",
    ("ltc", "ltc"): "ltc",
    ("xrp", "xrp"): "xrp",
    ("trx", "trx"): "trx",
}


def _get_swapzone_ticker(ticker: str, network: str) -> str:
    """Convert our internal (ticker, network) pair to Swapzone's currency identifier."""
    key = (ticker.lower(), network.lower())
    return CURRENCY_MAP.get(key, ticker.lower())


class SwapzoneService:
    def __init__(self):
        self.api_key = SWAPZONE_API_KEY
        self.headers = {"x-api-key": self.api_key}

    def _is_transient_error(self, error_msg: str) -> bool:
        """Check if an error message indicates a transient provider-level issue."""
        return bool(_PROVIDER_ERROR_RE.search(error_msg))

    def _sanitize_error(self, error_msg: str) -> str:
        """Replace technical provider errors with user-friendly messages."""
        if self._is_transient_error(error_msg):
            return TRANSIENT_ERROR_MSG
        return error_msg

    async def _request(
        self, method: str, endpoint: str, params: dict = None, json_data: dict = None, retries: int = MAX_RETRIES
    ) -> dict:
        """Generic request handler with error handling and retry logic for transient errors."""
        url = f"{BASE_URL}{endpoint}"

        for attempt in range(1, retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(method, url, headers=self.headers, params=params, json=json_data) as resp:
                        # Read raw text first for robust parsing and debugging
                        raw_text = await resp.text()

                        # Try to parse as JSON
                        try:
                            data = json.loads(raw_text)
                        except (ValueError, TypeError) as parse_err:
                            logger.error(
                                f"Swapzone API non-JSON response (attempt {attempt}/{retries}): "
                                f"status={resp.status}, body={raw_text[:500]}"
                            )
                            # If we have retries left and this looks transient, retry
                            if attempt < retries:
                                await asyncio.sleep(RETRY_DELAY)
                                continue
                            # Return user-friendly error
                            return {"error": TRANSIENT_ERROR_MSG, "_raw": raw_text[:200]}

                        # Handle non-200 status codes
                        if resp.status != 200:
                            error_msg = data.get("message", str(data)) if isinstance(data, dict) else str(data)
                            logger.error(f"Swapzone API error: {resp.status} - {error_msg}")

                            if self._is_transient_error(error_msg) and attempt < retries:
                                logger.info(f"Retrying transient error (attempt {attempt}/{retries})...")
                                await asyncio.sleep(RETRY_DELAY)
                                continue

                            return {"error": self._sanitize_error(error_msg), "status_code": resp.status}

                        # Swapzone may return {"error": true, "message": "..."} with HTTP 200
                        if isinstance(data, dict) and data.get("error") is True:
                            error_msg = data.get("message", "Unknown exchange error")
                            logger.warning(
                                f"Swapzone API returned error in body (attempt {attempt}/{retries}): {error_msg}"
                            )

                            if self._is_transient_error(error_msg) and attempt < retries:
                                logger.info(f"Retrying transient provider error (attempt {attempt}/{retries})...")
                                await asyncio.sleep(RETRY_DELAY)
                                continue

                            return {"error": self._sanitize_error(error_msg)}

                        # Validate that data is a dict (expected response format)
                        if not isinstance(data, dict):
                            logger.error(f"Swapzone API returned non-dict JSON: {type(data)} - {str(data)[:200]}")
                            if attempt < retries:
                                await asyncio.sleep(RETRY_DELAY)
                                continue
                            return {"error": TRANSIENT_ERROR_MSG}

                        return data

            except aiohttp.ClientError as e:
                logger.error(f"Swapzone API connection error (attempt {attempt}/{retries}): {e}")
                if attempt < retries:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                return {"error": self._sanitize_error(str(e))}
            except Exception as e:
                logger.error(f"Swapzone API unexpected error (attempt {attempt}/{retries}): {e}")
                if attempt < retries:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                return {"error": f"Unexpected error: {str(e)}"}

        # Should not reach here, but just in case
        return {"error": TRANSIENT_ERROR_MSG}

    async def get_estimated_amount(
        self,
        from_currency: str,
        from_network: str,
        to_currency: str,
        to_network: str,
        amount: float,
    ) -> dict:
        """
        Get estimated exchange amount and quotaId from Swapzone.
        Returns: {"estimatedAmount": float, "quotaId": str, ...} or {"error": "..."}
        """
        from_ticker = _get_swapzone_ticker(from_currency, from_network)
        to_ticker = _get_swapzone_ticker(to_currency, to_network)

        params = {
            "from": from_ticker,
            "to": to_ticker,
            "amount": str(amount),
            "rateType": "floating",
            "availableInUSA": "false",
            "chooseRate": "best",
            "noRefundAddress": "false",
        }

        data = await self._request("GET", "/exchange/get-rate", params=params)

        if "error" in data:
            return data

        # Extract relevant fields from response
        # Swapzone returns "amountTo" (not "estimatedAmount")
        estimated_amount = data.get("amountTo")
        quota_id = data.get("quotaId", "")

        if estimated_amount is None:
            logger.error(f"Swapzone get-rate response missing amountTo: {data}")
            return {"error": "Invalid response from exchange service"}

        return {
            "estimatedAmount": float(estimated_amount),
            "quotaId": quota_id,
            "minAmount": data.get("minAmount"),
            "maxAmount": data.get("maxAmount"),
            "transactionSpeedForecast": data.get("time", ""),
        }

    async def get_min_amount(
        self,
        from_currency: str,
        from_network: str,
        to_currency: str,
        to_network: str,
    ) -> dict:
        """
        Get minimum exchange amount from Swapzone.
        Uses the get-rate endpoint with a small amount to retrieve minAmount.
        Returns: {"minAmount": float, ...} or {"error": "..."}
        """
        from_ticker = _get_swapzone_ticker(from_currency, from_network)
        to_ticker = _get_swapzone_ticker(to_currency, to_network)

        params = {
            "from": from_ticker,
            "to": to_ticker,
            "amount": "100",
            "rateType": "floating",
            "availableInUSA": "false",
            "chooseRate": "best",
            "noRefundAddress": "false",
        }

        data = await self._request("GET", "/exchange/get-rate", params=params)

        if "error" in data:
            return data

        min_amount = data.get("minAmount")
        if min_amount is None:
            # If minAmount not in response, return 0 as fallback
            return {"minAmount": 0}

        return {"minAmount": float(min_amount)}

    async def create_exchange(
        self,
        from_currency: str,
        from_network: str,
        to_currency: str,
        to_network: str,
        amount: float,
        address: str,
        extra_id: str = None,
        quota_id: str = "",
        refund_address: str = "",
        refund_extra_id: str = "",
    ) -> dict:
        """
        Create an exchange transaction via Swapzone.
        Returns: {"id": str, "payinAddress": str, "payinExtraId": str, ...} or {"error": "..."}
        """
        from_ticker = _get_swapzone_ticker(from_currency, from_network)
        to_ticker = _get_swapzone_ticker(to_currency, to_network)

        payload = {
            "from": from_ticker,
            "to": to_ticker,
            "amountDeposit": str(amount),
            "addressReceive": address,
            "quotaId": quota_id,
        }

        if extra_id:
            payload["extraIdReceive"] = extra_id
        if refund_address:
            payload["refundAddress"] = refund_address
        if refund_extra_id:
            payload["refundExtraId"] = refund_extra_id

        data = await self._request("POST", "/exchange/create", json_data=payload)

        if "error" in data:
            return data

        # Swapzone wraps the result in a "transaction" object
        transaction = data.get("transaction", data)

        tx_id = transaction.get("id", "")
        deposit_address = transaction.get("addressDeposit", "")
        deposit_extra_id = transaction.get("extraIdDeposit", "")

        if not tx_id or not deposit_address:
            logger.error(f"Swapzone create exchange response missing fields: {data}")
            return {"error": "Invalid response from exchange service"}

        # Return in a format compatible with the existing handler expectations
        return {
            "id": tx_id,
            "payinAddress": deposit_address,
            "payinExtraId": deposit_extra_id or "",
        }

    async def get_transaction_status(self, transaction_id: str) -> dict:
        """
        Get transaction status by Swapzone transaction ID.
        Returns: {"status": str, "amountTo": float | None, ...} or {"error": "..."}
        
        Swapzone statuses: waiting, confirming, exchanging, sending, finished, failed, refunded, expired
        """
        params = {"id": transaction_id}
        data = await self._request("GET", "/exchange/tx", params=params)

        if "error" in data:
            return data

        # Swapzone wraps the result in a "transaction" object
        transaction = data.get("transaction", data)

        status = transaction.get("status", "").lower()
        amount_receive = transaction.get("amountReceive") or transaction.get("amountEstimated")

        result = {
            "id": transaction.get("id", transaction_id),
            "status": status,
        }

        if amount_receive is not None:
            result["amountTo"] = float(amount_receive)
        else:
            result["amountTo"] = None

        return result


# Singleton instance
swapzone = SwapzoneService()