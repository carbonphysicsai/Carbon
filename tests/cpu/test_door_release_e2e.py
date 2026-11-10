"""(D) The door release gate (runbook delta 0cace8f7, V2B's FINAL condition after RB door rs33, 9 Nov).

ONE flow on a CARRIED state root, through the code a live door runs, with real sqlite everywhere:

1. the previous release's state: an attempts ledger whose exam-slot tables are exactly as 2650bc09 created them (no
   ``group_id``, no recipe-copy tables), in rollback-journal mode, holding an upload admitted BEFORE the release;
2. the release: the real `AutoGrader` starts on that root (its first start activates the recipe-once rule);
3. FRESH admissions through the real signed door (`DirectRecipeIntake.handle` -> `Validator.evaluate` -> the real
   `LeanRecipeAdapter` -> a real per-hotkey `DirectDevelopmentTasksV3`), which note the recipe digest with the REAL
   `adapter.owner()` (it opens the attempts ledger itself: the rs33 lock);
4. ADVANCE: the real `adapter.advance` -> `provider.run_queued_task`, which builds and infers the candidate for real in a
   fresh local process and writes its own SUCCEEDED view and private evidence;
5. GRADE: the real `AutoGrader.run_once`: the pre-release upload and the first fresh one GRADED, an identical recipe
   from another hotkey DUPLICATE (no exam read), nothing left pending, nothing said on the failure journal.

Labelled stand-ins (nothing else is):

(a) the C-03 container boundary: `reconstruct_and_infer_public` runs for real with a local-process runner (the fixed
    build and inference programs in fresh processes, as `test_direct_clean_rebuild_acceptance`); its result is then
    marked ``C03_DOCKER`` with fixture controls digests, and `_private_controls_digest` returns those digests (a CPU gate
    has no Docker host whose settled operations it could bind);
(b) the sealed grade: `retain_result` checks the provider's real SUCCEEDED view and verified private evidence, then
    reserves and settles the real exam-cap slot; no score pack is read (the synthetic Challenge has none);
(c) the exam key and cadence: a fixture pack digest and a fixture cadence registering the synthetic Challenge.

RULE B (the downgrade gate, ``scripts/dev/release/downgrade_gate.sh``): with ``CARBON_RELEASE_GATE_STATE`` set, the
first test writes its state root there and the second (skipped otherwise) is run by the PREVIOUS release's checkout on
that same root: its receiver starts on it and must admit, build and grade a new submission from it.
Fixture material only (synthetic Challenge); no hidden value.
"""

from __future__ import annotations

import dataclasses
import gzip
import hashlib
import io
import json
import os
import sqlite3
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_c08_authenticated_miner_mcp import CONTEXT, NOW, _headers, _Verifier
from test_direct_clean_rebuild_acceptance import LocalProcessRunner

from carbon.battery.intake import SnapshotWindow
from carbon.battery.pool_store import PoolStore
from carbon.chain import MetagraphSnapshot, Participant
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger, auto_grade, exam_cap
from carbon.challenge_validator.direct_intake import (
    SUBMIT_PATH,
    SUBMIT_TOOL,
    DirectRecipeIntake,
)
from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable
from carbon.development_session import bundle_construction_worker
from carbon.development_session.library_bundles import (
    BUNDLE_SCHEMA,
    ProvisionedLibraryEnvironment,
    _environment_digest,
    bundle_ref,
)
from carbon.development_session.research_image import LibraryWorkerImage
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_service import DirectFixtureDiscovery
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.reconstruction.worker.model import WorkerImageIdentity
from carbon.research import DirectTaskStateV3
from carbon.transport.models import message
from carbon.transport.store import ReceiptJournal

STATE_ENV = "CARBON_RELEASE_GATE_STATE"
#: Written by the first test when it passes; the previous release's run reads only a root that carries it.
WROTE = "new-release-wrote.json"
RECEIVER = "validator"
#: Fixture hotkeys: the pre-release uploader, the first fresh one, a copier, and the one the rolled-back release admits.
PRE, FRESH, COPIER, AFTER_ROLLBACK = (
    "miner-pre",
    "miner-fresh",
    "miner-copy",
    "miner-back",
)
HOTKEYS = (PRE, FRESH, COPIER, AFTER_ROLLBACK)
#: (c) fixture exam key and controls digests (never a real pack's).
EXAM = "sha256:" + "e" * 64
CONTROLS = {"build": "sha256:" + "b" * 64, "inference": "sha256:" + "9" * 64}

#: The candidate: the least-squares scale of the public train (no seed or configuration use), in jax like the fixture.
SOURCE = (
    "import numpy as np\n"
    "import jax.numpy as jnp\n"
    "def build(train_inputs, train_targets, *, seed, configuration, train_use):\n"
    "    del seed, configuration, train_use\n"
    "    scale = np.float32(np.sum(train_inputs * train_targets) / np.sum(train_inputs**2))\n"
    "    return {'framework': 'jax', 'apply': lambda x: x * jnp.asarray(scale), 'parameters': []}\n"
)

#: The exam-slot tables exactly as 2650bc09 created them (Graphite-B 175d6307, `test_recipe_graded_once`).
EXAM_DDL_2650BC09 = (
    (
        "CREATE TABLE exam_graded(id INTEGER PRIMARY KEY AUTOINCREMENT, hotkey TEXT NOT NULL, "
        "challenge_id TEXT NOT NULL, challenge_version TEXT NOT NULL, exam_key TEXT NOT NULL, "
        "kind TEXT NOT NULL DEFAULT 'GRADED' CHECK(kind IN ('GRADED','REGRADE')), epoch INTEGER NOT NULL, "
        "submission_id TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('RESERVED','COUNTED','RELEASED')), "
        "status TEXT, reserved_ns INTEGER NOT NULL, settled_ns INTEGER, cpu_seconds REAL, lane_seconds REAL, "
        "UNIQUE(challenge_id, challenge_version, exam_key, submission_id))"
    ),
    "CREATE INDEX exam_graded_miner ON exam_graded(hotkey, challenge_id, challenge_version, exam_key)",
    "CREATE INDEX exam_graded_epoch ON exam_graded(epoch, challenge_id)",
    (
        "CREATE TABLE exam_requeues(submission_id TEXT PRIMARY KEY, attempt INTEGER NOT NULL, "
        "queued_ns INTEGER NOT NULL, reserved_ns INTEGER)"
    ),
    (
        "CREATE TABLE exam_keys(challenge_id TEXT NOT NULL, challenge_version TEXT NOT NULL, "
        "exam_key TEXT NOT NULL, first_block INTEGER NOT NULL, "
        "PRIMARY KEY(challenge_id, challenge_version, exam_key))"
    ),
)


def _sha(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _cadence(challenge_id):
    return {
        "capacity_gpu_lane_hours_per_day": 1000.0,
        "rebuild_gpu_lane_hours": {challenge_id: 1.0},
        "lanes": 1,
        "measurement_digest": "sha256:" + "a" * 64,
        "class_record_digest": "sha256:" + "c" * 64,
    }


def _source_image(root: Path):
    """The candidate's library bundle, byte-identical on every run (gzip mtime 0), so both releases' receivers resolve
    the same admitted bundle from the same root; the installed copy is the CPU stand-in for the container's install.
    """
    license_text = b"MIT\n"
    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode="w") as archive:
        for name, body in (
            ("source/candidate/__init__.py", b""),
            ("source/candidate/build.py", SOURCE.encode()),
            ("source/LICENSE", license_text),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(body)
            archive.addfile(member, io.BytesIO(body))
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode="wb", mtime=0) as zipped:
        zipped.write(tar.getvalue())
    source, lock, base = packed.getvalue(), b"", "sha256:" + "1" * 64
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "name": "release-gate-source",
        "language": "python",
        "source_sha256": _sha(source),
        "source_bytes": len(source),
        "runtime_profile_id": "jax-cuda13-py311",
        "base_environment_digest": base,
        "environment_digest": _environment_digest(base, _sha(lock)),
        "os": "linux",
        "architecture": "amd64",
        "python_abi": "cp311",
        "accelerator": "cuda13",
        "lock_sha256": _sha(lock),
        "wheels": {},
        "license_sha256": _sha(license_text),
    }
    reference = bundle_ref(manifest, source, {}, lock, license_text)
    installed = root / "installed"
    (installed / "candidate").mkdir(parents=True, exist_ok=True)
    (installed / "candidate" / "__init__.py").write_bytes(b"")
    (installed / "candidate" / "build.py").write_bytes(SOURCE.encode())
    parent = WorkerImageIdentity(*("sha256:" + "2" * 64 for _ in range(8)))
    provisioned = ProvisionedLibraryEnvironment(
        reference, parent.image_id, root, _sha(source), "sha256:" + "3" * 64
    )
    return LibraryWorkerImage(provisioned, parent, reference.to_dict()), installed


class _UniqueLocalRunner(LocalProcessRunner):
    """The fixture's local-process runner, each settled operation under its own ``operation-<64 hex>`` name (a provider
    runs several tasks in one campaign ledger)."""

    def __call__(self, ledger, **request):
        result = super().__call__(ledger, **request)
        named = (
            "operation-"
            + hashlib.sha256(
                f"{request['identity']}|{len(self.calls)}".encode()
            ).hexdigest()
        )
        (ledger.root / result["operation"]).rename(ledger.root / named)
        return {**result, "operation": named}


def _local_c03(monkeypatch, installed):
    """(a): the real two-phase build and inference in local processes; only the container boundary and its settled
    controls are stood in. Returns the identities it built."""
    real = bundle_construction_worker.reconstruct_and_infer_public
    built = []

    def run(ledger, **kwargs):
        built.append(kwargs["identity"])
        result = real(ledger, **kwargs, runner=_UniqueLocalRunner(installed))
        return dataclasses.replace(
            result,
            execution_boundary="C03_DOCKER",
            build_controls_digest=CONTROLS["build"],
            inference_controls_digest=CONTROLS["inference"],
        )

    def controls(_ledger, *, owner, identity, operation, provenance):
        del owner, identity, operation
        return CONTROLS["build" if "RECONSTRUCTION" in provenance else "inference"]

    monkeypatch.setattr(bundle_construction_worker, "reconstruct_and_infer_public", run)
    monkeypatch.setattr(
        bundle_construction_worker, "_private_controls_digest", controls
    )
    monkeypatch.setattr(
        "carbon.development_session.research_image.verify_library_worker_image",
        lambda value: value,
    )
    return built


class Door:
    """One direct receiver on ``root``, built as `direct_receiver` builds it: the attempts ledger, a per-hotkey task
    provider and campaign ledger, the signed intake, and (from `start_grader`) the auto-grader with a pool store.
    """

    def __init__(self, root: Path, monkeypatch):
        self.root = root
        self.material = bundle_material_v5()
        self.discovery = DirectFixtureDiscovery(self.material, task_admission=True)
        # (c) the door's pack: its key, and the digest every provider is bound to (as `direct_receiver` binds them)
        self.discovery.evaluation_pack_snapshot = SimpleNamespace(manifest_digest=EXAM)
        self.discovery.evaluation_pack_digest = EXAM
        self.image, installed = _source_image(root / "bundle")
        self.built = _local_c03(monkeypatch, installed)
        self.providers = {}
        self.ledger_path = root / "attempts" / "attempts.sqlite3"
        self.ledger_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.ledger_path.parent.chmod(0o700)
        self.ledger = AttemptLedger(self.ledger_path)
        self.state = MetagraphSnapshot(
            CONTEXT,
            10,
            "0x" + "2" * 64,
            NOW // 1_000_000,
            (
                Participant(0, RECEIVER, "owner", 1),
                *(Participant(i + 1, h, "cold", 2) for i, h in enumerate(HOTKEYS)),
            ),
        )
        window = SnapshotWindow(clock=lambda: NOW / 1_000_000_000)
        window.add(self.state)
        self.intake = DirectRecipeIntake(
            context=CONTEXT,
            receiver=RECEIVER,
            journal=ReceiptJournal(root / "transport.sqlite3", CONTEXT),
            verifier=_Verifier(),
            window=window,
            discovery=self.discovery,
            provider_for=self.provider,
            attempt_ledger=self.ledger,
            clock_ns=lambda: NOW,
        )
        self.adapter = self.intake.adapter
        self.adapter.exam_cadence = _cadence(self.adapter.challenge_id)  # (c)
        self.intake.retain_result = self.retain_result  # (b)
        self.graded = []
        self.grader = None

    def provider(self, hotkey):
        if hotkey not in HOTKEYS:
            return None
        if hotkey not in self.providers:
            directory = (
                self.root / "providers" / hashlib.sha256(hotkey.encode()).hexdigest()
            )
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.providers[hotkey] = DirectDevelopmentTasksV3(
                root=directory / "tasks",
                requester=hotkey,
                owner=hotkey,
                ledger=CampaignLedger(directory / "ledger"),
                discovery=self.discovery,
                image=self.image,
                inference_image=self.image.parent,
                evaluation_pack_digest=EXAM,
            )
        return self.providers[hotkey]

    def recipe(self, setting=None):
        kit = self.material["construction_kit"]
        return {
            "schema": "carbon.construction-recipe.v1",
            "challenge": kit,
            "source": {"kind": "bundle", "bundle_ref": self.image.bundle_ref},
            "procedure": {
                "entrypoint": {"module": "candidate.build", "name": "build"},
                "configuration": {} if setting is None else {"setting": setting},
                "train_use": {"cases": "all"},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": kit["interface_digest"],
            },
        }

    def submit(self, hotkey, recipe, nonce):
        body = message(
            CONTEXT,
            self.state.snapshot_id,
            self.discovery.info.challenge_key,
            session="direct-recipe-intake",
            request=f"release-gate-{hotkey}-{nonce}",
            tool=SUBMIT_TOOL,
            fields={
                "strategy_json": json.dumps(recipe, sort_keys=True),
                "contract_digest": self.adapter.contract_digest,
            },
        )
        answer = self.intake.handle(
            "POST", SUBMIT_PATH, _headers(body, nonce, hotkey), body, "127.0.0.1"
        )
        assert answer.status == 202, answer.body
        assert answer.body["outcome"]["state"] == "ADMITTED"
        return answer.body["outcome"]["task_id"]

    def start_grader(self):
        """The release's first start: the real grader (its start activates the copy rule), with a real pool store."""
        pool = self.root / "pool.sqlite3"
        if not pool.exists():
            PoolStore(pool)
        self.grader = auto_grade.AutoGrader(
            self.intake,
            self.root / "receiver",
            pool_store=pool,
            containers=lambda: 0,
            gpu=lambda: 0,
        )
        self.grader.chain_degraded = lambda: False
        self.intake.grade_marker = self.grader.marker

    def retain_result(self, submission_id, **_kwargs):
        """(b): the provider's own SUCCEEDED view and verified evidence, then the real exam-cap slot; no score pack."""
        owner = self.adapter.owner(submission_id)
        provider = self.adapter._provider(owner)
        view = provider._views.get(submission_id)
        if view is None or view.state is not DirectTaskStateV3.SUCCEEDED:
            raise RetentionUnavailable("task_not_succeeded")
        evidence = provider.private_attempt(view.task_id)
        assert evidence is not None and evidence["predictions"]
        cap = exam_cap.ExamCap(self.ledger, cadence=self.adapter.exam_cadence)
        reservation = cap.reserve(
            hotkey=owner,
            challenge_id=self.adapter.challenge_id,
            challenge_version=self.adapter.challenge_version,
            exam_key=EXAM,
            submission_id=submission_id,
            block=exam_cap.submission_block(
                self.ledger, self.adapter.contract_digest, submission_id
            ),
        )
        cap.settle(reservation, "SCORED_DEVELOPMENT_CANDIDATE")
        self.graded.append(submission_id)
        return {"entry_id": _sha(json.dumps(evidence["predictions"]).encode())}

    def advance_all(self):
        """The receiver's advance loop until nothing is queued; every task it moved must end SUCCEEDED."""
        moved = 0
        while self.adapter.advance():
            moved += 1
            assert moved <= len(HOTKEYS) * 2
        for provider in self.providers.values():
            for view in provider._views.values():
                assert view.state is DirectTaskStateV3.SUCCEEDED, view.state
        return moved

    def slot(self, submission_id):
        with self.ledger._db() as db:
            return db.execute(
                "SELECT state, status FROM exam_graded WHERE submission_id=? AND exam_key=?",
                (submission_id, EXAM),
            ).fetchone()

    def close(self):
        for provider in self.providers.values():
            provider.close()


def _state_root(tmp_path):
    configured = os.environ.get(STATE_ENV)
    return Path(configured) if configured else tmp_path / "door"


def _write_previous_release_ledger(path: Path):
    """Step 1: the ledger file as the previous release left it: its exam tables, rollback journal."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    AttemptLedger(path)  # the attempts tables, created as every release creates them
    with sqlite3.connect(path) as db:
        for statement in EXAM_DDL_2650BC09:
            db.execute(statement)


def test_a_carried_state_admits_builds_and_grades_after_the_release(
    tmp_path, monkeypatch, capsys
):
    root = _state_root(tmp_path)
    assert not root.exists() or not any(root.iterdir()), "the gate writes a fresh root"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    _write_previous_release_ledger(root / "attempts" / "attempts.sqlite3")
    door = Door(root, monkeypatch)
    try:
        with door.ledger._db() as db:
            assert db.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        # an upload admitted before the release (no grader has started on this root yet)
        pre = door.submit(PRE, door.recipe(), NOW)
        # 2. the release: the new grader's first start on the carried root
        door.start_grader()
        # 3. fresh admissions through the signed door: a first, and an identical recipe from another hotkey
        fresh = door.submit(FRESH, door.recipe(), NOW + 1)
        copy = door.submit(COPIER, door.recipe(), NOW + 2)
        from carbon.challenge_validator import recipe_copies

        assert recipe_copies.stored_digest(door.ledger, fresh) is not None
        assert recipe_copies.stored_digest(
            door.ledger, copy
        ) == recipe_copies.stored_digest(door.ledger, fresh)
        # 4. advance: each task built and inferred for real, SUCCEEDED by the provider's own code
        assert door.advance_all() == 3
        assert sorted(door.built) == sorted((pre, fresh, copy))
        # 5. grade: the real grade round
        assert door.grader.run_once() == (
            pre,
            "GRADED",
        )  # before the rule: never matched
        assert door.grader.run_once() == (fresh, "GRADED")
        assert door.grader.run_once() == (copy, "DUPLICATE")
        assert door.grader.run_once() is None
        assert door.graded == [pre, fresh]  # the copy never reached the exam
        assert recipe_copies.first_of(door.ledger, copy) == fresh
        assert door.slot(fresh) == ("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")
        assert door.slot(copy) == ("COUNTED", recipe_copies.DUPLICATE)
        assert door.grader.marker(copy)["state"] == "DUPLICATE"
        assert door.grader.pending() == []
        assert not any((root / "receiver" / "auto-grade" / "failures").iterdir())
        journal = capsys.readouterr().err
        assert "recipe_digest_note_failed" not in journal
        assert "direct_grade_failure" not in journal
    finally:
        door.close()
    (root / WROTE).write_text(
        json.dumps({"graded": [pre, fresh], "duplicate": copy}, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


@pytest.mark.skipif(
    not os.environ.get(STATE_ENV), reason="Rule B: run by downgrade_gate.sh only"
)
def test_a_release_rolled_back_to_grades_on_the_state_the_new_release_wrote(
    tmp_path, monkeypatch, capsys
):
    """Rule B: THIS checkout is the release a door would roll back to. Its receiver starts on the root the new release
    wrote (ledger, providers, journal, markers, pool) and must admit, build and grade a new submission from it.
    """
    root = _state_root(tmp_path)
    wrote = json.loads((root / WROTE).read_text(encoding="utf-8"))
    door = Door(root, monkeypatch)
    try:
        door.start_grader()
        for sid in (*wrote["graded"], wrote["duplicate"]):
            assert (
                door.grader.marker(sid) is not None
            )  # the new release's grades stay read
        assert door.grader.pending() == []
        # a different recipe: graded under any recipe-once rule (or none)
        after = door.submit(AFTER_ROLLBACK, door.recipe(setting=2), NOW + 10)
        assert door.advance_all() == 1
        assert door.grader.run_once() == (after, "GRADED")
        assert door.grader.run_once() is None
        assert door.graded == [after]
        journal = capsys.readouterr().err
        assert "recipe_digest_note_failed" not in journal
        assert "direct_grade_failure" not in journal
    finally:
        door.close()
