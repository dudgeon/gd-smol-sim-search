"""Retry HTTP requests with exponential backoff."""

import random
import time


def retry_request(send, attempts: int = 5, base_delay: float = 0.5):
    """Call `send()` until it succeeds, sleeping with exponential backoff and jitter
    between failed attempts. Re-raise the last error when all attempts fail."""
    for attempt in range(attempts):
        try:
            return send()
        except ConnectionError:
            if attempt == attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay + random.uniform(0, delay / 2))
