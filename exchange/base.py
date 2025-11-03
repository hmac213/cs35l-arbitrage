"""Abstract base class for exchange clients."""

from abc import ABC, abstractmethod
from typing import List

from .models import Market, OrderBook


class ExchangeClient(ABC):
    """Abstract interface for exchange clients.
    
    All exchange implementations must inherit from this class and implement
    the required methods for fetching markets, orderbooks, and market details.
    """

    @abstractmethod
    def fetch_all_markets(self) -> List[Market]:
        """Retrieve all markets from the exchange.
        
        Returns:
            List[Market]: A list of all available markets on the exchange.
            
        Raises:
            APIError: If the API request fails.
        """
        pass

    @abstractmethod
    def fetch_orderbook(self, market_id: str) -> OrderBook:
        """Get the full order book for a specific market.
        
        Args:
            market_id: The unique identifier for the market.
            
        Returns:
            OrderBook: The full order book containing bids and asks.
            
        Raises:
            APIError: If the API request fails.
            MarketNotFoundError: If the market_id doesn't exist.
        """
        pass

    @abstractmethod
    def fetch_market_details(self, market_id: str) -> Market:
        """Get market rules, name, and all associated metadata.
        
        Args:
            market_id: The unique identifier for the market.
            
        Returns:
            Market: Complete market information including rules, name, 
                   resolve date/time, and all metadata.
                   
        Raises:
            APIError: If the API request fails.
            MarketNotFoundError: If the market_id doesn't exist.
        """
        pass

