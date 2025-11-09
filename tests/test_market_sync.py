"""Tests for market sync service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from exchange.models import Market, MarketMetadata
from db.models import DatabaseMarket
from db.client import SupabaseClient
from engine.market_sync import MarketSyncService
from engine.errors import SyncError


@pytest.fixture
def mock_db_client():
    """Create a mock Supabase client."""
    client = Mock(spec=SupabaseClient)
    client.get_markets_by_exchange.return_value = []
    client.upsert_markets.return_value = []
    return client


@pytest.fixture
def mock_poller():
    """Create a mock market poller."""
    poller = Mock()
    poller.poll_all.return_value = {
        'kalshi': [],
        'polymarket': []
    }
    return poller


@pytest.fixture
def sample_market():
    """Create a sample market."""
    return Market(
        market_id='TEST-123',
        name='Test Market',
        rules='Test Rules',
        metadata=MarketMetadata(
            resolve_date='2025-12-31',
            resolve_time='23:59:59',
            category='Test'
        ),
        exchange='kalshi'
    )


def test_sync_markets_new_market(mock_db_client, sample_market):
    """Test syncing a new market."""
    # Setup mocks
    poller = Mock()
    poller.poll_all.return_value = {
        'kalshi': [sample_market],
        'polymarket': []
    }
    
    # Mock garbage collector
    with patch('engine.market_sync.GarbageCollector') as mock_gc_class:
        mock_gc = Mock()
        mock_gc.filter_expired.return_value = ([sample_market], [])
        mock_gc.cleanup_database.return_value = 0
        mock_gc_class.return_value = mock_gc
        
        # Mock poller
        with patch('engine.market_sync.MarketPoller') as mock_poller_class:
            mock_poller_class.return_value = poller
            
            service = MarketSyncService(mock_db_client)
            stats = service.sync_markets()
            
            assert stats['kalshi_added'] == 1
            assert stats['kalshi_updated'] == 0
            assert stats['kalshi_skipped'] == 0
            mock_db_client.upsert_markets.assert_called_once()


def test_sync_markets_unchanged_market(mock_db_client, sample_market):
    """Test syncing an unchanged market (should skip write)."""
    # Create existing market in DB
    existing_market = DatabaseMarket.from_exchange_market(sample_market)
    existing_market.status = 'active'
    existing_market.last_polled_at = datetime.now(timezone.utc)
    
    mock_db_client.get_markets_by_exchange.return_value = [existing_market]
    
    # Setup mocks
    poller = Mock()
    poller.poll_all.return_value = {
        'kalshi': [sample_market],
        'polymarket': []
    }
    
    # Mock garbage collector
    with patch('engine.market_sync.GarbageCollector') as mock_gc_class:
        mock_gc = Mock()
        mock_gc.filter_expired.return_value = ([sample_market], [])
        mock_gc.cleanup_database.return_value = 0
        mock_gc_class.return_value = mock_gc
        
        # Mock poller
        with patch('engine.market_sync.MarketPoller') as mock_poller_class:
            mock_poller_class.return_value = poller
            
            service = MarketSyncService(mock_db_client)
            stats = service.sync_markets()
            
            assert stats['kalshi_added'] == 0
            assert stats['kalshi_updated'] == 0
            assert stats['kalshi_skipped'] == 1
            # Should not call upsert_markets if nothing changed
            mock_db_client.upsert_markets.assert_not_called()


def test_sync_markets_changed_market(mock_db_client, sample_market):
    """Test syncing a changed market (should update)."""
    # Create existing market with different name
    existing_market = DatabaseMarket.from_exchange_market(sample_market)
    existing_market.name = 'Old Name'  # Different name
    existing_market.status = 'active'
    
    mock_db_client.get_markets_by_exchange.return_value = [existing_market]
    
    # Setup mocks
    poller = Mock()
    poller.poll_all.return_value = {
        'kalshi': [sample_market],
        'polymarket': []
    }
    
    # Mock garbage collector
    with patch('engine.market_sync.GarbageCollector') as mock_gc_class:
        mock_gc = Mock()
        mock_gc.filter_expired.return_value = ([sample_market], [])
        mock_gc.cleanup_database.return_value = 0
        mock_gc_class.return_value = mock_gc
        
        # Mock poller
        with patch('engine.market_sync.MarketPoller') as mock_poller_class:
            mock_poller_class.return_value = poller
            
            service = MarketSyncService(mock_db_client)
            stats = service.sync_markets()
            
            assert stats['kalshi_added'] == 0
            assert stats['kalshi_updated'] == 1
            assert stats['kalshi_skipped'] == 0
            mock_db_client.upsert_markets.assert_called_once()


def test_sync_markets_filters_expired(mock_db_client, sample_market):
    """Test that expired markets are filtered out."""
    from datetime import timedelta
    
    # Create expired market
    past_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    expired_market = Market(
        market_id='EXPIRED-123',
        name='Expired',
        rules='',
        metadata=MarketMetadata(resolve_date=past_date),
        exchange='kalshi'
    )
    
    # Setup mocks
    poller = Mock()
    poller.poll_all.return_value = {
        'kalshi': [expired_market],
        'polymarket': []
    }
    
    # Mock garbage collector to filter expired
    with patch('engine.market_sync.GarbageCollector') as mock_gc_class:
        mock_gc = Mock()
        mock_gc.filter_expired.return_value = ([], [expired_market])  # All expired
        mock_gc.cleanup_database.return_value = 0
        mock_gc_class.return_value = mock_gc
        
        # Mock poller
        with patch('engine.market_sync.MarketPoller') as mock_poller_class:
            mock_poller_class.return_value = poller
            
            service = MarketSyncService(mock_db_client)
            stats = service.sync_markets()
            
            # Should not add expired markets
            assert stats['kalshi_added'] == 0
            mock_db_client.upsert_markets.assert_not_called()

