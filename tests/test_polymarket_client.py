"""Tests for Polymarket client."""

import pytest
from unittest.mock import Mock
from exchange.clients.polymarket_client import PolymarketClient
from exchange.models import Market, OrderBook, MarketMetadata
from exchange.errors import PolymarketAPIError


class TestPolymarketClient:
    """Test suite for PolymarketClient."""
    
    @pytest.fixture
    def client(self):
        """Create a PolymarketClient instance for testing."""
        return PolymarketClient()
    
    @pytest.fixture
    def sample_market_data(self):
        """Sample market data from Polymarket API."""
        return {
            "slug": "test-market-slug",
            "question": "Test Market Question",
            "description": "Test description",
            "category": "Politics",
            "endDate": "2024-12-31T23:59:59Z",
            "conditionId": "123456789",
            "clobTokenIds": ["987654321"],
        }
    
    @pytest.fixture
    def sample_orderbook_data(self):
        """Sample orderbook data from Polymarket API."""
        return {
            "bids": [
                {"price": 0.65, "size": 100, "maker": "0x123"},
                {"price": 0.64, "size": 200, "maker": "0x456"},
            ],
            "asks": [
                {"price": 0.66, "size": 150, "maker": "0x789"},
                {"price": 0.67, "size": 250, "maker": "0xabc"},
            ],
        }
    
    def test_client_initialization(self, client):
        """Test that PolymarketClient initializes correctly."""
        assert client.exchange_name == "polymarket"
        assert client.gamma_api_url == "https://gamma-api.polymarket.com"
        assert client.clob_url == "https://clob.polymarket.com"
        assert client.session is not None
    
    def test_fetch_all_markets_success(self, client, sample_market_data):
        """Test fetching all markets successfully."""
        # Mock the Gamma API request method
        event_data = {"id": "event123", "title": "Test Event", **sample_market_data}
        client._make_gamma_request = Mock(return_value=[event_data])
        
        markets = client.fetch_all_markets()
        
        assert len(markets) == 1
        assert isinstance(markets[0], Market)
        assert markets[0].market_id == "test-market-slug"
        assert markets[0].name == "Test Market Question"
        assert markets[0].exchange == "polymarket"
    
    def test_fetch_all_markets_pagination(self, client, sample_market_data):
        """Test fetching all markets with pagination."""
        event_data_1 = {"id": "event1", **sample_market_data}
        sample_market_data_2 = sample_market_data.copy()
        sample_market_data_2["slug"] = "test-market-2"
        sample_market_data_2["question"] = "Test Market 2"
        event_data_2 = {"id": "event2", **sample_market_data_2}
        
        # First page returns 1 event, second page returns 1 event, third returns empty
        client._make_gamma_request = Mock(side_effect=[[event_data_1], [event_data_2], []])
        
        markets = client.fetch_all_markets(page_size=1)
        
        assert len(markets) == 2
        assert markets[0].market_id == "test-market-slug"
        assert markets[1].market_id == "test-market-2"
    
    def test_fetch_all_markets_with_limit(self, client, sample_market_data):
        """Test fetching markets with limit."""
        event_data = {"id": "event123", **sample_market_data}
        client._make_gamma_request = Mock(return_value=[event_data])
        
        markets = client.fetch_all_markets(limit=1)
        
        assert len(markets) == 1
    
    def test_fetch_all_markets_with_progress_callback(self, client, sample_market_data):
        """Test fetching markets with progress callback."""
        event_data = {"id": "event123", **sample_market_data}
        client._make_gamma_request = Mock(return_value=[event_data])
        
        progress_calls = []
        def progress_callback(page_num, total):
            progress_calls.append((page_num, total))
        
        markets = client.fetch_all_markets(progress_callback=progress_callback)
        
        assert len(markets) == 1
        assert len(progress_calls) >= 1
    
    def test_fetch_all_markets_empty_list(self, client):
        """Test fetching all markets when API returns empty list."""
        client._make_gamma_request = Mock(return_value=[])
        
        markets = client.fetch_all_markets()
        
        assert markets == []
    
    def test_fetch_all_markets_api_error(self, client):
        """Test that API errors are properly raised."""
        client._make_gamma_request = Mock(side_effect=PolymarketAPIError("API Error"))
        
        with pytest.raises(PolymarketAPIError):
            client.fetch_all_markets()
    
    def test_fetch_all_markets_partial_failure(self, client, sample_market_data):
        """Test that partial failures return what was fetched."""
        event_data = {"id": "event123", **sample_market_data}
        # First call succeeds, second fails
        client._make_gamma_request = Mock(side_effect=[[event_data], PolymarketAPIError("API Error")])
        
        markets = client.fetch_all_markets()
        
        # Should return what was successfully fetched
        assert len(markets) == 1
    
    def test_fetch_orderbook_success(self, client, sample_orderbook_data):
        """Test fetching orderbook successfully."""
        client._make_clob_request = Mock(return_value=sample_orderbook_data)
        
        orderbook = client.fetch_orderbook("test-market-slug")
        
        assert isinstance(orderbook, OrderBook)
        assert orderbook.market_id == "test-market-slug"
        assert len(orderbook.bids) > 0
        assert len(orderbook.asks) > 0
        # Bids should be sorted descending
        assert orderbook.bids[0].price >= orderbook.bids[1].price
        # Asks should be sorted ascending
        assert orderbook.asks[0].price <= orderbook.asks[1].price
    
    def test_fetch_market_details_success(self, client, sample_market_data):
        """Test fetching market details successfully."""
        event_data = {"id": "event123", **sample_market_data}
        client._make_gamma_request = Mock(return_value={"event": event_data})
        
        market = client.fetch_market_details("test-market-slug")
        
        assert isinstance(market, Market)
        assert market.market_id == "test-market-slug"
        assert market.name == "Test Market Question"
        assert isinstance(market.metadata, MarketMetadata)
    
    def test_normalize_market(self, client, sample_market_data):
        """Test market data normalization."""
        market = client._normalize_market(sample_market_data)
        
        assert market.market_id == "test-market-slug"
        assert market.name == "Test Market Question"
        assert market.exchange == "polymarket"
        assert market.metadata.category == "Politics"
        assert market.metadata.extra['conditionId'] == "123456789"
    
    def test_normalize_orderbook(self, client, sample_orderbook_data):
        """Test orderbook data normalization."""
        orderbook = client._normalize_orderbook("test-market-slug", sample_orderbook_data)
        
        assert orderbook.market_id == "test-market-slug"
        assert len(orderbook.bids) == 2
        assert len(orderbook.asks) == 2
        # Verify sorting
        assert orderbook.bids[0].price == 0.65
        assert orderbook.bids[1].price == 0.64
        assert orderbook.asks[0].price == 0.66
        assert orderbook.asks[1].price == 0.67
        # Verify metadata is preserved
        assert orderbook.bids[0].metadata['maker'] == "0x123"
