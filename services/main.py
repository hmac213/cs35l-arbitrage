#!/usr/bin/env python3
"""Main entry point for service orchestration."""

import sys
import os
import logging
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from .config import ServiceConfig
from .runner import ServiceRunner

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point for the service runner."""
    parser = argparse.ArgumentParser(description='Run arbitrage and market polling services')
    parser.add_argument(
        '--arbitrage-interval',
        type=int,
        help='Arbitrage calculation interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--market-interval',
        type=int,
        help='Market polling interval in seconds (default: 3600)'
    )
    parser.add_argument(
        '--no-arbitrage',
        action='store_true',
        help='Disable arbitrage service'
    )
    parser.add_argument(
        '--enable-market-polling',
        action='store_true',
        help='Enable market polling service (not implemented yet)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable DEBUG logging level'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Set logging level (default: INFO)'
    )
    
    args = parser.parse_args()
    
    # Configure logging level based on arguments
    log_level = logging.DEBUG if args.debug else logging.INFO
    if args.log_level:
        log_level = getattr(logging, args.log_level.upper())
    
    # Configure logging with the selected level
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True  # Override any existing configuration
    )
    
    logger.info(f"Logging level set to {logging.getLevelName(log_level)}")
    
    # Create configuration from environment
    config = ServiceConfig.from_env()
    
    # Override with command-line arguments
    if args.arbitrage_interval:
        config.arbitrage_poll_interval = args.arbitrage_interval
    if args.market_interval:
        config.market_poll_interval = args.market_interval
    if args.no_arbitrage:
        config.run_arbitrage = False
    if args.enable_market_polling:
        config.run_market_polling = True
    
    # Check required environment variables
    if config.run_arbitrage or config.run_market_polling:
        if not os.getenv('SUPABASE_URL'):
            logger.error("SUPABASE_URL environment variable is required")
            return 1
        
        if not os.getenv('SUPABASE_KEY'):
            logger.error("SUPABASE_KEY environment variable is required")
            return 1
    
    # Create and run service runner
    runner = ServiceRunner(config)
    
    try:
        runner.run()
        return 0
    except Exception as e:
        logger.error(f"Error running services: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

