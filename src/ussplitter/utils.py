import time
from functools import wraps
from typing import Callable, cast

from PySide6.QtWidgets import QApplication
from usdb_syncer.gui.mw import MainWindow


def get_main_window() -> MainWindow:
    """
    Get the main window of the application.
    """
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("No application instance found.")
    for widget in cast(QApplication, app).topLevelWidgets():
        if isinstance(widget, MainWindow):
            return widget
    raise RuntimeError("No main window found.")


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
                        raise RuntimeError() from e
                    time.sleep(delay)
            return None

        return wrapper

    return decorator
