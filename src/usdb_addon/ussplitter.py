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

import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import appdirs
import requests
import usdb_syncer.logger as usdb_logger
from usdb_syncer import hooks, usdb_song

# This is somewhat hacky, but usdb_syncer doesn't expose a config directory
CONFIG_DIR = Path(
    appdirs.user_data_dir(appname="usdb_syncer", appauthor="bohning", roaming=False)
).joinpath("addon_config")
CONFIGS: dict[str, str] = {}
NECCESARY_CONFIG_KEYS = ["SERVER_URI"]

logger = usdb_logger.logger


class AddonLogger(logging.LoggerAdapter):
    """Logger wrapper for general addon logs."""

    def __init__(self, addon_name: str, logger_: Any, extra: Any = ...) -> None:
        super().__init__(logger_, extra)
        self.addon_name = addon_name.upper()

    def process(self, msg: str, kwargs: Any) -> Any:
        return f"[{self.addon_name}]: {msg}", kwargs


def initialize_addon() -> None:
    """
    Initialize the addon by loading configs and subscribing to events
    """
    addon_logger = AddonLogger("ussplitter", logger)

    addon_logger.debug("Initializing ussplitter addon.")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    addon_logger.debug(f'Using config directory "{CONFIG_DIR}".')

    config_file = CONFIG_DIR.joinpath("ussplitter.txt")
    if not config_file.exists():
        addon_logger.error(
            f'Config file not found. Please create a config file at "{config_file}".'
        )
        return

    with open(config_file, "r") as f:
        configs_list = f.readlines()

    for config in configs_list:
        key, value = config.split("=")
        CONFIGS[key.strip()] = value.strip()

    addon_logger.debug(f"Loaded config successfully: {CONFIGS}")

    for key in NECCESARY_CONFIG_KEYS:
        if key not in CONFIGS:
            addon_logger.error(
                f"{key} not found in config file, but it is required. Addon will now exit."
            )
            return
    addon_logger.debug("All required config keys found.")

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

    note_lines = [
        ":",
        "*",
        "-",
        "R",
        "G",
        "F",
        "P1",
        "P2",
    ]  # Lines that start with these strings are not attributes.

    songlogger.debug(f"Reading {song_txt} to add tags.")
    with open(song_txt, "r", encoding="utf-8") as f:
        for line in f.readlines():
            if not tags_added and not any(line.startswith(note) for note in note_lines):
                # We've reached the lyrics. Now insert the #VOCALS and #INSTRUMENTAL tags above
                song.append(f"#VOCALS:{vocals}\n")
                song.append(f"#INSTRUMENTAL:{instrumental}\n")
                tags_added = True
            song.append(line)

    if tags_added:
        songlogger.debug(f"Writing tags to {song_txt}.")
        with open(song_txt, "w", encoding="utf-8") as f:
            f.writelines(song)
    else:
        songlogger.error(f"Failed to add tags to {song_txt}.")

    return tags_added


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
    response = requests.get(urljoin(base_url, endpoint), params=params)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.debug(e)
        logger.error(f"Failed to download {endpoint}.")
        return False

    try:
        with open(destination, "wb") as f:
            f.write(response.content)
    except Exception as e:
        logger.debug(e)
        logger.error(
            f"Failed to write {endpoint} to disk. This is probably because of an incorrect path."
        )
        return False

    logger.debug(f"Downloaded {endpoint} to {destination}.")
    return True


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
    model = CONFIGS.get("DEMUCS_MODEL", None)
    song_logger.debug(f"Using model {model} for splitting.")

    # Send the file to the server
    try:
        response = requests.post(
            urljoin(CONFIGS["SERVER_URI"], "/split"),
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
                urljoin(CONFIGS["SERVER_URI"], "/status"), params={"uuid": uuid}
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

    vocals_downloaded = False
    instrumental_downloaded = False
    error_retry = 5
    while not vocals_downloaded or not instrumental_downloaded:
        if error_retry <= 0:
            song_logger.error("Too many retries downloading mp3 files. Giving up.")
            break

        if not vocals_downloaded:
            song_logger.debug("Trying to download vocals.")
            vocals_downloaded = download_file_from_server(
                base_url=CONFIGS["SERVER_URI"],
                endpoint="/result/vocals",
                params={"uuid": uuid},
                destination=vocals_dest_path,
                logger=song_logger,
            )
            if not vocals_downloaded:
                error_retry -= 1

        if not instrumental_downloaded:
            song_logger.debug("Trying to download instrumental.")
            instrumental_downloaded = download_file_from_server(
                base_url=CONFIGS["SERVER_URI"],
                endpoint="/result/instrumental",
                params={"uuid": uuid},
                destination=instrumental_dest_path,
                logger=song_logger,
            )
            if not instrumental_downloaded:
                error_retry -= 1

        time.sleep(5)

    # Write the tags to the song file
    song_txt = song_folder.joinpath(song.sync_meta.txt.fname)
    write_song_tags(
        song_txt, vocals_dest_path.name, instrumental_dest_path.name, song_logger
    )

    try:
        # Cleanup on server
        response = requests.post(
            urljoin(CONFIGS["SERVER_URI"], "/cleanup"), params={"uuid": uuid}
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        song_logger.debug(e)
        song_logger.error("Failed to cleanup on server.")
        return

    song_logger.info("Split finished.")


initialize_addon()
