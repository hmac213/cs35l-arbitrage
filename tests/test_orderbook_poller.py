"""Unit tests for orderbook poller."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from exchange.models import OrderBook, OrderBookEntry
from db.models import DatabaseMarket, OrderbookSnapshot
from engine.orderbook_poller import OrderbookPoller


@pytest.fixture
def db_client_mock():
    """Create a mock database client."""
    client = Mock()
    client.client = Mock()
    return client


@pytest.fixture
def kalshi_client_mock():
    """Create a mock Kalshi client."""
    return Mock()


@pytest.fixture
def polymarket_client_mock():
    """Create a mock Polymarket client."""
    return Mock()


@pytest.fixture
def poller(db_client_mock, kalshi_client_mock, polymarket_client_mock):
    """Create an OrderbookPoller instance with mocked clients."""
    return OrderbookPoller(
        kalshi_client=kalshi_client_mock,
        polymarket_client=polymarket_client_mock,
        db_client=db_client_mock
    )


@pytest.fixture
def sample_kalshi_market():
    """Create a sample Kalshi market."""
    return DatabaseMarket(
        id="test-kalshi-uuid",
        market_id="KXTEST-123",
        exchange="kalshi",
        name="Test Market",
        status="active"
    )


@pytest.fixture
def sample_polymarket_market():
    """Create a sample Polymarket market."""
    return DatabaseMarket(
        id="test-polymarket-uuid",
        market_id="test-market-id",
        exchange="polymarket",
        name="Test Market",
        status="active"
    )


@pytest.fixture
def kalshi_orderbook():
    """Create a sample Kalshi orderbook with yes/no structure in metadata."""
    return OrderBook(
        market_id="KXTEST-123",
        bids=[
            OrderBookEntry(price=0.60, quantity=100),
            OrderBookEntry(price=0.59, quantity=200)
        ],
        asks=[
            OrderBookEntry(price=0.61, quantity=150),
            OrderBookEntry(price=0.62, quantity=250)
        ],
        timestamp=datetime.now(timezone.utc),
        metadata={
            'yes': {
                'bids': [{'price': 0.60, 'quantity': 100}, {'price': 0.59, 'quantity': 200}],
                'asks': [{'price': 0.61, 'quantity': 150}, {'price': 0.62, 'quantity': 250}]
            },
            'no': {
                'bids': [{'price': 0.40, 'quantity': 100}, {'price': 0.39, 'quantity': 200}],
                'asks': [{'price': 0.41, 'quantity': 150}, {'price': 0.42, 'quantity': 250}]
            }
        }
    )


@pytest.fixture
def polymarket_orderbook():
    """Create a sample Polymarket orderbook."""
    return OrderBook(
        market_id="test-market-id",
        bids=[
            OrderBookEntry(price=0.65, quantity=120),
            OrderBookEntry(price=0.64, quantity=180)
        ],
        asks=[
            OrderBookEntry(price=0.66, quantity=100),
            OrderBookEntry(price=0.67, quantity=200)
        ],
        timestamp=datetime.now(timezone.utc),
        metadata={}
    )


def test_convert_kalshi_orderbook(poller, sample_kalshi_market, kalshi_orderbook):
    """Test conversion of Kalshi orderbook to snapshot."""
    snapshot = poller._convert_kalshi_orderbook(kalshi_orderbook, sample_kalshi_market)
    
    assert snapshot.market_id == sample_kalshi_market.id
    assert snapshot.exchange == "kalshi"
    assert len(snapshot.yes_bids) == 2
    assert len(snapshot.yes_asks) == 2
    assert len(snapshot.no_bids) == 2
    assert len(snapshot.no_asks) == 2
    
    # Check sorting: bids descending, asks ascending
    assert snapshot.yes_bids[0]['price'] >= snapshot.yes_bids[1]['price']
    assert snapshot.yes_asks[0]['price'] <= snapshot.yes_asks[1]['price']


def test_convert_polymarket_orderbook(poller, sample_polymarket_market, polymarket_orderbook):
    """Test conversion of Polymarket orderbook to snapshot."""
    snapshot = poller._convert_polymarket_orderbook(polymarket_orderbook, sample_polymarket_market)
    
    assert snapshot.market_id == sample_polymarket_market.id
    assert snapshot.exchange == "polymarket"
    assert len(snapshot.yes_bids) == 2
    assert len(snapshot.yes_asks) == 2
    assert len(snapshot.no_bids) == 2
    assert len(snapshot.no_asks) == 2
    
    # Check that no side is inverted
    assert snapshot.no_bids[0]['price'] == pytest.approx(1.0 - polymarket_orderbook.asks[0].price)
    assert snapshot.no_asks[0]['price'] == pytest.approx(1.0 - polymarket_orderbook.bids[0].price)


def test_poll_single_market_kalshi(poller, sample_kalshi_market, kalshi_orderbook, kalshi_client_mock):
    """Test polling a single Kalshi market."""
    kalshi_client_mock.fetch_orderbook.return_value = kalshi_orderbook
    
    snapshot = poller._poll_single_market(sample_kalshi_market)
    
    assert snapshot is not None
    assert snapshot.exchange == "kalshi"
    kalshi_client_mock.fetch_orderbook.assert_called_once_with(sample_kalshi_market.market_id)


def test_poll_single_market_polymarket(poller, sample_polymarket_market, polymarket_orderbook, polymarket_client_mock):
    """Test polling a single Polymarket market."""
    polymarket_client_mock.fetch_orderbook.return_value = polymarket_orderbook
    
    snapshot = poller._poll_single_market(sample_polymarket_market)
    
    assert snapshot is not None
    assert snapshot.exchange == "polymarket"
    polymarket_client_mock.fetch_orderbook.assert_called_once_with(sample_polymarket_market.market_id)


def test_poll_single_market_error(poller, sample_kalshi_market, kalshi_client_mock):
    """Test error handling when polling fails."""
    kalshi_client_mock.fetch_orderbook.side_effect = Exception("API Error")
    
    snapshot = poller._poll_single_market(sample_kalshi_market)
    
    assert snapshot is None


def test_poll_market_pair(poller, sample_kalshi_market, sample_polymarket_market, kalshi_orderbook, polymarket_orderbook, kalshi_client_mock, polymarket_client_mock, db_client_mock):
    """Test polling orderbooks for a market pair."""
    from db.models import MarketPair
    
    # Setup mocks
    kalshi_client_mock.fetch_orderbook.return_value = kalshi_orderbook
    polymarket_client_mock.fetch_orderbook.return_value = polymarket_orderbook
    
    # Mock database responses - need to return different markets for different UUIDs
    def create_mock_response(market_data):
        mock_response = Mock()
        mock_response.data = [market_data] if market_data else []
        return mock_response
    
    # Setup the mock chain to return appropriate market based on UUID
    def eq_mock(field, value):
        mock_eq = Mock()
        mock_limit = Mock()
        
        # Return appropriate market based on UUID
        if value == sample_kalshi_market.id:
            market_data = {'id': sample_kalshi_market.id, 'market_id': sample_kalshi_market.market_id, 'exchange': 'kalshi', 'name': 'Test', 'status': 'active'}
        elif value == sample_polymarket_market.id:
            market_data = {'id': sample_polymarket_market.id, 'market_id': sample_polymarket_market.market_id, 'exchange': 'polymarket', 'name': 'Test', 'status': 'active'}
        else:
            market_data = None
        
        mock_limit.execute.return_value = create_mock_response(market_data)
        mock_eq.limit.return_value = mock_limit
        return mock_eq
    
    mock_select = Mock()
    mock_select.eq = eq_mock
    mock_table = Mock()
    mock_table.select.return_value = mock_select
    db_client_mock.client.table.return_value = mock_table
    
    market_pair = MarketPair(
        market_1_id=sample_kalshi_market.id,
        market_1_exchange="kalshi",
        market_2_id=sample_polymarket_market.id,
        market_2_exchange="polymarket",
        similarity_score=0.9
    )
    
    orderbook1, orderbook2 = poller.poll_market_pair(market_pair)
    
    assert orderbook1 is not None
    assert orderbook2 is not None
    assert orderbook1.exchange == "kalshi"
    assert orderbook2.exchange == "polymarket"

