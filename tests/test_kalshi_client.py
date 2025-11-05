"""Tests for Kalshi client."""

import pytest
from unittest.mock import Mock
from exchange.clients.kalshi_client import KalshiClient
from exchange.models import Market, OrderBook, MarketMetadata
from exchange.errors import KalshiAPIError


class TestKalshiClient:
    """Test suite for KalshiClient."""
    
    @pytest.fixture
    def client(self):
        """Create a KalshiClient instance for testing."""
        client = KalshiClient()
        # Mock the SDK client
        client.sdk_client = Mock()
        return client
    
    @pytest.fixture
    def sample_market_data(self):
        """Sample market data from Kalshi API."""
        return {
            "ticker": "TEST-123",
            "title": "Test Market",
            "rules": "Test rules",
            "description": "Test description",
            "category": "Politics",
            "expected_expiration_time": "2024-12-31T23:59:59Z",
        }
    
    @pytest.fixture
    def sample_orderbook_data(self):
        """Sample orderbook data from Kalshi API."""
        return {
            "yes": {
                "bids": [
                    {"price": 0.65, "quantity": 100},
                    {"price": 0.64, "quantity": 200},
                ],
                "asks": [
                    {"price": 0.66, "quantity": 150},
                    {"price": 0.67, "quantity": 250},
                ],
            },
            "no": {
                "bids": [
                    {"price": 0.35, "quantity": 100},
                    {"price": 0.34, "quantity": 200},
                ],
                "asks": [
                    {"price": 0.36, "quantity": 150},
                    {"price": 0.37, "quantity": 250},
                ],
            },
        }
    
    def test_client_initialization(self, client):
        """Test that KalshiClient initializes correctly."""
        assert client.exchange_name == "kalshi"
        assert client.host == "https://api.elections.kalshi.com/trade-api/v2"
        assert client.sdk_client is not None
    
    def test_fetch_all_markets_success(self, client, sample_market_data):
        """Test fetching all markets successfully."""
        # Mock SDK response with pagination
        mock_response = Mock()
        mock_response.markets = [sample_market_data]
        mock_response.cursor = None  # No more pages
        client.sdk_client.get_markets = Mock(return_value=mock_response)
        
        markets = client.fetch_all_markets()
        
        assert len(markets) == 1
        assert isinstance(markets[0], Market)
        assert markets[0].market_id == "TEST-123"
        assert markets[0].name == "Test Market"
        assert markets[0].exchange == "kalshi"
    
    def test_fetch_all_markets_pagination(self, client, sample_market_data):
        """Test fetching all markets with pagination."""
        # Mock first page
        mock_response_page1 = Mock()
        mock_response_page1.markets = [sample_market_data]
        mock_response_page1.cursor = "cursor123"
        
        # Mock second page
        sample_market_data_2 = sample_market_data.copy()
        sample_market_data_2["ticker"] = "TEST-456"
        sample_market_data_2["title"] = "Test Market 2"
        mock_response_page2 = Mock()
        mock_response_page2.markets = [sample_market_data_2]
        mock_response_page2.cursor = None  # No more pages
        
        client.sdk_client.get_markets = Mock(side_effect=[mock_response_page1, mock_response_page2])
        
        markets = client.fetch_all_markets()
        
        assert len(markets) == 2
        assert markets[0].market_id == "TEST-123"
        assert markets[1].market_id == "TEST-456"
    
    def test_fetch_all_markets_with_limit(self, client, sample_market_data):
        """Test fetching markets with limit."""
        mock_response = Mock()
        mock_response.markets = [sample_market_data]
        mock_response.cursor = None
        client.sdk_client.get_markets = Mock(return_value=mock_response)
        
        markets = client.fetch_all_markets(limit=1)
        
        assert len(markets) == 1
    
    def test_fetch_all_markets_with_progress_callback(self, client, sample_market_data):
        """Test fetching markets with progress callback."""
        mock_response = Mock()
        mock_response.markets = [sample_market_data]
        mock_response.cursor = None
        client.sdk_client.get_markets = Mock(return_value=mock_response)
        
        progress_calls = []
        def progress_callback(page_num, total):
            progress_calls.append((page_num, total))
        
        markets = client.fetch_all_markets(progress_callback=progress_callback)
        
        assert len(markets) == 1
        assert len(progress_calls) == 1
        assert progress_calls[0] == (1, 1)
    
    def test_fetch_all_markets_empty_list(self, client):
        """Test fetching all markets when API returns empty list."""
        mock_response = Mock()
        mock_response.markets = []
        mock_response.cursor = None
        client.sdk_client.get_markets = Mock(return_value=mock_response)
        
        markets = client.fetch_all_markets()
        
        assert markets == []
    
    def test_fetch_all_markets_api_error(self, client):
        """Test that API errors are properly raised."""
        from kalshi_python.exceptions import ApiException
        client.sdk_client.get_markets = Mock(side_effect=ApiException(status=500, reason="Server Error"))
        
        with pytest.raises(KalshiAPIError):
            client.fetch_all_markets()
    
    def test_fetch_all_markets_rate_limit_retry(self, client, sample_market_data):
        """Test that rate limit errors trigger retry."""
        from kalshi_python.exceptions import ApiException
        
        # First call raises rate limit, second succeeds
        mock_response = Mock()
        mock_response.markets = [sample_market_data]
        mock_response.cursor = None
        
        rate_limit_error = ApiException(status=429, reason="Rate Limited")
        client.sdk_client.get_markets = Mock(side_effect=[rate_limit_error, mock_response])
        
        markets = client.fetch_all_markets()
        
        assert len(markets) == 1
        assert client.sdk_client.get_markets.call_count == 2
    
    def test_fetch_orderbook_success(self, client, sample_orderbook_data):
        """Test fetching orderbook successfully."""
        # Mock SDK response
        client.sdk_client.get_orderbook = Mock(return_value=sample_orderbook_data)
        
        orderbook = client.fetch_orderbook("TEST-123")
        
        assert isinstance(orderbook, OrderBook)
        assert orderbook.market_id == "TEST-123"
        assert len(orderbook.bids) > 0
        assert len(orderbook.asks) > 0
        # Bids should be sorted descending
        assert orderbook.bids[0].price >= orderbook.bids[1].price
        # Asks should be sorted ascending
        assert orderbook.asks[0].price <= orderbook.asks[1].price
    
    def test_fetch_market_details_success(self, client, sample_market_data):
        """Test fetching market details successfully."""
        # Mock SDK response
        client.sdk_client.get_market = Mock(return_value=sample_market_data)
        
        market = client.fetch_market_details("TEST-123")
        
        assert isinstance(market, Market)
        assert market.market_id == "TEST-123"
        assert market.name == "Test Market"
        assert market.rules == "Test rules"
        assert isinstance(market.metadata, MarketMetadata)
    
    def test_normalize_market(self, client, sample_market_data):
        """Test market data normalization."""
        market = client._normalize_market(sample_market_data)
        
        assert market.market_id == "TEST-123"
        assert market.name == "Test Market"
        assert market.rules == "Test rules"
        assert market.exchange == "kalshi"
        assert market.metadata.category == "Politics"
    
    def test_normalize_orderbook(self, client, sample_orderbook_data):
        """Test orderbook data normalization."""
        orderbook = client._normalize_orderbook("TEST-123", sample_orderbook_data)
        
        assert orderbook.market_id == "TEST-123"
        assert len(orderbook.bids) > 0
        assert len(orderbook.asks) > 0
        # Verify sorting
        for i in range(len(orderbook.bids) - 1):
            assert orderbook.bids[i].price >= orderbook.bids[i + 1].price
        for i in range(len(orderbook.asks) - 1):
            assert orderbook.asks[i].price <= orderbook.asks[i + 1].price
