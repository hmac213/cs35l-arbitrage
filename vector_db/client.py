"""Vector store client for market embeddings using pgvector in Supabase."""

import os
import asyncio
import logging
from typing import List, Dict, Optional, Any
from openai import AsyncOpenAI
import httpx

from db.models import DatabaseMarket
from db.client import SupabaseClient
from engine.config import EngineConfig
from engine.errors import VectorStoreError

logger = logging.getLogger(__name__)


class SupabaseVectorStore:
    """Vector store using pgvector in Supabase for market embeddings.
    
    Uses Supabase RPC calls to execute vector operations, so only requires
    the Supabase API key (no database password needed).
    """
    
    def __init__(
        self,
        db_client: SupabaseClient,
        embedding_model: Optional[str] = None
    ):
        """Initialize Supabase vector store.
        
        Args:
            db_client: SupabaseClient instance for database operations.
            embedding_model: OpenAI embedding model name. If None, reads from config.
        """
        self.db_client = db_client
        self.embedding_model = embedding_model or EngineConfig.EMBEDDING_MODEL
        
        # Initialize OpenAI async client for embeddings
        # Try EngineConfig first, then fall back to direct os.getenv() in case .env wasn't loaded when config was imported
        openai_api_key = EngineConfig.OPENAI_API_KEY or os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            raise VectorStoreError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        # Create async HTTP client for Supabase RPC calls
        self._async_http_client: Optional[httpx.AsyncClient] = None
        logger.info("Initialized Supabase vector store (using RPC calls, async)")
    
    async def _get_async_http_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client for Supabase RPC calls."""
        if self._async_http_client is None:
            # Construct base URL from Supabase URL
            base_url = f"{self.db_client.supabase_url}/rest/v1"
            self._async_http_client = httpx.AsyncClient(
                base_url=base_url,
                headers={
                    "apikey": self.db_client.supabase_key,
                    "Authorization": f"Bearer {self.db_client.supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation"
                },
                timeout=30.0
            )
        return self._async_http_client
    
    async def _close_async_client(self):
        """Close async HTTP client."""
        if self._async_http_client:
            await self._async_http_client.aclose()
            self._async_http_client = None
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI (async).
        
        Args:
            text: Text to embed.
            
        Returns:
            List of floats representing the embedding vector.
        """
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise VectorStoreError(f"Failed to generate embedding: {str(e)}") from e
    
    def _get_market_text(self, market: DatabaseMarket) -> str:
        """Get text representation of market for embedding.
        
        Combines market rules and name for embedding.
        
        Args:
            market: DatabaseMarket instance.
            
        Returns:
            Combined text string.
        """
        parts = []
        
        # Add name
        if market.name:
            parts.append(f"Market: {market.name}")
        
        # Add rules (most important)
        if market.rules:
            parts.append(f"Rules: {market.rules}")
        
        # Add description if available
        if market.description:
            parts.append(f"Description: {market.description}")
        
        # Add category if available
        if market.category:
            parts.append(f"Category: {market.category}")
        
        return "\n\n".join(parts)
    
    async def embed_market(self, market: DatabaseMarket) -> List[float]:
        """Generate embedding for a market (async).
        
        Args:
            market: DatabaseMarket instance.
            
        Returns:
            List of floats representing the embedding vector.
        """
        logger.debug(f"Generating embedding text for market {market.market_id} ({market.exchange})...")
        text = self._get_market_text(market)
        if not text.strip():
            raise VectorStoreError(f"Market {market.market_id} has no text to embed (no name or rules)")
        
        logger.debug(f"Embedding text length: {len(text)} characters")
        logger.debug(f"Calling OpenAI API to generate embedding (model: {self.embedding_model})...")
        embedding = await self._generate_embedding(text)
        logger.debug(f"Generated embedding vector, dimension: {len(embedding)}")
        return embedding
    
    async def has_embedding(self, market: DatabaseMarket) -> bool:
        """Check if a market already has an embedding in the database (async).
        
        Args:
            market: DatabaseMarket instance.
            
        Returns:
            True if market has an embedding, False otherwise.
        """
        if not market.id:
            return False
        
        try:
            # Use async HTTP client for query
            client = await self._get_async_http_client()
            url = "/markets"
            params = {"id": f"eq.{market.id}", "select": "embedding"}
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data and len(data) > 0:
                embedding = data[0].get('embedding')
                return embedding is not None
            return False
        except Exception as e:
            logger.warning(f"Failed to check embedding for market {market.market_id}: {e}")
            return False
    
    async def batch_has_embeddings(self, markets: List[DatabaseMarket]) -> Dict[str, bool]:
        """Batch check if markets have embeddings (async).
        
        Args:
            markets: List of DatabaseMarket instances.
            
        Returns:
            Dictionary mapping market_id to boolean (True if has embedding).
        """
        if not markets:
            return {}
        
        # Filter markets with IDs
        markets_with_ids = [m for m in markets if m.id]
        if not markets_with_ids:
            return {m.market_id: False for m in markets}
        
        try:
            # Build query with IN clause for batch check
            market_ids = [str(m.id) for m in markets_with_ids]
            client = await self._get_async_http_client()
            url = "/markets"
            # Use 'in' filter for multiple IDs (PostgREST format)
            params = {"id": f"in.({','.join(market_ids)})", "select": "id,embedding"}
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            # Create mapping of id -> has_embedding
            result = {}
            for row in data:
                market_id = row.get('id')
                has_embedding = row.get('embedding') is not None
                result[market_id] = has_embedding
            
            # Fill in False for markets not found
            market_id_to_market = {m.id: m.market_id for m in markets_with_ids}
            final_result = {}
            for market in markets:
                if market.id:
                    final_result[market.market_id] = result.get(market.id, False)
                else:
                    final_result[market.market_id] = False
            
            return final_result
        except Exception as e:
            logger.warning(f"Failed to batch check embeddings: {e}")
            # Fallback to False for all
            return {m.market_id: False for m in markets}
    
    async def upsert_market(self, market: DatabaseMarket, embedding: Optional[List[float]] = None) -> None:
        """Store or update a market embedding in Supabase using RPC (async).
        
        Args:
            market: DatabaseMarket instance.
            embedding: Pre-computed embedding. If None, will be generated.
        """
        if not market.id:
            raise VectorStoreError(f"Market {market.market_id} must have database ID (id field) before storing embedding")
        
        # Check if embedding already exists to avoid duplicate work
        if await self.has_embedding(market):
            logger.info(f"Market {market.market_id} ({market.exchange}) already has embedding, skipping upsert")
            return
        
        logger.info(f"Generating and storing embedding for market {market.market_id} ({market.exchange})...")
        
        if embedding is None:
            embedding = await self.embed_market(market)
        
        logger.debug(f"Generated embedding for {market.market_id} ({market.exchange}), length: {len(embedding)}")
        
        # Convert embedding to string format for RPC call
        # PostgreSQL vector type expects array format: [1.0,2.0,3.0]
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        try:
            # Call RPC function to update embedding using async HTTP client
            client = await self._get_async_http_client()
            url = "/rpc/update_market_embedding"
            payload = {
                'market_uuid': str(market.id),
                'embedding_vector': embedding_str
            }
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            logger.info(f"✓ Successfully stored embedding for market {market.market_id} ({market.exchange})")
        except Exception as e:
            logger.error(f"✗ Failed to upsert embedding for market {market.market_id}: {e}")
            raise VectorStoreError(f"Failed to upsert market embedding: {str(e)}") from e
    
    async def search_similar_markets(
        self,
        market: DatabaseMarket,
        top_k: int = 5,
        threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """Search for similar markets from the opposing exchange using cosine similarity (async).
        
        Args:
            market: DatabaseMarket instance to find matches for.
            top_k: Number of top results to return.
            threshold: Minimum similarity score threshold (cosine similarity, 0-1).
            
        Returns:
            List of dictionaries with keys: market_id, exchange, score, metadata
        """
        logger.info(f"Searching for similar markets to {market.market_id} ({market.exchange}), "
                   f"top_k={top_k}, threshold={threshold}")
        
        # Generate embedding for the query market
        try:
            embedding = await self.embed_market(market)
        except VectorStoreError:
            logger.warning(f"Cannot search for market {market.market_id}: no text to embed")
            return []
        
        # Determine opposing exchange
        opposing_exchange = "polymarket" if market.exchange == "kalshi" else "kalshi"
        logger.debug(f"Searching in opposing exchange: {opposing_exchange}")
        
        # Convert embedding to string format for RPC call
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        try:
            logger.debug(f"Calling RPC function 'search_similar_markets'...")
            # Call RPC function to search for similar markets using async HTTP client
            client = await self._get_async_http_client()
            url = "/rpc/search_similar_markets"
            payload = {
                'query_embedding': embedding_str,
                'opposing_exchange': opposing_exchange,
                'result_limit': top_k,
                'similarity_threshold': float(threshold)
            }
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Process results
            matches = []
            if data:
                logger.debug(f"RPC returned {len(data)} candidate matches")
                for idx, row in enumerate(data):
                    similarity_score = float(row.get('similarity', 0.0))
                    
                    match_info = {
                        'market_id': row.get('market_id', ''),
                        'exchange': row.get('exchange', ''),
                        'score': similarity_score,
                        'metadata': {
                            'id': str(row.get('id', '')),
                            'name': row.get('name', ''),
                            'rules': row.get('rules', ''),
                            'resolve_date': str(row.get('resolve_date', '')) if row.get('resolve_date') else '',
                            'category': row.get('category', ''),
                        }
                    }
                    matches.append(match_info)
                    
                    logger.info(f"  Match #{idx+1}: {match_info['market_id']} ({match_info['exchange']}) "
                               f"- similarity: {similarity_score:.4f}")
            else:
                logger.debug("RPC returned no matches")
            
            logger.info(f"Found {len(matches)} similar markets for {market.market_id} "
                       f"(threshold: {threshold})")
            
            return matches
            
        except Exception as e:
            logger.error(f"Failed to search for similar markets: {e}")
            raise VectorStoreError(f"Failed to search for similar markets: {str(e)}") from e
    
    def delete_market(self, market_id: str, exchange: str) -> None:
        """Remove a market's embedding from Supabase using RPC.
        
        Args:
            market_id: Market identifier.
            exchange: Exchange name.
        """
        try:
            # Get market from database to find its UUID
            market = self.db_client.get_market(market_id, exchange)
            if not market or not market.id:
                logger.warning(f"Market {market_id} ({exchange}) not found, cannot delete embedding")
                return
            
            # Call RPC function to delete embedding
            self.db_client.client.rpc(
                'delete_market_embedding',
                {'market_uuid': market.id}
            ).execute()
            
            logger.debug(f"Deleted embedding for market {market_id} ({exchange})")
        except Exception as e:
            # Don't raise error if market doesn't exist
            logger.warning(f"Failed to delete market embedding (may not exist): {str(e)}")
    
    async def update_market(self, market: DatabaseMarket, embedding: Optional[List[float]] = None) -> None:
        """Update an existing market's embedding in Supabase (async).
        
        Args:
            market: DatabaseMarket instance.
            embedding: Pre-computed embedding. If None, will be generated.
        """
        # Upsert is idempotent, so we can just call upsert
        await self.upsert_market(market, embedding)
