"""Market poller component for fetching markets from exchanges."""

import logging
from typing import List, Optional, Callable
from exchange.base import ExchangeClient
from exchange.models import Market
from exchange.clients.kalshi_client import KalshiClient
from exchange.clients.polymarket_client import PolymarketClient
from .errors import PollingError, MarketValidationError
from .validators import validate_market_data
from .config import EngineConfig

logger = logging.getLogger(__name__)


class MarketPoller:
    """Polls markets from Kalshi and Polymarket exchanges."""
    
    def __init__(
        self,
        kalshi_client: Optional[KalshiClient] = None,
        polymarket_client: Optional[PolymarketClient] = None,
        rate_limit_delay: Optional[float] = None
    ):
        """Initialize the market poller.
        
        Args:
            kalshi_client: Kalshi client instance. If None, creates a new one.
            polymarket_client: Polymarket client instance. If None, creates a new one.
            rate_limit_delay: Delay between requests. If None, uses config default.
        """
        self.kalshi_client = kalshi_client or KalshiClient(
            rate_limit_delay=rate_limit_delay or EngineConfig.RATE_LIMIT_DELAY
        )
        self.polymarket_client = polymarket_client or PolymarketClient(
            rate_limit_delay=rate_limit_delay or EngineConfig.RATE_LIMIT_DELAY
        )
    
    def poll_exchange(
        self,
        exchange_client: ExchangeClient,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Market]:
        """Fetch all markets from an exchange.
        
        Args:
            exchange_client: Exchange client instance (KalshiClient or PolymarketClient).
            progress_callback: Optional callback function(count, total) for progress updates.
            
        Returns:
            List of validated Market instances.
            
        Raises:
            PollingError: If polling fails.
        """
        exchange_name = exchange_client.exchange_name
        logger.info(f"Polling markets from {exchange_name}...")
        
        try:
            # Fetch all markets
            markets = exchange_client.fetch_all_markets(
                progress_callback=progress_callback
            )
            
            logger.info(f"Fetched {len(markets)} markets from {exchange_name}")
            
            # Validate each market
            validated_markets = []
            for i, market in enumerate(markets):
                try:
                    self._validate_market(market)
                    validated_markets.append(market)
                except MarketValidationError as e:
                    logger.warning(
                        f"Skipping invalid market {market.market_id} from {exchange_name}: {e}"
                    )
                    continue
            
            logger.info(
                f"Validated {len(validated_markets)}/{len(markets)} markets from {exchange_name}"
            )
            
            return validated_markets
            
        except Exception as e:
            error_msg = f"Failed to poll markets from {exchange_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise PollingError(error_msg) from e
    
    def poll_all(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> dict[str, List[Market]]:
        """Poll markets from both exchanges.
        
        Args:
            progress_callback: Optional callback function(exchange, count, total) for progress.
            
        Returns:
            Dictionary mapping exchange names to lists of markets.
            
        Raises:
            PollingError: If polling fails for either exchange.
        """
        results = {}
        
        # Poll Kalshi
        try:
            kalshi_callback = None
            if progress_callback:
                def kalshi_progress(count, total):
                    progress_callback('kalshi', count, total)
                kalshi_callback = kalshi_progress
            
            results['kalshi'] = self.poll_exchange(self.kalshi_client, kalshi_callback)
        except PollingError as e:
            logger.error(f"Failed to poll Kalshi: {e}")
            results['kalshi'] = []
            # Continue to try Polymarket even if Kalshi fails
        
        # Poll Polymarket
        try:
            polymarket_callback = None
            if progress_callback:
                def polymarket_progress(count, total):
                    progress_callback('polymarket', count, total)
                polymarket_callback = polymarket_progress
            
            results['polymarket'] = self.poll_exchange(
                self.polymarket_client,
                polymarket_callback
            )
        except PollingError as e:
            logger.error(f"Failed to poll Polymarket: {e}")
            results['polymarket'] = []
            # Continue even if Polymarket fails
        
        total_markets = len(results.get('kalshi', [])) + len(results.get('polymarket', []))
        logger.info(f"Polled {total_markets} total markets across both exchanges")
        
        return results
    
    def _validate_market(self, market: Market) -> None:
        """Validate a market before processing.
        
        Args:
            market: Market instance to validate.
            
        Raises:
            MarketValidationError: If validation fails.
        """
        # Convert market to dict for validation
        market_dict = {
            'market_id': market.market_id,
            'exchange': market.exchange,
            'name': market.name,
            'rules': market.rules,
            'resolve_date': market.metadata.resolve_date,
            'resolve_time': market.metadata.resolve_time,
            'category': market.metadata.category,
            'subcategory': market.metadata.subcategory,
            'tags': market.metadata.tags,
            'description': market.metadata.description,
            'image_url': market.metadata.image_url,
            'liquidity': market.metadata.liquidity,
            'volume': market.metadata.volume,
        }
        
        validate_market_data(market_dict)

