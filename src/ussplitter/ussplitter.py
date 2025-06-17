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
USSplitter is an addon for usdb_syncer that splits the audio of a song into vocals and
instrumental using a remote server. This allows weaker machines to offload the
processing to a more powerful server.

KEEP BACKUPS OF YOUR SONG FILES. USE AT YOUR OWN RISK.
"""

import os
import time
from pathlib import Path

import usdb_syncer
import usdb_syncer.gui.mw
import usdb_syncer.logger as usdb_logger
from usdb_syncer import hooks, song_txt, usdb_song
from usdb_syncer.gui import hooks as hooks_gui

from ussplitter import consts
from ussplitter.logger import AddonLogger, AddonSongLogger
from ussplitter.net import ServerConnection
from ussplitter.settings import SettingsDialog, get_settings
from ussplitter.version import SemanticVersion

USDB_SYNCER_VERSION = usdb_syncer.__version__

NAME = "USSplitter"


def initialize_addon(usdb_main_window: usdb_syncer.gui.mw.MainWindow) -> None:
    """
    Initialize the addon by loading configs and subscribing to events
    """
    addon_logger = AddonLogger(NAME, usdb_logger.logger)
    addon_logger.debug(f"Initializing {NAME} v{consts.USSPLITTER_VERSION!s}.")

    # Check for version compatibility
    if USDB_SYNCER_VERSION == "dev":
        addon_logger.debug(
            "Detected dev version of usdb_syncer. Skipping version check."
        )
    else:
        usdb_syncer_version = SemanticVersion.from_string(USDB_SYNCER_VERSION)
        if usdb_syncer_version < consts.LEAST_COMPATIBLE_USDB_SYNCER_VERSION:
            addon_logger.error(
                f"{NAME} requires usdb_syncer"
                f"v{consts.LEAST_COMPATIBLE_USDB_SYNCER_VERSION} or higher."
            )
            return

    # Add the settings dialog to the tools menu
    ussplitter_settings_dialog = SettingsDialog(
        usdb_main_window, ServerConnection("", addon_logger), addon_logger
    )
    usdb_main_window.menu_tools.addSeparator()
    usdb_main_window.menu_tools.addAction(
        f"{NAME} Settings", ussplitter_settings_dialog.show
    )

    hooks.SongLoaderDidFinish.subscribe(on_download_finished)
    addon_logger.debug('Subscribed to "SongLoaderDidFinish" event.')


def write_song_tags(
    txt_path: Path, vocals: str, instrumental: str, songlogger: usdb_logger.Logger
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


def on_download_finished(song: usdb_song.UsdbSong) -> None:  # noqa: C901
    song_logger = AddonSongLogger(NAME, song.song_id, usdb_logger.logger)
    song_logger.debug(f"Addon {NAME} called.")

    # Get the server settings
    server_settings = get_settings()

    error = False
    if not song.sync_meta:
        song_logger.error(
            "Song has no sync meta. This probably indicates that ussplitter doesn't "
            "support the current syncer version."
        )
        error = True
    else:
        if not song.sync_meta.txt:
            song_logger.error("Missing txt file. Skipping splitting.")
            error = True
        if not song.sync_meta.audio:
            song_logger.error("Missing audio file. Skipping splitting.")
            error = True

    if error:
        return

    # For mypy's benefit, we'll do some static checking here.
    assert song.sync_meta is not None
    assert song.sync_meta.txt is not None
    assert song.sync_meta.audio is not None

    song_folder: Path = song.sync_meta.path.parent
    song_mp3 = song_folder.joinpath(song.sync_meta.audio.fname)

    vocals_dest_path = song_folder.joinpath(f"{song_mp3.stem} [VOC].mp3")
    instrumental_dest_path = song_folder.joinpath(f"{song_mp3.stem} [INSTR].mp3")

    # Check if the files already exist. If they do, skip splitting.
    if vocals_dest_path.exists() and instrumental_dest_path.exists():
        song_logger.info(
            "Vocals and instrumental files already exist. Writing tags to file."
        )
        if write_song_tags(
            song_folder.joinpath(song.sync_meta.txt.fname),
            vocals_dest_path.name,
            instrumental_dest_path.name,
            song_logger,
        ):
            song_logger.debug("Wrote tags to song file.")
        else:
            song_logger.error(
                "Failed to write tags. Vocals/Instrumental files will not be linked."
            )
        return

    # Get the model to use for splitting. If not provided, use None and let the server
    # decide on the default.
    model = server_settings.demucs_model
    song_logger.debug(f"Using model {model} for splitting.")

    server_connection = ServerConnection(server_settings.base_uri, song_logger)
    if not server_connection.connect():
        song_logger.error("Failed to connect to server. Skipping splitting.")
        return

    # Send the file to the server
    if not (uuid := server_connection.split(song_mp3, model)):
        song_logger.error("Failed to send file to server for split.")
        return
    song_logger.info(f"Sent file to server for split. Got uuid {uuid}.")

    # Splitting will take some time.
    time.sleep(10)

    while True:
        time.sleep(5)

        if status := server_connection.get_status(uuid):
            song_logger.debug(f"Got status: {status}")

            match status:
                case "NONE":
                    song_logger.error(
                        "An internal error occured while splitting."
                        "Server returned NONE status."
                    )
                    return
                case "FINISHED":
                    break
                case "PENDING" | "PROCESSING":
                    pass
                case "ERROR":
                    song_logger.error(
                        "An error occured while splitting. Server returned ERROR"
                        "status."
                    )
                    server_connection.cleanup(uuid)
                    return

    # Download the vocals and instrumental files
    server_connection.download_vocals(uuid=uuid, destination=vocals_dest_path)

    server_connection.download_instrumental(
        uuid=uuid, destination=instrumental_dest_path
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

    # Cleanup the files on the server
    server_connection.cleanup(uuid)
    song_logger.debug("Cleaned up server files.")

    song_logger.info("Split finished.")


hooks_gui.MainWindowDidLoad.subscribe(initialize_addon)
