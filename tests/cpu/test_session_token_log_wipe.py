"""The one-time wipe of session tokens from old Control Center logs
(OWNER_TOKEN_LOG_WIPE_20261022: "wipe")."""

from scripts.dev.miner_launchpad import controller

OLD = "old-token-" + "x" * 40


def _install(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "session-token").write_text(OLD + "\n", encoding="ascii")
    (state / "control-center.log").write_text(
        "Control Center on http://127.0.0.1:8788\n"
        f"Open (this link holds your session token; do not share): http://127.0.0.1:8788/#t={OLD}\n"
        f"Local session token (paste into page; do not share): {OLD}\n"
        f"a debug line that happens to quote {OLD}\n"
        "Set up your environment, then choose a Challenge and launch.\n",
        encoding="utf-8",
    )
    (state / "control-center.log.1").write_text(
        f"Local session token (paste into page; do not share): {OLD}\n"
        "an older, ordinary line\n",
        encoding="utf-8",
    )
    return state


def test_an_update_wipes_the_logged_token_and_rotates_it(tmp_path):
    state = _install(tmp_path)
    log = state / "control-center.log"
    inode = log.stat().st_ino
    assert controller.wipe_logged_token(state) is True
    for name in ("control-center.log", "control-center.log.1"):
        text = (state / name).read_text(encoding="utf-8")
        assert OLD not in text and "Local session token (paste" not in text
        assert "[session token removed from this log]" in text
    kept = log.read_text(encoding="utf-8")
    assert "Control Center on http://127.0.0.1:8788" in kept
    assert "Set up your environment" in kept
    # In place, so a running service keeps appending to the same file.
    assert log.stat().st_ino == inode
    assert "an older, ordinary line" in (state / "control-center.log.1").read_text(
        encoding="utf-8"
    )
    marker = state / controller.TOKEN_WIPE_MARKER
    assert marker.stat().st_mode & 0o777 == 0o600
    fresh = controller.session_token(state)
    assert fresh != OLD and len(fresh) >= 32
    assert (state / "session-token").stat().st_mode & 0o777 == 0o600


def test_the_wipe_runs_once(tmp_path):
    state = _install(tmp_path)
    assert controller.wipe_logged_token(state) is True
    fresh = controller.session_token(state)
    assert controller.wipe_logged_token(state) is False
    assert controller.session_token(state) == fresh


def test_a_fresh_install_has_nothing_to_wipe(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    assert controller.wipe_logged_token(state) is True
    assert sorted(p.name for p in state.iterdir()) == [controller.TOKEN_WIPE_MARKER]
    assert controller.wipe_logged_token(state) is False


def test_a_symlinked_log_is_not_followed(tmp_path):
    state = _install(tmp_path)
    outside = tmp_path / "elsewhere.log"
    outside.write_text(f"{OLD}\n", encoding="utf-8")
    (state / "control-center.log.2").symlink_to(outside)
    assert controller.wipe_logged_token(state) is True
    assert outside.read_text(encoding="utf-8") == f"{OLD}\n"
