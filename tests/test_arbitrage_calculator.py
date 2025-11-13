"""Unit tests for arbitrage calculator."""

import pytest
from db.models import OrderbookSnapshot, ArbitrageOpportunity
from engine.arbitrage_calculator import ArbitrageCalculator
from datetime import datetime, timezone


@pytest.fixture
def calculator():
    """Create an ArbitrageCalculator instance."""
    return ArbitrageCalculator(fees=0.0, min_profit=0.0)


@pytest.fixture
def sample_orderbook1():
    """Create a sample orderbook snapshot."""
    return OrderbookSnapshot(
        market_id="test-market-1",
        exchange="kalshi",
        yes_bids=[{'price': 0.60, 'quantity': 100}, {'price': 0.59, 'quantity': 200}],
        yes_asks=[{'price': 0.61, 'quantity': 150}, {'price': 0.62, 'quantity': 250}],
        no_bids=[{'price': 0.40, 'quantity': 100}, {'price': 0.39, 'quantity': 200}],
        no_asks=[{'price': 0.41, 'quantity': 150}, {'price': 0.42, 'quantity': 250}],
        timestamp=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_orderbook2():
    """Create another sample orderbook snapshot."""
    return OrderbookSnapshot(
        market_id="test-market-2",
        exchange="polymarket",
        yes_bids=[{'price': 0.65, 'quantity': 120}, {'price': 0.64, 'quantity': 180}],
        yes_asks=[{'price': 0.66, 'quantity': 100}, {'price': 0.67, 'quantity': 200}],
        no_bids=[{'price': 0.35, 'quantity': 120}, {'price': 0.34, 'quantity': 180}],
        no_asks=[{'price': 0.36, 'quantity': 100}, {'price': 0.37, 'quantity': 200}],
        timestamp=datetime.now(timezone.utc)
    )


def test_calculate_arbitrage_yes_direction(calculator, sample_orderbook1, sample_orderbook2):
    """Test arbitrage calculation - should find opportunity buying YES on one exchange and NO on the other."""
    opportunity = calculator.calculate_arbitrage(
        sample_orderbook1,
        sample_orderbook2,
        'test-pair-id'
    )
    
    assert opportunity is not None
    assert 'yes' in opportunity.direction.lower()
    assert opportunity.yes_exchange in ['kalshi', 'polymarket']
    assert opportunity.no_exchange in ['kalshi', 'polymarket']
    assert opportunity.yes_exchange != opportunity.no_exchange
    assert opportunity.profit_per_share > 0
    assert opportunity.max_size > 0
    assert isinstance(opportunity.max_size, (int, float))
    assert opportunity.yes_price > 0
    assert opportunity.no_price > 0


def test_calculate_arbitrage_no_direction(calculator, sample_orderbook1, sample_orderbook2):
    """Test arbitrage calculation - should find opportunity buying YES on one exchange and NO on the other."""
    opportunity = calculator.calculate_arbitrage(
        sample_orderbook1,
        sample_orderbook2,
        'test-pair-id'
    )
    
    assert opportunity is not None
    assert opportunity.profit_per_share > 0
    assert opportunity.max_size > 0
    assert isinstance(opportunity.max_size, (int, float))


def test_calculate_arbitrage_no_opportunity(calculator):
    """Test that no opportunity is found when prices don't allow arbitrage."""
    # Create orderbooks with no arbitrage opportunity
    # YES asks at 0.51 + NO asks at 0.50 = 1.01 (no profit)
    orderbook1 = OrderbookSnapshot(
        market_id="test-1",
        exchange="kalshi",
        yes_bids=[{'price': 0.50, 'quantity': 100}],
        yes_asks=[{'price': 0.51, 'quantity': 100}],
        no_bids=[{'price': 0.49, 'quantity': 100}],
        no_asks=[{'price': 0.50, 'quantity': 100}],
        timestamp=datetime.now(timezone.utc)
    )
    
    orderbook2 = OrderbookSnapshot(
        market_id="test-2",
        exchange="polymarket",
        yes_bids=[{'price': 0.50, 'quantity': 100}],
        yes_asks=[{'price': 0.51, 'quantity': 100}],
        no_bids=[{'price': 0.49, 'quantity': 100}],
        no_asks=[{'price': 0.50, 'quantity': 100}],
        timestamp=datetime.now(timezone.utc)
    )
    
    opportunity = calculator.calculate_arbitrage(
        orderbook1,
        orderbook2,
        'test-pair-id'
    )
    
    # Should return None when no arbitrage opportunity exists
    assert opportunity is None


def test_calculate_arbitrage_with_fees(calculator, sample_orderbook1, sample_orderbook2):
    """Test arbitrage calculation with fees."""
    calculator_with_fees = ArbitrageCalculator(fees=0.02, min_profit=0.0)  # 2% fees
    
    opportunity = calculator_with_fees.calculate_arbitrage(
        sample_orderbook1,
        sample_orderbook2,
        'test-pair-id'
    )
    
    # With fees, profit should be lower or opportunity might not exist
    if opportunity:
        assert opportunity.fees == 0.02
        assert opportunity.profit_per_share >= 0  # Should still be profitable after fees


def test_find_max_size_per_level(calculator, sample_orderbook1, sample_orderbook2):
    """Test per-level maximum size calculation."""
    yes_asks = sample_orderbook1.yes_asks
    no_asks = sample_orderbook2.no_asks
    
    max_size = calculator._find_max_size_per_level(yes_asks, no_asks, 0.0)
    
    assert isinstance(max_size, int)
    assert max_size >= 0
    # Max size should be limited by available liquidity
    assert max_size <= sum(entry['quantity'] for entry in yes_asks)
    assert max_size <= sum(entry['quantity'] for entry in no_asks)


def test_calculate_avg_price(calculator):
    """Test average price calculation for filling a size."""
    side = [
        {'price': 0.60, 'quantity': 100},
        {'price': 0.61, 'quantity': 150},
        {'price': 0.62, 'quantity': 200}
    ]
    
    # Fill 150 units
    avg_price, filled = calculator._calculate_avg_price(side, 150.0, is_ask=True)
    
    assert avg_price is not None
    assert filled == 150.0
    # Average should be between 0.60 and 0.61
    assert 0.60 <= avg_price <= 0.61


def test_calculate_avg_price_partial_fill(calculator):
    """Test average price when size exceeds available liquidity."""
    side = [
        {'price': 0.60, 'quantity': 50},
        {'price': 0.61, 'quantity': 30}
    ]
    
    # Try to fill 100 units (only 80 available)
    avg_price, filled = calculator._calculate_avg_price(side, 100.0, is_ask=True)
    
    assert filled == 80.0
    assert avg_price is not None


def test_calculate_yes_no_arbitrage_profitable(calculator):
    """Test the YES/NO arbitrage strategy with a clear profitable case."""
    # Create orderbooks where buying YES on one and NO on the other is profitable
    # Kalshi: YES asks at 0.97, NO asks at 0.04
    # Polymarket: YES asks at 0.99, NO asks at 0.02
    # Buy YES on Kalshi (0.97) + NO on Polymarket (0.02) = 0.99 (profit: 0.01)
    
    kalshi_orderbook = OrderbookSnapshot(
        market_id="test-kalshi",
        exchange="kalshi",
        yes_bids=[{'price': 0.96, 'quantity': 100}],
        yes_asks=[{'price': 0.97, 'quantity': 100}],
        no_bids=[{'price': 0.03, 'quantity': 100}],
        no_asks=[{'price': 0.04, 'quantity': 100}],
        timestamp=datetime.now(timezone.utc)
    )
    
    polymarket_orderbook = OrderbookSnapshot(
        market_id="test-polymarket",
        exchange="polymarket",
        yes_bids=[{'price': 0.98, 'quantity': 100}],
        yes_asks=[{'price': 0.99, 'quantity': 100}],
        no_bids=[{'price': 0.01, 'quantity': 100}],
        no_asks=[{'price': 0.02, 'quantity': 100}],
        timestamp=datetime.now(timezone.utc)
    )
    
    opportunity = calculator._calculate_yes_no_arbitrage(
        kalshi_orderbook,
        polymarket_orderbook,
        'test-pair-id',
        yes_exchange='kalshi',
        no_exchange='polymarket'
    )
    
    assert opportunity is not None
    assert opportunity.yes_exchange == 'kalshi'
    assert opportunity.no_exchange == 'polymarket'
    assert opportunity.yes_price == pytest.approx(0.97)
    assert opportunity.no_price == pytest.approx(0.02)
    assert opportunity.profit_per_share == pytest.approx(0.01, abs=0.001)
    assert opportunity.max_size > 0
    assert isinstance(opportunity.max_size, (int, float))

