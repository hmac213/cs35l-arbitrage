"""Main service orchestrator."""

import logging
import signal
import sys
from typing import Optional

from db.client import SupabaseClient
from .config import ServiceConfig
from .arbitrage_runner import ArbitrageRunner

logger = logging.getLogger(__name__)


class ServiceRunner:
    """Main orchestrator for all services.
    
    Manages lifecycle of configured services and handles graceful shutdown.
    """
    
    def __init__(self, config: ServiceConfig):
        """Initialize the service runner.
        
        Args:
            config: Service configuration.
        """
        self.config = config
        self.arbitrage_runner: Optional[ArbitrageRunner] = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def start(self) -> None:
        """Start all configured services."""
        # Validate configuration
        errors = self.config.validate()
        if errors:
            logger.error("Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            raise ValueError("Invalid configuration")
        
        logger.info("Starting services...")
        logger.info(f"Configuration: websockets={self.config.use_websockets}, "
                   f"arbitrage={self.config.run_arbitrage}, "
                   f"market_polling={self.config.run_market_polling}")
        
        # Start arbitrage service if enabled
        if self.config.run_arbitrage:
            logger.info("Starting arbitrage service...")
            self.arbitrage_runner = ArbitrageRunner(
                config=self.config
            )
            self.arbitrage_runner.start()
            logger.info("Arbitrage service started")
        
        # Start market polling service if enabled (not implemented yet)
        if self.config.run_market_polling:
            logger.warning("Market polling service is not yet implemented")
        
        logger.info("All services started")
    
    def stop(self) -> None:
        """Stop all services."""
        logger.info("Stopping services...")
        
        if self.arbitrage_runner:
            self.arbitrage_runner.stop()
            logger.info("Arbitrage service stopped")
        
        logger.info("All services stopped")
    
    def run(self) -> None:
        """Run services until interrupted."""
        try:
            self.start()
            
            # Keep running until interrupted
            import time
            last_stats_log = time.time()
            stats_interval = 30  # Log queue health every 30 seconds
            
            while True:
                time.sleep(1)
                
                # Log queue health stats periodically
                if self.arbitrage_runner:
                    current_time = time.time()
                    if current_time - last_stats_log >= stats_interval:
                        stats = self.arbitrage_runner.get_stats()
                        if stats.get('running') and 'queue' in stats:
                            queue_stats = stats['queue']
                            logger.info(
                                f"Queue health: enqueued={queue_stats.get('enqueued', 0)}, "
                                f"processed={queue_stats.get('processed', 0)}, "
                                f"dropped={queue_stats.get('dropped', 0)}, "
                                f"queue_size={queue_stats.get('queue_size', 0)}, "
                                f"circuit={queue_stats.get('circuit_state', 'unknown')}, "
                                f"opportunities={queue_stats.get('opportunities_found', 0)}"
                            )
                        last_stats_log = current_time
        
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Error running services: {e}", exc_info=True)
        finally:
            self.stop()
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

