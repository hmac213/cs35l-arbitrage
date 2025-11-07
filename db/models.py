"""Database models matching the Supabase schema."""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from datetime import date, time, datetime


def _convert_datetime_for_json(obj: Any) -> Any:
    """Recursively convert datetime objects to ISO format strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, time):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _convert_datetime_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetime_for_json(item) for item in obj]
    else:
        return obj


@dataclass
class DatabaseMarket:
    """Database model for markets table.
    
    This model represents a market record in the Supabase database.
    It maps to the markets table schema and can be converted from/to
    the exchange.models.Market format.
    """
    market_id: str
    exchange: str
    name: str
    rules: Optional[str] = None
    resolve_date: Optional[date] = None
    resolve_time: Optional[time] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    status: Optional[str] = 'active'  # 'active', 'expired', 'processing'
    last_polled_at: Optional[datetime] = None
    id: Optional[str] = None  # UUID from database
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self, exclude_none: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for database operations.
        
        Args:
            exclude_none: If True, exclude None values from the dict.
            
        Returns:
            Dictionary representation suitable for Supabase operations.
        """
        # Build dict manually to handle datetime conversions properly
        data = {}
        
        # Add all fields except those that shouldn't be inserted/updated
        if self.market_id is not None:
            data['market_id'] = self.market_id
        if self.exchange is not None:
            data['exchange'] = self.exchange
        if self.name is not None:
            data['name'] = self.name
        if self.rules is not None:
            data['rules'] = self.rules
        if self.resolve_date is not None:
            data['resolve_date'] = self.resolve_date.isoformat() if isinstance(self.resolve_date, date) else self.resolve_date
        if self.resolve_time is not None:
            data['resolve_time'] = self.resolve_time.isoformat() if isinstance(self.resolve_time, time) else self.resolve_time
        if self.category is not None:
            data['category'] = self.category
        if self.subcategory is not None:
            data['subcategory'] = self.subcategory
        if self.tags is not None:
            data['tags'] = self.tags
        if self.description is not None:
            data['description'] = self.description
        if self.status is not None:
            data['status'] = self.status
        if self.last_polled_at is not None:
            # Convert datetime to ISO format string
            if isinstance(self.last_polled_at, datetime):
                data['last_polled_at'] = self.last_polled_at.isoformat()
            else:
                data['last_polled_at'] = self.last_polled_at
        
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
        
        # Recursively convert any remaining datetime objects
        data = _convert_datetime_for_json(data)
        
        return data
    
    def is_expired(self) -> bool:
        """Check if market has passed its resolve date/time.
        
        Returns:
            True if market has expired, False otherwise.
        """
        if not self.resolve_date:
            return False
        
        from datetime import datetime, timezone
        
        # Combine resolve_date and resolve_time
        if self.resolve_time:
            resolve_datetime = datetime.combine(self.resolve_date, self.resolve_time)
        else:
            # If no time specified, assume end of day
            resolve_datetime = datetime.combine(self.resolve_date, datetime.max.time())
        
        # Compare with current time (UTC)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return resolve_datetime < now

    @classmethod
    def from_exchange_market(cls, market) -> 'DatabaseMarket':
        """Create DatabaseMarket from exchange.models.Market.
        
        Args:
            market: An instance of exchange.models.Market.
            
        Returns:
            DatabaseMarket instance.
        """
        metadata = market.metadata
        
        # Convert resolve_date and resolve_time from strings if needed
        resolve_date = None
        resolve_time = None
        
        if metadata.resolve_date:
            if isinstance(metadata.resolve_date, str):
                try:
                    resolve_date = date.fromisoformat(metadata.resolve_date)
                except ValueError:
                    pass
            elif isinstance(metadata.resolve_date, date):
                resolve_date = metadata.resolve_date
        
        if metadata.resolve_time:
            if isinstance(metadata.resolve_time, str):
                try:
                    resolve_time = time.fromisoformat(metadata.resolve_time)
                except ValueError:
                    pass
            elif isinstance(metadata.resolve_time, time):
                resolve_time = metadata.resolve_time
        
        return cls(
            market_id=market.market_id,
            exchange=market.exchange,
            name=market.name,
            rules=market.rules,
            resolve_date=resolve_date,
            resolve_time=resolve_time,
            category=metadata.category,
            subcategory=metadata.subcategory,
            tags=metadata.tags,
            description=metadata.description,
            status='active',  # New markets start as active
            last_polled_at=None  # Will be set during sync
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatabaseMarket':
        """Create DatabaseMarket from dictionary (e.g., from Supabase response).
        
        Args:
            data: Dictionary with market data.
            
        Returns:
            DatabaseMarket instance.
        """
        # Handle date/time conversions
        resolve_date = data.get('resolve_date')
        if isinstance(resolve_date, str):
            try:
                resolve_date = date.fromisoformat(resolve_date)
            except ValueError:
                resolve_date = None
        
        resolve_time = data.get('resolve_time')
        if isinstance(resolve_time, str):
            try:
                resolve_time = time.fromisoformat(resolve_time)
            except ValueError:
                resolve_time = None
        
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except ValueError:
                created_at = None
        
        updated_at = data.get('updated_at')
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            except ValueError:
                updated_at = None
        
        last_polled_at = data.get('last_polled_at')
        if isinstance(last_polled_at, str):
            try:
                last_polled_at = datetime.fromisoformat(last_polled_at.replace('Z', '+00:00'))
            except ValueError:
                last_polled_at = None
        
        return cls(
            id=data.get('id'),
            market_id=data['market_id'],
            exchange=data['exchange'],
            name=data['name'],
            rules=data.get('rules'),
            resolve_date=resolve_date,
            resolve_time=resolve_time,
            category=data.get('category'),
            subcategory=data.get('subcategory'),
            tags=data.get('tags'),
            description=data.get('description'),
            status=data.get('status', 'active'),
            last_polled_at=last_polled_at,
            created_at=created_at,
            updated_at=updated_at
        )

