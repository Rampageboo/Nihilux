"""Headless backend for the Nihilux desktop shell.

    python -m storyboard_tool.server --base-dir <dir> [--port 0] [--window-pid <pid>]

The shell (``desktop/src-tauri``) starts this with its bundled Python, passes the
per-launch API token in ``STORYBOARDER_LAUNCH_TOKEN`` (``--token`` also works),
waits for ``GET /api/health`` and then points its window at the printed address.
The first stdout line is ``PORT:<n>`` once the server accepts connections.

``POST /api/app/shutdown`` (token required) stops the server gracefully, so the
FastAPI lifespan stops its background loops and flushes the Blender session
before the shell ends the process tree (on exit and before installing an update).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import threading
import time
from pathlib import Path

HOST = "127.0.0.1"
WINDOW_PID_ENV = "STORYBOARDER_WINDOW_PID"
_LOGGER = logging.getLogger(__name__)


def wait_for_server(host: str, port: int, timeout: float = 15.0) -> None:
    import urllib.request

    from .live_bridge import server_identity_url

    deadline = time.time() + timeout
    url = server_identity_url(host, port)
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except Exception:
            # intentional: poll until the local server accepts connections
            pass
        time.sleep(0.1)
    raise RuntimeError(f"Nihilux server did not start on http://{host}:{port}")


def ignore_connection_reset(loop, context) -> None:
    exc = context.get("exception")
    if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
        return
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) in (10053, 10054):
        return
    message = str(context.get("message", ""))
    if "_call_connection_lost" in message:
        return
    loop.default_exception_handler(context)


def configure_windows_asyncio_noise() -> None:
    """Silence the proactor's ConnectionReset tracebacks when a client disconnects."""
    if sys.platform != "win32":
        return
    import asyncio.proactor_events

    try:
        asyncio.get_event_loop().set_exception_handler(ignore_connection_reset)
    except RuntimeError:
        pass

    transport_cls = getattr(asyncio.proactor_events, "_ProactorBasePipeTransport", None)
    if transport_cls is None or getattr(transport_cls, "_storyboard_patched", False):
        return
    original = getattr(transport_cls, "_call_connection_lost", None)
    if original is None:
        _LOGGER.warning("asyncio proactor transport patch skipped: _call_connection_lost is unavailable")
        return

    def _quiet_call_connection_lost(self, exc):
        try:
            original(self, exc)
        except ConnectionResetError:
            pass
        except OSError as os_err:
            if getattr(os_err, "winerror", None) not in (10053, 10054):
                raise

    transport_cls._call_connection_lost = _quiet_call_connection_lost
    transport_cls._storyboard_patched = True


def build_server(app, host: str, port: int):
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    # Lets POST /api/app/shutdown end the server the same way Ctrl+C would.
    app.state.request_shutdown = lambda: setattr(server, "should_exit", True)
    return server


def run_server_in_thread(server) -> threading.Thread:
    def run() -> None:
        configure_windows_asyncio_noise()
        if sys.platform == "win32":
            loop = asyncio.new_event_loop()
            loop.set_exception_handler(ignore_connection_reset)
            asyncio.set_event_loop(loop)
        server.run()

    thread = threading.Thread(target=run, name="storyboard-server", daemon=True)
    thread.start()
    return thread


def start_internal_server(app, host: str = HOST, port: int = 0) -> tuple[threading.Thread, int]:
    """Start the localhost server in a thread and wait until it answers."""
    from .live_bridge import resolve_server_port

    if port <= 0:
        port = resolve_server_port(host, port)
    app.state.bridge_port = port
    thread = run_server_in_thread(build_server(app, host, port))
    wait_for_server(host, port)
    return thread, port


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m storyboard_tool.server")
    parser.add_argument("--base-dir", type=Path, default=None,
                        help="Per-user state folder (Sessions/). Default: %%APPDATA%%\\StoryboardTool "
                             "when installed, the checkout otherwise.")
    parser.add_argument("--port", type=int, default=0, help="0 picks a free port.")
    parser.add_argument("--token", default=None,
                        help="Per-launch API token (default: STORYBOARDER_LAUNCH_TOKEN).")
    parser.add_argument("--window-pid", type=int, default=None,
                        help=f"Process owning the app window, for focus requests (default: {WINDOW_PID_ENV}).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.token is not None:
        # api._read_launch_token reads the environment; keep one source of truth.
        os.environ["STORYBOARDER_LAUNCH_TOKEN"] = args.token

    from . import runtime_paths
    from .api import create_app
    from .live_bridge import publish, resolve_server_port

    base_dir = (args.base_dir or runtime_paths.default_base_dir()).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    app = create_app(base_dir)

    window_pid = args.window_pid
    if window_pid is None:
        raw = os.environ.get(WINDOW_PID_ENV, "").strip()
        window_pid = int(raw) if raw.isdigit() else None
    app.state.window_pid = window_pid

    try:
        port = resolve_server_port(HOST, args.port)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    app.state.bridge_port = port
    publish(base_dir, None, port=port)

    server = build_server(app, HOST, port)
    thread = run_server_in_thread(server)
    try:
        wait_for_server(HOST, port, timeout=60.0)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    sys.stdout.write(f"PORT:{port}\n")
    sys.stdout.flush()
    try:
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
