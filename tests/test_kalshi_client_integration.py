"""Integration tests for Kalshi client.

These tests make real API calls to Kalshi. They are skipped by default unless
the KALSHI_API_KEY_ID environment variable is set (or tests are run with -m integration).
"""

import pytest
import os
from exchange.clients.kalshi_client import KalshiClient
from exchange.models import Market, OrderBook
from exchange.errors import KalshiAPIError


@pytest.mark.integration
class TestKalshiClientIntegration:
    """Integration tests for KalshiClient that make real API calls."""
    
    @pytest.fixture
    def client(self):
        """Create a KalshiClient instance for integration testing."""
        return KalshiClient(rate_limit_delay=0.2)  # Slightly slower for real API
    
    def test_fetch_all_markets_integration(self, client):
        """Test fetching markets from real Kalshi API."""
        # Fetch a small number of markets to avoid long test times
        markets = client.fetch_all_markets(limit=10, max_pages=2)
        
        assert isinstance(markets, list)
        assert len(markets) <= 10
        
        if len(markets) > 0:
            # Verify market structure
            market = markets[0]
            assert isinstance(market, Market)
            assert market.exchange == "kalshi"
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
        """Test fetching market details from real Kalshi API."""
        # First get a list of markets
        markets = client.fetch_all_markets(limit=1)
        
        if len(markets) == 0:
            pytest.skip("No markets available to test")
        
        market_id = markets[0].market_id
        
        # Fetch details for that market
        market = client.fetch_market_details(market_id)
        
        assert isinstance(market, Market)
        assert market.market_id == market_id
        assert market.exchange == "kalshi"
        assert market.name
    
    def test_fetch_orderbook_integration(self, client):
        """Test fetching orderbook from real Kalshi API."""
        # First get a list of markets
        markets = client.fetch_all_markets(limit=1)
        
        if len(markets) == 0:
            pytest.skip("No markets available to test")
        
        market_id = markets[0].market_id
        
        # Fetch orderbook for that market
        orderbook = client.fetch_orderbook(market_id)
        
        assert isinstance(orderbook, OrderBook)
        assert orderbook.market_id == market_id
        assert isinstance(orderbook.bids, list)
        assert isinstance(orderbook.asks, list)
        # Verify sorting
        if len(orderbook.bids) > 1:
            assert orderbook.bids[0].price >= orderbook.bids[1].price
        if len(orderbook.asks) > 1:
            assert orderbook.asks[0].price <= orderbook.asks[1].price
    
    def test_rate_limiting_integration(self, client):
        """Test that rate limiting works correctly."""
        import time
        
        start_time = time.time()
        
        # Make multiple requests
        markets1 = client.fetch_all_markets(limit=5)
        markets2 = client.fetch_all_markets(limit=5)
        
        elapsed = time.time() - start_time
        
        # Should have taken at least some time due to rate limiting
        # (0.2s delay * 2 requests = at least 0.4s, but allow for some variance)
        assert elapsed >= 0.3  # Allow some variance

