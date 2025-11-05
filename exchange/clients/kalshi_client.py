"""Kalshi exchange client implementation using kalshi-python SDK."""

import os
import logging
from typing import List, Optional, Callable
from datetime import datetime

from kalshi_python import Configuration, KalshiClient as KalshiSDKClient
from kalshi_python.exceptions import ApiException

from ..base import ExchangeClient
from ..models import Market, OrderBook, OrderBookEntry, MarketMetadata
from ..errors import KalshiAPIError
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class KalshiClient(ExchangeClient):
    """Client for interacting with Kalshi exchange via kalshi-python SDK.
    
    This client implements the ExchangeClient interface and uses the official
    Kalshi Python SDK to fetch markets, orderbooks, and market details.
    
    Reference: https://docs.kalshi.com/sdks/python/quickstart
    """
    
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    
    def __init__(
        self,
        host: Optional[str] = None,
        api_key_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        private_key: Optional[str] = None,
        rate_limit_delay: float = 0.1
    ):
        """Initialize the Kalshi client.
        
        Args:
            host: Base URL for Kalshi API (default: https://api.elections.kalshi.com/trade-api/v2).
            api_key_id: Kalshi API key ID. If not provided, reads from KALSHI_API_KEY_ID env var.
            private_key_path: Path to private key PEM file. If not provided, reads from KALSHI_PRIVATE_KEY_PATH env var.
            private_key: Private key PEM content as string. If not provided, reads from KALSHI_PRIVATE_KEY env var.
                        Takes precedence over private_key_path if both are provided.
            rate_limit_delay: Minimum delay between requests in seconds (default: 0.1).
        
        Note: Authentication is optional for public endpoints. If api_key_id and private_key/private_key_path
        are provided, authenticated requests will be used.
        """
        self.host = host or self.BASE_URL
        self.exchange_name = "kalshi"
        self.rate_limiter = RateLimiter(min_delay=rate_limit_delay)
        
        # Configure the SDK client
        config = Configuration(host=self.host)
        
        # Get API key from parameter or environment variable
        api_key_id = api_key_id or os.getenv("KALSHI_API_KEY_ID")
        
        # Get private key from parameter, environment variable, or file
        private_key_content = None
        if private_key:
            private_key_content = private_key
        elif os.getenv("KALSHI_PRIVATE_KEY"):
            private_key_content = os.getenv("KALSHI_PRIVATE_KEY")
        elif private_key_path or os.getenv("KALSHI_PRIVATE_KEY_PATH"):
            key_path = private_key_path or os.getenv("KALSHI_PRIVATE_KEY_PATH")
            if key_path and os.path.exists(key_path):
                with open(key_path, "r") as f:
                    private_key_content = f.read()
        
        # Set up authentication if both API key and private key are available
        if api_key_id and private_key_content:
            config.api_key_id = api_key_id
            config.private_key_pem = private_key_content
        
        self.sdk_client = KalshiSDKClient(config)

    def fetch_all_markets(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        max_pages: Optional[int] = None,
        page_size: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Market]:
        """Retrieve all markets from Kalshi.
        
        Uses Kalshi Python SDK to fetch all available markets. Handles pagination
        automatically to fetch all markets across multiple pages. The response is
        normalized to the common Market model.
        
        Args:
            limit: Maximum number of markets to return total (optional, None = all).
            cursor: Starting cursor for pagination (optional, usually None).
            max_pages: Maximum number of pages to fetch (optional, None = all).
            page_size: Number of markets per page (optional, uses API default if not provided).
            progress_callback: Optional callback function(page_num, total_markets) for progress updates.
        
        Returns:
            List[Market]: A list of all available markets.
            
        Raises:
            KalshiAPIError: If the API request fails.
        """
        all_markets = []
        page_num = 0
        current_cursor = cursor
        total_fetched = 0
        
        try:
            while True:
                # Check if we've hit the limit
                if limit and total_fetched >= limit:
                    break
                
                # Check if we've hit max pages
                if max_pages and page_num >= max_pages:
                    break
                
                # Rate limit before request
                self.rate_limiter.wait_if_needed()
                
                # Calculate how many to request this page
                page_limit = None
                if limit:
                    remaining = limit - total_fetched
                    if page_size:
                        page_limit = min(remaining, page_size)
                    else:
                        page_limit = remaining
                elif page_size:
                    page_limit = page_size
                
                try:
                    # Use SDK method to get markets
                    response = self.sdk_client.get_markets(
                        limit=page_limit,
                        cursor=current_cursor
                    )
                    
                    self.rate_limiter.record_request()
                    self.rate_limiter.reset_delay()
                    
                    page_markets = []
                    
                    # SDK returns a MarketsResponse object with markets attribute
                    if hasattr(response, 'markets') and response.markets:
                        for market_raw in response.markets:
                            # Convert SDK model to dict for normalization
                            market_dict = self._sdk_model_to_dict(market_raw)
                            market = self._normalize_market(market_dict)
                            if market:
                                page_markets.append(market)
                    
                    all_markets.extend(page_markets)
                    total_fetched = len(all_markets)
                    page_num += 1
                    
                    # Progress callback
                    if progress_callback:
                        progress_callback(page_num, total_fetched)
                    
                    # Check for next cursor
                    next_cursor = None
                    if hasattr(response, 'cursor'):
                        next_cursor = response.cursor
                    elif hasattr(response, 'next_cursor'):
                        next_cursor = response.next_cursor
                    
                    # If no more pages or no markets returned, break
                    if not next_cursor or not page_markets:
                        break
                    
                    current_cursor = next_cursor
                    
                    logger.info(f"Fetched page {page_num}: {len(page_markets)} markets (total: {total_fetched})")
                    
                except ApiException as e:
                    # Check if it's a rate limit error (429)
                    if hasattr(e, 'status') and e.status == 429:
                        logger.warning(f"Rate limit hit on page {page_num}, backing off...")
                        self.rate_limiter.handle_rate_limit_error()
                        self.rate_limiter.wait_if_needed()
                        continue  # Retry this page
                    else:
                        # For other errors, log and continue if we have some markets
                        logger.warning(f"Error fetching page {page_num}: {str(e)}")
                        if all_markets:
                            logger.info(f"Returning {len(all_markets)} markets fetched so far")
                            break
                        else:
                            raise KalshiAPIError(f"Kalshi API error: {str(e)}") from e
                
        except Exception as e:
            if all_markets:
                logger.warning(f"Error during pagination, returning {len(all_markets)} markets: {str(e)}")
                return all_markets
            raise KalshiAPIError(f"Failed to fetch Kalshi markets: {str(e)}") from e
        
        logger.info(f"Fetched {len(all_markets)} total markets across {page_num} pages")
        return all_markets

    def fetch_orderbook(self, market_id: str) -> OrderBook:
        """Get the full order book for a specific Kalshi market.
        
        Args:
            market_id: The Kalshi market ticker symbol.
            
        Returns:
            OrderBook: The full order book with bids and asks.
            
        Raises:
            KalshiAPIError: If the API request fails.
        """
        try:
            # Rate limit before request
            self.rate_limiter.wait_if_needed()
            
            # Kalshi SDK doesn't have a direct orderbook method, so use REST API
            import requests
            url = f"{self.host}/markets/{market_id}/orderbook"
            
            try:
                response_obj = requests.get(url, timeout=30)
                
                # Handle rate limit errors
                if response_obj.status_code == 429:
                    logger.warning(f"Rate limit hit (429), backing off...")
                    self.rate_limiter.handle_rate_limit_error()
                    self.rate_limiter.wait_if_needed()
                    # Retry once
                    response_obj = requests.get(url, timeout=30)
                
                response_obj.raise_for_status()
                self.rate_limiter.record_request()
                self.rate_limiter.reset_delay()
                
                response = response_obj.json()
                
                # Normalize the response to OrderBook model
                return self._normalize_orderbook(market_id, response)
            except requests.exceptions.HTTPError as e:
                if response_obj.status_code == 429:
                    self.rate_limiter.handle_rate_limit_error()
                    self.rate_limiter.wait_if_needed()
                    # Retry once
                    response_obj = requests.get(url, timeout=30)
                    response_obj.raise_for_status()
                    self.rate_limiter.record_request()
                    response = response_obj.json()
                    return self._normalize_orderbook(market_id, response)
                error_msg = f"HTTP {response_obj.status_code}: {response_obj.text}"
                raise KalshiAPIError(error_msg) from e
            except requests.exceptions.RequestException as e:
                raise KalshiAPIError(f"Request failed: {str(e)}") from e
        except Exception as e:
            if isinstance(e, KalshiAPIError):
                raise
            raise KalshiAPIError(f"Failed to fetch Kalshi orderbook for {market_id}: {str(e)}") from e

    def fetch_market_details(self, market_id: str) -> Market:
        """Get market rules, name, and all associated metadata.
        
        Args:
            market_id: The Kalshi market ticker symbol.
            
        Returns:
            Market: Complete market information.
            
        Raises:
            KalshiAPIError: If the API request fails.
        """
        try:
            # Rate limit before request
            self.rate_limiter.wait_if_needed()
            
            # Use SDK method to get market details
            response = self.sdk_client.get_market(ticker=market_id)
            
            self.rate_limiter.record_request()
            self.rate_limiter.reset_delay()
            
            # Convert SDK model to dict for normalization
            response_dict = self._sdk_model_to_dict(response)
            
            # Handle nested response structure (SDK might return response.market or response.event)
            market_dict = response_dict
            if isinstance(response_dict, dict):
                if 'market' in response_dict:
                    market_dict = response_dict['market']
                elif 'event' in response_dict:
                    event = response_dict['event']
                    # If event has markets, use the first one
                    if 'markets' in event and isinstance(event['markets'], list) and len(event['markets']) > 0:
                        market_dict = event['markets'][0]
                    else:
                        market_dict = event
                # If the response itself is the market (has 'ticker' field), use it directly
                elif 'ticker' in response_dict or 'event_ticker' in response_dict:
                    market_dict = response_dict
            
            # If we still don't have a ticker, use the market_id we passed in
            if isinstance(market_dict, dict) and not market_dict.get('ticker') and not market_dict.get('event_ticker'):
                market_dict['ticker'] = market_id
            
            return self._normalize_market(market_dict)
        except ApiException as e:
            # Check if it's a rate limit error
            if hasattr(e, 'status') and e.status == 429:
                self.rate_limiter.handle_rate_limit_error()
                self.rate_limiter.wait_if_needed()
                # Retry once
                try:
                    response = self.sdk_client.get_market(ticker=market_id)
                    self.rate_limiter.record_request()
                    response_dict = self._sdk_model_to_dict(response)
                    
                    # Handle nested response structure
                    market_dict = response_dict
                    if isinstance(response_dict, dict):
                        if 'market' in response_dict:
                            market_dict = response_dict['market']
                        elif 'event' in response_dict:
                            event = response_dict['event']
                            if 'markets' in event and isinstance(event['markets'], list) and len(event['markets']) > 0:
                                market_dict = event['markets'][0]
                            else:
                                market_dict = event
                        elif 'ticker' in response_dict or 'event_ticker' in response_dict:
                            market_dict = response_dict
                    
                    # If we still don't have a ticker, use the market_id we passed in
                    if isinstance(market_dict, dict) and not market_dict.get('ticker') and not market_dict.get('event_ticker'):
                        market_dict['ticker'] = market_id
                    
                    return self._normalize_market(market_dict)
                except ApiException as retry_e:
                    raise KalshiAPIError(f"Kalshi API error after retry: {str(retry_e)}") from retry_e
            raise KalshiAPIError(f"Kalshi API error: {str(e)}") from e
        except Exception as e:
            raise KalshiAPIError(f"Failed to fetch Kalshi market details for {market_id}: {str(e)}") from e

    def _sdk_model_to_dict(self, model) -> dict:
        """Convert SDK model object to dictionary.
        
        Args:
            model: SDK model object (e.g., Market, Orderbook, etc.) or dict.
            
        Returns:
            Dictionary representation of the model.
        """
        # If it's already a dict, return it
        if isinstance(model, dict):
            return model
        
        if hasattr(model, 'to_dict'):
            return model.to_dict()
        elif hasattr(model, '__dict__'):
            return {k: self._sdk_model_to_dict(v) if (hasattr(v, '__dict__') or isinstance(v, dict)) else v 
                   for k, v in model.__dict__.items()}
        elif isinstance(model, (str, int, float, bool, type(None))):
            return model
        elif isinstance(model, list):
            return [self._sdk_model_to_dict(item) for item in model]
        else:
            # Fallback: try to convert to string representation
            return str(model)

    def _normalize_market(self, market_data: dict) -> Market:
        """Normalize Kalshi market data to the common Market model.
        
        Args:
            market_data: Raw market data from Kalshi SDK.
            
        Returns:
            Market: Normalized market object.
        """
        # Extract market ID - Kalshi uses 'ticker' or 'event_ticker'
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
        
        # Extract expiration/resolution time
        expiration_time = market_data.get('expected_expiration_time') or market_data.get('expiration_time')
        resolve_date = None
        resolve_time = None
        
        if expiration_time:
            try:
                if isinstance(expiration_time, str):
                    dt = datetime.fromisoformat(expiration_time.replace('Z', '+00:00'))
                    resolve_date = dt.strftime('%Y-%m-%d')
                    resolve_time = dt.strftime('%H:%M:%S')
                elif isinstance(expiration_time, (int, float)):
                    dt = datetime.fromtimestamp(expiration_time)
                    resolve_date = dt.strftime('%Y-%m-%d')
                    resolve_time = dt.strftime('%H:%M:%S')
            except (ValueError, TypeError, OSError):
                pass
        
        # Extract metadata
        metadata = MarketMetadata(
            resolve_date=resolve_date,
            resolve_time=resolve_time,
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
                'event_ticker': market_data.get('event_ticker'),
                'series_ticker': market_data.get('series_ticker'),
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
            orderbook_data: Raw orderbook data from Kalshi SDK.
            
        Returns:
            OrderBook: Normalized orderbook object.
        """
        # Handle nested response structure
        data = orderbook_data
        if isinstance(orderbook_data, dict) and 'orderbook' in orderbook_data:
            data = orderbook_data['orderbook']
        
        bids = []
        asks = []
        
        # Kalshi typically has 'yes' and 'no' sides, or 'bids' and 'asks'
        if 'yes' in data and 'no' in data:
            # Binary market with yes/no sides
            # Handle case where yes/no might be None
            yes_data = data.get('yes') or {}
            no_data = data.get('no') or {}
            
            yes_bids = yes_data.get('bids', []) if isinstance(yes_data, dict) else []
            yes_asks = yes_data.get('asks', []) if isinstance(yes_data, dict) else []
            no_bids = no_data.get('bids', []) if isinstance(no_data, dict) else []
            no_asks = no_data.get('asks', []) if isinstance(no_data, dict) else []
            
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
                ts = data['timestamp']
                if isinstance(ts, str):
                    timestamp = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                elif isinstance(ts, (int, float)):
                    timestamp = datetime.fromtimestamp(ts)
            except (ValueError, TypeError, OSError):
                pass
        
        return OrderBook(
            market_id=str(market_id),
            bids=bids,
            asks=asks,
            timestamp=timestamp,
            metadata=orderbook_data
        )
