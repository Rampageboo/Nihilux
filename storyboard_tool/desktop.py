"""Development launcher: a pywebview window over the local server (run.bat, Storyboarder.vbs).

The installed app uses the Tauri shell in ``desktop/src-tauri`` with
``storyboard_tool.server`` instead; pywebview is not part of the installer.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
from pathlib import Path

from . import app_state, project_manager, server
from .live_bridge import global_bridge_dir, resolve_server_port


# The desktop shell starts a private localhost server for the React bundle and API.
# This is an implementation detail for pywebview — not a supported browser workflow.
_HOST = "127.0.0.1"
_PORT = 0  # 0 = resolved dynamically at startup; see resolve_server_port()
ICON_PATH = Path(__file__).resolve().parent / "assets" / "icon.ico"
APP_USER_MODEL_ID = "StoryboardTool.StoryboardTool.1"
_WEBVIEW_STORAGE_WARNED_PATHS: set[str] = set()
_LOGGER = logging.getLogger(__name__)

# t0 is set at process entry; all stage timings are relative to it.
_t0: float = time.perf_counter()


def _log_stage(label: str) -> None:
    elapsed = time.perf_counter() - _t0
    _LOGGER.info("[startup] %+.3fs  %s", elapsed, label)


_TOKEN_RE_DESKTOP = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')


def _write_launch_ready_marker(source: str = "pywebview loaded fallback") -> None:
    """Write the per-launch ready marker as a fallback after the page has loaded."""
    token = os.environ.get("STORYBOARDER_LAUNCH_TOKEN", "").strip()
    if not token or not _TOKEN_RE_DESKTOP.match(token):
        return
    try:
        Path(tempfile.gettempdir()).joinpath(f"storyboarder-launch-{token}.ready").write_text(
            "ready", encoding="utf-8"
        )
        _log_stage(f"{source}: ready marker written")
    except OSError:
        pass


def _schedule_launch_ready_marker(source: str, delay_seconds: float) -> None:
    timer = threading.Timer(delay_seconds, lambda: _write_launch_ready_marker(source))
    timer.daemon = True
    timer.start()


def _configure_windows_taskbar_identity() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        # intentional: optional Windows shell API
        pass


def start_internal_server(app, host: str = _HOST, port: int = _PORT) -> tuple[threading.Thread, int]:
    """Start the private localhost server that pywebview loads. Not a public endpoint."""
    _log_stage("internal server thread starting")
    thread, port = server.start_internal_server(app, host, port)
    _log_stage("server ready")
    return thread, port


def webview_storage_path() -> Path:
    candidates = [
        global_bridge_dir() / "webview",
        Path(tempfile.gettempdir()) / "StoryboardTool" / "webview",
    ]
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            key = str(path)
            if key not in _WEBVIEW_STORAGE_WARNED_PATHS:
                _WEBVIEW_STORAGE_WARNED_PATHS.add(key)
                print(f"Webview storage path unavailable: {path} ({exc})", file=sys.stderr)
            continue
        return path
    return Path(tempfile.gettempdir())


def _window_state_path() -> Path:
    return global_bridge_dir() / "window_state.json"


def _load_window_state() -> dict | None:
    try:
        return json.loads(_window_state_path().read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_window_state(window, maximized: bool = False) -> None:
    try:
        state = {"width": window.width, "height": window.height, "maximized": maximized}
        _window_state_path().write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def open_desktop_window(app, title: str = "Nihilux") -> int:
    _log_stage("desktop process entered open_desktop_window")
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "Desktop mode requires pywebview. Install dependencies with: pip install -r requirements.txt"
        ) from exc

    from .live_bridge import publish

    try:
        port = resolve_server_port(_HOST, _PORT)
    except RuntimeError as exc:
        print(str(exc))
        return 1

    app.state.bridge_port = port
    publish(app.state.base_dir, None, port=port)

    start_internal_server(app, _HOST, port)
    _log_stage("pywebview window about to be created")
    react_index = Path(__file__).resolve().parent / "web" / "dist" / "index.html"
    if not react_index.is_file():
        print(
            "React build not found. Run: cd frontend && npm run build",
            file=sys.stderr,
        )
        return 1
    internal_app_url = f"http://{_HOST}:{port}/"
    _configure_windows_taskbar_identity()

    saved_state = _load_window_state()
    # Default to maximized; restore previous size only when user had explicitly unmaximized.
    restore_maximized = saved_state is None or saved_state.get("maximized", True)
    win_width = saved_state["width"] if saved_state and not restore_maximized else 1440
    win_height = saved_state["height"] if saved_state and not restore_maximized else 900

    window = webview.create_window(
        title,
        internal_app_url,
        width=win_width,
        height=win_height,
        min_size=(1024, 680),
        text_select=False,
    )
    # Focus requests find this window by process id (see window_focus).
    app.state.window_pid = os.getpid()
    # Last non-minimized state, saved on close for the next launch.
    restore_state = {"value": "maximized" if restore_maximized else "normal", "minimized": False}

    def _mark_minimized(*_args):
        restore_state["minimized"] = True

    def _mark_maximized(*_args):
        restore_state["value"] = "maximized"
        restore_state["minimized"] = False

    def _mark_restored(*_args):
        # Coming back from minimized keeps the earlier state; a restore from
        # maximized is the user un-maximizing.
        if not restore_state["minimized"]:
            restore_state["value"] = "normal"
        restore_state["minimized"] = False

    def _on_shown():
        if restore_maximized:
            try:
                window.maximize()
            except Exception:
                pass

    def _on_loaded():
        _write_launch_ready_marker("pywebview loaded fallback")

    finalized = threading.Event()

    def _finalize(source: str) -> None:
        """Stop background writers and clean orphan references. Runs exactly once.

        Every mutation is already on disk, so closing has nothing to save; this
        only makes sure no background writer touches the project afterwards.
        """
        if finalized.is_set():
            return
        finalized.set()
        project = app.state.project
        started = time.perf_counter()
        # Silence the bridge/generation watchers first: both write into the
        # project folder.
        app_state.stop_background_loops(app)
        try:
            project_manager.shutdown_reference_cleanup(project)
        except Exception as exc:
            print(f"Reference cleanup failed: {exc}", file=sys.stderr)
        _log_stage(f"project finalized via {source} in {(time.perf_counter() - started) * 1000:.0f} ms")

    def _on_closing():
        # Window is still up here: save its state, then stop project writers
        # before the close proceeds.
        _save_window_state(window, maximized=restore_state["value"] == "maximized")
        _finalize("window closing")
        return True

    window.events.shown += _on_shown
    try:
        window.events.closing += _on_closing
    except Exception:
        # Older pywebview builds without a closing event fall back to the
        # post-start() finalize below.
        pass
    try:
        window.events.minimized += _mark_minimized
        window.events.maximized += _mark_maximized
        window.events.restored += _mark_restored
    except Exception:
        pass  # older pywebview versions may not expose these events
    try:
        window.events.loaded += _on_loaded
    except Exception:
        # Older pywebview builds may not expose loaded. Do not close the splash
        # on shown; wait long enough for the local React bundle to render.
        window.events.shown += lambda: _schedule_launch_ready_marker("pywebview shown delayed fallback", 3.0)

    start_kwargs: dict = {
        "private_mode": False,
        "storage_path": str(webview_storage_path()),
    }
    if ICON_PATH.is_file():
        start_kwargs["icon"] = str(ICON_PATH.resolve())
    webview.start(**start_kwargs)

    # webview.start() blocks until the window closes. The closing event above has
    # normally already saved the window state and flushed the document; both steps
    # are repeated here only as a safety net for a close path that skipped it
    # (e.g. a pywebview build without a closing event).
    if not finalized.is_set():
        # Use restore_state (not current_state) so closing while minimized persists
        # the correct pre-minimized geometry for the next launch.
        _save_window_state(window, maximized=restore_state["value"] == "maximized")
        _finalize("post-start fallback")
    return 0
