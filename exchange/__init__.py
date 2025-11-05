"""Exchange interface and clients for Kalshi and Polymarket."""

from .base import ExchangeClient
from .clients import KalshiClient, PolymarketClient
from .models import Market, OrderBook, OrderBookEntry, MarketMetadata
from .errors import ExchangeAPIError, KalshiAPIError, PolymarketAPIError

__all__ = [
    "ExchangeClient",
    "KalshiClient",
    "PolymarketClient",
    "Market",
    "OrderBook",
    "OrderBookEntry",
    "MarketMetadata",
    "ExchangeAPIError",
    "KalshiAPIError",
    "PolymarketAPIError",
]

