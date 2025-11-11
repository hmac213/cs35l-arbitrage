"""Tests for garbage collector component."""

import pytest
from datetime import datetime, timedelta, timezone
from exchange.models import Market, MarketMetadata
from db.models import DatabaseMarket
from engine.garbage_collector import GarbageCollector


@pytest.fixture
def garbage_collector():
    """Create a garbage collector instance."""
    return GarbageCollector(expiration_buffer_hours=1)


def test_filter_expired_active_market(garbage_collector):
    """Test filtering with an active (non-expired) market."""
    future_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y-%m-%d')
    future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime('%H:%M:%S')
    
    market = Market(
        market_id='ACTIVE-123',
        name='Active Market',
        rules='Rules',
        metadata=MarketMetadata(
            resolve_date=future_date,
            resolve_time=future_time
        ),
        exchange='kalshi'
    )
    
    active, expired = garbage_collector.filter_expired([market])
    
    assert len(active) == 1
    assert len(expired) == 0
    assert active[0].market_id == 'ACTIVE-123'


def test_filter_expired_expired_market(garbage_collector):
    """Test filtering with an expired market."""
    past_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime('%H:%M:%S')
    
    market = Market(
        market_id='EXPIRED-123',
        name='Expired Market',
        rules='Rules',
        metadata=MarketMetadata(
            resolve_date=past_date,
            resolve_time=past_time
        ),
        exchange='kalshi'
    )
    
    active, expired = garbage_collector.filter_expired([market])
    
    assert len(active) == 0
    assert len(expired) == 1
    assert expired[0].market_id == 'EXPIRED-123'


def test_filter_expired_mixed(garbage_collector):
    """Test filtering with both active and expired markets."""
    future_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y-%m-%d')
    past_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    active_market = Market(
        market_id='ACTIVE-123',
        name='Active',
        rules='',
        metadata=MarketMetadata(resolve_date=future_date),
        exchange='kalshi'
    )
    
    expired_market = Market(
        market_id='EXPIRED-123',
        name='Expired',
        rules='',
        metadata=MarketMetadata(resolve_date=past_date),
        exchange='kalshi'
    )
    
    active, expired = garbage_collector.filter_expired([active_market, expired_market])
    
    assert len(active) == 1
    assert len(expired) == 1
    assert active[0].market_id == 'ACTIVE-123'
    assert expired[0].market_id == 'EXPIRED-123'


def test_is_expired_no_resolve_date(garbage_collector):
    """Test that markets without resolve_date are not expired."""
    market = Market(
        market_id='NO-DATE-123',
        name='No Date',
        rules='',
        metadata=MarketMetadata(resolve_date=None),
        exchange='kalshi'
    )
    
    assert not garbage_collector._is_expired(market)


def test_database_market_is_expired():
    """Test DatabaseMarket.is_expired() method."""
    from datetime import date, time
    
    # Expired market
    expired_market = DatabaseMarket(
        market_id='EXPIRED-123',
        exchange='kalshi',
        name='Expired',
        resolve_date=date(2020, 1, 1),
        resolve_time=time(12, 0, 0)
    )
    assert expired_market.is_expired()
    
    # Active market
    future_date = date.today() + timedelta(days=1)
    active_market = DatabaseMarket(
        market_id='ACTIVE-123',
        exchange='kalshi',
        name='Active',
        resolve_date=future_date,
        resolve_time=time(12, 0, 0)
    )
    assert not active_market.is_expired()


def test_filter_bad_markets_multigame_extended(garbage_collector):
    """Test filtering of Kalshi multigame extended markets."""
    valid_market = Market(
        market_id='VALID-123',
        name='Valid Market',
        rules='Rules',
        metadata=MarketMetadata(),
        exchange='kalshi'
    )
    
    multigame_market = Market(
        market_id='KXMVESPORTSMULTIGAMEEXTENDED-S20255830C16DF69-6D10C5071D8',
        name='Multigame Market',
        rules='',
        metadata=MarketMetadata(),
        exchange='kalshi'
    )
    
    valid, bad = garbage_collector.filter_bad_markets([valid_market, multigame_market])
    
    assert len(valid) == 1
    assert len(bad) == 1
    assert valid[0].market_id == 'VALID-123'
    assert bad[0].market_id == 'KXMVESPORTSMULTIGAMEEXTENDED-S20255830C16DF69-6D10C5071D8'


def test_filter_bad_markets_placeholder_name(garbage_collector):
    """Test filtering of markets with PLACEHOLDER in name."""
    valid_market = Market(
        market_id='VALID-123',
        name='Valid Market Name',
        rules='Rules',
        metadata=MarketMetadata(),
        exchange='polymarket'
    )
    
    placeholder_market = Market(
        market_id='PLACEHOLDER-123',
        name='Will PLACEHOLDER X win',
        rules='Rules',
        metadata=MarketMetadata(),
        exchange='polymarket'
    )
    
    # Test market should NOT be filtered (user said nuclear test markets are fine)
    test_market = Market(
        market_id='TEST-123',
        name='Nuclear TEST Market',
        rules='Rules',
        metadata=MarketMetadata(),
        exchange='polymarket'
    )
    
    valid, bad = garbage_collector.filter_bad_markets([valid_market, placeholder_market, test_market])
    
    assert len(valid) == 2  # valid_market and test_market should pass
    assert len(bad) == 1
    assert valid[0].market_id == 'VALID-123'
    assert valid[1].market_id == 'TEST-123'
    assert bad[0].market_id == 'PLACEHOLDER-123'


def test_filter_bad_markets_short_name(garbage_collector):
    """Test filtering of markets with very short names."""
    valid_market = Market(
        market_id='VALID-123',
        name='Valid Market Name',
        rules='Rules',
        metadata=MarketMetadata(),
        exchange='polymarket'
    )
    
    short_name_market = Market(
        market_id='SHORT-123',
        name='Hi',
        rules='Rules',
        metadata=MarketMetadata(),
        exchange='polymarket'
    )
    
    valid, bad = garbage_collector.filter_bad_markets([valid_market, short_name_market])
    
    assert len(valid) == 1
    assert len(bad) == 1
    assert valid[0].market_id == 'VALID-123'
    assert bad[0].market_id == 'SHORT-123'


def test_filter_bad_markets_empty_rules(garbage_collector):
    """Test filtering of markets with empty or null rules."""
    valid_market = Market(
        market_id='VALID-123',
        name='Valid Market Name',
        rules='These are the rules',
        metadata=MarketMetadata(),
        exchange='kalshi'
    )
    
    empty_rules_market = Market(
        market_id='EMPTY-RULES-123',
        name='Market with Empty Rules',
        rules='',
        metadata=MarketMetadata(),
        exchange='kalshi'
    )
    
    null_rules_market = Market(
        market_id='NULL-RULES-123',
        name='Market with Null Rules',
        rules=None,
        metadata=MarketMetadata(),
        exchange='polymarket'
    )
    
    whitespace_rules_market = Market(
        market_id='WHITESPACE-RULES-123',
        name='Market with Whitespace Rules',
        rules='   ',
        metadata=MarketMetadata(),
        exchange='polymarket'
    )
    
    valid, bad = garbage_collector.filter_bad_markets([
        valid_market,
        empty_rules_market,
        null_rules_market,
        whitespace_rules_market
    ])
    
    assert len(valid) == 1
    assert len(bad) == 3
    assert valid[0].market_id == 'VALID-123'
    assert all(m.market_id in ['EMPTY-RULES-123', 'NULL-RULES-123', 'WHITESPACE-RULES-123'] 
               for m in bad)

