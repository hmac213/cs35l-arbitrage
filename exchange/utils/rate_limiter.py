"""Rate limiting utility for API requests."""

import time
from typing import Optional
from collections import deque
from threading import Lock


class RateLimiter:
    """Rate limiter to prevent hitting API rate limits.
    
    Tracks request timestamps and enforces minimum delays between requests.
    Supports exponential backoff on rate limit errors.
    """
    
    def __init__(
        self,
        min_delay: float = 0.1,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0
    ):
        """Initialize the rate limiter.
        
        Args:
            min_delay: Minimum delay between requests in seconds (default: 0.1).
            max_delay: Maximum delay between requests in seconds (default: 60.0).
            backoff_factor: Factor to multiply delay by on rate limit errors (default: 2.0).
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.current_delay = min_delay
        self.last_request_time = 0.0
        self.lock = Lock()
    
    def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limits.
        
        Calculates time since last request and waits if needed to maintain
        minimum delay between requests.
        """
        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.current_delay:
                sleep_time = self.current_delay - time_since_last
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
    
    def record_request(self) -> None:
        """Record that a request was made.
        
        Updates the last request time to current time.
        """
        with self.lock:
            self.last_request_time = time.time()
    
    def handle_rate_limit_error(self) -> None:
        """Handle a rate limit error by increasing delay.
        
        Increases the current delay using exponential backoff, up to max_delay.
        """
        with self.lock:
            self.current_delay = min(
                self.current_delay * self.backoff_factor,
                self.max_delay
            )
    
    def reset_delay(self) -> None:
        """Reset delay to minimum after successful requests.
        
        Gradually reduces delay back to minimum after rate limit errors.
        """
        with self.lock:
            if self.current_delay > self.min_delay:
                # Gradually reduce delay
                self.current_delay = max(
                    self.current_delay / self.backoff_factor,
                    self.min_delay
                )

