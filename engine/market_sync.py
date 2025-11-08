"""Market synchronization service that orchestrates polling, garbage collection, and database updates."""

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

logger = logging.getLogger(__name__)


class MarketSyncService:
    """Orchestrates market polling, garbage collection, and database synchronization."""
    
    def __init__(
        self,
        db_client: SupabaseClient,
        kalshi_client: Optional[KalshiClient] = None,
        polymarket_client: Optional[PolymarketClient] = None
    ):
        """Initialize the market sync service.
        
        Args:
            db_client: Supabase client instance.
            kalshi_client: Optional Kalshi client instance.
            polymarket_client: Optional Polymarket client instance.
        """
        self.db_client = db_client
        self.poller = MarketPoller(kalshi_client, polymarket_client)
        self.garbage_collector = GarbageCollector()
    
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
        if markets_to_upsert:
            try:
                self.db_client.upsert_markets(markets_to_upsert)
                logger.info(
                    f"Upserted {len(markets_to_upsert)} markets from {exchange_name}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to upsert markets from {exchange_name}: {e}",
                    exc_info=True
                )
                raise SyncError(f"Failed to upsert markets from {exchange_name}") from e
        
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

