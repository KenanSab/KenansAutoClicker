"""Shared fixtures.

The window is built **once** for the whole session. Creating and destroying a
Tk root repeatedly aborts the interpreter on macOS, so instead of a fresh app
per test we reset the app's state before each one.
"""

import os
import sys
import tkinter as tk

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def _root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:                    # headless CI with no display
        pytest.skip(f"no display available: {exc}")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture(scope="session")
def _app(_root, tmp_path_factory):
    """The one application instance, pointed at throwaway config files."""
    tmp = tmp_path_factory.mktemp("kac")
    from kenansautoclicker import presets as presets_mod, storage
    storage.CONFIG_PATH = str(tmp / "cfg.json")
    presets_mod.LOCAL_PRESET_PATH = str(tmp / "presets.json")

    from kenansautoclicker.app import AutoClickerApp
    instance = AutoClickerApp(_root)
    _root.update()
    instance._defaults = {name: var.get() for name, var in instance.vars.items()}
    return instance


@pytest.fixture
def app(_app):
    """The app, returned to a known state before and after each test."""
    _reset(_app)
    yield _app
    _reset(_app)


def _reset(instance):
    instance.stop_all()
    instance.scroll_active = False
    for name, value in instance._defaults.items():
        try:
            instance.vars[name].set(value)
        except tk.TclError:
            pass
    instance.points = []
    instance.total_clicks = 0
    instance.run_clicks = 0
    instance.recording_target = None
    instance.community_presets = []
    instance._sync_flags()
    instance._refresh_points()
    instance._refresh_target_ui()
    instance._refresh_key_ui()
    instance._refresh_limit_ui()
    instance._refresh_action_ui()
    instance.show_page("home")
    if instance.theme_name != "dark":
        instance.toggle_theme()
    try:
        instance.root.withdraw()
        instance.root.update()
    except tk.TclError:
        pass
