"""Auto-atualização do próprio launcher (funciona quando empacotado com PyInstaller)."""
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests

from . import config


def parse_version(v) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0")))


def can_self_update() -> bool:
    return bool(getattr(sys, "frozen", False))


def check():
    """Retorna o dict de launcher.json se houver versão mais nova, senão None."""
    try:
        r = requests.get(config.LAUNCHER_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    if parse_version(data.get("version")) <= parse_version(config.LAUNCHER_VERSION):
        return None
    if config.platform_key() not in (data.get("downloads") or {}):
        return None
    return data


def download(data, progress_cb, cancel) -> Path:
    info = data["downloads"][config.platform_key()]
    suffix = ".exe" if config.platform_key() == "windows" else ""
    dest = config.CACHE_DIR / f"launcher_new{suffix}"
    sha = hashlib.sha256()
    with requests.get(info["url"], stream=True, timeout=15) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(256 * 1024):
                f.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                progress_cb(done, total, "Baixando launcher")
    expected = (info.get("sha256") or "").lower()
    if expected and sha.hexdigest() != expected:
        dest.unlink(missing_ok=True)
        raise ValueError("Atualização do launcher corrompida (hash não confere).")
    return dest


def finalize(new_file: Path):
    """Troca o executável atual pelo novo e reinicia. Chame na thread principal."""
    exe = Path(sys.executable)
    if config.platform_key() == "windows":
        bat = config.CACHE_DIR / "apply_update.bat"
        bat.write_text(
            "@echo off\n"
            ":retry\n"
            f'move /Y "{new_file}" "{exe}" >nul 2>&1\n'
            "if errorlevel 1 (\n  ping 127.0.0.1 -n 2 >nul\n  goto retry\n)\n"
            f'start "" "{exe}"\n'
            'del "%~f0"\n',
            encoding="utf-8",
        )
        subprocess.Popen(["cmd", "/c", str(bat)], creationflags=0x00000008 | 0x08000000, close_fds=True)
    else:
        tmp = exe.with_name(exe.name + ".new")
        shutil.copy2(new_file, tmp)
        os.chmod(tmp, 0o755)
        os.replace(tmp, exe)
        os.execv(str(exe), [str(exe)])
