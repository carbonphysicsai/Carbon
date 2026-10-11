import copy
import json
import subprocess
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import metrics as m
from carbon.challenge_pipeline.onboarding import packet

SOURCE = Path("docs/development/challenge_pipeline/onboarding-metrics/sources.json")


def sources():
    return json.loads(SOURCE.read_text())


def toy():
    raw = sources()
    observations = {}
    for c in raw["challenges"]:
        for i, s in enumerate(c["stages"]):
            when = f"2026-10-01T{i:02d}:00:00Z"
            first = {"commit": "a" * 40, "committed_utc": when}
            observations[(c["challenge"], s["id"])] = {
                **s,
                "coverage": "MAIN_ARTIFACT",
                "first_draft": first,
                "last_revision": first,
                "first_main": first,
                "publication_pr": 42,
                "commits": [{**first, "git_author": "shared-account"}],
                "current_revision_in_main": True,
            }
    prs = {
        "42": {
            "state": "MERGED",
            "createdAt": "2026-10-01T00:00:00Z",
            "mergedAt": "2026-10-01T12:00:00Z",
            "mergeCommit": {"oid": "a" * 40},
        }
    }
    return raw, observations, prs


def report(raw, observations, prs, **kwargs):
    return m.summarize(
        observations, raw, prs, captured_at="2026-10-02T00:00:00Z", **kwargs
    )


def test_eleven_cohorts_ten_rows_and_no_invented_stage_or_effort():
    raw, obs, prs = toy()
    out = report(raw, obs, prs)
    assert len(out["rows"]) == 110
    assert all(
        r["stage_elapsed_s"] is None and r["team_effort_hours"] is None
        for r in out["rows"]
    )
    assert out["activity_proxy"]["unique_post_brief_commits"] == 1
    assert out["activity_proxy"]["unique_prs"] == 1
    assert out["activity_proxy"]["headcount"] is None
    assert (
        out["slowest_recurring_observed_arrivals"] == []
    )  # one shared delivery is not replication
    assert "TRAIN/kit means a plan/hook" in m.render(out)


def test_reuse_bundled_out_of_order_and_unavailable_are_not_elapsed_success():
    raw, obs, prs = toy()
    row = obs[("motor", "comparator")]
    row["first_draft"]["committed_utc"] = "2026-09-01T00:00:00Z"
    obs[("motor", "panel")]["first_draft"]["committed_utc"] = "2026-10-01T01:00:00Z"
    obs[("f02", "packet")]["first_draft"]["committed_utc"] = "2026-10-01T00:00:00Z"
    obs[("f13", "verification_spec")]["first_draft"] = None
    out = report(raw, obs, prs)
    get = lambda c, s: next(
        r for r in out["rows"] if r["challenge"] == c and r["stage"] == s
    )
    assert get("motor", "comparator")["arrival_gap_basis"] == "REUSE_PREDATES_BRIEF"
    assert get("motor", "comparator")["brief_to_artifact_s"] is None
    assert get("motor", "panel")["arrival_gap_basis"] == "OUT_OF_ORDER"
    assert get("motor", "panel")["previous_artifact_arrival_gap_s"] is None
    assert get("f02", "packet")["arrival_gap_basis"] == "BUNDLED_OR_SIMULTANEOUS"
    assert get("f13", "verification_spec")["first_draft_utc"] is None


def test_api_clock_only_when_exact_integration_matches_and_pending_censored():
    raw, obs, prs = toy()
    prs["42"]["mergeCommit"] = None
    out = report(raw, obs, prs)
    assert out["rows"][0]["github_first_publication_utc"] is None
    pending = obs[("motor", "generators_decks")]
    pending.update(
        first_main=None,
        publication_pr=None,
        pending_pr=43,
        current_revision_in_main=False,
    )
    prs["43"] = {
        "state": "OPEN",
        "createdAt": "2026-10-01T00:00:00Z",
        "mergedAt": None,
        "mergeCommit": None,
    }
    row = next(
        r
        for r in report(raw, obs, prs)["rows"]
        if r["challenge"] == "motor" and r["stage"] == "generators_decks"
    )
    assert row["draft_to_first_publication_s"] is None
    assert row["pending_pr_age_s"] == 86400
    assert row["current_revision_in_main"] is False


def test_recurring_arrival_ranking_requires_distinct_delivery_events():
    raw, obs, prs = toy()
    for cohort in raw["challenges"]:
        obs[(cohort["challenge"], "packet")]["first_draft"][
            "committed_utc"
        ] = "2026-10-01T00:00:00Z"
    for c, hour, sha in [("motor", 1, "b"), ("f02", 2, "c"), ("f13", 4, "d")]:
        obs[(c, "packet")]["first_draft"] = {
            "commit": sha * 40,
            "committed_utc": f"2026-10-01T0{hour}:00:00Z",
        }
    ranked = report(raw, obs, prs)["slowest_recurring_observed_arrivals"]
    assert next(b for b in ranked if b["stage"] == "packet") == {
        "stage": "packet",
        "sample_n": 3,
        "cohort_rows_n": 3,
        "event_basis": "UNIQUE_FIRST_DRAFT_COMMIT_MEDIAN_ACROSS_COHORT_ROWS",
        "median_arrival_gap_s": 7200,
        "max_arrival_gap_s": 14400,
    }


def test_only_explicit_partial_effort_with_provenance_can_be_measured():
    raw, obs, prs = toy()
    event = {
        "event_id": "work-1",
        "challenge": "motor",
        "stage": "packet",
        "actor": "packets",
        "duration_s": 600,
        "basis": "MEASURED_ACTIVE_DURATION",
        "source": "active timer record",
    }
    row = next(
        r
        for r in report(raw, obs, prs, effort_events=[event])["rows"]
        if r["challenge"] == "motor" and r["stage"] == "packet"
    )
    assert row["team_effort_hours"] == pytest.approx(1 / 6)
    assert row["team_effort_basis"].endswith("PARTIAL")
    for bad in [
        {**event, "duration_s": True},
        {**event, "basis": "GIT_ELAPSED"},
        {**event, "source": ""},
    ]:
        with pytest.raises(packet.DraftError):
            m.effort_totals([bad])
    with pytest.raises(packet.DraftError):
        m.effort_totals([event, event])


@pytest.mark.parametrize(
    "path",
    [
        "docs/development/challenge_pipeline/hidden/panel.json",
        "../data.json",
        "carbon/battery/ev5.py",
        "docs/development/challenge_pipeline/secrets.json",
        ".git/config",
    ],
)
def test_protected_or_unbounded_sources_refused(path):
    source = copy.deepcopy(sources()["challenges"][0]["stages"][0])
    source["path"] = path
    with pytest.raises(packet.DraftError):
        m.source_check(source)


def test_mutable_refs_duplicate_cohorts_and_shallow_history_fail_closed(monkeypatch):
    raw = sources()
    raw["challenges"][0]["stages"][0]["ref"] = "origin/main"
    with pytest.raises(packet.DraftError):
        m.validate_sources(raw)
    raw = sources()
    raw["challenges"][0] = raw["challenges"][1]
    with pytest.raises(packet.DraftError):
        m.validate_sources(raw)
    monkeypatch.setattr(m.timeline, "git", lambda *args: "true")
    with pytest.raises(packet.DraftError, match="shallow"):
        m.collect(Path("."), sources())


def test_real_git_metadata_is_not_worktree_bytes_and_missing_path_is_unknown(tmp_path):
    def git(*args):
        return subprocess.check_output(
            [
                "git",
                "-c",
                "user.name=fixture",
                "-c",
                "user.email=fixture@example.invalid",
                *args,
            ],
            cwd=tmp_path,
            text=True,
        ).strip()

    git("init", "-q")
    path = tmp_path / "docs/development/challenge_pipeline/toy.md"
    path.parent.mkdir(parents=True)
    path.write_text("public draft")
    git("add", ".")
    git("commit", "-qm", "first")
    sha = git("rev-parse", "HEAD")
    source = {
        "id": "packet",
        "path": path.relative_to(tmp_path).as_posix(),
        "ref": sha,
        "pending_pr": None,
    }
    first = m.observe(tmp_path, source, sha)
    path.write_text("dirty changed body, not committed")
    assert m.observe(tmp_path, source, sha) == first
    assert first["coverage"] == "MAIN_ARTIFACT"
    assert first["first_draft"]["commit"] == sha
    source["path"] = "docs/development/challenge_pipeline/missing.md"
    assert (
        m.observe(tmp_path, source, sha)["coverage"] == "MISSING_OR_HISTORY_UNAVAILABLE"
    )


def test_public_registry_entry_is_dated_when_family_arrives(monkeypatch):
    commits = [
        {"commit": str(i) * 40, "committed_utc": f"2026-10-01T0{i}:00:00Z"}
        for i in range(3)
    ]
    values = [
        {"challenges": [{"challenge": "motor"}]},
        {"challenges": [{"challenge": "motor"}, {"challenge": "f02"}]},
        {"challenges": [{"challenge": "motor", "changed": True}, {"challenge": "f02"}]},
    ]
    monkeypatch.setattr(
        m.timeline,
        "git",
        lambda root, command, target: json.dumps(values[int(target[0])]),
    )
    source = {
        "json_entry": "f02",
        "path": "docs/development/challenge_pipeline/evidence-readiness/bindings.json",
    }
    assert m.selected_history(Path("."), commits, source) == [commits[1]]
    source["json_entry"] = "motor"
    assert m.selected_history(Path("."), commits, source) == [commits[0], commits[2]]


def test_registry_selector_cannot_read_arbitrary_historical_json():
    source = copy.deepcopy(sources()["challenges"][0]["stages"][0])
    source["json_entry"] = "motor"
    with pytest.raises(packet.DraftError, match="selectors"):
        m.source_check(source)
