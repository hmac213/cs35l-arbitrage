"""Exchange-specific error classes."""


class ExchangeAPIError(Exception):
    """Base exception for all exchange API errors."""
    pass


class KalshiAPIError(ExchangeAPIError):
    """Exception raised for Kalshi API errors."""
    pass


class PolymarketAPIError(ExchangeAPIError):
    """Exception raised for Polymarket API errors."""
    pass

