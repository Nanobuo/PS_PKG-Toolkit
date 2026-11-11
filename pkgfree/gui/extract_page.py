"""'Estrai' page: PKGs grouped by game, in the order they will be applied."""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, FlowLayout, FluentIcon, IconWidget,
                            ImageLabel, InfoBar, InfoBarIcon, InfoBarPosition, PrimaryPushButton,
                            PushButton, ScrollArea, SimpleCardWidget, StrongBodyLabel,
                            SubtitleLabel, TitleLabel, ToolTipFilter, TransparentPushButton,
                            TransparentToolButton, setCustomStyleSheet)

from .. import installer
from ..i18n import tr
from ..pkg import PkgError, PkgInfo
from .config import cfg
from .widgets import DropZone, StepBadge, elastic, elide, fmt_size, secondary


def collect_pkgs(paths) -> list[str]:
    """Expand folders into the .pkg files they contain."""
    found = []
    for path in paths:
        if os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                found += [os.path.join(root, f) for f in sorted(files) if f.lower().endswith(".pkg")]
        elif path.lower().endswith(".pkg"):
            found.append(path)
    return found


class StepChip(SimpleCardWidget):
    removeRequested = Signal(str)

    def __init__(self, number: int, info: PkgInfo, parent=None):
        super().__init__(parent)
        self.setFixedWidth(210)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 6, 10)
        lay.setSpacing(10)
        lay.addWidget(StepBadge(number, info.kind == "dlc", self), 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(StrongBodyLabel(installer.kind_label(info.kind), self))
        size = fmt_size(os.path.getsize(info.path))
        if info.kind == "dlc":
            detail = f"{info.entitlement_label or info.content_id} · {size}"
        else:
            detail = f"v{info.app_ver or info.version} · {size}"
        cap = secondary(CaptionLabel(detail, self))
        cap.setToolTip(os.path.basename(info.path))
        cap.installEventFilter(ToolTipFilter(cap))
        col.addWidget(cap)
        lay.addLayout(col, 1)
        btn = TransparentToolButton(FluentIcon.CLOSE, self)
        btn.setFixedSize(24, 24)
        btn.setIconSize(btn.iconSize() * 0.7)
        btn.setToolTip(tr("Rimuovi questo PKG"))
        btn.installEventFilter(ToolTipFilter(btn))
        btn.clicked.connect(lambda: self.removeRequested.emit(info.path))
        lay.addWidget(btn, 0, Qt.AlignTop)


class GameCard(SimpleCardWidget):
    removeRequested = Signal(list)
    createPkgRequested = Signal(list)

    def __init__(self, group: installer.TitleGroup, games_dir: str, icon: Optional[bytes],
                 parent=None):
        super().__init__(parent)
        items = group.ordered()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 16, 18)
        lay.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(16)
        pix = QPixmap()
        if icon and pix.loadFromData(icon):
            img = ImageLabel(pix, self)
            img.scaledToHeight(72)
            img.setBorderRadius(6, 6, 6, 6)
            head.addWidget(img)
        else:
            box = IconWidget(FluentIcon.GAME, self)
            box.setFixedSize(48, 48)
            head.addSpacing(12)
            head.addWidget(box)
            head.addSpacing(12)

        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(SubtitleLabel(group.title, self))
        total = sum(os.path.getsize(i.path) for i in items)
        col.addWidget(secondary(CaptionLabel(
            f"{group.title_id} · {len(items)} PKG · {fmt_size(total)}", self)))
        if games_dir:
            dest = group.game_dir(games_dir)
            col.addWidget(elastic(secondary(CaptionLabel(tr("Destinazione: {dest}", dest=dest), self))))
        head.addLayout(col, 1)

        if group.final_version:
            ver = QVBoxLayout()
            ver.setSpacing(0)
            ver.addWidget(secondary(CaptionLabel(tr("Versione finale"), self)), 0, Qt.AlignRight)
            ver.addWidget(SubtitleLabel(group.final_version, self), 0, Qt.AlignRight)
            head.addLayout(ver)
        if group.base and group.patches:
            pack = PushButton(FluentIcon.SAVE_AS, tr("Crea PKG"), self)
            pack.setToolTip(tr("Unisce gioco base e aggiornamenti in un nuovo PKG, da installare "
                               "su una PS4 modificata. I DLC restano PKG separati."))
            pack.installEventFilter(ToolTipFilter(pack))
            sources = [group.base.path] + [p.path for p in group.patches]
            pack.clicked.connect(lambda: self.createPkgRequested.emit(sources))
            head.addWidget(pack, 0, Qt.AlignTop)
        rm = TransparentToolButton(FluentIcon.DELETE, self)
        rm.setToolTip(tr("Rimuovi questo gioco dall'elenco"))
        rm.installEventFilter(ToolTipFilter(rm))
        rm.clicked.connect(lambda: self.removeRequested.emit([i.path for i in items]))
        head.addWidget(rm, 0, Qt.AlignTop)
        lay.addLayout(head)

        lay.addWidget(secondary(CaptionLabel(tr("Ordine di applicazione"), self)))
        steps = QWidget(self)
        flow = FlowLayout(steps, needAni=False)
        flow.setContentsMargins(0, 0, 0, 0)
        flow.setHorizontalSpacing(6)
        flow.setVerticalSpacing(8)
        for n, info in enumerate(items, 1):
            if n > 1:
                holder = QWidget(steps)
                holder.setFixedSize(14, 58)
                arrow = IconWidget(FluentIcon.CHEVRON_RIGHT, holder)
                arrow.setGeometry(1, 23, 12, 12)
                flow.addWidget(holder)
            chip = StepChip(n, info, steps)
            chip.removeRequested.connect(lambda p: self.removeRequested.emit([p]))
            flow.addWidget(chip)
        lay.addWidget(steps)

        for text in group.warnings(games_dir):
            bar = InfoBar(InfoBarIcon.WARNING, tr("Attenzione"), text, Qt.Horizontal,
                          isClosable=False, duration=-1, position=InfoBarPosition.NONE,
                          parent=self)
            lay.addWidget(bar)


class ExtractPage(QWidget):
    startRequested = Signal()
    createPkgRequested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("extractPage")
        self.setAcceptDrops(True)
        self.infos: dict[str, PkgInfo] = {}
        self.icons: dict[str, Optional[bytes]] = {}
        self.cards: list[QWidget] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = ScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.enableTransparentBackground()
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view = QWidget()
        view.setObjectName("extractView")
        view.setStyleSheet("#extractView{background: transparent}")
        self.scroll.setWidget(view)
        self.body = QVBoxLayout(view)
        self.body.setContentsMargins(36, 24, 36, 24)
        self.body.setSpacing(14)
        self.body.addWidget(TitleLabel(tr("I tuoi giochi"), view))
        self.drop = DropZone(view)
        self.drop.addFilesClicked.connect(self.choose_files)
        self.drop.addFolderClicked.connect(self.choose_folder)
        self.body.addWidget(self.drop)
        self.empty = secondary(BodyLabel(tr(
            "Nessun PKG aggiunto. Puoi aggiungere insieme gioco base, aggiornamenti e DLC: "
            "vengono raggruppati per gioco e applicati nell'ordine giusto."), view))
        self.empty.setWordWrap(True)
        self.body.addWidget(self.empty)
        self.cardsLayout = QVBoxLayout()
        self.cardsLayout.setSpacing(12)
        self.body.addLayout(self.cardsLayout)
        self.body.addStretch(1)
        outer.addWidget(self.scroll, 1)

        bar = QFrame(self)
        bar.setObjectName("bottomBar")
        setCustomStyleSheet(
            bar,
            "#bottomBar{background: rgba(255,255,255,0.6); border-top: 1px solid rgba(0,0,0,0.08)}",
            "#bottomBar{background: rgba(255,255,255,0.04); border-top: 1px solid rgba(255,255,255,0.08)}")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(36, 12, 36, 14)
        bl.setSpacing(10)
        info = QVBoxLayout()
        info.setSpacing(0)
        self.summary = secondary(CaptionLabel("", bar))
        info.addWidget(self.summary)
        self.destButton = TransparentPushButton(FluentIcon.FOLDER, "", bar)
        self.destButton.setToolTip(tr("Cartella in cui estrarre i giochi"))
        self.destButton.installEventFilter(ToolTipFilter(self.destButton))
        self.destButton.clicked.connect(self.choose_games_dir)
        info.addWidget(self.destButton, 0, Qt.AlignLeft)
        bl.addLayout(info, 1)
        self.clearButton = PushButton(FluentIcon.BROOM, tr("Svuota"), bar)
        self.clearButton.clicked.connect(self.clear)
        self.startButton = PrimaryPushButton(FluentIcon.DOWNLOAD, tr("Estrai tutto"), bar)
        self.startButton.clicked.connect(self.startRequested)
        bl.addWidget(self.clearButton)
        bl.addWidget(self.startButton)
        outer.addWidget(bar)

        cfg.gamesDir.valueChanged.connect(lambda _: self.refresh())
        cfg.addonsDir.valueChanged.connect(lambda _: self.refresh())
        cfg.titleFolder.valueChanged.connect(lambda _: self.refresh())
        self.refresh()

    # -- data --------------------------------------------------------------------
    def plan(self) -> installer.Plan:
        return installer.build_plan(list(self.infos.values()), cfg.get(cfg.gamesDir),
                                    cfg.get(cfg.titleFolder))

    def add_paths(self, paths) -> None:
        errors = []
        for path in collect_pkgs(paths):
            path = os.path.abspath(path)
            if path in self.infos:
                continue
            try:
                info = installer.read_info(path)
                installer.build_plan(list(self.infos.values()) + [info], "")
            except (PkgError, OSError) as ex:
                errors.append(f"{os.path.basename(path)}: {ex}")
                continue
            self.infos[path] = info
            self.icons[path] = installer.read_icon(path)
            cfg.set(cfg.lastDir, os.path.dirname(path))
        if errors:
            InfoBar.error(tr("Alcuni PKG non sono stati aggiunti"), "\n".join(errors),
                          duration=8000, position=InfoBarPosition.TOP_RIGHT, parent=self.window())
        self.refresh()

    def remove_paths(self, paths) -> None:
        for p in paths:
            self.infos.pop(p, None)
            self.icons.pop(p, None)
        self.refresh()

    def clear(self) -> None:
        self.infos.clear()
        self.icons.clear()
        self.refresh()

    def set_busy(self, busy: bool) -> None:
        for w in (self.drop, self.clearButton, self.startButton, self.destButton):
            w.setEnabled(not busy)
        for c in self.cards:
            c.setEnabled(not busy)

    def refresh(self) -> None:
        for c in self.cards:
            self.cardsLayout.removeWidget(c)
            c.deleteLater()
        self.cards = []
        games_dir = cfg.get(cfg.gamesDir)
        plan = self.plan()
        for group in plan.groups.values():
            icon = next((self.icons.get(i.path) for i in group.ordered()
                         if i.kind != "dlc" and self.icons.get(i.path)), None)
            card = GameCard(group, games_dir, icon, self)
            card.removeRequested.connect(self.remove_paths)
            card.createPkgRequested.connect(self.createPkgRequested)
            self.cardsLayout.addWidget(card)
            self.cards.append(card)
        self.empty.setVisible(not plan.groups)
        n_pkg = len(self.infos)
        total = sum(os.path.getsize(p) for p in self.infos)
        self.summary.setText(
            tr("{games} giochi · {pkgs} PKG · {size}", games=len(plan.groups), pkgs=n_pkg,
               size=fmt_size(total)) if n_pkg else tr("Nessun PKG"))
        self.destButton.setText(elide(self.destButton, games_dir, 480) if games_dir
                                else tr("Scegli la cartella dei giochi…"))
        self.startButton.setEnabled(bool(n_pkg))
        self.clearButton.setEnabled(bool(n_pkg))

    # -- dialogs -------------------------------------------------------------------
    def choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr("Seleziona i file PKG"), cfg.get(cfg.lastDir),
            tr("PKG PS4 (*.pkg);;Tutti i file (*)"))
        if paths:
            self.add_paths(paths)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("Cartella con file PKG"),
                                                  cfg.get(cfg.lastDir))
        if folder:
            if not collect_pkgs([folder]):
                InfoBar.info(tr("Nessun PKG"), tr("La cartella non contiene file .pkg."), duration=4000,
                             position=InfoBarPosition.TOP_RIGHT, parent=self.window())
            self.add_paths([folder])

    def choose_games_dir(self) -> bool:
        folder = QFileDialog.getExistingDirectory(self, tr("Cartella dei giochi"),
                                                  cfg.get(cfg.gamesDir))
        if folder:
            cfg.set(cfg.gamesDir, os.path.normpath(folder))
            return True
        return False

    # -- drag & drop -------------------------------------------------------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and self.drop.isEnabled():
            e.acceptProposedAction()
            self.drop.set_highlight(True)

    def dragLeaveEvent(self, e):
        self.drop.set_highlight(False)

    def dropEvent(self, e):
        self.drop.set_highlight(False)
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.add_paths(paths)
            e.acceptProposedAction()
