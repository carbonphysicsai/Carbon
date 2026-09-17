"""Loopback control adapter over Carbon's existing finite research runner.

Only the local operator supplies configuration/paths. Browser callers select an
opaque profile. No scientific loop, evaluator or consumption ledger lives here.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_admission import Admission, private_json
from carbon.development_session.research_control import CampaignControl, DispatchStopped
from carbon.development_session.research_ledger import CampaignLedger
from scripts.dev.miner_launchpad.controller import Rejected, owner_lock

PATH_FIELDS = {
    "image_manifest",
    "analysis_image_manifest",
    "operator_config",
    "api_key_file",
    "miner_public",
    "miner_password_file",
    "quarantine_journal",
}


class RunnerAdapter:
    def __init__(self, database, *, configuration=None, principal=None):
        self.database = database
        self.configuration = configuration
        self.principal = (
            private_json(configuration)["principal"]
            if configuration is not None
            else principal
        )
        self.threads = {}
        self.lock = threading.RLock()
        with self.db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS research_runs (id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, profile TEXT NOT NULL, principal TEXT NOT NULL, config_digest TEXT NOT NULL, grant_digest TEXT NOT NULL, campaign TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL, root TEXT NOT NULL, grant_record BLOB NOT NULL, grant_id TEXT UNIQUE NOT NULL)"
            )
            roots = [
                Path(r[0])
                for r in db.execute(
                    "SELECT root FROM research_runs WHERE principal=?",
                    (self.principal,),
                )
            ]
        for root in roots:
            if (root / "campaign.sqlite3").exists():
                try:
                    with owner_lock(root):
                        control = CampaignControl(CampaignLedger(root))
                        if control.status()["state"] not in {
                            "COMPLETED",
                            "STOPPED",
                            "PAUSED",
                        }:
                            control.settled(control.acquire(), cleanup_verified=False)
                except RuntimeError:
                    pass  # Another live owner still holds the exact campaign lock.

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def configured(self):
        if self.configuration is None:
            raise ValueError("operator configuration absent")
        cfg = private_json(self.configuration)
        if (
            set(cfg)
            != {
                "schema",
                "profile_id",
                "principal",
                "grant_file",
                "account_ref",
                "enabled",
                "paths",
                "accepted_revision",
            }
            or cfg["schema"] != "carbon.launchpad.runner-profile.v1"
        ):
            raise ValueError("closed operator configuration required")
        if set(cfg["paths"]) != PATH_FIELDS:
            raise ValueError("closed runner inputs required")
        if any(
            type(v) is not str or not Path(v).is_absolute()
            for v in cfg["paths"].values()
        ):
            raise ValueError("operator paths must be absolute")
        admission = Admission.load(Path(cfg["grant_file"]))
        doc = admission.document
        root = Path(doc["root"])
        admission.verify(
            root=root,
            principal=cfg["principal"],
            runtime=doc["runtime"],
            now=time.time(),
        )
        if (
            cfg["enabled"] is not True
            or cfg["principal"] != self.principal
            or cfg["account_ref"] != doc["account_ref"]
            or cfg["accepted_revision"] != doc["runtime"]["implementation"]["revision"]
        ):
            raise ValueError("admission disabled or runtime/account mismatch")
        return cfg, admission, root

    def preflight(self):
        try:
            cfg, admission, _ = self.configured()
            return {
                "available": True,
                "profile": cfg["profile_id"],
                "mode": "LIVE_PRACTICE_RESEARCH",
                "challenge": admission.document["profile"],
                "agent": "carbon-autoresearch",
                "reasoning": "gpt-5-mini-2025-08-07",
                "compute": "local-isolated-cpu",
                "ceilings": admission.document["ceilings"],
                "expires_unix": admission.document["expires_unix"],
                "status": "GRANT_CONFIGURED_RUNTIME_CHECK_AT_START",
            }
        except Exception:  # noqa: BLE001 - private configuration errors stay private.
            return {
                "available": False,
                "profile": None,
                "status": "ADMISSION_DISABLED",
                "reason": "A separate approved grant, existing miner and exact accepted runtime/images are required.",
            }

    def launch(self, value, key):
        if type(value) is not dict or set(value) != {"profile"}:
            raise Rejected("closed_research_launch_required")
        if (
            type(key) is not str
            or not 16 <= len(key) <= 80
            or not all(c.isascii() and (c.isalnum() or c in "-_") for c in key)
        ):
            raise Rejected("invalid_idempotency_key")
        try:
            cfg, admission, root = self.configured()
        except Exception:  # noqa: BLE001
            raise Rejected("research_admission_unavailable", 409) from None
        if value["profile"] != cfg["profile_id"] or cfg["principal"] != self.principal:
            raise Rejected("research_profile_mismatch", 409)
        run_id = digest(
            canonical([admission.document["campaign_id"], cfg["principal"]])
        )[7:39]
        config_pin = digest(canonical(cfg))
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT * FROM research_runs WHERE request_key=? OR id=? OR grant_id=?",
                (key, run_id, admission.document["grant_id"]),
            ).fetchall()
            if previous:
                if len(previous) != 1 or any(
                    previous[0][k] != v
                    for k, v in {
                        "id": run_id,
                        "profile": cfg["profile_id"],
                        "principal": cfg["principal"],
                        "config_digest": config_pin,
                        "grant_digest": admission.pin,
                    }.items()
                ):
                    raise Rejected("research_launch_replay_conflict", 409)
            else:
                db.execute(
                    "INSERT INTO research_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        key,
                        cfg["profile_id"],
                        cfg["principal"],
                        config_pin,
                        admission.pin,
                        admission.document["campaign_id"],
                        "QUEUED",
                        time.time(),
                        str(root),
                        canonical(
                            {
                                "path": str(admission.path),
                                "document": admission.document,
                            }
                        ),
                        admission.document["grant_id"],
                    ),
                )
        # A lost HTTP response cannot produce a second campaign. The identity is
        # grant-derived; its original root and OS lease are independent of this DB.
        self._start(run_id, cfg, admission, root)
        return self.get(run_id)

    def _start(self, run_id, cfg, admission, root):
        with self.lock:
            if run_id in self.threads and self.threads[run_id].is_alive():
                return
            thread = threading.Thread(
                target=self._run, args=(run_id, cfg, admission, root), daemon=True
            )
            self.threads[run_id] = thread
            thread.start()

    def _run(self, run_id, cfg, admission, root):
        from carbon.development_session.research_agent_policy import AUTONOMOUS
        from carbon.development_session.research_campaign import execute

        generation = None
        try:
            with owner_lock(root):
                ledger = CampaignLedger(root, admission=admission)
                control = CampaignControl(ledger)
                generation = control.acquire()
                ledger.generation = generation
                # Ambiguous work never resumes automatically, even under a new
                # generation. Completed observations remain replayable by runner.
                with ledger.db() as db:
                    pending = db.execute(
                        "SELECT 1 FROM operations WHERE state='RESERVED' LIMIT 1"
                    ).fetchone()
                if pending:
                    raise DispatchStopped("unresolved operation")
                args = SimpleNamespace(
                    **{k: Path(v) for k, v in cfg["paths"].items()},
                    root=root,
                    accepted_revision=cfg["accepted_revision"],
                    principal=cfg["principal"],
                    agent_policy=AUTONOMOUS,
                    command=(
                        "resume"
                        if (root / "campaign-manifest.json").exists()
                        else "run"
                    ),
                )
                try:
                    asyncio.run(execute(args, ledger=ledger))
                except Exception:  # noqa: BLE001 - never publish provider/key errors.
                    with self.db() as db:
                        db.execute(
                            "UPDATE research_runs SET state='INTERRUPTED' WHERE id=?",
                            (run_id,),
                        )
                finally:
                    clean = self._cleanup(ledger)
                    control.settled(
                        generation,
                        completed=(root / "campaign-complete.json").exists(),
                        cleanup_verified=clean,
                    )
        except Exception:  # noqa: BLE001
            with self.db() as db:
                db.execute(
                    "UPDATE research_runs SET state='RECONCILIATION_REQUIRED' WHERE id=?",
                    (run_id,),
                )
            if generation is not None:
                control.settled(generation, cleanup_verified=False)

    @staticmethod
    def _cleanup(ledger):
        """Use domain cleanup journals; absence of a browser process proves nothing."""
        from carbon.development_session.research_carrier import reconcile_worker
        from carbon.execution import DurableWorkerLaunchStore
        from carbon.reconstruction.worker.docker_runtime import (
            DockerCLI,
            remove_exact_container,
        )
        from carbon.reconstruction.worker.operator import _stores

        clean = True
        with ledger.db() as db:
            rows = db.execute(
                "SELECT id,owner,reservation FROM operations WHERE state='RESERVED'"
            ).fetchall()
        for identity, owner, reserved in rows:
            if json.loads(reserved).get("numerical_milliseconds"):
                try:
                    reconcile_worker(ledger, owner=owner, identity=identity)
                except Exception:  # noqa: BLE001
                    clean = False
        for path in _stores(ledger.root):
            store = DurableWorkerLaunchStore(path)
            for item in store.reconciliation_targets():
                try:
                    cli = DockerCLI()
                    remove_exact_container(
                        cli=cli,
                        container_name=item["container_name"],
                        launch_digest=item["launch_digest"],
                    )
                    if cli.run(
                        [
                            "ps",
                            "-aq",
                            "--filter",
                            "name=^" + item["container_name"] + "$",
                        ],
                        timeout=10,
                    ).stdout.strip():
                        raise ValueError("owned worker remains")
                    store.record_operator_cleanup(
                        execution_id=item["execution_id"],
                        launch_digest=item["launch_digest"],
                        cleaned=True,
                    )
                except Exception:  # noqa: BLE001
                    clean = False
        return clean

    def _bound(self, identity):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM research_runs WHERE id=?", (identity,)
            ).fetchone()
        if row is None or row["principal"] != self.principal:
            raise Rejected("research_run_unavailable", 404)
        # Expiry/revocation never removes access to stop or original evidence.
        # Retained trusted associations cannot redirect to a changed grant root.
        record = json.loads(row["grant_record"])
        admission = Admission(
            Path(record["path"]), row["grant_digest"], record["document"]
        )
        return row, admission, Path(row["root"])

    def control(self, identity, action):
        row, admission, root = self._bound(identity)
        ledger = CampaignLedger(root, admission=admission)
        control = CampaignControl(ledger)
        if action == "reconcile":
            with owner_lock(root):
                generation = control.acquire()
                control.settled(generation, cleanup_verified=self._cleanup(ledger))
        else:
            if action == "resume":
                cfg, current, current_root = self.configured()
                if (
                    digest(canonical(cfg)) != row["config_digest"]
                    or current.pin != admission.pin
                    or current_root != root
                ):
                    raise ValueError("resume binding differs")
            control.request(action)
            if action == "stop":
                from carbon.development_session.research_carrier import request_cancel

                with ledger.db() as db:
                    operations = db.execute(
                        "SELECT id,owner FROM operations WHERE state='RESERVED'"
                    ).fetchall()
                for operation, owner in operations:
                    request_cancel(ledger, owner=owner, identity=operation)
            if action == "resume":
                self._start(identity, cfg, admission, root)
        return self.get(identity)

    def get(self, identity):
        from scripts.dev.miner_launchpad.projection import project

        row, _, root = self._bound(identity)
        return project(dict(row), root)

    def recent(self):
        with self.db() as db:
            ids = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM research_runs WHERE principal=? ORDER BY created DESC LIMIT 100",
                    (self.principal,),
                )
            ]
        result = []
        for identity in ids:
            try:
                result.append(self.get(identity))
            except Rejected:
                result.append(
                    {
                        "id": identity,
                        "state": "READBACK_UNAVAILABLE",
                        "mode": "LIVE_PRACTICE_RESEARCH",
                    }
                )
        return result

    def close(self):
        for identity, thread in tuple(self.threads.items()):
            if thread.is_alive():
                try:
                    self.control(identity, "stop")
                except Exception:  # noqa: BLE001
                    with self.db() as db:
                        db.execute(
                            "UPDATE research_runs SET state='RECONCILIATION_REQUIRED' WHERE id=?",
                            (identity,),
                        )
        for thread in tuple(self.threads.values()):
            thread.join(timeout=1)
