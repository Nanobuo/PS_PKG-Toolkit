"""'Impostazioni' and 'Registro' pages."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QFileDialog, QVBoxLayout, QWidget
from qfluentwidgets import (FluentIcon, HyperlinkCard, OptionsSettingCard, PlainTextEdit,
                            PushSettingCard, ScrollArea, SettingCardGroup, SwitchSettingCard,
                            TitleLabel)

from .. import __version__
from ..i18n import tr
from .config import cfg, is_portable

REPO_URL = "https://github.com/nanobuo/pkg-free"


class LocalizedSwitchSettingCard(SwitchSettingCard):
    """SwitchSettingCard writes "On"/"Off" on every change; show translated labels instead."""

    def setValue(self, isChecked: bool):
        super().setValue(isChecked)
        self.switchButton.setText(tr("Attivo") if isChecked else tr("Disattivo"))


class SettingsPage(QWidget):
    checkUpdatesRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = ScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.enableTransparentBackground()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view = QWidget()
        view.setObjectName("settingsView")
        view.setStyleSheet("#settingsView{background: transparent}")
        scroll.setWidget(view)
        outer.addWidget(scroll)

        lay = QVBoxLayout(view)
        lay.setContentsMargins(36, 24, 36, 24)
        lay.setSpacing(24)
        lay.addWidget(TitleLabel(tr("Impostazioni"), view))

        paths = SettingCardGroup(tr("Cartelle"), view)
        self.gamesCard = PushSettingCard(tr("Scegli cartella"), FluentIcon.FOLDER,
                                         tr("Cartella giochi"),
                                         "", paths)
        self.gamesCard.clicked.connect(self._choose_games)
        self.addonsCard = PushSettingCard(tr("Scegli cartella"), FluentIcon.LIBRARY,
                                          tr("Cartella DLC"),
                                          "", paths)
        self.addonsCard.clicked.connect(self._choose_addons)
        paths.addSettingCard(self.gamesCard)
        paths.addSettingCard(self.addonsCard)
        lay.addWidget(paths)

        extraction = SettingCardGroup(tr("Estrazione"), view)
        self.mergeCard = self._switch(
            extraction, cfg.mergeUpdates, FluentIcon.SYNC, tr("Unisci gli aggiornamenti al gioco"),
            tr("Se disattivato, gli aggiornamenti vengono estratti a parte in <TITLE_ID>-UPDATE"))
        self.titleCard = self._switch(
            extraction, cfg.titleFolder, FluentIcon.TAG, tr("Cartella con il nome del gioco"),
            tr("Es. Giochi\\Driveclub\\CUSA00003: shadPS4 trova il gioco anche nella "
               "sottocartella. I DLC restano in addcont\\<TITLE_ID>."))
        self.verifyCard = self._switch(
            extraction, cfg.verifyPkgs, FluentIcon.CERTIFICATE,
            tr("Verifica i PKG prima di estrarli"),
            tr("Controlla le impronte SHA-256 per scoprire download danneggiati. Rilegge tutto "
               "il PKG: circa un minuto in più ogni 50 GB."))
        self.deleteCard = self._switch(
            extraction, cfg.deletePkgs, FluentIcon.DELETE, tr("Sposta i PKG nel Cestino al termine"),
            tr("Solo se l'estrazione di tutti i PKG è riuscita."))
        self.notifyCard = self._switch(
            extraction, cfg.notifyDone, FluentIcon.RINGER, tr("Notifica a fine estrazione"),
            tr("Mostra una notifica di sistema se nel frattempo stai usando un'altra finestra."))
        lay.addWidget(extraction)

        look = SettingCardGroup(tr("Aspetto"), view)
        self.themeCard = OptionsSettingCard(
            cfg.themeMode, FluentIcon.BRUSH, tr("Tema"), tr("Chiaro, scuro o come Windows"),
            texts=[tr("Chiaro"), tr("Scuro"), tr("Usa impostazione di sistema")], parent=look)
        self.languageCard = OptionsSettingCard(
            cfg.language, FluentIcon.LANGUAGE, tr("Lingua"), tr("Si applica al prossimo avvio"),
            texts=[tr("Automatica (lingua del sistema)"), "Italiano", "English"], parent=look)
        look.addSettingCard(self.themeCard)
        look.addSettingCard(self.languageCard)
        lay.addWidget(look)

        updates = SettingCardGroup(tr("Aggiornamenti"), view)
        self.updateSwitch = self._switch(
            updates, cfg.checkUpdates, FluentIcon.UPDATE,
            tr("Controlla gli aggiornamenti all'avvio"),
            tr("Cerca una nuova versione su GitHub quando apri il programma."))
        self.updateCard = PushSettingCard(tr("Controlla ora"), FluentIcon.SYNC,
                                          tr("Versione installata"), f"PS PKG Toolkit {__version__}",
                                          updates)
        self.updateCard.clicked.connect(self.checkUpdatesRequested)
        updates.addSettingCard(self.updateCard)
        lay.addWidget(updates)

        about = SettingCardGroup(tr("Informazioni"), view)
        about.addSettingCard(HyperlinkCard(
            REPO_URL, tr("Codice sorgente"), FluentIcon.INFO, "PS PKG Toolkit",
            tr("Versione {version} · GPL-3.0 · supporta solo PKG fake (fPKG)",
               version=__version__), about))
        data_dir = os.path.dirname(str(cfg.file))
        self.dataCard = PushSettingCard(
            tr("Apri cartella"), FluentIcon.SAVE,
            tr("Versione portatile") if is_portable() else tr("Impostazioni salvate in"),
            tr("Impostazioni salvate accanto al programma: {folder}", folder=data_dir)
            if is_portable() else data_dir, about)
        self.dataCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(data_dir)))
        about.addSettingCard(self.dataCard)
        lay.addWidget(about)
        lay.addStretch(1)

        cfg.gamesDir.valueChanged.connect(lambda _: self._refresh())
        cfg.addonsDir.valueChanged.connect(lambda _: self._refresh())
        self._refresh()

    @staticmethod
    def _switch(group, item, icon, title, content):
        card = LocalizedSwitchSettingCard(icon, title, content, configItem=item, parent=group)
        card.setValue(cfg.get(item))
        group.addSettingCard(card)
        return card

    def set_update_status(self, text: str) -> None:
        self.updateCard.setContent(text)

    def _refresh(self) -> None:
        games = cfg.get(cfg.gamesDir)
        self.gamesCard.setContent(games or tr("Non impostata"))
        addons = cfg.get(cfg.addonsDir)
        if addons:
            self.addonsCard.setContent(addons)
        else:
            default = (os.path.join(games, "addcont") if games
                       else tr("<cartella giochi>\\addcont"))
            self.addonsCard.setContent(tr("Predefinita: {folder}", folder=default))

    def _choose_games(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("Cartella dei giochi"),
                                                  cfg.get(cfg.gamesDir))
        if folder:
            cfg.set(cfg.gamesDir, os.path.normpath(folder))

    def _choose_addons(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("Cartella DLC"),
                                                  cfg.get(cfg.addonsDir))
        if folder:
            cfg.set(cfg.addonsDir, os.path.normpath(folder))


class LogPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logPage")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 24, 36, 24)
        lay.setSpacing(14)
        lay.addWidget(TitleLabel(tr("Registro"), self))
        self.text = PlainTextEdit(self)
        self.text.setReadOnly(True)
        font = QFont()
        font.setFamilies(["Cascadia Mono", "Consolas", "DejaVu Sans Mono"])
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(9)
        self.text.setFont(font)
        lay.addWidget(self.text, 1)

    def append(self, line: str) -> None:
        self.text.appendPlainText(line)
