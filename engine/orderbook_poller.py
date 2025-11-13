"""Orderbook poller for fetching and converting orderbooks from exchanges."""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from exchange.models import OrderBook
from exchange.clients.kalshi_client import KalshiClient
from exchange.clients.polymarket_client import PolymarketClient
from exchange.errors import PolymarketAPIError, KalshiAPIError
from db.models import OrderbookSnapshot, MarketPair, DatabaseMarket
from db.client import SupabaseClient
from .errors import PollingError

logger = logging.getLogger(__name__)


class OrderbookPoller:
    """Polls orderbooks from exchanges and converts to storage format."""
    
    def __init__(
        self,
        kalshi_client: Optional[KalshiClient] = None,
        polymarket_client: Optional[PolymarketClient] = None,
        db_client: Optional[SupabaseClient] = None
    ):
        """Initialize the orderbook poller.
        
        Args:
            kalshi_client: Kalshi client instance. If None, creates a new one.
            polymarket_client: Polymarket client instance. If None, creates a new one.
            db_client: Database client instance. If None, creates a new one.
        """
        self.kalshi_client = kalshi_client or KalshiClient()
        self.polymarket_client = polymarket_client or PolymarketClient()
        self.db_client = db_client or SupabaseClient()
    
    def poll_market_pair(
        self,
        market_pair: MarketPair
    ) -> Tuple[Optional[OrderbookSnapshot], Optional[OrderbookSnapshot]]:
        """Poll orderbooks for both markets in a pair.
        
        Args:
            market_pair: MarketPair instance.
            
        Returns:
            Tuple of (orderbook1, orderbook2) OrderbookSnapshots. Either may be None if polling failed.
        """
        # Get market details from database
        market1 = self._get_market_by_id(market_pair.market_1_id)
        market2 = self._get_market_by_id(market_pair.market_2_id)
        
        if not market1 or not market2:
            logger.warning(f"Could not find markets for pair {market_pair.id}")
            return None, None
        
        # Poll orderbooks
        orderbook1 = self._poll_single_market(market1)
        orderbook2 = self._poll_single_market(market2)
        
        return orderbook1, orderbook2
    
    def _poll_single_market(self, market: DatabaseMarket) -> Optional[OrderbookSnapshot]:
        """Poll orderbook for a single market.
        
        Args:
            market: DatabaseMarket instance.
            
        Returns:
            OrderbookSnapshot if successful, None otherwise.
        """
        try:
            # Get the appropriate client
            if market.exchange == 'kalshi':
                client = self.kalshi_client
                orderbook_id = market.market_id
            elif market.exchange == 'polymarket':
                client = self.polymarket_client
                # For Polymarket, we need token_id, not market_id (slug)
                orderbook_id = self._get_polymarket_token_id(market)
                if not orderbook_id:
                    logger.warning(f"No token_id found for Polymarket market {market.market_id}, skipping orderbook")
                    return None
            else:
                logger.error(f"Unknown exchange: {market.exchange}")
                return None
            
            # Fetch orderbook
            orderbook = client.fetch_orderbook(orderbook_id)
            
            # Convert to storage format
            snapshot = self._convert_orderbook_to_snapshot(orderbook, market)
            
            return snapshot
            
        except (PolymarketAPIError, KalshiAPIError) as e:
            # Check if this is a "not found" error (expected case - market has no orderbook)
            error_msg = str(e).lower()
            if '404' in str(e) or 'not found' in error_msg or 'no orderbook exists' in error_msg:
                logger.debug(f"Orderbook not available for {market.market_id} ({market.exchange}): {e}")
                return None  # Skip markets without orderbooks (expected)
            # For other API errors, re-raise as they might be critical
            logger.error(f"API error polling orderbook for {market.market_id} ({market.exchange}): {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to poll orderbook for {market.market_id} ({market.exchange}): {e}")
            raise
    
    def _get_polymarket_token_id(self, market: DatabaseMarket) -> Optional[str]:
        """Extract token_id from Polymarket market's extra field.
        
        If token_id is not in the database, attempts to fetch it from the API.
        
        Args:
            market: DatabaseMarket instance for Polymarket.
            
        Returns:
            token_id string if found, None otherwise.
        """
        import json
        
        # First try to get from extra field
        if market.extra:
            # Try direct token_id first
            token_id = market.extra.get('token_id')
            if token_id:
                return str(token_id)
            
            # Try clobTokenIds (can be JSON string, list, or string)
            clob_tokens = market.extra.get('clobTokenIds')
            if clob_tokens:
                # If it's a string, try to parse as JSON
                if isinstance(clob_tokens, str):
                    try:
                        parsed = json.loads(clob_tokens)
                        if isinstance(parsed, list) and len(parsed) > 0:
                            return str(parsed[0])  # Take first token_id
                        elif isinstance(parsed, str):
                            return parsed
                    except (json.JSONDecodeError, ValueError):
                        # If not JSON, use as-is
                        return clob_tokens
                elif isinstance(clob_tokens, list) and len(clob_tokens) > 0:
                    return str(clob_tokens[0])  # Take first token_id
        
        # Fallback: fetch market details from API if token_id is missing
        try:
            logger.debug(f"Fetching market details for {market.market_id} to get token_id")
            api_market = self.polymarket_client.fetch_market_details(market.market_id)
            
            if api_market and api_market.metadata and api_market.metadata.extra:
                # Try to extract token_id from API response
                token_id = api_market.metadata.extra.get('token_id')
                if token_id:
                    return str(token_id)
                
                # Try clobTokenIds
                clob_tokens = api_market.metadata.extra.get('clobTokenIds')
                if clob_tokens:
                    if isinstance(clob_tokens, str):
                        try:
                            parsed = json.loads(clob_tokens)
                            if isinstance(parsed, list) and len(parsed) > 0:
                                return str(parsed[0])
                            elif isinstance(parsed, str):
                                return parsed
                        except (json.JSONDecodeError, ValueError):
                            return clob_tokens
                    elif isinstance(clob_tokens, list) and len(clob_tokens) > 0:
                        return str(clob_tokens[0])
        except Exception as e:
            logger.warning(f"Failed to fetch market details for {market.market_id}: {e}")
        
        return None
    
    def _convert_orderbook_to_snapshot(
        self,
        orderbook: OrderBook,
        market: DatabaseMarket
    ) -> OrderbookSnapshot:
        """Convert OrderBook model to OrderbookSnapshot format.
        
        Args:
            orderbook: OrderBook instance from exchange.
            market: DatabaseMarket instance.
            
        Returns:
            OrderbookSnapshot instance.
        """
        if market.exchange == 'kalshi':
            return self._convert_kalshi_orderbook(orderbook, market)
        elif market.exchange == 'polymarket':
            return self._convert_polymarket_orderbook(orderbook, market)
        else:
            raise ValueError(f"Unknown exchange: {market.exchange}")
    
    def _convert_kalshi_orderbook(
        self,
        orderbook: OrderBook,
        market: DatabaseMarket
    ) -> OrderbookSnapshot:
        """Convert Kalshi OrderBook to OrderbookSnapshot.
        
        Kalshi orderbook metadata contains the raw yes/no structure.
        The normalized OrderBook has bids/asks that combine yes and no sides.
        We need to extract the original yes/no structure from metadata.
        """
        metadata = orderbook.metadata or {}
        
        # Try to extract yes/no structure from raw metadata
        data = metadata
        if isinstance(metadata, dict) and 'orderbook' in metadata:
            data = metadata['orderbook']
        
        yes_bids = []
        yes_asks = []
        no_bids = []
        no_asks = []
        
        # Check if we have yes/no structure in metadata
        if 'yes' in data and 'no' in data:
            yes_data = data.get('yes')
            no_data = data.get('no')
            
            # Handle dictionary format with bids/asks
            if isinstance(yes_data, dict):
                yes_bids_raw = yes_data.get('bids', [])
                yes_asks_raw = yes_data.get('asks', [])
                
                # Convert to our format
                yes_bids = [{'price': float(entry.get('price', entry.get('yes_price', 0))), 'quantity': float(entry.get('quantity', entry.get('size', 0)))} for entry in yes_bids_raw]
                yes_asks = [{'price': float(entry.get('price', entry.get('yes_price', 0))), 'quantity': float(entry.get('quantity', entry.get('size', 0)))} for entry in yes_asks_raw]
            
            # Handle list format: yes list = YES BIDS (Kalshi only returns bids)
            elif isinstance(yes_data, list):
                for entry in yes_data:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        price_cents = float(entry[0])
                        price = price_cents / 100.0
                        quantity = float(entry[1])
                        yes_bids.append({'price': price, 'quantity': quantity})
                        # YES bid at price X = NO ask at price (1-X)
                        no_asks.append({'price': 1.0 - price, 'quantity': quantity})
            
            # Handle dictionary format with bids/asks for NO
            if isinstance(no_data, dict):
                no_bids_raw = no_data.get('bids', [])
                no_asks_raw = no_data.get('asks', [])
                
                # Convert to our format (NO prices, not inverted)
                no_bids = [{'price': float(entry.get('price', entry.get('no_price', 0))), 'quantity': float(entry.get('quantity', entry.get('size', 0)))} for entry in no_bids_raw]
                no_asks = [{'price': float(entry.get('price', entry.get('no_price', 0))), 'quantity': float(entry.get('quantity', entry.get('size', 0)))} for entry in no_asks_raw]
                # NO bids at price X = YES asks at price (1-X)
                for no_bid in no_bids:
                    yes_asks.append({'price': 1.0 - no_bid['price'], 'quantity': no_bid['quantity']})
                # NO asks at price X = YES bids at price (1-X)
                for no_ask in no_asks:
                    yes_bids.append({'price': 1.0 - no_ask['price'], 'quantity': no_ask['quantity']})
            
            # Handle list format: no list = NO BIDS (Kalshi only returns bids)
            elif isinstance(no_data, list):
                for entry in no_data:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        no_price_cents = float(entry[0])
                        no_price = no_price_cents / 100.0
                        quantity = float(entry[1])
                        no_bids.append({'price': no_price, 'quantity': quantity})
                        # NO bid at price X = YES ask at price (1-X)
                        yes_asks.append({'price': 1.0 - no_price, 'quantity': quantity})
        
        # If we still don't have yes/no structure, try to extract from OrderBookEntry metadata
        # The entries might have 'side' and 'type' metadata from _normalize_orderbook
        if not yes_bids and not yes_asks:
            # Separate YES and NO entries based on metadata
            for entry in orderbook.bids:
                entry_meta = entry.metadata or {}
                if entry_meta.get('side') == 'yes' and entry_meta.get('type') == 'bid':
                    yes_bids.append({'price': float(entry.price), 'quantity': float(entry.quantity)})
                    # YES bid at price X = NO ask at price (1-X)
                    no_asks.append({'price': 1.0 - float(entry.price), 'quantity': float(entry.quantity)})
                elif entry_meta.get('side') == 'no' and entry_meta.get('type') == 'bid':
                    # NO bid at price X = YES ask at price (1-X)
                    no_price = entry_meta.get('no_price', float(entry.price))
                    no_bids.append({'price': float(no_price), 'quantity': float(entry.quantity)})
                    yes_asks.append({'price': 1.0 - float(no_price), 'quantity': float(entry.quantity)})
            
            for entry in orderbook.asks:
                entry_meta = entry.metadata or {}
                if entry_meta.get('side') == 'yes' and entry_meta.get('type') == 'ask':
                    yes_asks.append({'price': float(entry.price), 'quantity': float(entry.quantity)})
                    # YES ask at price X = NO bid at price (1-X)
                    no_bids.append({'price': 1.0 - float(entry.price), 'quantity': float(entry.quantity)})
                elif entry_meta.get('side') == 'no' and entry_meta.get('type') == 'ask':
                    # NO ask at price X = YES bid at price (1-X)
                    no_price = entry_meta.get('no_price', float(entry.price))
                    no_asks.append({'price': float(no_price), 'quantity': float(entry.quantity)})
                    yes_bids.append({'price': 1.0 - float(no_price), 'quantity': float(entry.quantity)})
                elif entry_meta.get('derived_from') == 'no_bid':
                    # This is a YES ask derived from a NO bid
                    yes_asks.append({'price': float(entry.price), 'quantity': float(entry.quantity)})
                    no_price = entry_meta.get('no_price', 1.0 - float(entry.price))
                    no_bids.append({'price': float(no_price), 'quantity': float(entry.quantity)})
        
        # Last resort: If we still don't have structure, this is an error case
        # Don't make assumptions - log a warning
        if not yes_bids and not yes_asks:
            logger.warning(f"Could not extract yes/no structure from Kalshi orderbook for market {market.market_id}. Orderbook may be incomplete.")
            # Return empty orderbook snapshot rather than incorrect data
            return OrderbookSnapshot(
                market_id=market.id,
                exchange=market.exchange,
                yes_bids=[],
                yes_asks=[],
                no_bids=[],
                no_asks=[],
                timestamp=orderbook.timestamp or datetime.now(timezone.utc)
            )
        
        # Sort: bids descending, asks ascending
        yes_bids.sort(key=lambda x: x['price'], reverse=True)
        yes_asks.sort(key=lambda x: x['price'])
        no_bids.sort(key=lambda x: x['price'], reverse=True)
        no_asks.sort(key=lambda x: x['price'])
        
        return OrderbookSnapshot(
            market_id=market.id,
            exchange=market.exchange,
            yes_bids=yes_bids,
            yes_asks=yes_asks,
            no_bids=no_bids,
            no_asks=no_asks,
            timestamp=orderbook.timestamp or datetime.now(timezone.utc)
        )
    
    def _convert_polymarket_orderbook(
        self,
        orderbook: OrderBook,
        market: DatabaseMarket
    ) -> OrderbookSnapshot:
        """Convert Polymarket OrderBook to OrderbookSnapshot.
        
        Polymarket CLOB API returns bids/asks for the yes side.
        We calculate no side by inverting prices.
        """
        # Polymarket bids/asks represent yes side
        yes_bids = [{'price': float(entry.price), 'quantity': float(entry.quantity)} for entry in orderbook.bids]
        yes_asks = [{'price': float(entry.price), 'quantity': float(entry.quantity)} for entry in orderbook.asks]
        
        # Invert for no side: no_bid = 1 - yes_ask, no_ask = 1 - yes_bid
        no_bids = [{'price': 1.0 - float(entry.price), 'quantity': float(entry.quantity)} for entry in orderbook.asks]
        no_asks = [{'price': 1.0 - float(entry.price), 'quantity': float(entry.quantity)} for entry in orderbook.bids]
        
        # Sort: bids descending, asks ascending
        yes_bids.sort(key=lambda x: x['price'], reverse=True)
        yes_asks.sort(key=lambda x: x['price'])
        no_bids.sort(key=lambda x: x['price'], reverse=True)
        no_asks.sort(key=lambda x: x['price'])
        
        return OrderbookSnapshot(
            market_id=market.id,
            exchange=market.exchange,
            yes_bids=yes_bids,
            yes_asks=yes_asks,
            no_bids=no_bids,
            no_asks=no_asks,
            timestamp=orderbook.timestamp or datetime.now(timezone.utc)
        )
    
    def _get_market_by_id(self, market_uuid: str) -> Optional[DatabaseMarket]:
        """Get market by UUID from database.
        
        Args:
            market_uuid: UUID of the market.
            
        Returns:
            DatabaseMarket if found, None otherwise.
        """
        try:
            # Use the db_client's get_markets_by_exchange and filter, or query directly
            response = self.db_client.client.table("markets").select("*").eq("id", market_uuid).limit(1).execute()
            if response.data and len(response.data) > 0:
                return DatabaseMarket.from_dict(response.data[0])
        except Exception as e:
            logger.error(f"Failed to get market by UUID {market_uuid}: {e}")
        return None

