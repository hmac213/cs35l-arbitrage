"""Queue system for processing orderbook updates and calculating arbitrage."""

import asyncio
import logging
from enum import Enum
from typing import Dict, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

from db.models import OrderbookSnapshot, MarketPair
from db.client import SupabaseClient
from .arbitrage_calculator import ArbitrageCalculator

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation, accepting updates
    OPEN = "open"  # Circuit open, rejecting updates
    HALF_OPEN = "half_open"  # Testing if conditions improved


@dataclass
class OrderbookUpdate:
    """Represents an orderbook update to process."""
    market_id: str  # UUID
    exchange: str
    orderbook: OrderbookSnapshot
    timestamp: datetime


class OrderbookUpdateQueue:
    """Queue for processing orderbook updates and triggering arbitrage calculations.
    
    Features:
    - Debouncing: Only process latest update per market within debounce window
    - Backpressure: Drop oldest updates if queue is full
    - Change detection: Skip processing if orderbook hasn't changed
    - Parallel processing: Multiple workers process updates concurrently
    - Circuit breaker: Pauses enqueueing when queue is at risk of overflow
    """
    
    def __init__(
        self,
        db_client: Optional[SupabaseClient] = None,
        arbitrage_calculator: Optional[ArbitrageCalculator] = None,
        max_workers: int = 8,
        queue_maxsize: int = 10000,
        debounce_ms: int = 100,
        circuit_breaker_utilization_threshold: float = 0.9,
        circuit_breaker_drop_rate_threshold: float = 0.1,
        circuit_breaker_recovery_check_interval: int = 5
    ):
        """Initialize the orderbook update queue.
        
        Args:
            db_client: Database client instance. If None, creates a new one.
            arbitrage_calculator: ArbitrageCalculator instance. If None, creates a new one.
            max_workers: Number of worker tasks to process updates in parallel.
            queue_maxsize: Maximum queue size before dropping oldest updates.
            debounce_ms: Debounce window in milliseconds (only process latest update per market).
            circuit_breaker_utilization_threshold: Queue utilization (0.0-1.0) that triggers circuit open.
            circuit_breaker_drop_rate_threshold: Drop rate (0.0-1.0) that triggers circuit open.
            circuit_breaker_recovery_check_interval: Seconds between recovery checks when circuit is open.
        """
        self.db_client = db_client or SupabaseClient()
        self.arbitrage_calculator = arbitrage_calculator or ArbitrageCalculator()
        self.max_workers = max_workers
        self.queue_maxsize = queue_maxsize
        self.debounce_ms = debounce_ms / 1000.0  # Convert to seconds
        
        # Circuit breaker configuration
        self.circuit_utilization_threshold = circuit_breaker_utilization_threshold
        self.circuit_drop_rate_threshold = circuit_breaker_drop_rate_threshold
        self.circuit_recovery_interval = circuit_breaker_recovery_check_interval
        
        # Queue for orderbook updates
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_maxsize)
        
        # Track which pairs are affected by each market
        self._market_to_pairs: Dict[str, Set[str]] = {}  # market_id -> set of pair_ids
        self._pair_cache: Dict[str, MarketPair] = {}  # pair_id -> MarketPair (cached to avoid refetching)
        
        # Debouncing: track last update per market
        self._pending_updates: Dict[str, OrderbookUpdate] = {}  # market_id -> latest update
        self._last_processed: Dict[str, Tuple[OrderbookSnapshot, datetime]] = {}  # market_id -> (orderbook, time)
        self._debounce_tasks: Dict[str, asyncio.Task] = {}  # market_id -> debounce task
        
        # Worker tasks
        self._workers: list[asyncio.Task] = []
        self._running = False
        
        # Circuit breaker state
        self._circuit_state = CircuitState.CLOSED
        self._circuit_recovery_task: Optional[asyncio.Task] = None
        self._circuit_opened_at: Optional[datetime] = None
        self._circuit_rejected_count = 0  # Count of rejected updates when circuit is open
        
        # Metrics
        self._stats = {
            'enqueued': 0,
            'processed': 0,
            'dropped': 0,
            'skipped_unchanged': 0,
            'opportunities_found': 0,
            'circuit_rejected': 0
        }
    
    async def start(self) -> None:
        """Start the queue workers."""
        if self._running:
            logger.warning("OrderbookUpdateQueue is already running")
            return
        
        logger.info("Starting OrderbookUpdateQueue...")
        self._running = True
        
        # Build market-to-pairs mapping
        logger.info("Building market-to-pairs mapping...")
        await self._refresh_market_pairs_mapping()
        logger.info("Market-to-pairs mapping built successfully")
        
        # Start worker tasks
        logger.info(f"Starting {self.max_workers} worker tasks...")
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.append(worker)
        
        # Start circuit breaker recovery task
        logger.info("Starting circuit breaker recovery task...")
        self._circuit_recovery_task = asyncio.create_task(self._circuit_breaker_recovery_loop())
        
        logger.info(
            f"OrderbookUpdateQueue started with {self.max_workers} workers "
            f"(queue_maxsize={self.queue_maxsize}, debounce={self.debounce_ms*1000}ms, "
            f"circuit_breaker: utilization>{self.circuit_utilization_threshold:.0%} or "
            f"drop_rate>{self.circuit_drop_rate_threshold:.0%})"
        )
    
    async def stop(self) -> None:
        """Stop the queue workers."""
        self._running = False
        
        # Cancel all debounce tasks
        for task in self._debounce_tasks.values():
            task.cancel()
        await asyncio.gather(*self._debounce_tasks.values(), return_exceptions=True)
        self._debounce_tasks.clear()
        
        # Process any pending updates immediately
        for update in self._pending_updates.values():
            try:
                await self._queue.put(update)
            except asyncio.QueueFull:
                self._stats['dropped'] += 1
                logger.warning(f"Queue full, dropping update for market {update.market_id}")
        self._pending_updates.clear()
        
        # Wait for queue to drain
        await self._queue.join()
        
        # Cancel circuit breaker recovery task
        if self._circuit_recovery_task:
            self._circuit_recovery_task.cancel()
            await asyncio.gather(self._circuit_recovery_task, return_exceptions=True)
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._workers.clear()
        logger.info(f"OrderbookUpdateQueue stopped. Stats: {self._stats}")
    
    async def enqueue(self, update: OrderbookUpdate) -> None:
        """Enqueue an orderbook update for processing.
        
        Uses debouncing: if an update for the same market is already pending,
        it replaces the old one. The update will be processed after the debounce window.
        
        Args:
            update: OrderbookUpdate instance.
        """
        if not self._running:
            logger.warning("Queue is not running, dropping update")
            return
        
        # Check circuit breaker - reject if open
        if self._circuit_state == CircuitState.OPEN:
            self._stats['circuit_rejected'] += 1
            self._circuit_rejected_count += 1
            logger.warning(f"Circuit breaker OPEN, rejecting update for market {update.market_id}")
            return
        
        self._stats['enqueued'] += 1
        
        # Check if we should skip this update (no change)
        if self._should_skip_update(update):
            self._stats['skipped_unchanged'] += 1
            logger.debug(f"Skipping unchanged update for market {update.market_id}")
            return
        
        # Store as pending update (replaces any previous pending update for this market)
        self._pending_updates[update.market_id] = update
        
        # Cancel existing debounce task for this market if any
        if update.market_id in self._debounce_tasks:
            self._debounce_tasks[update.market_id].cancel()
        
        # Create new debounce task
        task = asyncio.create_task(self._debounce_and_enqueue(update.market_id))
        self._debounce_tasks[update.market_id] = task
    
    async def _debounce_and_enqueue(self, market_id: str) -> None:
        """Wait for debounce window, then enqueue the update."""
        try:
            await asyncio.sleep(self.debounce_ms)
            
            # Get the pending update (may have been replaced)
            if market_id not in self._pending_updates:
                return
            
            update = self._pending_updates.pop(market_id)
            
            # Check circuit breaker state before enqueueing
            self._check_circuit_breaker()
            
            # If circuit is open, reject the update
            if self._circuit_state == CircuitState.OPEN:
                self._stats['circuit_rejected'] += 1
                self._circuit_rejected_count += 1
                logger.debug(f"Circuit breaker OPEN, rejecting update for market {update.market_id}")
                return
            
            # Try to put in queue (non-blocking with maxsize check)
            try:
                self._queue.put_nowait(update)
                
                # If in HALF_OPEN state and successfully enqueued, close circuit
                if self._circuit_state == CircuitState.HALF_OPEN:
                    self._circuit_state = CircuitState.CLOSED
                    self._circuit_opened_at = None
                    self._circuit_rejected_count = 0
                    logger.info("Circuit breaker CLOSED - conditions improved")
                    
            except asyncio.QueueFull:
                # Queue is full - implement backpressure: drop oldest to make room
                dropped_update = None
                try:
                    # Remove oldest update to make room
                    dropped_update = self._queue.get_nowait()
                    self._stats['dropped'] += 1
                    logger.warning(
                        f"Queue full ({self._queue.qsize()}/{self.queue_maxsize}), "
                        f"dropped oldest update for market {dropped_update.market_id}"
                    )
                except asyncio.QueueEmpty:
                    # Race condition: queue became empty between put_nowait and get_nowait
                    # This shouldn't happen, but handle gracefully
                    logger.warning("Queue was full but became empty (race condition)")
                
                # Now try to add the new update
                try:
                    self._queue.put_nowait(update)
                except asyncio.QueueFull:
                    # Still full (another update was added) - drop this one
                    self._stats['dropped'] += 1
                    logger.warning(f"Queue still full, dropping update for market {update.market_id}")
            
        except asyncio.CancelledError:
            # Debounce was cancelled (newer update arrived)
            pass
        finally:
            # Clean up task reference
            if market_id in self._debounce_tasks:
                del self._debounce_tasks[market_id]
    
    def _should_skip_update(self, update: OrderbookUpdate) -> bool:
        """Check if update should be skipped (orderbook hasn't changed).
        
        Args:
            update: OrderbookUpdate to check.
            
        Returns:
            True if update should be skipped, False otherwise.
        """
        if update.market_id not in self._last_processed:
            return False
        
        last_orderbook, last_timestamp = self._last_processed[update.market_id]
        
        # Skip if update is too recent (within last 10ms) - rapid updates
        # Reduced from 50ms to 10ms to allow more updates through
        time_diff = (update.timestamp - last_timestamp).total_seconds()
        if time_diff < 0.01:  # 10ms threshold (very rapid duplicate updates)
            return True
        
        # Compare best bid/ask prices with tolerance for floating point
        new_yes_bids = update.orderbook.yes_bids
        new_yes_asks = update.orderbook.yes_asks
        last_yes_bids = last_orderbook.yes_bids
        last_yes_asks = last_orderbook.yes_asks
        
        # Check if best prices changed (with small tolerance for floating point)
        new_best_yes_bid = new_yes_bids[0]['price'] if new_yes_bids else None
        new_best_yes_ask = new_yes_asks[0]['price'] if new_yes_asks else None
        last_best_yes_bid = last_yes_bids[0]['price'] if last_yes_bids else None
        last_best_yes_ask = last_yes_asks[0]['price'] if last_yes_asks else None
        
        # Skip if prices haven't changed (with tolerance)
        price_tolerance = 0.0001  # $0.0001 tolerance
        bid_changed = (new_best_yes_bid is None) != (last_best_yes_bid is None) or \
                     (new_best_yes_bid is not None and last_best_yes_bid is not None and 
                      abs(new_best_yes_bid - last_best_yes_bid) > price_tolerance)
        ask_changed = (new_best_yes_ask is None) != (last_best_yes_ask is None) or \
                     (new_best_yes_ask is not None and last_best_yes_ask is not None and 
                      abs(new_best_yes_ask - last_best_yes_ask) > price_tolerance)
        
        if not bid_changed and not ask_changed:
            return True
        
        return False
    
    async def _refresh_market_pairs_mapping(self) -> None:
        """Refresh the mapping of markets to pairs."""
        try:
            logger.info("Refreshing market-to-pairs mapping...")
            # Run blocking DB call in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            pairs = await loop.run_in_executor(None, self.db_client.get_all_market_pairs)
            
            self._market_to_pairs.clear()
            self._pair_cache.clear()
            
            for pair in pairs:
                # Cache pair for quick lookup
                self._pair_cache[pair.id] = pair
                
                # Add pair to market_1's set
                if pair.market_1_id not in self._market_to_pairs:
                    self._market_to_pairs[pair.market_1_id] = set()
                self._market_to_pairs[pair.market_1_id].add(pair.id)
                
                # Add pair to market_2's set
                if pair.market_2_id not in self._market_to_pairs:
                    self._market_to_pairs[pair.market_2_id] = set()
                self._market_to_pairs[pair.market_2_id].add(pair.id)
            
            logger.info(f"Refreshed market-to-pairs mapping: {len(self._market_to_pairs)} markets, {len(pairs)} pairs")
        except Exception as e:
            logger.error(f"Error refreshing market-to-pairs mapping: {e}", exc_info=True)
            raise
    
    async def _worker_loop(self, worker_name: str) -> None:
        """Worker loop that processes orderbook updates."""
        logger.info(f"{worker_name} started")
        
        while self._running:
            try:
                # Get update from queue (with timeout to allow checking _running)
                try:
                    update = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # No updates in queue - this is normal, continue waiting
                    continue
                
                try:
                    await self._process_update(update)
                except Exception as e:
                    logger.error(f"{worker_name} error processing update: {e}", exc_info=True)
                finally:
                    self._queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"{worker_name} unexpected error: {e}", exc_info=True)
        
        logger.info(f"{worker_name} stopped")
    
    async def _process_update(self, update: OrderbookUpdate) -> None:
        """Process a single orderbook update."""
        self._stats['processed'] += 1
        
        # Update last processed cache first (for change detection)
        self._last_processed[update.market_id] = (update.orderbook, update.timestamp)
        
        # Find all pairs that use this market
        affected_pairs = self._market_to_pairs.get(update.market_id, set())
        
        # Store orderbook and calculate arbitrage in parallel (don't wait for storage)
        loop = asyncio.get_event_loop()
        
        # Fire-and-forget orderbook storage (non-blocking)
        # This is less critical than arbitrage calculation
        async def store_orderbook_async():
            await loop.run_in_executor(None, self.db_client.store_orderbook, update.orderbook)
        asyncio.create_task(store_orderbook_async())
        
        # Calculate arbitrage (this is the important part)
        if affected_pairs:
            await self._calculate_arbitrage_for_pairs_batch(affected_pairs, update.market_id)
    
    async def _calculate_arbitrage_for_pairs_batch(
        self, 
        pair_ids: Set[str], 
        updated_market_id: str
    ) -> None:
        """Calculate arbitrage for multiple pairs in batch (optimized).
        
        Args:
            pair_ids: Set of pair IDs to process.
            updated_market_id: UUID of the market that was updated (for logging).
        """
        if not pair_ids:
            return
        
        # Get pairs from cache (no HTTP request)
        pairs = []
        market_uuids = set()
        for pair_id in pair_ids:
            pair = self._pair_cache.get(pair_id)
            if pair:
                pairs.append(pair)
                market_uuids.add(pair.market_1_id)
                market_uuids.add(pair.market_2_id)
            else:
                logger.warning(f"Pair {pair_id} not found in cache")
        
        if not pairs:
            return
        
        # Batch fetch markets and orderbooks in parallel (both are independent DB calls)
        loop = asyncio.get_event_loop()
        
        # Fetch markets and orderbooks in parallel
        markets_task = loop.run_in_executor(
            None, 
            self.db_client.get_markets_by_uuids, 
            list(market_uuids)
        )
        
        # Build exchange mapping for orderbook fetch (we need markets first, but can start the task)
        # Actually, we need markets to know exchanges, so fetch markets first, then orderbooks
        markets = await markets_task
        
        # Build exchange mapping for orderbook fetch
        market_exchanges = {}
        for market_uuid, market in markets.items():
            market_exchanges[market_uuid] = market.exchange
        
        # Now fetch orderbooks
        orderbooks = await loop.run_in_executor(
            None,
            self.db_client.get_latest_orderbooks_batch,
            list(market_uuids),
            market_exchanges
        )
        
        # Process pairs in parallel (up to 10 at a time to avoid overwhelming)
        # This prevents one market update with many pairs from blocking the worker
        opportunities = []
        loop = asyncio.get_event_loop()
        
        async def process_single_pair(pair):
            """Process a single pair and return opportunity if found."""
            try:
                market1 = markets.get(pair.market_1_id)
                market2 = markets.get(pair.market_2_id)
                
                if not market1 or not market2:
                    return None
                
                orderbook1 = orderbooks.get(pair.market_1_id)
                orderbook2 = orderbooks.get(pair.market_2_id)
                
                if not orderbook1 or not orderbook2:
                    return None
                
                # Calculate arbitrage in executor (CPU-bound operation)
                opportunity = await loop.run_in_executor(
                    None,
                    self.arbitrage_calculator.calculate_arbitrage,
                    orderbook1, orderbook2, pair.id
                )
                
                return opportunity
            except Exception as e:
                logger.error(f"Error calculating arbitrage for pair {pair.id}: {e}", exc_info=True)
                return None
        
        # Process pairs in larger batches and more aggressively in parallel
        # Increase batch size to process more pairs at once
        batch_size = 20  # Increased from 10
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i + batch_size]
            # Process batch in parallel
            batch_opportunities = await asyncio.gather(*[process_single_pair(pair) for pair in batch])
            opportunities.extend([opp for opp in batch_opportunities if opp is not None])
        
        # Store opportunities (fire-and-forget to avoid blocking)
        # Opportunities are less time-sensitive than processing new updates
        if opportunities:
            self._stats['opportunities_found'] += len(opportunities)
            # Store in background without blocking
            async def store_opportunity_async(opp):
                await loop.run_in_executor(None, self.db_client.store_arbitrage_opportunity, opp)
            for opportunity in opportunities:
                asyncio.create_task(store_opportunity_async(opportunity))
    
    def refresh_market_pairs_mapping(self) -> None:
        """Refresh the market-to-pairs mapping (synchronous version for external calls)."""
        # Schedule async refresh
        if self._running:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._refresh_market_pairs_mapping())
                else:
                    loop.run_until_complete(self._refresh_market_pairs_mapping())
            except RuntimeError:
                # No event loop, create one
                asyncio.run(self._refresh_market_pairs_mapping())
    
    def _check_circuit_breaker(self) -> None:
        """Check if circuit breaker should open based on current conditions."""
        if self._circuit_state == CircuitState.OPEN:
            return  # Already open, recovery loop will handle closing
        
        # Calculate current metrics
        queue_size = self._queue.qsize()
        queue_utilization = queue_size / self.queue_maxsize if self.queue_maxsize > 0 else 0.0
        
        total_attempted = self._stats['enqueued'] + self._stats['dropped']
        drop_rate = self._stats['dropped'] / total_attempted if total_attempted > 0 else 0.0
        
        # Check if thresholds exceeded
        utilization_exceeded = queue_utilization >= self.circuit_utilization_threshold
        drop_rate_exceeded = drop_rate >= self.circuit_drop_rate_threshold
        
        if utilization_exceeded or drop_rate_exceeded:
            if self._circuit_state == CircuitState.CLOSED:
                self._circuit_state = CircuitState.OPEN
                self._circuit_opened_at = datetime.now(timezone.utc)
                logger.warning(
                    f"Circuit breaker OPENED: "
                    f"utilization={queue_utilization:.1%} (threshold={self.circuit_utilization_threshold:.1%}), "
                    f"drop_rate={drop_rate:.1%} (threshold={self.circuit_drop_rate_threshold:.1%})"
                )
    
    async def _circuit_breaker_recovery_loop(self) -> None:
        """Periodically check if circuit breaker should close (recovery)."""
        while self._running:
            try:
                await asyncio.sleep(self.circuit_recovery_interval)
                
                if self._circuit_state == CircuitState.OPEN:
                    # Check if conditions improved
                    queue_size = self._queue.qsize()
                    queue_utilization = queue_size / self.queue_maxsize if self.queue_maxsize > 0 else 0.0
                    
                    total_attempted = self._stats['enqueued'] + self._stats['dropped']
                    drop_rate = self._stats['dropped'] / total_attempted if total_attempted > 0 else 0.0
                    
                    # Conditions improved - move to HALF_OPEN to test
                    utilization_ok = queue_utilization < self.circuit_utilization_threshold * 0.7  # 70% of threshold
                    drop_rate_ok = drop_rate < self.circuit_drop_rate_threshold * 0.7  # 70% of threshold
                    
                    if utilization_ok and drop_rate_ok:
                        self._circuit_state = CircuitState.HALF_OPEN
                        logger.info(
                            f"Circuit breaker HALF_OPEN: "
                            f"utilization={queue_utilization:.1%}, drop_rate={drop_rate:.1%} - testing recovery"
                        )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in circuit breaker recovery loop: {e}", exc_info=True)
    
    def get_stats(self) -> dict:
        """Get queue statistics.
        
        Returns:
            Dictionary with statistics: enqueued, processed, dropped, skipped_unchanged, opportunities_found, queue_size, drop_rate, circuit_state.
        """
        stats = self._stats.copy()
        stats['queue_size'] = self._queue.qsize()
        stats['pending_updates'] = len(self._pending_updates)
        
        # Calculate drop rate
        total_attempted = stats['enqueued'] + stats['dropped']
        if total_attempted > 0:
            stats['drop_rate'] = stats['dropped'] / total_attempted
        else:
            stats['drop_rate'] = 0.0
        
        # Calculate queue utilization
        stats['queue_utilization'] = stats['queue_size'] / self.queue_maxsize if self.queue_maxsize > 0 else 0.0
        
        # Circuit breaker state
        stats['circuit_state'] = self._circuit_state.value
        stats['circuit_rejected'] = self._stats['circuit_rejected']
        if self._circuit_opened_at:
            stats['circuit_opened_at'] = self._circuit_opened_at.isoformat()
        
        return stats

