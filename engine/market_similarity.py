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
    
    async def process_new_market(self, market: DatabaseMarket) -> Optional[List[Dict[str, any]]]:
        """Process a newly added market: embed it and search for similar markets (async).
        
        Args:
            market: DatabaseMarket instance that was just added to the database.
            
        Returns:
            List of candidate matches (dicts with market_id, exchange, score) if found,
            None otherwise. Note: LLM verification is queued asynchronously.
        """
        logger.info(f"[SIMILARITY] Processing new market: {market.market_id} ({market.exchange})")
        
        if not market.id:
            logger.warning(f"Market {market.market_id} has no database ID, skipping similarity processing")
            return None
        
        try:
            # Check if market already has embedding (avoid duplicate work)
            has_embedding = await self.vector_store.has_embedding(market)
            if has_embedding:
                logger.info(f"[SIMILARITY] Market {market.market_id} already has embedding, skipping generation")
            else:
                logger.info(f"[SIMILARITY] Generating embedding for {market.market_id}...")
                # Generate embedding
                embedding = await self.vector_store.embed_market(market)
                
                # Upsert to vector store
                logger.info(f"[SIMILARITY] Storing embedding for {market.market_id}...")
                await self.vector_store.upsert_market(market, embedding)
            
            # Search for similar markets from opposing exchange
            # Only need top_k=1 since there's at most one identical pair
            logger.info(f"[SIMILARITY] Searching for similar markets to {market.market_id} "
                       f"(threshold: {self.similarity_threshold}, top_k=1)...")
            candidates = await self.vector_store.search_similar_markets(
                market,
                top_k=1,
                threshold=self.similarity_threshold
            )
            
            # Process candidate (top_k=1, so at most one candidate)
            if candidates:
                candidate = candidates[0]  # Only one candidate since top_k=1
                score = candidate['score']
                
                # Only run LLM if similarity > 0.8 (threshold)
                if score > self.similarity_threshold:
                    logger.info(
                        f"[SIMILARITY] ✓ Found candidate match for {market.market_id}: "
                        f"{candidate['market_id']} ({candidate['exchange']}), "
                        f"score: {score:.4f} (above threshold {self.similarity_threshold})"
                    )
                    
                    # Queue LLM verification if enabled
                    if EngineConfig.LLM_VERIFICATION_ENABLED:
                        logger.info(f"[SIMILARITY] Queuing candidate for LLM verification...")
                        self.verification_queue.enqueue(
                            market1_id=market.market_id,
                            market1_exchange=market.exchange,
                            market2_id=candidate['market_id'],
                            market2_exchange=candidate['exchange'],
                            similarity_score=score
                        )
                        logger.info(f"[SIMILARITY] ✓ Queued verification task")
                    else:
                        logger.info(f"[SIMILARITY] LLM verification is disabled, skipping queue")
                    
                    return candidates
                else:
                    logger.debug(
                        f"[SIMILARITY] Candidate found but score {score:.4f} "
                        f"is below threshold {self.similarity_threshold}, skipping LLM verification"
                    )
                    return None
            else:
                logger.info(f"[SIMILARITY] No similar markets found for {market.market_id} ({market.exchange}) "
                          f"at threshold {self.similarity_threshold}")
                return None
            
        except Exception as e:
            logger.error(
                f"[SIMILARITY] ✗ Error processing new market {market.market_id}: {e}",
                exc_info=True
            )
            raise SimilarityError(f"Failed to process new market: {str(e)}") from e
    
    async def verify_and_create_pair(
        self,
        market1: DatabaseMarket,
        market2: DatabaseMarket,
        similarity_score: float
    ) -> Optional[MarketPair]:
        """Verify if two markets are identical using LLM and create pair if verified (async).
        
        Args:
            market1: First market.
            market2: Second market.
            similarity_score: Similarity score from vector search.
            
        Returns:
            MarketPair instance if verified, None otherwise.
        """
        logger.info(f"[VERIFY] Verifying pair: {market1.market_id} ({market1.exchange}) "
                   f"<-> {market2.market_id} ({market2.exchange}), similarity: {similarity_score:.4f}")
        
        # Check if pair already exists
        existing_pairs = self.db_client.get_market_pairs_by_market(market1.market_id, market1.exchange)
        for pair in existing_pairs:
            if (pair.market_1_id == market1.id and pair.market_2_id == market2.id) or \
               (pair.market_1_id == market2.id and pair.market_2_id == market1.id):
                logger.info(f"[VERIFY] Pair already exists for {market1.market_id} and {market2.market_id}, skipping")
                return pair
        
        try:
            logger.info(f"[VERIFY] Calling LLM to verify if markets are identical...")
            # Verify with LLM
            verification_result = await self.llm_verifier.verify_markets_identical(market1, market2)
            
            is_identical = verification_result.get('is_identical', False)
            confidence = verification_result.get('confidence', 0.0)
            reasoning = verification_result.get('reasoning', '')
            
            logger.info(f"[VERIFY] LLM result: is_identical={is_identical}, confidence={confidence:.4f}")
            if reasoning:
                logger.info(f"[VERIFY] LLM reasoning: {reasoning}")
            
            if is_identical:
                # Create market pair
                try:
                    logger.info(f"[VERIFY] Creating market pair in database...")
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
                        f"[VERIFY] ✓ Created verified market pair: {market1.market_id} ({market1.exchange}) "
                        f"<-> {market2.market_id} ({market2.exchange}), "
                        f"similarity: {similarity_score:.4f}, confidence: {confidence:.4f}"
                    )
                    
                    return pair
                    
                except Exception as e:
                    logger.error(
                        f"[VERIFY] ✗ Failed to create market pair: {e}",
                        exc_info=True
                    )
                    return None
            else:
                logger.info(
                    f"[VERIFY] Markets are NOT identical: {market1.market_id} vs {market2.market_id}, "
                    f"confidence: {confidence:.4f} (rejected by LLM despite similarity score {similarity_score:.4f})"
                )
                return None
                
        except Exception as e:
            logger.error(
                f"[VERIFY] ✗ Error verifying markets {market1.market_id} and {market2.market_id}: {e}",
                exc_info=True
            )
            raise SimilarityError(f"Failed to verify markets: {str(e)}") from e
    
    async def update_market_embedding(self, market: DatabaseMarket) -> None:
        """Update a market's embedding when market data changes (async).
        
        Args:
            market: DatabaseMarket instance with updated data.
        """
        if not market.id:
            logger.warning(f"Market {market.market_id} has no database ID, skipping embedding update")
            return
        
        try:
            embedding = await self.vector_store.embed_market(market)
            await self.vector_store.update_market(market, embedding)
            logger.debug(f"Updated embedding for market {market.market_id} ({market.exchange})")
        except Exception as e:
            logger.error(
                f"Error updating embedding for market {market.market_id}: {e}",
                exc_info=True
            )
            raise SimilarityError(f"Failed to update market embedding: {str(e)}") from e

