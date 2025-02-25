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

KEEP BACKUPS OF YOUR SONG FILES. USE AT YOUR OWN RISK.

The server is expected to have the following endpoints:
- POST /split: Accepts a file named "audio" and returns a UUID. The server should start processing the file in the background.
- GET /status: Accepts a query parameter "uuid" and returns the status of the processing. The status can be one of "NONE", "PENDING", "PROCESSING", "FINISHED", "ERROR".
- GET /results/vocals: Accepts a query parameter "uuid" and returns the vocals file if it is finished.
- GET /results/instrumental: Accepts a query parameter "uuid" and returns the instrumental file if it is finished.
- POST /cleanup: Accepts a query parameter "uuid" and cleans up the files associated with the UUID.
- POST /cleanupall: Cleans up all files on the server.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import usdb_syncer.logger as usdb_logger
from PySide6.QtWidgets import QApplication, QDialog, QWidget
from usdb_syncer import hooks, song_txt, usdb_song
from usdb_syncer.gui.mw import MainWindow

from ussplitter.forms.Settings import Ui_Dialog
from ussplitter.settings import DemucsModels, get_settings, set_settings
from ussplitter.utils import catch_and_log_exception, retry_operation

NOTE_LINE_PREFIXES = frozenset([":", "*", "-", "R", "G", "F", "P1", "P2"])
NECCESARY_CONFIG_KEYS = ["SERVER_URI"]


class AddonLogger(logging.LoggerAdapter):
    """Logger wrapper for general addon logs."""

    def __init__(self, addon_name: str, logger_: Any, extra: Any = ...) -> None:
        super().__init__(logger_, extra)
        self.addon_name = addon_name.upper()

    def process(self, msg: str, kwargs: Any) -> Any:
        return f"[{self.addon_name}]: {msg}", kwargs


class SettingsDialog(Ui_Dialog, QDialog):
    """Settings dialog for the addon."""

    def __init__(self, parent: QWidget, log: AddonLogger) -> None:
        self.log = log
        super().__init__(parent=parent)
        self.setupUi(self)
        self.setModal(True)
        self.setWindowTitle("USSplitter Settings")

        # populate the fields with the current settings
        settings = get_settings()
        self.lineEdit_server_uri.setText(settings.base_uri)
        self.lineEdit_server_uri.setPlaceholderText("http://localhost:5000")

        for model in DemucsModels:
            self.comboBox_model.addItem(model.value)
        self.comboBox_model.setCurrentText(settings.demucs_model.value)

    def accept(self) -> None:
        """Save the settings when the dialog is closed."""
        server_uri = self.lineEdit_server_uri.text().strip()
        if not server_uri:
            logging.error("Server URI is empty.")
            self.lineEdit_server_uri.setFocus()
            return

        settings = get_settings()
        settings.base_uri = server_uri
        demucs_model = self.comboBox_model.currentText().strip()
        settings.demucs_model = DemucsModels(demucs_model)
        set_settings(settings)
        self.log.debug("Saved settings.")
        super().accept()

    def reject(self) -> None:
        """Close the dialog without saving."""
        self.log.debug("Settings dialog closed.")
        super().reject()


@catch_and_log_exception(usdb_logger.logger)
def get_main_window() -> MainWindow:
    """Get the main window of usdb_syncer."""
    app = QApplication.instance()
    for widget in app.topLevelWidgets():  # type: ignore
        if isinstance(widget, MainWindow):
            return widget
    raise RuntimeError("MainWindow not found.")


@catch_and_log_exception(usdb_logger.logger)
def initialize_addon() -> None:
    """
    Initialize the addon by loading configs and subscribing to events
    """
    addon_logger = AddonLogger("ussplitter", usdb_logger.logger)
    addon_logger.debug("Initializing ussplitter addon.")

    try:
        main_window = get_main_window()
    except RuntimeError:
        addon_logger.error("Failed to get main window. Addon will now exit.")
        return

    # Add the settings dialog to the tools menu
    about_dialog = SettingsDialog(main_window, addon_logger)
    main_window.menu_tools.addSeparator()
    main_window.menu_tools.addAction("USSplitter Settings", about_dialog.show)

    hooks.SongLoaderDidFinish.subscribe(on_download_finished)
    addon_logger.debug('Subscribed to "SongLoaderDidFinish" event.')


@catch_and_log_exception(usdb_logger.logger)
def write_song_tags(
    txt_path: Path, vocals: str, instrumental: str, songlogger: usdb_logger.Log
) -> bool:
    """
    Write the #VOCALS and #INSTRUMENTAL tags to the song file
    """
    songlogger.debug(f"Reading {txt_path} to add tags.")

    try:
        song = song_txt.SongTxt.parse(txt_path.read_text(encoding="utf-8"), songlogger)
    except Exception as e:
        songlogger.error(f"Failed to parse song file: {e}")
        return False
    songlogger.debug("Parsed song file.")

    song.headers.vocals = vocals
    song.headers.instrumental = instrumental

    try:
        song.write_to_file(path=txt_path, encoding="utf-8", newline=os.linesep)
    except Exception as e:
        songlogger.error(f"Failed to write tags to song file: {e}")
        return False
    return True


@catch_and_log_exception(usdb_logger.logger)
@retry_operation(retries=3, delay=5)
def download_file_from_server(
    base_url: str,
    endpoint: str,
    params: dict,
    destination: Path,
    logger: usdb_logger.Log,
) -> None:
    """
    Download a file from a server
    """
    with requests.get(
        urljoin(base_url, endpoint), params=params, stream=True
    ) as response:
        response.raise_for_status()
        logger.debug(
            f"Got response {response.status_code} from server downloading {endpoint}."
        )
        destination.write_bytes(response.content)


@catch_and_log_exception(usdb_logger.logger)
def on_download_finished(song: usdb_song.UsdbSong) -> None:
    # Create a custom logger for the song to match usdb_syncer's logging format
    # {date} {time} {level} {song_id} {message}
    song_logger = usdb_logger.song_logger(song.song_id)
    song_logger.debug(f"Addon {__name__} called.")

    # Get the server settings
    server_settings = get_settings()

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
    model = server_settings.demucs_model
    song_logger.debug(f"Using model {model.value} for splitting.")

    # Send the file to the server
    try:
        response = requests.post(
            urljoin(server_settings.base_uri, "/split"),
            params={"model": model.value},
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
                urljoin(server_settings.base_uri, "/status"), params={"uuid": uuid}
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
        base_url=server_settings.base_uri,
        endpoint="/result/vocals",
        params={"uuid": uuid},
        destination=vocals_dest_path,
        logger=song_logger,
    )

    download_file_from_server(
        base_url=server_settings.base_uri,
        endpoint="/result/instrumental",
        params={"uuid": uuid},
        destination=instrumental_dest_path,
        logger=song_logger,
    )

    # Write the tags to the song file
    song_txt = song_folder.joinpath(song.sync_meta.txt.fname)
    if write_song_tags(
        song_txt, vocals_dest_path.name, instrumental_dest_path.name, song_logger
    ):
        song_logger.debug("Wrote tags to song file.")
    else:
        song_logger.error(
            "Failed to write tags to song file. The audio files will not be linked."
        )

    try:
        # Cleanup on server
        response = requests.post(
            urljoin(server_settings.base_uri, "/cleanup"), params={"uuid": uuid}
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        song_logger.debug(e)
        song_logger.error("Failed to cleanup on server.")
        return

    song_logger.info("Split finished.")


initialize_addon()
