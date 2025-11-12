"""Queue system for async LLM verification of market pairs."""

import asyncio
import logging
from typing import List, Dict, Optional, NamedTuple
from dataclasses import dataclass
from threading import Lock

from .config import EngineConfig

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
            f"[QUEUE] Enqueued verification task: {market1_id} ({market1_exchange}) vs "
            f"{market2_id} ({market2_exchange}), score: {similarity_score:.4f} "
            f"(queue size: {len(self._queue)})"
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
    
    async def process_queue(
        self,
        db_client,
        similarity_service
    ) -> Dict[str, int]:
        """Process all queued verification tasks in parallel batches (async).
        
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
        
        queue_size = self.size()
        logger.info(f"[QUEUE] Processing verification queue ({queue_size} tasks) in parallel batches...")
        
        if queue_size == 0:
            logger.info(f"[QUEUE] Queue is empty, nothing to process")
            return stats
        
        # Get all tasks at once
        tasks = []
        while True:
            task = self.dequeue()
            if task is None:
                break
            tasks.append(task)
        
        batch_size = EngineConfig.ASYNC_VERIFICATION_BATCH_SIZE
        total_batches = (len(tasks) + batch_size - 1) // batch_size
        
        logger.info(f"[QUEUE] Processing {len(tasks)} tasks in {total_batches} batches of {batch_size}")
        
        async def process_single_task(task: VerificationTask, task_idx: int) -> Dict[str, int]:
            """Process a single verification task."""
            task_stats = {'processed': 0, 'verified': 0, 'failed': 0}
            
            try:
                # Fetch markets from database
                logger.debug(f"[QUEUE] Task {task_idx+1}: Fetching markets from database...")
                market1 = db_client.get_market(task.market1_id, task.market1_exchange)
                market2 = db_client.get_market(task.market2_id, task.market2_exchange)
                
                if not market1 or not market2:
                    logger.warning(
                        f"[QUEUE] ✗ Task {task_idx+1}: Could not find markets for verification: "
                        f"{task.market1_id} or {task.market2_id}"
                    )
                    task_stats['failed'] = 1
                    task_stats['processed'] = 1
                    return task_stats
                
                logger.debug(f"[QUEUE] Task {task_idx+1}: Found both markets, verifying...")
                # Verify and create pair (async)
                pair = await similarity_service.verify_and_create_pair(
                    market1,
                    market2,
                    task.similarity_score
                )
                
                if pair:
                    task_stats['verified'] = 1
                    logger.info(f"[QUEUE] ✓ Task {task_idx+1} verified and pair created")
                else:
                    task_stats['failed'] = 1
                    logger.info(f"[QUEUE] ✗ Task {task_idx+1} not verified (markets not identical)")
                
                task_stats['processed'] = 1
                
            except Exception as e:
                logger.error(
                    f"[QUEUE] ✗ Error processing verification task {task_idx+1}: {e}",
                    exc_info=True
                )
                task_stats['failed'] = 1
                task_stats['processed'] = 1
            
            return task_stats
        
        # Process tasks in batches
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(tasks))
            batch = tasks[start_idx:end_idx]
            
            logger.info(f"[QUEUE] Processing batch {batch_idx+1}/{total_batches} ({len(batch)} tasks)...")
            
            # Process batch in parallel
            batch_results = await asyncio.gather(
                *[process_single_task(task, start_idx + i) for i, task in enumerate(batch)],
                return_exceptions=True
            )
            
            # Aggregate stats
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"[QUEUE] Batch task raised exception: {result}", exc_info=True)
                    stats['failed'] += 1
                    stats['processed'] += 1
                else:
                    stats['processed'] += result.get('processed', 0)
                    stats['verified'] += result.get('verified', 0)
                    stats['failed'] += result.get('failed', 0)
            
            logger.info(
                f"[QUEUE] Batch {batch_idx+1}/{total_batches} complete: "
                f"{stats['processed']} processed, {stats['verified']} verified, {stats['failed']} failed"
            )
        
        logger.info(
            f"[QUEUE] ✓ Verification queue processing complete: "
            f"{stats['processed']} processed, {stats['verified']} verified, {stats['failed']} failed"
        )
        
        return stats

