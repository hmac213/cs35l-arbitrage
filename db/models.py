"""Database models matching the Supabase schema."""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from datetime import date, time, datetime


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
    image_url: Optional[str] = None
    liquidity: Optional[float] = None
    volume: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None
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
        data = asdict(self)
        
        # Remove fields that shouldn't be inserted/updated
        data.pop('id', None)
        data.pop('created_at', None)
        data.pop('updated_at', None)
        
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
        
        return data

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
            image_url=metadata.image_url,
            liquidity=metadata.liquidity,
            volume=metadata.volume,
            extra=metadata.extra
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
            image_url=data.get('image_url'),
            liquidity=data.get('liquidity'),
            volume=data.get('volume'),
            extra=data.get('extra'),
            created_at=created_at,
            updated_at=updated_at
        )

