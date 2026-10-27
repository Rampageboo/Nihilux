"""Focus requests restore and activate the app window by process id (window_focus)."""
from __future__ import annotations

import pytest

from storyboard_tool import window_focus


class FakeApi:
    def __init__(self, *, hwnd: int | None = 7, minimized: bool = False, maximized_after_restore: bool = False,
                 fail_restore: bool = False, activate_ok: bool = True) -> None:
        self.hwnd = hwnd
        self.minimized = minimized
        self.maximized = False
        self.maximized_after_restore = maximized_after_restore
        self.fail_restore = fail_restore
        self.activate_ok = activate_ok
        self.calls: list[str] = []

    def find_window(self, pid: int) -> int | None:
        self.calls.append(f"find:{pid}")
        return self.hwnd

    def is_minimized(self, hwnd: int) -> bool:
        return self.minimized

    def is_maximized(self, hwnd: int) -> bool:
        return self.maximized

    def restore(self, hwnd: int) -> None:
        self.calls.append("restore")
        if self.fail_restore:
            raise OSError("restore failed")
        self.minimized = False
        self.maximized = self.maximized_after_restore

    def activate(self, hwnd: int) -> bool:
        self.calls.append("activate")
        return self.activate_ok


@pytest.fixture
def fake(request):
    api = FakeApi(**getattr(request, "param", {}))
    window_focus.set_window_api(api)
    yield api
    window_focus.set_window_api(None)


def test_no_window_pid_is_a_noop(fake) -> None:
    result = window_focus.focus_process_window(None)
    assert result["ok"] and not result["focused"] and fake.calls == []


@pytest.mark.parametrize("fake", [{"hwnd": None}], indirect=True)
def test_missing_window_reports_not_found(fake) -> None:
    result = window_focus.focus_process_window(99)
    assert result["ok"] and not result["focused"]
    assert result["errors"] == ["window_not_found"]


def test_normal_window_is_activated_without_restore(fake) -> None:
    result = window_focus.focus_process_window(99)
    assert fake.calls == ["find:99", "activate"]
    assert result["focused"] and not result["restored_from_minimized"]
    assert result["window_state_before"] == result["window_state_after"] == "normal"


@pytest.mark.parametrize("fake", [{"minimized": True, "maximized_after_restore": True}], indirect=True)
def test_minimized_maximized_window_returns_maximized(fake) -> None:
    result = window_focus.focus_process_window(99)
    assert fake.calls == ["find:99", "restore", "activate"]
    assert result["restored_from_minimized"] and result["remaximized"]
    assert result["window_state_before"] == "minimized"
    assert result["window_state_after"] == "maximized"


@pytest.mark.parametrize("fake", [{"minimized": True}], indirect=True)
def test_minimized_normal_window_returns_normal(fake) -> None:
    result = window_focus.focus_process_window(99)
    assert result["restored_from_minimized"] and not result["remaximized"]
    assert result["window_state_after"] == "normal"


@pytest.mark.parametrize("fake", [{"minimized": True, "fail_restore": True}], indirect=True)
def test_restore_failure_still_activates_and_never_raises(fake) -> None:
    result = window_focus.focus_process_window(99)
    assert "activate" in fake.calls
    assert result["ok"] and "restore_failed" in result["errors"]
    assert result["window_state_after"] == "minimized"


def test_focus_endpoint_uses_window_pid(tmp_path, fake) -> None:
    from fastapi.testclient import TestClient

    from storyboard_tool import api as api_module

    app = api_module.create_app(tmp_path)
    app.state.window_pid = 1234
    with TestClient(app) as client:
        body = client.post("/api/app/focus").json()
    assert body["focused"] and fake.calls[0] == "find:1234"
