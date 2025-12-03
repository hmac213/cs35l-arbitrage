"""Websocket-based orderbook streamer for real-time orderbook updates."""

import logging
import asyncio
from typing import Dict, Optional, Callable, Set, Any, Any
from datetime import datetime, timezone

from exchange.clients.kalshi_client import KalshiClient
from exchange.clients.polymarket_client import PolymarketClient
from exchange.models import OrderBook
from db.client import SupabaseClient
from db.models import MarketPair, DatabaseMarket, OrderbookSnapshot
from .orderbook_poller import OrderbookPoller

logger = logging.getLogger(__name__)


class OrderbookStreamer:
    """Manages websocket connections for real-time orderbook streaming.
    
    Subscribes to orderbook updates for markets in active pairs and converts
    them to OrderbookSnapshot format for storage.
    """
    
    def __init__(
        self,
        kalshi_client: Optional[KalshiClient] = None,
        polymarket_client: Optional[PolymarketClient] = None,
        db_client: Optional[SupabaseClient] = None,
        orderbook_poller: Optional[OrderbookPoller] = None,
        update_queue: Optional[Any] = None
    ):
        """Initialize the orderbook streamer.
        
        Args:
            kalshi_client: Kalshi client instance. If None, creates a new one.
            polymarket_client: Polymarket client instance. If None, creates a new one.
            db_client: Database client instance. If None, creates a new one.
            orderbook_poller: OrderbookPoller instance for conversion logic. If None, creates a new one.
            update_queue: OrderbookUpdateQueue instance for event-driven processing. If None, stores directly to DB.
        """
        self.kalshi_client = kalshi_client or KalshiClient()
        self.polymarket_client = polymarket_client or PolymarketClient()
        self.db_client = db_client or SupabaseClient()
        self.orderbook_poller = orderbook_poller or OrderbookPoller(
            kalshi_client=self.kalshi_client,
            polymarket_client=self.polymarket_client,
            db_client=self.db_client
        )
        self.update_queue = update_queue
        
        # Track subscriptions
        self._kalshi_subscriptions: Dict[str, str] = {}  # market_uuid -> ticker
        self._polymarket_subscriptions: Dict[str, str] = {}  # market_uuid -> token_id
        self._active_market_pairs: Set[str] = set()  # Set of market pair UUIDs
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_task: Optional[asyncio.Task] = None
        self._queue_loop: Optional[asyncio.AbstractEventLoop] = None  # Event loop where queue is running
    
    async def start(self) -> None:
        """Start the websocket streamer.
        
        Connects to both exchanges and subscribes to orderbook updates
        for all markets in active pairs.
        """
        if self._running:
            logger.warning("OrderbookStreamer is already running")
            return
        
        self._running = True
        
        # Create or get event loop
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        
        # Start async operations
        try:
            # Connect to websockets
            await self.kalshi_client.connect_websocket()
            await self.polymarket_client.connect_websocket()
            
            # Subscribe to all active market pairs
            await self._refresh_subscriptions()
            
            logger.info("OrderbookStreamer started")
        except Exception as e:
            logger.error(f"Failed to start OrderbookStreamer: {e}", exc_info=True)
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the websocket streamer and disconnect."""
        self._running = False
        
        # Unsubscribe from all markets
        await self._unsubscribe_all()
        
        # Disconnect websockets
        try:
            await self.kalshi_client.disconnect_websocket()
        except Exception as e:
            logger.warning(f"Error disconnecting Kalshi websocket: {e}")
        
        try:
            await self.polymarket_client.disconnect_websocket()
        except Exception as e:
            logger.warning(f"Error disconnecting Polymarket websocket: {e}")
        
        logger.info("OrderbookStreamer stopped")
    
    async def refresh_subscriptions(self) -> None:
        """Refresh subscriptions based on current market pairs.
        
        This should be called periodically to pick up new pairs or remove old ones.
        """
        if not self._running:
            return
        
        await self._refresh_subscriptions()
    
    async def _refresh_subscriptions(self) -> None:
        """Internal method to refresh subscriptions."""
        # Get all market pairs (run in executor to avoid blocking)
        loop = asyncio.get_event_loop()
        market_pairs = await loop.run_in_executor(None, self.db_client.get_all_market_pairs)
        current_pair_ids = {pair.id for pair in market_pairs}
        
        # Collect all unique market UUIDs
        all_market_uuids = set()
        for pair in market_pairs:
            all_market_uuids.add(pair.market_1_id)
            all_market_uuids.add(pair.market_2_id)
        
        # Batch fetch all markets in one query (run in executor)
        markets_dict = await loop.run_in_executor(
            None,
            self.db_client.get_markets_by_uuids,
            list(all_market_uuids)
        )
        
        # Collect all unique markets from all pairs
        kalshi_tickers = {}  # ticker -> (market_uuid, callback)
        polymarket_token_ids = {}  # token_id -> (market_uuid, callback)
        
        for pair in market_pairs:
            market1 = markets_dict.get(pair.market_1_id)
            market2 = markets_dict.get(pair.market_2_id)
            
            if not market1 or not market2:
                continue
            
            # Collect Kalshi markets
            if market1.exchange == 'kalshi' and market1.id not in self._kalshi_subscriptions:
                ticker = market1.market_id
                callback = self._create_orderbook_callback(market1)
                kalshi_tickers[ticker] = (market1.id, callback)
            
            if market2.exchange == 'kalshi' and market2.id not in self._kalshi_subscriptions:
                ticker = market2.market_id
                callback = self._create_orderbook_callback(market2)
                kalshi_tickers[ticker] = (market2.id, callback)
            
            # Collect Polymarket markets
            if market1.exchange == 'polymarket' and market1.id not in self._polymarket_subscriptions:
                token_id = self.orderbook_poller._get_polymarket_token_id(market1)
                if token_id:
                    callback = self._create_orderbook_callback(market1)
                    polymarket_token_ids[token_id] = (market1.id, callback)
            
            if market2.exchange == 'polymarket' and market2.id not in self._polymarket_subscriptions:
                token_id = self.orderbook_poller._get_polymarket_token_id(market2)
                if token_id:
                    callback = self._create_orderbook_callback(market2)
                    polymarket_token_ids[token_id] = (market2.id, callback)
        
        # Subscribe to all Kalshi markets at once
        if kalshi_tickers:
            tickers = list(kalshi_tickers.keys())
            callbacks = {ticker: callback for ticker, (_, callback) in kalshi_tickers.items()}
            try:
                await self.kalshi_client.subscribe_orderbooks_batch(tickers, callbacks)
                # Update subscriptions tracking
                for ticker, (market_uuid, _) in kalshi_tickers.items():
                    self._kalshi_subscriptions[market_uuid] = ticker
                logger.info(f"Subscribed to {len(tickers)} Kalshi markets")
            except Exception as e:
                logger.error(f"Failed to batch subscribe to Kalshi markets: {e}", exc_info=True)
        
        # Subscribe to all Polymarket markets at once (if Polymarket supports batch)
        if polymarket_token_ids:
            # For now, subscribe individually since we need to check if Polymarket supports batch
            # TODO: Add batch subscribe to PolymarketClient if supported
            success_count = 0
            for token_id, (market_uuid, callback) in polymarket_token_ids.items():
                try:
                    await self.polymarket_client.subscribe_orderbook(token_id, callback)
                    self._polymarket_subscriptions[market_uuid] = token_id
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to subscribe to Polymarket market {token_id}: {e}", exc_info=True)
            logger.info(f"Subscribed to {success_count}/{len(polymarket_token_ids)} Polymarket markets")
        
        self._active_market_pairs = current_pair_ids
    
    async def _subscribe_to_pair(self, pair: MarketPair) -> None:
        """Subscribe to orderbook updates for a market pair.
        
        Args:
            pair: MarketPair instance.
        """
        # Get market details
        market1 = self._get_market_by_id(pair.market_1_id)
        market2 = self._get_market_by_id(pair.market_2_id)
        
        if not market1 or not market2:
            logger.warning(f"Could not find markets for pair {pair.id}")
            return
        
        # Subscribe to market1
        await self._subscribe_to_market(market1)
        
        # Subscribe to market2
        await self._subscribe_to_market(market2)
    
    async def _subscribe_to_market(self, market: DatabaseMarket) -> None:
        """Subscribe to orderbook updates for a single market.
        
        Args:
            market: DatabaseMarket instance.
        """
        if market.exchange == 'kalshi':
            # Subscribe via Kalshi websocket
            if market.id in self._kalshi_subscriptions:
                return  # Already subscribed
            
            ticker = market.market_id
            callback = self._create_orderbook_callback(market)
            
            try:
                await self.kalshi_client.subscribe_orderbook(ticker, callback)
                self._kalshi_subscriptions[market.id] = ticker
                logger.debug(f"Subscribed to Kalshi market {ticker} (UUID: {market.id})")
            except Exception as e:
                logger.error(f"Failed to subscribe to Kalshi market {ticker}: {e}")
        
        elif market.exchange == 'polymarket':
            # Subscribe via Polymarket websocket
            if market.id in self._polymarket_subscriptions:
                return  # Already subscribed
            
            # Get token_id
            token_id = self.orderbook_poller._get_polymarket_token_id(market)
            if not token_id:
                logger.warning(f"No token_id found for Polymarket market {market.market_id}, skipping subscription")
                return
            
            callback = self._create_orderbook_callback(market)
            
            try:
                await self.polymarket_client.subscribe_orderbook(token_id, callback)
                self._polymarket_subscriptions[market.id] = token_id
                logger.debug(f"Subscribed to Polymarket market {token_id} (UUID: {market.id})")
            except Exception as e:
                logger.error(f"Failed to subscribe to Polymarket market {token_id}: {e}")
    
    async def _unsubscribe_from_pair(self, pair: MarketPair) -> None:
        """Unsubscribe from orderbook updates for a market pair.
        
        Args:
            pair: MarketPair instance.
        """
        # Get market details
        market1 = self._get_market_by_id(pair.market_1_id)
        market2 = self._get_market_by_id(pair.market_2_id)
        
        if market1:
            await self._unsubscribe_from_market(market1)
        
        if market2:
            await self._unsubscribe_from_market(market2)
    
    async def _unsubscribe_from_market(self, market: DatabaseMarket) -> None:
        """Unsubscribe from orderbook updates for a single market.
        
        Args:
            market: DatabaseMarket instance.
        """
        if market.exchange == 'kalshi':
            if market.id in self._kalshi_subscriptions:
                ticker = self._kalshi_subscriptions[market.id]
                try:
                    await self.kalshi_client.unsubscribe_orderbook(ticker)
                except Exception as e:
                    logger.warning(f"Error unsubscribing from Kalshi market {ticker}: {e}")
                del self._kalshi_subscriptions[market.id]
        
        elif market.exchange == 'polymarket':
            if market.id in self._polymarket_subscriptions:
                token_id = self._polymarket_subscriptions[market.id]
                try:
                    await self.polymarket_client.unsubscribe_orderbook(token_id)
                except Exception as e:
                    logger.warning(f"Error unsubscribing from Polymarket market {token_id}: {e}")
                del self._polymarket_subscriptions[market.id]
    
    async def _unsubscribe_all(self) -> None:
        """Unsubscribe from all markets."""
        # Unsubscribe from all Kalshi markets
        for market_id, ticker in list(self._kalshi_subscriptions.items()):
            try:
                await self.kalshi_client.unsubscribe_orderbook(ticker)
            except Exception as e:
                logger.warning(f"Error unsubscribing from Kalshi market {ticker}: {e}")
        self._kalshi_subscriptions.clear()
        
        # Unsubscribe from all Polymarket markets
        for market_id, token_id in list(self._polymarket_subscriptions.items()):
            try:
                await self.polymarket_client.unsubscribe_orderbook(token_id)
            except Exception as e:
                logger.warning(f"Error unsubscribing from Polymarket market {token_id}: {e}")
        self._polymarket_subscriptions.clear()
    
    def _create_orderbook_callback(self, market: DatabaseMarket) -> Callable[[OrderBook], None]:
        """Create a callback function for orderbook updates.
        
        Args:
            market: DatabaseMarket instance.
        
        Returns:
            Callback function that processes orderbook updates.
        """
        def callback(orderbook: OrderBook) -> None:
            """Process orderbook update and enqueue it for processing."""
            try:
                # Log callback invocation for diagnostics
                logger.debug(f"Callback invoked for {market.market_id}: bids={len(orderbook.bids)}, asks={len(orderbook.asks)}")
                
                # Check if this is an empty orderbook (no bids/asks)
                # Empty deltas are normal (no changes), but we should still process initial snapshots
                # to establish the state, even if they're empty
                is_empty = not orderbook.bids and not orderbook.asks
                
                # Convert OrderBook to OrderbookSnapshot
                snapshot = self.orderbook_poller._convert_orderbook_to_snapshot(orderbook, market)
                
                # Skip empty snapshots - they represent markets with no trading activity
                # We don't need to enqueue these as they won't trigger any arbitrage calculations
                # The conversion logic already logs these at DEBUG level
                if not snapshot.yes_bids and not snapshot.yes_asks and not snapshot.no_bids and not snapshot.no_asks:
                    logger.debug(f"Skipping empty snapshot for {market.market_id} (no orderbook data - market has no active trading)")
                    return
                
                # If update_queue is available, enqueue for event-driven processing
                if self.update_queue:
                    from .orderbook_update_queue import OrderbookUpdate
                    update = OrderbookUpdate(
                        market_id=market.id,
                        exchange=market.exchange,
                        orderbook=snapshot,
                        timestamp=snapshot.timestamp or datetime.now(timezone.utc)
                    )
                    # Enqueue asynchronously (non-blocking)
                    # Callback runs in executor thread, so we need to schedule on the queue's event loop
                    if self._queue_loop:
                        try:
                            # Check if loop is running (this might fail in executor thread, so catch it)
                            is_running = self._queue_loop.is_running()
                            if is_running:
                                # Schedule on the queue's event loop (which is in a different thread)
                                future = asyncio.run_coroutine_threadsafe(
                                    self.update_queue.enqueue(update),
                                    self._queue_loop
                                )
                                logger.debug(f"Scheduled enqueue for {market.market_id} (yes_bids={len(snapshot.yes_bids)}, yes_asks={len(snapshot.yes_asks)})")
                            else:
                                logger.warning(f"Queue loop exists but is not running for {market.market_id}")
                        except (RuntimeError, AttributeError) as e:
                            logger.warning(f"Error checking queue loop status for {market.market_id}: {e}")
                    else:
                        logger.warning(f"No queue loop set for {market.market_id}")
                else:
                    # Fallback: store directly in database (old behavior)
                    self.db_client.store_orderbook(snapshot)
            except Exception as e:
                logger.error(f"Error processing orderbook update for {market.market_id}: {e}", exc_info=True)
        
        return callback
    
    def _get_market_by_id(self, market_uuid: str) -> Optional[DatabaseMarket]:
        """Get market by UUID from database.
        
        Args:
            market_uuid: UUID of the market.
        
        Returns:
            DatabaseMarket if found, None otherwise.
        """
        try:
            response = self.db_client.client.table("markets").select("*").eq("id", market_uuid).limit(1).execute()
            if response.data and len(response.data) > 0:
                return DatabaseMarket.from_dict(response.data[0])
        except Exception as e:
            logger.error(f"Failed to get market by UUID {market_uuid}: {e}")
        return None
    
    def is_running(self) -> bool:
        """Check if the streamer is running.
        
        Returns:
            True if running, False otherwise.
        """
        return self._running
    
    def is_connected(self) -> bool:
        """Check if websockets are connected.
        
        Returns:
            True if both websockets are connected, False otherwise.
        """
        kalshi_connected = self.kalshi_client.is_websocket_connected()
        polymarket_connected = self.polymarket_client.is_websocket_connected()
        return kalshi_connected and polymarket_connected

