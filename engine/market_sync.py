"""Market synchronization service that orchestrates polling, garbage collection, and database updates."""

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
from exchange.models import Market
from exchange.clients.kalshi_client import KalshiClient
from exchange.clients.polymarket_client import PolymarketClient
from db.client import SupabaseClient
from db.models import DatabaseMarket
from .market_poller import MarketPoller
from .garbage_collector import GarbageCollector
from .validators import compare_markets
from .errors import SyncError, MarketValidationError
from .market_similarity import MarketSimilarityService
from .config import EngineConfig

logger = logging.getLogger(__name__)


class MarketSyncService:
    """Orchestrates market polling, garbage collection, and database synchronization."""
    
    def __init__(
        self,
        db_client: SupabaseClient,
        kalshi_client: Optional[KalshiClient] = None,
        polymarket_client: Optional[PolymarketClient] = None,
        similarity_service: Optional[MarketSimilarityService] = None
    ):
        """Initialize the market sync service.
        
        Args:
            db_client: Supabase client instance.
            kalshi_client: Optional Kalshi client instance.
            polymarket_client: Optional Polymarket client instance.
            similarity_service: Optional MarketSimilarityService instance.
        """
        self.db_client = db_client
        self.poller = MarketPoller(kalshi_client, polymarket_client)
        self.garbage_collector = GarbageCollector()
        self.similarity_service = similarity_service
        
        if self.similarity_service:
            logger.info("[SIMILARITY] Similarity service is enabled and will process markets")
        else:
            logger.info("[SIMILARITY] Similarity service is not enabled")
    
    def sync_markets(self) -> Dict[str, int]:
        """Run the full market synchronization pipeline.
        
        Returns:
            Dictionary with sync statistics:
            - 'kalshi_added': Number of new Kalshi markets
            - 'kalshi_updated': Number of updated Kalshi markets
            - 'kalshi_skipped': Number of unchanged Kalshi markets
            - 'polymarket_added': Number of new Polymarket markets
            - 'polymarket_updated': Number of updated Polymarket markets
            - 'polymarket_skipped': Number of unchanged Polymarket markets
            - 'expired_marked': Number of expired markets marked
            - 'bad_deleted': Number of bad markets deleted
            - 'pairs_created': Number of market pairs created (if similarity service enabled)
            - 'pairs_verified': Number of pairs verified by LLM (if similarity service enabled)
        """
        stats = {
            'kalshi_added': 0,
            'kalshi_updated': 0,
            'kalshi_skipped': 0,
            'polymarket_added': 0,
            'polymarket_updated': 0,
            'polymarket_skipped': 0,
            'expired_marked': 0,
            'bad_deleted': 0,
            'pairs_created': 0,
            'pairs_verified': 0,
        }
        
        logger.info("Starting market synchronization...")
        
        try:
            # Step 1: Poll markets from both exchanges
            polled_markets = self.poller.poll_all()
            
            # Step 2: Sync each exchange
            if polled_markets.get('kalshi'):
                kalshi_stats = self._sync_exchange(
                    'kalshi',
                    polled_markets['kalshi']
                )
                stats.update(kalshi_stats)
            
            if polled_markets.get('polymarket'):
                polymarket_stats = self._sync_exchange(
                    'polymarket',
                    polled_markets['polymarket']
                )
                stats.update(polymarket_stats)
            
            # Step 3: Cleanup expired and bad markets from database
            cleanup_results = self.garbage_collector.cleanup_database(self.db_client)
            stats['expired_marked'] = cleanup_results.get('expired_marked', 0)
            stats['bad_deleted'] = cleanup_results.get('bad_deleted', 0)
            
            # Step 4: Process verification queue if similarity service is enabled (async)
            if self.similarity_service:
                logger.info("[QUEUE] Processing verification queue...")
                queue_stats = asyncio.run(
                    self.similarity_service.verification_queue.process_queue(
                        self.db_client,
                        self.similarity_service
                    )
                )
                stats['pairs_verified'] = queue_stats.get('verified', 0)
                stats['pairs_created'] = queue_stats.get('verified', 0)  # Same as verified since pairs are created on verification
                logger.info(f"[QUEUE] ✓ Queue processing complete: {stats['pairs_verified']} pairs created")
            
            logger.info(f"Market synchronization complete. Stats: {stats}")
            return stats
            
        except Exception as e:
            error_msg = f"Market synchronization failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise SyncError(error_msg) from e
    
    def _sync_exchange(
        self,
        exchange_name: str,
        markets: List[Market]
    ) -> Dict[str, int]:
        """Sync markets from a single exchange.
        
        Args:
            exchange_name: Name of the exchange ('kalshi' or 'polymarket').
            markets: List of Market instances from the exchange.
            
        Returns:
            Dictionary with sync statistics for this exchange.
        """
        stats = {
            f'{exchange_name}_added': 0,
            f'{exchange_name}_updated': 0,
            f'{exchange_name}_skipped': 0,
        }
        
        logger.info(f"Syncing {len(markets)} markets from {exchange_name}...")
        
        # Step 1: Filter bad markets (multigame extended, suspicious patterns, etc.)
        valid_markets, bad_markets = self.garbage_collector.filter_bad_markets(markets)
        
        if bad_markets:
            logger.info(
                f"Filtered {len(bad_markets)} bad markets from {exchange_name}"
            )
        
        # Step 2: Filter expired markets
        active_markets, expired_markets = self.garbage_collector.filter_expired(valid_markets)
        
        if expired_markets:
            logger.info(
                f"Filtered {len(expired_markets)} expired markets from {exchange_name}"
            )
        
        # Step 3: Batch fetch existing markets for comparison
        # This reduces DB queries by fetching all at once
        existing_markets = self.db_client.get_markets_by_exchange(exchange_name)
        existing_by_id = {
            m.market_id: m for m in existing_markets
        }
        
        # Step 4: Process each active market
        now = datetime.now(timezone.utc)
        markets_to_upsert = []
        new_market_ids = set()  # Track which markets are new for similarity processing
        
        for market in active_markets:
            try:
                # Convert to DatabaseMarket
                new_db_market = DatabaseMarket.from_exchange_market(market)
                new_db_market.last_polled_at = now
                new_db_market.status = 'active'
                
                # Check if market exists
                existing_market = existing_by_id.get(market.market_id)
                
                if existing_market:
                    # Market exists - check if it has changed
                    if compare_markets(new_db_market, existing_market):
                        # No changes - skip write
                        stats[f'{exchange_name}_skipped'] += 1
                        logger.debug(
                            f"Skipping unchanged market {market.market_id} ({exchange_name})"
                        )
                        continue
                    else:
                        # Market has changed - update
                        stats[f'{exchange_name}_updated'] += 1
                        logger.debug(
                            f"Updating changed market {market.market_id} ({exchange_name})"
                        )
                else:
                    # New market - add
                    stats[f'{exchange_name}_added'] += 1
                    new_market_ids.add(market.market_id)
                    logger.debug(
                        f"Adding new market {market.market_id} ({exchange_name})"
                    )
                
                # Add to batch for upsert
                markets_to_upsert.append(new_db_market)
                
            except MarketValidationError as e:
                logger.warning(
                    f"Skipping invalid market {market.market_id} ({exchange_name}): {e}"
                )
                continue
            except Exception as e:
                logger.error(
                    f"Error processing market {market.market_id} ({exchange_name}): {e}",
                    exc_info=True
                )
                continue
        
        # Step 5: Batch upsert markets
        new_markets = []  # Track newly added markets for similarity processing
        if markets_to_upsert:
            try:
                # Upsert markets and get results with IDs
                results = self.db_client.upsert_markets(markets_to_upsert)
                logger.info(
                    f"Upserted {len(markets_to_upsert)} markets from {exchange_name}"
                )
                
                # Identify newly added markets (those that didn't exist before)
                # Create a mapping of market_id to result for easier lookup
                result_by_market_id = {}
                for result in results:
                    if isinstance(result, dict) and result.get('market_id'):
                        result_by_market_id[result['market_id']] = result
                
                # Fetch new markets that were just added
                logger.debug(f"[SIMILARITY] Looking for {len(new_market_ids)} new markets in upsert results...")
                for market_id in new_market_ids:
                    if market_id in result_by_market_id:
                        result_dict = result_by_market_id[market_id]
                        if result_dict.get('id'):
                            new_db_market = DatabaseMarket.from_dict(result_dict)
                            new_markets.append(new_db_market)
                            logger.debug(f"[SIMILARITY] Found new market in results: {market_id} (id: {result_dict.get('id')})")
                        else:
                            logger.warning(f"[SIMILARITY] Market {market_id} in results but missing 'id' field")
                    else:
                        logger.warning(f"[SIMILARITY] Market {market_id} not found in upsert results")
                
                logger.info(f"[SIMILARITY] Identified {len(new_markets)} new markets from {len(new_market_ids)} tracked new market IDs")
                
            except Exception as e:
                logger.error(
                    f"Failed to upsert markets from {exchange_name}: {e}",
                    exc_info=True
                )
                raise SyncError(f"Failed to upsert markets from {exchange_name}") from e
        
        # Step 6: Process new markets through similarity service
        # Also process existing markets that don't have embeddings yet
        if not self.similarity_service:
            logger.info(f"[SIMILARITY] Similarity service not initialized, skipping")
        else:
            markets_to_process = []
            
            # Add new markets (these already have IDs from the upsert results)
            markets_to_process.extend(new_markets)
            logger.info(f"[SIMILARITY] Found {len(new_markets)} new markets to process")
            
            # Also check existing markets that might not have embeddings
            # Use the upsert results to get markets with IDs, avoiding individual DB queries
            if markets_to_upsert:
                logger.info(f"[SIMILARITY] Checking {len(markets_to_upsert)} upserted markets for missing embeddings...")
                
                # Get markets with IDs from upsert results (already fetched above)
                # Create a set of new market IDs for quick lookup
                new_market_ids_set = {m.market_id for m in new_markets}
                
                # Use existing_by_id to get markets that were updated (not new)
                # These already have database IDs from the earlier fetch
                markets_with_ids = []
                for market in markets_to_upsert:
                    # Skip if it's a new market (already in new_markets)
                    if market.market_id in new_market_ids_set:
                        continue
                    
                    # Get from existing_by_id (already fetched, has ID)
                    existing_market = existing_by_id.get(market.market_id)
                    if existing_market and existing_market.id:
                        markets_with_ids.append(existing_market)
                
                logger.debug(f"[SIMILARITY] Retrieved {len(markets_with_ids)} existing markets with IDs (from cache)")
                
                # Batch check which ones need embeddings (much faster than individual queries)
                if markets_with_ids:
                    logger.info(f"[SIMILARITY] Batch checking {len(markets_with_ids)} markets for embeddings...")
                    # Run async batch check
                    has_embeddings_map = asyncio.run(
                        self.similarity_service.vector_store.batch_has_embeddings(markets_with_ids)
                    )
                    
                    for market in markets_with_ids:
                        if not has_embeddings_map.get(market.market_id, False):
                            logger.info(f"[SIMILARITY] Market {market.market_id} ({market.exchange}) missing embedding, will process")
                            markets_to_process.append(market)
            
            if markets_to_process:
                logger.info(f"[SIMILARITY] Processing {len(markets_to_process)} markets through similarity service "
                           f"({len(new_markets)} new, {len(markets_to_process) - len(new_markets)} missing embeddings) in parallel batches...")
                
                # Process markets in parallel batches using a single async context
                batch_size = EngineConfig.ASYNC_BATCH_SIZE
                total_batches = (len(markets_to_process) + batch_size - 1) // batch_size
                
                async def process_all_markets() -> None:
                    """Process all markets in parallel batches within a single async context."""
                    async def process_market_batch(batch: List[DatabaseMarket], batch_idx: int) -> None:
                        """Process a batch of markets in parallel."""
                        logger.info(f"[SIMILARITY] Processing batch {batch_idx+1}/{total_batches} ({len(batch)} markets)...")
                        
                        tasks = []
                        for idx, market in enumerate(batch):
                            market_idx = batch_idx * batch_size + idx + 1
                            logger.debug(f"[SIMILARITY] Queuing market {market_idx}/{len(markets_to_process)}: "
                                       f"{market.market_id} ({market.exchange})")
                            tasks.append(self.similarity_service.process_new_market(market))
                        
                        # Process batch in parallel
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Log results
                        success_count = sum(1 for r in results if not isinstance(r, Exception))
                        error_count = sum(1 for r in results if isinstance(r, Exception))
                        
                        if error_count > 0:
                            logger.warning(f"[SIMILARITY] Batch {batch_idx+1} completed with {error_count} errors")
                            for idx, result in enumerate(results):
                                if isinstance(result, Exception):
                                    market = batch[idx]
                                    logger.warning(
                                        f"[SIMILARITY] ✗ Error processing market {market.market_id}: {result}",
                                        exc_info=True
                                    )
                        else:
                            logger.info(f"[SIMILARITY] Batch {batch_idx+1} completed successfully ({success_count} markets)")
                    
                    # Process all batches sequentially (but each batch processes markets in parallel)
                    # This prevents overwhelming the API with too many concurrent requests
                    for batch_idx in range(total_batches):
                        start_idx = batch_idx * batch_size
                        end_idx = min(start_idx + batch_size, len(markets_to_process))
                        batch = markets_to_process[start_idx:end_idx]
                        await process_market_batch(batch, batch_idx)
                
                # Run all processing in a single async context
                asyncio.run(process_all_markets())
                
                logger.info(f"[SIMILARITY] ✓ Finished processing {len(markets_to_process)} markets in {total_batches} batches")
            else:
                logger.info(f"[SIMILARITY] No markets to process (all markets already have embeddings or were skipped)")
                logger.debug(f"[SIMILARITY] new_market_ids tracked: {len(new_market_ids)}, "
                           f"new_markets found: {len(new_markets)}, markets_to_upsert: {len(markets_to_upsert) if 'markets_to_upsert' in locals() else 0}")
        
        added_key = f'{exchange_name}_added'
        updated_key = f'{exchange_name}_updated'
        skipped_key = f'{exchange_name}_skipped'
        logger.info(
            f"Sync complete for {exchange_name}: "
            f"{stats[added_key]} added, "
            f"{stats[updated_key]} updated, "
            f"{stats[skipped_key]} skipped"
        )
        
        return stats

