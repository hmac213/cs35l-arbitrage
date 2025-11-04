"""Tests for data models."""

import pytest
from datetime import datetime
from exchange.models import Market, OrderBook, OrderBookEntry, MarketMetadata


class TestOrderBookEntry:
    """Test suite for OrderBookEntry."""
    
    def test_orderbook_entry_creation(self):
        """Test creating an OrderBookEntry."""
        entry = OrderBookEntry(price=0.65, quantity=100)
        
        assert entry.price == 0.65
        assert entry.quantity == 100
        assert entry.metadata is None
    
    def test_orderbook_entry_with_metadata(self):
        """Test creating an OrderBookEntry with metadata."""
        metadata = {"maker": "0x123", "timestamp": 1234567890}
        entry = OrderBookEntry(price=0.65, quantity=100, metadata=metadata)
        
        assert entry.price == 0.65
        assert entry.quantity == 100
        assert entry.metadata == metadata


class TestOrderBook:
    """Test suite for OrderBook."""
    
    def test_orderbook_creation(self):
        """Test creating an OrderBook."""
        bids = [OrderBookEntry(price=0.65, quantity=100)]
        asks = [OrderBookEntry(price=0.66, quantity=150)]
        
        orderbook = OrderBook(
            market_id="TEST-123",
            bids=bids,
            asks=asks
        )
        
        assert orderbook.market_id == "TEST-123"
        assert len(orderbook.bids) == 1
        assert len(orderbook.asks) == 1
        assert orderbook.timestamp is None
        assert orderbook.metadata is None
    
    def test_orderbook_with_timestamp(self):
        """Test creating an OrderBook with timestamp."""
        timestamp = datetime.now()
        orderbook = OrderBook(
            market_id="TEST-123",
            bids=[],
            asks=[],
            timestamp=timestamp
        )
        
        assert orderbook.timestamp == timestamp


class TestMarketMetadata:
    """Test suite for MarketMetadata."""
    
    def test_market_metadata_creation(self):
        """Test creating MarketMetadata."""
        metadata = MarketMetadata(
            resolve_date="2024-12-31",
            resolve_time="23:59:59",
            category="Politics"
        )
        
        assert metadata.resolve_date == "2024-12-31"
        assert metadata.resolve_time == "23:59:59"
        assert metadata.category == "Politics"
        assert metadata.tags is None
        assert metadata.extra is None
    
    def test_market_metadata_with_all_fields(self):
        """Test creating MarketMetadata with all fields."""
        metadata = MarketMetadata(
            resolve_date="2024-12-31",
            resolve_time="23:59:59",
            category="Politics",
            subcategory="Elections",
            tags=["election", "2024"],
            description="Test description",
            image_url="https://example.com/image.jpg",
            liquidity=1000000.0,
            volume=500000.0,
            extra={"key": "value"}
        )
        
        assert metadata.resolve_date == "2024-12-31"
        assert metadata.category == "Politics"
        assert metadata.tags == ["election", "2024"]
        assert metadata.liquidity == 1000000.0
        assert metadata.extra == {"key": "value"}


class TestMarket:
    """Test suite for Market."""
    
    def test_market_creation(self):
        """Test creating a Market."""
        metadata = MarketMetadata(category="Politics")
        market = Market(
            market_id="TEST-123",
            name="Test Market",
            rules="Test rules",
            metadata=metadata,
            exchange="kalshi"
        )
        
        assert market.market_id == "TEST-123"
        assert market.name == "Test Market"
        assert market.rules == "Test rules"
        assert market.metadata == metadata
        assert market.exchange == "kalshi"
        assert market.extra is None
    
    def test_market_with_extra(self):
        """Test creating a Market with extra fields."""
        metadata = MarketMetadata()
        market = Market(
            market_id="TEST-123",
            name="Test Market",
            rules="Test rules",
            metadata=metadata,
            exchange="polymarket",
            extra={"original_data": {"key": "value"}}
        )
        
        assert market.extra == {"original_data": {"key": "value"}}

