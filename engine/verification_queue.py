"""Queue system for async LLM verification of market pairs."""

import logging
from typing import List, Dict, Optional, NamedTuple
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class VerificationTask:
    """Represents a market pair verification task."""
    market1_id: str
    market1_exchange: str
    market2_id: str
    market2_exchange: str
    similarity_score: float


class VerificationQueue:
    """Simple in-memory queue for LLM verification tasks."""
    
    def __init__(self):
        """Initialize the verification queue."""
        self._queue: List[VerificationTask] = []
        self._lock = Lock()
    
    def enqueue(
        self,
        market1_id: str,
        market1_exchange: str,
        market2_id: str,
        market2_exchange: str,
        similarity_score: float
    ) -> None:
        """Add a verification task to the queue.
        
        Args:
            market1_id: First market identifier.
            market1_exchange: First market exchange.
            market2_id: Second market identifier.
            market2_exchange: Second market exchange.
            similarity_score: Similarity score from vector search.
        """
        task = VerificationTask(
            market1_id=market1_id,
            market1_exchange=market1_exchange,
            market2_id=market2_id,
            market2_exchange=market2_exchange,
            similarity_score=similarity_score
        )
        
        with self._lock:
            self._queue.append(task)
        
        logger.debug(
            f"Enqueued verification task: {market1_id} ({market1_exchange}) vs "
            f"{market2_id} ({market2_exchange}), score: {similarity_score}"
        )
    
    def dequeue(self) -> Optional[VerificationTask]:
        """Remove and return the next task from the queue.
        
        Returns:
            VerificationTask if queue is not empty, None otherwise.
        """
        with self._lock:
            if self._queue:
                return self._queue.pop(0)
            return None
    
    def size(self) -> int:
        """Get the current queue size.
        
        Returns:
            Number of tasks in the queue.
        """
        with self._lock:
            return len(self._queue)
    
    def clear(self) -> None:
        """Clear all tasks from the queue."""
        with self._lock:
            self._queue.clear()
        logger.debug("Cleared verification queue")
    
    def process_queue(
        self,
        db_client,
        similarity_service
    ) -> Dict[str, int]:
        """Process all queued verification tasks.
        
        Args:
            db_client: SupabaseClient instance.
            similarity_service: MarketSimilarityService instance.
            
        Returns:
            Dictionary with stats: {'processed': count, 'verified': count, 'failed': count}
        """
        stats = {
            'processed': 0,
            'verified': 0,
            'failed': 0
        }
        
        logger.info(f"Processing verification queue ({self.size()} tasks)...")
        
        while True:
            task = self.dequeue()
            if task is None:
                break
            
            try:
                # Fetch markets from database
                market1 = db_client.get_market(task.market1_id, task.market1_exchange)
                market2 = db_client.get_market(task.market2_id, task.market2_exchange)
                
                if not market1 or not market2:
                    logger.warning(
                        f"Could not find markets for verification: "
                        f"{task.market1_id} or {task.market2_id}"
                    )
                    stats['failed'] += 1
                    continue
                
                # Verify and create pair
                pair = similarity_service.verify_and_create_pair(
                    market1,
                    market2,
                    task.similarity_score
                )
                
                if pair:
                    stats['verified'] += 1
                else:
                    stats['failed'] += 1
                
                stats['processed'] += 1
                
            except Exception as e:
                logger.error(
                    f"Error processing verification task: {e}",
                    exc_info=True
                )
                stats['failed'] += 1
                stats['processed'] += 1
        
        logger.info(
            f"Verification queue processing complete: "
            f"{stats['processed']} processed, {stats['verified']} verified, {stats['failed']} failed"
        )
        
        return stats

