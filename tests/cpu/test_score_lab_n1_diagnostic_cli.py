"""Synthetic saved-model/producer bundles; no fit, physical solver or hidden data."""

from __future__ import annotations

import hashlib
import json

import pytest

from carbon.design_search import tasks
from carbon.development_comparison import carbon_arm
from scripts.dev.score_lab import n1_diagnostic as cli
from scripts.dev.score_lab import owner_v3_n1 as diagnostic
from scripts.dev.score_lab import owner_v3_panel_export as producer
from tests.cpu.test_score_lab_owner_v3_n1 import commitment
from tests.cpu.test_score_lab_owner_v3_panel_export import fixture as producer_fixture


def _bytes(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def bundle():
    files, artifacts, rows, banks, draws = {}, {}, [], [], []

    def add(name, raw):
        artifacts[name] = raw
        files[name] = {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}
        return name

    for i, role in enumerate(("LEG", "VALUE")):
        args = producer_fixture()
        task = args["registered"]
        task["task_id"] = "synthetic-cli-" + role
        task["task_digest"] = tasks.digest(
            {k: v for k, v in task.items() if k != "task_digest"}
        )
        args["manifest"]["task_digest"] = task["task_digest"]
        args["expected_manifest_digest"] = tasks.digest(args["manifest"])
        evidence = producer.build(**args)
        draw = {
            "population": "P",
            "role": role,
            "outer_weight": 1,
            "bank_cluster": args["expected_plan_digest"],
            "task": task,
        }
        rows.append({"draw": draw, "evidence": evidence})
        draws.append(draw)
        binding = {
            k: evidence.receipt[k]
            for k in ("plan_digest", "source_pins_digest", "manifest_digest")
        }
        banks.append(
            {
                "population_index": i,
                "plan": add("plan.json", _bytes(args["plan"])),
                "source_pins": add("pins.json", _bytes(args["source_pins"])),
                "manifest": add(f"producer-{i}.json", _bytes(args["manifest"])),
                "raw_chunks": {
                    k: add(k + ".jsonl", raw) for k, raw in args["raw_chunks"].items()
                },
                "binding": binding,
            }
        )
    view_digest = tasks.digest(
        {
            "schema": producer.CANDIDATE_VIEW,
            "scope": "SYNTHETIC_FIXTURE",
            "family": "battery-v3",
            "questions": [r["evidence"].prediction_view["questions"][0] for r in rows],
        }
    )
    manifest = {
        "schema": cli.SCHEMA,
        "scope": "SYNTHETIC_FIXTURE",
        "job": "battery-v3-job-dev-v1",
        "population": "P",
        "registration_sha256": diagnostic.REGISTRATION_SHA256,
        "files": files,
        "draws": add("draws.json", _bytes(draws)),
        "banks": banks,
        "members": [],
        "gamers": [],
        "bootstrap": 20,
        "seed": 7,
    }
    for n in range(3):
        mid = f"toy-model-{n}"
        physical = []
        for panel in rows[0]["evidence"].references:
            for (candidate, condition), point in panel["values"].items():
                point = dict(point)
                if candidate == f"p{n}-h1":
                    point["minutes"] = 1.0
                physical.append(
                    {
                        "band": panel["index_value"],
                        "candidate": candidate,
                        "condition": condition,
                        "values": point,
                    }
                )
        fit = {
            "schema": carbon_arm.RECEIPT,
            "scope": "SYNTHETIC_FIXTURE",
            "kit": "carbon.battery-v3.kit.v1",
            "model_id": mid,
            "export_digest": view_digest,
            "train": {"sha256": "sha256:" + "d" * 64, "fixture": True},
            "code": {"actual_source": {"commit": "a" * 40}},
        }
        prediction = {
            "schema": carbon_arm.PREDICTIONS,
            "scope": "SYNTHETIC_FIXTURE",
            "model_id": mid,
            "export_digest": view_digest,
            "source_receipt_digest": "sha256:"
            + hashlib.sha256(carbon_arm.canonical(fit)).hexdigest(),
            "rows": physical,
        }
        commitments = []
        for i, row in enumerate(rows):
            panels = cli._panels(
                row["draw"],
                {
                    (p["band"], p["candidate"], p["condition"]): p["values"]
                    for p in physical
                },
            )
            committed = commitment(row, panels)
            # Reuse the frozen toy optimizer; bind the original saved identity.
            committed["model_id"] = mid
            for sub in committed["subcommitments"]:
                sub["model_id"] = mid
                sub["commitment_digest"] = tasks.digest(
                    {k: v for k, v in sub.items() if k != "commitment_digest"}
                )
            committed["commitment_digest"] = tasks.digest(
                {k: v for k, v in committed.items() if k != "commitment_digest"}
            )
            commitments.append(
                {
                    "population_index": i,
                    **{
                        k: row["draw"][k]
                        for k in ("population", "role", "outer_weight", "bank_cluster")
                    },
                    "commitment": committed,
                }
            )
        raw_commitments = b"".join(_bytes(c) for c in commitments)
        receipt = {
            "scope": "SYNTHETIC_FIXTURE",
            "model_id": mid,
            "references_joined": False,
            "sealed_holdout_read": False,
            "commitments_sha256": hashlib.sha256(raw_commitments).hexdigest(),
            "model_predictions_sha256": hashlib.sha256(_bytes(prediction)).hexdigest(),
        }
        manifest["members"].append(
            {
                "id": mid,
                "recipe": f"recipe-{n}",
                "predictions": add(f"pred-{n}.json", _bytes(prediction)),
                "fit_receipt": add(f"fit-{n}.json", _bytes(fit)),
                "commitments": add(f"commits-{n}.jsonl", raw_commitments),
                "commitment_receipt": add(f"receipt-{n}.json", _bytes(receipt)),
                "train_sha256": "d" * 64,
                "fit_source": "a" * 40,
                "kit": fit["kit"],
            }
        )
    return manifest, artifacts, rows


def _replace(manifest, artifacts, key, value):
    artifacts[key] = _bytes(value)
    manifest["files"][key]["sha256"] = hashlib.sha256(artifacts[key]).hexdigest()


def test_complete_diagnostic_is_exactly_direct_library_calls_and_replays():
    manifest, artifacts, rows = bundle()
    result = cli.evaluate(manifest, artifacts)
    assert result == cli.evaluate(manifest, artifacts)
    legs, values = {}, {}
    for member in manifest["members"]:
        physical, commits = cli._member(
            member,
            artifacts.__getitem__,
            [r["draw"] for r in rows],
            json.loads(artifacts[member["predictions"]])["export_digest"],
            "SYNTHETIC_FIXTURE",
        )
        for i, row in enumerate(rows):
            qid = row["draw"]["task"]["task_digest"]
            bindings = {qid: manifest["banks"][i]["binding"]}
            kwargs = {
                "producer_bindings": bindings,
                "expected_registration_digest": diagnostic.REGISTRATION_SHA256,
                "scope": "SYNTHETIC_FIXTURE",
            }
            if row["draw"]["role"] == "LEG":
                legs[member["id"]] = diagnostic.score_leg(
                    [row], {qid: cli._panels(row["draw"], physical)}, **kwargs
                )
            else:
                values[member["id"]] = diagnostic.judge_values(
                    [row], {qid: commits[i]}, **kwargs
                )
    expected = diagnostic.alignment(
        legs,
        values,
        recipe_of={m["id"]: m["recipe"] for m in manifest["members"]},
        gamers=[],
        bootstrap=20,
        seed=7,
    )
    assert result["members"] == {"legs": legs, "values": values}
    assert result["alignment"] == expected
    assert expected["recipe_clusters"] == 3
    assert set(expected["rules"]) == {diagnostic.N1, diagnostic.CONTROL}
    assert expected["rules"][diagnostic.N1]["bootstrap"] is not None
    assert expected["stage_c_or_d_adoption"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("scope", "PRIVATE"),
        ("job", "battery-v3-job-guard419-dev-v1"),
        ("population", "MIXED"),
    ],
)
def test_context_refusal_precedes_any_artifact_access(field, value):
    manifest, _, _ = bundle()
    manifest[field] = value

    class NoReads:
        def __getitem__(self, _key):
            raise AssertionError("forbidden input access")

    with pytest.raises(cli.Refused, match="DEVELOPMENT_CONTEXT_REQUIRED"):
        cli.evaluate(manifest, NoReads())


def test_mixed_roles_and_missing_bank_cannot_become_a_partial_cohort():
    manifest, artifacts, _ = bundle()
    draws = json.loads(artifacts["draws.json"])
    draws[1]["role"] = "FINAL_HOLDOUT"
    _replace(manifest, artifacts, "draws.json", draws)
    with pytest.raises(cli.Refused, match="DRAW_ROLE_OR_POPULATION"):
        cli.evaluate(manifest, artifacts)
    manifest, artifacts, _ = bundle()
    manifest["banks"].pop()
    with pytest.raises(cli.Refused, match="COMPLETE_BANK_REQUIRED"):
        cli.evaluate(manifest, artifacts)


def test_changed_bytes_and_original_commitment_identity_are_refused():
    manifest, artifacts, _ = bundle()
    artifacts["pred-0.json"] += b" "
    with pytest.raises(cli.Refused, match="INPUT_SHA256_DIFFERS"):
        cli.evaluate(manifest, artifacts)
    manifest, artifacts, _ = bundle()
    rows = [json.loads(line) for line in artifacts["commits-0.jsonl"].splitlines()]
    rows[1]["commitment"]["model_id"] = "a-different-model"
    raw = b"".join(_bytes(r) for r in rows)
    artifacts["commits-0.jsonl"] = raw
    manifest["files"]["commits-0.jsonl"]["sha256"] = hashlib.sha256(raw).hexdigest()
    receipt = json.loads(artifacts["receipt-0.json"])
    receipt["commitments_sha256"] = hashlib.sha256(raw).hexdigest()
    _replace(manifest, artifacts, "receipt-0.json", receipt)
    with pytest.raises(cli.Refused, match="COMMITMENT_CONTEXT_DIFFERS"):
        cli.evaluate(manifest, artifacts)


def test_missing_predictions_withhold_the_member_without_replacing_it():
    manifest, artifacts, _ = bundle()
    prediction = json.loads(artifacts["pred-0.json"])
    prediction["rows"].pop()
    _replace(manifest, artifacts, "pred-0.json", prediction)
    receipt = json.loads(artifacts["receipt-0.json"])
    receipt["model_predictions_sha256"] = manifest["files"]["pred-0.json"]["sha256"]
    _replace(manifest, artifacts, "receipt-0.json", receipt)
    result = cli.evaluate(manifest, artifacts)
    assert result["members"]["legs"]["toy-model-0"]["status"] == "CANDIDATE_UNAVAILABLE"
    assert result["alignment"]["offered_members"] == [
        "toy-model-0",
        "toy-model-1",
        "toy-model-2",
    ]
    assert "toy-model-0" in result["alignment"]["conditional_tau_excluded"]


def _on_disk(tmp_path):
    manifest, artifacts, _ = bundle()
    root = tmp_path / "public"
    root.mkdir()
    for key, raw in artifacts.items():
        (root / manifest["files"][key]["path"]).write_bytes(raw)
    raw = _bytes(manifest)
    (root / "run.json").write_bytes(raw)
    args = [
        "--input-root",
        str(root),
        "--manifest",
        "run.json",
        "--manifest-sha256",
        hashlib.sha256(raw).hexdigest(),
        "--output-dir",
        str(tmp_path / "out"),
    ]
    return manifest, root, args


def test_cli_writes_reproducible_outputs_and_never_overwrites(tmp_path, capsys):
    _, _, args = _on_disk(tmp_path)
    assert cli.main(args) == 0
    capsys.readouterr()
    out = tmp_path / "out"
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert set(before) == {
        "cohort.json",
        "members.json",
        "alignment.json",
        "complete.json",
    }
    complete = json.loads(before["complete.json"])
    assert complete["status"] == "COMPLETED_DEVELOPMENT_DIAGNOSTIC"
    assert complete["qualification"] is False
    for name, digest in complete["files"].items():
        assert hashlib.sha256(before[name]).hexdigest() == digest
    assert cli.main(args) == 2
    assert "OUTPUT_ALREADY_EXISTS" in capsys.readouterr().out
    assert before == {p.name: p.read_bytes() for p in out.iterdir()}


@pytest.mark.parametrize(
    "defect", ["traversal", "symlink", "missing", "bad_manifest_sha"]
)
def test_file_refusals_publish_no_numerical_output(tmp_path, capsys, defect):
    manifest, root, args = _on_disk(tmp_path)
    if defect == "traversal":
        manifest["files"]["pred-0.json"]["path"] = "../outside.json"
    elif defect == "symlink":
        target = root / "pred-0.json"
        copy_path = root / "original-prediction.json"
        target.rename(copy_path)
        target.symlink_to(copy_path)
    elif defect == "missing":
        (root / "eval.jsonl").unlink()
    else:
        args[args.index("--manifest-sha256") + 1] = "0" * 64
    if defect == "traversal":
        raw = _bytes(manifest)
        (root / "run.json").write_bytes(raw)
        args[args.index("--manifest-sha256") + 1] = hashlib.sha256(raw).hexdigest()
    assert cli.main(args) == 2
    assert not (tmp_path / "out").exists()
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "REFUSED" and status["candidate_penalty"] is False
