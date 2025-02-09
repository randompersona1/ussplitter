from dataclasses import dataclass
from typing import Optional
from enum import Enum
from PySide6.QtCore import QSettings


@dataclass
class DefaultSettings:
    """Default settings for the server."""

    BASE_URI = "http://localhost:5000"
    DEMUCS_MODEL = "htdemucs"


class DemucsModels(Enum):
    """Enum for the available demucs models."""

    HTDEMUCS = "htdemucs"
    HTDEMUCS_FT = "htdemucs_ft"
    HDEMUCS_MMI = "hdemucs_mmi"
    MDX = "mdx"
    MDX_EXTRA = "mdx_extra"
    MDX_Q = "mdx_q"
    MDX_EXTRA_Q = "mdx_extra_q"


@dataclass
class ServerSettings:
    """Configuration for the server."""

    base_uri: str
    demucs_model: DemucsModels = None


def set_settings(server_settings: ServerSettings):
    """Set the server settings in the QSettings object."""
    settings = QSettings("randompersona1", "USSplitter")
    settings.setValue("base_uri", server_settings.base_uri)
    settings.setValue("demucs_model", server_settings.demucs_model.value)


def get_settings() -> Optional[ServerSettings]:
    """Get the server settings from the QSettings object."""
    settings = QSettings("randompersona1", "USSplitter")
    base_uri = settings.value("base_uri")
    demucs_model = settings.value("demucs_model")
    if base_uri is None:
        base_uri = DefaultSettings.BASE_URI
    if demucs_model is None:
        demucs_model = DefaultSettings.DEMUCS_MODEL
    return ServerSettings(base_uri=base_uri, demucs_model=DemucsModels(demucs_model))