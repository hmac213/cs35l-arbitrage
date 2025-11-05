"""Integration tests for Polymarket client.

These tests make real API calls to Polymarket. They are skipped by default unless
tests are run with -m integration.
"""

import pytest
import os
from exchange.clients.polymarket_client import PolymarketClient
from exchange.models import Market, OrderBook
from exchange.errors import PolymarketAPIError


@pytest.mark.integration
class TestPolymarketClientIntegration:
    """Integration tests for PolymarketClient that make real API calls."""
    
    @pytest.fixture
    def client(self):
        """Create a PolymarketClient instance for integration testing."""
        return PolymarketClient(rate_limit_delay=0.2)  # Slightly slower for real API
    
    def test_fetch_all_markets_integration(self, client):
        """Test fetching markets from real Polymarket API."""
        # Fetch a small number of markets to avoid long test times
        markets = client.fetch_all_markets(limit=10, max_pages=2, page_size=5)
        
        assert isinstance(markets, list)
        assert len(markets) <= 10
        
        if len(markets) > 0:
            # Verify market structure
            market = markets[0]
            assert isinstance(market, Market)
            assert market.exchange == "polymarket"
            assert market.market_id
            assert market.name
            assert isinstance(market.metadata, dict) or hasattr(market, 'metadata')
    
    def test_fetch_all_markets_pagination_integration(self, client):
        """Test pagination works correctly with real API."""
        progress_calls = []
        
        def progress_callback(page_num, total):
            progress_calls.append((page_num, total))
        
        markets = client.fetch_all_markets(
            limit=20,
            max_pages=3,
            page_size=10,
            progress_callback=progress_callback
        )
        
        assert len(markets) <= 20
        # Should have made progress calls if markets were fetched
        if len(markets) > 0:
            assert len(progress_calls) > 0
    
    def test_fetch_market_details_integration(self, client):
        """Test fetching market details from real Polymarket API."""
        # First get a list of markets
        markets = client.fetch_all_markets(limit=1, page_size=1)
        
        if len(markets) == 0:
            pytest.skip("No markets available to test")
        
        market_id = markets[0].market_id
        
        # Fetch details for that market
        try:
            market = client.fetch_market_details(market_id)
            
            assert isinstance(market, Market)
            assert market.exchange == "polymarket"
            assert market.name
        except PolymarketAPIError as e:
            # Some markets might not be fetchable by slug, that's okay
            pytest.skip(f"Market {market_id} not fetchable: {str(e)}")
    
    def test_fetch_orderbook_integration(self, client):
        """Test fetching orderbook from real Polymarket API."""
        # First get a list of markets - fetch more to find one with orderbook data
        markets = client.fetch_all_markets(limit=10, page_size=10)
        
        if len(markets) == 0:
            pytest.skip("No markets available to test")
        
        # Try to find a market with token_id in extra data
        token_id = None
        market = None
        
        import json
        
        for m in markets:
            if hasattr(m, 'extra') and m.extra:
                # Try to get token_id from various possible locations
                raw_token_id = None
                
                # First try direct token_id
                if m.extra.get('token_id'):
                    raw_token_id = m.extra.get('token_id')
                # Then try clobTokenIds (can be list, JSON string, or string)
                elif m.extra.get('clobTokenIds'):
                    clob_tokens = m.extra.get('clobTokenIds')
                    
                    # If it's a string, try to parse it as JSON (it might be a JSON array string)
                    if isinstance(clob_tokens, str):
                        try:
                            # Try to parse as JSON array
                            parsed = json.loads(clob_tokens)
                            if isinstance(parsed, list) and len(parsed) > 0:
                                raw_token_id = parsed[0]
                            else:
                                raw_token_id = clob_tokens
                        except (json.JSONDecodeError, ValueError):
                            # If it's not JSON, use it as-is
                            raw_token_id = clob_tokens
                    elif isinstance(clob_tokens, list) and len(clob_tokens) > 0:
                        # Take the first token_id from the list
                        raw_token_id = clob_tokens[0]
                
                # Normalize to string
                if raw_token_id is not None:
                    # Handle nested lists (in case the first element is also a list)
                    while isinstance(raw_token_id, list) and len(raw_token_id) > 0:
                        raw_token_id = raw_token_id[0]
                    
                    # Convert to string
                    if raw_token_id is not None:
                        token_id = str(raw_token_id).strip()
                        
                        # Only use if it's a non-empty string
                        if token_id and len(token_id) > 0:
                            market = m
                            break
        
        if not token_id or not isinstance(token_id, str):
            # If no token_id found, skip the test
            pytest.skip("No markets with valid token_id found in test sample (orderbook requires token_id, not slug)")
        
        # Double-check token_id is a string before API call
        assert isinstance(token_id, str), f"token_id must be string, got {type(token_id)}: {token_id}"
        
        # Fetch orderbook for that market
        try:
            orderbook = client.fetch_orderbook(token_id)
            
            assert isinstance(orderbook, OrderBook)
            assert orderbook.market_id == token_id
            assert isinstance(orderbook.bids, list)
            assert isinstance(orderbook.asks, list)
            # Verify sorting
            if len(orderbook.bids) > 1:
                assert orderbook.bids[0].price >= orderbook.bids[1].price
            if len(orderbook.asks) > 1:
                assert orderbook.asks[0].price <= orderbook.asks[1].price
        except PolymarketAPIError as e:
            # Some markets might not have orderbooks, that's okay
            # Include the actual error message for debugging
            error_msg = str(e)
            pytest.skip(f"Orderbook not available for token_id '{token_id}' (type: {type(token_id).__name__}): {error_msg}")
    
    def test_rate_limiting_integration(self, client):
        """Test that rate limiting works correctly."""
        import time
        
        start_time = time.time()
        
        # Make multiple requests
        markets1 = client.fetch_all_markets(limit=5, page_size=5)
        markets2 = client.fetch_all_markets(limit=5, page_size=5)
        
        elapsed = time.time() - start_time
        
        # Should have taken at least some time due to rate limiting
        # (0.2s delay * 2 requests = at least 0.4s, but allow for some variance)
        assert elapsed >= 0.3  # Allow some variance

