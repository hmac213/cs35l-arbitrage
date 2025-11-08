"""Market data validation functions."""

from typing import Dict, Any, Optional
from datetime import date, time, datetime
from .errors import MarketValidationError
from db.models import DatabaseMarket


def validate_market_data(market_data: Dict[str, Any]) -> None:
    """Validate market data before processing.
    
    Args:
        market_data: Dictionary containing market data.
        
    Raises:
        MarketValidationError: If validation fails.
    """
    # Required fields
    required_fields = ['market_id', 'exchange', 'name']
    for field in required_fields:
        if not market_data.get(field):
            raise MarketValidationError(f"Missing required field: {field}")
    
    # Validate exchange name
    valid_exchanges = ['kalshi', 'polymarket']
    if market_data.get('exchange') not in valid_exchanges:
        raise MarketValidationError(
            f"Invalid exchange: {market_data.get('exchange')}. "
            f"Must be one of {valid_exchanges}"
        )
    
    # Validate market_id format (non-empty string)
    market_id = market_data.get('market_id')
    if not isinstance(market_id, str) or not market_id.strip():
        raise MarketValidationError("market_id must be a non-empty string")
    
    # Validate name (non-empty string)
    name = market_data.get('name')
    if not isinstance(name, str) or not name.strip():
        raise MarketValidationError("name must be a non-empty string")
    
    # Validate resolve_date format if present
    resolve_date = market_data.get('resolve_date')
    if resolve_date is not None:
        if isinstance(resolve_date, str):
            try:
                date.fromisoformat(resolve_date)
            except ValueError:
                raise MarketValidationError(
                    f"Invalid resolve_date format: {resolve_date}. "
                    "Expected ISO format (YYYY-MM-DD)"
                )
        elif not isinstance(resolve_date, date):
            raise MarketValidationError(
                f"resolve_date must be a date or ISO string, got {type(resolve_date)}"
            )
    
    # Validate resolve_time format if present
    resolve_time = market_data.get('resolve_time')
    if resolve_time is not None:
        if isinstance(resolve_time, str):
            try:
                time.fromisoformat(resolve_time)
            except ValueError:
                raise MarketValidationError(
                    f"Invalid resolve_time format: {resolve_time}. "
                    "Expected ISO format (HH:MM:SS)"
                )
        elif not isinstance(resolve_time, time):
            raise MarketValidationError(
                f"resolve_time must be a time or ISO string, got {type(resolve_time)}"
            )


def compare_markets(market1: DatabaseMarket, market2: DatabaseMarket) -> bool:
    """Compare two markets to determine if they are equivalent.
    
    Compares key fields that determine if a market has changed.
    If markets are equivalent, no database write is needed.
    
    Args:
        market1: First market to compare.
        market2: Second market to compare.
        
    Returns:
        True if markets are equivalent (no changes), False otherwise.
    """
    # Compare key fields that indicate market state
    key_fields = [
        'name',
        'rules',
        'resolve_date',
        'resolve_time',
        'status',
        'category',
        'subcategory',
        'description',
        'image_url',
        'liquidity',
        'volume',
    ]
    
    for field in key_fields:
        val1 = getattr(market1, field, None)
        val2 = getattr(market2, field, None)
        
        # Handle None comparisons
        if val1 is None and val2 is None:
            continue
        if val1 is None or val2 is None:
            return False
        
        # Handle list comparisons (tags)
        if field == 'tags':
            if val1 != val2:
                # Compare as sets to ignore order
                set1 = set(val1) if val1 else set()
                set2 = set(val2) if val2 else set()
                if set1 != set2:
                    return False
        else:
            if val1 != val2:
                return False
    
    return True


def get_comparable_fields(market: DatabaseMarket) -> Dict[str, Any]:
    """Extract fields that determine if a market has changed.
    
    Args:
        market: DatabaseMarket instance.
        
    Returns:
        Dictionary of comparable fields.
    """
    return {
        'name': market.name,
        'rules': market.rules,
        'resolve_date': market.resolve_date,
        'resolve_time': market.resolve_time,
        'status': market.status,
        'category': market.category,
        'subcategory': market.subcategory,
        'description': market.description,
        'image_url': market.image_url,
        'liquidity': market.liquidity,
        'volume': market.volume,
        'tags': market.tags,
    }

