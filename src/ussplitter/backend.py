import contextlib
import logging
import os
import shlex
import shutil
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from enum import Enum, auto, unique
from pathlib import Path
from typing import Generator

import demucs.api
import demucs.separate
import platformdirs
import torch as th

FILE_DIRECTORY = Path(
    platformdirs.user_data_dir(
        "ussplitter", roaming=False, appauthor=False, ensure_exists=True
    )
)
DB_PATH = FILE_DIRECTORY.joinpath("db.sqlite")


logging.basicConfig(
    format="%(asctime)s,%(msecs)03d %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)


@unique
class SplitStatus(Enum):
    NONE = auto()
    PENDING = auto()
    PROCESSING = auto()
    FINISHED = auto()
    ERROR = auto()


@dataclass(frozen=True)
class SplitArgs:
    input_file: Path
    output_dir: Path
    bitrate: int = 128
    model: str = "htdemucs_ft"


class AudioSplitError(Exception):
    def __init__(self, message: str, error_code: int):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)

    def __str__(self):
        return self.message

    def ec(self):
        return self.error_code


class ArgsError(AudioSplitError):
    def __init__(self, message: str):
        super().__init__(message, 400)


def init_db() -> None:
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS queue (
                song_uuid TEXT PRIMARY KEY NOT NULL,
                model TEXT
            )
        """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS status (
                song_uuid TEXT PRIMARY KEY NOT NULL,
                status TEXT
            )
        """
        )


@contextlib.contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def make_folder() -> tuple[str, Path]:
    """
    Create a new directory for a song to be stored in

    :return: A tuple containing the UUID of the song and the path where the mp3 file will be stored
    """
    song_uuid = str(uuid.uuid4())

    tempdir = FILE_DIRECTORY.joinpath(song_uuid)
    tempdir.mkdir(exist_ok=False)

    mp3_file = tempdir.joinpath("input.mp3")

    return song_uuid, mp3_file


def put(song_uuid: str) -> None:
    """
    Put a song into the queue to be separated

    :param uuid: The UUID of the song
    :return: None
    """
    with get_db() as db:
        db.execute("INSERT INTO queue (song_uuid) VALUES (?)", (song_uuid,))
        db.execute(
            "INSERT INTO status (song_uuid, status) VALUES (?, ?)",
            (song_uuid, SplitStatus.PENDING.name),
        )
        db.commit()


def get_status(song_uuid: str) -> SplitStatus:
    """
    Get the status of a song

    :param song_uuid: The UUID of the song
    :return: True if the song has been separated, False otherwise
    """
    with get_db() as db:
        status = db.execute(
            "SELECT status FROM status WHERE song_uuid = ?", (song_uuid,)
        )
        result = status.fetchone()
        if result is None:
            return SplitStatus.NONE
        return SplitStatus[result[0]]


def get_vocals(song_uuid: str) -> Path:
    """
    Get the path to the vocals file. This path is not guaranteed to exist. Only try to access the file if the status is FINISHED

    :param song_uuid: The UUID of the song
    :return: The path to the vocals file
    """
    return (
        FILE_DIRECTORY.joinpath(song_uuid)
        .joinpath("htdemucs_ft")
        .joinpath("input")
        .joinpath("vocals.mp3")
    )


def get_instrumental(song_uuid: str) -> Path:
    """
    Get the path to the instrumental file. This path is not guaranteed to exist. Only try to access this file if the status is FINISHED.

    :param song_uuid: The UUID of the song
    :return: The path to the instrumental file
    """
    return (
        FILE_DIRECTORY.joinpath(song_uuid)
        .joinpath("htdemucs_ft")
        .joinpath("input")
        .joinpath("no_vocals.mp3")
    )


def cleanup(song_uuid: str) -> bool:
    """
    Remove the files associated with a song

    :param song_uuid: The UUID of the song
    :return: None
    """
    logger.debug(f"Cleaning up {song_uuid}.")

    with get_db() as db:
        status = db.execute(
            "SELECT status FROM status WHERE song_uuid = ?", (song_uuid,)
        )
        status = status.fetchone()
        if (
            status is None
            or status[0] == SplitStatus.NONE.name
            or status[0] == SplitStatus.PROCESSING.name
            or status[0] == SplitStatus.PENDING.name
        ):
            return False

    path = FILE_DIRECTORY.joinpath(song_uuid)
    shutil.rmtree(path)

    with get_db() as db:
        db.execute("DELETE FROM queue WHERE song_uuid = ?", (song_uuid,))
        db.execute("DELETE FROM status WHERE song_uuid = ?", (song_uuid,))
        db.commit()

    return True


def cleanup_all() -> bool:
    """
    Remove all files associated with all songs. Only allowed if there are no songs currently being processed

    :return: None
    """
    for songfolder in FILE_DIRECTORY.iterdir():
        shutil.rmtree(songfolder)

    with get_db() as db:
        db.execute("DELETE FROM queue")
        db.execute("DELETE FROM status")
        db.commit()

    return True


def split_worker() -> None:
    # Entrypoint for the backend worker. Make sure this is running only once.

    # Debug information
    logger.debug("Starting split worker.")
    logger.debug(f"File directory: {FILE_DIRECTORY}")
    logger.debug(f"Database path: {DB_PATH}")
    logger.debug(f"GPU available: {th.cuda.is_available()}")
    logger.debug(f"Available models: {demucs.api.list_models()}")

    init_db()

    while True:
        # Get a song to separate. If not available, sleep for 1 second and try again
        with get_db() as db:
            task = db.execute("SELECT * FROM queue LIMIT 1")
            task = task.fetchone()

        if task is None:
            time.sleep(1)
            continue

        song_uuid = task[0]
        model = task[1]
        if model is None:
            model = "htdemucs_ft"

        logger.info(f"Picked up task {task[0]} with model {model}.")

        with get_db() as db:
            db.execute("DELETE FROM queue WHERE song_uuid = ?", (song_uuid,))
            db.execute(
                "UPDATE status SET status = ? WHERE song_uuid = ?",
                (SplitStatus.PROCESSING.name, song_uuid),
            )
            db.commit()

        path = FILE_DIRECTORY.joinpath(song_uuid)
        input_file = path.joinpath("input.mp3")

        args = SplitArgs(input_file=input_file, output_dir=path, model=model)

        try:
            logger.info("Separating...")
            separate_audio(args)
            with get_db() as db:
                db.execute(
                    "UPDATE status SET status = ? WHERE song_uuid = ?",
                    (SplitStatus.FINISHED.name, song_uuid),
                )
                db.commit()
            logger.info("Finished separating.")
        except AssertionError as e:
            with get_db() as db:
                db.execute(
                    "UPDATE status SET status = ? WHERE song_uuid = ?",
                    (SplitStatus.ERROR.name, song_uuid),
                )
                db.commit()
            raise AudioSplitError(str(e), 500)
        except ArgsError as e:
            with get_db() as db:
                db.execute(
                    "UPDATE status SET status = ? WHERE song_uuid = ?",
                    (SplitStatus.ERROR.name, song_uuid),
                )
                db.commit()
            raise e


def separate_audio(args: SplitArgs) -> None:
    """
    :param args: SplitArgs object
    :return: None

    :raises AssertionError: If the input file does not exist or is not a file, or if the output directory does not exist or is not a directory
    :raises ArgsError: If the arguments are invalid
    """
    assert args.input_file.exists(), args.input_file.is_file()
    assert args.output_dir.exists(), args.output_dir.is_dir()
    assert args.bitrate > 0, args.bitrate < 320

    try:
        demucs_args = shlex.split(
            f'--mp3 --mp3-bitrate={str(args.bitrate)} --two-stems=vocals -n {args.model} -j 2 -o "{args.output_dir.as_posix()}" "{args.input_file.as_posix()}"'
        )
    except ValueError as e:
        raise ArgsError(str(e))
    with contextlib.ExitStack() as stack:
        # Redirect stdout and stderr to null
        null_file = stack.enter_context(open(os.devnull, "w"))
        stack.enter_context(contextlib.redirect_stdout(null_file))
        stack.enter_context(contextlib.redirect_stderr(null_file))

        # Temporarily disable tqdm progress bars
        stack.enter_context(contextlib.suppress(Exception))
        if "tqdm" in sys.modules:
            sys.modules["tqdm"].tqdm = lambda *args, **kwargs: args[0] if args else None  # type: ignore
        demucs.separate.main(demucs_args)
