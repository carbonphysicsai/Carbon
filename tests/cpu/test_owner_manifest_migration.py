"""OWNER MANIFEST MIGRATION (Lead 4 Nov, option (a); TL board 2151): a byte-exact carry of a receiver's owners/ store
into a receiver on a NEWER accepted revision met each owner's frozen campaign manifest (the revision is part of it) and
refused to start.

Claims: the manifest is re-frozen to the new revision only when the revision is the ONLY change, the old revision is an
ancestor of the new one, and every retained task names the contract served now; otherwise the start refuses as before.
Only the campaign row changes (every task row kept), the change is logged, and a second start is a no-op (idempotent).
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

from carbon.challenge_validator import direct_receiver as dr
from carbon.development_session.profile import canonical, digest

OLD, NEW = "a" * 40, "b" * 40


def _manifest(revision, *, image="sha256:" + "1" * 64, campaign=None):
    implementation = {"revision": revision, "tree": "t", "source_tree_digest": "s"}
    return {
        "schema": "x",
        "owner": "5Owner",
        "challenge": {"id": "f02", "version": "2.5"},
        "implementation": implementation,
        "runtime": {"implementation": implementation, "images": [image]},
        "receiver_binding": {"implementation": implementation, "parent_image": image},
        "campaign_id": campaign or ("direct-" + revision[:8]),
        "admission": {"uid": 3},
    }


class Ledger:
    """The owner ledger's campaign + direct_tasks tables, on a real SQLite file."""

    def __init__(self, root, manifest, contracts):
        self.root = Path(root)
        self.path = self.root / "ledger.sqlite3"
        with sqlite3.connect(self.path) as db:
            db.executescript(
                "CREATE TABLE campaign (id INTEGER PRIMARY KEY CHECK(id=1), manifest BLOB NOT NULL, "
                "digest TEXT NOT NULL, started REAL);"
                "CREATE TABLE direct_tasks (id TEXT PRIMARY KEY, request BLOB NOT NULL, view BLOB NOT NULL, "
                "cancellation TEXT);"
            )
            payload = canonical(manifest)
            db.execute(
                "INSERT INTO campaign VALUES(1,?,?,NULL)", (payload, digest(payload))
            )
            for i, contract in enumerate(contracts):
                db.execute(
                    "INSERT INTO direct_tasks VALUES(?,?,?,NULL)",
                    (
                        f"rtsk_{i}",
                        json.dumps({"identities": {"contract_digest": contract}}),
                        b"view",
                    ),
                )
        self.raw = canonical(manifest)

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            yield connection
            if connection.in_transaction:
                connection.execute("COMMIT")
        finally:
            connection.close()

    def manifest(self):
        with self.db() as db:
            return json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])

    def tasks(self):
        with self.db() as db:
            return db.execute(
                "SELECT id, request, view FROM direct_tasks ORDER BY id"
            ).fetchall()


@pytest.fixture
def served(monkeypatch):
    from carbon.reconstruction import served_recipe_contract

    contract = "sha256:" + "c" * 64
    monkeypatch.setattr(
        served_recipe_contract,
        "registered",
        lambda cid, version: type("C", (), {"digest": contract})(),
    )
    monkeypatch.setattr(
        dr, "_is_ancestor", lambda old, new, root=None: (old, new) == (OLD, NEW)
    )
    # M2: these fixture revisions change no grading path (the git check has its own tests below)
    monkeypatch.setattr(dr, "_grading_change", lambda old, new, root=None: ())
    return contract


def _migrate(ledger, frozen, candidate):
    return dr._migrate_owner_manifest(ledger, "5Owner", ledger.raw, frozen, candidate)


def test_a_revision_only_change_on_an_ancestor_is_migrated_and_history_kept(
    tmp_path, served
):
    frozen, candidate = _manifest(OLD), _manifest(NEW)
    ledger = Ledger(tmp_path, frozen, [served, served])
    before = ledger.tasks()
    assert _migrate(ledger, frozen, candidate) is True
    assert ledger.manifest() == candidate
    assert ledger.tasks() == before  # every task row byte-identical
    (line,) = (tmp_path / "manifest-migrations.jsonl").read_text().splitlines()
    record = json.loads(line)
    assert record["from_revision"] == OLD and record["to_revision"] == NEW
    assert record["to_manifest_sha256"] == digest(canonical(candidate)).removeprefix(
        "sha256:"
    )
    assert len(record["from_manifest_sha256"]) == 64
    assert record["from_manifest_sha256"] != record["to_manifest_sha256"]
    assert "5Owner" not in line  # the owner appears only as a digest


def test_a_second_start_after_migration_is_a_no_op(tmp_path, served):
    frozen, candidate = _manifest(OLD), _manifest(NEW)
    ledger = Ledger(tmp_path, frozen, [served])
    assert _migrate(ledger, frozen, candidate)
    # on the next start the frozen manifest IS the candidate: no migration is asked for, nothing changes
    assert not dr._revision_only_change(ledger.manifest(), candidate)
    assert ledger.manifest() == candidate


def test_a_non_ancestor_revision_is_refused(tmp_path, served):
    frozen, candidate = _manifest(NEW), _manifest(OLD)  # going backwards
    ledger = Ledger(tmp_path, frozen, [served])
    assert _migrate(ledger, frozen, candidate) is False
    assert ledger.manifest() == frozen


def test_any_other_change_is_refused(tmp_path, served):
    frozen = _manifest(OLD)
    changed = (
        _manifest(NEW, image="sha256:" + "2" * 64),  # another image
        {**_manifest(NEW), "owner": "5Other"},
        {**_manifest(NEW), "challenge": {"id": "f02", "version": "2.6"}},
        {**_manifest(NEW), "admission": {"uid": 4}},
    )
    for n, candidate in enumerate(changed):
        root = tmp_path / str(n)
        root.mkdir()
        ledger = Ledger(root, frozen, [served])
        assert _migrate(ledger, frozen, candidate) is False
        assert ledger.manifest() == frozen


def test_a_task_on_another_contract_refuses(tmp_path, served):
    frozen, candidate = _manifest(OLD), _manifest(NEW)
    ledger = Ledger(tmp_path, frozen, [served, "sha256:" + "d" * 64])
    assert _migrate(ledger, frozen, candidate) is False
    assert ledger.manifest() == frozen


def test_is_ancestor_reads_git_history(tmp_path):
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    git("init", "-q")
    for n in (1, 2):
        (tmp_path / "f").write_text(str(n))
        git("add", "f")
        git("-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", str(n))
    first, second = git("rev-list", "--reverse", "HEAD").split()
    assert dr._is_ancestor(first, second, tmp_path)
    assert not dr._is_ancestor(second, first, tmp_path)
    assert not dr._is_ancestor("not-a-sha", second, tmp_path)


# ---------------------------------------------------------------- M2: no grading or rebuild change is migrated


@pytest.mark.parametrize(
    "path, grading",
    [
        ("carbon/scoring/engine.py", True),
        ("carbon/reconstruction/worker/operator.py", True),
        ("carbon/backbone_catalog/served.py", True),
        ("carbon/challenge_validator/lean_recipe_retention.py", True),
        ("carbon/challenge_validator/f02_hidden.py", True),
        ("carbon/challenge_validator/motor_scoring.py", True),
        ("carbon/challenge_validator/battery_bank.py", True),
        ("carbon/challenge_kit/version_registry.py", True),
        ("carbon/evaluation_packs/x.json", True),
        ("carbon/development_session/research_carrier.py", True),
        # the A1 / migration move (Validator 13:53: no grading path)
        ("carbon/challenge_validator/direct_receiver.py", False),
        ("carbon/challenge_validator/auto_grade.py", False),
        ("carbon/chain/sdk.py", False),
        ("carbon/dashboard/web/index.html", False),
        ("carbon/motor/campaign.py", False),
        ("tests/cpu/test_scoring.py", False),
        ("docs/carbon/scoring/x.md", False),
        ("carbon/scoringx.py", False),
    ],
)
def test_the_grading_paths_follow_the_validators_categories(path, grading):
    assert dr.grading_path(path) is grading


def _repo(tmp_path):
    from carbon.reconstruction.worker import build_inputs

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def commit(files, message):
        for name, text in files.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            git("add", name)
        git("-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", message)
        return git("rev-parse", "HEAD")

    git("init", "-q")
    base = commit(
        {
            build_inputs.INPUTS_FILE_IN_REPO: "pyproject.toml\n",
            "pyproject.toml": "[project]\n",
            "carbon/challenge_validator/direct_receiver.py": "1\n",
            "carbon/scoring/engine.py": "1\n",
            "docs/a.md": "1\n",
        },
        "base",
    )
    return git, commit, base


def test_the_grading_change_reads_the_real_diff(tmp_path):
    dr._GRADING_CHANGES.clear()
    _git, commit, base = _repo(tmp_path)
    receiver = commit(
        {"carbon/challenge_validator/direct_receiver.py": "2\n", "docs/a.md": "2\n"},
        "r",
    )
    assert dr._grading_change(base, receiver, tmp_path) == ()
    scoring = commit({"carbon/scoring/engine.py": "2\n"}, "s")
    assert dr._grading_change(receiver, scoring, tmp_path) == (
        "carbon/scoring/engine.py",
    )
    assert dr._grading_change(base, scoring, tmp_path) == ("carbon/scoring/engine.py",)
    image = commit({"pyproject.toml": "[project]\nname='x'\n"}, "i")
    assert dr._grading_change(scoring, image, tmp_path) == (dr.BUILD_INPUTS_CHANGED,)
    assert (
        dr._grading_change("f" * 40, image, tmp_path) is None
    )  # git cannot tell: refuse


def test_a_rename_out_of_a_grading_path_counts(tmp_path):
    dr._GRADING_CHANGES.clear()
    git, _commit, base = _repo(tmp_path)
    git("mv", "carbon/scoring/engine.py", "carbon/other.py")
    git("-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", "mv")
    moved = git("rev-parse", "HEAD")
    assert dr._grading_change(base, moved, tmp_path) == ("carbon/scoring/engine.py",)


@pytest.mark.parametrize("touched", [("carbon/scoring/engine.py",), None])
def test_a_grading_change_or_an_unknown_one_refuses_the_migration(
    tmp_path, served, monkeypatch, capsys, touched
):
    monkeypatch.setattr(dr, "_grading_change", lambda old, new, root=None: touched)
    frozen, candidate = _manifest(OLD), _manifest(NEW)
    ledger = Ledger(tmp_path, frozen, [served])
    assert _migrate(ledger, frozen, candidate) is False
    assert ledger.manifest() == frozen
    assert not (tmp_path / "manifest-migrations.jsonl").exists()
    said = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert said["event"] == "owner_manifest_migration_refused"
    assert said["reason"] == (
        "grading_change_unknown" if touched is None else "grading_path_changed"
    )
    assert said["paths"] == ([] if touched is None else list(touched))


@pytest.mark.parametrize(
    "old",
    [
        "a19b219606b5",  # Burst Thermal + Motor doors (rs15)
        "f3badf2400ec",  # Ribbed Bracket + Cooling doors (rs16)
    ],
)
def test_the_validators_own_m2_check_of_the_a1_move_reproduces(old):
    """Validator 13:53 checked a19b2196/f3badf24..95f661a4 by hand: no grading path. The encoded rule agrees."""
    root = Path(dr.__file__).resolve().parents[2]

    def full(rev):
        done = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "-q", rev + "^{commit}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return done.stdout.strip() if done.returncode == 0 else None

    old_sha, new_sha = full(old), full("95f661a4013373319329dcba66067cd173d09e27")
    if old_sha is None or new_sha is None:
        pytest.skip("this checkout lacks the door revisions")
    assert dr._grading_change(old_sha, new_sha, root) == ()
