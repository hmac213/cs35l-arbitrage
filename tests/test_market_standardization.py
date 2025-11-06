"""Tests for market data standardization across exchanges."""

import pytest
from datetime import date, time
from exchange.models import Market, MarketMetadata
from db.models import DatabaseMarket


def test_kalshi_market_normalization():
    """Test that Kalshi markets are normalized correctly."""
    from exchange.clients.kalshi_client import KalshiClient
    
    client = KalshiClient()
    
    # Sample Kalshi market data (from actual API response)
    sample_data = {
        'ticker': 'KXMVESPORTSMULTIGAMEEXTENDED-S20257D2122032BC-6531DB1E8D6',
        'event_ticker': 'KXMVESPORTSMULTIGAMEEXTENDED-S20257D2122032BC',
        'title': 'Test Market Title',
        'rules_primary': 'Primary rules text',
        'rules_secondary': 'Secondary rules text',
        'subtitle': 'Test Rules',
        'open_time': '2025-11-29 02:25:39.279338+00:00',
        'close_time': '2025-12-13 03:00:00+00:00',
        'expiration_time': '2025-12-13 03:00:00+00:00',
        'status': 'active',
        'yes_bid': 50,
        'yes_ask': 55,
        'no_bid': 45,
        'no_ask': 50,
        'last_price': 52,
        'volume': 1000,
        'volume_24h': 500,
    }
    
    market = client._normalize_market(sample_data)
    
    # Verify core fields
    assert market.market_id == sample_data['ticker']
    assert market.name == sample_data['title']
    # Rules should combine rules_primary and rules_secondary
    assert market.rules == 'Primary rules text\n\nSecondary rules text'
    assert market.exchange == 'kalshi'
    
    # Test fallback when rules_primary/secondary are not present
    sample_data_no_rules = {**sample_data}
    del sample_data_no_rules['rules_primary']
    del sample_data_no_rules['rules_secondary']
    market_no_rules = client._normalize_market(sample_data_no_rules)
    assert market_no_rules.rules == sample_data['subtitle']
    
    # Verify metadata
    assert market.metadata.resolve_date == '2025-12-13'
    assert market.metadata.resolve_time == '03:00:00'
    assert market.metadata.category is None  # Kalshi doesn't provide category
    assert market.metadata.tags is None  # Kalshi doesn't provide tags
    assert market.metadata.volume == 1000
    
    # Verify extra fields
    assert market.metadata.extra['status'] == 'active'
    assert market.metadata.extra['ticker'] == sample_data['ticker']
    assert market.metadata.extra['event_ticker'] == sample_data['event_ticker']
    assert market.metadata.extra['yes_bid'] == 50
    # Verify rules_primary and rules_secondary are stored in extra
    assert market.metadata.extra['rules_primary'] == 'Primary rules text'
    assert market.metadata.extra['rules_secondary'] == 'Secondary rules text'


def test_polymarket_market_normalization():
    """Test that Polymarket markets are normalized correctly."""
    from exchange.clients.polymarket_client import PolymarketClient
    
    client = PolymarketClient()
    
    # Sample Polymarket market data (from actual API response)
    sample_data = {
        'slug': 'test-market-slug',
        'title': 'Test Market Title',
        'question': 'Test Market Question',
        'description': 'Test Market Description',
        'endDate': '2025-11-30T02:30:00Z',
        'image': 'https://example.com/image.png',
        'liquidity': '97430.0234',
        'tags': [
            {'id': '1', 'label': 'Crypto', 'slug': 'crypto', 'forceShow': True},
            {'id': '2', 'label': 'Bitcoin', 'slug': 'bitcoin', 'forceShow': False},
        ],
        'conditionId': '0x123',
        'clobTokenIds': '["token1", "token2"]',
        'active': True,
        'closed': False,
    }
    
    market = client._normalize_market(sample_data)
    
    # Verify core fields
    assert market.market_id == sample_data['slug']
    assert market.name == sample_data['question']  # Prefer question over title
    assert market.rules == sample_data['description']
    assert market.exchange == 'polymarket'
    
    # Verify metadata
    assert market.metadata.resolve_date == '2025-11-30'
    assert market.metadata.resolve_time == '02:30:00'
    assert market.metadata.category == 'Crypto'  # Extracted from first tag with forceShow
    assert market.metadata.tags == ['Crypto', 'Bitcoin']  # Extracted labels
    assert market.metadata.image_url == sample_data['image']
    assert market.metadata.liquidity == 97430.0234  # Converted from string
    
    # Verify extra fields
    assert market.metadata.extra['conditionId'] == '0x123'
    assert market.metadata.extra['active'] is True
    assert market.metadata.extra['tags_full'] == sample_data['tags']


def test_database_market_conversion():
    """Test conversion from Market to DatabaseMarket."""
    # Create a normalized market
    metadata = MarketMetadata(
        resolve_date='2025-12-13',
        resolve_time='03:00:00',
        category='Sports',
        tags=['NFL', 'Football'],
        description='Test description',
        image_url='https://example.com/image.png',
        liquidity=1000.5,
        volume=5000.0,
        extra={'status': 'active'}
    )
    
    market = Market(
        market_id='TEST-MARKET-123',
        name='Test Market',
        rules='Test Rules',
        metadata=metadata,
        exchange='kalshi',
        extra={'ticker': 'TEST-MARKET-123'}
    )
    
    # Convert to DatabaseMarket
    db_market = DatabaseMarket.from_exchange_market(market)
    
    # Verify conversion
    assert db_market.market_id == 'TEST-MARKET-123'
    assert db_market.exchange == 'kalshi'
    assert db_market.name == 'Test Market'
    assert db_market.rules == 'Test Rules'
    assert isinstance(db_market.resolve_date, date)
    assert db_market.resolve_date == date(2025, 12, 13)
    assert isinstance(db_market.resolve_time, time)
    assert db_market.resolve_time == time(3, 0, 0)
    assert db_market.category == 'Sports'
    assert db_market.tags == ['NFL', 'Football']
    assert db_market.description == 'Test description'
    assert db_market.image_url == 'https://example.com/image.png'
    assert db_market.liquidity == 1000.5
    assert db_market.volume == 5000.0
    assert db_market.extra == {'status': 'active'}


def test_database_market_to_dict():
    """Test DatabaseMarket.to_dict() for database operations."""
    db_market = DatabaseMarket(
        market_id='TEST-MARKET-123',
        exchange='polymarket',
        name='Test Market',
        rules='Test Rules',
        resolve_date=date(2025, 12, 13),
        resolve_time=time(3, 0, 0),
        category='Crypto',
        tags=['Bitcoin', 'BTC'],
        description='Test description',
        image_url='https://example.com/image.png',
        liquidity=1000.5,
        volume=5000.0,
        extra={'conditionId': '0x123'}
    )
    
    data = db_market.to_dict()
    
    # Verify all fields are present
    assert 'market_id' in data
    assert 'exchange' in data
    assert 'name' in data
    assert 'rules' in data
    assert 'resolve_date' in data
    assert 'resolve_time' in data
    assert 'category' in data
    assert 'tags' in data
    assert 'description' in data
    assert 'image_url' in data
    assert 'liquidity' in data
    assert 'volume' in data
    assert 'extra' in data
    
    # Verify id, created_at, updated_at are excluded
    assert 'id' not in data
    assert 'created_at' not in data
    assert 'updated_at' not in data
    
    # Verify data types
    assert isinstance(data['resolve_date'], date)
    assert isinstance(data['resolve_time'], time)
    assert isinstance(data['tags'], list)
    assert isinstance(data['extra'], dict)


def test_unified_schema_compatibility():
    """Test that both exchanges produce compatible data for the unified schema."""
    from exchange.clients.kalshi_client import KalshiClient
    from exchange.clients.polymarket_client import PolymarketClient
    
    kalshi_client = KalshiClient()
    polymarket_client = PolymarketClient()
    
    # Sample data from both exchanges
    kalshi_data = {
        'ticker': 'KALSHI-123',
        'title': 'Kalshi Market',
        'subtitle': 'Kalshi Rules',
        'close_time': '2025-12-13 03:00:00+00:00',
        'status': 'active',
        'volume': 1000,
    }
    
    polymarket_data = {
        'slug': 'polymarket-123',
        'question': 'Polymarket Market',
        'description': 'Polymarket Rules',
        'endDate': '2025-12-13T03:00:00Z',
        'liquidity': '5000.0',
        'tags': [{'id': '1', 'label': 'Crypto', 'slug': 'crypto'}],
    }
    
    kalshi_market = kalshi_client._normalize_market(kalshi_data)
    polymarket_market = polymarket_client._normalize_market(polymarket_data)
    
    # Convert both to DatabaseMarket
    kalshi_db = DatabaseMarket.from_exchange_market(kalshi_market)
    polymarket_db = DatabaseMarket.from_exchange_market(polymarket_market)
    
    # Both should have the same core structure
    assert kalshi_db.resolve_date == polymarket_db.resolve_date
    assert kalshi_db.resolve_time == polymarket_db.resolve_time
    
    # Both should convert to dict successfully
    kalshi_dict = kalshi_db.to_dict()
    polymarket_dict = polymarket_db.to_dict()
    
    # Both should have the same required fields
    required_fields = ['market_id', 'exchange', 'name', 'rules', 'resolve_date', 'resolve_time']
    for field in required_fields:
        assert field in kalshi_dict
        assert field in polymarket_dict
    
    # Both should have extra field
    assert 'extra' in kalshi_dict
    assert 'extra' in polymarket_dict

