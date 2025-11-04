"""Tests for Kalshi client."""

import pytest
from unittest.mock import Mock, patch
from exchange.clients.kalshi_client import KalshiClient
from exchange.models import Market, OrderBook, MarketMetadata
from exchange.dome_api import DomeAPIError


class TestKalshiClient:
    """Test suite for KalshiClient."""
    
    @pytest.fixture
    def client(self):
        """Create a KalshiClient instance for testing."""
        return KalshiClient(dome_api_key="test_key")
    
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
            "data": {
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
        }
    
    def test_client_initialization(self, client):
        """Test that KalshiClient initializes correctly."""
        assert client.exchange_name == "kalshi"
        assert client.dome_client is not None
    
    @patch.object(KalshiClient, 'dome_client')
    def test_fetch_all_markets_success(self, mock_dome_client, client, sample_market_data):
        """Test fetching all markets successfully."""
        # Mock the API response
        mock_dome_client.get_kalshi_markets.return_value = {
            "data": [sample_market_data]
        }
        
        markets = client.fetch_all_markets()
        
        assert len(markets) == 1
        assert isinstance(markets[0], Market)
        assert markets[0].market_id == "TEST-123"
        assert markets[0].name == "Test Market"
        assert markets[0].exchange == "kalshi"
    
    @patch.object(KalshiClient, 'dome_client')
    def test_fetch_all_markets_empty_list(self, mock_dome_client, client):
        """Test fetching all markets when API returns empty list."""
        mock_dome_client.get_kalshi_markets.return_value = []
        
        markets = client.fetch_all_markets()
        
        assert markets == []
    
    @patch.object(KalshiClient, 'dome_client')
    def test_fetch_all_markets_api_error(self, mock_dome_client, client):
        """Test that API errors are properly raised."""
        mock_dome_client.get_kalshi_markets.side_effect = DomeAPIError("API Error")
        
        with pytest.raises(DomeAPIError):
            client.fetch_all_markets()
    
    @patch.object(KalshiClient, 'dome_client')
    def test_fetch_orderbook_success(self, mock_dome_client, client, sample_orderbook_data):
        """Test fetching orderbook successfully."""
        mock_dome_client.get_kalshi_orderbook.return_value = sample_orderbook_data
        
        orderbook = client.fetch_orderbook("TEST-123")
        
        assert isinstance(orderbook, OrderBook)
        assert orderbook.market_id == "TEST-123"
        assert len(orderbook.bids) > 0
        assert len(orderbook.asks) > 0
        # Bids should be sorted descending
        assert orderbook.bids[0].price >= orderbook.bids[1].price
        # Asks should be sorted ascending
        assert orderbook.asks[0].price <= orderbook.asks[1].price
    
    @patch.object(KalshiClient, 'dome_client')
    def test_fetch_market_details_success(self, mock_dome_client, client, sample_market_data):
        """Test fetching market details successfully."""
        mock_dome_client.get_kalshi_market_details.return_value = {
            "data": sample_market_data
        }
        
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

