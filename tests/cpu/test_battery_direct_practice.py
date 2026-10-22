"""Direct Battery practice bypasses the historical backbone compiler."""

import json
from pathlib import Path
from types import SimpleNamespace

from carbon.battery import (
    construction_kit,
    direct_graph,
    direct_graph_inference,
    direct_graph_worker,
)
from carbon.battery.public_model_retention import (
    OPT_IN_SCHEMA,
    PROGRAM_VERSION,
    inventory,
)
from carbon.battery.research import BatteryPractice
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.development_session.profile import digest
from carbon.development_session.research_ledger import VERSION, CampaignLedger
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.level4 import staging, submission

ROOT = Path(__file__).resolve().parents[2]


def _recipe(graph_digest):
    kit = construction_kit.construction_kit()
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": kit,
        "source": {"kind": "graph", "submission_digest": graph_digest},
        "procedure": {
            "entrypoint": None,
            "configuration": {"training": {"steps": 16, "batch_size": 8}},
            "train_use": {
                "dataset": direct_graph.TRAIN_USE,
                "train_fraction": 0.1,
                "curriculum": "none",
            },
            "initial_state": None,
        },
        "output": {
            "format": direct_graph.OUTPUT_FORMAT,
            "interface_digest": kit["interface_digest"],
        },
    }


def test_direct_practice_uses_exact_owner_graph_and_retains_state(
    tmp_path, monkeypatch
):
    ledger = CampaignLedger(tmp_path / "campaign")
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": {},
            "elapsed_seconds": None,
            "campaign_id": "direct-test",
            "implementation": "fixture",
            "objective": "fixture",
            "sampling": "fixture",
            "control": "none",
            "selection": "none",
            "replica_policy": "fixture",
            "provider": "none",
            "owner": "alice",
        }
    )
    raw = b'{"documents":{}}'
    workspace = ResearchWorkspace(ledger, "alice")
    workspace.put(staging.WORKSPACE_MANIFEST, raw)
    strategy = _recipe(submission.name(raw))
    opt_in = {
        "schema": OPT_IN_SCHEMA,
        "campaign_id": "direct-test",
        "scope": "PUBLIC_GRAPHITE_TEST",
        "program_version": PROGRAM_VERSION,
        "source_commit": "a" * 40,
    }
    practice = BatteryPractice(
        ledger=ledger,
        owner="alice",
        root=ROOT,
        image=SimpleNamespace(image_id="sha256:" + "a" * 64),
        construction_mode="direct",
        model_retention=opt_in,
    )
    monkeypatch.setattr(
        practice,
        "compile",
        lambda *_: (_ for _ in ()).throw(AssertionError("legacy compile")),
    )
    predictions = {row["case_id"]: row["outputs"] for row in practice.practice.records}
    from carbon.battery import practice_safety

    decision = practice_safety.decision_set(ROOT)
    predictions.update(
        {case: decision.references[case]["outputs"] for case in decision.case_ids}
    )
    # C13: the model's predictions on the public development bank (the reference
    # rows themselves; the unmeasured probe rows get a fixed valid row).
    import numpy as np

    from carbon.battery import domain
    from carbon.challenge_kit import physical_pack

    bank = physical_pack.development_bank(
        "battery-fastcharge-ageing-development-v1", "2.0"
    )
    references = np.asarray(bank["references"], dtype=float)
    fixed = references[~np.isnan(references).any(axis=1)][0]
    g = domain.GRID_POINTS
    for case_id, row in zip(bank["case_ids"], references, strict=True):
        row = fixed if np.isnan(row).any() else row
        predictions.setdefault(
            case_id,
            {
                "voltage_v": row[:g].tolist(),
                "temperature_c": row[g : 2 * g].tolist(),
                "plating_margin_v": float(row[2 * g]),
                "capacity_ah": row[2 * g + 1 :].tolist(),
            },
        )
    operation = ledger.root / "operation-direct-test" / "snapshot"
    operation.mkdir(parents=True)
    state = b"numeric-state-fixture"
    (operation / "state.npz").write_bytes(state)
    seen = {}
    recipe_digest = ConstructionRecipe.from_dict(strategy).digest

    def reconstruct(_ledger, **kwargs):
        seen.update(kwargs)
        return direct_graph_worker.DirectGraphResult(
            recipe_digest=recipe_digest,
            graph_digest=strategy["source"]["submission_digest"],
            interface_digest=strategy["challenge"]["interface_digest"],
            train_digest=strategy["challenge"]["train_digest"],
            state_digest=digest(state),
            state_path=operation / "state.npz",
            predictions_digest=digest(b"fixture-predictions"),
            predictions=predictions,
            fit={"n_params": 123, "params_sha256": "fixture", "train_loss": 1.5},
            worker_operation="operation-direct-test",
        )

    monkeypatch.setattr(direct_graph_worker, "reconstruct_public", reconstruct)

    def infer(_ledger, **kwargs):
        assert kwargs["build"].state_digest == digest(state)
        assert kwargs["identity"].startswith("direct-infer-")
        return direct_graph_inference.DirectInferenceResult(
            recipe_digest,
            digest(state),
            digest(b"inference-predictions"),
            predictions,
            "operation-inference-test",
        )

    monkeypatch.setattr(direct_graph_inference, "infer_public", infer)
    result = practice("trial-1", strategy)
    assert seen["owner"] == "alice" and seen["root"] == ROOT
    assert (
        seen["source_envelope"]
        == json.dumps(
            staging.envelope(raw, {}), sort_keys=True, separators=(",", ":")
        ).encode()
    )
    assert len(seen["test_inputs"]["cases"]) >= len(practice.practice.case_ids)
    assert result["schema"] == "carbon.battery.direct-practice-feedback.v2"
    dual = result["practice_dual"]
    assert dual["schema"] == "carbon.practice.dual-feedback.v1"
    assert dual["challenge"]["version"] == "2.0" and dual["available"] is True
    assert dual["n_cases"] == len(bank["case_ids"])
    assert dual["gates"]["paired_repeat"] == "NOT_TESTED_ON_PRACTICE"
    assert dual["eligible"] is True and 0 < dual["total"] <= 1
    # The bank's decision and probe cases were asked of the model, once.
    asked = {c["case_id"] for c in seen["test_inputs"]["cases"]}
    assert set(bank["case_ids"]) <= asked
    assert result["provenance"] == "BATTERY_PUBLIC_PRACTICE"
    assert result["worker"]["inference_operation"] == "operation-inference-test"
    assert result["recipe"] == strategy and result["official_eligible"] is False
    assert workspace.get(result["model"]["workspace_name"]) == state
    retained = inventory(ledger, owner="alice")
    assert len(retained) == 1
    assert retained[0]["status"] == "COMPLETED"
    assert retained[0]["state"]["sha256"] == digest(state)
