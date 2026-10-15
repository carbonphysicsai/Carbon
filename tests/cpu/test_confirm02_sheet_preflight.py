"""A stale or incomplete copied operator sheet fails before host use."""

from __future__ import annotations

import pytest

from scripts.dev.battery import confirm02_sheet_preflight as preflight


@pytest.fixture
def sheet():
    return (
        "git clone --branch producer-code-r8.6 https://example.invalid/repo /opt/carbon-r86\n"
        "R=/opt/carbon-r86; cd $R\n"
        'test "$(git -C /opt/carbon-r86 rev-parse HEAD)" = e9a28008b3975c3aaa93b710b6f623221241c2eb\n'
        "sha256sum scripts/dev/battery/pod_watchdog.py                           # must be eba55521a397574560e75ee50be6ad2b625f737a11d44568d00436c093bc90e8\n"
        "startup_shard split --shards 3\n"
        "public_dev_questions draw --work $WD --questions 1\n"
        "score_proof --phase confirmation --look final\n"
    )


def test_current_sheet_shape_passes_static_preflight(sheet):
    result = preflight.inspect(sheet)
    assert result["checked_count"] == 7
    assert result["host_execution"] == "NOT_RUN"


def test_stale_release_anywhere_refused(sheet):
    with pytest.raises(preflight.SheetRefused, match="stale_release_pin"):
        preflight.inspect(sheet + "\nold note: r8.4")


def test_missing_exact_commit_guard_refused(sheet):
    stale = sheet.replace(preflight.COMMIT, "0" * 40)
    with pytest.raises(preflight.SheetRefused, match="exact_commit_guard"):
        preflight.inspect(stale)


def test_missing_public_dry_question_refused(sheet):
    stale = sheet.replace("--questions 1", "--questions 0")
    with pytest.raises(preflight.SheetRefused, match="public_dry_question"):
        preflight.inspect(stale)
