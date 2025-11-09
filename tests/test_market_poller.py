"""Tests for market poller component."""

import pytest
from unittest.mock import Mock, patch
from exchange.models import Market, MarketMetadata
from engine.market_poller import MarketPoller
from engine.errors import PollingError, MarketValidationError


@pytest.fixture
def mock_kalshi_client():
    """Create a mock Kalshi client."""
    client = Mock()
    client.exchange_name = 'kalshi'
    return client


@pytest.fixture
def mock_polymarket_client():
    """Create a mock Polymarket client."""
    client = Mock()
    client.exchange_name = 'polymarket'
    return client


@pytest.fixture
def sample_market():
    """Create a sample market for testing."""
    return Market(
        market_id='TEST-123',
        name='Test Market',
        rules='Test Rules',
        metadata=MarketMetadata(
            resolve_date='2025-12-31',
            resolve_time='23:59:59',
            category='Test',
            volume=1000.0
        ),
        exchange='kalshi'
    )


def test_poll_exchange_success(mock_kalshi_client, sample_market):
    """Test successful polling from an exchange."""
    mock_kalshi_client.fetch_all_markets.return_value = [sample_market]
    
    poller = MarketPoller(kalshi_client=mock_kalshi_client)
    markets = poller.poll_exchange(mock_kalshi_client)
    
    assert len(markets) == 1
    assert markets[0].market_id == 'TEST-123'
    mock_kalshi_client.fetch_all_markets.assert_called_once()


def test_poll_exchange_filters_invalid(mock_kalshi_client):
    """Test that invalid markets are filtered out."""
    invalid_market = Market(
        market_id='',  # Invalid: empty market_id
        name='Test',
        rules='',
        metadata=MarketMetadata(),
        exchange='kalshi'
    )
    valid_market = Market(
        market_id='VALID-123',
        name='Valid Market',
        rules='Rules',
        metadata=MarketMetadata(),
        exchange='kalshi'
    )
    
    mock_kalshi_client.fetch_all_markets.return_value = [invalid_market, valid_market]
    
    poller = MarketPoller(kalshi_client=mock_kalshi_client)
    markets = poller.poll_exchange(mock_kalshi_client)
    
    assert len(markets) == 1
    assert markets[0].market_id == 'VALID-123'


def test_poll_exchange_handles_errors(mock_kalshi_client):
    """Test error handling during polling."""
    mock_kalshi_client.fetch_all_markets.side_effect = Exception("API Error")
    
    poller = MarketPoller(kalshi_client=mock_kalshi_client)
    
    with pytest.raises(PollingError):
        poller.poll_exchange(mock_kalshi_client)


def test_poll_all(mock_kalshi_client, mock_polymarket_client, sample_market):
    """Test polling from both exchanges."""
    mock_kalshi_client.fetch_all_markets.return_value = [sample_market]
    
    polymarket_market = Market(
        market_id='POLY-123',
        name='Polymarket Market',
        rules='Rules',
        metadata=MarketMetadata(),
        exchange='polymarket'
    )
    mock_polymarket_client.fetch_all_markets.return_value = [polymarket_market]
    
    poller = MarketPoller(
        kalshi_client=mock_kalshi_client,
        polymarket_client=mock_polymarket_client
    )
    results = poller.poll_all()
    
    assert 'kalshi' in results
    assert 'polymarket' in results
    assert len(results['kalshi']) == 1
    assert len(results['polymarket']) == 1


def test_poll_all_continues_on_error(mock_kalshi_client, mock_polymarket_client):
    """Test that polling continues even if one exchange fails."""
    mock_kalshi_client.fetch_all_markets.side_effect = Exception("Kalshi Error")
    mock_polymarket_client.fetch_all_markets.return_value = []
    
    poller = MarketPoller(
        kalshi_client=mock_kalshi_client,
        polymarket_client=mock_polymarket_client
    )
    results = poller.poll_all()
    
    # Should still return results, even if Kalshi failed
    assert 'kalshi' in results
    assert 'polymarket' in results
    assert len(results['kalshi']) == 0

