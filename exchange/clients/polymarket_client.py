"""Polymarket exchange client implementation using native Polymarket API."""

import requests
import logging
import time
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime

from ..base import ExchangeClient
from ..models import Market, OrderBook, OrderBookEntry, MarketMetadata
from ..errors import PolymarketAPIError
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class PolymarketClient(ExchangeClient):
    """Client for interacting with Polymarket exchange via native API.
    
    This client implements the ExchangeClient interface and uses Polymarket's
    Gamma API (REST) and CLOB API to fetch markets, orderbooks, and market details.
    
    Reference: https://docs.polymarket.com/developers/gamma-markets-api/fetch-markets-guide
    """
    
    GAMMA_API_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        gamma_api_url: Optional[str] = None,
        clob_url: Optional[str] = None,
        rate_limit_delay: float = 0.1
    ):
        """Initialize the Polymarket client.
        
        Args:
            api_key: Your Polymarket API key (optional for public endpoints).
            gamma_api_url: Gamma API URL (default: https://gamma-api.polymarket.com).
            clob_url: CLOB API URL (default: https://clob.polymarket.com).
            rate_limit_delay: Minimum delay between requests in seconds (default: 0.1).
        """
        self.gamma_api_url = (gamma_api_url or self.GAMMA_API_URL).rstrip('/')
        self.clob_url = (clob_url or self.CLOB_URL).rstrip('/')
        self.api_key = api_key
        self.exchange_name = "polymarket"
        self.rate_limiter = RateLimiter(min_delay=rate_limit_delay)
        self.session = requests.Session()
        
        # Set headers
        self.session.headers.update({
            'Content-Type': 'application/json',
        })
        
        # Add authentication if provided
        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}',
            })

    def _make_gamma_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        retries: int = 3
    ) -> dict:
        """Make a REST request to Polymarket Gamma API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path (e.g., '/events').
            params: Query parameters.
            retries: Number of retry attempts on failure (default: 3).
            
        Returns:
            Dict containing the JSON response.
            
        Raises:
            PolymarketAPIError: If the request fails after retries.
        """
        url = f"{self.gamma_api_url}{endpoint}"
        
        for attempt in range(retries):
            try:
                # Rate limit before request
                self.rate_limiter.wait_if_needed()
                
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    timeout=30
                )
                
                self.rate_limiter.record_request()
                
                # Handle rate limit errors
                if response.status_code == 429:
                    logger.warning(f"Rate limit hit (429), backing off...")
                    self.rate_limiter.handle_rate_limit_error()
                    self.rate_limiter.wait_if_needed()
                    if attempt < retries - 1:
                        continue  # Retry
                
                response.raise_for_status()
                self.rate_limiter.reset_delay()
                return response.json()
                
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < retries - 1:
                    continue  # Retry on rate limit
                error_msg = f"HTTP {response.status_code}: {response.text}"
                raise PolymarketAPIError(error_msg) from e
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    logger.warning(f"Request failed, retrying ({attempt + 1}/{retries}): {str(e)}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise PolymarketAPIError(f"Request failed: {str(e)}") from e
        
        raise PolymarketAPIError(f"Request failed after {retries} attempts")

    def _make_clob_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        retries: int = 3
    ) -> dict:
        """Make a REST request to Polymarket CLOB API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path (e.g., '/book').
            params: Query parameters.
            retries: Number of retry attempts on failure (default: 3).
            
        Returns:
            Dict containing the JSON response.
            
        Raises:
            PolymarketAPIError: If the request fails after retries.
        """
        url = f"{self.clob_url}{endpoint}"
        
        for attempt in range(retries):
            try:
                # Rate limit before request
                self.rate_limiter.wait_if_needed()
                
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    timeout=30
                )
                
                self.rate_limiter.record_request()
                
                # Handle rate limit errors
                if response.status_code == 429:
                    logger.warning(f"Rate limit hit (429), backing off...")
                    self.rate_limiter.handle_rate_limit_error()
                    self.rate_limiter.wait_if_needed()
                    if attempt < retries - 1:
                        continue  # Retry
                
                response.raise_for_status()
                self.rate_limiter.reset_delay()
                return response.json()
                
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < retries - 1:
                    continue  # Retry on rate limit
                error_msg = f"HTTP {response.status_code}: {response.text}"
                raise PolymarketAPIError(error_msg) from e
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    logger.warning(f"Request failed, retrying ({attempt + 1}/{retries}): {str(e)}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise PolymarketAPIError(f"Request failed: {str(e)}") from e
        
        raise PolymarketAPIError(f"Request failed after {retries} attempts")

    def fetch_all_markets(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        closed: bool = False,
        order: str = "id",
        ascending: bool = False,
        max_pages: Optional[int] = None,
        page_size: int = 100,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Market]:
        """Retrieve all markets from Polymarket.
        
        Uses Polymarket Gamma API to fetch all available markets. Handles pagination
        automatically to fetch all markets across multiple pages. The response is normalized
        to the common Market model.
        
        Args:
            limit: Maximum number of markets to return total (optional, None = all).
            offset: Starting offset (optional, usually 0).
            closed: Whether to include closed markets (default: False).
            order: Field to order by (default: "id").
            ascending: Whether to sort ascending (default: False).
            max_pages: Maximum number of pages to fetch (optional, None = all).
            page_size: Number of markets per page (default: 100).
            progress_callback: Optional callback function(page_num, total_markets) for progress updates.
        
        Returns:
            List[Market]: A list of all available markets.
            
        Raises:
            PolymarketAPIError: If the API request fails.
        """
        all_markets = []
        page_num = 0
        current_offset = offset or 0
        total_fetched = 0
        
        try:
            while True:
                # Check if we've hit the limit
                if limit and total_fetched >= limit:
                    break
                
                # Check if we've hit max pages
                if max_pages and page_num >= max_pages:
                    break
                
                # Calculate how many to request this page
                page_limit = page_size
                if limit:
                    remaining = limit - total_fetched
                    page_limit = min(remaining, page_size)
                
                try:
                    # Use Gamma API /events endpoint to fetch markets
                    # According to docs: https://docs.polymarket.com/developers/gamma-markets-api/fetch-markets-guide
                    params = {
                        'order': order,
                        'ascending': str(ascending).lower(),
                        'closed': str(closed).lower(),
                        'limit': page_limit,
                        'offset': current_offset,
                    }
                    
                    response = self._make_gamma_request('GET', '/events', params=params)
                    page_markets = []
                    
                    # Gamma API returns events (which contain markets)
                    # Response might be a list or dict with 'data' key
                    events_data = response
                    if isinstance(response, dict):
                        if 'data' in response:
                            events_data = response['data']
                        elif 'events' in response:
                            events_data = response['events']
                    
                    if isinstance(events_data, list):
                        for event_raw in events_data:
                            # Check if we've hit the limit before processing more markets
                            if limit and total_fetched >= limit:
                                break
                            
                            # Each event may contain multiple markets
                            if 'markets' in event_raw and isinstance(event_raw['markets'], list):
                                for market_raw in event_raw['markets']:
                                    # Check limit before adding each market
                                    if limit and total_fetched >= limit:
                                        break
                                    market = self._normalize_market(market_raw, event_raw)
                                    if market:
                                        page_markets.append(market)
                                        total_fetched = len(all_markets) + len(page_markets)
                            else:
                                # Treat the event itself as a market
                                # Check limit before adding
                                if limit and total_fetched >= limit:
                                    break
                                market = self._normalize_market(event_raw)
                                if market:
                                    page_markets.append(market)
                                    total_fetched = len(all_markets) + len(page_markets)
                    
                    # If no markets returned, we're done
                    if not page_markets:
                        break
                    
                    all_markets.extend(page_markets)
                    total_fetched = len(all_markets)
                    page_num += 1
                    
                    # Progress callback
                    if progress_callback:
                        progress_callback(page_num, total_fetched)
                    
                    # Check if we've hit the limit after processing this page
                    if limit and total_fetched >= limit:
                        # Trim to exact limit if we went over
                        if len(all_markets) > limit:
                            all_markets = all_markets[:limit]
                            total_fetched = limit
                        break
                    
                    # If we got fewer results than requested, we're at the end
                    if len(page_markets) < page_limit:
                        break
                    
                    # Update offset for next page
                    current_offset += page_limit
                    
                    logger.info(f"Fetched page {page_num}: {len(page_markets)} markets (total: {total_fetched})")
                    
                except PolymarketAPIError as e:
                    # For API errors, log and continue if we have some markets
                    logger.warning(f"Error fetching page {page_num}: {str(e)}")
                    if all_markets:
                        logger.info(f"Returning {len(all_markets)} markets fetched so far")
                        break
                    else:
                        raise
                
        except Exception as e:
            if all_markets:
                logger.warning(f"Error during pagination, returning {len(all_markets)} markets: {str(e)}")
                return all_markets
            raise PolymarketAPIError(f"Failed to fetch Polymarket markets: {str(e)}") from e
        
        logger.info(f"Fetched {len(all_markets)} total markets across {page_num} pages")
        return all_markets

    def fetch_orderbook(self, market_id: str) -> OrderBook:
        """Get the full order book for a specific Polymarket market.
        
        Args:
            market_id: The Polymarket token_id (required for CLOB API).
                      Format should be a hex string like "0x1b6f76e5b8587ee896c35847e12d11e75290a8c3934c5952e8a9d6e4c6f03cfa"
            
        Returns:
            OrderBook: The full order book with bids and asks.
            
        Raises:
            PolymarketAPIError: If the API request fails.
        """
        try:
            # CLOB API endpoint for orderbook
            # Documentation: GET /book?token_id={token_id}
            # The token_id must be a valid token identifier (hex string)
            response = self._make_clob_request('GET', '/book', params={'token_id': market_id})
            
            # Normalize the response to OrderBook model
            return self._normalize_orderbook(market_id, response)
        except PolymarketAPIError as e:
            # Re-raise with more context about token_id requirement
            error_msg = str(e)
            if '404' in error_msg or 'not found' in error_msg.lower():
                raise PolymarketAPIError(
                    f"Orderbook not found for token_id '{market_id}'. "
                    f"Ensure token_id is a valid hex string (e.g., '0x1b6f76e5...'). "
                    f"Original error: {error_msg}"
                ) from e
            raise
        except Exception as e:
            raise PolymarketAPIError(f"Failed to fetch Polymarket orderbook for {market_id}: {str(e)}") from e

    def fetch_market_details(self, market_id: str) -> Market:
        """Get market rules, name, and all associated metadata.
        
        Args:
            market_id: The Polymarket market identifier (slug, condition_id, or token_id).
            
        Returns:
            Market: Complete market information.
            
        Raises:
            PolymarketAPIError: If the API request fails.
        """
        try:
            # Try to fetch by slug first (most common)
            # Gamma API: GET /events/slug/{slug} or GET /markets/slug/{slug}
            try:
                response = self._make_gamma_request('GET', f'/events/slug/{market_id}')
            except PolymarketAPIError:
                # Try markets endpoint if events doesn't work
                response = self._make_gamma_request('GET', f'/markets/slug/{market_id}')
            
            # Handle response structure
            market_data = response
            if isinstance(response, dict):
                if 'data' in response:
                    market_data = response['data']
                elif 'event' in response:
                    event = response['event']
                    # If event has markets, use the first one
                    if 'markets' in event and isinstance(event['markets'], list) and len(event['markets']) > 0:
                        market_data = event['markets'][0]
                    else:
                        market_data = event
                elif 'market' in response:
                    market_data = response['market']
            
            return self._normalize_market(market_data)
        except PolymarketAPIError:
            raise
        except Exception as e:
            raise PolymarketAPIError(f"Failed to fetch Polymarket market details for {market_id}: {str(e)}") from e

    def _normalize_market(self, market_data: dict, event_data: Optional[dict] = None) -> Market:
        """Normalize Polymarket market data to the common Market model.
        
        Args:
            market_data: Raw market data from Polymarket API.
            event_data: Optional event data that contains the market.
            
        Returns:
            Market: Normalized market object.
        """
        # Merge event data if provided (events contain market metadata)
        if event_data:
            # Event-level fields take precedence
            merged_data = {**market_data, **{k: v for k, v in event_data.items() if k not in market_data}}
        else:
            merged_data = market_data
        
        # Extract market ID - Polymarket uses 'slug', 'condition_id', or 'token_id'
        market_id = (
            merged_data.get('slug') or
            market_data.get('slug') or
            merged_data.get('condition_id') or
            market_data.get('conditionId') or
            merged_data.get('conditionId') or
            market_data.get('token_id') or
            merged_data.get('id') or
            market_data.get('id') or
            merged_data.get('market_id') or
            ''
        )
        
        # Extract market name
        name = (
            merged_data.get('question') or
            market_data.get('question') or
            merged_data.get('title') or
            market_data.get('title') or
            merged_data.get('name') or
            market_data.get('name') or
            merged_data.get('market_title') or
            ''
        )
        
        # Extract rules/description
        rules = (
            merged_data.get('description') or
            market_data.get('description') or
            merged_data.get('rules') or
            market_data.get('rules') or
            merged_data.get('resolutionRules') or
            market_data.get('resolution_rules') or
            merged_data.get('subtitle') or
            ''
        )
        
        # Extract resolution date/time
        resolve_date = None
        resolve_time = None
        resolution_date = (
            merged_data.get('resolution_date') or
            merged_data.get('endDate') or
            merged_data.get('end_date') or
            market_data.get('endDate') or
            market_data.get('end_date')
        )
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
            category=(
                merged_data.get('category') or
                merged_data.get('groupItemTitle') or
                merged_data.get('group_item_title') or
                market_data.get('category')
            ),
            subcategory=merged_data.get('subcategory') or market_data.get('subcategory'),
            tags=merged_data.get('tags') or market_data.get('tags'),
            description=merged_data.get('description') or market_data.get('description') or merged_data.get('subtitle'),
            image_url=(
                merged_data.get('imageUrl') or
                merged_data.get('image_url') or
                market_data.get('imageUrl') or
                market_data.get('image')
            ),
            liquidity=merged_data.get('liquidity') or market_data.get('liquidity') or merged_data.get('liquidity_usd'),
            volume=(
                merged_data.get('volume') or
                market_data.get('volume') or
                merged_data.get('volume_usd') or
                market_data.get('total_volume')
            ),
            extra={
                'outcomes': merged_data.get('outcomes') or market_data.get('outcomes'),
                'active': merged_data.get('active') or market_data.get('active'),
                'closed': merged_data.get('closed') or market_data.get('closed'),
                'new': merged_data.get('new') or market_data.get('new'),
                'end_date_iso': merged_data.get('end_date_iso') or market_data.get('end_date_iso'),
                'start_date_iso': merged_data.get('start_date_iso') or market_data.get('start_date_iso'),
                'clobTokenIds': merged_data.get('clobTokenIds') or market_data.get('clob_token_ids') or market_data.get('clobTokenIds'),
                'conditionId': merged_data.get('conditionId') or merged_data.get('condition_id') or market_data.get('conditionId'),
                'token_id': market_data.get('token_id') or merged_data.get('token_id'),
            }
        )
        
        return Market(
            market_id=str(market_id),
            name=name,
            rules=rules,
            metadata=metadata,
            exchange=self.exchange_name,
            extra={**merged_data, **market_data}
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
        
        # Polymarket CLOB API typically has 'bids' and 'asks' arrays
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
