"""Publica uma build do Eldervale: gera o .zip, calcula SHA-256 e atualiza version_manifest.json.

Exemplo:
  python tools/publish.py --version 1.2.0 --platform windows --build-dir build/win \
      --exe Eldervale.exe --base-url https://meusite.com/eldervale \
      --changelog "- Nova região: Vale das Brumas\n- Correções de bugs"
Depois envie a pasta --out (padrão: server/) para o seu hospedamento.
"""
import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--type", default="release", choices=["release", "beta", "snapshot"])
    ap.add_argument("--platform", required=True, choices=["windows", "linux", "macos"])
    ap.add_argument("--build-dir", required=True)
    ap.add_argument("--exe", required=True, help="caminho do executável dentro da build")
    ap.add_argument("--changelog", default="", help="texto, ou @arquivo.txt")
    ap.add_argument("--out", default="docs", help="pasta do manifesto (servida pelo GitHub Pages)")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--zip-dir", default=None, help="onde salvar o .zip (padrão: <out>/downloads)")
    ap.add_argument("--download-base-url", default=None,
                    help="prefixo da URL pública do .zip. No GitHub: "
                         "https://github.com/USUARIO/REPO/releases/download/v1.0.0")
    ap.add_argument("--no-latest", action="store_true", help="não marcar como 'última versão'")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    zip_dir = Path(a.zip_dir) if a.zip_dir else out / "downloads"
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_path = zip_dir / f"eldervale-{a.version}-{a.platform}.zip"
    download_base = (a.download_base_url or f"{a.base_url.rstrip('/')}/downloads").rstrip("/")
    build = Path(a.build_dir)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(build.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(build).as_posix())

    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    mpath = out / "version_manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {"latest": {"release": None}, "versions": []}

    entry = next((v for v in manifest["versions"] if v["id"] == a.version), None)
    if not entry:
        entry = {"id": a.version, "type": a.type, "releaseTime": datetime.now(timezone.utc).isoformat(timespec="seconds"), "downloads": {}}
        manifest["versions"].append(entry)
    changelog = a.changelog
    if changelog.startswith("@"):
        changelog = Path(changelog[1:]).read_text(encoding="utf-8")
    if changelog:
        entry["changelog"] = changelog.replace("\\n", "\n")
    entry["downloads"][a.platform] = {
        "url": f"{download_base}/{zip_path.name}",
        "sha256": sha,
        "size": zip_path.stat().st_size,
        "executable": a.exe,
    }
    if a.type == "release" and not a.no_latest:
        manifest["latest"]["release"] = a.version
    manifest["versions"].sort(key=lambda v: v["releaseTime"], reverse=True)
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {zip_path.name}  sha256={sha[:12]}…  manifesto atualizado em {mpath}")


if __name__ == "__main__":
    main()
