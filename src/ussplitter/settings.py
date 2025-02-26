from dataclasses import dataclass

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from ussplitter.forms.Settings import Ui_Dialog
from ussplitter.logger import AddonLogger
from ussplitter.net import ServerConnection


@dataclass
class ServerSettings:
    """Configuration for the server."""

    base_uri: str
    demucs_model: str

    @staticmethod
    def from_dict(settings: dict[str, str]) -> "ServerSettings":
        """Create a ServerSettings object from a dictionary."""
        return ServerSettings(
            base_uri=settings["base_uri"], demucs_model=settings["demucs_model"]
        )


def set_settings(server_settings: ServerSettings):
    """Set the server settings in the QSettings object."""
    settings = QSettings("randompersona1", "USSplitter")
    for key, value in server_settings.__dict__.items():
        settings.setValue(key, value)


def get_settings() -> ServerSettings:
    """Get the server settings from the QSettings object."""
    settings = QSettings("randompersona1", "USSplitter")
    out: dict[str, str] = {}
    for key in settings.allKeys():
        out[key] = settings.value(key, type=str)  # type: ignore
    return ServerSettings.from_dict(out)


class SettingsDialog(Ui_Dialog, QDialog):
    """Settings dialog for the addon."""

    def __init__(
        self, parent: QWidget, server_connection: ServerConnection, log: AddonLogger
    ) -> None:
        self.server_connection = server_connection
        self.log = log

        super().__init__(parent)
        self.setupUi(self)
        self.load_settings()
        self.pushButton_connect.clicked.connect(self.connect_server)

    def load_settings(self) -> None:
        settings = get_settings()
        self.lineEdit_serverAddress.setText(settings.base_uri)
        self.comboBox_modelSelect.setCurrentText(settings.demucs_model)

    def set_models(self, models: list[str]) -> None:
        self.comboBox_modelSelect.clear()
        self.comboBox_modelSelect.addItem("Default server model")
        self.comboBox_modelSelect.addItems(models)

    def connect_server(self) -> None:
        self.server_connection.set_base_uri(self.lineEdit_serverAddress.text())
        if self.server_connection.connect():
            self.log.debug("Connected to server.")
            models = self.server_connection.get_models()
            if models:
                self.set_models(models)
            else:
                QMessageBox.critical(self, "Error", "Failed to get models from server.")
        else:
            QMessageBox.critical(self, "Error", "Failed to connect to server.")

    def accept(self) -> None:
        self.server_connection.set_base_uri(self.lineEdit_serverAddress.text())
        set_settings(
            ServerSettings(
                base_uri=self.lineEdit_serverAddress.text(),
                demucs_model=self.comboBox_modelSelect.currentText()
                if not self.comboBox_modelSelect.currentText() == "Default server model"
                else "default",
            )
        )
