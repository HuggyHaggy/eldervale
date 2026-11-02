"""Configurações globais, caminhos e preferências do Eldervale Launcher."""
import json
import os
import platform
import sys
from pathlib import Path

APP_NAME = "Eldervale"
LAUNCHER_VERSION = "1.0.0"

# >>> Troque pela URL onde você hospeda os arquivos do jogo <<<
BASE_URL = os.environ.get("https://github.com/HuggyHaggy/eldervale", "http://127.0.0.1:8000").rstrip("/")
MANIFEST_URL = f"{BASE_URL}/version_manifest.json"   # lista de todas as versões do jogo
LAUNCHER_URL = f"{BASE_URL}/launcher.json"           # versão mais recente do próprio launcher
NEWS_URL = f"{BASE_URL}/news.json"                   # notícias exibidas na aba Novidades


def platform_key() -> str:
    s = platform.system().lower()
    return {"windows": "windows", "darwin": "macos"}.get(s, "linux")


def _data_dir() -> Path:
    plat = platform_key()
    if plat == "windows":
        base = Path(os.environ.get("APPDATA", str(Path.home()))) / ".eldervale"
    elif plat == "macos":
        base = Path.home() / "Library" / "Application Support" / "eldervale"
    else:
        base = Path.home() / ".eldervale"
    return base


DATA_DIR = Path(os.environ.get("ELDERVALE_DATA", _data_dir()))
VERSIONS_DIR = DATA_DIR / "versions"   # uma pasta por versão instalada
SAVES_DIR = DATA_DIR / "saves"         # saves compartilhados entre todas as versões
CACHE_DIR = DATA_DIR / "cache"
SETTINGS_FILE = DATA_DIR / "launcher_settings.json"
for _d in (DATA_DIR, VERSIONS_DIR, SAVES_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def asset_path(name: str) -> Path:
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
    return Path(base) / "assets" / name


DEFAULTS = {
    "selected": "latest",        # "latest" = sempre a última versão (como no launcher do Minecraft)
    "last_played": None,
    "last_seen_latest": None,    # para mostrar o aviso de atualização só uma vez
    "show_beta": False,
    "close_on_launch": False,
}


class Settings:
    def __init__(self):
        self.data = dict(DEFAULTS)
        try:
            self.data.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass

    def __getitem__(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self.data[key] = value
        try:
            SETTINGS_FILE.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except OSError:
            pass
