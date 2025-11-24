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
        
        # Initialize orderbook poller (used by streamer for storage)
        self.orderbook_poller = OrderbookPoller(
            kalshi_client=self.kalshi_client,
            polymarket_client=self.polymarket_client,
            db_client=self.db_client
        )
        
        # Initialize arbitrage service
        # Will be updated to use_stored_orderbooks=True when websocket mode starts
        self.arbitrage_service = ArbitrageService(
            db_client=self.db_client,
            orderbook_poller=self.orderbook_poller,
            poll_interval=config.arbitrage_poll_interval,
            use_stored_orderbooks=False  # Will be set to True in websocket mode
        )
        
        # Initialize websocket streamer (optional)
        self.orderbook_streamer: Optional[OrderbookStreamer] = None
        if config.use_websockets:
            self.orderbook_streamer = OrderbookStreamer(
                kalshi_client=self.kalshi_client,
                polymarket_client=self.polymarket_client,
                db_client=self.db_client,
                orderbook_poller=self.orderbook_poller
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
        
        # Update arbitrage service to use stored orderbooks
        self.arbitrage_service.use_stored_orderbooks = True
        
        # Create event loop in a separate thread
        def run_event_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            # Start streamer
            self._loop.run_until_complete(self.orderbook_streamer.start())
            
            # Start refresh task
            self._refresh_task = self._loop.create_task(self._refresh_subscriptions_loop())
            
            # Run event loop
            self._loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_event_loop, daemon=True)
        self._loop_thread.start()
        
        # Wait a bit for connection to establish
        import time
        time.sleep(2)
        
        # Verify connection
        if not self.orderbook_streamer.is_connected():
            raise RuntimeError("Failed to establish websocket connections")
        
        # Start arbitrage service (it will use stored orderbooks)
        self.arbitrage_service.start()
    
    def _stop_websocket_mode(self) -> None:
        """Stop websocket mode."""
        # Stop arbitrage service
        self.arbitrage_service.stop()
        
        if self._loop:
            # Schedule stop
            asyncio.run_coroutine_threadsafe(
                self.orderbook_streamer.stop() if self.orderbook_streamer else asyncio.sleep(0),
                self._loop
            )
            
            # Cancel tasks
            if self._refresh_task:
                asyncio.run_coroutine_threadsafe(self._refresh_task.cancel(), self._loop)
            
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
        
        return stats

