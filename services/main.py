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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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
    
    args = parser.parse_args()
    
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

