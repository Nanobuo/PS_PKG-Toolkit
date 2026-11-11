"""'Avanzamento' page and the background extraction thread."""

from __future__ import annotations

import os
import threading
import time

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, FluentIcon, IconWidget, InfoBar,
                            InfoBarIcon, InfoBarPosition, LargeTitleLabel, ProgressBar,
                            ProgressRing, PushButton, ScrollArea, SimpleCardWidget, TitleLabel)

from .. import installer, merge
from ..i18n import tr
from ..pkg import Cancelled, PkgError, PkgInfo
from .widgets import elastic, fmt_size, secondary


class ExtractWorker(QThread):
    logged = Signal(str)
    progressed = Signal(int, object, object, str)  # index, done bytes, total bytes, file
    itemStatus = Signal(int, str)
    verifyProgressed = Signal(int, object, object)  # index, done bytes, total bytes
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, plan, games_dir, addons_dir, separate_update, verify=False,
                 remove_pkg=None, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.games_dir = games_dir
        self.addons_dir = addons_dir
        self.separate_update = separate_update
        self.verify = verify
        self.remove_pkg = remove_pkg
        self.cancel_event = threading.Event()
        self._last_emit = 0.0

    def cancel(self) -> None:
        self.cancel_event.set()

    def _progress(self, idx, _count, done, total, name):
        now = time.monotonic()
        if name and now - self._last_emit < 0.1:
            return
        self._last_emit = now
        self.progressed.emit(idx, done, total, name)

    def _verify_progress(self, idx, done, total):
        now = time.monotonic()
        if done != total and now - self._last_emit < 0.1:
            return
        self._last_emit = now
        self.verifyProgressed.emit(idx, done, total)

    def run(self) -> None:
        try:
            installer.install(
                self.plan, self.games_dir, self.addons_dir, self.separate_update,
                log=self.logged.emit, progress=self._progress,
                should_cancel=self.cancel_event.is_set, item_status=self.itemStatus.emit,
                resume=True, verify=self.verify, verify_progress=self._verify_progress,
                remove_pkg=self.remove_pkg)
            self.succeeded.emit()
        except Cancelled:
            self.failed.emit(tr("Operazione annullata. Avviando di nuovo l'estrazione con gli "
                                "stessi PKG riprenderà da dove si è fermata."))
        except (PkgError, OSError) as ex:
            self.failed.emit(str(ex))
        except Exception as ex:  # keep the UI alive and tell the user
            self.failed.emit(tr("Errore inatteso: {error}", error=repr(ex)))


class MergeWorker(QThread):
    """Builds a new game PKG from a base game and its updates."""
    logged = Signal(str)
    progressed = Signal(object, object, str)  # done bytes, total bytes, what is happening
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, paths: list[str], out_path: str, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.out_path = out_path
        self.cancel_event = threading.Event()
        self._last_emit = 0.0

    def cancel(self) -> None:
        self.cancel_event.set()

    def _progress(self, done, total, label):
        now = time.monotonic()
        if done != total and now - self._last_emit < 0.1:
            return
        self._last_emit = now
        self.progressed.emit(done, total, label)

    def run(self) -> None:
        try:
            result = merge.merge_pkgs(self.paths, self.out_path, log=self.logged.emit,
                                      progress=self._progress,
                                      should_cancel=self.cancel_event.is_set)
            self.logged.emit(tr("Creato {path}: {title} v{version} ({cid})", path=self.out_path,
                                title=result.title, version=result.version,
                                cid=result.content_id))
            self.succeeded.emit(result)
        except Cancelled:
            self.failed.emit(tr("Operazione annullata: il PKG incompleto è stato eliminato."))
        except (PkgError, OSError) as ex:
            self.failed.emit(str(ex))
        except Exception as ex:  # keep the UI alive and tell the user
            self.failed.emit(tr("Errore inatteso: {error}", error=repr(ex)))


class QueueRow(SimpleCardWidget):
    def __init__(self, info: PkgInfo, dest: str, games_dir: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(14)
        self.ring = ProgressRing(self)
        self.ring.setFixedSize(22, 22)
        self.ring.setStrokeWidth(3)
        self.ring.setTextVisible(False)
        self.icon = IconWidget(FluentIcon.STOP_WATCH, self)
        self.icon.setFixedSize(20, 20)
        self.ring.hide()
        lay.addWidget(self.ring)
        lay.addWidget(self.icon)
        col = QVBoxLayout()
        col.setSpacing(0)
        ver = info.app_ver or info.version
        name = installer.kind_label(info.kind)
        if info.kind == "dlc":
            name += f" {info.entitlement_label}"
        elif ver:
            name += f" v{ver}"
        col.addWidget(BodyLabel(name, self))
        size = fmt_size(os.path.getsize(info.path))
        shown = dest
        rel = os.path.relpath(dest, games_dir) if games_dir else dest
        if not rel.startswith(".."):
            shown = rel
        col.addWidget(elastic(secondary(CaptionLabel(
            f"{os.path.basename(info.path)} · {size} → {shown}", self)), dest))
        lay.addLayout(col, 1)
        self.state = secondary(BodyLabel(tr("In attesa"), self))
        lay.addWidget(self.state)

    def set_running(self, frac: float) -> None:
        self.icon.hide()
        self.ring.show()
        self.ring.setValue(int(frac * 100))
        self.state.setText(f"{int(frac * 100)}%")

    def set_verifying(self, frac: float) -> None:
        self.icon.hide()
        self.ring.show()
        self.ring.setValue(int(frac * 100))
        self.state.setText(tr("Verifica {pct}%", pct=int(frac * 100)))

    def set_skipped(self) -> None:
        self.ring.hide()
        self.icon.setIcon(InfoBarIcon.SUCCESS)
        self.icon.show()
        self.state.setText(tr("Già estratto"))

    def set_done(self) -> None:
        self.ring.hide()
        self.icon.setIcon(InfoBarIcon.SUCCESS)
        self.icon.show()
        self.state.setText(tr("Completato"))

    def set_failed(self, text: str) -> None:
        self.ring.hide()
        self.icon.setIcon(InfoBarIcon.ERROR)
        self.icon.show()
        self.state.setText(text)


class ProgressPage(QWidget):
    cancelRequested = Signal()
    fractionChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("progressPage")
        self.rows: list[QueueRow] = []
        self.weights: list[int] = []
        self.current = -1
        self.result_bar = None
        self.mode = "extract"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = ScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.enableTransparentBackground()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view = QWidget()
        view.setObjectName("progressView")
        view.setStyleSheet("#progressView{background: transparent}")
        scroll.setWidget(view)
        outer.addWidget(scroll)

        self.body = QVBoxLayout(view)
        self.body.setContentsMargins(36, 24, 36, 24)
        self.body.setSpacing(14)
        head = QVBoxLayout()
        head.setSpacing(2)
        self.title = TitleLabel(tr("Nessuna estrazione in corso"), view)
        self.subtitle = secondary(BodyLabel(tr("Aggiungi i PKG nella pagina Estrai e premi "
                                               "«Estrai tutto»."), view))
        head.addWidget(self.title)
        head.addWidget(elastic(self.subtitle))
        self.body.addLayout(head)

        self.card = SimpleCardWidget(view)
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(20, 18, 20, 18)
        cl.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(14)
        self.percent = LargeTitleLabel("0%", self.card)
        top.addWidget(self.percent)
        self.stats = secondary(BodyLabel("", self.card))
        top.addWidget(self.stats, 1, Qt.AlignVCenter)
        self.cancelButton = PushButton(FluentIcon.CLOSE, tr("Annulla"), self.card)
        self.cancelButton.clicked.connect(self.cancelRequested)
        top.addWidget(self.cancelButton, 0, Qt.AlignVCenter)
        cl.addLayout(top)
        self.bar = ProgressBar(self.card)
        self.bar.setRange(0, 1000)
        cl.addWidget(self.bar)
        self.fileLabel = secondary(CaptionLabel("", self.card))
        cl.addWidget(self.fileLabel)
        self.body.addWidget(self.card)
        self.card.hide()

        self.queue = QVBoxLayout()
        self.queue.setSpacing(4)
        self.body.addLayout(self.queue)
        self.resultLayout = QVBoxLayout()
        self.body.addLayout(self.resultLayout)
        self.body.addStretch(1)

    # -- lifecycle -----------------------------------------------------------------
    def _reset(self) -> None:
        for r in self.rows:
            self.queue.removeWidget(r)
            r.hide()
            r.deleteLater()
        self.rows = []
        if self.result_bar:
            self.resultLayout.removeWidget(self.result_bar)
            self.result_bar.hide()
            self.result_bar.deleteLater()
            self.result_bar = None
        self.current = -1
        self.base_bytes = 0
        self.item_bytes = 0
        self.started = time.monotonic()
        self.card.show()
        self.cancelButton.setEnabled(True)
        self.cancelButton.show()
        self._set_fraction(0.0)
        self.stats.setText(tr("Preparazione…"))
        self.fileLabel.setText("")

    def start(self, plan: installer.Plan, games_dir: str, addons_dir: str,
              separate_update: bool) -> None:
        self._reset()
        self.mode = "extract"
        items = plan.all_items()
        self.rows = []
        for info in items:
            dest = plan.target_dir(info, games_dir, addons_dir, separate_update)
            row = QueueRow(info, dest, games_dir, self)
            self.queue.addWidget(row)
            self.rows.append(row)
        self.weights = [max(os.path.getsize(i.path), 1) for i in items]
        self.games_dir = games_dir
        self.addons_dir = addons_dir
        titles = ", ".join(g.title for g in plan.groups.values())
        self.title.setText(tr("Estrazione in corso"))
        self.subtitle.setText(f"{titles} → {games_dir}")
        self.subtitle.setToolTip(self.subtitle.text())

    def start_merge(self, infos: list[PkgInfo], out_path: str) -> None:
        self._reset()
        self.mode = "merge"
        self.out_path = out_path
        out_dir = os.path.dirname(out_path)
        for info in infos:
            row = QueueRow(info, out_path, out_dir, self)
            self.queue.addWidget(row)
            self.rows.append(row)
        self.weights = [1]
        self.title.setText(tr("Creazione del PKG in corso"))
        self.subtitle.setText(f"{infos[0].title} → {out_path}")
        self.subtitle.setToolTip(self.subtitle.text())

    def on_merge_progress(self, done, total, label: str) -> None:
        frac = done / total if total else 1.0
        for row in self.rows:
            row.set_running(frac)
        self.item_bytes = done
        self.fileLabel.setText(label)
        self.current = 0
        self._update(0, frac)

    def _set_fraction(self, frac: float) -> None:
        self.percent.setText(f"{int(frac * 100)}%")
        self.bar.setValue(int(frac * 1000))
        self.fractionChanged.emit(frac)

    def on_status(self, idx: int, state: str) -> None:
        if state == "verify":
            self.current = idx
            self.rows[idx].set_verifying(0.0)
            self.fileLabel.setText(tr("Verifica integrità del PKG…"))
        elif state == "skipped":
            self.rows[idx].set_skipped()
            self._update(idx, 1.0)
        elif state == "start":
            self.current = idx
            self.base_bytes += self.item_bytes
            self.item_bytes = 0
            self.rows[idx].set_running(0.0)
        elif state == "done":
            self.rows[idx].set_done()
            self._update(idx, 1.0)

    def on_verify(self, idx: int, done, total) -> None:
        frac = done / total if total else 1.0
        self.rows[idx].set_verifying(frac)
        self.fileLabel.setText(tr("Verifica integrità: {done} / {total}", done=fmt_size(done),
                                  total=fmt_size(total)))

    def on_progress(self, idx: int, done, total, name: str) -> None:
        frac_item = done / total if total else 1.0
        self.item_bytes = done
        self.rows[idx].set_running(frac_item)
        if name:
            self.fileLabel.setText(tr("Sto scrivendo: {name}", name=name))
        self._update(idx, frac_item)

    def _update(self, idx: int, frac_item: float) -> None:
        total_w = sum(self.weights)
        frac = (sum(self.weights[:idx]) + self.weights[idx] * frac_item) / total_w
        self._set_fraction(frac)
        elapsed = time.monotonic() - self.started
        written = self.base_bytes + self.item_bytes
        parts = [tr("{size} elaborati", size=fmt_size(written)) if self.mode == "merge"
                 else tr("{size} scritti", size=fmt_size(written))]
        if elapsed > 1:
            parts.append(f"{fmt_size(written / elapsed)}/s")
        if 0.02 < frac < 1 and elapsed > 3:
            left = elapsed * (1 - frac) / frac
            parts.append(tr("circa {min} min {sec} s rimanenti", min=int(left // 60),
                            sec=int(left % 60)) if left >= 60
                         else tr("circa {sec} s rimanenti", sec=int(left)))
        self.stats.setText(" · ".join(parts))

    def finish(self, ok: bool, message: str = "") -> None:
        self.cancelButton.hide()
        self.fileLabel.setText("")
        if ok and self.mode == "merge":
            self._set_fraction(1.0)
            for row in self.rows:
                row.set_done()
            self.title.setText(tr("PKG creato"))
            self.stats.setText(tr("Tempo impiegato: {sec} s",
                                   sec=int(time.monotonic() - self.started)))
            bar = InfoBar(InfoBarIcon.SUCCESS, tr("PKG pronto"),
                          tr("Installalo sulla PS4 modificata come un normale PKG."),
                          Qt.Horizontal, isClosable=False, duration=-1,
                          position=InfoBarPosition.NONE, parent=self)
            folder = os.path.dirname(self.out_path)
            btn = PushButton(FluentIcon.FOLDER, tr("Apri cartella"), bar)
            btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(folder)))
            bar.addWidget(btn)
        elif ok:
            self._set_fraction(1.0)
            self.title.setText(tr("Estrazione completata"))
            self.stats.setText(tr("Tempo impiegato: {sec} s",
                                   sec=int(time.monotonic() - self.started)))
            bar = InfoBar(InfoBarIcon.SUCCESS, tr("Pronto per shadPS4"),
                          tr("Aggiungi la cartella dei giochi in shadPS4 e imposta la cartella "
                             "DLC nelle sue impostazioni."),
                          Qt.Horizontal, isClosable=False, duration=-1,
                          position=InfoBarPosition.NONE, parent=self)
            btn = PushButton(FluentIcon.FOLDER, tr("Apri cartella"), bar)
            btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.games_dir)))
            bar.addWidget(btn)
        else:
            self.title.setText(tr("Creazione del PKG interrotta") if self.mode == "merge"
                               else tr("Estrazione interrotta"))
            failed = self.rows if self.mode == "merge" else self.rows[self.current:self.current + 1]
            if self.current >= 0:
                for row in failed:
                    row.set_failed(tr("Interrotto"))
            bar = InfoBar(InfoBarIcon.ERROR, tr("Errore"), message, Qt.Horizontal, isClosable=False,
                          duration=-1, position=InfoBarPosition.NONE, parent=self)
        self.result_bar = bar
        self.resultLayout.addWidget(bar)
