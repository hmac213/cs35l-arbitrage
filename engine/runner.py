"""Main engine runner for orchestrating the data engine."""

import logging
import time
import signal
import sys
from typing import Optional
from threading import Event, Thread
from db.client import SupabaseClient
from exchange.clients.kalshi_client import KalshiClient
from exchange.clients.polymarket_client import PolymarketClient
from .market_sync import MarketSyncService
from .config import EngineConfig

logger = logging.getLogger(__name__)


class DataEngineRunner:
    """Main runner for the data engine."""
    
    def __init__(
        self,
        db_client: Optional[SupabaseClient] = None,
        kalshi_client: Optional[KalshiClient] = None,
        polymarket_client: Optional[PolymarketClient] = None,
        poll_interval: Optional[int] = None
    ):
        """Initialize the data engine runner.
        
        Args:
            db_client: Supabase client instance. If None, creates a new one.
            kalshi_client: Kalshi client instance. If None, creates a new one.
            polymarket_client: Polymarket client instance. If None, creates a new one.
            poll_interval: Polling interval in seconds. If None, uses config default.
        """
        self.db_client = db_client or SupabaseClient()
        self.sync_service = MarketSyncService(
            self.db_client,
            kalshi_client,
            polymarket_client
        )
        self.poll_interval = poll_interval or EngineConfig.get_market_poll_interval()
        self._stop_event = Event()
        self._running = False
        self._sync_thread: Optional[Thread] = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def start(self) -> None:
        """Start the engine with continuous polling."""
        if self._running:
            logger.warning("Engine is already running")
            return
        
        logger.info(f"Starting data engine (poll interval: {self.poll_interval}s)")
        self._running = True
        self._stop_event.clear()
        
        # Start sync thread
        self._sync_thread = Thread(target=self._run_loop, daemon=True)
        self._sync_thread.start()
        
        logger.info("Data engine started")
    
    def stop(self) -> None:
        """Stop the engine gracefully."""
        if not self._running:
            return
        
        logger.info("Stopping data engine...")
        self._running = False
        self._stop_event.set()
        
        if self._sync_thread:
            self._sync_thread.join(timeout=30)
            if self._sync_thread.is_alive():
                logger.warning("Sync thread did not stop within timeout")
        
        logger.info("Data engine stopped")
    
    def run_once(self) -> dict:
        """Run one full sync cycle.
        
        Returns:
            Dictionary with sync statistics.
        """
        logger.info("Running single sync cycle...")
        try:
            stats = self.sync_service.sync_markets()
            logger.info(f"Sync cycle complete. Stats: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Sync cycle failed: {e}", exc_info=True)
            raise
    
    def _run_loop(self) -> None:
        """Main loop for continuous polling."""
        while self._running and not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                logger.error(
                    f"Error in sync cycle: {e}. Continuing...",
                    exc_info=True
                )
            
            # Wait for next poll interval or stop event
            if self._stop_event.wait(self.poll_interval):
                # Stop event was set
                break
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def is_running(self) -> bool:
        """Check if the engine is running.
        
        Returns:
            True if running, False otherwise.
        """
        return self._running

