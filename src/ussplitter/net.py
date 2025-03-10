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

from pathlib import Path
from urllib.parse import urljoin

from requests import Session
from requests.exceptions import HTTPError, RequestException

from ussplitter import logger, utils


class ServerConnection:
    """Class for handling server connections."""

    _base_uri: str
    _session: Session
    _log: logger.AddonLogger | logger.AddonSongLogger

    def __init__(
        self, base_uri: str, log: logger.AddonLogger | logger.AddonSongLogger
    ) -> None:
        """
        :param base_uri: The base URI of the server.
        :param log: The logger instance. Errors will be logged to this instance.
        """
        self.set_base_uri(base_uri)
        self._session = Session()
        self._log = log

    def set_base_uri(self, base_uri: str) -> bool:
        """
        :param base_uri: The base URI of the server.
        :return: True if the base URI was set successfully, False otherwise.
        """
        self._base_uri = base_uri
        return True

    def connect(self) -> bool:
        """
        :return: True if the server is reachable, False otherwise.
        """
        if not self._base_uri:
            return False
        try:
            response = self._session.get(urljoin(self._base_uri, "/connect"))
            response.raise_for_status()
            return True
        except (HTTPError, RequestException) as e:
            self._log.debug(e)
            self._log.error("Failed to connect to server.")
            return False

    def get_models(self) -> list[str] | None:
        """
        :return: A list of available models on the server, or None if the request
            failed.
        """
        if not self._base_uri:
            return None
        try:
            response = self._session.get(urljoin(self._base_uri, "/models"))
            response.raise_for_status()
            return response.json()
        except (HTTPError, RequestException) as e:
            self._log.debug(e)
            self._log.error("Failed to get models from server.")
            return None

    def split(self, input_file: Path, model: str | None) -> str | None:
        """
        :param input_file: The path to the audio file to split.
        :param model: The model to use for splitting. If None, the server will use the
            default model.
        :return: The UUID of the split job, or None if the request failed.
        """
        if not self._base_uri:
            return None
        params = {"model": model} if model else {}
        try:
            with input_file.open("rb") as f:
                response = self._session.post(
                    urljoin(self._base_uri, "/split"),
                    params=params,
                    files={"audio": f},
                )
                response.raise_for_status()
                return response.text
        except (HTTPError, RequestException) as e:
            self._log.debug(e)
            self._log.error("Failed to send file to server for split.")
            return None

    def get_status(self, uuid: str) -> str | None:
        """
        :param uuid: The UUID of the split job.
        :return: The status of the split job, or None if the request failed.
        """
        if not self._base_uri:
            return None
        try:
            response = self._session.get(
                urljoin(self._base_uri, "/status"), params={"uuid": uuid}
            )
            response.raise_for_status()
            return response.text
        except (HTTPError, RequestException) as e:
            self._log.debug(e)
            self._log.error("Failed to get status from server.")
            return None

    def download_vocals(self, uuid: str, destination: Path) -> None:
        """
        :param uuid: The UUID of the split job to download.
        :param destination: The path to save the downloaded vocals
            file to.
        """
        params = {"uuid": uuid}
        if file := self._download("/result/vocals", params):
            destination.write_bytes(file)

    def download_instrumental(self, uuid: str, destination: Path) -> None:
        """
        :param uuid: The UUID of the split job to download.
        :param destination: The path to save the downloaded instrumental
            file to.
        """
        params = {"uuid": uuid}
        if file := self._download("/result/instrumental", params):
            destination.write_bytes(file)

    def cleanup(self, uuid: str) -> None:
        """
        :param uuid: The UUID of the split job to cleanup.
        """
        response = self._session.post(
            urljoin(self._base_uri, "/cleanup"), params={"uuid": uuid}
        )
        try:
            response.raise_for_status()
        except (HTTPError, RequestException) as e:
            self._log.debug(e)
            self._log.error("Failed to cleanup server.")
        self._session.close()

    def _download(self, endpoint: str, params: dict) -> bytes | None:
        try:
            return self._download_with_retry(endpoint, params)
        except RuntimeError as e:
            self._log.debug(e)
            self._log.error(f"Failed to download {endpoint}.")
            return None

    @utils.retry_operation(3, 5, RuntimeError())
    def _download_with_retry(
        self,
        endpoint: str,
        params: dict,
    ) -> bytes | None:
        if not self._base_uri:
            return None
        with self._session.get(
            urljoin(self._base_uri, endpoint), params=params, stream=True
        ) as response:
            response.raise_for_status()
            return response.content
