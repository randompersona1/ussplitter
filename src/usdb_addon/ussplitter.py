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

import time
from pathlib import Path
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


def initialize_addon() -> None:
    """
    Initialize the addon by loading configs and subscribing to events
    """

    logger.debug("Initializing remote audio splitter addon.")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Using config directory {CONFIG_DIR}")

    config_file = CONFIG_DIR.joinpath("ussplitter.txt")
    if not config_file.exists():
        logger.error(
            f"Config file not found. Please create a config file at {config_file}"
        )
        return

    with open(config_file, "r") as f:
        configs_list = f.readlines()

    for config in configs_list:
        key, value = config.split("=")
        CONFIGS[key.strip()] = value.strip()

    logger.debug(f"Loaded config successfully: {CONFIGS}")

    for key in NECCESARY_CONFIG_KEYS:
        if key not in CONFIGS:
            logger.error(f"{key} not found in config file. Please add it.")
            return
    assert CONFIGS["SERVER_URI"] is not None, "SERVER_URI is required in config file."
    assert CONFIGS["SERVER_URI"].startswith("http://"), (
        "SERVER_URI must start with http://."
    )

    hooks.SongLoaderDidFinish.subscribe(on_download_finished)
    logger.debug("Subscribed to SongLoaderDidFinish event.")


def write_song_tags(song_txt: Path, vocals: str, instrumental: str) -> bool:
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
    with open(song_txt, "r", encoding="utf-8") as f:
        for line in f.readlines():
            if not tags_added and not any(line.startswith(note) for note in note_lines):
                # We've reached the lyrics. Now insert the #VOCALS and #INSTRUMENTAL tags above
                song.append(f"#VOCALS:{vocals}\n")
                song.append(f"#INSTRUMENTAL:{instrumental}\n")
                tags_added = True
            song.append(line)

    if tags_added:
        with open(song_txt, "w", encoding="utf-8") as f:
            f.writelines(song)

    return tags_added


def on_download_finished(song: usdb_song.UsdbSong) -> None:
    # Create a custom logger for the song to match usdb_syncer's logging format
    # {date} {time} {level} {song_id} {message}
    song_logger = usdb_logger.song_logger(song.song_id)

    if not song.sync_meta:
        song_logger.error("Missing sync_meta. This should never happen.")
        return
    if not song.sync_meta.txt:
        song_logger.error("Missing txt file. Skipping splitting.")
        return
    if not song.sync_meta.audio:
        song_logger.error("Missing audio file. Skipping splitting.")
        return

    song_logger.info("Preparing split.")

    song_folder: Path = song.sync_meta.path.parent
    song_mp3 = song_folder.joinpath(song.sync_meta.audio.fname)

    # Send the file to the server
    response = requests.post(
        urljoin(CONFIGS["SERVER_URI"], "/split"), files={"audio": open(song_mp3, "rb")}
    )
    response.raise_for_status()
    uuid = response.text

    song_logger.info(f"Got uuid {uuid} from server.")

    # Splitting will take some time.
    time.sleep(20)

    while True:
        response = requests.get(
            urljoin(CONFIGS["SERVER_URI"], "/status"), params={"uuid": uuid}
        )
        response.raise_for_status()
        status = response.text
        if status == "NONE":
            song_logger.error(
                "An error occured while splitting. Server returned NONE status."
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
        time.sleep(5)

    response = requests.get(
        urljoin(CONFIGS["SERVER_URI"], "/result/vocals"), params={"uuid": uuid}
    )
    response.raise_for_status()

    # Vocals should be saved as a `{...} [VOC].mp3` next to the original file
    vocals_path = song_folder.joinpath(f"{song_mp3.stem} [VOC].mp3")
    with open(vocals_path, "wb") as f:
        f.write(response.content)
    song_logger.debug(f"Saved vocals for {song.song_id}")

    response = requests.get(
        urljoin(CONFIGS["SERVER_URI"], "/result/instrumental"), params={"uuid": uuid}
    )
    response.raise_for_status()

    # Same for instrumental
    instrumental_path = song_folder.joinpath(f"{song_mp3.stem} [INSTR].mp3")
    with open(instrumental_path, "wb") as f:
        f.write(response.content)
    song_logger.debug(f"Saved instrumental for {song.song_id}")

    # Write the tags to the song file
    song_txt = song_folder.joinpath(song.sync_meta.txt.fname)
    write_song_tags(song_txt, vocals_path.name, instrumental_path.name)
    song_logger.debug(f"Wrote tags for {song.song_id}")

    # Cleanup on server
    response = requests.post(
        urljoin(CONFIGS["SERVER_URI"], "/cleanup"), params={"uuid": uuid}
    )
    response.raise_for_status()

    song_logger.info(f"Successfully split {song.song_id}.")


initialize_addon()
