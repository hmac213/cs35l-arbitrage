"""Garbage collector component for filtering expired markets."""

import logging
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
from exchange.models import Market
from db.models import DatabaseMarket
from db.client import SupabaseClient
from .config import EngineConfig

logger = logging.getLogger(__name__)


class GarbageCollector:
    """Filters and removes expired markets."""
    
    def __init__(self, expiration_buffer_hours: Optional[int] = None):
        """Initialize the garbage collector.
        
        Args:
            expiration_buffer_hours: Hours after resolve time to mark as expired.
                                    If None, uses config default.
        """
        self.expiration_buffer_hours = (
            expiration_buffer_hours or EngineConfig.get_expiration_buffer()
        )
    
    def filter_expired(self, markets: List[Market]) -> tuple[List[Market], List[Market]]:
        """Filter expired markets from API response.
        
        Args:
            markets: List of Market instances from API.
            
        Returns:
            Tuple of (active_markets, expired_markets).
        """
        active_markets = []
        expired_markets = []
        
        for market in markets:
            if self._is_expired(market):
                expired_markets.append(market)
                logger.debug(
                    f"Market {market.market_id} ({market.exchange}) is expired"
                )
            else:
                active_markets.append(market)
        
        if expired_markets:
            logger.info(
                f"Filtered {len(expired_markets)} expired markets, "
                f"{len(active_markets)} active markets remain"
            )
        
        return active_markets, expired_markets
    
    def filter_bad_markets(self, markets: List[Market]) -> tuple[List[Market], List[Market]]:
        """Filter out bad/problematic markets that shouldn't be stored.
        
        Filters out:
        - Kalshi multigame extended markets
        - Markets with "PLACEHOLDER" in the name (template/test markets)
        - Markets with very short or empty names
        
        Args:
            markets: List of Market instances from API.
            
        Returns:
            Tuple of (valid_markets, bad_markets).
        """
        valid_markets = []
        bad_markets = []
        
        for market in markets:
            is_bad = False
            reason = []
            
            # Filter Kalshi multigame extended markets (case-insensitive)
            market_id_upper = (market.market_id or '').upper()
            if market.exchange == 'kalshi' and 'MULTIGAMEEXTENDED' in market_id_upper:
                is_bad = True
                reason.append('multigame_extended')
            
            # Filter markets without resolve_date (except for special cases)
            # Note: Some valid markets might not have resolve_date, but multigame ones definitely shouldn't
            if not market.metadata.resolve_date:
                # Only filter if it's also a multigame market or has other bad characteristics
                if 'MULTIGAMEEXTENDED' in market_id_upper:
                    is_bad = True
                    reason.append('no_resolve_date')
            
            # Filter markets with PLACEHOLDER in name (these are template/test markets)
            name_upper = (market.name or '').upper()
            if 'PLACEHOLDER' in name_upper:
                is_bad = True
                reason.append('placeholder_name')
            
            # Filter markets with very short or empty names
            if not market.name or len(market.name.strip()) < 5:
                is_bad = True
                reason.append('invalid_name')
            
            if is_bad:
                bad_markets.append(market)
                logger.debug(
                    f"Filtered bad market {market.market_id} ({market.exchange}): {', '.join(reason)}"
                )
            else:
                valid_markets.append(market)
        
        if bad_markets:
            logger.info(
                f"Filtered {len(bad_markets)} bad markets, "
                f"{len(valid_markets)} valid markets remain"
            )
        
        return valid_markets, bad_markets
    
    def cleanup_database(
        self,
        db_client: SupabaseClient,
        batch_size: Optional[int] = None
    ) -> Dict[str, int]:
        """Scan database for expired and bad markets, then remove them.
        
        Args:
            db_client: Supabase client instance.
            batch_size: Number of markets to process per batch. If None, uses config default.
            
        Returns:
            Dictionary with counts: {'expired_marked': count, 'bad_deleted': count, 'deleted': total}
        """
        batch_size = batch_size or EngineConfig.BATCH_SIZE
        expired_count = 0
        bad_count = 0
        offset = 0
        
        logger.info("Starting database cleanup for expired and bad markets...")
        
        while True:
            # Fetch batch of markets (including expired ones to check for bad markets)
            markets = db_client.get_all_markets(limit=batch_size, offset=offset)
            
            if not markets:
                break
            
            expired_in_batch = []
            bad_in_batch = []
            
            for market in markets:
                # Check if it's a bad market (regardless of status)
                is_bad = False
                reason = []
                
                # Check for multigame extended markets (case-insensitive)
                market_id_upper = (market.market_id or '').upper()
                if market.exchange == 'kalshi' and 'MULTIGAMEEXTENDED' in market_id_upper:
                    is_bad = True
                    reason.append('multigame_extended')
                
                # Check for PLACEHOLDER in name (these are template/test markets)
                name_upper = (market.name or '').upper()
                if 'PLACEHOLDER' in name_upper:
                    is_bad = True
                    reason.append('placeholder_name')
                
                # Check for invalid names
                if not market.name or len(market.name.strip()) < 5:
                    is_bad = True
                    reason.append('invalid_name')
                
                if is_bad:
                    bad_in_batch.append((market, reason))
                    continue
                
                # Check if expired (only for non-bad markets)
                if market.status != 'expired' and market.is_expired():
                    expired_in_batch.append(market)
            
            # Delete bad markets in batch
            if bad_in_batch:
                try:
                    bad_markets_to_delete = [market for market, _ in bad_in_batch]
                    deleted = db_client.delete_markets_batch(bad_markets_to_delete, batch_size=100)
                    bad_count += deleted
                    if deleted > 0:
                        logger.debug(
                            f"Deleted {deleted} bad markets in batch"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to delete bad markets in batch: {e}. Falling back to individual deletion."
                    )
                    # Fallback to individual deletion
                    for market, reason in bad_in_batch:
                        try:
                            db_client.delete_market(market.market_id, market.exchange)
                            bad_count += 1
                        except Exception as e2:
                            logger.warning(
                                f"Failed to delete bad market {market.market_id}: {e2}"
                            )
            
            # Mark expired markets
            if expired_in_batch:
                for market in expired_in_batch:
                    market.status = 'expired'
                    db_client.upsert_market(market)
                    expired_count += 1
                    logger.debug(
                        f"Marked market {market.market_id} ({market.exchange}) as expired"
                    )
            
            # If we got fewer than batch_size, we're done
            if len(markets) < batch_size:
                break
            
            offset += batch_size
        
        total_deleted = bad_count
        results = {
            'expired_marked': expired_count,
            'bad_deleted': bad_count,
            'deleted': total_deleted
        }
        
        if expired_count > 0 or bad_count > 0:
            logger.info(
                f"Database cleanup complete: {expired_count} expired, {bad_count} bad markets deleted"
            )
        else:
            logger.info("No expired or bad markets found in database")
        
        return results
    
    def _is_expired(self, market: Market) -> bool:
        """Check if a market has passed its resolve date/time.
        
        Args:
            market: Market instance to check.
            
        Returns:
            True if market is expired, False otherwise.
        """
        if not market.metadata.resolve_date:
            return False
        
        # Parse resolve date
        try:
            if isinstance(market.metadata.resolve_date, str):
                resolve_date = datetime.fromisoformat(
                    market.metadata.resolve_date
                ).date()
            else:
                resolve_date = market.metadata.resolve_date
        except (ValueError, AttributeError):
            logger.warning(
                f"Invalid resolve_date for market {market.market_id}: "
                f"{market.metadata.resolve_date}"
            )
            return False
        
        # Parse resolve time (default to end of day if not specified)
        if market.metadata.resolve_time:
            try:
                if isinstance(market.metadata.resolve_time, str):
                    resolve_time = datetime.strptime(
                        market.metadata.resolve_time,
                        '%H:%M:%S'
                    ).time()
                else:
                    resolve_time = market.metadata.resolve_time
            except (ValueError, AttributeError):
                logger.warning(
                    f"Invalid resolve_time for market {market.market_id}: "
                    f"{market.metadata.resolve_time}, using end of day"
                )
                resolve_time = datetime.max.time()
        else:
            resolve_time = datetime.max.time()
        
        # Combine date and time
        resolve_datetime = datetime.combine(resolve_date, resolve_time)
        
        # Add expiration buffer
        expiration_time = resolve_datetime + timedelta(
            hours=self.expiration_buffer_hours
        )
        
        # Compare with current time (UTC)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        return expiration_time < now

