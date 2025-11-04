"""Tests for Dome API client."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from exchange.dome_api import DomeAPIClient, DomeAPIError


class TestDomeAPIClient:
    """Test suite for DomeAPIClient."""
    
    @pytest.fixture
    def client(self):
        """Create a DomeAPIClient instance for testing."""
        return DomeAPIClient(api_key="test_key")
    
    def test_client_initialization(self, client):
        """Test that DomeAPIClient initializes correctly."""
        assert client.api_key == "test_key"
        assert client.base_url == "http://api.domeapi.io"
        assert client.timeout == 30
        assert "Authorization" in client.session.headers
        assert client.session.headers["Authorization"] == "Bearer test_key"
    
    def test_client_custom_base_url(self):
        """Test client initialization with custom base URL."""
        client = DomeAPIClient(api_key="test_key", base_url="https://custom.api.com")
        assert client.base_url == "https://custom.api.com"
    
    @patch('exchange.dome_api.requests.Session')
    def test_make_request_success(self, mock_session_class, client):
        """Test successful API request."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status.return_value = None
        
        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session
        client.session = mock_session
        
        result = client._make_request('GET', '/test/endpoint')
        
        assert result == {"data": "test"}
        mock_session.request.assert_called_once()
    
    @patch('exchange.dome_api.requests.Session')
    def test_make_request_http_error(self, mock_session_class, client):
        """Test API request with HTTP error."""
        # Setup mock response with error
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        
        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session
        client.session = mock_session
        
        with pytest.raises(DomeAPIError):
            client._make_request('GET', '/test/endpoint')
    
    @patch('exchange.dome_api.requests.Session')
    def test_make_request_connection_error(self, mock_session_class, client):
        """Test API request with connection error."""
        mock_session = MagicMock()
        mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection failed")
        mock_session_class.return_value = mock_session
        client.session = mock_session
        
        with pytest.raises(DomeAPIError) as exc_info:
            client._make_request('GET', '/test/endpoint')
        
        assert "Request failed" in str(exc_info.value)
    
    @patch.object(DomeAPIClient, '_make_request')
    def test_get_kalshi_markets(self, mock_make_request, client):
        """Test get_kalshi_markets method."""
        mock_make_request.return_value = {"markets": []}
        
        result = client.get_kalshi_markets()
        
        mock_make_request.assert_called_once_with('GET', '/kalshi/markets', params={})
        assert result == {"markets": []}
    
    @patch.object(DomeAPIClient, '_make_request')
    def test_get_kalshi_orderbook(self, mock_make_request, client):
        """Test get_kalshi_orderbook method."""
        mock_make_request.return_value = {"bids": [], "asks": []}
        
        result = client.get_kalshi_orderbook("TEST-123")
        
        mock_make_request.assert_called_once_with('GET', '/kalshi/markets/TEST-123/orderbook')
        assert result == {"bids": [], "asks": []}
    
    @patch.object(DomeAPIClient, '_make_request')
    def test_get_polymarket_markets(self, mock_make_request, client):
        """Test get_polymarket_markets method."""
        mock_make_request.return_value = {"markets": []}
        
        result = client.get_polymarket_markets()
        
        mock_make_request.assert_called_once_with('GET', '/polymarket/markets', params={})
        assert result == {"markets": []}
    
    @patch.object(DomeAPIClient, '_make_request')
    def test_get_polymarket_market_price(self, mock_make_request, client):
        """Test get_polymarket_market_price method."""
        mock_make_request.return_value = {"price": 0.65}
        
        result = client.get_polymarket_market_price("token123")
        
        mock_make_request.assert_called_once_with('GET', '/polymarket/market-price/token123', params={})
        assert result == {"price": 0.65}

