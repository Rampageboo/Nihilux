"""Bring the app window to the front for the Photoshop plugin's "focus app" request.

The window belongs to another process (the Nihilux desktop shell) or, in the
pywebview development launcher, to this one. Either way the backend knows the
owning process id (``app.state.window_pid``) and finds its top-level window with
Win32 calls, so it does not need a handle to a GUI toolkit object.

A minimized window is restored with ``SW_RESTORE``, which returns it to the state
it had before minimizing (maximized stays maximized). A normal or maximized
window is never resized: it is only activated.
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class WindowApi(Protocol):
    def find_window(self, pid: int) -> int | None: ...
    def is_minimized(self, hwnd: int) -> bool: ...
    def is_maximized(self, hwnd: int) -> bool: ...
    def restore(self, hwnd: int) -> None: ...
    def activate(self, hwnd: int) -> bool: ...


class _Win32WindowApi:
    """Thin ctypes wrapper over user32. Only constructed on Windows."""

    SW_RESTORE = 9
    GW_OWNER = 4
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    VK_MENU = 0x12

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._wintypes = wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._user32 = user32
        self._enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [self._enum_proc, wintypes.LPARAM]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        for name in ("IsWindowVisible", "IsIconic", "IsZoomed", "SetForegroundWindow", "BringWindowToTop"):
            getattr(user32, name).argtypes = [wintypes.HWND]
            getattr(user32, name).restype = wintypes.BOOL
        user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetWindow.restype = wintypes.HWND
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_void_p]

    def find_window(self, pid: int) -> int | None:
        found: list[int] = []
        wintypes = self._wintypes
        user32 = self._user32

        def callback(hwnd, _lparam):
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, self._ctypes.byref(owner))
            if owner.value != pid:
                return True
            # The app window: top-level (no owner), titled, and shown or minimized.
            if user32.GetWindow(hwnd, self.GW_OWNER):
                return True
            if user32.GetWindowTextLengthW(hwnd) <= 0:
                return True
            if not (user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd)):
                return True
            found.append(int(hwnd))
            return False

        user32.EnumWindows(self._enum_proc(callback), 0)
        return found[0] if found else None

    def is_minimized(self, hwnd: int) -> bool:
        return bool(self._user32.IsIconic(hwnd))

    def is_maximized(self, hwnd: int) -> bool:
        return bool(self._user32.IsZoomed(hwnd))

    def restore(self, hwnd: int) -> None:
        self._user32.ShowWindow(hwnd, self.SW_RESTORE)

    def activate(self, hwnd: int) -> bool:
        user32 = self._user32
        if user32.SetForegroundWindow(hwnd):
            return True
        # Windows only lets the foreground process hand over focus. A synthetic Alt
        # tap counts as user input and lifts that lock (the same thing the Tauri
        # window's set_focus does), then the request is repeated.
        user32.keybd_event(self.VK_MENU, 0, 0, None)
        user32.keybd_event(self.VK_MENU, 0, self.KEYEVENTF_KEYUP, None)
        user32.BringWindowToTop(hwnd)
        return bool(user32.SetForegroundWindow(hwnd))


_api: WindowApi | None = None


def _window_api() -> WindowApi | None:
    global _api
    if _api is None and sys.platform == "win32":
        try:
            _api = _Win32WindowApi()
        except Exception:
            logger.debug("Win32 window API unavailable", exc_info=True)
            return None
    return _api


def set_window_api(api: WindowApi | None) -> None:
    """Tests replace the Win32 layer with a fake."""
    global _api
    _api = api


def _result(**fields: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": True,
        "window_found": False,
        "shown": False,
        "activation_requested": False,
        "focused": False,
        "restored_from_minimized": False,
        "remaximized": False,
        "window_state_before": "unknown",
        "window_restore_state_before": "unknown",
        "window_state_after": "unknown",
        "errors": [],
    }
    result.update(fields)
    return result


def _state(api: WindowApi, hwnd: int) -> str:
    if api.is_minimized(hwnd):
        return "minimized"
    return "maximized" if api.is_maximized(hwnd) else "normal"


def focus_process_window(pid: int | None) -> dict[str, Any]:
    """Best effort: restore (if minimized) and activate the window owned by ``pid``.

    Never raises. Without a known window (browser development, other platforms)
    the result says nothing was done.
    """
    if not pid:
        return _result()
    api = _window_api()
    if api is None:
        return _result(errors=["window_api_unavailable"])
    errors: list[str] = []
    try:
        hwnd = api.find_window(int(pid))
    except Exception:
        logger.debug("Window lookup failed", exc_info=True)
        return _result(errors=["find_window_failed"])
    if not hwnd:
        return _result(errors=["window_not_found"])

    before = _state(api, hwnd)
    restored = False
    if before == "minimized":
        try:
            api.restore(hwnd)
            restored = True
        except Exception:
            errors.append("restore_failed")
            logger.debug("Window restore failed", exc_info=True)
    focused = False
    try:
        focused = api.activate(hwnd)
    except Exception:
        errors.append("activate_failed")
        logger.debug("Window activation failed", exc_info=True)
    after = _state(api, hwnd)
    return _result(
        window_found=True,
        shown=True,
        activation_requested=True,
        focused=focused,
        restored_from_minimized=restored,
        remaximized=restored and after == "maximized",
        window_state_before=before,
        # SW_RESTORE brings back the pre-minimize state; report what it became.
        window_restore_state_before=after if before == "minimized" else before,
        window_state_after=after,
        errors=errors,
    )
