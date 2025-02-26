from pathlib import Path
from re import compile
from urllib.parse import urljoin

from requests import Session
from requests.exceptions import HTTPError, RequestException

from ussplitter import utils

uri_regex = r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)"  # noqa: E501


class ServerConnection:
    def __init__(self, base_uri: str):
        self.set_base_uri(base_uri)
        self._session = Session()

    def set_base_uri(self, base_uri: str) -> bool:
        if not compile(uri_regex).match(base_uri):
            return False
        self._base_uri = base_uri
        return True

    def connect(self) -> bool:
        if not self._base_uri:
            return False
        try:
            response = self._session.get(urljoin(self._base_uri, "/ping"))
            response.raise_for_status()
            return True
        except HTTPError:
            return False
        except RequestException:
            return False

    def get_models(self) -> list[str] | None:
        if not self._base_uri:
            return None
        try:
            response = self._session.get(urljoin(self._base_uri, "/models"))
            response.raise_for_status()
            return response.json()
        except HTTPError:
            return None
        except RequestException:
            return None

    def put(self, input_file: Path, model: str) -> str | None:
        if not self._base_uri:
            return None
        try:
            with input_file.open("rb") as f:
                response = self._session.put(
                    urljoin(self._base_uri, "/split"),
                    files={"file": f},
                    data={"model": model},
                )
                response.raise_for_status()
                return response.text
        except HTTPError:
            return None
        except RequestException:
            return None

    def get_status(self, uuid: str) -> str | None:
        if not self._base_uri:
            return None
        try:
            response = self._session.get(
                urljoin(self._base_uri, "/status"), params={"uuid": uuid}
            )
            response.raise_for_status()
            return response.text
        except HTTPError:
            return None
        except RequestException:
            return None

    def download_vocals(self, params: dict, destination: Path) -> None:
        destination.write_bytes(self._download("/result/vocals", params))

    def download_instrumental(self, params: dict, destination: Path) -> None:
        destination.write_bytes(self._download("/result/instrumental", params))

    def cleanup(self, uuid: str) -> None:
        response = self._session.get(
            urljoin(self._base_uri, "/cleanup"), params={"uuid": uuid}
        )
        try:
            response.raise_for_status()
        except HTTPError:
            pass
        self._session.close()

    @utils.retry_operation(3, 5)
    def _download(
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
