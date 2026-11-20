"""LEAD #1 (no door-wide admission lock), V2's MUST-SHOW 21:12Z: the cross-owner WRITES of parallel admissions.

`_write` used to serialise every admission's writes too. Now admissions of different allowance groups and coldkeys run
at once, through the REAL path (`DirectRecipeIntake._admit` -> `Validator.evaluate` -> `LeanRecipeAdapter.evaluate` ->
each owner's own `DirectDevelopmentTasksV3.start_research_task`), all writing ONE shared `AttemptLedger` (every write its
own BEGIN IMMEDIATE transaction under the ledger's busy wait). 16 owners of 16 coldkeys, each sending its recipe twice at
once: every admission answered OUTCOME (no 'database is locked', no Unavailable from contention), each owner's duplicate
admitted once, one intent per task, one OUTCOME row per admission with unique ledger seqs, a strict first-arrival queue
order of the 16 tasks, and the admissions really overlapped (they are not serialised behind one lock). Fixture doubles
only for the images (`_fixture`).
"""

from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

from test_admission_scope import _Grouping, _Snapshot
from test_direct_v3_durable_tasks import _fixture

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import (
    Adapters,
    AttemptLedger,
    Submission,
    Validator,
    exam_cap,
)
from carbon.challenge_validator.direct_intake import DirectRecipeIntake
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

OWNERS = 16
START_SECONDS = 0.05


def test_sixteen_owners_admit_in_parallel_and_every_shared_write_stays_exact(
    tmp_path, monkeypatch
):
    (tmp_path / "fixture").mkdir()
    request, factory, discovery = _fixture(
        tmp_path / "fixture", monkeypatch, material=bundle_material_v5()
    )
    fixed = factory()
    image, inference = fixed.image, fixed.inference_image
    owners = [f"5Owner{i:02d}".ljust(48, "x") for i in range(OWNERS)]
    providers = {}
    for index, owner in enumerate(owners):
        base = tmp_path / "owners" / f"{index:02d}"
        base.mkdir(parents=True)
        providers[owner] = DirectDevelopmentTasksV3(
            root=base / "tasks",
            requester=owner,
            ledger=CampaignLedger(base / "ledger"),
            owner=owner,
            discovery=discovery,
            image=image,
            inference_image=inference,
        )
    root = tmp_path / "attempts"
    root.mkdir(mode=0o700)
    ledger = AttemptLedger(root / "ledger.sqlite3")
    adapter = LeanRecipeAdapter(discovery, providers.get, ledger)
    snapshot = _Snapshot({owner: "ck-" + owner[:8] for owner in owners})
    grouping = _Grouping(snapshot, {owner: "g:" + owner[:8] for owner in owners})

    # a task start that takes live time, and a count of how many run at once
    inside = {"now": 0, "max": 0}
    guard = threading.Lock()
    real_start = DirectDevelopmentTasksV3.start_research_task

    def start(provider, *args, **kwargs):
        with guard:
            inside["now"] += 1
            inside["max"] = max(inside["max"], inside["now"])
        try:
            time.sleep(START_SECONDS)
            return real_start(provider, *args, **kwargs)
        finally:
            with guard:
                inside["now"] -= 1

    monkeypatch.setattr(DirectDevelopmentTasksV3, "start_research_task", start)
    intake = object.__new__(DirectRecipeIntake)
    intake.door = Validator(Adapters([adapter]), ledger)
    intake.adapter = adapter
    intake.window = SimpleNamespace(latest=lambda: snapshot)
    strategy = json.dumps(request.recipe, sort_keys=True)
    sends = [(owner, n) for n, owner in enumerate(owners * 2)]  # each recipe twice
    barrier = threading.Barrier(len(sends))
    results = {}

    def send(owner, n):
        barrier.wait(30)
        results[n] = (
            owner,
            intake._admit(
                Submission(
                    owner,
                    {"sequence": n + 1, "digest": f"{n + 1:064x}"},
                    adapter.challenge_id,
                    adapter.challenge_version,
                    strategy,
                    adapter.contract_digest,
                )
            ),
        )

    exam_cap.install_grouping(grouping)
    try:
        threads = [threading.Thread(target=send, args=s) for s in sends]
        for t in threads:
            t.start()
        for t in threads:
            t.join(120)
    finally:
        exam_cap.install_grouping(None)
    # every admission answered, none refused by contention
    assert len(results) == len(sends)
    kinds = {n: r[1]["kind"] for n, r in results.items()}
    assert set(kinds.values()) == {"OUTCOME"}, kinds
    # each owner's duplicate admitted once: one task per owner, 16 tasks in all
    task_of = {}
    for owner, result in results.values():
        task = result["outcome"]["submission_id"]
        assert task_of.setdefault(owner, task) == task
    assert len(set(task_of.values())) == OWNERS
    assert all(len(providers[o]._views) == 1 for o in owners)
    # the shared ledger: one intent per task, one OUTCOME row per admission, unique seqs, a strict queue order
    with ledger._read() as db:
        intents = db.execute(
            "SELECT submission_id, hotkey FROM recipe_task_intents"
        ).fetchall()
        rows = db.execute(
            "SELECT seq, submission_id, hotkey FROM attempts WHERE kind='OUTCOME' "
            "ORDER BY seq"
        ).fetchall()
    assert sorted(intents) == sorted((t, o) for o, t in task_of.items())
    assert len(rows) == len(sends)
    assert len({seq for seq, _t, _o in rows}) == len(rows)
    assert all(task_of[owner] == task for _seq, task, owner in rows)
    first = []
    for _seq, task, _owner in rows:
        if task not in first:
            first.append(task)
    # each task holds exactly one place
    assert sorted(first) == sorted(task_of.values())
    # the admissions overlapped: different groups and coldkeys never wait for each other
    assert inside["max"] > 1, inside
