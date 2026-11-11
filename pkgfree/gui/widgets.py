"""Small custom widgets shared by the pages."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget
from qfluentwidgets import (BodyLabel, FluentIcon, IconWidget, PushButton,
                            ThemeColor, isDarkTheme, qconfig)

from ..i18n import get_language, tr

SECONDARY_LIGHT = QColor(96, 96, 96)
SECONDARY_DARK = QColor(206, 206, 206)


def fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(n)} B"
            text = f"{n:.1f} {unit}"
            return text.replace(".", ",") if get_language() == "it" else text
        n /= 1024
    return str(n)


def secondary(label):
    """Give a Fluent label the 'secondary text' colour in both themes."""
    label.setTextColor(SECONDARY_LIGHT, SECONDARY_DARK)
    return label


def elastic(label, tooltip: str = ""):
    """Let a label shrink (clipping long paths) instead of widening the page."""
    label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    label.setMinimumWidth(40)
    label.setToolTip(tooltip or label.text())
    return label


def elide(widget, text: str, width: int) -> str:
    return widget.fontMetrics().elidedText(text, Qt.ElideMiddle, width)


class StepBadge(QWidget):
    """Filled circle with the step number (accent for game/update, purple for DLC)."""

    def __init__(self, number: int, dlc: bool = False, parent=None):
        super().__init__(parent)
        self.number = number
        self.dlc = dlc
        self.setFixedSize(22, 22)
        # A bound method (not a lambda) is disconnected when the widget is destroyed.
        qconfig.themeChanged.connect(self._theme_changed)

    def _theme_changed(self, _theme) -> None:
        self.update()

    def paintEvent(self, _):
        dark = isDarkTheme()
        if self.dlc:
            fill = QColor("#C9A9F5") if dark else QColor("#6B3FA0")
        else:
            fill = ThemeColor.PRIMARY.color()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawEllipse(self.rect())
        font = QFont(self.font())
        font.setPixelSize(11)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("black") if dark else QColor("white"))
        p.drawText(self.rect(), Qt.AlignCenter, str(self.number))


class DropZone(QWidget):
    """Dashed drop target with 'add files' / 'add folder' buttons."""

    addFilesClicked = Signal()
    addFolderClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlight = False
        self.setMinimumHeight(72)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(12)
        lay.addStretch(1)
        icon = IconWidget(FluentIcon.DOWNLOAD, self)
        icon.setFixedSize(20, 20)
        lay.addWidget(icon)
        lay.addWidget(secondary(BodyLabel(
            tr("Trascina qui i file .pkg (gioco, aggiornamenti, DLC, in qualsiasi ordine) oppure"),
            self)))
        self.btnFiles = PushButton(FluentIcon.ADD, tr("Aggiungi PKG…"), self)
        self.btnFolder = PushButton(FluentIcon.FOLDER_ADD, tr("Aggiungi cartella…"), self)
        self.btnFiles.clicked.connect(self.addFilesClicked)
        self.btnFolder.clicked.connect(self.addFolderClicked)
        lay.addWidget(self.btnFiles)
        lay.addWidget(self.btnFolder)
        lay.addStretch(1)
        qconfig.themeChanged.connect(self._theme_changed)

    def _theme_changed(self, _theme) -> None:
        self.update()

    def set_highlight(self, on: bool) -> None:
        self.highlight = on
        self.update()

    def paintEvent(self, _):
        dark = isDarkTheme()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.highlight:
            border = ThemeColor.PRIMARY.color()
            fill = QColor(border)
            fill.setAlpha(28)
        else:
            border = QColor(255, 255, 255, 70) if dark else QColor(0, 0, 0, 80)
            fill = QColor(255, 255, 255, 8) if dark else QColor(255, 255, 255, 140)
        pen = QPen(border, 1.5, Qt.DashLine)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
