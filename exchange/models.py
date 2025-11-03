"""Data models for exchange data structures."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class OrderBookEntry:
    """Represents a single order book entry (bid or ask)."""
    price: float
    quantity: float
    # Optional: additional metadata like order IDs, timestamps, etc.
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class OrderBook:
    """Represents a full order book for a market."""
    market_id: str
    bids: List[OrderBookEntry]  # Sorted descending by price (best bid first)
    asks: List[OrderBookEntry]  # Sorted ascending by price (best ask first)
    timestamp: Optional[datetime] = None
    # Optional: exchange-specific metadata
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MarketMetadata:
    """Contains all associated metadata for a market."""
    resolve_date: Optional[str] = None
    resolve_time: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    liquidity: Optional[float] = None
    volume: Optional[float] = None
    # Additional exchange-specific fields
    extra: Optional[Dict[str, Any]] = None


@dataclass
class Market:
    """Represents a market with all its details."""
    market_id: str
    name: str
    rules: str
    metadata: MarketMetadata
    # Exchange-specific identifier
    exchange: str
    # Optional: additional fields
    extra: Optional[Dict[str, Any]] = None

