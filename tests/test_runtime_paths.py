"""Installed vs. checkout layout: base dir, bundled tools, health and shutdown endpoints."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from storyboard_tool import __version__, runtime_paths
from storyboard_tool import api as api_module
from storyboard_tool import server


def test_checkout_keeps_repo_root_as_base_dir() -> None:
    assert not runtime_paths.is_packaged()
    assert runtime_paths.default_base_dir() == runtime_paths.code_root()


def test_installed_layout_uses_per_user_base_dir(tmp_path, monkeypatch) -> None:
    (tmp_path / runtime_paths.PACKAGED_MARKER).write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")
    monkeypatch.setattr(runtime_paths, "code_root", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert runtime_paths.is_packaged()
    if sys.platform == "win32":
        assert runtime_paths.default_base_dir() == tmp_path / "Roaming" / "StoryboardTool"
    assert runtime_paths.default_base_dir().name == "StoryboardTool"


def test_bundled_tool_wins_over_path(tmp_path, monkeypatch) -> None:
    exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    (tmp_path / exe).write_bytes(b"")
    monkeypatch.setenv(runtime_paths.TOOLS_DIR_ENV, str(tmp_path))
    assert runtime_paths.find_ffmpeg() == str(tmp_path / exe)


def test_missing_bundled_tool_falls_back_to_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(runtime_paths.TOOLS_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(runtime_paths.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert runtime_paths.find_ffprobe() == "/usr/bin/ffprobe"


@pytest.mark.parametrize(
    ("encoders", "expected"),
    [
        (frozenset({"libx264", "libopenh264"}), "libx264"),
        (frozenset({"libopenh264", "h264_mf"}), "libopenh264"),
        (frozenset({"h264_mf"}), "h264_mf"),
    ],
)
def test_h264_encoder_follows_the_build(monkeypatch, encoders, expected) -> None:
    monkeypatch.setattr(runtime_paths, "_encoders", lambda _ffmpeg: encoders)
    args = runtime_paths.h264_encoder_args("ffmpeg")
    assert args[args.index("-c:v") + 1] == expected


def test_health_endpoint(tmp_path) -> None:
    with TestClient(api_module.create_app(tmp_path)) as client:
        body = client.get("/api/health").json()
    assert body == {"ok": True, "app": "nihilux", "version": __version__, "packaged": False}


def test_shutdown_requires_launch_token(tmp_path, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.delenv("STORYBOARDER_LAUNCH_TOKEN", raising=False)
    app = api_module.create_app(tmp_path)
    app.state.request_shutdown = lambda: calls.append("stop")
    with TestClient(app) as client:
        assert client.post("/api/app/shutdown").status_code == 404
    assert calls == []

    monkeypatch.setenv("STORYBOARDER_LAUNCH_TOKEN", "tok123")
    app = api_module.create_app(tmp_path)
    app.state.request_shutdown = lambda: calls.append("stop")
    with TestClient(app) as client:
        assert client.post("/api/app/shutdown").status_code == 403
        ok = client.post("/api/app/shutdown", headers={"x-storyboarder-token": "tok123"})
    assert ok.status_code == 200 and calls == ["stop"]


def test_server_arguments(tmp_path) -> None:
    args = server._parse_args(["--base-dir", str(tmp_path), "--token", "abc", "--window-pid", "12"])
    assert args.base_dir == Path(tmp_path) and args.token == "abc" and args.window_pid == 12 and args.port == 0
