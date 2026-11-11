"""GUI side of the in-app update: background check, notice, download dialog."""

from __future__ import annotations

import re
import threading

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication
from qfluentwidgets import (BodyLabel, MessageBoxBase, PlainTextEdit, ProgressBar,
                            SubtitleLabel)

from .. import updater
from ..i18n import tr
from .widgets import fmt_size, secondary


class UpdateCheckWorker(QThread):
    found = Signal(object)      # updater.Release, newer than this version
    upToDate = Signal(object)   # updater.Release
    failed = Signal(str)

    def run(self) -> None:
        try:
            release = updater.fetch_latest()
        except updater.UpdateError as ex:
            self.failed.emit(str(ex))
            return
        if updater.is_newer(release.version):
            self.found.emit(release)
        else:
            self.upToDate.emit(release)


class UpdateDownloadWorker(QThread):
    progressed = Signal(object, object)
    finishedOk = Signal()
    failed = Signal(str)

    def __init__(self, release: updater.Release, target: str, parent=None):
        super().__init__(parent)
        self.release = release
        self.target = target
        self.cancel_event = threading.Event()

    def run(self) -> None:
        try:
            staged = updater.download(self.release, updater.staging_path(self.target),
                                      progress=self.progressed.emit,
                                      should_cancel=self.cancel_event.is_set)
            updater.apply_update(staged, self.target)
        except updater.UpdateError as ex:
            self.failed.emit(str(ex))
            return
        except OSError as ex:
            self.failed.emit(tr("Impossibile sostituire il programma: {error}. Scarica la nuova "
                                "versione dalla pagina delle release.", error=ex))
            return
        self.finishedOk.emit()


class UpdateDialog(MessageBoxBase):
    """Shows the release notes, then the download progress; restarts when done."""

    def __init__(self, release: updater.Release, parent=None):
        super().__init__(parent)
        self.release = release
        self.target = updater.install_target()
        self.worker: UpdateDownloadWorker | None = None

        self.viewLayout.addWidget(SubtitleLabel(
            tr("PS PKG Toolkit {version} disponibile", version=release.version), self))
        self.notes = PlainTextEdit(self)
        self.notes.setReadOnly(True)
        notes = re.sub(r"\*\*|__|`", "", release.notes).strip()
        self.notes.setPlainText(notes or tr("Nessuna nota per questa versione."))
        self.notes.setMinimumSize(460, 180)
        self.viewLayout.addWidget(self.notes)
        self.status = secondary(BodyLabel("", self))
        self.status.setWordWrap(True)
        self.viewLayout.addWidget(self.status)
        self.bar = ProgressBar(self)
        self.bar.setRange(0, 1000)
        self.bar.hide()
        self.viewLayout.addWidget(self.bar)

        self.cancelButton.setText(tr("Più tardi"))
        if self.target and release.asset_url:
            self.yesButton.setText(tr("Aggiorna e riavvia"))
            self.status.setText(tr("Il programma verrà scaricato, sostituito e riavviato."))
        else:
            self.yesButton.setText(tr("Apri la pagina della release"))
            self.status.setText(tr("Aggiornamento automatico non disponibile per questa copia "
                                   "(avviata dal codice sorgente o file mancante nella "
                                   "release)."))

    def validate(self) -> bool:
        """Called on the yes button: start the download instead of closing."""
        if not (self.target and self.release.asset_url):
            QDesktopServices.openUrl(QUrl(self.release.page_url))
            return True
        if self.worker is not None:
            return False
        self.yesButton.setEnabled(False)
        self.cancelButton.setText(tr("Annulla"))
        self.bar.show()
        self.status.setText(tr("Download in corso…"))
        self.worker = UpdateDownloadWorker(self.release, self.target, self)
        self.worker.progressed.connect(self._progress)
        self.worker.finishedOk.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.start()
        return False

    def reject(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel_event.set()
            self.worker.wait(5000)
        super().reject()

    def _progress(self, done, total) -> None:
        if total:
            self.bar.setValue(int(done * 1000 / total))
            self.status.setText(tr("Download: {done} / {total}", done=fmt_size(done),
                                   total=fmt_size(total)))

    def _done(self) -> None:
        self.status.setText(tr("Aggiornamento installato. Riavvio…"))
        try:
            updater.relaunch(self.target)
        except OSError as ex:
            self.status.setText(tr("Aggiornamento installato. Riavvia PS PKG Toolkit a mano "
                                   "({error}).", error=ex))
            self.cancelButton.setText(tr("Chiudi"))
            return
        QApplication.quit()

    def _failed(self, message: str) -> None:
        self.worker = None
        self.bar.hide()
        self.status.setText(message)
        self.yesButton.setEnabled(True)
        self.yesButton.setText(tr("Riprova"))
        self.cancelButton.setText(tr("Chiudi"))
