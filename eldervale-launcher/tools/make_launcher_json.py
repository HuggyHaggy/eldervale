"""Gera/atualiza launcher.json a partir dos executáveis do launcher (usado pelo GitHub Actions).

Uso:
  python tools/make_launcher_json.py --version 1.0.1 --files-dir dist \
      --download-base-url https://github.com/USUARIO/REPO/releases/download/launcher-v1.0.1 \
      --out docs/launcher.json --changelog "Correções"

Espera arquivos chamados EldervaleLauncher-windows.exe, EldervaleLauncher-linux, EldervaleLauncher-macos.
"""
import argparse
import hashlib
import json
from pathlib import Path

NAMES = {
    "windows": "EldervaleLauncher-windows.exe",
    "linux": "EldervaleLauncher-linux",
    "macos": "EldervaleLauncher-macos",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--files-dir", required=True)
    ap.add_argument("--download-base-url", required=True)
    ap.add_argument("--out", default="docs/launcher.json")
    ap.add_argument("--changelog", default="")
    a = ap.parse_args()

    out = Path(a.out)
    old = {}
    if out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    downloads = dict(old.get("downloads", {})) if old.get("version") == a.version else {}
    base = a.download_base_url.rstrip("/")
    for plat, name in NAMES.items():
        f = Path(a.files_dir) / name
        if f.exists():
            downloads[plat] = {"url": f"{base}/{name}", "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
    if not downloads:
        raise SystemExit("Nenhum executável encontrado em " + a.files_dir)
    data = {"version": a.version, "changelog": a.changelog.replace("\\n", "\n"), "downloads": downloads}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {out} (v{a.version}, plataformas: {', '.join(downloads)})")


if __name__ == "__main__":
    main()
