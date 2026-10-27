"""Settings → Integrations: MCP config, Photoshop plugin and Blender add-on paths."""
from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from storyboard_tool import api as api_module
from storyboard_tool import integrations, runtime_paths


def test_mcp_config_runs_this_python_on_this_code(tmp_path) -> None:
    server = integrations.mcp_config()["mcpServers"]["nihilux"]
    assert server["args"] == ["-m", "storyboard_tool.mcp_server"]
    assert server["env"]["PYTHONPATH"] == str(runtime_paths.code_root())
    assert not server["command"].lower().endswith("pythonw.exe")


def test_checkout_offers_the_plugin_folder() -> None:
    info = integrations.info()
    assert info["photoshop_plugin_kind"] == "folder"
    assert info["photoshop_plugin"].endswith("photoshop_uxp_plugin")
    assert info["blender_addon_dir"].endswith("blender_addon")


def test_installed_layout_offers_the_ccx(tmp_path, monkeypatch) -> None:
    ccx = tmp_path / "integrations" / "photoshop" / "plugin_PS.ccx"
    ccx.parent.mkdir(parents=True)
    ccx.write_bytes(b"PK")
    monkeypatch.setattr(runtime_paths, "code_root", lambda: tmp_path)
    assert integrations.photoshop_plugin_path() == ccx
    assert integrations.info()["photoshop_plugin_kind"] == "ccx"


def test_open_endpoint(tmp_path, monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(integrations.os, "startfile", lambda path: opened.append(path), raising=False)
    monkeypatch.setattr(integrations.sys, "platform", "win32")
    with TestClient(api_module.create_app(tmp_path)) as client:
        assert client.get("/api/app/integrations").json()["mcp_config"]["mcpServers"]["nihilux"]
        ok = client.post("/api/app/integrations/open", json={"target": "blender_addon"})
        bad = client.post("/api/app/integrations/open", json={"target": "nope"})
    assert ok.status_code == 200 and opened == [ok.json()["path"]]
    assert bad.status_code == 400
    assert sys.platform  # restored by monkeypatch


def test_verbatim_windows_paths_are_made_plain() -> None:
    assert integrations._plain(r"\\?\C:\Nihilux\python\python.exe") == r"C:\Nihilux\python\python.exe"
    assert integrations._plain(r"\\?\UNC\server\share") == r"\\?\UNC\server\share"
    assert integrations._plain(r"C:\a") == r"C:\a"
