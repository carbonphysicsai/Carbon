"""A selected Challenge pack binds private result and incumbent history.

These are synthetic DEVELOPMENT originals; no worker, solver, or chain runs.
"""

import json
from types import SimpleNamespace

import pytest
from test_bank_private_evaluation import admitted, inputs
from test_score_lab_private_evaluation_evidence import _graph_case

from carbon.battery.pool_store import PoolStore, StateError
from carbon.challenge_validator.bank_promotion import BankPromotion
from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    PUBLIC_ROLES,
    SCHEMA,
    UNAVAILABLE,
    prepare_pack,
)
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.challenge_validator import lean_recipe_retention
from carbon.challenge_validator.lean_recipe_retention import (
    RetentionUnavailable,
    register_served_pack_source,
)
from carbon.research import DirectTaskStateV3


def _selected_pack(root, case, version, *, bank_bytes=None):
    draft, public, private = (root / name for name in ("draft", "public", "private"))
    for directory in (draft, public, private):
        directory.mkdir(parents=True)
    (public / "train.bin").write_bytes(case["originals"]["stage/train.npz"])
    (public / "interface.bin").write_bytes(b"synthetic-2d-interface")
    (private / "case-bank.bin").write_bytes(
        case["ordered_query_bytes"][0] if bank_bytes is None else bank_bytes
    )
    for name, value in (
        ("references.json", case["references"]),
        ("solver.json", case["registration"]["reference"]),
        ("score-pack.json", case["pack"]),
    ):
        (private / name).write_text(json.dumps(value), encoding="utf-8")
    public_roles = {name: UNAVAILABLE for name in PUBLIC_ROLES}
    public_roles.update(
        construction_kit={"inline": {"test": "synthetic-construction-kit"}},
        interface={"path": "interface.bin"},
        train={"path": "train.bin"},
        physics_contract={"inline": case["job"]["physics_contract"]},
    )
    private_roles = {name: UNAVAILABLE for name in PRIVATE_ROLES}
    private_roles.update(
        case_bank={"path": "case-bank.bin"},
        reference_rows={"path": "references.json"},
        solver_evidence={"path": "solver.json"},
        score_pack={"path": "score-pack.json"},
    )
    (draft / "evaluation-pack.json").write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "challenge": {
                    "id": case["entry"]["challenge"],
                    "version": case["entry"]["challenge_version"],
                },
                "pack_version": version,
                "public": public_roles,
                "private": private_roles,
            }
        ),
        encoding="utf-8",
    )
    selected = prepare_pack(
        draft,
        "evaluation-pack.json",
        public_root=public,
        private_root=private,
        challenge_id=case["entry"]["challenge"],
        challenge_version=case["entry"]["challenge_version"],
    ).snapshot
    return selected, public, private


def _registered_source(tmp_path, monkeypatch, case, selected, public, private, name):
    discovery = SimpleNamespace(
        evaluation_pack_snapshot=selected,
        evaluation_pack_digest=selected.manifest_digest,
        evaluation_pack_public_root=public,
        evaluation_pack_private_root=private,
    )
    adapter = object.__new__(LeanRecipeAdapter)
    adapter.discovery = discovery
    task_root = tmp_path / (name + "-task")
    task_root.mkdir(mode=0o700)
    entry_path = tmp_path / (name + "-entry.json")
    entry_path.write_text(json.dumps(case["entry"]), encoding="utf-8")
    retained = {
        "evaluation_pack_digest": selected.manifest_digest,
        "entry_id": case["entry"]["entry_id"],
        "entry_path": entry_path,
        "artifact_path": task_root,
    }
    monkeypatch.setattr(
        lean_recipe_retention, "retain_served_result", lambda *args, **kwargs: retained
    )
    return register_served_pack_source(
        adapter,
        "rtsk_" + ("a" if name == "old" else "b") * 64,
        artifact_directory=tmp_path,
        entry_directory=tmp_path,
        trusted_job=case["job"],
        registration=case["registration"],
        ordered_query_bytes=case["ordered_query_bytes"],
        evaluation_version="synthetic-eval-v1",
    )


def test_selected_pack_changes_private_result_key_without_rewriting_history(
    tmp_path, monkeypatch
):
    case = _graph_case(tmp_path)
    state = tmp_path / "bank.sqlite3"
    store = PoolStore(state, clock=lambda: 123.0)
    for model in ("inc", "candidate"):
        admitted(store, case, model)
    store.set_incumbent("inc", "synthetic historical fixture")
    with store.db() as db:
        incumbent_since = db.execute("SELECT since FROM incumbent").fetchone()
    legacy_pin, args = inputs(case)
    legacy_flow = BankPromotion(store, registered_source_receipt_sha256=legacy_pin)
    legacy_result = legacy_flow.retain_private("inc", **args)
    old, old_public, old_private = _selected_pack(tmp_path / "old-pack", case, "1")
    old_source = _registered_source(
        tmp_path, monkeypatch, case, old, old_public, old_private, "old"
    )
    old_flow = BankPromotion(
        store,
        registered_source_receipt_sha256=old_source["registered_source_receipt_sha256"],
    )
    old_result = old_flow.retain_private(
        "inc",
        **{
            **args,
            "entry": old_source["entry"],
            "references": old_source["references"],
            "score_pack": old_source["score_pack"],
            "evaluation_source_receipt_raw": old_source[
                "evaluation_source_receipt_raw"
            ],
            "expected_evaluation_pack_digest": old_source[
                "expected_evaluation_pack_digest"
            ],
        },
    )
    assert old_result["evaluation_key"] != legacy_result["evaluation_key"]
    projected_adapter = object.__new__(LeanRecipeAdapter)
    projected_adapter.challenge_id = case["entry"]["challenge"]
    projected_adapter.challenge_version = case["entry"]["challenge_version"]
    task = SimpleNamespace(
        state=DirectTaskStateV3.SUCCEEDED,
        task_id=SimpleNamespace(value="rtsk_" + "c" * 64),
        terminal_receipt=SimpleNamespace(
            state_digest=case["entry"]["state_digest"],
            predictions_digest="sha256:" + "d" * 64,
        ),
    )
    provider = SimpleNamespace(
        public_result=lambda _task: {
            "official_eligible": False,
            "predictions_digest": task.terminal_receipt.predictions_digest,
            "evaluation_pack_digest": old.manifest_digest,
        }
    )
    assert old.manifest_digest not in json.dumps(
        projected_adapter._project(task, provider)
    )

    new, new_public, new_private = _selected_pack(tmp_path / "new-pack", case, "2")
    assert new.manifest_digest != old.manifest_digest
    new_source = _registered_source(
        tmp_path, monkeypatch, case, new, new_public, new_private, "new"
    )
    assert new_source["score_pack"] == old_source["score_pack"]
    assert (
        new_source["registered_source_receipt_sha256"]
        != old_source["registered_source_receipt_sha256"]
    )
    new_flow = BankPromotion(
        store,
        registered_source_receipt_sha256=new_source["registered_source_receipt_sha256"],
    )
    new_args = {
        **args,
        "entry": new_source["entry"],
        "references": new_source["references"],
        "score_pack": new_source["score_pack"],
        "evaluation_source_receipt_raw": new_source["evaluation_source_receipt_raw"],
        "expected_evaluation_pack_digest": new_source[
            "expected_evaluation_pack_digest"
        ],
    }
    with pytest.raises(StateError, match="evaluation_pack_pin_mismatch"):
        new_flow.retain_private(
            "candidate",
            **{**new_args, "expected_evaluation_pack_digest": old.manifest_digest},
        )
    revised = new_flow.retain_private("candidate", **new_args)
    assert revised["evidence"]["evaluation_pack_digest"] == new.manifest_digest
    assert revised["evaluation_key"] != old_result["evaluation_key"]
    with pytest.raises(StateError, match="incumbent_evaluation_required"):
        new_flow.private_pair("candidate", revised["evaluation_key"])

    reopened = PoolStore(state, clock=lambda: 999.0)
    for pin, result in (
        (legacy_pin, legacy_result),
        (old_source["registered_source_receipt_sha256"], old_result),
    ):
        history = BankPromotion(reopened, registered_source_receipt_sha256=pin)
        assert (
            history.private_pair("inc", result["evaluation_key"])["candidate"] == result
        )
    assert reopened.incumbent()["model_id"] == "inc"
    with reopened.db() as db:
        assert db.execute("SELECT since FROM incumbent").fetchone() == incumbent_since


def test_same_challenge_and_version_with_different_case_material_refuses(
    tmp_path, monkeypatch
):
    case = _graph_case(tmp_path)
    selected, public, private = _selected_pack(
        tmp_path / "wrong-pack", case, "1", bank_bytes=b"different query"
    )
    with pytest.raises(RetentionUnavailable, match="registered_material_mismatch"):
        _registered_source(
            tmp_path, monkeypatch, case, selected, public, private, "old"
        )
