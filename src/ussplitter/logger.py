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

import logging
from typing import Any

from usdb_syncer.logger import SongLogger
from usdb_syncer.song_loader import SongId


class AddonLogger(logging.LoggerAdapter):
    """Logger wrapper for addon logs. Logs are prefixed with the addon name."""

    def __init__(self, addon_name: str, logger_: Any, extra: Any = ...) -> None:
        super().__init__(logger_, extra)
        self.addon_name = addon_name.upper()

    def process(self, msg: str, kwargs: Any) -> Any:
        return f"[{self.addon_name}]: {msg}", kwargs


class AddonSongLogger(SongLogger):
    """Logger wrapper for addon song logs. Logs are prefixed with the song ID and
    addon name."""

    def __init__(
        self, addon_name: str, song_id: SongId, logger_: Any, extra: Any = ...
    ) -> None:
        super().__init__(song_id, logger_, extra)
        self.addon_name = addon_name.upper()

    def process(self, msg: str, kwargs: Any) -> Any:
        return f"#{self.song_id} [{self.addon_name}]: {msg}", kwargs

    @classmethod
    def from_song_logger(
        cls, addon_name: str, song_logger: SongLogger
    ) -> "AddonSongLogger":
        return cls(
            addon_name, song_logger.song_id, song_logger.logger, song_logger.extra
        )
