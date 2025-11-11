"""Market similarity service for identifying matching markets across exchanges."""

import logging
from typing import List, Dict, Optional
from db.models import DatabaseMarket, MarketPair
from db.client import SupabaseClient
from vector_db.client import SupabaseVectorStore
from .llm_verifier import LLMVerifier
from .verification_queue import VerificationQueue
from .config import EngineConfig
from .errors import SimilarityError

logger = logging.getLogger(__name__)


class MarketSimilarityService:
    """Service for identifying and verifying matching markets across exchanges."""
    
    def __init__(
        self,
        vector_store: SupabaseVectorStore,
        llm_verifier: LLMVerifier,
        db_client: SupabaseClient,
        verification_queue: Optional[VerificationQueue] = None,
        similarity_threshold: Optional[float] = None
    ):
        """Initialize the market similarity service.
        
        Args:
            vector_store: SupabaseVectorStore instance.
            llm_verifier: LLMVerifier instance.
            db_client: SupabaseClient instance.
            verification_queue: Optional VerificationQueue instance. If None, creates a new one.
            similarity_threshold: Similarity score threshold. If None, uses config default.
        """
        self.vector_store = vector_store
        self.llm_verifier = llm_verifier
        self.db_client = db_client
        self.verification_queue = verification_queue or VerificationQueue()
        self.similarity_threshold = similarity_threshold or EngineConfig.SIMILARITY_THRESHOLD
    
    def process_new_market(self, market: DatabaseMarket) -> Optional[List[Dict[str, any]]]:
        """Process a newly added market: embed it and search for similar markets.
        
        Args:
            market: DatabaseMarket instance that was just added to the database.
            
        Returns:
            List of candidate matches (dicts with market_id, exchange, score) if found,
            None otherwise. Note: LLM verification is queued asynchronously.
        """
        if not market.id:
            logger.warning(f"Market {market.market_id} has no database ID, skipping similarity processing")
            return None
        
        try:
            # Generate embedding
            embedding = self.vector_store.embed_market(market)
            
            # Upsert to Pinecone
            self.vector_store.upsert_market(market, embedding)
            
            # Search for similar markets from opposing exchange
            candidates = self.vector_store.search_similar_markets(
                market,
                top_k=5,
                threshold=self.similarity_threshold
            )
            
            if not candidates:
                logger.debug(f"No similar markets found for {market.market_id} ({market.exchange})")
                return None
            
            logger.info(
                f"Found {len(candidates)} candidate matches for {market.market_id} ({market.exchange})"
            )
            
            # Queue LLM verification for candidates above threshold
            if EngineConfig.LLM_VERIFICATION_ENABLED:
                for candidate in candidates:
                    self.verification_queue.enqueue(
                        market1_id=market.market_id,
                        market1_exchange=market.exchange,
                        market2_id=candidate['market_id'],
                        market2_exchange=candidate['exchange'],
                        similarity_score=candidate['score']
                    )
            
            return candidates
            
        except Exception as e:
            logger.error(
                f"Error processing new market {market.market_id}: {e}",
                exc_info=True
            )
            raise SimilarityError(f"Failed to process new market: {str(e)}") from e
    
    def verify_and_create_pair(
        self,
        market1: DatabaseMarket,
        market2: DatabaseMarket,
        similarity_score: float
    ) -> Optional[MarketPair]:
        """Verify if two markets are identical using LLM and create pair if verified.
        
        Args:
            market1: First market.
            market2: Second market.
            similarity_score: Similarity score from vector search.
            
        Returns:
            MarketPair instance if verified, None otherwise.
        """
        # Check if pair already exists
        existing_pairs = self.db_client.get_market_pairs_by_market(market1.market_id, market1.exchange)
        for pair in existing_pairs:
            if (pair.market_1_id == market1.id and pair.market_2_id == market2.id) or \
               (pair.market_1_id == market2.id and pair.market_2_id == market1.id):
                logger.debug(f"Pair already exists for {market1.market_id} and {market2.market_id}")
                return pair
        
        try:
            # Verify with LLM
            verification_result = self.llm_verifier.verify_markets_identical(market1, market2)
            
            is_identical = verification_result.get('is_identical', False)
            confidence = verification_result.get('confidence', 0.0)
            reasoning = verification_result.get('reasoning', '')
            
            if is_identical:
                # Create market pair
                try:
                    pair = MarketPair.from_markets(
                        market1,
                        market2,
                        similarity_score,
                        llm_verified=True,
                        llm_confidence=confidence
                    )
                    
                    # Store in database
                    result = self.db_client.upsert_market_pair(pair)
                    pair = MarketPair.from_dict(result)
                    
                    logger.info(
                        f"Created verified market pair: {market1.market_id} ({market1.exchange}) "
                        f"<-> {market2.market_id} ({market2.exchange}), "
                        f"similarity: {similarity_score:.3f}, confidence: {confidence:.3f}"
                    )
                    
                    if reasoning:
                        logger.debug(f"LLM reasoning: {reasoning}")
                    
                    return pair
                    
                except Exception as e:
                    logger.error(
                        f"Failed to create market pair: {e}",
                        exc_info=True
                    )
                    return None
            else:
                logger.debug(
                    f"LLM determined markets are not identical: {market1.market_id} vs {market2.market_id}, "
                    f"confidence: {confidence:.3f}"
                )
                if reasoning:
                    logger.debug(f"LLM reasoning: {reasoning}")
                return None
                
        except Exception as e:
            logger.error(
                f"Error verifying markets {market1.market_id} and {market2.market_id}: {e}",
                exc_info=True
            )
            raise SimilarityError(f"Failed to verify markets: {str(e)}") from e
    
    def update_market_embedding(self, market: DatabaseMarket) -> None:
        """Update a market's embedding in Pinecone when market data changes.
        
        Args:
            market: DatabaseMarket instance with updated data.
        """
        if not market.id:
            logger.warning(f"Market {market.market_id} has no database ID, skipping embedding update")
            return
        
        try:
            embedding = self.vector_store.embed_market(market)
            self.vector_store.update_market(market, embedding)
            logger.debug(f"Updated embedding for market {market.market_id} ({market.exchange})")
        except Exception as e:
            logger.error(
                f"Error updating embedding for market {market.market_id}: {e}",
                exc_info=True
            )
            raise SimilarityError(f"Failed to update market embedding: {str(e)}") from e

