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
    extra: Optional[Dict[str, Any]] = None  # JSONB field for exchange-specific data
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
        if self.extra is not None:
            data['extra'] = self.extra
        
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
            last_polled_at=None,  # Will be set during sync
            extra=metadata.extra  # Preserve extra data from exchange
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
            extra=data.get('extra'),
            created_at=created_at,
            updated_at=updated_at
        )


@dataclass
class MarketPair:
    """Database model for market_pairs table.
    
    This model represents a pair of matching markets from different exchanges.
    """
    market_1_id: str  # UUID from markets table
    market_1_exchange: str
    market_2_id: str  # UUID from markets table
    market_2_exchange: str
    similarity_score: float
    llm_verified: bool = False
    llm_confidence: Optional[float] = None
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
        data = {
            'market_1_id': self.market_1_id,
            'market_1_exchange': self.market_1_exchange,
            'market_2_id': self.market_2_id,
            'market_2_exchange': self.market_2_exchange,
            'similarity_score': float(self.similarity_score),
            'llm_verified': self.llm_verified,
        }
        
        if self.llm_confidence is not None:
            data['llm_confidence'] = float(self.llm_confidence)
        
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
        
        # Convert datetime objects
        data = _convert_datetime_for_json(data)
        
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketPair':
        """Create MarketPair from dictionary (e.g., from Supabase response).
        
        Args:
            data: Dictionary with market pair data.
            
        Returns:
            MarketPair instance.
        """
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
            market_1_id=data['market_1_id'],
            market_1_exchange=data['market_1_exchange'],
            market_2_id=data['market_2_id'],
            market_2_exchange=data['market_2_exchange'],
            similarity_score=float(data.get('similarity_score', 0.0)),
            llm_verified=bool(data.get('llm_verified', False)),
            llm_confidence=float(data['llm_confidence']) if data.get('llm_confidence') is not None else None,
            created_at=created_at,
            updated_at=updated_at
        )

    @classmethod
    def from_markets(
        cls,
        market1: 'DatabaseMarket',
        market2: 'DatabaseMarket',
        similarity_score: float,
        llm_verified: bool = False,
        llm_confidence: Optional[float] = None
    ) -> 'MarketPair':
        """Create MarketPair from two DatabaseMarket instances.
        
        Args:
            market1: First market (must have id from database).
            market2: Second market (must have id from database).
            similarity_score: Similarity score from vector search.
            llm_verified: Whether LLM verified the match.
            llm_confidence: LLM confidence score if available.
            
        Returns:
            MarketPair instance.
        """
        if not market1.id or not market2.id:
            raise ValueError("Both markets must have database IDs (id field)")
        
        # Ensure markets are from different exchanges
        if market1.exchange == market2.exchange:
            raise ValueError("Markets must be from different exchanges")
        
        # Order markets consistently (alphabetically by exchange)
        if market1.exchange > market2.exchange:
            market1, market2 = market2, market1
        
        return cls(
            market_1_id=market1.id,
            market_1_exchange=market1.exchange,
            market_2_id=market2.id,
            market_2_exchange=market2.exchange,
            similarity_score=similarity_score,
            llm_verified=llm_verified,
            llm_confidence=llm_confidence
        )


@dataclass
class OrderbookSnapshot:
    """Database model for orderbooks table.
    
    Represents a snapshot of an orderbook at a specific point in time.
    Stores yes/no bids and asks as JSONB arrays.
    """
    market_id: str  # UUID from markets table
    exchange: str
    yes_bids: List[Dict[str, float]]  # [{ price, quantity }, ...] sorted descending
    yes_asks: List[Dict[str, float]]  # [{ price, quantity }, ...] sorted ascending
    no_bids: List[Dict[str, float]]  # [{ price, quantity }, ...] sorted descending
    no_asks: List[Dict[str, float]]  # [{ price, quantity }, ...] sorted ascending
    timestamp: Optional[datetime] = None
    id: Optional[str] = None  # UUID from database
    created_at: Optional[datetime] = None

    def to_dict(self, exclude_none: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        data = {
            'market_id': self.market_id,
            'exchange': self.exchange,
            'yes_bids': self.yes_bids,
            'yes_asks': self.yes_asks,
            'no_bids': self.no_bids,
            'no_asks': self.no_asks,
        }
        
        if self.timestamp is not None:
            data['timestamp'] = self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp
        
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
        
        data = _convert_datetime_for_json(data)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderbookSnapshot':
        """Create OrderbookSnapshot from dictionary."""
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                timestamp = None
        
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except ValueError:
                created_at = None
        
        return cls(
            id=data.get('id'),
            market_id=data['market_id'],
            exchange=data['exchange'],
            yes_bids=data.get('yes_bids', []),
            yes_asks=data.get('yes_asks', []),
            no_bids=data.get('no_bids', []),
            no_asks=data.get('no_asks', []),
            timestamp=timestamp,
            created_at=created_at
        )


@dataclass
class ArbitrageOpportunity:
    """Database model for arbitrage_opportunities table.
    
    Represents a calculated arbitrage opportunity between two markets.
    Strategy: Buy YES on one exchange and NO on the other.
    """
    market_pair_id: str  # UUID from market_pairs table
    direction: str  # e.g., 'yes_kalshi_no_polymarket'
    yes_exchange: str  # Exchange where we buy YES
    no_exchange: str  # Exchange where we buy NO
    yes_price: float  # Price to buy YES
    no_price: float  # Price to buy NO
    profit_per_share: float  # Profit per share (1.0 - yes_price - no_price - fees)
    max_size: float  # Maximum number of shares that can be arbitraged
    fees: float = 0.0
    timestamp: Optional[datetime] = None
    id: Optional[str] = None  # UUID from database
    created_at: Optional[datetime] = None

    def to_dict(self, exclude_none: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        data = {
            'market_pair_id': self.market_pair_id,
            'direction': self.direction,
            'yes_exchange': self.yes_exchange,
            'no_exchange': self.no_exchange,
            'yes_price': float(self.yes_price),
            'no_price': float(self.no_price),
            'profit_per_share': float(self.profit_per_share),
            'max_size': float(self.max_size),
            'fees': float(self.fees),
        }
        
        if self.timestamp is not None:
            data['timestamp'] = self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp
        
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
        
        data = _convert_datetime_for_json(data)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArbitrageOpportunity':
        """Create ArbitrageOpportunity from dictionary."""
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                timestamp = None
        
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except ValueError:
                created_at = None
        
        return cls(
            id=data.get('id'),
            market_pair_id=data['market_pair_id'],
            direction=data['direction'],
            yes_exchange=data['yes_exchange'],
            no_exchange=data['no_exchange'],
            yes_price=float(data['yes_price']),
            no_price=float(data['no_price']),
            profit_per_share=float(data['profit_per_share']),
            max_size=float(data['max_size']),
            fees=float(data.get('fees', 0.0)),
            timestamp=timestamp,
            created_at=created_at
        )


@dataclass
class User:
    """Database model for users table.

    Represents a user account for authentication.
    """
    email: str
    password_hash: str
    full_name: str
    google_id: Optional[str] = None
    avatar_url: Optional[str] = None
    email_verified: bool = False
    id: Optional[str] = None  # UUID from database
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self, exclude_none: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        data = {
            'email': self.email,
            'password_hash': self.password_hash,
            'full_name': self.full_name,
            'email_verified': self.email_verified,
        }

        if self.google_id is not None:
            data['google_id'] = self.google_id
        if self.avatar_url is not None:
            data['avatar_url'] = self.avatar_url

        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}

        data = _convert_datetime_for_json(data)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create User from dictionary (e.g., from Supabase response)."""
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
            email=data['email'],
            password_hash=data['password_hash'],
            full_name=data['full_name'],
            google_id=data.get('google_id'),
            avatar_url=data.get('avatar_url'),
            email_verified=bool(data.get('email_verified', False)),
            created_at=created_at,
            updated_at=updated_at
        )

