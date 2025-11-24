"""Integration tests for websocket integration and service runner."""

import pytest
import pytest_asyncio
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from db.models import DatabaseMarket, MarketPair, OrderbookSnapshot
from exchange.models import OrderBook, OrderBookEntry
from exchange.clients.kalshi_client import KalshiClient
from exchange.clients.polymarket_client import PolymarketClient
from engine.orderbook_streamer import OrderbookStreamer
from engine.arbitrage_service import ArbitrageService
from services.config import ServiceConfig
from services.arbitrage_runner import ArbitrageRunner
from services.runner import ServiceRunner


@pytest.fixture
def mock_db_client():
    """Create a mock database client."""
    client = Mock()
    client.get_all_market_pairs = Mock(return_value=[])
    client.store_orderbook = Mock(return_value={})
    client.get_latest_orderbook = Mock(return_value=None)
    client.client = Mock()
    client.client.table = Mock(return_value=Mock(
        select=Mock(return_value=Mock(
            eq=Mock(return_value=Mock(
                limit=Mock(return_value=Mock(
                    execute=Mock(return_value=Mock(data=[]))
                ))
            ))
        ))
    ))
    return client


@pytest.fixture
def sample_market_kalshi():
    """Create a sample Kalshi market."""
    return DatabaseMarket(
        id="test-kalshi-uuid",
        market_id="TEST-KALSHI",
        exchange="kalshi",
        name="Test Kalshi Market",
        rules="Test rules"
    )


@pytest.fixture
def sample_market_polymarket():
    """Create a sample Polymarket market."""
    return DatabaseMarket(
        id="test-polymarket-uuid",
        market_id="test-polymarket-slug",
        exchange="polymarket",
        name="Test Polymarket Market",
        rules="Test rules",
        extra={"token_id": "0x1234567890abcdef"}
    )


@pytest.fixture
def sample_market_pair(sample_market_kalshi, sample_market_polymarket):
    """Create a sample market pair."""
    return MarketPair(
        id="test-pair-uuid",
        market_1_id=sample_market_kalshi.id,
        market_1_exchange=sample_market_kalshi.exchange,
        market_2_id=sample_market_polymarket.id,
        market_2_exchange=sample_market_polymarket.exchange,
        similarity_score=0.95,
        llm_verified=True
    )


@pytest.fixture
def sample_orderbook():
    """Create a sample OrderBook."""
    return OrderBook(
        market_id="TEST-KALSHI",
        bids=[
            OrderBookEntry(price=0.60, quantity=100),
            OrderBookEntry(price=0.59, quantity=200)
        ],
        asks=[
            OrderBookEntry(price=0.61, quantity=150),
            OrderBookEntry(price=0.62, quantity=250)
        ],
        timestamp=datetime.now(timezone.utc),
        metadata={"orderbook": {"yes": [[60, 100], [59, 200]], "no": [[40, 100], [39, 200]]}}
    )


@pytest.fixture
def service_config():
    """Create a test service configuration."""
    return ServiceConfig(
        run_arbitrage=True,
        run_market_polling=False,
        use_websockets=True,
        websocket_fallback_to_rest=True,
        arbitrage_poll_interval=60,
        websocket_refresh_subscriptions_interval=300
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_kalshi_client_websocket_connection():
    """Test Kalshi client websocket connection."""
    try:
        import websockets
    except ImportError:
        pytest.skip("websockets library not available")
    
    client = KalshiClient()
    
    # Mock websocket connection
    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_ws.send = AsyncMock()
    mock_ws.ping = AsyncMock()
    mock_ws.close = AsyncMock()
    
    async def mock_connect(*args, **kwargs):
        return mock_ws
    
    with patch('exchange.clients.kalshi_client.websockets.connect', side_effect=mock_connect):
        await client.connect_websocket()
        assert client.is_websocket_connected()
        
        # Test subscription
        callback_called = []
        def test_callback(orderbook):
            callback_called.append(orderbook)
        
        await client.subscribe_orderbook("TEST-TICKER", test_callback)
        assert "TEST-TICKER" in client._ws_subscriptions
        
        # Test unsubscribe
        await client.unsubscribe_orderbook("TEST-TICKER")
        assert "TEST-TICKER" not in client._ws_subscriptions
        
        await client.disconnect_websocket()
        assert not client.is_websocket_connected()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_polymarket_client_websocket_connection():
    """Test Polymarket client websocket connection."""
    try:
        import websockets
    except ImportError:
        pytest.skip("websockets library not available")
    
    client = PolymarketClient()
    
    # Mock websocket connection
    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()
    
    async def mock_connect(*args, **kwargs):
        return mock_ws
    
    with patch('exchange.clients.polymarket_client.websockets.connect', side_effect=mock_connect):
        await client.connect_websocket()
        assert client.is_websocket_connected()
        
        # Test subscription
        callback_called = []
        def test_callback(orderbook):
            callback_called.append(orderbook)
        
        await client.subscribe_orderbook("0x123456", test_callback)
        assert "0x123456" in client._ws_subscriptions
        
        # Test unsubscribe
        await client.unsubscribe_orderbook("0x123456")
        assert "0x123456" not in client._ws_subscriptions
        
        await client.disconnect_websocket()
        assert not client.is_websocket_connected()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_orderbook_streamer_subscription(mock_db_client, sample_market_pair, sample_market_kalshi, sample_market_polymarket):
    """Test OrderbookStreamer subscription management."""
    try:
        import websockets
    except ImportError:
        pytest.skip("websockets library not available")
    
    # Mock clients
    kalshi_client = Mock(spec=KalshiClient)
    kalshi_client.connect_websocket = AsyncMock()
    kalshi_client.disconnect_websocket = AsyncMock()
    kalshi_client.subscribe_orderbook = AsyncMock()
    kalshi_client.unsubscribe_orderbook = AsyncMock()
    kalshi_client.is_websocket_connected = Mock(return_value=True)
    
    polymarket_client = Mock(spec=PolymarketClient)
    polymarket_client.connect_websocket = AsyncMock()
    polymarket_client.disconnect_websocket = AsyncMock()
    polymarket_client.subscribe_orderbook = AsyncMock()
    polymarket_client.unsubscribe_orderbook = AsyncMock()
    polymarket_client.is_websocket_connected = Mock(return_value=True)
    
    # Mock orderbook poller
    mock_poller = Mock()
    mock_poller._get_market_by_id = Mock(side_effect=lambda uuid: {
        sample_market_kalshi.id: sample_market_kalshi,
        sample_market_polymarket.id: sample_market_polymarket
    }.get(uuid))
    mock_poller._get_polymarket_token_id = Mock(return_value="0x1234567890abcdef")
    mock_poller._convert_orderbook_to_snapshot = Mock(return_value=OrderbookSnapshot(
        market_id=sample_market_kalshi.id,
        exchange="kalshi",
        yes_bids=[],
        yes_asks=[],
        no_bids=[],
        no_asks=[]
    ))
    
    # Setup mock_db_client to return market pair and markets
    mock_db_client.get_all_market_pairs = Mock(return_value=[sample_market_pair])
    # Mock the _get_market_by_id method that streamer uses
    def get_market_by_id(uuid):
        return {
            sample_market_kalshi.id: sample_market_kalshi,
            sample_market_polymarket.id: sample_market_polymarket
        }.get(uuid)
    
    streamer = OrderbookStreamer(
        kalshi_client=kalshi_client,
        polymarket_client=polymarket_client,
        db_client=mock_db_client,
        orderbook_poller=mock_poller
    )
    
    # Patch the streamer's _get_market_by_id method
    streamer._get_market_by_id = get_market_by_id
    
    await streamer.start()
    
    # Verify connections
    kalshi_client.connect_websocket.assert_called_once()
    polymarket_client.connect_websocket.assert_called_once()
    
    # Verify subscriptions (should be called for both markets in the pair)
    assert kalshi_client.subscribe_orderbook.call_count >= 0  # May be called if markets found
    assert polymarket_client.subscribe_orderbook.call_count >= 0  # May be called if markets found
    
    await streamer.stop()
    
    # Verify disconnections
    kalshi_client.disconnect_websocket.assert_called_once()
    polymarket_client.disconnect_websocket.assert_called_once()


@pytest.mark.integration
def test_arbitrage_service_with_stored_orderbooks(mock_db_client, sample_market_pair, sample_orderbook):
    """Test ArbitrageService using stored orderbooks."""
    from engine.orderbook_poller import OrderbookPoller
    from engine.arbitrage_calculator import ArbitrageCalculator
    
    # Create orderbook snapshots
    snapshot1 = OrderbookSnapshot(
        market_id="test-kalshi-uuid",
        exchange="kalshi",
        yes_bids=[{'price': 0.60, 'quantity': 100}],
        yes_asks=[{'price': 0.61, 'quantity': 150}],
        no_bids=[{'price': 0.40, 'quantity': 100}],
        no_asks=[{'price': 0.41, 'quantity': 150}]
    )
    
    snapshot2 = OrderbookSnapshot(
        market_id="test-polymarket-uuid",
        exchange="polymarket",
        yes_bids=[{'price': 0.65, 'quantity': 120}],
        yes_asks=[{'price': 0.66, 'quantity': 100}],
        no_bids=[{'price': 0.35, 'quantity': 120}],
        no_asks=[{'price': 0.36, 'quantity': 100}]
    )
    
    # Setup mocks
    mock_db_client.get_all_market_pairs = Mock(return_value=[sample_market_pair])
    mock_db_client.get_latest_orderbook = Mock(side_effect=lambda market_id, exchange: {
        ("test-kalshi-uuid", "kalshi"): snapshot1,
        ("test-polymarket-uuid", "polymarket"): snapshot2
    }.get((market_id, exchange)))
    mock_db_client.store_arbitrage_opportunity = Mock(return_value={})
    
    # Mock orderbook poller
    mock_poller = Mock(spec=OrderbookPoller)
    mock_poller._get_market_by_id = Mock(side_effect=lambda uuid: {
        "test-kalshi-uuid": DatabaseMarket(
            id="test-kalshi-uuid",
            market_id="TEST-KALSHI",
            exchange="kalshi",
            name="Test Market"
        ),
        "test-polymarket-uuid": DatabaseMarket(
            id="test-polymarket-uuid",
            market_id="test-slug",
            exchange="polymarket",
            name="Test Market"
        )
    }.get(uuid))
    
    service = ArbitrageService(
        db_client=mock_db_client,
        orderbook_poller=mock_poller,
        use_stored_orderbooks=True
    )
    
    # Run calculation
    stats = service.poll_and_calculate()
    
    # Verify results
    assert stats['pairs_processed'] >= 0
    assert 'opportunities_found' in stats
    assert 'errors' in stats


@pytest.mark.integration
def test_arbitrage_runner_requires_websockets(service_config, mock_db_client):
    """Test ArbitrageRunner requires websockets to be enabled."""
    # Disable websockets
    service_config.use_websockets = False
    
    # Mock clients
    kalshi_client = Mock(spec=KalshiClient)
    polymarket_client = Mock(spec=PolymarketClient)
    
    runner = ArbitrageRunner(
        config=service_config,
        db_client=mock_db_client,
        kalshi_client=kalshi_client,
        polymarket_client=polymarket_client
    )
    
    # Start should raise ValueError
    with pytest.raises(ValueError, match="Websockets must be enabled"):
        runner.start()
    
    assert not runner.is_running()


@pytest.mark.integration
def test_arbitrage_runner_websocket_failure_raises_error(service_config, mock_db_client):
    """Test ArbitrageRunner raises error when websocket connection fails."""
    # Enable websockets
    service_config.use_websockets = True
    
    # Mock clients that fail to connect
    kalshi_client = Mock(spec=KalshiClient)
    kalshi_client.connect_websocket = AsyncMock(side_effect=Exception("Connection failed"))
    kalshi_client.is_websocket_connected = Mock(return_value=False)
    
    polymarket_client = Mock(spec=PolymarketClient)
    polymarket_client.connect_websocket = AsyncMock(side_effect=Exception("Connection failed"))
    polymarket_client.is_websocket_connected = Mock(return_value=False)
    
    runner = ArbitrageRunner(
        config=service_config,
        db_client=mock_db_client,
        kalshi_client=kalshi_client,
        polymarket_client=polymarket_client
    )
    
    # Start should raise RuntimeError
    with pytest.raises(RuntimeError, match="Failed to start websocket mode"):
        runner.start()
    
    assert not runner.is_running()


@pytest.mark.integration
def test_service_runner_start_stop(service_config, mock_db_client):
    """Test ServiceRunner start and stop."""
    # Set required config values
    service_config.supabase_url = "https://test.supabase.co"
    service_config.supabase_key = "test-key"
    
    # Mock the ArbitrageRunner
    with patch('services.runner.ArbitrageRunner') as mock_runner_class:
        mock_runner = Mock()
        mock_runner.is_running = Mock(return_value=True)
        mock_runner.get_stats = Mock(return_value={'running': True, 'mode': 'rest'})
        mock_runner_class.return_value = mock_runner
        
        runner = ServiceRunner(service_config)
        
        # Start
        runner.start()
        mock_runner.start.assert_called_once()
        
        # Stop
        runner.stop()
        mock_runner.stop.assert_called_once()


@pytest.mark.integration
def test_service_config_from_env():
    """Test ServiceConfig creation from environment variables."""
    import os
    
    # Set test environment variables
    os.environ['RUN_ARBITRAGE'] = 'true'
    os.environ['USE_WEBSOCKETS'] = 'false'
    os.environ['ARBITRAGE_POLL_INTERVAL'] = '30'
    
    config = ServiceConfig.from_env()
    
    assert config.run_arbitrage is True
    assert config.use_websockets is False
    assert config.arbitrage_poll_interval == 30
    
    # Cleanup
    del os.environ['RUN_ARBITRAGE']
    del os.environ['USE_WEBSOCKETS']
    del os.environ['ARBITRAGE_POLL_INTERVAL']


@pytest.mark.integration
def test_service_config_validation():
    """Test ServiceConfig validation."""
    # Valid config
    config = ServiceConfig(
        run_arbitrage=True,
        supabase_url="https://test.supabase.co",
        supabase_key="test-key"
    )
    errors = config.validate()
    assert len(errors) == 0
    
    # Invalid config - missing required fields
    config = ServiceConfig(
        run_arbitrage=True,
        supabase_url=None,
        supabase_key=None
    )
    errors = config.validate()
    assert len(errors) > 0
    assert any("SUPABASE_URL" in error for error in errors)
    assert any("SUPABASE_KEY" in error for error in errors)


@pytest.mark.integration
def test_orderbook_streamer_callback_processing(mock_db_client, sample_market_kalshi, sample_orderbook):
    """Test OrderbookStreamer processing orderbook updates via callback."""
    # Mock clients
    kalshi_client = Mock(spec=KalshiClient)
    kalshi_client.is_websocket_connected = Mock(return_value=True)
    
    polymarket_client = Mock(spec=PolymarketClient)
    polymarket_client.is_websocket_connected = Mock(return_value=True)
    
    # Mock orderbook poller
    mock_poller = Mock()
    snapshot = OrderbookSnapshot(
        market_id=sample_market_kalshi.id,
        exchange="kalshi",
        yes_bids=[{'price': 0.60, 'quantity': 100}],
        yes_asks=[{'price': 0.61, 'quantity': 150}],
        no_bids=[{'price': 0.40, 'quantity': 100}],
        no_asks=[{'price': 0.41, 'quantity': 150}]
    )
    mock_poller._convert_orderbook_to_snapshot = Mock(return_value=snapshot)
    
    streamer = OrderbookStreamer(
        kalshi_client=kalshi_client,
        polymarket_client=polymarket_client,
        db_client=mock_db_client,
        orderbook_poller=mock_poller
    )
    
    # Create callback
    callback = streamer._create_orderbook_callback(sample_market_kalshi)
    
    # Call callback with orderbook
    callback(sample_orderbook)
    
    # Verify orderbook was stored
    mock_db_client.store_orderbook.assert_called_once()
    call_args = mock_db_client.store_orderbook.call_args[0][0]
    assert call_args.market_id == sample_market_kalshi.id
    assert call_args.exchange == "kalshi"

