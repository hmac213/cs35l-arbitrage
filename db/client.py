"""Supabase database client wrapper."""

import os
from typing import List, Optional, Dict, Any
from supabase import create_client, Client

from .models import DatabaseMarket, MarketPair, OrderbookSnapshot, ArbitrageOpportunity


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
            self.supabase_key
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
    
    def upsert_markets(
        self, 
        markets: List[DatabaseMarket], 
        batch_size: int = 500
    ) -> List[Dict[str, Any]]:
        """Insert or update multiple markets in the database.
        
        Args:
            markets: List of DatabaseMarket instances to upsert.
            batch_size: Number of markets to upsert per batch (default: 500).
            
        Returns:
            List of dictionaries containing the inserted/updated market data.
        """
        if not markets:
            return []
        
        # Deduplicate markets by (market_id, exchange) - keep the last occurrence
        seen = {}
        for market in markets:
            key = (market.market_id, market.exchange)
            seen[key] = market
        deduplicated_markets = list(seen.values())
        
        all_results = []
        
        # Process in batches to avoid timeout
        for i in range(0, len(deduplicated_markets), batch_size):
            batch = deduplicated_markets[i:i + batch_size]
            data = [market.to_dict(exclude_none=True) for market in batch]
            
            response = self.client.table("markets").upsert(
                data,
                on_conflict="market_id,exchange"
            ).execute()
            
            if response.data:
                batch_results = response.data if isinstance(response.data, list) else [response.data]
                all_results.extend(batch_results)
        
        return all_results
    
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
    
    def delete_markets_batch(
        self,
        markets: List[DatabaseMarket],
        batch_size: int = 100
    ) -> int:
        """Delete multiple markets from the database in batches.
        
        Args:
            markets: List of DatabaseMarket instances to delete.
            batch_size: Number of markets to delete per batch (default: 100).
            
        Returns:
            Number of markets successfully deleted.
        """
        if not markets:
            return 0
        
        deleted_count = 0
        
        # Group by exchange for more efficient batch deletion
        by_exchange = {}
        for market in markets:
            if market.exchange not in by_exchange:
                by_exchange[market.exchange] = []
            by_exchange[market.exchange].append(market.market_id)
        
        # Delete in batches per exchange
        for exchange, market_ids in by_exchange.items():
            # Process in batches
            for i in range(0, len(market_ids), batch_size):
                batch_ids = market_ids[i:i + batch_size]
                
                # Use .in_() for batch deletion
                response = self.client.table("markets").delete().eq(
                    "exchange", exchange
                ).in_("market_id", batch_ids).execute()
                
                # Count deleted (response.data is a list of deleted records)
                if response.data:
                    deleted_count += len(response.data) if isinstance(response.data, list) else 1
        
        return deleted_count
    
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
    
    def upsert_market_pair(self, pair: MarketPair) -> Dict[str, Any]:
        """Insert or update a market pair in the database.
        
        Uses the unique constraint on (market_1_id, market_2_id) to determine
        if the pair already exists. If it exists, updates it; otherwise inserts.
        
        Args:
            pair: MarketPair instance to upsert.
            
        Returns:
            Dictionary containing the inserted/updated pair data.
        """
        data = pair.to_dict(exclude_none=True)
        
        response = self.client.table("market_pairs").upsert(
            data,
            on_conflict="market_1_id,market_2_id"
        ).execute()
        
        if response.data:
            return response.data[0] if isinstance(response.data, list) else response.data
        return {}
    
    def get_market_pairs_by_market(self, market_id: str, exchange: str) -> List[MarketPair]:
        """Get all market pairs that include a specific market.
        
        Args:
            market_id: The market identifier (market_id field, not UUID).
            exchange: The exchange name ('kalshi' or 'polymarket').
            
        Returns:
            List of MarketPair instances.
        """
        # First get the market's UUID
        market = self.get_market(market_id, exchange)
        if not market or not market.id:
            return []
        
        # Query pairs where this market is either market_1 or market_2
        response = self.client.table("market_pairs").select("*").or_(
            f"market_1_id.eq.{market.id},market_2_id.eq.{market.id}"
        ).execute()
        
        if response.data:
            return [MarketPair.from_dict(item) for item in response.data]
        return []
    
    def get_all_market_pairs(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        llm_verified: Optional[bool] = None
    ) -> List[MarketPair]:
        """Get all market pairs.
        
        Args:
            limit: Maximum number of results to return.
            offset: Number of results to skip.
            llm_verified: Filter by LLM verification status (optional).
            
        Returns:
            List of MarketPair instances.
        """
        query = self.client.table("market_pairs").select("*")
        
        if llm_verified is not None:
            query = query.eq("llm_verified", llm_verified)
        
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        
        response = query.execute()
        
        if response.data:
            return [MarketPair.from_dict(item) for item in response.data]
        return []
    
    def delete_market_pair(self, pair_id: str) -> bool:
        """Delete a market pair from the database.
        
        Args:
            pair_id: The pair UUID (id field).
            
        Returns:
            True if deleted, False otherwise.
        """
        response = self.client.table("market_pairs").delete().eq(
            "id", pair_id
        ).execute()
        
        return response.data is not None
    
    def delete_pairs_by_market(self, market_id: str, exchange: str) -> int:
        """Delete all market pairs that include a specific market.
        
        This is useful when a market is deleted and we need to clean up pairs.
        Note: The database foreign key constraint should handle this automatically,
        but this method provides explicit cleanup if needed.
        
        Args:
            market_id: The market identifier (market_id field, not UUID).
            exchange: The exchange name ('kalshi' or 'polymarket').
            
        Returns:
            The number of deleted pairs.
        """
        # First get the market's UUID
        market = self.get_market(market_id, exchange)
        if not market or not market.id:
            return 0
        
        # Delete pairs where this market is either market_1 or market_2
        response = self.client.table("market_pairs").delete().or_(
            f"market_1_id.eq.{market.id},market_2_id.eq.{market.id}"
        ).execute()
        
        if response.data:
            return len(response.data) if isinstance(response.data, list) else 1
        return 0

    def store_orderbook(self, orderbook: OrderbookSnapshot) -> Dict[str, Any]:
        """Store an orderbook snapshot in the database.
        
        Args:
            orderbook: OrderbookSnapshot instance to store.
            
        Returns:
            Dictionary containing the inserted orderbook data.
        """
        data = orderbook.to_dict(exclude_none=True)
        
        response = self.client.table("orderbooks").insert(data).execute()
        
        if response.data:
            return response.data[0] if isinstance(response.data, list) else response.data
        return {}

    def get_latest_orderbook(self, market_id: str, exchange: str) -> Optional[OrderbookSnapshot]:
        """Get the latest orderbook snapshot for a market.
        
        Args:
            market_id: Market identifier (market_id field) or UUID.
            exchange: Exchange name.
            
        Returns:
            OrderbookSnapshot if found, None otherwise.
        """
        # If market_id is a UUID (36 chars), use it directly; otherwise get the market first
        if len(market_id) == 36 and market_id.count('-') == 4:
            # Looks like a UUID, use directly
            market_uuid = market_id
        else:
            # Get the market to find its UUID
            market = self.get_market(market_id, exchange)
            if not market or not market.id:
                return None
            market_uuid = market.id
        
        response = self.client.table("orderbooks") \
            .select("*") \
            .eq("market_id", market_uuid) \
            .eq("exchange", exchange) \
            .order("timestamp", desc=True) \
            .limit(1) \
            .execute()
        
        if response.data and len(response.data) > 0:
            return OrderbookSnapshot.from_dict(response.data[0])
        return None

    def store_arbitrage_opportunity(self, opportunity: ArbitrageOpportunity) -> Dict[str, Any]:
        """Store an arbitrage opportunity in the database.
        
        Args:
            opportunity: ArbitrageOpportunity instance to store.
            
        Returns:
            Dictionary containing the inserted opportunity data.
        """
        data = opportunity.to_dict(exclude_none=True)
        
        response = self.client.table("arbitrage_opportunities").insert(data).execute()
        
        if response.data:
            return response.data[0] if isinstance(response.data, list) else response.data
        return {}

    def get_arbitrage_opportunities(
        self,
        market_pair_id: str,
        limit: int = 100
    ) -> List[ArbitrageOpportunity]:
        """Get arbitrage opportunities for a market pair.
        
        Args:
            market_pair_id: UUID of the market pair.
            limit: Maximum number of opportunities to return.
            
        Returns:
            List of ArbitrageOpportunity instances, ordered by timestamp descending.
        """
        response = self.client.table("arbitrage_opportunities") \
            .select("*") \
            .eq("market_pair_id", market_pair_id) \
            .order("timestamp", desc=True) \
            .limit(limit) \
            .execute()
        
        if response.data:
            return [ArbitrageOpportunity.from_dict(item) for item in response.data]
        return []

