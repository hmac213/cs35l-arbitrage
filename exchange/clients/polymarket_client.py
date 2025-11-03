"""Polymarket exchange client implementation using Dome API."""

from typing import List
from datetime import datetime

from ..base import ExchangeClient
from ..models import Market, OrderBook, OrderBookEntry, MarketMetadata
from ..dome_api import DomeAPIClient, DomeAPIError


class PolymarketClient(ExchangeClient):
    """Client for interacting with Polymarket exchange via Dome API.
    
    This client implements the ExchangeClient interface and uses Dome API
    to fetch markets, orderbooks, and market details from Polymarket.
    """
    
    def __init__(self, dome_api_key: str, dome_base_url: str = "http://api.domeapi.io"):
        """Initialize the Polymarket client.
        
        Args:
            dome_api_key: Your Dome API key for authentication.
            dome_base_url: Base URL for Dome API (default: http://api.domeapi.io).
        """
        self.dome_client = DomeAPIClient(dome_api_key, dome_base_url)
        self.exchange_name = "polymarket"

    def fetch_all_markets(self) -> List[Market]:
        """Retrieve all markets from Polymarket.
        
        Uses Dome API to fetch all available markets. The response is normalized
        to the common Market model.
        
        Returns:
            List[Market]: A list of all available markets.
            
        Raises:
            DomeAPIError: If the API request fails.
        """
        try:
            response = self.dome_client.get_polymarket_markets()
            markets = []
            
            # Handle different possible response structures
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
            elif isinstance(market_data, dict):
                # Handle paginated responses or nested structures
                if 'items' in market_data:
                    for market_raw in market_data['items']:
                        market = self._normalize_market(market_raw)
                        if market:
                            markets.append(market)
                elif 'data' in market_data:
                    for market_raw in market_data['data']:
                        market = self._normalize_market(market_raw)
                        if market:
                            markets.append(market)
            
            return markets
        except DomeAPIError:
            raise
        except Exception as e:
            raise DomeAPIError(f"Failed to fetch Polymarket markets: {str(e)}") from e

    def fetch_orderbook(self, market_id: str) -> OrderBook:
        """Get the full order book for a specific Polymarket market.
        
        Args:
            market_id: The Polymarket market identifier (token_id or condition_id).
            
        Returns:
            OrderBook: The full order book with bids and asks.
            
        Raises:
            DomeAPIError: If the API request fails.
        """
        try:
            response = self.dome_client.get_polymarket_orderbook(market_id)
            
            # Normalize the response to OrderBook model
            return self._normalize_orderbook(market_id, response)
        except DomeAPIError:
            raise
        except Exception as e:
            raise DomeAPIError(f"Failed to fetch Polymarket orderbook for {market_id}: {str(e)}") from e

    def fetch_market_details(self, market_id: str) -> Market:
        """Get market rules, name, and all associated metadata.
        
        Args:
            market_id: The Polymarket market identifier (token_id or condition_id).
            
        Returns:
            Market: Complete market information.
            
        Raises:
            DomeAPIError: If the API request fails.
        """
        try:
            response = self.dome_client.get_polymarket_market_details(market_id)
            
            # Handle nested response structure
            market_data = response
            if isinstance(response, dict) and 'data' in response:
                market_data = response['data']
            
            return self._normalize_market(market_data)
        except DomeAPIError:
            raise
        except Exception as e:
            raise DomeAPIError(f"Failed to fetch Polymarket market details for {market_id}: {str(e)}") from e

    def _normalize_market(self, market_data: dict) -> Market:
        """Normalize Polymarket market data to the common Market model.
        
        Args:
            market_data: Raw market data from Polymarket API.
            
        Returns:
            Market: Normalized market object.
        """
        # Extract market ID - could be 'slug', 'condition_id', 'token_id', 'id', etc.
        market_id = (
            market_data.get('slug') or
            market_data.get('condition_id') or
            market_data.get('token_id') or
            market_data.get('id') or
            market_data.get('market_id') or
            ''
        )
        
        # Extract market name
        name = (
            market_data.get('question') or
            market_data.get('title') or
            market_data.get('name') or
            market_data.get('market_title') or
            ''
        )
        
        # Extract rules/description
        rules = (
            market_data.get('description') or
            market_data.get('rules') or
            market_data.get('resolution_rules') or
            market_data.get('subtitle') or
            ''
        )
        
        # Extract resolution date/time
        resolve_date = None
        resolve_time = None
        resolution_date = market_data.get('resolution_date') or market_data.get('end_date')
        if resolution_date:
            try:
                # Try to parse the date
                if isinstance(resolution_date, str):
                    # Handle ISO format or other formats
                    dt = datetime.fromisoformat(resolution_date.replace('Z', '+00:00'))
                    resolve_date = dt.strftime('%Y-%m-%d')
                    resolve_time = dt.strftime('%H:%M:%S')
                elif isinstance(resolution_date, (int, float)):
                    # Unix timestamp
                    dt = datetime.fromtimestamp(resolution_date)
                    resolve_date = dt.strftime('%Y-%m-%d')
                    resolve_time = dt.strftime('%H:%M:%S')
            except (ValueError, TypeError, OSError):
                resolve_date = str(resolution_date)
        
        # Extract metadata
        metadata = MarketMetadata(
            resolve_date=resolve_date,
            resolve_time=resolve_time,
            category=market_data.get('category') or market_data.get('group_item_title'),
            subcategory=market_data.get('subcategory'),
            tags=market_data.get('tags') or market_data.get('keywords'),
            description=market_data.get('description') or market_data.get('subtitle'),
            image_url=market_data.get('image_url') or market_data.get('image'),
            liquidity=market_data.get('liquidity') or market_data.get('liquidity_usd'),
            volume=market_data.get('volume') or market_data.get('volume_usd') or market_data.get('total_volume'),
            extra={
                'outcomes': market_data.get('outcomes'),
                'active': market_data.get('active'),
                'closed': market_data.get('closed'),
                'new': market_data.get('new'),
                'end_date_iso': market_data.get('end_date_iso'),
                'start_date_iso': market_data.get('start_date_iso'),
                'clob_token_ids': market_data.get('clob_token_ids'),
                'condition_id': market_data.get('condition_id'),
                'token_id': market_data.get('token_id'),
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
        """Normalize Polymarket orderbook data to the common OrderBook model.
        
        Args:
            market_id: The market identifier.
            orderbook_data: Raw orderbook data from Polymarket API.
            
        Returns:
            OrderBook: Normalized orderbook object.
        """
        # Handle nested response structure
        data = orderbook_data
        if isinstance(orderbook_data, dict) and 'data' in orderbook_data:
            data = orderbook_data['data']
        
        bids = []
        asks = []
        
        # Polymarket typically has 'bids' and 'asks' arrays
        # Each entry might have 'price', 'size', 'maker', 'timestamp', etc.
        raw_bids = data.get('bids', [])
        raw_asks = data.get('asks', [])
        
        # If the structure is different, try alternative keys
        if not raw_bids and 'buy' in data:
            raw_bids = data.get('buy', [])
        if not raw_asks and 'sell' in data:
            raw_asks = data.get('sell', [])
        
        # Process bids
        for bid in raw_bids:
            # Polymarket prices are typically in decimal format (0-1 for binary markets)
            price = float(bid.get('price', bid.get('px', 0)))
            quantity = float(bid.get('size', bid.get('quantity', bid.get('qty', 0))))
            
            bid_metadata = {
                'maker': bid.get('maker'),
                'timestamp': bid.get('timestamp'),
                'order_id': bid.get('order_id'),
            }
            # Include all original fields
            bid_metadata.update({k: v for k, v in bid.items() if k not in ['price', 'px', 'size', 'quantity', 'qty']})
            
            bids.append(OrderBookEntry(price=price, quantity=quantity, metadata=bid_metadata))
        
        # Process asks
        for ask in raw_asks:
            price = float(ask.get('price', ask.get('px', 0)))
            quantity = float(ask.get('size', ask.get('quantity', ask.get('qty', 0))))
            
            ask_metadata = {
                'maker': ask.get('maker'),
                'timestamp': ask.get('timestamp'),
                'order_id': ask.get('order_id'),
            }
            # Include all original fields
            ask_metadata.update({k: v for k, v in ask.items() if k not in ['price', 'px', 'size', 'quantity', 'qty']})
            
            asks.append(OrderBookEntry(price=price, quantity=quantity, metadata=ask_metadata))
        
        # Sort bids descending (best bid first) and asks ascending (best ask first)
        bids.sort(key=lambda x: x.price, reverse=True)
        asks.sort(key=lambda x: x.price)
        
        # Extract timestamp if available
        timestamp = None
        if 'timestamp' in data:
            try:
                ts = data['timestamp']
                if isinstance(ts, (int, float)):
                    timestamp = datetime.fromtimestamp(ts)
                elif isinstance(ts, str):
                    timestamp = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except (ValueError, TypeError, OSError):
                pass
        
        return OrderBook(
            market_id=str(market_id),
            bids=bids,
            asks=asks,
            timestamp=timestamp,
            metadata=orderbook_data
        )

