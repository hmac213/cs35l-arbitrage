"""Vector store client for market embeddings using pgvector in Supabase."""

import logging
from typing import List, Dict, Optional, Any
from openai import OpenAI

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
        
        # Initialize OpenAI client for embeddings
        openai_api_key = EngineConfig.OPENAI_API_KEY
        if not openai_api_key:
            raise VectorStoreError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.openai_client = OpenAI(api_key=openai_api_key)
        logger.info("Initialized Supabase vector store (using RPC calls)")
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI.
        
        Args:
            text: Text to embed.
            
        Returns:
            List of floats representing the embedding vector.
        """
        try:
            response = self.openai_client.embeddings.create(
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
    
    def embed_market(self, market: DatabaseMarket) -> List[float]:
        """Generate embedding for a market.
        
        Args:
            market: DatabaseMarket instance.
            
        Returns:
            List of floats representing the embedding vector.
        """
        text = self._get_market_text(market)
        if not text.strip():
            raise VectorStoreError(f"Market {market.market_id} has no text to embed (no name or rules)")
        
        return self._generate_embedding(text)
    
    def upsert_market(self, market: DatabaseMarket, embedding: Optional[List[float]] = None) -> None:
        """Store or update a market embedding in Supabase using RPC.
        
        Args:
            market: DatabaseMarket instance.
            embedding: Pre-computed embedding. If None, will be generated.
        """
        if not market.id:
            raise VectorStoreError(f"Market {market.market_id} must have database ID (id field) before storing embedding")
        
        if embedding is None:
            embedding = self.embed_market(market)
        
        # Convert embedding to string format for RPC call
        # PostgreSQL vector type expects array format: [1.0,2.0,3.0]
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        try:
            # Call RPC function to update embedding
            response = self.db_client.client.rpc(
                'update_market_embedding',
                {
                    'market_uuid': market.id,
                    'embedding_vector': embedding_str
                }
            ).execute()
            
            logger.debug(f"Upserted embedding for market {market.market_id} ({market.exchange})")
        except Exception as e:
            raise VectorStoreError(f"Failed to upsert market embedding: {str(e)}") from e
    
    def search_similar_markets(
        self,
        market: DatabaseMarket,
        top_k: int = 5,
        threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """Search for similar markets from the opposing exchange using cosine similarity.
        
        Args:
            market: DatabaseMarket instance to find matches for.
            top_k: Number of top results to return.
            threshold: Minimum similarity score threshold (cosine similarity, 0-1).
            
        Returns:
            List of dictionaries with keys: market_id, exchange, score, metadata
        """
        # Generate embedding for the query market
        try:
            embedding = self.embed_market(market)
        except VectorStoreError:
            logger.warning(f"Cannot search for market {market.market_id}: no text to embed")
            return []
        
        # Determine opposing exchange
        opposing_exchange = "polymarket" if market.exchange == "kalshi" else "kalshi"
        
        # Convert embedding to string format for RPC call
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        try:
            # Call RPC function to search for similar markets
            response = self.db_client.client.rpc(
                'search_similar_markets',
                {
                    'query_embedding': embedding_str,
                    'opposing_exchange': opposing_exchange,
                    'result_limit': top_k,
                    'similarity_threshold': threshold
                }
            ).execute()
            
            # Process results
            matches = []
            if response.data:
                for row in response.data:
                    similarity_score = float(row.get('similarity', 0.0))
                    
                    matches.append({
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
                    })
            
            logger.debug(
                f"Found {len(matches)} similar markets for {market.market_id} "
                f"(threshold: {threshold})"
            )
            
            return matches
            
        except Exception as e:
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
    
    def update_market(self, market: DatabaseMarket, embedding: Optional[List[float]] = None) -> None:
        """Update an existing market's embedding in Supabase.
        
        Args:
            market: DatabaseMarket instance.
            embedding: Pre-computed embedding. If None, will be generated.
        """
        # Upsert is idempotent, so we can just call upsert
        self.upsert_market(market, embedding)
