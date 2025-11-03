"""Kalshi exchange client implementation using Dome API."""

from typing import List
from datetime import datetime

from ..base import ExchangeClient
from ..models import Market, OrderBook, OrderBookEntry, MarketMetadata
from ..dome_api import DomeAPIClient, DomeAPIError


class KalshiClient(ExchangeClient):
    """Client for interacting with Kalshi exchange via Dome API.
    
    This client implements the ExchangeClient interface and uses Dome API
    to fetch markets, orderbooks, and market details from Kalshi.
    """
    
    def __init__(self, dome_api_key: str, dome_base_url: str = "http://api.domeapi.io"):
        """Initialize the Kalshi client.
        
        Args:
            dome_api_key: Your Dome API key for authentication.
            dome_base_url: Base URL for Dome API (default: http://api.domeapi.io).
        """
        self.dome_client = DomeAPIClient(dome_api_key, dome_base_url)
        self.exchange_name = "kalshi"

    def fetch_all_markets(self) -> List[Market]:
        """Retrieve all markets from Kalshi.
        
        Uses Dome API to fetch all available markets. The response is normalized
        to the common Market model.
        
        Returns:
            List[Market]: A list of all available markets.
            
        Raises:
            DomeAPIError: If the API request fails.
        """
        try:
            response = self.dome_client.get_kalshi_markets()
            markets = []
            
            # Handle different possible response structures
            # Dome API might return data directly or nested in a 'data' or 'markets' key
            market_data = response
            if isinstance(response, dict):
                if 'data' in response:
                    market_data = response['data']
                elif 'markets' in response:
                    market_data = response['markets']
                elif 'results' in response:
                    market_data = response['results']
            
            # If market_data is a list, iterate through it
            if isinstance(market_data, list):
                for market_raw in market_data:
                    market = self._normalize_market(market_raw)
                    if market:
                        markets.append(market)
            elif isinstance(market_data, dict) and 'items' in market_data:
                # Handle paginated responses
                for market_raw in market_data['items']:
                    market = self._normalize_market(market_raw)
                    if market:
                        markets.append(market)
            
            return markets
        except DomeAPIError:
            raise
        except Exception as e:
            raise DomeAPIError(f"Failed to fetch Kalshi markets: {str(e)}") from e

    def fetch_orderbook(self, market_id: str) -> OrderBook:
        """Get the full order book for a specific Kalshi market.
        
        Args:
            market_id: The Kalshi market identifier (e.g., ticker symbol).
            
        Returns:
            OrderBook: The full order book with bids and asks.
            
        Raises:
            DomeAPIError: If the API request fails.
        """
        try:
            response = self.dome_client.get_kalshi_orderbook(market_id)
            
            # Normalize the response to OrderBook model
            return self._normalize_orderbook(market_id, response)
        except DomeAPIError:
            raise
        except Exception as e:
            raise DomeAPIError(f"Failed to fetch Kalshi orderbook for {market_id}: {str(e)}") from e

    def fetch_market_details(self, market_id: str) -> Market:
        """Get market rules, name, and all associated metadata.
        
        Args:
            market_id: The Kalshi market identifier.
            
        Returns:
            Market: Complete market information.
            
        Raises:
            DomeAPIError: If the API request fails.
        """
        try:
            response = self.dome_client.get_kalshi_market_details(market_id)
            
            # Handle nested response structure
            market_data = response
            if isinstance(response, dict) and 'data' in response:
                market_data = response['data']
            
            return self._normalize_market(market_data)
        except DomeAPIError:
            raise
        except Exception as e:
            raise DomeAPIError(f"Failed to fetch Kalshi market details for {market_id}: {str(e)}") from e

    def _normalize_market(self, market_data: dict) -> Market:
        """Normalize Kalshi market data to the common Market model.
        
        Args:
            market_data: Raw market data from Kalshi API.
            
        Returns:
            Market: Normalized market object.
        """
        # Extract market ID - could be 'ticker', 'event_ticker', 'market_id', etc.
        market_id = (
            market_data.get('ticker') or
            market_data.get('event_ticker') or
            market_data.get('market_id') or
            market_data.get('id') or
            str(market_data.get('event_id', ''))
        )
        
        # Extract market name
        name = (
            market_data.get('title') or
            market_data.get('name') or
            market_data.get('event_title') or
            market_data.get('question') or
            ''
        )
        
        # Extract rules
        rules = (
            market_data.get('rules') or
            market_data.get('subtitle') or
            market_data.get('description') or
            ''
        )
        
        # Extract metadata
        metadata = MarketMetadata(
            resolve_date=market_data.get('expected_expiration_time') or market_data.get('expiration_time') or market_data.get('resolve_date'),
            resolve_time=market_data.get('expected_expiration_time') or market_data.get('expiration_time') or market_data.get('resolve_time'),
            category=market_data.get('category') or market_data.get('series_ticker'),
            subcategory=market_data.get('subcategory'),
            tags=market_data.get('tags') or market_data.get('keywords'),
            description=market_data.get('description') or market_data.get('subtitle'),
            image_url=market_data.get('image_url') or market_data.get('image'),
            liquidity=market_data.get('liquidity'),
            volume=market_data.get('volume') or market_data.get('total_volume'),
            extra={
                'status': market_data.get('status'),
                'yes_bid': market_data.get('yes_bid'),
                'yes_ask': market_data.get('yes_ask'),
                'no_bid': market_data.get('no_bid'),
                'no_ask': market_data.get('no_ask'),
                'last_price': market_data.get('last_price'),
                'previous_price': market_data.get('previous_price'),
            }
        )
        
        return Market(
            market_id=str(market_id),
            name=name,
            rules=rules,
            metadata=metadata,
            exchange=self.exchange_name,
            extra=market_data
        )

    def _normalize_orderbook(self, market_id: str, orderbook_data: dict) -> OrderBook:
        """Normalize Kalshi orderbook data to the common OrderBook model.
        
        Args:
            market_id: The market identifier.
            orderbook_data: Raw orderbook data from Kalshi API.
            
        Returns:
            OrderBook: Normalized orderbook object.
        """
        # Handle nested response structure
        data = orderbook_data
        if isinstance(orderbook_data, dict) and 'data' in orderbook_data:
            data = orderbook_data['data']
        
        bids = []
        asks = []
        
        # Kalshi typically has 'yes' and 'no' sides, or 'bids' and 'asks'
        if 'yes' in data and 'no' in data:
            # Binary market with yes/no sides
            yes_bids = data.get('yes', {}).get('bids', [])
            yes_asks = data.get('yes', {}).get('asks', [])
            no_bids = data.get('no', {}).get('bids', [])
            no_asks = data.get('no', {}).get('asks', [])
            
            # Convert yes/no to standard bids/asks
            # Yes bids are bids, Yes asks are asks
            # No bids are asks (betting against), No asks are bids
            for bid in yes_bids:
                price = float(bid.get('price', bid.get('yes_price', 0)))
                quantity = float(bid.get('quantity', bid.get('size', 0)))
                bids.append(OrderBookEntry(price=price, quantity=quantity, metadata=bid))
            
            for ask in yes_asks:
                price = float(ask.get('price', ask.get('yes_price', 0)))
                quantity = float(ask.get('quantity', ask.get('size', 0)))
                asks.append(OrderBookEntry(price=price, quantity=quantity, metadata=ask))
            
            # Add no side orders (inverted)
            for bid in no_bids:
                price = 1.0 - float(bid.get('price', bid.get('no_price', 0)))
                quantity = float(bid.get('quantity', bid.get('size', 0)))
                asks.append(OrderBookEntry(price=price, quantity=quantity, metadata=bid))
            
            for ask in no_asks:
                price = 1.0 - float(ask.get('price', ask.get('no_price', 0)))
                quantity = float(ask.get('quantity', ask.get('size', 0)))
                bids.append(OrderBookEntry(price=price, quantity=quantity, metadata=ask))
        else:
            # Standard bids/asks structure
            raw_bids = data.get('bids', [])
            raw_asks = data.get('asks', [])
            
            for bid in raw_bids:
                price = float(bid.get('price', 0))
                quantity = float(bid.get('quantity', bid.get('size', 0)))
                bids.append(OrderBookEntry(price=price, quantity=quantity, metadata=bid))
            
            for ask in raw_asks:
                price = float(ask.get('price', 0))
                quantity = float(ask.get('quantity', ask.get('size', 0)))
                asks.append(OrderBookEntry(price=price, quantity=quantity, metadata=ask))
        
        # Sort bids descending (best bid first) and asks ascending (best ask first)
        bids.sort(key=lambda x: x.price, reverse=True)
        asks.sort(key=lambda x: x.price)
        
        # Extract timestamp if available
        timestamp = None
        if 'timestamp' in data:
            try:
                timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        
        return OrderBook(
            market_id=str(market_id),
            bids=bids,
            asks=asks,
            timestamp=timestamp,
            metadata=orderbook_data
        )

