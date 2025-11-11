"""Configuration for the data engine."""

import os
from typing import Optional


class EngineConfig:
    """Configuration settings for the data engine."""
    
    # Polling intervals (in seconds)
    MARKET_POLL_INTERVAL: int = int(os.getenv('MARKET_POLL_INTERVAL', '300'))  # 5 minutes default
    ORDERBOOK_POLL_INTERVAL: int = int(os.getenv('ORDERBOOK_POLL_INTERVAL', '30'))  # 30 seconds default
    
    # Retry settings
    MAX_RETRIES: int = int(os.getenv('MAX_RETRIES', '3'))
    RETRY_DELAY: float = float(os.getenv('RETRY_DELAY', '1.0'))  # seconds
    
    # Batch sizes
    BATCH_SIZE: int = int(os.getenv('BATCH_SIZE', '100'))  # Markets per batch
    
    # Expiration settings
    EXPIRATION_BUFFER_HOURS: int = int(os.getenv('EXPIRATION_BUFFER_HOURS', '1'))  # Mark expired 1 hour after resolve time
    
    # Rate limiting
    RATE_LIMIT_DELAY: float = float(os.getenv('RATE_LIMIT_DELAY', '0.2'))  # seconds between requests
    
    # Timeout settings
    REQUEST_TIMEOUT: int = int(os.getenv('REQUEST_TIMEOUT', '30'))  # seconds
    
    # Progress callback settings
    PROGRESS_CALLBACK_INTERVAL: int = int(os.getenv('PROGRESS_CALLBACK_INTERVAL', '50'))  # Call every N markets
    
    # Vector DB settings (using pgvector in Supabase via RPC)
    # No additional config needed - uses SUPABASE_URL and SUPABASE_KEY
    
    # OpenAI settings
    OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    EMBEDDING_MODEL: str = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
    
    # Similarity settings
    SIMILARITY_THRESHOLD: float = float(os.getenv('SIMILARITY_THRESHOLD', '0.8'))
    LLM_VERIFICATION_ENABLED: bool = os.getenv('LLM_VERIFICATION_ENABLED', 'true').lower() == 'true'
    
    @classmethod
    def get_market_poll_interval(cls) -> int:
        """Get market polling interval in seconds."""
        return cls.MARKET_POLL_INTERVAL
    
    @classmethod
    def get_orderbook_poll_interval(cls) -> int:
        """Get orderbook polling interval in seconds."""
        return cls.ORDERBOOK_POLL_INTERVAL
    
    @classmethod
    def get_expiration_buffer(cls) -> int:
        """Get expiration buffer in hours."""
        return cls.EXPIRATION_BUFFER_HOURS

