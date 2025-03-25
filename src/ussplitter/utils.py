# Copyright (C) 2025 randompersona1
#
# USSplitter is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# USSplitter is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with USSplitter. If not, see <https://www.gnu.org/licenses/>.

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


def retry_operation(retries: int, delay: int, exception: RuntimeError):
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
                        raise exception() from e
                    time.sleep(delay)
            return None

        return wrapper

    return decorator
