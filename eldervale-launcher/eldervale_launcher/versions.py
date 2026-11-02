"""Manifesto de versões, download, instalação e execução do Eldervale.

Funciona igual ao launcher do Minecraft: um manifesto lista todas as versões,
cada uma com URL + hash. O jogador pode instalar e jogar qualquer uma delas.
"""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path

import requests

from . import config

META_FILE = ".eldervale.json"


class Cancelled(Exception):
    pass


def _get_json(url, cache_name):
    cache = config.CACHE_DIR / cache_name
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        cache.write_text(json.dumps(data), encoding="utf-8")
        return data, True
    except Exception:
        if cache.exists():
            try:
                return json.loads(cache.read_text(encoding="utf-8")), False
            except Exception:
                pass
        return None, False


def fetch_manifest():
    """Retorna (manifesto|None, online?). Offline usa o último cache."""
    return _get_json(config.MANIFEST_URL, "manifest.json")


def fetch_news():
    data, _ = _get_json(config.NEWS_URL, "news.json")
    return data or []


def version_dir(vid: str) -> Path:
    return config.VERSIONS_DIR / vid


def installed_versions() -> dict:
    """id -> entrada do manifesto salva na instalação (permite jogar offline)."""
    out = {}
    for d in config.VERSIONS_DIR.iterdir():
        meta = d / META_FILE
        if d.is_dir() and meta.exists():
            try:
                entry = json.loads(meta.read_text(encoding="utf-8"))
                out[entry["id"]] = entry
            except Exception:
                continue
    return out


def is_installed(vid: str) -> bool:
    return (version_dir(vid) / META_FILE).exists()


def download_info(version: dict):
    return (version.get("downloads") or {}).get(config.platform_key())


def install_version(version: dict, progress_cb, cancel):
    vid = version["id"]
    info = download_info(version)
    if not info:
        raise RuntimeError(f"A versão {vid} não está disponível para {config.platform_key()}.")

    part = config.CACHE_DIR / f"{vid}-{config.platform_key()}.zip.part"
    sha = hashlib.sha256()
    cancelled = False
    with requests.get(info["url"], stream=True, timeout=15) as r:
        r.raise_for_status()
        total = int(info.get("size") or r.headers.get("Content-Length") or 0)
        done = 0
        with open(part, "wb") as f:
            for chunk in r.iter_content(256 * 1024):
                if cancel.is_set():
                    cancelled = True
                    break
                f.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                progress_cb(done, total, "Baixando")
    if cancelled:
        part.unlink(missing_ok=True)
        raise Cancelled()

    expected = (info.get("sha256") or "").lower()
    if expected and sha.hexdigest() != expected:
        part.unlink(missing_ok=True)
        raise ValueError("Arquivo corrompido: o hash SHA-256 não confere.")

    staging = config.VERSIONS_DIR / f".{vid}.staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    root = staging.resolve()
    with zipfile.ZipFile(part) as zf:
        members = zf.infolist()
        for i, m in enumerate(members, 1):
            if cancel.is_set():
                shutil.rmtree(staging, ignore_errors=True)
                part.unlink(missing_ok=True)
                raise Cancelled()
            target = (staging / m.filename).resolve()
            if root != target and root not in target.parents:
                raise ValueError("Arquivo zip inválido (caminho suspeito).")
            zf.extract(m, staging)
            mode = (m.external_attr >> 16) & 0o777
            if mode and os.name == "posix" and not m.is_dir():
                os.chmod(target, mode)
            progress_cb(i, len(members), "Extraindo")
    part.unlink(missing_ok=True)

    # se o zip tem uma única pasta na raiz, "achata"
    entries = list(staging.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        inner = entries[0]
        for item in list(inner.iterdir()):
            shutil.move(str(item), str(staging / item.name))
        inner.rmdir()

    (staging / META_FILE).write_text(json.dumps(version, indent=2), encoding="utf-8")
    final = version_dir(vid)
    if final.exists():
        shutil.rmtree(final)
    staging.rename(final)


def uninstall(vid: str):
    shutil.rmtree(version_dir(vid), ignore_errors=True)


def launch(version: dict) -> subprocess.Popen:
    vid = version["id"]
    info = download_info(version)
    if not info or not info.get("executable"):
        raise RuntimeError("Executável não definido no manifesto.")
    vdir = version_dir(vid)
    exe = vdir / info["executable"]
    if not exe.exists():
        raise FileNotFoundError(f"Executável não encontrado: {exe}")
    if os.name == "posix":
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    env = os.environ.copy()
    env["ELDERVALE_DATA_DIR"] = str(config.SAVES_DIR)
    env["ELDERVALE_VERSION"] = vid
    return subprocess.Popen([str(exe)], cwd=str(vdir), env=env)
