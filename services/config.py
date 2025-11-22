"""Configuration for service orchestration."""

import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ServiceConfig:
    """Configuration for service orchestration.
    
    Controls which services to run, websocket connection settings,
    and various timing/connection settings.
    """
    # Which services to run
    run_arbitrage: bool = True
    run_market_polling: bool = False  # Not implemented yet
    
    # Connection mode
    use_websockets: bool = True  # Use websockets for orderbook updates
    
    # Polling intervals (seconds)
    arbitrage_poll_interval: int = 60  # How often to run arbitrage calculations
    market_poll_interval: int = 3600  # How often to poll for new markets
    
    # Websocket settings
    websocket_reconnect_delay: float = 1.0  # Initial reconnect delay
    websocket_max_reconnect_delay: float = 60.0  # Maximum reconnect delay
    websocket_refresh_subscriptions_interval: int = 300  # Refresh subscriptions every 5 minutes
    
    # Database settings
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    
    # Exchange API keys (optional, for authenticated requests)
    kalshi_api_key_id: Optional[str] = None
    kalshi_private_key: Optional[str] = None
    kalshi_private_key_path: Optional[str] = None
    polymarket_api_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'ServiceConfig':
        """Create configuration from environment variables.
        
        Returns:
            ServiceConfig instance with values from environment.
        """
        return cls(
            run_arbitrage=os.getenv('RUN_ARBITRAGE', 'true').lower() == 'true',
            run_market_polling=os.getenv('RUN_MARKET_POLLING', 'false').lower() == 'true',
            use_websockets=os.getenv('USE_WEBSOCKETS', 'true').lower() == 'true',
            arbitrage_poll_interval=int(os.getenv('ARBITRAGE_POLL_INTERVAL', '60')),
            market_poll_interval=int(os.getenv('MARKET_POLL_INTERVAL', '3600')),
            websocket_reconnect_delay=float(os.getenv('WEBSOCKET_RECONNECT_DELAY', '1.0')),
            websocket_max_reconnect_delay=float(os.getenv('WEBSOCKET_MAX_RECONNECT_DELAY', '60.0')),
            websocket_refresh_subscriptions_interval=int(os.getenv('WEBSOCKET_REFRESH_SUBSCRIPTIONS_INTERVAL', '300')),
            supabase_url=os.getenv('SUPABASE_URL'),
            supabase_key=os.getenv('SUPABASE_KEY'),
            kalshi_api_key_id=os.getenv('KALSHI_API_KEY_ID'),
            kalshi_private_key=os.getenv('KALSHI_PRIVATE_KEY'),
            kalshi_private_key_path=os.getenv('KALSHI_PRIVATE_KEY_PATH'),
            polymarket_api_key=os.getenv('POLYMARKET_API_KEY'),
        )
    
    def validate(self) -> List[str]:
        """Validate configuration.
        
        Returns:
            List of validation error messages. Empty list if valid.
        """
        errors = []
        
        if self.run_arbitrage or self.run_market_polling:
            if not self.supabase_url:
                errors.append("SUPABASE_URL is required when running services")
            if not self.supabase_key:
                errors.append("SUPABASE_KEY is required when running services")
        
        if self.arbitrage_poll_interval < 1:
            errors.append("arbitrage_poll_interval must be at least 1 second")
        
        if self.market_poll_interval < 1:
            errors.append("market_poll_interval must be at least 1 second")
        
        return errors

