import os
import subprocess
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import packet, timeline


def command(root, *args):
    env = dict(
        os.environ,
        GIT_AUTHOR_DATE="2026-10-01T12:00:00+00:00",
        GIT_COMMITTER_DATE="2026-10-01T12:00:00+00:00",
    )
    return subprocess.run(
        ["git", *args], cwd=root, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def history(tmp_path):
    command(tmp_path, "init", "-b", "main")
    command(tmp_path, "config", "user.email", "fixture@example.invalid")
    command(tmp_path, "config", "user.name", "fixture")
    (tmp_path / "README.md").write_text("toy fixture", encoding="utf-8")
    command(tmp_path, "add", "README.md")
    command(tmp_path, "commit", "-m", "initial")
    command(tmp_path, "checkout", "-b", "feature")
    folder = tmp_path / "docs/development"
    folder.mkdir(parents=True)
    (folder / "packet.md").write_text("toy packet", encoding="utf-8")
    command(tmp_path, "add", "docs/development/packet.md")
    first = command(tmp_path, "commit", "-m", "packet")
    assert first
    return tmp_path


def stages():
    return [
        {
            "id": "S1_packet",
            "owner": "Test Lead",
            "artifacts": [{"path": "docs/development/packet.md"}],
        }
    ]


def test_branch_creation_not_main_merge_or_stage_completion(history):
    doc = timeline.generate(history, "toy", stages(), main_ref="main")
    row = doc["stages"][0]
    item = row["artifacts"][0]
    assert item["first_recorded"]["committed_utc"] == "2026-10-01T12:00:00Z"
    assert item["first_main_integration"] is None
    assert row["accepted_exit_utc"] is None
    assert doc["brief_to_tested_seconds"] is None
    assert doc["human_effort_saved_hours"] is None


def test_normal_merge_has_separate_identity_and_no_acceptance(history):
    original = command(history, "rev-parse", "HEAD")
    command(history, "checkout", "main")
    command(history, "merge", "--no-ff", "feature", "-m", "integrate")
    doc = timeline.generate(history, "toy", stages(), main_ref="main")
    item = doc["stages"][0]["artifacts"][0]
    assert item["first_recorded"]["commit"] == original
    assert item["first_main_integration"]["commit"] != original
    assert item["first_main_integration"]["kind"] == "MERGE_INTEGRATION"
    assert item["accepted_stage_completion_utc"] is None


def test_dirty_untracked_file_does_not_invent_timestamp(history):
    (history / "docs/development/pending.md").write_text("pending", encoding="utf-8")
    row = [
        {
            "id": "S1_packet",
            "owner": "Test Lead",
            "artifacts": [{"path": "docs/development/pending.md"}],
        }
    ]
    item = timeline.generate(history, "toy", row, main_ref="main")["stages"][0][
        "artifacts"
    ][0]
    assert item["first_recorded"] is None
    assert item["coverage"] == "NO_ADDITION_IN_AVAILABLE_HISTORY"


def test_rename_and_reintroduction_are_ambiguous(history):
    command(history, "mv", "docs/development/packet.md", "docs/development/renamed.md")
    command(history, "commit", "-m", "rename")
    row = [
        {
            "id": "S1_packet",
            "owner": "Test Lead",
            "artifacts": [{"path": "docs/development/renamed.md"}],
        }
    ]
    item = timeline.generate(history, "toy", row, main_ref="main")["stages"][0][
        "artifacts"
    ][0]
    assert item["rename_seen"]
    assert item["coverage"] == "AMBIGUOUS_RENAME_OR_MULTIPLE_ADDITIONS"
    command(history, "rm", "docs/development/renamed.md")
    command(history, "commit", "-m", "remove")
    (history / "docs/development").mkdir(parents=True, exist_ok=True)
    (history / "docs/development/renamed.md").write_text(
        "new version", encoding="utf-8"
    )
    command(history, "add", "docs/development/renamed.md")
    command(history, "commit", "-m", "new version")
    item = timeline.generate(history, "toy", row, main_ref="main")["stages"][0][
        "artifacts"
    ][0]
    assert item["path_additions"] == 2


def test_no_git_and_no_main_remain_unknown(tmp_path_factory, history):
    empty = tmp_path_factory.mktemp("without-git")
    absent = timeline.generate(empty, "toy", stages())
    assert absent["coverage"] == "GIT_UNAVAILABLE"
    no_main = timeline.generate(history, "toy", stages())
    assert no_main["basis"]["main"] is None
    assert no_main["stages"][0]["artifacts"][0]["first_main_integration"] is None


def test_shallow_history_marked_partial(history, tmp_path):
    clone = tmp_path / "shallow"
    command(tmp_path, "clone", "--depth=1", history.as_uri(), str(clone))
    doc = timeline.generate(clone, "toy", stages(), main_ref="HEAD")
    assert doc["coverage"] == "PARTIAL_SHALLOW_HISTORY"


@pytest.mark.parametrize(
    "name",
    [
        "../secret",
        ".git/config",
        "docs/development/hidden/cases.json",
        "docs/development/../secret",
        "carbon/battery/private.json",
        "--all",
        "docs/development/*.json",
        "docs/development/[a-z].json",
    ],
)
def test_public_metadata_allowlist(name):
    with pytest.raises(packet.DraftError):
        timeline.metadata_path(name)


def test_invalid_revision_cannot_be_a_git_option(history):
    with pytest.raises(packet.DraftError):
        timeline.pin(history, "--all")


def test_mutating_a_view_cannot_change_cached_history(history):
    view = timeline.generate(history, "toy", stages(), main_ref="main")
    view["stages"][0]["artifacts"][0]["first_recorded"]["commit"] = "fabricated"
    later = timeline.generate(history, "toy", stages(), main_ref="main")
    assert (
        later["stages"][0]["artifacts"][0]["first_recorded"]["commit"] != "fabricated"
    )


def test_battery_public_paths_are_only_metadata_and_effort_unknown():
    from carbon.challenge_pipeline.onboarding import status

    view = status.generate(Path(__file__).resolve().parents[2], "battery")
    report = view["artifact_timeline"]
    assert report["challenge"] == "battery-v3"
    assert report["brief_to_tested_seconds"] is None
    assert all(r["stage_cycle_seconds"] is None for r in report["stages"])
    bank = next(r for r in report["stages"] if r["id"] == "S5_bank")
    assert bank["artifacts"][0]["path"].endswith("RUNBOOK.md")
    assert bank["accepted_exit_utc"] is None
