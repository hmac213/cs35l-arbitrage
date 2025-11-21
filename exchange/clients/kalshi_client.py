"""Kalshi exchange client implementation using kalshi-python SDK."""

import os
import logging
import requests
import asyncio
import json
import time
import base64
from typing import List, Optional, Callable, Dict, Any
from datetime import datetime

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    websockets = None

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
        # Cache for event metadata to avoid repeated API calls
        self._event_metadata_cache: dict[str, dict] = {}
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
        
        # Websocket connection state
        self._ws_url = "wss://api.elections.kalshi.com/trade-api/ws/v2"
        self._ws_connection: Optional[Any] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._ws_subscriptions: Dict[str, Callable[[OrderBook], None]] = {}
        self._ws_running = False
        self._api_key_id = api_key_id or os.getenv("KALSHI_API_KEY_ID")
        self._private_key_content = private_key_content
        self._message_id = 1  # Message ID counter for websocket commands

    def fetch_all_markets(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        max_pages: Optional[int] = None,
        page_size: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        fetch_image_urls: bool = False
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
        seen_cursors = set()  # Track cursors to detect infinite loops
        
        try:
            while True:
                # Check if we've hit the limit
                if limit and total_fetched >= limit:
                    break
                
                # Check if we've hit max pages
                if max_pages and page_num >= max_pages:
                    break
                
                # Safety check: detect if we're stuck in a loop (same cursor twice)
                if current_cursor and current_cursor in seen_cursors:
                    logger.warning(f"Detected duplicate cursor {current_cursor}, stopping pagination to prevent infinite loop")
                    break
                if current_cursor:
                    seen_cursors.add(current_cursor)
                
                # Rate limit before request
                self.rate_limiter.wait_if_needed()
                
                # Calculate how many to request this page
                # Default page size if not specified (Kalshi API supports up to 1000 per page)
                default_page_size = page_size or 1000
                
                if limit:
                    remaining = limit - total_fetched
                    if remaining <= 0:
                        break  # Already fetched enough
                    page_limit = min(remaining, default_page_size)
                else:
                    page_limit = default_page_size
                
                try:
                    # Use REST API directly to get markets (SDK doesn't include rules_primary/rules_secondary)
                    import requests
                    url = f"{self.host}/markets"
                    params = {
                        "status": "open",  # Only fetch open markets
                        "mve_filter": "exclude"  # Exclude multivariate events
                    }
                    # Only add limit if we have a specific limit to enforce
                    if page_limit is not None:
                        params["limit"] = page_limit
                    if current_cursor:
                        params["cursor"] = current_cursor
                    
                    self.rate_limiter.wait_if_needed()
                    response_obj = requests.get(url, params=params, timeout=30)
                    
                    # Handle rate limit errors
                    if response_obj.status_code == 429:
                        logger.warning(f"Rate limit hit on page {page_num}, backing off...")
                        self.rate_limiter.handle_rate_limit_error()
                        self.rate_limiter.wait_if_needed()
                        response_obj = requests.get(url, params=params, timeout=30)
                    
                    response_obj.raise_for_status()
                    self.rate_limiter.record_request()
                    self.rate_limiter.reset_delay()
                    
                    response_data = response_obj.json()
                    
                    page_markets = []
                    
                    # Extract markets from response
                    markets_list = response_data.get('markets', [])
                    if markets_list:
                        for market_dict in markets_list:
                            # market_dict is already a dict from REST API, includes rules_primary/rules_secondary
                            market = self._normalize_market(market_dict, fetch_image_urls=fetch_image_urls)
                            if market:
                                page_markets.append(market)
                    
                    # Get cursor for next page
                    next_cursor = response_data.get('cursor')
                    
                    all_markets.extend(page_markets)
                    total_fetched = len(all_markets)
                    page_num += 1
                    
                    # Progress callback
                    if progress_callback:
                        progress_callback(page_num, total_fetched)
                    
                    # If no more pages or no markets returned, break
                    if not next_cursor or not page_markets:
                        logger.info(f"No more pages (cursor: {next_cursor}, markets: {len(page_markets)}), stopping pagination")
                        break
                    
                    # Check if cursor changed (safety check)
                    if next_cursor == current_cursor:
                        logger.warning(f"Cursor did not change ({current_cursor}), stopping pagination to prevent infinite loop")
                        break
                    
                    current_cursor = next_cursor
                    
                    logger.info(f"Fetched page {page_num}: {len(page_markets)} markets (total: {total_fetched}, next_cursor: {next_cursor[:20] if next_cursor else None}...)")
                    
                except requests.exceptions.HTTPError as e:
                    # Check if it's a rate limit error (429)
                    if hasattr(e.response, 'status_code') and e.response.status_code == 429:
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
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Request error on page {page_num}: {str(e)}")
                    if all_markets:
                        logger.info(f"Returning {len(all_markets)} markets fetched so far")
                        break
                    else:
                        raise KalshiAPIError(f"Kalshi API request failed: {str(e)}") from e
                
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
            
            # For fetch_market_details, fetch image URLs since it's a single market
            return self._normalize_market(market_dict, fetch_image_urls=True)
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
                    
                    # For fetch_market_details, fetch image URLs since it's a single market
                    return self._normalize_market(market_dict, fetch_image_urls=True)
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

    def _fetch_event_metadata(self, event_ticker: str) -> Optional[dict]:
        """Fetch event metadata including image URLs.
        
        Uses caching to avoid repeated API calls for the same event.
        
        Args:
            event_ticker: The event ticker to fetch metadata for.
            
        Returns:
            Dictionary with event metadata, or None if not found.
        """
        if not event_ticker:
            return None
        
        # Check cache first
        if event_ticker in self._event_metadata_cache:
            return self._event_metadata_cache[event_ticker]
        
        try:
            # Rate limit before request
            self.rate_limiter.wait_if_needed()
            
            # Use REST API to fetch event metadata
            import requests
            url = f"{self.host}/events/{event_ticker}/metadata"
            
            try:
                response_obj = requests.get(url, timeout=30)
                
                # Handle rate limit errors
                if response_obj.status_code == 429:
                    logger.warning(f"Rate limit hit (429) for event metadata, backing off...")
                    self.rate_limiter.handle_rate_limit_error()
                    self.rate_limiter.wait_if_needed()
                    # Retry once
                    response_obj = requests.get(url, timeout=30)
                
                response_obj.raise_for_status()
                self.rate_limiter.record_request()
                self.rate_limiter.reset_delay()
                
                metadata = response_obj.json()
                # Cache the result
                self._event_metadata_cache[event_ticker] = metadata
                return metadata
            except requests.exceptions.HTTPError as e:
                if response_obj.status_code == 404:
                    # Event metadata not found - not an error, just return None
                    logger.debug(f"Event metadata not found for {event_ticker}")
                    return None
                if response_obj.status_code == 429:
                    self.rate_limiter.handle_rate_limit_error()
                    self.rate_limiter.wait_if_needed()
                    # Retry once
                    response_obj = requests.get(url, timeout=30)
                    response_obj.raise_for_status()
                    self.rate_limiter.record_request()
                    metadata = response_obj.json()
                    # Cache the result
                    self._event_metadata_cache[event_ticker] = metadata
                    return metadata
                error_msg = f"HTTP {response_obj.status_code}: {response_obj.text}"
                logger.warning(f"Failed to fetch event metadata for {event_ticker}: {error_msg}")
                return None
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed for event metadata {event_ticker}: {str(e)}")
                return None
        except Exception as e:
            logger.warning(f"Error fetching event metadata for {event_ticker}: {str(e)}")
            return None
    
    def _get_market_image_url(self, market_ticker: str, event_ticker: Optional[str], event_metadata: Optional[dict] = None) -> Optional[str]:
        """Get image URL for a market from event metadata.
        
        Args:
            market_ticker: The market ticker.
            event_ticker: The event ticker (optional, used to fetch metadata if not provided).
            event_metadata: Pre-fetched event metadata (optional).
            
        Returns:
            Image URL string or None if not found.
        """
        # If metadata not provided, try to fetch it
        if event_metadata is None and event_ticker:
            event_metadata = self._fetch_event_metadata(event_ticker)
        
        if not event_metadata:
            return None
        
        # First, try to find market-specific image_url in market_details
        market_details = event_metadata.get('market_details', [])
        if market_details:
            for market_detail in market_details:
                if market_detail.get('market_ticker') == market_ticker:
                    image_url = market_detail.get('image_url')
                    if image_url:
                        return image_url
        
        # Fall back to event-level image URLs
        # Prefer featured_image_url if available, otherwise image_url
        return event_metadata.get('featured_image_url') or event_metadata.get('image_url')
    
    def _normalize_market(self, market_data: dict, event_metadata: Optional[dict] = None, fetch_image_urls: bool = False) -> Market:
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
        
        # Extract rules - Kalshi has rules_primary and rules_secondary that should be combined
        rules_parts = []
        rules_primary = market_data.get('rules_primary')
        rules_secondary = market_data.get('rules_secondary')
        
        # Handle empty strings as well as None
        if rules_primary and str(rules_primary).strip():
            rules_parts.append(str(rules_primary).strip())
        if rules_secondary and str(rules_secondary).strip():
            rules_parts.append(str(rules_secondary).strip())
        
        # Combine rules_primary and rules_secondary, or fall back to other fields
        if rules_parts:
            rules = '\n\n'.join([r for r in rules_parts if r])  # Join with double newline, filter empty
        else:
            # Fall back to other fields
            rules = (
                market_data.get('rules') or
                market_data.get('subtitle') or
                market_data.get('description') or
                None  # Return None instead of empty string if not available
            )
        
        # Extract expiration/resolution time
        # Prefer close_time or expiration_time for resolve date/time
        resolution_datetime = (
            market_data.get('close_time') or
            market_data.get('expiration_time') or
            market_data.get('expected_expiration_time')
        )
        resolve_date = None
        resolve_time = None
        
        if resolution_datetime:
            try:
                # Handle datetime objects directly
                if isinstance(resolution_datetime, datetime):
                    dt = resolution_datetime
                    # Remove timezone info for date/time extraction
                    if dt.tzinfo:
                        dt = dt.replace(tzinfo=None)
                    resolve_date = dt.strftime('%Y-%m-%d')
                    resolve_time = dt.strftime('%H:%M:%S')
                elif isinstance(resolution_datetime, str):
                    # Handle various datetime string formats
                    # Format: "2025-12-14 18:00:00+00:00" or "2025-12-14T18:00:00Z" etc.
                    dt_str = resolution_datetime.replace('Z', '+00:00')
                    # Try parsing with timezone first
                    try:
                        dt = datetime.fromisoformat(dt_str)
                    except ValueError:
                        # Try parsing without timezone
                        dt_str_no_tz = dt_str.split('+')[0].split('-')[0] if '+' in dt_str else dt_str
                        dt = datetime.strptime(dt_str_no_tz, '%Y-%m-%d %H:%M:%S')
                    
                    if dt.tzinfo:
                        dt = dt.replace(tzinfo=None)
                    resolve_date = dt.strftime('%Y-%m-%d')
                    resolve_time = dt.strftime('%H:%M:%S')
                elif isinstance(resolution_datetime, (int, float)):
                    dt = datetime.fromtimestamp(resolution_datetime)
                    resolve_date = dt.strftime('%Y-%m-%d')
                    resolve_time = dt.strftime('%H:%M:%S')
            except (ValueError, TypeError, OSError, AttributeError) as e:
                logger.debug(f"Failed to parse resolution datetime {resolution_datetime}: {e}")
                pass
        
        # Extract metadata
        # Kalshi doesn't have tags, category, or subcategory in standard format
        # Store all Kalshi-specific fields in extra
        # Note: image_url is not stored in the database - will be fetched later for matching pairs
        metadata = MarketMetadata(
            resolve_date=resolve_date,
            resolve_time=resolve_time,
            category=market_data.get('category') or None,  # Kalshi provides category in REST API
            subcategory=None,  # Kalshi doesn't provide subcategory
            tags=None,  # Kalshi doesn't provide tags
            description=market_data.get('description') or market_data.get('subtitle') or None,
            image_url=None,  # Not stored in database - will be fetched later for matching pairs
            liquidity=None,  # Kalshi doesn't expose liquidity
            volume=market_data.get('volume') or market_data.get('volume_24h') or market_data.get('total_volume'),
            extra={
                'ticker': market_data.get('ticker'),
                'event_ticker': market_data.get('event_ticker'),
                'series_ticker': market_data.get('series_ticker'),
                'open_time': market_data.get('open_time'),
                'close_time': market_data.get('close_time'),
                'expiration_time': market_data.get('expiration_time'),
                'status': market_data.get('status'),
                'yes_bid': market_data.get('yes_bid'),
                'yes_ask': market_data.get('yes_ask'),
                'no_bid': market_data.get('no_bid'),
                'no_ask': market_data.get('no_ask'),
                'last_price': market_data.get('last_price'),
                'previous_price': market_data.get('previous_price'),
                'result': market_data.get('result'),
                'can_close_early': market_data.get('can_close_early'),
                'rules_primary': market_data.get('rules_primary'),  # Store original fields in extra
                'rules_secondary': market_data.get('rules_secondary'),
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
        
        # Store original yes/no structure in metadata for later extraction
        orderbook_metadata = {'raw': orderbook_data}
        
        # Kalshi typically has 'yes' and 'no' sides, or 'bids' and 'asks'
        if 'yes' in data and 'no' in data:
            # Binary market with yes/no sides
            # Handle case where yes/no might be None
            yes_data = data.get('yes')
            no_data = data.get('no')
            
            # Preserve original structure in metadata
            orderbook_metadata['yes'] = yes_data
            orderbook_metadata['no'] = no_data
            
            # Kalshi API returns yes/no as arrays of [price, quantity] pairs
            # IMPORTANT: Kalshi only returns BIDS for both YES and NO sides
            # ASKS are implied: YES ask = NO bid inverted, NO ask = YES bid inverted
            # Prices are in cents (1-100), so divide by 100 to get decimal (0.01-1.0)
            # Or as dictionaries with bids/asks (legacy format)
            if isinstance(yes_data, list):
                # Array format: [[price_cents, quantity], ...]
                # This represents YES BIDS (people buying YES)
                for entry in yes_data:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        price_cents = float(entry[0])
                        price = price_cents / 100.0  # Convert cents to decimal
                        quantity = float(entry[1])
                        # Mark this as YES bid in metadata
                        bids.append(OrderBookEntry(price=price, quantity=quantity, metadata={'raw': entry, 'side': 'yes', 'type': 'bid'}))
            elif isinstance(yes_data, dict):
                # Dictionary format: {"bids": [...], "asks": [...]}
                yes_bids = yes_data.get('bids', [])
                yes_asks = yes_data.get('asks', [])
                
                for bid in yes_bids:
                    if isinstance(bid, (list, tuple)) and len(bid) >= 2:
                        price_cents = float(bid[0])
                        price = price_cents / 100.0 if price_cents > 1 else price_cents
                        quantity = float(bid[1])
                        bids.append(OrderBookEntry(price=price, quantity=quantity, metadata={'raw': bid}))
                    elif isinstance(bid, dict):
                        price = float(bid.get('price', bid.get('yes_price', 0)))
                        quantity = float(bid.get('quantity', bid.get('size', 0)))
                        bids.append(OrderBookEntry(price=price, quantity=quantity, metadata=bid))
                
                for ask in yes_asks:
                    if isinstance(ask, (list, tuple)) and len(ask) >= 2:
                        price_cents = float(ask[0])
                        price = price_cents / 100.0 if price_cents > 1 else price_cents
                        quantity = float(ask[1])
                        asks.append(OrderBookEntry(price=price, quantity=quantity, metadata={'raw': ask}))
                    elif isinstance(ask, dict):
                        price = float(ask.get('price', ask.get('yes_price', 0)))
                        quantity = float(ask.get('quantity', ask.get('size', 0)))
                        asks.append(OrderBookEntry(price=price, quantity=quantity, metadata=ask))
            
            # Handle no side (inverted prices: no_price = 1 - yes_price)
            if isinstance(no_data, list):
                # Array format: [[price_cents, quantity], ...]
                # IMPORTANT: This represents NO BIDS (people buying NO)
                # NO bids stay as NO bids, but we also need to create YES asks from them
                # YES ask price = 1 - NO bid price (because buying NO at X = selling YES at 1-X)
                for entry in no_data:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        no_price_cents = float(entry[0])
                        no_price = no_price_cents / 100.0  # Convert cents to decimal
                        quantity = float(entry[1])
                        # NO bid stays as bid (we'll handle the YES ask conversion in orderbook_poller)
                        # But we also add it to bids with metadata
                        bids.append(OrderBookEntry(price=no_price, quantity=quantity, metadata={'raw': entry, 'side': 'no', 'type': 'bid', 'no_price': no_price}))
                        # Also create YES ask (inverted): buying NO at no_price = selling YES at (1 - no_price)
                        yes_ask_price = 1.0 - no_price
                        asks.append(OrderBookEntry(price=yes_ask_price, quantity=quantity, metadata={'raw': entry, 'side': 'yes', 'type': 'ask', 'derived_from': 'no_bid', 'no_price': no_price}))
            elif isinstance(no_data, dict):
                # Dictionary format: {"bids": [...], "asks": [...]}
                no_bids = no_data.get('bids', [])
                no_asks = no_data.get('asks', [])
                
                for bid in no_bids:
                    if isinstance(bid, (list, tuple)) and len(bid) >= 2:
                        no_price_cents = float(bid[0])
                        no_price = no_price_cents / 100.0 if no_price_cents > 1 else no_price_cents
                        yes_price = 1.0 - no_price
                        quantity = float(bid[1])
                        asks.append(OrderBookEntry(price=yes_price, quantity=quantity, metadata={'raw': bid, 'no_price': no_price}))
                    elif isinstance(bid, dict):
                        no_price = float(bid.get('price', bid.get('no_price', 0)))
                        yes_price = 1.0 - no_price
                        quantity = float(bid.get('quantity', bid.get('size', 0)))
                        asks.append(OrderBookEntry(price=yes_price, quantity=quantity, metadata=bid))
                
                for ask in no_asks:
                    if isinstance(ask, (list, tuple)) and len(ask) >= 2:
                        no_price_cents = float(ask[0])
                        no_price = no_price_cents / 100.0 if no_price_cents > 1 else no_price_cents
                        yes_price = 1.0 - no_price
                        quantity = float(ask[1])
                        bids.append(OrderBookEntry(price=yes_price, quantity=quantity, metadata={'raw': ask, 'no_price': no_price}))
                    elif isinstance(ask, dict):
                        no_price = float(ask.get('price', ask.get('no_price', 0)))
                        yes_price = 1.0 - no_price
                        quantity = float(ask.get('quantity', ask.get('size', 0)))
                        bids.append(OrderBookEntry(price=yes_price, quantity=quantity, metadata=ask))
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
    
    async def connect_websocket(self) -> None:
        """Connect to Kalshi websocket for real-time orderbook updates.
        
        Raises:
            KalshiAPIError: If websockets library is not available or connection fails.
        """
        if not WEBSOCKETS_AVAILABLE:
            raise KalshiAPIError("websockets library is not installed. Install it with: pip install websockets")
        
        if self._ws_connection is not None:
            logger.warning("Websocket already connected")
            return
        
        try:
            # Prepare authentication headers if API key and private key are available
            headers = {}
            if not self._api_key_id:
                raise KalshiAPIError("KALSHI_API_KEY_ID is required for websocket authentication")
            if not self._private_key_content:
                raise KalshiAPIError("KALSHI_PRIVATE_KEY is required for websocket authentication")
            
            if self._api_key_id and self._private_key_content:
                # Kalshi websocket requires signed authentication
                # According to docs: https://docs.kalshi.com/getting_started/quick_start_websockets
                # Message to sign: timestamp + "GET" + "/trade-api/ws/v2"
                timestamp = str(int(time.time() * 1000))
                method = "GET"
                path = "/trade-api/ws/v2"
                msg_string = timestamp + method + path
                
                try:
                    from cryptography.hazmat.primitives import hashes, serialization
                    from cryptography.hazmat.primitives.asymmetric import padding
                    from cryptography.hazmat.backends import default_backend
                    
                    # Load private key - ensure it's bytes
                    if isinstance(self._private_key_content, str):
                        private_key_bytes = self._private_key_content.encode('utf-8')
                    else:
                        private_key_bytes = self._private_key_content
                    
                    private_key = serialization.load_pem_private_key(
                        private_key_bytes,
                        password=None,
                        backend=default_backend()
                    )
                    
                    # Sign using RSA-PSS (not PKCS1v15!)
                    # Docs specify: RSA-PSS with MGF1 and SHA256
                    # Message format: timestamp + "GET" + "/trade-api/ws/v2"
                    signature = private_key.sign(
                        msg_string.encode('utf-8'),
                        padding.PSS(
                            mgf=padding.MGF1(hashes.SHA256()),
                            salt_length=padding.PSS.DIGEST_LENGTH
                        ),
                        hashes.SHA256()
                    )
                    # Base64 encode the signature (not hex!)
                    signature_b64 = base64.b64encode(signature).decode('utf-8')
                    
                    headers['KALSHI-ACCESS-KEY'] = self._api_key_id
                    headers['KALSHI-ACCESS-SIGNATURE'] = signature_b64
                    headers['KALSHI-ACCESS-TIMESTAMP'] = timestamp
                    
                    logger.debug(f"Generated websocket auth headers: key={self._api_key_id[:8]}..., timestamp={timestamp}, signature_length={len(signature_b64)}")
                except ImportError:
                    logger.error("cryptography library not available, websocket authentication will fail")
                    raise KalshiAPIError("cryptography library is required for websocket authentication")
                except Exception as e:
                    logger.error(f"Failed to generate signature: {e}", exc_info=True)
                    raise KalshiAPIError(f"Failed to generate websocket signature: {e}") from e
            
            # Connect to websocket with authentication
            # websockets library uses 'additional_headers' parameter
            connect_kwargs = {
                'ping_interval': 30,  # Send ping every 30 seconds
                'ping_timeout': 10
            }
            if headers:
                # Convert headers dict to list of tuples for websockets library
                additional_headers = [(k, v) for k, v in headers.items()]
                connect_kwargs['additional_headers'] = additional_headers
                logger.debug(f"Connecting with headers: {list(headers.keys())}")
            else:
                logger.warning("No authentication headers generated, connection may fail")
            
            self._ws_connection = await websockets.connect(
                self._ws_url,
                **connect_kwargs
            )
            self._ws_running = True
            
            # Start message handler task
            self._ws_task = asyncio.create_task(self._ws_message_handler())
            
            logger.info("Connected to Kalshi websocket")
        except Exception as e:
            self._ws_connection = None
            self._ws_running = False
            raise KalshiAPIError(f"Failed to connect to Kalshi websocket: {e}") from e
    
    async def disconnect_websocket(self) -> None:
        """Disconnect from Kalshi websocket."""
        self._ws_running = False
        
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        
        if self._ws_connection:
            try:
                await self._ws_connection.close()
            except Exception as e:
                logger.warning(f"Error closing websocket: {e}")
            self._ws_connection = None
        
        self._ws_subscriptions.clear()
        logger.info("Disconnected from Kalshi websocket")
    
    async def subscribe_orderbooks_batch(
        self,
        market_tickers: List[str],
        callbacks: Dict[str, Callable[[OrderBook], None]]
    ) -> None:
        """Subscribe to orderbook updates for multiple markets at once.
        
        This is more efficient than subscribing individually.
        
        Args:
            market_tickers: List of Kalshi market ticker symbols.
            callbacks: Dictionary mapping ticker to callback function.
        
        Raises:
            KalshiAPIError: If websocket is not connected or subscription fails.
        """
        if self._ws_connection is None or not self._ws_running:
            raise KalshiAPIError("Websocket is not connected. Call connect_websocket() first.")
        
        if not market_tickers:
            return
        
        # Store all subscriptions
        self._ws_subscriptions.update(callbacks)
        
        # Send batch subscription message using Kalshi's subscribe command format
        # According to docs: https://docs.kalshi.com/getting_started/quick_start_websockets
        # Format: {"id": 1, "cmd": "subscribe", "params": {"channels": ["orderbook_delta"], "market_tickers": [...]}}
        subscribe_msg = {
            "id": self._message_id,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_tickers": market_tickers
            }
        }
        self._message_id += 1
        
        try:
            await self._ws_connection.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to orderbook updates for {len(market_tickers)} Kalshi markets")
        except Exception as e:
            # Remove subscriptions on failure
            for ticker in market_tickers:
                self._ws_subscriptions.pop(ticker, None)
            raise KalshiAPIError(f"Failed to subscribe to markets: {e}") from e
    
    async def subscribe_orderbook(
        self,
        market_ticker: str,
        callback: Callable[[OrderBook], None]
    ) -> None:
        """Subscribe to orderbook updates for a single market.
        
        For multiple markets, use subscribe_orderbooks_batch() instead.
        
        Args:
            market_ticker: The Kalshi market ticker symbol.
            callback: Callback function that receives OrderBook updates.
        
        Raises:
            KalshiAPIError: If websocket is not connected or subscription fails.
        """
        await self.subscribe_orderbooks_batch([market_ticker], {market_ticker: callback})
    
    async def unsubscribe_orderbook(self, market_ticker: str) -> None:
        """Unsubscribe from orderbook updates for a specific market.
        
        Args:
            market_ticker: The Kalshi market ticker symbol.
        """
        if market_ticker not in self._ws_subscriptions:
            return
        
        if self._ws_connection is not None:
            # Send unsubscribe message (if Kalshi supports it)
            # Note: Kalshi docs don't specify unsubscribe format, so we just remove from subscriptions
            # The connection will stop sending updates when we disconnect
            pass
        
        del self._ws_subscriptions[market_ticker]
        logger.info(f"Unsubscribed from orderbook updates for {market_ticker}")
    
    async def _ws_message_handler(self) -> None:
        """Handle incoming websocket messages."""
        max_reconnect_delay = 60
        reconnect_delay = 1
        
        while self._ws_running:
            try:
                if self._ws_connection is None:
                    break
                
                # Receive message with timeout
                try:
                    message = await asyncio.wait_for(
                        self._ws_connection.recv(),
                        timeout=60.0
                    )
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    if self._ws_connection:
                        try:
                            await self._ws_connection.ping()
                        except Exception:
                            pass
                    continue
                
                # Parse message
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON from websocket: {message}")
                    continue
                
                # Handle different message types
                # According to docs: https://docs.kalshi.com/getting_started/quick_start_websockets
                # Message types: subscribed, orderbook_snapshot, orderbook_delta, error
                msg_type = data.get("type")
                
                if msg_type == "subscribed":
                    # Confirmation of subscription
                    logger.debug(f"Subscription confirmed: {data}")
                elif msg_type == "orderbook_snapshot":
                    # Full orderbook snapshot
                    ticker = data.get("data", {}).get("market_ticker")
                    if ticker and ticker in self._ws_subscriptions:
                        try:
                            orderbook = self._parse_websocket_orderbook(data)
                            callback = self._ws_subscriptions[ticker]
                            if asyncio.iscoroutinefunction(callback):
                                await callback(orderbook)
                            else:
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(None, callback, orderbook)
                        except Exception as e:
                            logger.error(f"Error processing orderbook snapshot for {ticker}: {e}", exc_info=True)
                elif msg_type == "orderbook_delta":
                    # Incremental orderbook update
                    ticker = data.get("data", {}).get("market_ticker")
                    if ticker and ticker in self._ws_subscriptions:
                        try:
                            orderbook = self._parse_websocket_orderbook(data)
                            callback = self._ws_subscriptions[ticker]
                            # Call callback in thread-safe way
                            if asyncio.iscoroutinefunction(callback):
                                await callback(orderbook)
                            else:
                                # Run in executor if callback is sync
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(None, callback, orderbook)
                        except Exception as e:
                            logger.error(f"Error processing orderbook update for {ticker}: {e}", exc_info=True)
                elif msg_type == "error":
                    # Error response format: {"id": 123, "type": "error", "msg": {"code": 6, "msg": "..."}}
                    error_msg = data.get("msg", {})
                    error_code = error_msg.get("code", "unknown")
                    error_text = error_msg.get("msg", "Unknown error")
                    logger.error(f"Websocket error {error_code}: {error_text}")
                else:
                    logger.debug(f"Received unknown message type: {msg_type}, data keys: {list(data.keys())}")
                
                # Reset reconnect delay on successful message
                reconnect_delay = 1
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Websocket connection closed, attempting to reconnect...")
                await self._reconnect_websocket(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
            except Exception as e:
                logger.error(f"Error in websocket message handler: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _reconnect_websocket(self, delay: float) -> None:
        """Reconnect to websocket after a delay.
        
        Args:
            delay: Delay in seconds before reconnecting.
        """
        await asyncio.sleep(delay)
        
        if not self._ws_running:
            return
        
        try:
            # Close old connection if exists
            if self._ws_connection:
                try:
                    await self._ws_connection.close()
                except Exception:
                    pass
                self._ws_connection = None
            
            # Reconnect with authentication
            headers = {}
            if self._api_key_id and self._private_key_content:
                # Generate authentication headers (same as initial connection)
                timestamp = str(int(time.time() * 1000))
                method = "GET"
                path = "/trade-api/ws/v2"
                msg_string = timestamp + method + path
                
                try:
                    from cryptography.hazmat.primitives import hashes, serialization
                    from cryptography.hazmat.primitives.asymmetric import padding
                    from cryptography.hazmat.backends import default_backend
                    
                    # Load private key - ensure it's bytes
                    if isinstance(self._private_key_content, str):
                        private_key_bytes = self._private_key_content.encode('utf-8')
                    else:
                        private_key_bytes = self._private_key_content
                    
                    private_key = serialization.load_pem_private_key(
                        private_key_bytes,
                        password=None,
                        backend=default_backend()
                    )
                    
                    # Sign using RSA-PSS
                    signature = private_key.sign(
                        msg_string.encode('utf-8'),
                        padding.PSS(
                            mgf=padding.MGF1(hashes.SHA256()),
                            salt_length=padding.PSS.DIGEST_LENGTH
                        ),
                        hashes.SHA256()
                    )
                    signature_b64 = base64.b64encode(signature).decode('utf-8')
                    
                    headers['KALSHI-ACCESS-KEY'] = self._api_key_id
                    headers['KALSHI-ACCESS-SIGNATURE'] = signature_b64
                    headers['KALSHI-ACCESS-TIMESTAMP'] = timestamp
                except Exception as e:
                    logger.error(f"Failed to generate signature for reconnect: {e}", exc_info=True)
                    raise
            
            connect_kwargs = {
                'ping_interval': 30,
                'ping_timeout': 10
            }
            if headers:
                connect_kwargs['additional_headers'] = list(headers.items())
            
            self._ws_connection = await websockets.connect(
                self._ws_url,
                **connect_kwargs
            )
            
            # Resubscribe to all markets in batch
            if self._ws_subscriptions:
                tickers = list(self._ws_subscriptions.keys())
                subscribe_msg = {
                    "id": self._message_id,
                    "cmd": "subscribe",
                    "params": {
                        "channels": ["orderbook_delta"],
                        "market_tickers": tickers
                    }
                }
                self._message_id += 1
                try:
                    await self._ws_connection.send(json.dumps(subscribe_msg))
                    logger.info(f"Resubscribed to {len(tickers)} Kalshi markets")
                except Exception as e:
                    logger.warning(f"Failed to resubscribe to markets: {e}")
            
            logger.info("Reconnected to Kalshi websocket")
        except Exception as e:
            logger.error(f"Failed to reconnect to websocket: {e}")
    
    def _parse_websocket_orderbook(self, data: Dict[str, Any]) -> OrderBook:
        """Parse websocket orderbook message into OrderBook model.
        
        Handles both orderbook_snapshot (full orderbook) and orderbook_delta (incremental updates).
        According to docs: https://docs.kalshi.com/getting_started/quick_start_websockets
        
        Args:
            data: Raw websocket message data with structure: {"type": "...", "data": {...}}
        
        Returns:
            OrderBook instance.
        """
        # Extract data from message structure
        msg_data = data.get("data", data)
        ticker = msg_data.get("market_ticker", "")
        msg_type = data.get("type")
        
        # For orderbook_snapshot and orderbook_delta, the orderbook data is in the "data" field
        # Use the data field directly for normalization
        orderbook_data = msg_data
        
        # Use existing normalization logic
        return self._normalize_orderbook(ticker, orderbook_data)
    
    def is_websocket_connected(self) -> bool:
        """Check if websocket is connected.
        
        Returns:
            True if connected, False otherwise.
        """
        return self._ws_connection is not None and self._ws_running
