"""Main window: Fluent navigation with Estrai, Libreria, Avanzamento, Registro, Impostazioni."""

from __future__ import annotations

import os

from PySide6.QtCore import QFile, QSize, Qt, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QSystemTrayIcon
from qfluentwidgets import (FluentIcon, FluentWindow, InfoBar, InfoBarIcon, InfoBarPosition,
                            MessageBox,
                            NavigationItemPosition, PushButton, Theme, isDarkTheme)

from .. import __version__, installer, merge, updater
from ..i18n import tr
from ..pkg import PkgError
from .config import cfg
from .extract_page import ExtractPage
from .library_page import LibraryPage
from .progress_page import ExtractWorker, MergeWorker, ProgressPage
from .settings_page import LogPage, SettingsPage
from .update_ui import UpdateCheckWorker, UpdateDialog
from .widgets import fmt_size

APP_NAME = "PS PKG Toolkit"


def trash_pkg(path: str) -> None:
    """Move a PKG to the system trash; delete it if the platform has no trash."""
    if not QFile.moveToTrash(path):
        os.remove(path)


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.worker: ExtractWorker | MergeWorker | None = None
        self.tray: QSystemTrayIcon | None = None
        self.updateCheck: UpdateCheckWorker | None = None
        self.updateBar: InfoBar | None = None
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(FluentIcon.GAME.icon())
        self.resize(1120, 780)
        self.setMinimumSize(QSize(900, 620))

        self.extractPage = ExtractPage(self)
        self.libraryPage = LibraryPage(self)
        self.progressPage = ProgressPage(self)
        self.logPage = LogPage(self)
        self.settingsPage = SettingsPage(self)

        self.addSubInterface(self.extractPage, FluentIcon.DOWNLOAD, tr("Estrai"))
        self.addSubInterface(self.libraryPage, FluentIcon.LIBRARY, tr("Libreria"))
        self.addSubInterface(self.progressPage, FluentIcon.SPEED_HIGH, tr("Avanzamento"))
        self.addSubInterface(self.logPage, FluentIcon.DOCUMENT, tr("Registro"))
        self.navigationInterface.addItem(
            "themeToggle", FluentIcon.CONSTRACT, tr("Cambia tema"), onClick=self.toggle_theme,
            selectable=False, position=NavigationItemPosition.BOTTOM)
        self.addSubInterface(self.settingsPage, FluentIcon.SETTING, tr("Impostazioni"),
                             NavigationItemPosition.BOTTOM)

        self.extractPage.startRequested.connect(self.start_extraction)
        self.extractPage.createPkgRequested.connect(self.start_merge)
        self.progressPage.cancelRequested.connect(self.cancel_extraction)
        self.progressPage.fractionChanged.connect(self._show_fraction)
        self.settingsPage.checkUpdatesRequested.connect(lambda: self.check_updates(manual=True))
        cfg.appRestartSig.connect(self._restart_needed)
        self.logPage.append(f"PS PKG Toolkit {__version__}")
        updater.cleanup_previous()
        if cfg.get(cfg.checkUpdates):
            QTimer.singleShot(2000, lambda: self.check_updates(manual=False))

    # -- updates -----------------------------------------------------------------------
    def check_updates(self, manual: bool) -> None:
        if self.updateCheck is not None and self.updateCheck.isRunning():
            return
        self.settingsPage.set_update_status(tr("Controllo in corso…"))
        self.updateCheck = UpdateCheckWorker(self)
        self.updateCheck.found.connect(self._update_found)
        self.updateCheck.upToDate.connect(lambda rel: self._update_none(rel, manual))
        self.updateCheck.failed.connect(lambda msg: self._update_failed(msg, manual))
        self.updateCheck.start()

    def _update_found(self, release) -> None:
        self.settingsPage.set_update_status(tr(
            "PS PKG Toolkit {current} · disponibile la versione {version}", current=__version__,
            version=release.version))
        self.logPage.append(tr("Disponibile PS PKG Toolkit {version}", version=release.version))
        if self.updateBar is not None:
            self.updateBar.close()
        # Built in full before show(): the bar sizes itself when shown.
        self.updateBar = InfoBar(
            InfoBarIcon.INFORMATION, tr("Aggiornamento disponibile"), f"PS PKG Toolkit {release.version}",
            isClosable=True, duration=-1, position=InfoBarPosition.TOP_RIGHT,
            parent=self.stackedWidget)
        button = PushButton(tr("Dettagli"), self.updateBar)
        button.clicked.connect(lambda: self.show_update(release))
        self.updateBar.addWidget(button)
        self.updateBar.show()

    def _update_none(self, release, manual: bool) -> None:
        self.settingsPage.set_update_status(
            tr("PS PKG Toolkit {current} · è l'ultima versione", current=__version__))
        if manual:
            InfoBar.success(tr("Nessun aggiornamento"),
                            tr("Stai già usando l'ultima versione ({version}).",
                               version=release.version), duration=4000,
                            position=InfoBarPosition.TOP_RIGHT, parent=self)

    def _update_failed(self, message: str, manual: bool) -> None:
        self.settingsPage.set_update_status(
            tr("PS PKG Toolkit {current} · controllo non riuscito", current=__version__))
        self.logPage.append(tr("Controllo aggiornamenti: {message}", message=message))
        if manual:
            InfoBar.warning(tr("Controllo non riuscito"), message, duration=6000,
                            position=InfoBarPosition.TOP_RIGHT, parent=self)

    def show_update(self, release) -> None:
        if self.worker and self.worker.isRunning():
            InfoBar.warning(tr("Operazione in corso"), tr("Aggiorna al termine dell'operazione."),
                            duration=4000, position=InfoBarPosition.TOP_RIGHT, parent=self)
            return
        UpdateDialog(release, self).exec()

    def _restart_needed(self) -> None:
        InfoBar.info(tr("Riavvio necessario"), tr("La nuova lingua verrà usata al prossimo avvio."),
                     duration=5000, position=InfoBarPosition.TOP_RIGHT, parent=self)

    # -- theme -----------------------------------------------------------------------
    def toggle_theme(self) -> None:
        cfg.set(cfg.themeMode, Theme.LIGHT if isDarkTheme() else Theme.DARK)

    # -- extraction --------------------------------------------------------------------
    def start_extraction(self) -> None:
        games = cfg.get(cfg.gamesDir)
        if not games and not self.extractPage.choose_games_dir():
            return
        games = os.path.abspath(cfg.get(cfg.gamesDir))
        addons = os.path.abspath(cfg.addons_dir_for(games))
        try:
            plan = self.extractPage.plan()
        except PkgError as ex:
            InfoBar.error(tr("Impossibile procedere"), str(ex), duration=6000,
                          position=InfoBarPosition.TOP_RIGHT, parent=self)
            return
        existing = [g.title_id for g in plan.groups.values()
                    if g.base and os.path.isdir(g.game_dir(games))]
        if plan.downgrades:
            box = MessageBox(tr("Versione più vecchia"),
                             "\n\n".join(plan.downgrades) + "\n\n" +
                             tr("Vuoi davvero sovrascrivere la versione installata?"), self)
            box.yesButton.setText(tr("Sovrascrivi"))
            box.cancelButton.setText(tr("Annulla"))
            if not box.exec():
                return
        elif existing:
            box = MessageBox(tr("Cartella già esistente"),
                             tr("Esiste già una cartella per {games}. I file con lo stesso nome "
                                "verranno sovrascritti. Continuare?", games=", ".join(existing)),
                             self)
            box.yesButton.setText(tr("Continua"))
            box.cancelButton.setText(tr("Annulla"))
            if not box.exec():
                return

        separate = not cfg.get(cfg.mergeUpdates)
        if not self._space_ok(plan, games, addons, separate):
            return
        remove = trash_pkg if cfg.get(cfg.deletePkgs) else None
        self.worker = ExtractWorker(plan, games, addons, separate,
                                    verify=cfg.get(cfg.verifyPkgs), remove_pkg=remove, parent=self)
        self.worker.logged.connect(self.logPage.append)
        self.worker.progressed.connect(self.progressPage.on_progress)
        self.worker.itemStatus.connect(self.progressPage.on_status)
        self.worker.verifyProgressed.connect(self.progressPage.on_verify)
        self.worker.succeeded.connect(lambda: self._finished(True, ""))
        self.worker.failed.connect(lambda msg: self._finished(False, msg))
        self.progressPage.start(plan, games, addons, separate)
        self.extractPage.set_busy(True)
        self.switchTo(self.progressPage)
        self.worker.start()

    def start_merge(self, paths: list[str]) -> None:
        if self.worker and self.worker.isRunning():
            return
        try:
            title, tid, version = merge.describe(paths)
        except (PkgError, OSError) as ex:
            InfoBar.error(tr("Impossibile procedere"), str(ex), duration=6000,
                          position=InfoBarPosition.TOP_RIGHT, parent=self)
            return
        start_dir = cfg.get(cfg.pkgDir) or os.path.dirname(paths[0])
        out, _ = QFileDialog.getSaveFileName(
            self, tr("Salva il nuovo PKG"),
            os.path.join(start_dir, merge.output_name(title, tid, version)),
            tr("PKG PS4 (*.pkg)"))
        if not out:
            return
        if not out.lower().endswith(".pkg"):
            out += ".pkg"
        out = os.path.abspath(out)
        if out in (os.path.abspath(p) for p in paths):
            InfoBar.error(tr("Impossibile procedere"),
                          tr("Scegli un nome diverso da quello dei PKG di origine."),
                          duration=6000, position=InfoBarPosition.TOP_RIGHT, parent=self)
            return
        cfg.set(cfg.pkgDir, os.path.dirname(out))
        short = merge.check_space(paths, out)
        if short:
            box = MessageBox(tr("Spazio su disco insufficiente"),
                             tr("Per il nuovo PKG servono fino a {needed}, liberi {free}.",
                                needed=fmt_size(short[0]), free=fmt_size(short[1])) + "\n\n" +
                             tr("Libera spazio oppure scegli un'altra cartella."), self)
            box.yesButton.setText(tr("Crea comunque"))
            box.cancelButton.setText(tr("Annulla"))
            if not box.exec():
                return
        infos = sorted((installer.read_info(p) for p in paths),
                       key=lambda i: (i.kind != "game", installer._version_key(i.app_ver)))
        self.worker = MergeWorker(paths, out, parent=self)
        self.worker.logged.connect(self.logPage.append)
        self.worker.progressed.connect(self.progressPage.on_merge_progress)
        self.worker.succeeded.connect(lambda _result: self._finished(True, ""))
        self.worker.failed.connect(lambda msg: self._finished(False, msg))
        self.logPage.append(tr("Creazione di {path}", path=out))
        self.progressPage.start_merge(infos, out)
        self.extractPage.set_busy(True)
        self.switchTo(self.progressPage)
        self.worker.start()

    def _space_ok(self, plan, games: str, addons: str, separate: bool) -> bool:
        """Warn before starting when a destination disk is too small."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            shortages = installer.check_space(plan, games, addons, separate)
        except (PkgError, OSError) as ex:
            shortages = []
            self.logPage.append(tr("Controllo dello spazio non riuscito: {error}", error=ex))
        finally:
            QApplication.restoreOverrideCursor()
        if not shortages:
            return True
        lines = ["• " + tr("{path}: servono {needed}, liberi {free}", path=sh.path,
                            needed=fmt_size(sh.needed), free=fmt_size(sh.free))
                 for sh in shortages]
        box = MessageBox(tr("Spazio su disco insufficiente"),
                         "\n".join(lines) + "\n\n" +
                         tr("L'estrazione si fermerebbe a metà. Libera spazio oppure scegli "
                            "un'altra cartella."), self)
        box.yesButton.setText(tr("Estrai comunque"))
        box.cancelButton.setText(tr("Annulla"))
        return bool(box.exec())

    def _show_fraction(self, frac: float) -> None:
        running = self.worker is not None and self.worker.isRunning()
        self.setWindowTitle(f"{int(frac * 100)}% · {APP_NAME}" if running and frac < 1
                            else APP_NAME)

    def _notify(self, ok: bool, message: str) -> None:
        """Tell the user an extraction ended while they were doing something else."""
        if self.isActiveWindow():
            return
        QApplication.alert(self)
        if not cfg.get(cfg.notifyDone) or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if self.tray is None:
            self.tray = QSystemTrayIcon(self.windowIcon(), self)
            self.tray.messageClicked.connect(self._raise)
            self.tray.activated.connect(lambda _reason: self._raise())
        self.tray.show()
        if ok:
            done = (tr("PKG creato.") if isinstance(self.worker, MergeWorker)
                    else tr("Estrazione completata."))
            self.tray.showMessage(APP_NAME, done, QSystemTrayIcon.Information, 8000)
        else:
            self.tray.showMessage(APP_NAME, message, QSystemTrayIcon.Warning, 8000)
        QTimer.singleShot(15000, self.tray.hide)

    def _raise(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def cancel_extraction(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.progressPage.cancelButton.setEnabled(False)
            self.progressPage.stats.setText(tr("Annullamento…"))

    def _finished(self, ok: bool, message: str) -> None:
        self.setWindowTitle(APP_NAME)
        self._notify(ok, message)
        self.progressPage.finish(ok, message)
        self.extractPage.set_busy(False)
        self.extractPage.refresh()
        if not ok:
            self.logPage.append(tr("ERRORE: {message}", message=message))

    def closeEvent(self, e):
        if self.worker and self.worker.isRunning():
            box = MessageBox(tr("Operazione in corso"),
                             tr("Vuoi interrompere l'operazione in corso e uscire?"), self)
            box.yesButton.setText(tr("Interrompi ed esci"))
            box.cancelButton.setText(tr("Continua"))
            if not box.exec():
                e.ignore()
                return
            self.worker.cancel()
            self.worker.wait(10000)
        super().closeEvent(e)
