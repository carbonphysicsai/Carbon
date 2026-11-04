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
    for candidate in (
        _manifest(NEW, image="sha256:" + "2" * 64),  # another image
        {**_manifest(NEW), "owner": "5Other"},
        {**_manifest(NEW), "challenge": {"id": "f02", "version": "2.6"}},
        {**_manifest(NEW), "admission": {"uid": 4}},
    ):
        ledger = Ledger(tmp_path / str(id(candidate)), frozen, [served])
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
