"""Sharded solves for a startup host (PRODUCER-STARTUP-HOST-01 slice 1):
split, scripted solve, merge, over battery-shaped jobs in a temporary work
directory. There is no container, network or second host. Not a security
audit (AGENTS.md §13)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from carbon.battery.truth import LOCK_PATH
from carbon.challenge_validator import startup_shard as ss
from carbon.challenge_validator.batch_source import ProducerRefused
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

REPOSITORY = Path(__file__).resolve().parents[2]
HOST = "SHA256:" + "A" * 43
RECORD = "2026-10-08-OWNER-STARTUP-HOST-CUSTODY-01.md"
COMMIT = "c" * 40


@pytest.fixture
def repo(tmp_path):
    """A repository with the owner's custody record and the truth lock."""
    root = tmp_path / "repo"
    (root / ".agent" / "decisions").mkdir(parents=True)
    (root / ".agent" / "decisions" / RECORD).write_text(
        f"## OWNER-STARTUP-HOST-CUSTODY-01\n\nHost key: {HOST}\n"
    )
    lock = root / LOCK_PATH
    lock.parent.mkdir(parents=True)
    shutil.copy(REPOSITORY / LOCK_PATH, lock)
    return root


def job(i, refined=False):
    value = {
        "case_id": f"c{i:02d}",
        "c1": 1.0 + i,
        "c2": 2.0,
        "t_amb_c": 25.0,
        "soc0": 0.1,
    }
    if refined:
        value["refined"] = True
    return value


def record(j, status="OK", value=None):
    return {
        "case_id": j["case_id"],
        "refined": j.get("refined", False),
        "inputs": {k: j[k] for k in ("c1", "c2", "t_amb_c", "soc0")},
        "status": status,
        "value": value if value is not None else j["c1"] * 2,
        "wall_s": 10.0 + j["c1"],
    }


@pytest.fixture
def work(tmp_path):
    path = tmp_path / "work"
    path.mkdir(mode=0o700)
    jobs = [job(i) for i in range(10)] + [job(3, refined=True)]
    (path / "jobs.json").write_text(
        json.dumps({"fingerprint": "sha256:" + "f" * 64, "jobs": jobs})
    )
    with (path / "records.jsonl").open("w") as handle:
        for j in jobs[:2]:
            handle.write(json.dumps(record(j)) + "\n")
    return path


def split(work, tmp_path, repo, shards=3, **options):
    return ss.split(
        work,
        shards,
        tmp_path / "shards",
        BATTERY_CHALLENGE,
        custody=options.get("custody", RECORD),
        host_key=options.get("host_key", HOST),
        repository=repo,
        commit=COMMIT,
    )


def solve(shard_dir, status="OK", value=None):
    jobs = json.loads((shard_dir / "jobs.json").read_text())["jobs"]
    with (shard_dir / "records.jsonl").open("w") as handle:
        for j in jobs:
            handle.write(json.dumps(record(j, status, value)) + "\n")


def merge(work, shard_dir, repo):
    return ss.merge(work, shard_dir, BATTERY_CHALLENGE, repository=repo, commit=COMMIT)


def records(work):
    return [json.loads(l) for l in (work / "records.jsonl").read_text().splitlines()]


def test_split_covers_every_unsolved_job_once_and_is_deterministic(
    work, tmp_path, repo
):
    first = split(work, tmp_path, repo)
    assert sum(s["jobs"] for s in first) == 9  # 11 jobs, 2 solved
    keys = []
    for s in first:
        jobs = json.loads(
            (tmp_path / "shards" / f"shard-{s['shard']}" / "jobs.json").read_text()
        )["jobs"]
        keys += [(j["case_id"], bool(j.get("refined"))) for j in jobs]
    assert len(keys) == len(set(keys)) == 9
    assert ("c03", True) in keys and ("c03", False) in keys
    assert split(work, tmp_path, repo) == first
    written = [e for e in ss._journal(work) if e["event"] == "shard_written"]
    assert len(written) == 3
    manifest = json.loads(
        (tmp_path / "shards" / "shard-0" / "manifest.json").read_text()
    )
    assert manifest["code"] == COMMIT and manifest["host_key"] == HOST
    assert manifest["image"] and manifest["overlay"].startswith("sha256:")


@pytest.mark.parametrize(
    ("options", "code"),
    [
        ({"custody": "2026-10-08-NOT-THERE.md"}, "startup_custody_unrecorded"),
        ({"host_key": "SHA256:" + "B" * 43}, "startup_custody_unrecorded"),
        ({"host_key": "not-a-key"}, "startup_host_key_malformed"),
        ({"custody": "../x.md"}, "startup_custody_unrecorded"),
    ],
)
def test_no_export_without_the_owners_custody_record(
    work, tmp_path, repo, options, code
):
    with pytest.raises(ProducerRefused) as refused:
        split(work, tmp_path, repo, **options)
    assert refused.value.code == code
    assert not (tmp_path / "shards").exists()


def test_split_solve_merge_equals_a_single_host_solve(work, tmp_path, repo):
    single = tmp_path / "single"
    shutil.copytree(work, single)
    for s in split(single, tmp_path / "s1", repo, shards=1):
        directory = tmp_path / "s1" / "shards" / f"shard-{s['shard']}"
        solve(directory)
        merge(single, directory, repo)
    for s in split(work, tmp_path, repo):
        directory = tmp_path / "shards" / f"shard-{s['shard']}"
        solve(directory)
        result = merge(work, directory, repo)
        assert result["accepted"] == s["jobs"] and result["wall_s_p50"] is not None

    def as_set(path):
        return sorted(json.dumps(r, sort_keys=True) for r in records(path))

    assert as_set(work) == as_set(single) and len(records(work)) == 11
    # A re-merge appends nothing.
    again = merge(work, tmp_path / "shards" / "shard-0", repo)
    assert again["accepted"] == 0 and again["skipped"] > 0
    assert len(records(work)) == 11


def test_infrastructure_failures_are_left_for_a_resplit(work, tmp_path, repo):
    [s] = split(work, tmp_path, repo, shards=1)
    directory = tmp_path / "shards" / "shard-0"
    solve(directory, status="FAILED_INFRA")
    result = merge(work, directory, repo)
    assert result["accepted"] == 0 and result["infra"] == s["jobs"]
    assert sum(r["jobs"] for r in split(work, tmp_path / "again", repo, shards=2)) == 9


@pytest.mark.parametrize(
    "change", ["mismatch", "outside", "inputs", "pins", "foreign", "jobs"]
)
def test_a_wrong_shard_appends_nothing(work, tmp_path, repo, change):
    split(work, tmp_path, repo, shards=1)
    directory = tmp_path / "shards" / "shard-0"
    solve(directory)
    before = (work / "records.jsonl").read_text()
    codes = {
        "mismatch": "startup_record_mismatch",
        "outside": "startup_record_outside_shard",
        "inputs": "startup_record_inputs_changed",
        "pins": "startup_shard_pins_changed",
        "foreign": "startup_shard_not_from_this_work",
        "jobs": "startup_shard_jobs_changed",
    }
    rows = [
        json.loads(l) for l in (directory / "records.jsonl").read_text().splitlines()
    ]
    if change == "mismatch":
        rows.append(record(job(0), value=-1.0))  # c00 already holds another record
        rows[-1]["refined"] = False
        jobs = json.loads((directory / "jobs.json").read_text())
        # Make c00 part of the shard so only the value differs.
        manifest = json.loads((directory / "manifest.json").read_text())
        jobs["jobs"].append(job(0))
        jobs["jobs"].sort(key=lambda j: (j["case_id"], bool(j.get("refined"))))
        manifest["jobs"] = len(jobs["jobs"])
        manifest["jobs_digest"] = ss._digest(jobs["jobs"])
        (directory / "manifest.json").write_text(json.dumps(manifest))
        jobs["shard"] = ss._digest(manifest)
        (directory / "jobs.json").write_text(json.dumps(jobs))
        ss._append_journal(
            work,
            "shard_written",
            manifest_digest=ss._digest(manifest),
            shard=0,
            jobs=manifest["jobs"],
        )
    elif change == "outside":
        rows.append(record(job(77)))
    elif change == "inputs":
        rows[0]["inputs"]["c1"] += 1.0
    elif change == "pins":
        pass
    elif change == "foreign":
        manifest = json.loads((directory / "manifest.json").read_text())
        manifest["shard"] = 9
        (directory / "manifest.json").write_text(json.dumps(manifest))
    else:
        jobs = json.loads((directory / "jobs.json").read_text())
        jobs["jobs"].pop()
        (directory / "jobs.json").write_text(json.dumps(jobs))
    (directory / "records.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
    )
    with pytest.raises(ProducerRefused) as refused:
        if change == "pins":
            ss.merge(
                work, directory, BATTERY_CHALLENGE, repository=repo, commit="d" * 40
            )
        else:
            merge(work, directory, repo)
    assert refused.value.code == codes[change]
    assert (work / "records.jsonl").read_text() == before


def test_status_reports_public_counts_only(work, tmp_path, repo):
    for s in split(work, tmp_path, repo, shards=2):
        directory = tmp_path / "shards" / f"shard-{s['shard']}"
        solve(directory)
        merge(work, directory, repo)
    report = ss.status(work)
    assert [s["merged"] for s in report["shards"]] == [
        s["jobs"] for s in report["shards"]
    ]
    assert "c0" not in json.dumps(report)
