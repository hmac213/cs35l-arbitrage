#!/usr/bin/env python3
"""Test script to diagnose Kalshi orderbook parsing issues."""

import json
import sys
import os
from pprint import pprint

# Add project root to path (go up one level from tests/)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(project_root, '.env'))
except ImportError:
    pass  # dotenv not available, rely on system env vars

from exchange.clients.kalshi_client import KalshiClient
from engine.orderbook_poller import OrderbookPoller
from db.models import DatabaseMarket

# Try to import SupabaseClient, but make it optional
try:
    from db.client import SupabaseClient
    SUPABASE_AVAILABLE = True
except Exception:
    SUPABASE_AVAILABLE = False
    SupabaseClient = None

def test_orderbook_parsing(market_id: str):
    """Test orderbook parsing for a specific market."""
    print(f"\n{'='*80}")
    print(f"Testing orderbook parsing for market: {market_id}")
    print(f"{'='*80}\n")
    
    # Initialize clients
    kalshi_client = KalshiClient()
    
    # Try to initialize database client (optional)
    db_client = None
    if SUPABASE_AVAILABLE:
        try:
            db_client = SupabaseClient()
        except Exception as e:
            print(f"Warning: Could not initialize SupabaseClient: {e}")
            print("  Continuing without database access...")
    
    poller = OrderbookPoller(kalshi_client=kalshi_client, db_client=db_client)
    
    # Step 1: Fetch raw orderbook from API
    print("Step 1: Fetching raw orderbook from Kalshi API...")
    try:
        orderbook = kalshi_client.fetch_orderbook(market_id)
        print(f"✓ Successfully fetched orderbook")
        print(f"  - Timestamp: {orderbook.timestamp}")
        print(f"  - Number of bids: {len(orderbook.bids)}")
        print(f"  - Number of asks: {len(orderbook.asks)}")
    except Exception as e:
        print(f"✗ Failed to fetch orderbook: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 2: Inspect raw API response (from metadata)
    print("\nStep 2: Inspecting raw API response structure...")
    metadata = orderbook.metadata or {}
    if 'raw' in metadata:
        raw_data = metadata['raw']
        print(f"Raw API response keys: {list(raw_data.keys()) if isinstance(raw_data, dict) else 'Not a dict'}")
        
        # Check for nested orderbook
        if isinstance(raw_data, dict) and 'orderbook' in raw_data:
            orderbook_data = raw_data['orderbook']
            print(f"Nested 'orderbook' keys: {list(orderbook_data.keys()) if isinstance(orderbook_data, dict) else 'Not a dict'}")
            if isinstance(orderbook_data, dict):
                if 'yes' in orderbook_data:
                    yes_data = orderbook_data['yes']
                    print(f"  - 'yes' type: {type(yes_data)}, value: {yes_data[:3] if isinstance(yes_data, list) and len(yes_data) > 0 else yes_data}")
                if 'no' in orderbook_data:
                    no_data = orderbook_data['no']
                    print(f"  - 'no' type: {type(no_data)}, value: {no_data[:3] if isinstance(no_data, list) and len(no_data) > 0 else no_data}")
        elif isinstance(raw_data, dict):
            if 'yes' in raw_data:
                yes_data = raw_data['yes']
                print(f"  - 'yes' type: {type(yes_data)}, value: {yes_data[:3] if isinstance(yes_data, list) and len(yes_data) > 0 else yes_data}")
            if 'no' in raw_data:
                no_data = raw_data['no']
                print(f"  - 'no' type: {type(no_data)}, value: {no_data[:3] if isinstance(no_data, list) and len(no_data) > 0 else no_data}")
    
    # Check metadata for yes/no structure
    print("\nStep 3: Checking metadata for yes/no structure...")
    if 'yes' in metadata:
        yes_data = metadata['yes']
        print(f"  - Metadata has 'yes': {type(yes_data)}")
        if isinstance(yes_data, list):
            print(f"    - List length: {len(yes_data)}")
            if len(yes_data) > 0:
                print(f"    - First entry: {yes_data[0]}")
        elif isinstance(yes_data, dict):
            print(f"    - Dict keys: {list(yes_data.keys())}")
    else:
        print("  - Metadata does NOT have 'yes' key")
    
    if 'no' in metadata:
        no_data = metadata['no']
        print(f"  - Metadata has 'no': {type(no_data)}")
        if isinstance(no_data, list):
            print(f"    - List length: {len(no_data)}")
            if len(no_data) > 0:
                print(f"    - First entry: {no_data[0]}")
        elif isinstance(no_data, dict):
            print(f"    - Dict keys: {list(no_data.keys())}")
    else:
        print("  - Metadata does NOT have 'no' key")
    
    # Step 4: Inspect normalized orderbook entries
    print("\nStep 4: Inspecting normalized orderbook entries...")
    print(f"Bids ({len(orderbook.bids)} entries):")
    for i, bid in enumerate(orderbook.bids[:5]):  # Show first 5
        bid_meta = bid.metadata or {}
        print(f"  [{i}] price={bid.price}, qty={bid.quantity}, metadata={bid_meta}")
    
    print(f"\nAsks ({len(orderbook.asks)} entries):")
    for i, ask in enumerate(orderbook.asks[:5]):  # Show first 5
        ask_meta = ask.metadata or {}
        print(f"  [{i}] price={ask.price}, qty={ask.quantity}, metadata={ask_meta}")
    
    # Step 5: Try to get market from database
    print("\nStep 5: Fetching market from database...")
    if db_client:
        try:
            market = db_client.get_market_by_id(market_id, 'kalshi')
            if market:
                print(f"✓ Found market in database: {market.id}")
                print(f"  - Name: {market.name}")
                print(f"  - Exchange: {market.exchange}")
            else:
                print(f"✗ Market not found in database, creating temporary market object...")
                market = DatabaseMarket(
                    id=None,
                    market_id=market_id,
                    exchange='kalshi',
                    name=f"Test market {market_id}",
                    status='active'
                )
        except Exception as e:
            print(f"✗ Error fetching market: {e}")
            market = DatabaseMarket(
                id=None,
                market_id=market_id,
                exchange='kalshi',
                name=f"Test market {market_id}",
                status='active'
            )
    else:
        print("  - Database client not available, creating temporary market object...")
        market = DatabaseMarket(
            id=None,
            market_id=market_id,
            exchange='kalshi',
            name=f"Test market {market_id}",
            status='active'
        )
    
    # Step 6: Try conversion
    print("\nStep 6: Attempting to convert orderbook to snapshot...")
    try:
        snapshot = poller._convert_kalshi_orderbook(orderbook, market)
        print(f"✓ Conversion successful!")
        print(f"  - YES bids: {len(snapshot.yes_bids)}")
        print(f"  - YES asks: {len(snapshot.yes_asks)}")
        print(f"  - NO bids: {len(snapshot.no_bids)}")
        print(f"  - NO asks: {len(snapshot.no_asks)}")
        
        if snapshot.yes_bids:
            print(f"  - Sample YES bid: {snapshot.yes_bids[0]}")
        if snapshot.yes_asks:
            print(f"  - Sample YES ask: {snapshot.yes_asks[0]}")
        if snapshot.no_bids:
            print(f"  - Sample NO bid: {snapshot.no_bids[0]}")
        if snapshot.no_asks:
            print(f"  - Sample NO ask: {snapshot.no_asks[0]}")
    except Exception as e:
        print(f"✗ Conversion failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 7: Full raw response dump (for debugging)
    print("\nStep 7: Full raw API response (first 2000 chars)...")
    if 'raw' in metadata:
        raw_str = json.dumps(metadata['raw'], indent=2)
        print(raw_str[:2000])
        if len(raw_str) > 2000:
            print(f"\n... (truncated, total length: {len(raw_str)} chars)")
    
    print(f"\n{'='*80}\n")

def test_multiple_markets(market_ids: list):
    """Test multiple markets to find patterns in failures."""
    print(f"\n{'='*80}")
    print(f"Testing {len(market_ids)} markets to find patterns...")
    print(f"{'='*80}\n")
    
    kalshi_client = KalshiClient()
    db_client = None
    if SUPABASE_AVAILABLE:
        try:
            db_client = SupabaseClient()
        except Exception:
            pass
    
    poller = OrderbookPoller(kalshi_client=kalshi_client, db_client=db_client)
    
    results = {
        'success': [],
        'failed': [],
        'no_orderbook': []
    }
    
    for market_id in market_ids:
        try:
            print(f"\n--- Testing {market_id} ---")
            orderbook = kalshi_client.fetch_orderbook(market_id)
            
            if not orderbook.bids and not orderbook.asks:
                print(f"  No bids/asks")
                results['no_orderbook'].append(market_id)
                continue
            
            # Check metadata structure
            metadata = orderbook.metadata or {}
            has_top_level_yes_no = 'yes' in metadata or (isinstance(metadata, dict) and 'orderbook' in metadata and 'yes' in metadata.get('orderbook', {}))
            has_entry_metadata = False
            
            if orderbook.bids:
                bid_meta = orderbook.bids[0].metadata or {}
                has_entry_metadata = 'side' in bid_meta or 'type' in bid_meta
            
            if orderbook.asks:
                ask_meta = orderbook.asks[0].metadata or {}
                has_entry_metadata = has_entry_metadata or 'side' in ask_meta or 'type' in ask_meta
            
            print(f"  Bids: {len(orderbook.bids)}, Asks: {len(orderbook.asks)}")
            print(f"  Top-level yes/no: {has_top_level_yes_no}")
            print(f"  Entry metadata (side/type): {has_entry_metadata}")
            
            # Try conversion
            market = DatabaseMarket(
                id=None,
                market_id=market_id,
                exchange='kalshi',
                name=f"Test {market_id}",
                status='active'
            )
            
            snapshot = poller._convert_kalshi_orderbook(orderbook, market)
            
            if snapshot.yes_bids or snapshot.yes_asks:
                print(f"  ✓ SUCCESS: YES bids={len(snapshot.yes_bids)}, YES asks={len(snapshot.yes_asks)}")
                results['success'].append({
                    'market_id': market_id,
                    'has_top_level': has_top_level_yes_no,
                    'has_entry_meta': has_entry_metadata,
                    'yes_bids': len(snapshot.yes_bids),
                    'yes_asks': len(snapshot.yes_asks)
                })
            else:
                print(f"  ✗ FAILED: No yes/no structure extracted")
                results['failed'].append({
                    'market_id': market_id,
                    'has_top_level': has_top_level_yes_no,
                    'has_entry_meta': has_entry_metadata,
                    'bids': len(orderbook.bids),
                    'asks': len(orderbook.asks)
                })
                
                # Show sample entry metadata
                if orderbook.bids:
                    print(f"    Sample bid metadata: {orderbook.bids[0].metadata}")
                if orderbook.asks:
                    print(f"    Sample ask metadata: {orderbook.asks[0].metadata}")
                
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results['failed'].append({'market_id': market_id, 'error': str(e)})
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Success: {len(results['success'])}")
    print(f"Failed: {len(results['failed'])}")
    print(f"No orderbook: {len(results['no_orderbook'])}")
    
    if results['failed']:
        print(f"\nFailed markets analysis:")
        failed_with_entry_meta = [m for m in results['failed'] if m.get('has_entry_meta')]
        failed_without_entry_meta = [m for m in results['failed'] if not m.get('has_entry_meta')]
        print(f"  - With entry metadata: {len(failed_with_entry_meta)}")
        print(f"  - Without entry metadata: {len(failed_without_entry_meta)}")
        
        if failed_without_entry_meta:
            print(f"\n  Markets without entry metadata (should use fallback):")
            for m in failed_without_entry_meta[:5]:
                print(f"    - {m['market_id']}: bids={m.get('bids', 0)}, asks={m.get('asks', 0)}")
    
    if results['success']:
        print(f"\nSuccessful markets analysis:")
        success_with_entry_meta = [m for m in results['success'] if m.get('has_entry_meta')]
        success_without_entry_meta = [m for m in results['success'] if not m.get('has_entry_meta')]
        print(f"  - With entry metadata: {len(success_with_entry_meta)}")
        print(f"  - Without entry metadata (using fallback): {len(success_without_entry_meta)}")
    
    print(f"\n{'='*80}\n")
    return results

if __name__ == "__main__":
    # Test the specific market mentioned in the error
    test_market = "KXOSCARNOMBCASTING-26-TNG"
    
    # Also allow command-line argument
    if len(sys.argv) > 1:
        if sys.argv[1] == "--multi":
            # Test multiple markets from command line
            market_ids = sys.argv[2:] if len(sys.argv) > 2 else [
                "KXOSCARNOMBCASTING-26-TNG",
                # Add more market IDs here to test
            ]
            test_multiple_markets(market_ids)
        else:
            test_market = sys.argv[1]
            test_orderbook_parsing(test_market)
    else:
        test_orderbook_parsing(test_market)

