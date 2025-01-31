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

"""
This is an addon for usdb_syncer that splits the audio of a song into vocals and instrumental using a remote server. This allows weaker machines to offload the processing to a more powerful server.

THIS ADDON IS EXPERIMENTAL. KEEP BACKUPS OF YOUR FILES. USE AT YOUR OWN RISK.

Usage requires a config file. Since usdb_syncer currently does not allow this explicitly, we just use the data directory of usdb_syncer. On a windows machine, this would be `%LOCALAPPDATA%/usdb_syncer/addon_config/config.txt`.
usdb_syncer does not allow us to have external dependancies, so the config file is a simple key=value file. The following keys are required:
- SERVER_URI: The URI of the server to send the audio to. This should be the base URI, e.g. `http://localhost:5000`.

The server is expected to have the following endpoints:
- POST /split: Accepts a file named "audio" and returns a UUID. The server should start processing the file in the background.
- GET /status: Accepts a query parameter "uuid" and returns the status of the processing. The status can be one of "NONE", "PENDING", "PROCESSING", "FINISHED", "ERROR".
- GET /results/vocals: Accepts a query parameter "uuid" and returns the vocals file if it is finished.
- GET /results/instrumental: Accepts a query parameter "uuid" and returns the instrumental file if it is finished.
- POST /cleanup: Accepts a query parameter "uuid" and cleans up the files associated with the UUID.
- POST /cleanupall: Cleans up all files on the server.
"""

from dataclasses import dataclass
from functools import wraps
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urljoin

import appdirs
import requests
import usdb_syncer.logger as usdb_logger
from usdb_syncer import hooks, usdb_song

NOTE_LINE_PREFIXES = frozenset([":", "*", "-", "R", "G", "F", "P1", "P2"])
NECCESARY_CONFIG_KEYS = ["SERVER_URI"]

@dataclass
class ServerConfig:
    """Configuration for the server."""
    base_uri: str
    demucs_model: Optional[str] = None


class DownloadError(Exception):
    """Error raised when a download fails."""
    pass


class AddonLogger(logging.LoggerAdapter):
    """Logger wrapper for general addon logs."""

    def __init__(self, addon_name: str, logger_: Any, extra: Any = ...) -> None:
        super().__init__(logger_, extra)
        self.addon_name = addon_name.upper()

    def process(self, msg: str, kwargs: Any) -> Any:
        return f"[{self.addon_name}]: {msg}", kwargs


def load_config(config_file: Path, log: AddonLogger) -> ServerConfig:
    """
    Load the server configuration from a file
    """
    if not config_file.exists():
        log.error(f"Config file {config_file} not found.")
        raise FileNotFoundError(f"Config file {config_file} not found.")
    
    config_data = {}
    for line in config_file.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=")
            config_data[key.strip().upper()] = value.strip()
    
    # Check if all required keys are present
    for key in NECCESARY_CONFIG_KEYS:
        if key not in config_data:
            log.error(f"Key {key} not found in config file.")
            raise KeyError(f"Key {key} not found in config file.")
    
    return ServerConfig(
        base_uri=config_data["SERVER_URI"],
        demucs_model=config_data.get("DEMUCS_MODEL", None)
    )


def initialize_addon() -> None:
    """
    Initialize the addon by loading configs and subscribing to events
    """
    addon_logger = AddonLogger("ussplitter", usdb_logger.logger)
    addon_logger.debug("Initializing ussplitter addon.")


    CONFIG_DIR = Path(appdirs.user_data_dir("usdb_syncer", "bohning", roaming=False)).joinpath("addon_config")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    addon_logger.debug(f'Using config directory "{CONFIG_DIR}".')

    config_file = CONFIG_DIR.joinpath("ussplitter.txt")

    try:
        global SERVER_CONFIG
        SERVER_CONFIG = load_config(config_file, addon_logger)
        addon_logger.debug("Loaded config file.")
    except (FileNotFoundError, KeyError):
        addon_logger.error("Failed to load config file. Addon will now exit.")
        return

    hooks.SongLoaderDidFinish.subscribe(on_download_finished)
    addon_logger.debug('Subscribed to "SongLoaderDidFinish" event.')


def write_song_tags(
    song_txt: Path, vocals: str, instrumental: str, songlogger: usdb_logger.Log
) -> bool:
    """
    Write the #VOCALS and #INSTRUMENTAL tags to the song file
    """

    song: list[str] = []
    tags_added = False


    songlogger.debug(f"Reading {song_txt} to add tags.")
    file_content = song_txt.read_text(encoding="utf-8").splitlines()

    for line in file_content:
        if not tags_added and not line.strip():
            continue
        if not tags_added and not any(line.startswith(note) for note in NOTE_LINE_PREFIXES):
            # We've reached the lyrics. Now insert the #VOCALS and #INSTRUMENTAL tags above
            song.extend([
                f"#VOCALS:{vocals}",
                f"#INSTRUMENTAL:{instrumental}",
            ])
            tags_added = True
        song.append(line)

    if tags_added:
        songlogger.debug(f"Writing tags to {song_txt}.")
        song_txt.write_text("\n".join(song) + "\n", encoding="utf-8")
        return True

    songlogger.error(f"Failed to add tags to {song_txt}.")
    return False


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
                except Exception:
                    attempts -= 1
                    if attempts == 0:
                        raise DownloadError()
                    time.sleep(delay)
            return None
        return wrapper
    return decorator


@retry_operation(retries=3, delay=5)
def download_file_from_server(
    base_url: str,
    endpoint: str,
    params: dict,
    destination: Path,
    logger: usdb_logger.Log,
) -> bool:
    """
    Download a file from a server
    """
    with requests.get(urljoin(base_url, endpoint), params=params, stream=True) as response:
        response.raise_for_status()
        logger.debug(f"Got response {response.status_code} from server downloading {endpoint}.")
        destination.write_bytes(response.content)


def on_download_finished(song: usdb_song.UsdbSong) -> None:
    # Create a custom logger for the song to match usdb_syncer's logging format
    # {date} {time} {level} {song_id} {message}
    song_logger = usdb_logger.song_logger(song.song_id)
    song_logger.debug(f"Addon {__name__} called.")

    if not song.sync_meta:
        song_logger.error("Missing sync_meta. This should never happen.")
        return
    if not song.sync_meta.txt:
        song_logger.error("Missing txt file. Skipping splitting.")
        return
    if not song.sync_meta.audio:
        song_logger.error("Missing audio file. Skipping splitting.")
        return

    song_folder: Path = song.sync_meta.path.parent
    song_mp3 = song_folder.joinpath(song.sync_meta.audio.fname)

    # Get the model to use for splitting. If not provided, use None and let the server decide on the default.
    model = SERVER_CONFIG.demucs_model
    song_logger.debug(f"Using model {model} for splitting.")

    # Send the file to the server
    try:
        response = requests.post(
            urljoin(SERVER_CONFIG.base_uri, "/split"),
            params={"model": model},
            files={"audio": open(song_mp3, "rb")},
            timeout=2,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as e:
        song_logger.debug(e)
        song_logger.error(
            "Timeout while sending file to server. Check if server is running"
        )
        return
    except requests.exceptions.HTTPError as e:
        song_logger.debug(e)
        song_logger.error("Failed to send file to server.")
        return
    except requests.exceptions.RequestException as e:
        song_logger.debug(e)
        song_logger.error("Failed to send file to server.")
        return

    uuid = response.text
    if not uuid:
        song_logger.error("Server returned an empty uuid.")
        return

    song_logger.info(f"Sent file to server for split. Got uuid {uuid}.")

    # Splitting will take some time.
    time.sleep(15)

    error_retry = 5

    while True:
        if error_retry == 0:
            song_logger.error("Too many retries. Giving up.")
        time.sleep(5)
        try:
            response = requests.get(
                urljoin(SERVER_CONFIG.base_uri, "/status"), params={"uuid": uuid}
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            song_logger.debug(e)
            song_logger.error(
                "Failed to get status from server. Retrying in 5 seconds."
            )
            error_retry -= 1
            continue

        status = response.text
        if not status:
            song_logger.error("Server returned an empty status.")
            return

        if status == "NONE":
            song_logger.error(
                "An internal error occured while splitting. Server returned NONE status."
            )
            return
        elif status == "PENDING":
            pass
        elif status == "PROCESSING":
            pass
        elif status == "FINISHED":
            break
        elif status == "ERROR":
            song_logger.error(
                "An error occured while splitting. Server returned ERROR status."
            )
            return

    vocals_dest_path = song_folder.joinpath(f"{song_mp3.stem} [VOC].mp3")
    instrumental_dest_path = song_folder.joinpath(f"{song_mp3.stem} [INSTR].mp3")

    download_file_from_server(
        base_url=SERVER_CONFIG.base_uri,
        endpoint="/result/vocals",
        params={"uuid": uuid},
        destination=vocals_dest_path,
        logger=song_logger,
    )

    download_file_from_server(
        base_url=SERVER_CONFIG.base_uri,
        endpoint="/result/instrumental",
        params={"uuid": uuid},
        destination=instrumental_dest_path,
        logger=song_logger,
    )

    # Write the tags to the song file
    song_txt = song_folder.joinpath(song.sync_meta.txt.fname)
    write_song_tags(
        song_txt, vocals_dest_path.name, instrumental_dest_path.name, song_logger
    )

    try:
        # Cleanup on server
        response = requests.post(
            urljoin(SERVER_CONFIG.base_uri, "/cleanup"), params={"uuid": uuid}
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        song_logger.debug(e)
        song_logger.error("Failed to cleanup on server.")
        return

    song_logger.info("Split finished.")


initialize_addon()
