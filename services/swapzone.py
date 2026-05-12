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
    ("usdt", "ton"): "usdtton",
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
    ):
        """Generic request handler with error handling and retry logic for transient errors.
        Returns dict or list depending on the API endpoint."""
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

                            result = {"error": self._sanitize_error(error_msg)}
                            # Preserve minAmount/maxAmount from error responses (useful for user feedback)
                            if data.get("minAmount") is not None:
                                result["minAmount"] = data["minAmount"]
                            if data.get("maxAmount") is not None:
                                result["maxAmount"] = data["maxAmount"]
                            return result

                        # Accept both dict and list responses (list for chooseRate=all)
                        if isinstance(data, (dict, list)):
                            return data

                        logger.error(f"Swapzone API returned unexpected JSON type: {type(data)} - {str(data)[:200]}")
                        if attempt < retries:
                            await asyncio.sleep(RETRY_DELAY)
                            continue
                        return {"error": TRANSIENT_ERROR_MSG}

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
        Uses chooseRate=all to fetch ALL providers, then picks the best one
        that actually supports the given amount (amount >= provider minAmount).
        This avoids the mismatch where get_min_amount shows the lowest min across
        all providers but chooseRate=best picks a provider with a higher min.
        Returns: {"estimatedAmount": float, "quotaId": str, ...} or {"error": "..."}
        """
        from_ticker = _get_swapzone_ticker(from_currency, from_network)
        to_ticker = _get_swapzone_ticker(to_currency, to_network)

        # Use chooseRate=all to get ALL providers and pick the best one that supports our amount
        params = {
            "from": from_ticker,
            "to": to_ticker,
            "amount": str(amount),
            "rateType": "floating",
            "availableInUSA": "false",
            "chooseRate": "all",
            "noRefundAddress": "false",
        }

        data = await self._request("GET", "/exchange/get-rate", params=params)

        # If the response is a list (chooseRate=all), pick the best provider for this amount
        if isinstance(data, list) and len(data) > 0:
            # Filter providers where the amount meets their minimum
            eligible = []
            for provider in data:
                provider_min = provider.get("minAmount")
                provider_max = provider.get("maxAmount")
                provider_amount_to = provider.get("amountTo")

                # Skip providers without a valid amountTo
                if provider_amount_to is None or float(provider_amount_to) <= 0:
                    continue

                # Check minimum
                if provider_min is not None and float(provider_min) > 0 and amount < float(provider_min):
                    continue

                # Check maximum
                if provider_max is not None and float(provider_max) > 0 and amount > float(provider_max):
                    continue

                eligible.append(provider)

            if not eligible:
                # No provider supports this amount — find the actual lowest minimum to inform the user
                all_mins = []
                for provider in data:
                    provider_min = provider.get("minAmount")
                    if provider_min is not None and float(provider_min) > 0:
                        all_mins.append(float(provider_min))
                if all_mins:
                    actual_min = min(all_mins)
                    logger.warning(
                        f"No provider supports amount {amount} for {from_ticker}->{to_ticker}. "
                        f"Lowest provider min: {actual_min}"
                    )
                    return {"error": f"Minimum amount for this pair is {actual_min:.2f}", "minAmount": actual_min}
                return {"error": "No providers available for this exchange pair"}

            # Pick the provider with the highest amountTo (best rate for the user)
            best = max(eligible, key=lambda p: float(p.get("amountTo", 0)))
            logger.info(
                f"Swapzone get_estimated_amount: picked provider '{best.get('adapter')}' "
                f"(amountTo={best.get('amountTo')}) from {len(eligible)} eligible / {len(data)} total providers"
            )

            return {
                "estimatedAmount": float(best["amountTo"]),
                "quotaId": best.get("quotaId", ""),
                "minAmount": best.get("minAmount"),
                "maxAmount": best.get("maxAmount"),
                "transactionSpeedForecast": best.get("time", ""),
            }

        # If the response is a dict with an error, try fallback
        if isinstance(data, dict) and "error" in data:
            # Save minAmount from first error response for better error messaging
            first_error_min = data.get("minAmount")

            # Fallback: try with noRefundAddress=true
            logger.info("get_estimated_amount: retrying with noRefundAddress=true")
            params["noRefundAddress"] = "true"
            fallback_data = await self._request("GET", "/exchange/get-rate", params=params)

            if isinstance(fallback_data, list) and len(fallback_data) > 0:
                # Same filtering logic for fallback
                eligible = []
                for provider in fallback_data:
                    provider_min = provider.get("minAmount")
                    provider_max = provider.get("maxAmount")
                    provider_amount_to = provider.get("amountTo")
                    if provider_amount_to is None or float(provider_amount_to) <= 0:
                        continue
                    if provider_min is not None and float(provider_min) > 0 and amount < float(provider_min):
                        continue
                    if provider_max is not None and float(provider_max) > 0 and amount > float(provider_max):
                        continue
                    eligible.append(provider)

                if not eligible:
                    return {"error": "No providers available for this amount"}

                best = max(eligible, key=lambda p: float(p.get("amountTo", 0)))
                return {
                    "estimatedAmount": float(best["amountTo"]),
                    "quotaId": best.get("quotaId", ""),
                    "minAmount": best.get("minAmount"),
                    "maxAmount": best.get("maxAmount"),
                    "transactionSpeedForecast": best.get("time", ""),
                }

            # Fallback also failed — return error with minAmount if available
            if isinstance(fallback_data, dict) and "error" in fallback_data:
                error_result = fallback_data
                # Prefer minAmount from first error if fallback doesn't have one
                if first_error_min is not None and "minAmount" not in error_result:
                    error_result["minAmount"] = first_error_min
                return error_result

            # Return original error with minAmount preserved
            return data

        # Fallback: handle single dict response (shouldn't happen with chooseRate=all, but be safe)
        if isinstance(data, dict):
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

        logger.error(f"Swapzone get_estimated_amount: unexpected response type: {type(data)}")
        return {"error": "Invalid response from exchange service"}

    async def get_min_amount(
        self,
        from_currency: str,
        from_network: str,
        to_currency: str,
        to_network: str,
    ) -> dict:
        """
        Get minimum exchange amount from Swapzone.
        Uses the get-rate endpoint with chooseRate=all to find the lowest minAmount
        across all available providers.
        Returns: {"minAmount": float, ...} or {"error": "..."}
        """
        from_ticker = _get_swapzone_ticker(from_currency, from_network)
        to_ticker = _get_swapzone_ticker(to_currency, to_network)

        # Use chooseRate=all and noRefundAddress=false to get ALL providers and find lowest min
        params = {
            "from": from_ticker,
            "to": to_ticker,
            "amount": "100",
            "rateType": "floating",
            "availableInUSA": "false",
            "chooseRate": "all",
            "noRefundAddress": "false",
        }

        data = await self._request("GET", "/exchange/get-rate", params=params)

        if "error" in data:
            return data

        # When chooseRate=all, response is a list of providers
        if isinstance(data, list) and len(data) > 0:
            # Find the lowest minAmount across all providers
            min_amounts = []
            for provider in data:
                provider_min = provider.get("minAmount")
                if provider_min is not None and float(provider_min) > 0:
                    min_amounts.append(float(provider_min))
            if min_amounts:
                return {"minAmount": min(min_amounts)}
            # If no valid minAmount found in list, return 0
            return {"minAmount": 0}

        # Fallback: single response (shouldn't happen with chooseRate=all, but handle gracefully)
        if isinstance(data, dict):
            min_amount = data.get("minAmount")
            if min_amount is None:
                return {"minAmount": 0}
            return {"minAmount": float(min_amount)}

        return {"minAmount": 0}

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
        If creation fails (e.g. provider requires refund address), retries with
        a new quote from a provider that supports noRefundAddress.
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
            "noRefundAddress": True,
        }

        if extra_id:
            payload["extraIdReceive"] = extra_id
        if refund_address:
            # If a refund address is provided, use it and disable noRefundAddress flag
            payload["refundAddress"] = refund_address
            payload["noRefundAddress"] = False
        if refund_extra_id:
            payload["refundExtraId"] = refund_extra_id

        logger.info(f"Swapzone create_exchange payload: from={from_ticker}, to={to_ticker}, amount={amount}, quotaId={quota_id[:16]}...")
        data = await self._request("POST", "/exchange/create", json_data=payload)

        if "error" in data:
            first_error = data.get("error", "")
            logger.warning(f"Swapzone create_exchange first attempt failed: {first_error}")

            # Fallback: get a new quote with noRefundAddress=true and retry
            logger.info("create_exchange: retrying with noRefundAddress=true provider...")
            fallback_params = {
                "from": from_ticker,
                "to": to_ticker,
                "amount": str(amount),
                "rateType": "floating",
                "availableInUSA": "false",
                "chooseRate": "best",
                "noRefundAddress": "true",
            }
            fallback_rate = await self._request("GET", "/exchange/get-rate", params=fallback_params)

            if isinstance(fallback_rate, dict) and "error" not in fallback_rate:
                new_quota_id = fallback_rate.get("quotaId", "")
                if new_quota_id:
                    payload["quotaId"] = new_quota_id
                    logger.info(f"Swapzone create_exchange retry with new quotaId from noRefundAddress=true provider")
                    data = await self._request("POST", "/exchange/create", json_data=payload)
                    if "error" in data:
                        logger.error(f"Swapzone create_exchange retry also failed: {data}")
                        return data
                else:
                    return {"error": first_error}
            else:
                # Fallback rate fetch also failed, return original error
                return {"error": first_error}

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