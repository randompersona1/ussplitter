import logging
import time
from functools import wraps
from typing import Callable


class DownloadError(Exception):
    """Error raised when a download fails."""

    def __init__(self):
        super().__init__("Download failed.")


def catch_and_log_exception(logger: logging.Logger) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"An unexpected error in the USSplitter addon occurred in {func.__name__}: {e}"
                )

        return wrapper

    return decorator


def retry_operation(retries: int, delay: int):
    """
    Decorator for retrying an operation if it fails with delays.
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = retries
            while attempts > 0:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts -= 1
                    if attempts == 0:
                        raise DownloadError() from e
                    time.sleep(delay)
            return None

        return wrapper

    return decorator
