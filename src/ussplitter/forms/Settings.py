# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'Settings.ui'
##
## Created by: Qt User Interface Compiler version 6.8.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (
    QCoreApplication,
    QDate,
    QDateTime,
    QLocale,
    QMetaObject,
    QObject,
    QPoint,
    QRect,
    QSize,
    QTime,
    QUrl,
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QCursor,
    QFont,
    QFontDatabase,
    QGradient,
    QIcon,
    QImage,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPalette,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName("Dialog")
        Dialog.resize(382, 200)
        self.buttonBox = QDialogButtonBox(Dialog)
        self.buttonBox.setObjectName("buttonBox")
        self.buttonBox.setGeometry(QRect(0, 160, 371, 32))
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.SettingsGroupBox = QGroupBox(Dialog)
        self.SettingsGroupBox.setObjectName("SettingsGroupBox")
        self.SettingsGroupBox.setGeometry(QRect(0, 10, 371, 151))
        self.SettingsGroupBox.setCheckable(True)
        self.verticalLayoutWidget = QWidget(self.SettingsGroupBox)
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayoutWidget.setGeometry(QRect(9, 19, 351, 126))
        self.verticalLayout = QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label_serverAddress = QLabel(self.verticalLayoutWidget)
        self.label_serverAddress.setObjectName("label_serverAddress")

        self.horizontalLayout.addWidget(self.label_serverAddress)

        self.lineEdit_serverAddress = QLineEdit(self.verticalLayoutWidget)
        self.lineEdit_serverAddress.setObjectName("lineEdit_serverAddress")

        self.horizontalLayout.addWidget(self.lineEdit_serverAddress)

        self.verticalLayout.addLayout(self.horizontalLayout)

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.horizontalSpacer = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )

        self.horizontalLayout_3.addItem(self.horizontalSpacer)

        self.graphicsView_connected = QGraphicsView(self.verticalLayoutWidget)
        self.graphicsView_connected.setObjectName("graphicsView_connected")
        self.graphicsView_connected.setMaximumSize(QSize(20, 20))

        self.horizontalLayout_3.addWidget(self.graphicsView_connected)

        self.pushButton_connect = QPushButton(self.verticalLayoutWidget)
        self.pushButton_connect.setObjectName("pushButton_connect")

        self.horizontalLayout_3.addWidget(self.pushButton_connect)

        self.verticalLayout.addLayout(self.horizontalLayout_3)

        self.verticalSpacer = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )

        self.verticalLayout.addItem(self.verticalSpacer)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.label_modelSelect = QLabel(self.verticalLayoutWidget)
        self.label_modelSelect.setObjectName("label_modelSelect")
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.label_modelSelect.sizePolicy().hasHeightForWidth()
        )
        self.label_modelSelect.setSizePolicy(sizePolicy)
        self.label_modelSelect.setAlignment(
            Qt.AlignmentFlag.AlignLeading
            | Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.horizontalLayout_2.addWidget(self.label_modelSelect)

        self.comboBox_modelSelect = QComboBox(self.verticalLayoutWidget)
        self.comboBox_modelSelect.setObjectName("comboBox_modelSelect")
        sizePolicy1 = QSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(
            self.comboBox_modelSelect.sizePolicy().hasHeightForWidth()
        )
        self.comboBox_modelSelect.setSizePolicy(sizePolicy1)

        self.horizontalLayout_2.addWidget(self.comboBox_modelSelect)

        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.retranslateUi(Dialog)
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)

        QMetaObject.connectSlotsByName(Dialog)

    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", "Dialog", None))
        self.SettingsGroupBox.setTitle(
            QCoreApplication.translate("Dialog", "Enabled", None)
        )
        self.label_serverAddress.setText(
            QCoreApplication.translate("Dialog", "Server Address", None)
        )
        self.pushButton_connect.setText(
            QCoreApplication.translate("Dialog", "Connect", None)
        )
        self.label_modelSelect.setText(
            QCoreApplication.translate("Dialog", "Model", None)
        )

    # retranslateUi
