import contextlib
import logging
import os
import shlex
import shutil
import sys
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from queue import Queue
from threading import Lock

import demucs.api
import demucs.separate
import platformdirs

FILE_DIRECTORY = Path(
    platformdirs.user_data_dir(
        "ussplitter", roaming=False, appauthor=False, ensure_exists=True
    )
)


logging.basicConfig(
    format="%(asctime)s,%(msecs)03d %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)


to_separate = Queue()

status_lock = Lock()
pending_separations = []
processing_separations = []
finished_separations = []
errored_separations = []


@dataclass(frozen=True)
class SplitStatus(Enum):
    NONE = 0
    PENDING = 1
    PROCESSING = 2
    FINISHED = 3
    ERROR = 4


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

    def __str__(self) -> tuple[int, str]:
        """
        :return: A tuple containing the error code and the error message
        """
        return self.error_code, self.message


class ArgsError(AudioSplitError):
    def __init__(self, message: str):
        super().__init__(message, 400)


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
    to_separate.put(song_uuid)
    with status_lock:
        pending_separations.append(song_uuid)


def get_status(song_uuid: str) -> SplitStatus:
    """
    Get the status of a song

    :param song_uuid: The UUID of the song
    :return: True if the song has been separated, False otherwise
    """
    with status_lock:
        if song_uuid in pending_separations:
            return SplitStatus.PENDING
        if song_uuid in processing_separations:
            return SplitStatus.PROCESSING
        if song_uuid in finished_separations:
            return SplitStatus.FINISHED
        if song_uuid in errored_separations:
            return SplitStatus.ERROR
        return SplitStatus.NONE


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
    if song_uuid not in finished_separations and song_uuid not in errored_separations:
        return False

    path = FILE_DIRECTORY.joinpath(song_uuid)
    shutil.rmtree(path)

    with status_lock:
        if song_uuid in finished_separations:
            finished_separations.remove(song_uuid)
        elif song_uuid in errored_separations:
            errored_separations.remove(song_uuid)

    return True


def cleanup_all() -> bool:
    """
    Remove all files associated with all songs. Only allowed if there are no songs currently being processed

    :return: None
    """

    if to_separate.qsize() > 0:
        return False

    with status_lock:
        for songfolder in FILE_DIRECTORY.iterdir():
            shutil.rmtree(songfolder)

    pending_separations.clear()
    processing_separations.clear()
    finished_separations.clear()
    errored_separations.clear()

    return True


def split_worker() -> None:
    while True:
        song_uuid = to_separate.get()
        with status_lock:
            pending_separations.remove(song_uuid)
            processing_separations.append(song_uuid)
        path = FILE_DIRECTORY.joinpath(song_uuid)
        input_file = path.joinpath("input.mp3")

        args = SplitArgs(input_file=input_file, output_dir=path)

        try:
            separate_audio(args)
            with status_lock:
                processing_separations.remove(song_uuid)
                finished_separations.append(song_uuid)
        except AssertionError as e:
            with status_lock:
                processing_separations.remove(song_uuid)
                errored_separations.append(song_uuid)
            raise AudioSplitError(str(e), 500)
        except ArgsError as e:
            with status_lock:
                processing_separations.remove(song_uuid)
                errored_separations.append(song_uuid)
            raise e
        finally:
            to_separate.task_done()


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
            sys.modules["tqdm"].tqdm = lambda *args, **kwargs: args[0] if args else None
        demucs.separate.main(demucs_args)
