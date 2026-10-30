"""A server miner who joins the docker group is told what actually clears the check (clean-machine N1).

On a server the user's systemd manager is usually already running when the group is joined, so a new login alone does not give the
service the group: the installer's two Docker messages and the guide all say to restart that manager (or log out of every session,
or reboot)."""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "scripts/install_miner.sh").read_text(encoding="utf-8")
GUIDE = (ROOT / "docs/MINING.md").read_text(encoding="utf-8")
RESTART = "sudo systemctl restart user@$(id -u).service"


def test_the_permission_denied_message_names_the_manager_restart():
    start = SCRIPT.index("your user is not allowed to use it (permission denied)")
    message = SCRIPT[start : SCRIPT.index("\n", start)]
    assert "log out of every session for this user" in message
    assert RESTART in message and "reboot" in message


def test_the_manager_check_message_names_the_restart_a_login_and_a_reboot():
    start = SCRIPT.index('restart="Run: ' + RESTART)
    message = SCRIPT[start : SCRIPT.index("\n", start)]
    assert "log out of every session for this user" in message and "reboot" in message


def test_the_guide_says_the_same():
    assert "log out of every session for this user and in again" in GUIDE
    assert RESTART in GUIDE
