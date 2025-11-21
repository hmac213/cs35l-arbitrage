"""Arbitrage service that orchestrates polling, calculation, and storage."""

import logging
import time
import threading
from typing import Dict, Optional
from db.client import SupabaseClient
from db.models import MarketPair, OrderbookSnapshot, ArbitrageOpportunity
from .orderbook_poller import OrderbookPoller
from .arbitrage_calculator import ArbitrageCalculator
from .config import EngineConfig
from .errors import PollingError

logger = logging.getLogger(__name__)


class ArbitrageService:
    """Service that continuously polls orderbooks and calculates arbitrage opportunities."""
    
    def __init__(
        self,
        db_client: Optional[SupabaseClient] = None,
        orderbook_poller: Optional[OrderbookPoller] = None,
        arbitrage_calculator: Optional[ArbitrageCalculator] = None,
        poll_interval: Optional[int] = None,
        use_stored_orderbooks: bool = False
    ):
        """Initialize the arbitrage service.
        
        Args:
            db_client: Database client instance. If None, creates a new one.
            orderbook_poller: OrderbookPoller instance. If None, creates a new one.
            arbitrage_calculator: ArbitrageCalculator instance. If None, creates a new one.
            poll_interval: Polling interval in seconds. If None, uses config.
            use_stored_orderbooks: If True, calculate from stored orderbooks instead of polling.
                                  Useful when websockets are streaming orderbooks.
        """
        self.db_client = db_client or SupabaseClient()
        self.orderbook_poller = orderbook_poller or OrderbookPoller(db_client=self.db_client)
        self.arbitrage_calculator = arbitrage_calculator or ArbitrageCalculator()
        self.poll_interval = poll_interval or EngineConfig.ORDERBOOK_POLL_INTERVAL
        self.use_stored_orderbooks = use_stored_orderbooks
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def poll_and_calculate(self, stop_on_error: bool = False) -> Dict[str, int]:
        """Poll orderbooks and calculate arbitrage opportunities for all market pairs.
        
        Args:
            stop_on_error: If True, raise exception on first error instead of continuing.
        
        Returns:
            Dictionary with statistics: pairs_processed, orderbooks_stored, opportunities_found
        
        Raises:
            Exception: If stop_on_error is True and an error occurs.
        """
        stats = {
            'pairs_processed': 0,
            'orderbooks_stored': 0,
            'opportunities_found': 0,
            'errors': 0
        }
        
        # Get all market pairs
        market_pairs = self.db_client.get_all_market_pairs()
        logger.info(f"[ARBITRAGE] Processing {len(market_pairs)} market pairs...")
        
        for pair in market_pairs:
            try:
                if self.use_stored_orderbooks:
                    # Use latest stored orderbooks instead of polling
                    # Get market details to know exchange
                    market1 = self.orderbook_poller._get_market_by_id(pair.market_1_id)
                    market2 = self.orderbook_poller._get_market_by_id(pair.market_2_id)
                    
                    if not market1 or not market2:
                        logger.debug(f"[ARBITRAGE] Skipping pair {pair.id} - market(s) not found")
                        stats['errors'] += 1
                        continue
                    
                    orderbook1 = self.db_client.get_latest_orderbook(pair.market_1_id, market1.exchange)
                    orderbook2 = self.db_client.get_latest_orderbook(pair.market_2_id, market2.exchange)
                else:
                    # Poll orderbooks for both markets
                    orderbook1, orderbook2 = self.orderbook_poller.poll_market_pair(pair)
                    
                    if not orderbook1 or not orderbook2:
                        # Missing orderbooks are expected for some markets - skip, don't error
                        logger.debug(f"[ARBITRAGE] Skipping pair {pair.id} - orderbook(s) not available")
                        stats['errors'] += 1
                        continue
                    
                    # Store orderbooks
                    self.db_client.store_orderbook(orderbook1)
                    self.db_client.store_orderbook(orderbook2)
                    stats['orderbooks_stored'] += 2
                
                if not orderbook1 or not orderbook2:
                    # Missing orderbooks - skip
                    logger.debug(f"[ARBITRAGE] Skipping pair {pair.id} - orderbook(s) not available")
                    stats['errors'] += 1
                    continue
                
                # Calculate arbitrage opportunity (buy YES on one exchange, NO on the other)
                opportunity = self.arbitrage_calculator.calculate_arbitrage(
                    orderbook1, orderbook2, pair.id
                )
                
                if opportunity:
                    self.db_client.store_arbitrage_opportunity(opportunity)
                    stats['opportunities_found'] += 1
                    logger.info(
                        f"[ARBITRAGE] ✓ Opportunity: {opportunity.direction}, "
                        f"YES @ {opportunity.yes_exchange} (${opportunity.yes_price:.4f}), "
                        f"NO @ {opportunity.no_exchange} (${opportunity.no_price:.4f}), "
                        f"total cost: ${opportunity.yes_price + opportunity.no_price:.4f}/pair, "
                        f"profit: ${opportunity.profit_per_share:.4f}/share, "
                        f"max size: {opportunity.max_size:.2f} shares, "
                        f"total profit: ${opportunity.profit_per_share * opportunity.max_size:.2f}"
                    )
                
                stats['pairs_processed'] += 1
                
            except Exception as e:
                if stop_on_error:
                    logger.error(f"[ARBITRAGE] Error processing pair {pair.id}: {e}", exc_info=True)
                    raise
                logger.error(f"[ARBITRAGE] Error processing pair {pair.id}: {e}", exc_info=True)
                stats['errors'] += 1
        
        logger.info(
            f"[ARBITRAGE] Complete: {stats['pairs_processed']} pairs processed, "
            f"{stats['orderbooks_stored']} orderbooks stored, "
            f"{stats['opportunities_found']} opportunities found, "
            f"{stats['errors']} errors"
        )
        
        return stats
    
    def start(self) -> None:
        """Start the continuous polling loop in a background thread."""
        if self._running:
            logger.warning("[ARBITRAGE] Service is already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"[ARBITRAGE] Service started (poll interval: {self.poll_interval}s)")
    
    def stop(self) -> None:
        """Stop the continuous polling loop."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=10)
        
        logger.info("[ARBITRAGE] Service stopped")
    
    def _run_loop(self) -> None:
        """Main polling loop that runs continuously."""
        while self._running and not self._stop_event.is_set():
            try:
                self.poll_and_calculate()
            except Exception as e:
                logger.error(f"[ARBITRAGE] Error in polling loop: {e}", exc_info=True)
            
            # Wait for poll interval or until stop event
            if self._stop_event.wait(self.poll_interval):
                # Stop event was set
                break

