"""Settings → Integrations: the MCP config, the Photoshop plugin and the Blender add-on.

The installed app ships the Photoshop plugin as a ``.ccx`` (``app/integrations/photoshop``)
and the Blender add-on inside the package; a checkout has the plugin folder instead,
loaded with Adobe's UXP Developer Tool. The MCP config points an agent (Claude Code,
Codex) at this app's own Python, so it works without a checkout.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from . import runtime_paths

MCP_SERVER_NAME = "nihilux"


def _plain(path: str) -> str:
    """Drop a Windows verbatim prefix (``\\\\?\\``) so MCP clients get an ordinary path."""
    if path.startswith("\\\\?\\") and not path.startswith("\\\\?\\UNC\\"):
        return path[4:]
    return path


def python_executable() -> str:
    """A console interpreter for stdio MCP servers (never pythonw.exe)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        candidate = exe.with_name("python.exe")
        if candidate.is_file():
            exe = candidate
    return _plain(str(exe))


def mcp_config() -> dict[str, Any]:
    code_root = _plain(str(runtime_paths.code_root()))
    return {
        "mcpServers": {
            MCP_SERVER_NAME: {
                "type": "stdio",
                "command": python_executable(),
                "args": ["-m", "storyboard_tool.mcp_server"],
                "env": {"PYTHONPATH": code_root, "PYTHONNOUSERSITE": "1"},
            }
        }
    }


def photoshop_plugin_path() -> Path | None:
    """The bundled .ccx when installed, else the plugin source folder of a checkout."""
    root = runtime_paths.code_root()
    bundled = sorted((root / "integrations" / "photoshop").glob("*.ccx"))
    if bundled:
        return bundled[0]
    folder = root / "photoshop_uxp_plugin"
    return folder if folder.is_dir() else None


def blender_addon_dir() -> Path:
    return Path(__file__).resolve().parent / "blender_addon"


def info() -> dict[str, Any]:
    plugin = photoshop_plugin_path()
    return {
        "packaged": runtime_paths.is_packaged(),
        "mcp_config": mcp_config(),
        "photoshop_plugin": str(plugin) if plugin else "",
        "photoshop_plugin_kind": ("ccx" if plugin and plugin.suffix == ".ccx" else "folder") if plugin else "",
        "blender_addon_dir": str(blender_addon_dir()),
    }


def open_target(target: str) -> str:
    """Open the .ccx (Creative Cloud installs it) or show a folder. Returns the path."""
    if target == "photoshop_plugin":
        path = photoshop_plugin_path()
    elif target == "blender_addon":
        path = blender_addon_dir()
    else:
        raise ValueError(f"Unknown integration: {target}")
    if path is None or not path.exists():
        raise FileNotFoundError("This integration is not available in this build.")
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        import subprocess

        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
    return str(path)
