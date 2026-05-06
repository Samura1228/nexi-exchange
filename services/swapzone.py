import aiohttp
import logging
from typing import Optional

from config import SWAPZONE_API_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://api.swapzone.io/v1"

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

    async def _request(self, method: str, endpoint: str, params: dict = None, json_data: dict = None) -> dict:
        """Generic request handler with error handling."""
        url = f"{BASE_URL}{endpoint}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=self.headers, params=params, json=json_data) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        text = await resp.text()
                        logger.error(f"Swapzone API non-JSON response: {resp.status} - {text}")
                        return {"error": f"API error {resp.status}: {text}"}

                    if resp.status != 200:
                        error_msg = data.get("message", str(data)) if isinstance(data, dict) else str(data)
                        logger.error(f"Swapzone API error: {resp.status} - {error_msg}")
                        return {"error": error_msg, "status_code": resp.status}
                    return data
        except aiohttp.ClientError as e:
            logger.error(f"Swapzone API connection error: {e}")
            return {"error": f"Connection error: {str(e)}"}
        except Exception as e:
            logger.error(f"Swapzone API unexpected error: {e}")
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
        estimated_amount = data.get("estimatedAmount")
        quota_id = data.get("quotaId", "")

        if estimated_amount is None:
            logger.error(f"Swapzone get-rate response missing estimatedAmount: {data}")
            return {"error": "Invalid response from exchange service"}

        return {
            "estimatedAmount": float(estimated_amount),
            "quotaId": quota_id,
            "minAmount": data.get("minAmount"),
            "maxAmount": data.get("maxAmount"),
            "transactionSpeedForecast": data.get("transactionSpeedForecast", ""),
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
            "amount": "1",
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