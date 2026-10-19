"""Public f02/f08 pilot plans bind disjoint roles and retain judge inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.dev.reference_packages.calculix import f08_near_feasible
from scripts.dev.reference_packages.elmer import f02_cold_pilot

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/development/evidence/reference-solvers-2026-10-15"


def _load(relative):
    return json.loads((EVIDENCE / relative).read_text())


def test_f02_pilot_selects_exact_source_roles_and_retains_b5_vtu():
    plan = _load("plans/f02-cold-pilot-source.json")
    assert [s["name"] for s in plan["steps"]] == [
        "f02-cold-convergence",
        "f02-cold-train40",
        "f02-cold-step-responses",
    ]
    expected = [36, 40, 4]
    for step, count in zip(plan["steps"], expected):
        manifest = json.loads((ROOT / step["manifest"]).read_text())
        rows = [
            c
            for c in manifest["cases"]
            if c["reservation"] in step["select"]["reservations"]
        ]
        assert len(rows) == count
        assert step["families"]["f02"]["ceilings"]["launches"] == count
        assert "final*.vtu" in step["keep"]["patterns"]
        assert step["keep"]["max_file_bytes"] > 8_003_572
        assert "observe" not in step  # rejudge requires the prior matching baselines
    train = json.loads(f02_cold_pilot.readiness.TRAIN_MANIFEST.read_text())["cases"]
    cold = [row for row in train if row["context"] == f02_cold_pilot.TRAIN_CONTEXT]
    assert len(cold) == 40
    assert (
        not {(r["peak_w"], r["on_time_s"]) for r in cold} & f02_cold_pilot.EVAL_ACTIONS
    )


def test_f08_pilot_is_three_rungs_per_new_action_and_retains_native_sources():
    plan = _load("plans/f08-near-feasible-public-pilot.json")
    manifest = _load("pins/f08-near-feasible-h3-h225-h17-manifest.json")
    train = _load("pins/f08-train-256-h3-manifest.json")
    assert manifest["counts"] == {"pilot": 8, "pilot_witness": 16}
    assert len(manifest["cases"]) == 24
    assert len(train["cases"]) == 256
    assert not {c["action_digest"] for c in manifest["cases"]} & {
        c["action_digest"] for c in train["cases"]
    }
    for i in range(8):
        stem = f"pilot-{i:04d}"
        assert {c["case"] for c in manifest["cases"] if c["case"].startswith(stem)} == {
            stem,
            f"{stem}-h2.25",
            f"{stem}-h1.7",
        }
    step = plan["steps"][0]
    assert step["families"]["f08"]["ceilings"]["launches"] == 24
    assert {"case.dat", "mesh.inp", "deck.json", "case.inp"} <= set(
        step["keep"]["patterns"]
    )
    assert step["keep"]["max_file_bytes"] >= 21_144_994
    assert "f08_near_feasible.py" in step["observe"]["argv"][1]
    assert manifest["pilot"]["train_manifest_sha256"] == f08_near_feasible._sha(
        EVIDENCE / "pins/f08-train-256-h3-manifest.json"
    )


def test_f02_rejudge_refuses_unretained_final_vtu(tmp_path):
    work = tmp_path / "new/cases/f02/one-primary/work"
    work.mkdir(parents=True)
    deck_bytes = b'{"case": {}}\n'
    (work / "deck.json").write_bytes(deck_bytes)
    (work / "scalars.dat").write_text("solved\n")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case": "one-primary",
                        "reservation": "primary",
                        "files": {"deck.json": hashlib.sha256(deck_bytes).hexdigest()},
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError, match="final VTU was not retained"):
        f02_cold_pilot.rejudge(
            tmp_path / "new", tmp_path / "old", manifest, tmp_path / "judgement.json"
        )


def test_f02_rejudge_embeds_manifest_provenance(tmp_path, monkeypatch):
    work = tmp_path / "new/cases/f02/one-primary/work"
    work.mkdir(parents=True)
    deck_bytes = b'{"case": {}}\n'
    (work / "deck.json").write_bytes(deck_bytes)
    (work / "scalars.dat").write_text("solved\n")
    (work / "mesh").mkdir()
    (work / "mesh/final_t0001.vtu").write_text("retained\n")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case": "one-primary",
                        "reservation": "primary",
                        "files": {"deck.json": hashlib.sha256(deck_bytes).hexdigest()},
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(
        f02_cold_pilot.readiness,
        "judge",
        lambda *_args, **_kwargs: {
            "schema": "carbon.f02-readiness.judgement.v1",
            "family_acceptance": {"status": "NOT_ACCEPTED"},
        },
    )
    out = tmp_path / "judgement.json"
    result = f02_cold_pilot.rejudge(tmp_path / "new", tmp_path / "old", manifest, out)
    expected = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert result["provenance"]["manifest_sha256"] == expected
    assert json.loads(out.read_text())["provenance"]["manifest_sha256"] == expected
