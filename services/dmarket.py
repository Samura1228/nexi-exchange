import aiohttp
import hashlib
import hmac
import json
import logging
import time
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

from config import DMARKET_API_KEY, DMARKET_API_SECRET, DMARKET_API_URL

logger = logging.getLogger(__name__)


class DMarketService:
    """DMarket API client for CS2 skin trading."""
    
    def __init__(self):
        self.api_key = DMARKET_API_KEY
        self.api_secret = DMARKET_API_SECRET
        self.base_url = DMARKET_API_URL
    
    def _sign_request(self, method: str, path: str, body: str = "") -> dict:
        """
        Generate DMarket API signature headers.
        
        DMarket uses HMAC-SHA256 signing:
        - String to sign: METHOD + PATH + BODY + TIMESTAMP
        - Sign with API secret (hex-encoded)
        - Headers: X-Api-Key, X-Request-Sign (dmar ed25519 SIGNATURE), X-Sign-Date
        """
        timestamp = str(int(time.time()))
        string_to_sign = method.upper() + path + body + timestamp
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "X-Api-Key": self.api_key,
            "X-Request-Sign": f"dmar ed25519 {signature}",
            "X-Sign-Date": timestamp,
            "Content-Type": "application/json",
        }
    
    async def _request(self, method: str, path: str, params: dict = None, json_data: dict = None) -> dict:
        """Generic request handler with error handling."""
        # Build full path with query params
        if params:
            query_string = urlencode(params)
            full_path = f"{path}?{query_string}"
        else:
            full_path = path
        
        body = json.dumps(json_data) if json_data else ""
        headers = self._sign_request(method, full_path, body)
        url = f"{self.base_url}{full_path}"
        
        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {"headers": headers}
                if json_data:
                    kwargs["data"] = body  # Use pre-serialized body to match signature
                
                async with session.request(method, url, **kwargs) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        text = await resp.text()
                        logger.error(f"DMarket API non-JSON response: {resp.status} - {text}")
                        return {"error": f"API error {resp.status}: {text}"}
                    
                    if resp.status not in (200, 201):
                        error_msg = data.get("message", str(data)) if isinstance(data, dict) else str(data)
                        logger.error(f"DMarket API error: {resp.status} - {error_msg}")
                        return {"error": error_msg, "status_code": resp.status}
                    return data
        except aiohttp.ClientError as e:
            logger.error(f"DMarket API connection error: {e}")
            return {"error": f"Connection error: {str(e)}"}
        except Exception as e:
            logger.error(f"DMarket API unexpected error: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    async def search_items(
        self,
        title: str = "",
        game_id: str = "a8db",  # CS2 game ID on DMarket
        limit: int = 10,
        offset: int = 0,
        order_by: str = "price",
        order_dir: str = "asc",
        price_from: int = 0,  # Price in USD cents
        price_to: int = 0,    # Price in USD cents (0 = no limit)
        currency: str = "USD",
    ) -> dict:
        """
        Search for CS2 items on DMarket marketplace.
        
        GET /exchange/v1/market/items
        
        Args:
            title: Search query (e.g., "AK-47 Redline")
            game_id: "a8db" for CS2
            limit: Number of results (max 100)
            offset: Pagination offset
            order_by: Sort field ("price", "title", "discount")
            order_dir: Sort direction ("asc", "desc")
            price_from: Min price in USD cents
            price_to: Max price in USD cents
            currency: Price currency
            
        Returns: {"objects": [...], "total": {"items": 123, ...}} or {"error": "..."}
        """
        params = {
            "side": "market",
            "orderBy": order_by,
            "orderDir": order_dir,
            "title": title,
            "priceFrom": str(price_from),
            "priceTo": str(price_to) if price_to > 0 else "",
            "treeFilters": "",
            "gameId": game_id,
            "limit": str(limit),
            "offset": str(offset),
            "currency": currency,
        }
        # Remove empty params
        params = {k: v for k, v in params.items() if v}
        
        return await self._request("GET", "/exchange/v1/market/items", params=params)
    
    async def get_item_details(self, item_id: str) -> dict:
        """
        Get details for a specific item.
        
        GET /exchange/v1/market/items/{itemId}
        """
        return await self._request("GET", f"/exchange/v1/market/items/{item_id}")
    
    async def get_balance(self) -> dict:
        """
        Get account balance.
        
        GET /account/v1/balance
        
        Returns: {"usd": "1234", "dmc": "0", ...} or {"error": "..."}
        (amounts in cents)
        """
        return await self._request("GET", "/account/v1/balance")
    
    async def buy_item(self, offer_id: str, price: dict) -> dict:
        """
        Purchase an item from the marketplace.
        
        POST /exchange/v1/offers-buy
        
        Args:
            offer_id: The offer/item ID to purchase
            price: Price dict like {"amount": "1250", "currency": "USD"} (amount in cents)
            
        Returns: Purchase result or {"error": "..."}
        """
        payload = {
            "Offers": [
                {
                    "OfferId": offer_id,
                    "Price": price,
                    "Type": "DmarketBuy",
                }
            ]
        }
        return await self._request("POST", "/exchange/v1/offers-buy", json_data=payload)
    
    async def get_user_inventory(self, game_id: str = "a8db", limit: int = 50) -> dict:
        """
        Get items in the bot's DMarket inventory (purchased but not yet withdrawn).
        
        GET /marketplace-api/v1/user-inventory
        """
        params = {
            "GameID": game_id,
            "Limit": str(limit),
            "BasicFilters.InMarket": "false",
        }
        return await self._request("GET", "/marketplace-api/v1/user-inventory", params=params)
    
    async def withdraw_to_steam(self, asset_ids: list, steam_trade_url: str) -> dict:
        """
        Withdraw items to a Steam account via trade offer.
        
        POST /marketplace-api/v1/user-targets/create
        
        Args:
            asset_ids: List of DMarket asset IDs to withdraw
            steam_trade_url: User's Steam trade URL
            
        Returns: Trade offer details or {"error": "..."}
        """
        payload = {
            "AssetID": asset_ids,
            "TradeUrl": steam_trade_url,
        }
        return await self._request("POST", "/marketplace-api/v1/withdraw-assets", json_data=payload)
    
    async def get_trade_status(self, trade_id: str) -> dict:
        """
        Get status of a withdrawal/trade.
        """
        return await self._request("GET", f"/marketplace-api/v1/user-offers/{trade_id}")
    
    def is_configured(self) -> bool:
        """Check if DMarket API credentials are configured."""
        return bool(self.api_key and self.api_secret)


# Singleton instance
dmarket = DMarketService()