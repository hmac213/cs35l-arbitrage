"""Supabase database client wrapper."""

import os
from typing import List, Optional, Dict, Any
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

from .models import DatabaseMarket


class SupabaseClient:
    """Client for interacting with Supabase database.
    
    This client provides methods for managing markets in the Supabase database,
    including CRUD operations and syncing data from exchange clients.
    """
    
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None
    ):
        """Initialize the Supabase client.
        
        Args:
            supabase_url: Supabase project URL. If not provided, reads from SUPABASE_URL env var.
            supabase_key: Supabase anon/service role key. If not provided, reads from SUPABASE_KEY env var.
        """
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_KEY")
        
        if not self.supabase_url:
            raise ValueError("Supabase URL is required. Set SUPABASE_URL environment variable or pass supabase_url parameter.")
        if not self.supabase_key:
            raise ValueError("Supabase key is required. Set SUPABASE_KEY environment variable or pass supabase_key parameter.")
        
        self.client: Client = create_client(
            self.supabase_url,
            self.supabase_key,
            options=ClientOptions(
                postgrest_client_timeout=30,
                storage_client_timeout=30,
            )
        )
    
    def upsert_market(self, market: DatabaseMarket) -> Dict[str, Any]:
        """Insert or update a market in the database.
        
        Uses the unique constraint on (market_id, exchange) to determine
        if the market already exists. If it exists, updates it; otherwise inserts.
        
        Args:
            market: DatabaseMarket instance to upsert.
            
        Returns:
            Dictionary containing the inserted/updated market data.
        """
        data = market.to_dict(exclude_none=True)
        
        response = self.client.table("markets").upsert(
            data,
            on_conflict="market_id,exchange"
        ).execute()
        
        if response.data:
            return response.data[0] if isinstance(response.data, list) else response.data
        return {}
    
    def upsert_markets(self, markets: List[DatabaseMarket]) -> List[Dict[str, Any]]:
        """Insert or update multiple markets in the database.
        
        Args:
            markets: List of DatabaseMarket instances to upsert.
            
        Returns:
            List of dictionaries containing the inserted/updated market data.
        """
        if not markets:
            return []
        
        data = [market.to_dict(exclude_none=True) for market in markets]
        
        response = self.client.table("markets").upsert(
            data,
            on_conflict="market_id,exchange"
        ).execute()
        
        if response.data:
            return response.data if isinstance(response.data, list) else [response.data]
        return []
    
    def get_market(self, market_id: str, exchange: str) -> Optional[DatabaseMarket]:
        """Get a single market by market_id and exchange.
        
        Args:
            market_id: The market identifier.
            exchange: The exchange name ('kalshi' or 'polymarket').
            
        Returns:
            DatabaseMarket instance if found, None otherwise.
        """
        response = self.client.table("markets").select("*").eq(
            "market_id", market_id
        ).eq("exchange", exchange).execute()
        
        if response.data and len(response.data) > 0:
            return DatabaseMarket.from_dict(response.data[0])
        return None
    
    def get_markets_by_exchange(
        self,
        exchange: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[DatabaseMarket]:
        """Get all markets for a specific exchange.
        
        Args:
            exchange: The exchange name ('kalshi' or 'polymarket').
            limit: Maximum number of results to return.
            offset: Number of results to skip.
            
        Returns:
            List of DatabaseMarket instances.
        """
        query = self.client.table("markets").select("*").eq("exchange", exchange)
        
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        
        response = query.execute()
        
        if response.data:
            return [DatabaseMarket.from_dict(item) for item in response.data]
        return []
    
    def get_markets_by_category(
        self,
        category: str,
        exchange: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[DatabaseMarket]:
        """Get markets by category.
        
        Args:
            category: The category name.
            exchange: Optional exchange filter.
            limit: Maximum number of results to return.
            
        Returns:
            List of DatabaseMarket instances.
        """
        query = self.client.table("markets").select("*").eq("category", category)
        
        if exchange:
            query = query.eq("exchange", exchange)
        if limit:
            query = query.limit(limit)
        
        response = query.execute()
        
        if response.data:
            return [DatabaseMarket.from_dict(item) for item in response.data]
        return []
    
    def get_all_markets(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[DatabaseMarket]:
        """Get all markets.
        
        Args:
            limit: Maximum number of results to return.
            offset: Number of results to skip.
            
        Returns:
            List of DatabaseMarket instances.
        """
        query = self.client.table("markets").select("*")
        
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        
        response = query.execute()
        
        if response.data:
            return [DatabaseMarket.from_dict(item) for item in response.data]
        return []
    
    def delete_market(self, market_id: str, exchange: str) -> bool:
        """Delete a market from the database.
        
        Args:
            market_id: The market identifier.
            exchange: The exchange name ('kalshi' or 'polymarket').
            
        Returns:
            True if deleted, False otherwise.
        """
        response = self.client.table("markets").delete().eq(
            "market_id", market_id
        ).eq("exchange", exchange).execute()
        
        return response.data is not None
    
    def sync_market_from_exchange(self, exchange_market) -> DatabaseMarket:
        """Sync a market from an exchange client to the database.
        
        Converts an exchange.models.Market to DatabaseMarket and upserts it.
        
        Args:
            exchange_market: An instance of exchange.models.Market.
            
        Returns:
            DatabaseMarket instance that was synced.
        """
        db_market = DatabaseMarket.from_exchange_market(exchange_market)
        result = self.upsert_market(db_market)
        return DatabaseMarket.from_dict(result)
    
    def sync_markets_from_exchange(self, exchange_markets: List) -> List[DatabaseMarket]:
        """Sync multiple markets from an exchange client to the database.
        
        Args:
            exchange_markets: List of exchange.models.Market instances.
            
        Returns:
            List of DatabaseMarket instances that were synced.
        """
        db_markets = [DatabaseMarket.from_exchange_market(m) for m in exchange_markets]
        results = self.upsert_markets(db_markets)
        return [DatabaseMarket.from_dict(result) for result in results]

