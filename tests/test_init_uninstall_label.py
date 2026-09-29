"""`fidelis init --uninstall` must target the unit that `fidelis init` installs.

Install names the systemd unit after ``SERVICE_LABEL`` (or ``--label``); uninstall
used to look for a bare ``fidelis-server`` unit, so it reported "no service
installed" and left the real service enabled. Tests use a temp home and a recorded
fake ``subprocess.run``: no real systemctl/launchctl call, no real service touched.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from fidelis import init_cmd


@pytest.fixture
def linux_env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".config/systemd/user").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(init_cmd.platform, "system", lambda: "Linux")
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(init_cmd.subprocess, "run", fake_run)
    return home, calls


def _unit(home: Path, label: str) -> Path:
    path = home / ".config/systemd/user" / f"{label}.service"
    path.write_text("[Service]\nExecStart=/bin/true\n")
    return path


def _args(**kw) -> argparse.Namespace:
    base = {"uninstall": True, "label": None, "migrate": False, "port": None, "force": False, "dry_run": False}
    base.update(kw)
    return argparse.Namespace(**base)


def test_uninstall_removes_the_default_unit_that_init_installs(linux_env):
    home, calls = linux_env
    unit = _unit(home, init_cmd.SERVICE_LABEL)
    assert init_cmd.cmd_init(_args()) == 0
    assert not unit.exists()
    assert ["systemctl", "--user", "stop", f"{init_cmd.SERVICE_LABEL}.service"] in calls
    assert ["systemctl", "--user", "disable", f"{init_cmd.SERVICE_LABEL}.service"] in calls


def test_uninstall_honours_custom_label(linux_env):
    home, calls = linux_env
    default = _unit(home, init_cmd.SERVICE_LABEL)
    custom = _unit(home, "fidelis-second")
    assert init_cmd.cmd_init(_args(label="fidelis-second")) == 0
    assert not custom.exists()
    assert default.exists(), "an explicit --label must not remove the default unit"
    assert ["systemctl", "--user", "stop", "fidelis-second.service"] in calls


def test_uninstall_still_removes_a_bare_legacy_unit(linux_env):
    home, calls = linux_env
    legacy = _unit(home, "fidelis-server")
    assert init_cmd.cmd_init(_args()) == 0
    assert not legacy.exists()
    assert ["systemctl", "--user", "stop", "fidelis-server.service"] in calls


def test_empty_label_means_default_as_on_install(linux_env):
    home, _ = linux_env
    unit = _unit(home, init_cmd.SERVICE_LABEL)
    assert init_cmd.cmd_init(_args(label="")) == 0
    assert not unit.exists()
