"""Arbitrage service runner with websocket support."""

import logging
import asyncio
import threading
from typing import Optional

from db.client import SupabaseClient
from exchange.clients.kalshi_client import KalshiClient
from exchange.clients.polymarket_client import PolymarketClient
from engine.arbitrage_service import ArbitrageService
from engine.orderbook_streamer import OrderbookStreamer
from engine.orderbook_poller import OrderbookPoller
from engine.orderbook_update_queue import OrderbookUpdateQueue
from engine.arbitrage_calculator import ArbitrageCalculator
from .config import ServiceConfig

logger = logging.getLogger(__name__)


class ArbitrageRunner:
    """Runs arbitrage service with websocket support.
    
    Manages websocket connections for real-time orderbook updates.
    Requires websockets to be enabled and working.
    """
    
    def __init__(
        self,
        config: ServiceConfig,
        db_client: Optional[SupabaseClient] = None,
        kalshi_client: Optional[KalshiClient] = None,
        polymarket_client: Optional[PolymarketClient] = None
    ):
        """Initialize the arbitrage runner.
        
        Args:
            config: Service configuration.
            db_client: Database client instance. If None, creates a new one.
            kalshi_client: Kalshi client instance. If None, creates a new one.
            polymarket_client: Polymarket client instance. If None, creates a new one.
        """
        self.config = config
        self.db_client = db_client or SupabaseClient()
        
        # Initialize clients
        self.kalshi_client = kalshi_client or KalshiClient(
            api_key_id=config.kalshi_api_key_id,
            private_key=config.kalshi_private_key,
            private_key_path=config.kalshi_private_key_path
        )
        self.polymarket_client = polymarket_client or PolymarketClient(
            api_key=config.polymarket_api_key
        )
        
        # Initialize orderbook poller (used by streamer for conversion)
        self.orderbook_poller = OrderbookPoller(
            kalshi_client=self.kalshi_client,
            polymarket_client=self.polymarket_client,
            db_client=self.db_client
        )
        
        # Initialize arbitrage calculator (used by queue)
        self.arbitrage_calculator = ArbitrageCalculator()
        
        # Initialize orderbook update queue (event-driven processing)
        self.update_queue: Optional[OrderbookUpdateQueue] = None
        if config.use_websockets:
            self.update_queue = OrderbookUpdateQueue(
                db_client=self.db_client,
                arbitrage_calculator=self.arbitrage_calculator,
                max_workers=4,
                queue_maxsize=10000,
                debounce_ms=100
            )
        
        # Initialize websocket streamer (optional)
        self.orderbook_streamer: Optional[OrderbookStreamer] = None
        if config.use_websockets:
            self.orderbook_streamer = OrderbookStreamer(
                kalshi_client=self.kalshi_client,
                polymarket_client=self.polymarket_client,
                db_client=self.db_client,
                orderbook_poller=self.orderbook_poller,
                update_queue=self.update_queue
            )
        
        # State
        self._running = False
        self._websocket_mode = False
        self._streamer_task: Optional[asyncio.Task] = None
        self._refresh_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start the arbitrage runner.
        
        Starts websocket connections for real-time orderbook updates.
        Requires websockets to be enabled.
        
        Raises:
            ValueError: If websockets are not enabled or streamer is not initialized.
            RuntimeError: If websocket connection fails.
        """
        if self._running:
            logger.warning("ArbitrageRunner is already running")
            return
        
        if not self.config.use_websockets:
            raise ValueError("Websockets must be enabled. Set use_websockets=True in config.")
        
        if not self.orderbook_streamer:
            raise ValueError("OrderbookStreamer is not initialized. Websockets are required.")
        
        self._running = True
        
        try:
            self._start_websocket_mode()
            self._websocket_mode = True
            logger.info("ArbitrageRunner started in websocket mode")
        except Exception as e:
            self._running = False
            logger.error(f"Failed to start websocket mode: {e}")
            raise RuntimeError(f"Failed to start websocket mode: {e}") from e
    
    def stop(self) -> None:
        """Stop the arbitrage runner."""
        if not self._running:
            return
        
        self._running = False
        
        if self._websocket_mode:
            self._stop_websocket_mode()
        
        logger.info("ArbitrageRunner stopped")
    
    def _start_websocket_mode(self) -> None:
        """Start websocket mode."""
        if not self.orderbook_streamer:
            raise ValueError("OrderbookStreamer is not initialized")
        
        if not self.update_queue:
            raise ValueError("OrderbookUpdateQueue is not initialized")
        
        # Create event loop in a separate thread
        def run_event_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            try:
                # Pass the queue's event loop to the streamer FIRST so callbacks can schedule work
                # This must be done before starting the streamer, as callbacks are created during start()
                if self.orderbook_streamer:
                    self.orderbook_streamer._queue_loop = self._loop
                    logger.debug(f"Set queue loop on streamer: {self._loop}")
                
                # Start update queue first (event-driven processing)
                logger.info("Starting update queue...")
                self._loop.run_until_complete(self.update_queue.start())
                logger.info("Update queue started successfully")
                
                # Start streamer (will enqueue updates to the queue)
                logger.info("Starting orderbook streamer...")
                self._loop.run_until_complete(self.orderbook_streamer.start())
                logger.info("Orderbook streamer started successfully")
                
                # Verify queue loop is still set
                if self.orderbook_streamer._queue_loop != self._loop:
                    logger.warning(f"Queue loop mismatch! streamer._queue_loop={self.orderbook_streamer._queue_loop}, expected={self._loop}")
                
                # Start refresh task
                self._refresh_task = self._loop.create_task(self._refresh_subscriptions_loop())
                
                # Run event loop
                logger.info("Event loop running...")
                self._loop.run_forever()
            except Exception as e:
                logger.error(f"Error in event loop: {e}", exc_info=True)
                raise
        
        self._loop_thread = threading.Thread(target=run_event_loop, daemon=True)
        self._loop_thread.start()
        
        # Wait a bit for connection to establish
        import time
        time.sleep(2)
        
        # Verify connection
        if not self.orderbook_streamer.is_connected():
            raise RuntimeError("Failed to establish websocket connections")
        
        # Note: No longer starting ArbitrageService polling - everything is event-driven now
    
    def _stop_websocket_mode(self) -> None:
        """Stop websocket mode."""
        if self._loop:
            # Schedule stop for streamer and queue
            if self.orderbook_streamer:
                asyncio.run_coroutine_threadsafe(
                    self.orderbook_streamer.stop(),
                    self._loop
                )
            
            if self.update_queue:
                asyncio.run_coroutine_threadsafe(
                    self.update_queue.stop(),
                    self._loop
                )
            
            # Cancel tasks
            if self._refresh_task:
                # cancel() returns a coroutine, so we need to await it
                async def cancel_task():
                    self._refresh_task.cancel()
                    try:
                        await self._refresh_task
                    except asyncio.CancelledError:
                        pass
                asyncio.run_coroutine_threadsafe(cancel_task(), self._loop)
            
            # Stop event loop
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        if self._loop_thread:
            self._loop_thread.join(timeout=5)
    
    async def _refresh_subscriptions_loop(self) -> None:
        """Periodically refresh websocket subscriptions."""
        while self._running:
            try:
                await asyncio.sleep(self.config.websocket_refresh_subscriptions_interval)
                if self.orderbook_streamer and self._running:
                    await self.orderbook_streamer.refresh_subscriptions()
                    # Also refresh market-to-pairs mapping in queue
                    if self.update_queue:
                        self.update_queue.refresh_market_pairs_mapping()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error refreshing subscriptions: {e}", exc_info=True)
    
    def is_running(self) -> bool:
        """Check if the runner is running.
        
        Returns:
            True if running, False otherwise.
        """
        return self._running
    
    def is_websocket_mode(self) -> bool:
        """Check if running in websocket mode.
        
        Returns:
            True if websocket mode (always True when running).
        """
        return self._websocket_mode
    
    def get_stats(self) -> dict:
        """Get runner statistics.
        
        Returns:
            Dictionary with statistics.
        """
        stats = {
            'running': self._running,
            'mode': 'websocket',
            'websocket_connected': False
        }
        
        if self.orderbook_streamer:
            stats['websocket_connected'] = self.orderbook_streamer.is_connected()
            stats['kalshi_subscriptions'] = len(self.orderbook_streamer._kalshi_subscriptions)
            stats['polymarket_subscriptions'] = len(self.orderbook_streamer._polymarket_subscriptions)
        
        if self.update_queue:
            queue_stats = self.update_queue.get_stats()
            stats['queue'] = queue_stats
        
        return stats

