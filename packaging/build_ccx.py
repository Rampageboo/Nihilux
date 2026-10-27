"""Package the Photoshop UXP plugin folder as a .ccx (a zip with manifest.json at its root).

    python packaging/build_ccx.py photoshop_uxp_plugin <out.ccx>

Double-clicking the .ccx installs it through Creative Cloud. Only the plugin's own
files go in: no older .ccx, no READMEs of other tools, no caches.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

SKIP_SUFFIXES = {".ccx", ".pyc"}
SKIP_DIRS = {"__pycache__", "node_modules", ".git"}


def build(source: Path, target: Path) -> list[str]:
    if not (source / "manifest.json").is_file():
        raise SystemExit(f"no manifest.json in {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if path.is_dir() or path.suffix.lower() in SKIP_SUFFIXES or SKIP_DIRS & set(relative.parts):
                continue
            name = relative.as_posix()
            archive.write(path, name)
            names.append(name)
    return names


if __name__ == "__main__":
    files = build(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"{sys.argv[2]}: {len(files)} files")
