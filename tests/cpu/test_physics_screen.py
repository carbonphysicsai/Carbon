"""Public-only screening and provenance regressions; no solver or model training."""

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import physics_contract as pc
from scripts.dev.battery import physics_calibration as calibration
from scripts.dev.battery import physics_screen as screen

ROOT = Path(__file__).resolve().parents[2]


def contract():
    return pc.load(ROOT / "carbon/battery/physics_contract.v1.json")


def prediction(ambient=25, dip=0):
    return {
        "voltage_v": [3.6] * 121,
        "temperature_c": [ambient] + [ambient - dip] * 120,
        "plating_margin_v": 0.01,
        "capacity_ah": [5.0, 4.9, 4.8, 4.7],
    }


def fixture_panel():
    inputs = {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2}
    names = ["good1", "good2", "neutral", "control-bad"]
    return {
        "store": SimpleNamespace(
            refs={
                "public-fixture": {
                    "status": "OK",
                    "inputs": inputs,
                    "outputs": prediction(),
                }
            }
        ),
        "ids": ["public-fixture"],
        "names": names,
        "predictions": {
            m: {
                "public-fixture": prediction(
                    dip=2 if m in ("good1", "control-bad") else 0
                )
            }
            for m in names
        },
        "values": dict(zip(names, [0.1, 0.2, 0.9, 1.0])),
    }


@pytest.fixture
def simple_screen(monkeypatch):
    monkeypatch.setattr(screen, "_ocv", lambda: lambda soc: 3.6)
    monkeypatch.setattr(screen, "_taus", lambda panel, names: {"A": len(names) / 10})


def test_uncalibrated_pair_diagnostics_never_become_reference_tolerances(simple_screen):
    result = screen.screen(
        fixture_panel(),
        {"known_bad": ["control-bad"]},
        contract(),
        pair_residuals={"B5a": {"good1": [0], "good2": [0], "control-bad": [1]}},
    )
    law = result["laws"]["B5a"]
    assert law["calibration"].startswith("UNRESOLVED")
    assert law["reference_points"] == 0 and law["gate_state"] == "UNRESOLVED"
    assert law["screen"][0]["false_rejection"] == "0/2"
    assert law["screen"][0]["catch"] == "1/1"
    assert law["screen"][0]["reference_quantile"] is None
    assert result["registered_margin"] == "HUMAN_INPUT"
    text = screen.markdown(result)
    assert "UNRESOLVED" in text and "B5a" in text and "Tau before / after" in text


def test_reference_pair_residuals_and_role_coverage_are_reported(simple_screen):
    result = screen.screen(
        fixture_panel(),
        {"known_bad": ["control-bad"], "adversarial": ["absent"]},
        contract(),
        pair_residuals={
            "B5a": {"good1": [0, 0], "good2": [0, 0], "control-bad": [1, 1]}
        },
        reference_pairs={"B5a": {"residuals": [0.2, 0.4], "unresolved": 0}},
        provenance={"fixture": True},
    )
    law = result["laws"]["B5a"]
    row = next(
        r
        for r in law["screen"]
        if r["reference_quantile"] == 1 and r["max_violation_rate"] == 0
    )
    assert row["tolerance"] == 0.4 and row["reference_violation_rate"] == 0
    assert law["member_residuals"]["control-bad"] == {
        "p50": 1,
        "p99": 1,
        "max": 1,
        "points": 2,
        "missing_pairs": 0,
    }
    assert law["member_residuals"]["neutral"]["missing_pairs"] == 2
    assert row["catch_by_role"]["adversarial"] == {
        "caught": 0,
        "resolved": 0,
        "unresolved": 1,
    }
    assert law["gate_state"] == "UNRESOLVED"


def test_b9_diagnosis_is_paired_raw_data_not_a_tolerance_artefact(simple_screen):
    result = screen.screen(fixture_panel(), {"known_bad": ["control-bad"]}, contract())
    diagnosis = result["b9_diagnosis"]
    assert diagnosis["good_members_with_excess_subambient_predictions"] == 1
    assert diagnosis["member_case_comparisons"] == 2
    assert diagnosis["predicted_deficit_c"]["max"] == 2
    assert diagnosis["reference_deficit_c"]["max"] == 0
    assert diagnosis["excess_over_reference_c"]["max"] == 2
    assert diagnosis["descriptive_tail_counts"]["0.1"]["good_members_above"] == 1


def test_missing_member_predictions_never_count_as_gate_passes(simple_screen):
    panel = fixture_panel()
    panel["predictions"]["good2"] = {}
    result = screen.screen(panel, {"known_bad": ["control-bad"]}, contract())
    assert result["laws"]["B2"]["unresolved_members"] == ["good2"]
    assert result["laws"]["B2"]["screen"][0]["false_rejection"] == "0/1"


def write_panel(tmp_path):
    inputs = {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2}
    records = {}
    for cid, p in [("base", inputs), ("partner", {**inputs, "c1": 1.075})]:
        body = json.dumps(
            {"case_id": cid, "status": "OK", "inputs": p, "outputs": prediction()}
        ).encode()
        name = cid + ".json"
        (tmp_path / name).write_bytes(body)
        records[name] = hashlib.sha256(body).hexdigest()
    plan_body = json.dumps(
        {
            "pairs": [
                {
                    "law_id": "B5a",
                    "along": "c1",
                    "base_id": "base",
                    "partner_id": "partner",
                }
            ]
        }
    ).encode()
    (tmp_path / "plan.json").write_bytes(plan_body)
    manifest = {
        "visibility": "PUBLIC",
        "image_digest": calibration.IMAGE,
        "overlay_lock_sha256": hashlib.sha256(
            (ROOT / calibration.OVERLAY).read_bytes()
        ).hexdigest(),
        "plan_sha256": hashlib.sha256(plan_body).hexdigest(),
        "records": records,
    }
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest))
    return manifest


def test_manifest_hashes_image_overlay_plan_and_every_record(tmp_path):
    write_panel(tmp_path)
    readings, provenance = calibration.load_directory(
        tmp_path, contract(), repository=ROOT
    )
    assert readings["B5a"] == {"residuals": [0.0], "unresolved": 0}
    assert not readings["B10"]["residuals"]
    assert provenance["records"] == 2 and provenance["pairs"] == 1
    (tmp_path / "partner.json").write_text("{}")
    with pytest.raises(calibration.CalibrationRefused, match="record_hash"):
        calibration.load_directory(tmp_path, contract(), repository=ROOT)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("image_digest", "sha256:other", "reference_image"),
        ("overlay_lock_sha256", "wrong", "overlay_hash"),
        ("plan_sha256", "wrong", "plan_hash"),
        ("visibility", "SEALED", "not_public"),
    ],
)
def test_manifest_mismatch_is_refused_before_using_references(
    tmp_path, field, value, reason
):
    manifest = write_panel(tmp_path)
    manifest[field] = value
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(calibration.CalibrationRefused, match=reason):
        calibration.load_directory(tmp_path, contract(), repository=ROOT)


def test_outside_range_and_reference_failures_are_unresolved():
    base = {"status": "REFERENCE_SOLVER_FAILED"}
    readings = calibration.readings(
        {"pairs": [{"law_id": "B5a", "base": base, "partner": base}]}, contract()
    )
    assert readings["B5a"] == {"residuals": [], "unresolved": 1}


def test_pair_geometry_cannot_calibrate_a_different_law_step():
    base = {
        "status": "OK",
        "inputs": {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2},
        "outputs": prediction(),
    }
    partner = copy.deepcopy(base)
    partner["inputs"]["c1"] += 0.15
    with pytest.raises(calibration.CalibrationRefused, match="pair_step"):
        calibration.readings(
            {
                "pairs": [
                    {"law_id": "B5a", "along": "c1", "base": base, "partner": partner}
                ]
            },
            contract(),
        )


def test_data_collection_jsonl_plan_and_per_record_hashes(tmp_path):
    manifest = write_panel(tmp_path)
    records = [
        json.loads((tmp_path / name).read_bytes())
        for name in ("base.json", "partner.json")
    ]
    lines = [json.dumps(r, sort_keys=True).encode() for r in records]
    (tmp_path / "records.jsonl").write_bytes(b"\n".join(lines) + b"\n")
    manifest["record_sha256"] = {
        r["case_id"]: hashlib.sha256(line).hexdigest()
        for r, line in zip(records, lines)
    }
    del manifest["records"]
    jobs = [{"case_id": r["case_id"], **r["inputs"]} for r in records]
    jobs_body = json.dumps({"jobs": jobs}).encode()
    (tmp_path / "jobs.json").write_bytes(jobs_body)
    plan = {
        "schema": "carbon.battery.physics-calibration-plan.v1",
        "scope": "PUBLIC_DEVELOPMENT synthetic",
        "contract": {"probe_region": contract()["probe_region"]},
        "jobs_sha256": hashlib.sha256(jobs_body).hexdigest(),
        "pairs": [
            {
                "base": "base",
                "partner": "partner",
                "input": "c1",
                "step": 0.075,
                "step_fraction": 0.05,
                "laws": ["B5a", "B6"],
            }
        ],
    }
    plan_body = json.dumps(plan).encode()
    (tmp_path / "plan.json").write_bytes(plan_body)
    manifest["plan_sha256"] = hashlib.sha256(plan_body).hexdigest()
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest))
    readings, provenance = calibration.load_directory(
        tmp_path, contract(), repository=ROOT
    )
    assert readings["B5a"]["residuals"] == [0] and readings["B6"]["residuals"] == [0]
    assert provenance["pairs"] == 2
    plan_loaded, public_jobs, identity = calibration.public_plan(tmp_path, contract())
    assert (
        plan_loaded == plan
        and public_jobs == jobs
        and identity == manifest["plan_sha256"]
    )


def write_data_collection_panel(directory):
    """One public synthetic base in the actual nested manifest format."""
    c = contract()
    source = copy.deepcopy(c)
    source["laws"] = [
        law for law in source["laws"] if law["type"] != "prefix_invariance"
    ]
    source_body = json.dumps(source).encode()
    (directory / "contract.v1.json").write_bytes(source_body)
    inputs = {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2}
    moves = [
        ("c1", 0.05, ["B5a", "B6"]),
        ("c2", 0.05, ["B5b"]),
        ("t_amb_c", 0.05, ["B7", "B8"]),
    ] + [(axis, 0.01, ["B10"]) for axis in inputs]
    jobs = [{"case_id": "base", **inputs}]
    pairs = []
    for axis, fraction, lids in moves:
        cid = f"{axis}-{fraction}"
        lo, hi = c["probe_region"][axis]
        jobs.append(
            {"case_id": cid, **inputs, axis: inputs[axis] + fraction * (hi - lo)}
        )
        pairs.append(
            {
                "base": "base",
                "partner": cid,
                "input": axis,
                "step_fraction": fraction,
                "laws": lids,
            }
        )
    solver_image = (
        "ghcr.io/carbonphysicsai/carbon-determinism-study@" + calibration.IMAGE
    )
    overlay = (
        "sha256:"
        + hashlib.sha256((ROOT / calibration.OVERLAY).read_bytes()).hexdigest()
    )
    records = [
        {
            "case_id": j["case_id"],
            "status": "OK",
            "inputs": {k: j[k] for k in inputs},
            "outputs": prediction(),
            "solver_provenance": {
                "schema": "carbon.battery.solver-provenance.v1",
                "solver_image": solver_image,
                "overlay_lock": calibration.OVERLAY,
                "overlay_lock_sha256": overlay,
                "pybamm": "26.8.0.0",
            },
        }
        for j in jobs
    ]
    jobs_body = json.dumps({"jobs": jobs}).encode()
    plan = {
        "schema": "carbon.battery.physics-calibration-plan.v1",
        "scope": "PUBLIC_DEVELOPMENT fixture",
        "contract": {k: source[k] for k in ("challenge", "version", "probe_region")},
        "jobs_sha256": hashlib.sha256(jobs_body).hexdigest(),
        "jobs": len(jobs),
        "bases": 1,
        "pairs": pairs,
    }
    plan["contract"]["sha256"] = hashlib.sha256(source_body).hexdigest()
    plan_body = json.dumps(plan).encode()
    lines = [json.dumps(r, sort_keys=True).encode() for r in records]
    records_body = b"\n".join(lines) + b"\n"
    files = {
        "plan.json": plan_body,
        "jobs.json": jobs_body,
        "records.jsonl": records_body,
        "physcal_plan.py": b"# public deterministic fixture\n",
        "solve-command.json": b"[]",
    }
    for name, body in files.items():
        (directory / name).write_bytes(body)
    manifest = {
        "schema": "carbon.battery.physics-calibration-manifest.v1",
        "scope": "PUBLIC_DEVELOPMENT fixture",
        "counts": {"OK": len(records)},
        "missing": [],
        "records": {
            r["case_id"]: hashlib.sha256(line).hexdigest()
            for r, line in zip(records, lines)
        },
        "records_file_sha256": hashlib.sha256(records_body).hexdigest(),
        "plan": {
            "contract_sha256": plan["contract"]["sha256"],
            "contract_source": "public fixture",
            "plan_sha256": hashlib.sha256(plan_body).hexdigest(),
            "jobs_sha256": plan["jobs_sha256"],
            "generator_sha256": hashlib.sha256(files["physcal_plan.py"]).hexdigest(),
            "jobs": len(jobs),
            "pairs": len(pairs),
        },
        "solver": {
            "image": solver_image,
            "overlay_lock": calibration.OVERLAY,
            "overlay_lock_sha256": overlay,
            "solve_command_sha256": hashlib.sha256(
                files["solve-command.json"]
            ).hexdigest(),
            "overlay_verified": {
                "base_image": solver_image,
                "lock_sha256": overlay.removeprefix("sha256:"),
                "network": "none",
                "versions": {"pybamm": "26.8.0.0"},
            },
        },
    }
    (directory / "MANIFEST.json").write_text(json.dumps(manifest))
    return manifest, records


def test_complete_published_manifest_and_prospective_prefix_projection(tmp_path):
    manifest, _records = write_data_collection_panel(tmp_path)
    rows, provenance = calibration.load_directory(tmp_path, contract(), repository=ROOT)
    assert rows["B15"] == rows["B16"] == {"residuals": [0, 0], "unresolved": 0}
    assert len(rows["B10"]["residuals"]) == 4
    assert provenance["records"] == 8 and provenance["physical_pairs"] == 7
    assert (
        provenance["manifest_sha256"]
        == hashlib.sha256((tmp_path / "MANIFEST.json").read_bytes()).hexdigest()
    )
    assert provenance["acceptance_link"]["image_digest"] == calibration.IMAGE
    assert provenance["derived_prefix_laws"] == ["B15", "B16"]
    assert provenance["source_contract_sha256"] == manifest["plan"]["contract_sha256"]


@pytest.mark.parametrize(
    "path,value,reason",
    [
        (("solver", "image"), "sha256:wrong", "solver_binding"),
        (("solver", "overlay_lock_sha256"), "sha256:wrong", "solver_binding"),
        (("plan", "plan_sha256"), "wrong", "plan_hash"),
        (("plan", "jobs_sha256"), "wrong", "jobs_hash"),
        (("plan", "contract_sha256"), "wrong", "contract_hash"),
        (("records_file_sha256",), "wrong", "records_file_hash"),
        (("records", "base"), "wrong", "record_hash"),
        (("counts",), {"OK": 7}, "incomplete"),
        (("missing",), ["base"], "incomplete"),
        (("scope",), "SEALED", "not_public"),
    ],
)
def test_published_manifest_mutations_fail_closed(tmp_path, path, value, reason):
    manifest, _ = write_data_collection_panel(tmp_path)
    target = manifest
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(calibration.CalibrationRefused, match=reason):
        calibration.load_directory(tmp_path, contract(), repository=ROOT)


def test_rehashed_record_with_wrong_solver_provenance_is_refused(tmp_path):
    manifest, records = write_data_collection_panel(tmp_path)
    records[0]["solver_provenance"]["solver_image"] = "sha256:wrong"
    lines = [json.dumps(r, sort_keys=True).encode() for r in records]
    body = b"\n".join(lines) + b"\n"
    (tmp_path / "records.jsonl").write_bytes(body)
    manifest["records_file_sha256"] = hashlib.sha256(body).hexdigest()
    manifest["records"]["base"] = hashlib.sha256(lines[0]).hexdigest()
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(calibration.CalibrationRefused, match="record_provenance"):
        calibration.load_directory(tmp_path, contract(), repository=ROOT)


def test_changed_law_cannot_borrow_historical_calibration(tmp_path):
    write_data_collection_panel(tmp_path)
    changed = contract()
    next(law for law in changed["laws"] if law["id"] == "B5a")[
        "direction"
    ] = "decreasing"
    with pytest.raises(calibration.CalibrationRefused, match="contract_law"):
        calibration.load_directory(tmp_path, changed, repository=ROOT)


def test_partial_calibrated_member_is_unresolved(simple_screen):
    result = screen.screen(
        fixture_panel(),
        {"known_bad": ["control-bad"]},
        contract(),
        pair_residuals={"B15": {"good1": [0], "good2": [0, 0]}},
        reference_pairs={"B15": {"residuals": [0, 0], "unresolved": 0}},
    )
    assert "good1" in result["laws"]["B15"]["unresolved_members"]
    assert result["laws"]["B15"]["screen"][0]["false_rejection"] == "0/1"


def test_cache_requires_exact_checker_contract_plan_manifest_and_members():
    identity = {
        "contract_digest": "fixture-contract",
        "checker_sha256": "fixture-checker",
        "plan_sha256": "fixture-plan",
        "manifest_sha256": "fixture-manifest",
        "public_members": ["m"],
    }
    rows = {
        law["id"]: {"m": [0.0]} for law in contract()["laws"] if law["type"] in pc.PAIR
    }
    cache = {**identity, "readings": rows, "complete": True}
    assert screen.cached_readings(cache, identity, contract()) == rows
    for key in identity:
        broken = {**cache, key: None}
        with pytest.raises(pc.ContractRefused, match="cache_identity"):
            screen.cached_readings(broken, identity, contract())
    del cache["readings"]["B15"]
    with pytest.raises(pc.ContractRefused, match="cache_shape"):
        screen.cached_readings(cache, identity, contract())


def test_partial_checkpoint_can_resume_but_cannot_screen():
    identity = {"public_members": ["m", "n"], "checker_sha256": "fixture"}
    rows = {
        law["id"]: {"m": [0]} for law in contract()["laws"] if law["type"] in pc.PAIR
    }
    cached = {**identity, "complete": False, "readings": rows}
    assert (
        screen.cached_readings(cached, identity, contract(), allow_incomplete=True)
        == rows
    )
    with pytest.raises(pc.ContractRefused, match="cache_incomplete"):
        screen.cached_readings(cached, identity, contract())
    cached["complete"] = True
    with pytest.raises(pc.ContractRefused, match="cache_incomplete"):
        screen.cached_readings(cached, identity, contract())


def test_memory_bounded_public_names_match_decided_bundles_and_controls(tmp_path):
    import gzip

    for i, name in enumerate(["m", "n", "undecided"]):
        with gzip.open(tmp_path / f"{i}.json.gz", "wt") as handle:
            json.dump(
                {"member": name, "predictions": {"public-fixture": prediction()}},
                handle,
            )
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps({"decisions": {"m": {}, "n": {}, "control-oracle": {}}})
    )
    assert screen.public_member_names([tmp_path], results) == [
        "control-oracle",
        "m",
        "n",
    ]


def test_later_screen_controls_cannot_silently_expand_frozen_study():
    panel = fixture_panel()
    original = list(panel["names"])
    panel["names"].append("control-always_abstain")
    frozen = screen.frozen_public_panel(panel, original)
    assert frozen["names"] == sorted(original)
    assert "control-always_abstain" in panel["names"]
    with pytest.raises(pc.ContractRefused, match="members_missing"):
        screen.frozen_public_panel(panel, ["missing-member"])


def test_pair_builder_resumes_completed_members_and_emits_checkpoint(
    tmp_path, monkeypatch
):
    from carbon.battery import worker
    from carbon.battery.value import experiment
    from carbon.battery.value import panel as members

    write_data_collection_panel(tmp_path)
    c = contract()
    rows, _provenance, references = calibration.load_directory(
        tmp_path, c, repository=ROOT, include_records=True
    )
    initial = {lid: {"a": row["residuals"]} for lid, row in rows.items()}
    calls, checkpoints, clears = [], [], []
    monkeypatch.setattr(worker, "DirectBackend", lambda root: object())
    monkeypatch.setattr(
        members,
        "members",
        lambda name: [("a", "fixture", None, 0), ("b", "fixture", None, 1)],
    )

    def bundle(backend, member, strategy, seed, inputs):
        calls.append(member)
        return {
            "predictions": {
                cid: prediction(point["t_amb_c"]) for cid, point in inputs.items()
            }
        }, b"fixture"

    monkeypatch.setattr(experiment, "member_bundle", bundle)
    monkeypatch.setitem(
        screen.sys.modules,
        "jax",
        SimpleNamespace(clear_caches=lambda: clears.append(True)),
    )
    result = screen._pair_readings(
        ["a", "b"],
        c,
        1,
        "fixture",
        tmp_path,
        references,
        initial=initial,
        checkpoint=lambda member, rows: checkpoints.append((member, rows)),
    )
    assert calls == ["b"] and len(clears) == 1
    assert len(checkpoints) == 1 and checkpoints[0][0] == "b"
    assert all(set(row) == {"a", "b"} for row in result.values())
    assert all(row["a"] == initial[lid]["a"] for lid, row in result.items())
