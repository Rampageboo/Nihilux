"""Where the running app keeps its state and finds its bundled tools.

Two layouts:

- **Source checkout** (development): the code root is the repository, per-user
  state (``Sessions/``) sits in it as before, and ffmpeg comes from PATH.
- **Installed** (the Nihilux installer): the code root is ``<install>/app``, which
  holds a ``packaged.json`` marker written by ``packaging/stage.ps1``. An update
  replaces the install folder, so per-user state lives in
  ``%APPDATA%\\StoryboardTool`` instead, and ffmpeg/ffprobe ship in
  ``<install>/app/bin``.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path

APP_DATA_DIRNAME = "StoryboardTool"
PACKAGED_MARKER = "packaged.json"
# Overrides the bundled-tools folder (tests, unusual layouts).
TOOLS_DIR_ENV = "STORYBOARDER_TOOLS_DIR"


def code_root() -> Path:
    """The folder that contains the ``storyboard_tool`` package."""
    return Path(__file__).resolve().parents[1]


def packaged_info() -> dict | None:
    marker = code_root() / PACKAGED_MARKER
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else {}


def is_packaged() -> bool:
    return packaged_info() is not None


def user_data_dir() -> Path:
    """Per-user state of the installed app: ``%APPDATA%\\StoryboardTool``."""
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root / APP_DATA_DIRNAME


def default_base_dir() -> Path:
    """``create_app``'s base dir: per-user when installed, the checkout otherwise."""
    return user_data_dir() if is_packaged() else code_root()


def bundled_tools_dir() -> Path:
    override = os.environ.get(TOOLS_DIR_ENV, "").strip()
    return Path(override) if override else code_root() / "bin"


def find_tool(name: str) -> str | None:
    """Path of an external tool (``ffmpeg``, ``ffprobe``): bundled first, then PATH."""
    exe = f"{name}.exe" if sys.platform == "win32" else name
    bundled = bundled_tools_dir() / exe
    if bundled.is_file():
        return str(bundled)
    return shutil.which(name)


def find_ffmpeg() -> str | None:
    return find_tool("ffmpeg")


def find_ffprobe() -> str | None:
    return find_tool("ffprobe")


@lru_cache(maxsize=8)
def _encoders(ffmpeg: str) -> frozenset[str]:
    import subprocess

    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True, text=True, check=False, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    names = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        # Encoder rows look like " V....D libx264  description".
        if len(parts) >= 2 and len(parts[0]) == 6 and parts[0][0] in "VAS":
            names.add(parts[1])
    return frozenset(names)


def h264_encoder_args(ffmpeg: str) -> list[str]:
    """Video codec arguments for an H.264 MP4 with the encoder this ffmpeg has.

    A PATH ffmpeg is usually a GPL build with libx264. The installer ships an LGPL
    build, which has no libx264; it encodes with OpenH264 or Windows' Media
    Foundation encoder instead.
    """
    encoders = _encoders(ffmpeg)
    if "libx264" in encoders or not encoders:
        return ["-c:v", "libx264", "-preset", "medium"]
    if "libopenh264" in encoders:
        return ["-c:v", "libopenh264", "-b:v", "8M"]
    if "h264_mf" in encoders:
        return ["-c:v", "h264_mf", "-b:v", "8M"]
    return ["-c:v", "libx264", "-preset", "medium"]
