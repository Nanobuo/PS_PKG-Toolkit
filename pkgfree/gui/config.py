"""Persistent settings, stored as JSON in PkgFree-data next to the program (portable)
or in %APPDATA%\\PkgFree."""

import os
from typing import Optional

from qfluentwidgets import (BoolValidator, ConfigItem, ConfigSerializer, EnumSerializer,
                            OptionsConfigItem, OptionsValidator, QConfig, Theme, qconfig)

from .. import portable

# Program folder when running in portable mode (folders are stored relative to it).
_portable_base: Optional[str] = None


def config_path() -> str:
    global _portable_base
    prog = portable.program_dir()
    data = portable.portable_data_dir(prog)
    _portable_base = prog if data else None
    return os.path.join(data or portable.user_data_dir(), portable.CONFIG_NAME)


def is_portable() -> bool:
    return _portable_base is not None


class PathSerializer(ConfigSerializer):
    def serialize(self, value):
        return portable.to_stored(value, _portable_base)

    def deserialize(self, value):
        return portable.from_stored(value, _portable_base)


class Config(QConfig):
    themeMode = OptionsConfigItem(
        "QFluentWidgets", "ThemeMode", Theme.AUTO, OptionsValidator(Theme), EnumSerializer(Theme))
    gamesDir = ConfigItem("Paths", "GamesDir", "", serializer=PathSerializer())
    addonsDir = ConfigItem("Paths", "AddonsDir", "", serializer=PathSerializer())
    lastDir = ConfigItem("Paths", "LastDir", "", serializer=PathSerializer())
    mergeUpdates = ConfigItem("Extraction", "MergeUpdates", True, BoolValidator())
    titleFolder = ConfigItem("Extraction", "TitleFolder", True, BoolValidator())
    verifyPkgs = ConfigItem("Extraction", "VerifyPkgs", False, BoolValidator())
    deletePkgs = ConfigItem("Extraction", "DeletePkgs", False, BoolValidator())
    notifyDone = ConfigItem("Extraction", "NotifyDone", True, BoolValidator())
    checkUpdates = ConfigItem("Updates", "CheckAtStartup", True, BoolValidator())
    language = OptionsConfigItem("General", "Language", "auto",
                                 OptionsValidator(["auto", "it", "en"]), restart=True)

    def addons_dir_for(self, games_dir: str) -> str:
        return self.get(self.addonsDir) or os.path.join(games_dir, "addcont")


cfg = Config()


def load_config() -> None:
    qconfig.load(config_path(), cfg)
