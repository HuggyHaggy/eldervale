"""Troca LAUNCHER_VERSION em eldervale_launcher/config.py (usado pelo GitHub Actions)."""
import re
import sys
from pathlib import Path

version = sys.argv[1]
p = Path("eldervale_launcher/config.py")
text = p.read_text(encoding="utf-8")
new, n = re.subn(r'LAUNCHER_VERSION = "[^"]*"', f'LAUNCHER_VERSION = "{version}"', text)
if n != 1:
    raise SystemExit("LAUNCHER_VERSION não encontrado em config.py")
p.write_text(new, encoding="utf-8")
print("LAUNCHER_VERSION =", version)
