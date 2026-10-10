"""Real export contracts, synthetic physics; no solves, models or cloud access."""

from __future__ import annotations

import json

import pytest
from test_portfolio_baselines import fixture as portfolio_fixture
from test_portfolio_baselines import thermal_payloads

from carbon.design_search import (
    diversity,
    indexed,
    power_accumulation,
    producer_panels,
    tasks,
)
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import evidence_pipeline as ep


def sha(n):
    return ep._sha(str(n).encode())


def export_questions(family, task, reference):
    cases = ["q1", "q2", "q3", "q4"]
    law = diversity.register_law(
        {
            "schema": diversity.LAW_SCHEMA_V2,
            "population_status": "UNREGISTERED",
            "kind": "grid",
            "draw_model": "iid_with_replacement",
            "batch_size": 1,
            "bins": [{"case": c, "q_mass": 0.25} for c in cases],
            "mass_l1_error_bound": 0,
        }
    )
    return producer_panels.seal_export(
        {
            "schema": producer_panels.EXPORT_SCHEMA,
            "sealed": True,
            "family": family,
            "challenge_id": "synthetic-challenge",
            "exposure_unit": "per_question_draws",
            "exposure": [{"case": c, "limit": 2, "used": 0} for c in cases],
            "window_sampling": power_accumulation.register_window_sampling(
                case_strata=[{"case": c, "stratum": "only"} for c in cases],
                quotas_by_k=[{"questions_per_batch": 1, "quotas": {"only": 1}}],
            ),
            "questions": [
                {
                    "case": c,
                    "support_case": "bank-" + str(i // 2),
                    "task": task,
                    "reference": reference,
                    "close_call": False,
                    "refinement_demand": False,
                }
                for i, c in enumerate(cases)
            ],
            "laws": [law],
        }
    )


def plain_task(actions, objective, limit):
    variables = [
        {
            "name": name,
            "type": "number",
            "min": min(a[name] for a in actions.values()),
            "max": max(a[name] for a in actions.values()),
            "step": min(
                (
                    b - a
                    for a, b in zip(
                        sorted({v[name] for v in actions.values()}),
                        sorted({v[name] for v in actions.values()})[1:],
                    )
                ),
                default=1,
            ),
        }
        for name in next(iter(actions.values()))
    ]
    return tasks.task(
        "synthetic-question",
        identity={
            "challenge": "synthetic-challenge",
            "contract_version": "fixture-v1",
            "action_grammar": {
                "schema": tasks.GRAMMAR_SCHEMA,
                "version": "fixture-v1",
                "variables": variables,
                "rules": [],
            },
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": len(actions),
            "seed": 0,
            "observer_version": "synthetic-observer-v1",
            "reference_bank": "synthetic-bank",
        },
        conditions=[{"id": "context", "stratum": "only"}],
        strata={"only": {"p": 1, "q": 1, "w": 1}},
        candidates=list(actions),
        actions=actions,
        objective=objective,
        limits=[limit],
    )


def bundle(family="f02", *, indexed_f02=False):
    if family == "f02":
        original, material = portfolio_fixture("f02", thermal_payloads())
        first = original["questions"][0]
        export = export_questions(family, first["task"], first["reference"])
        material = ep.pb.seal_materials(
            {
                **{k: v for k, v in material.items() if k != "materials_digest"},
                "export_digest": export["export_digest"],
            }
        )
        if indexed_f02:
            task = indexed.indexed_task(
                "burst-context-map",
                index_axis="context",
                indices=[
                    {"index_value": i, "buyer_weight": 0.5, "task": first["task"]}
                    for i in (0, 1)
                ],
                query_budget=10,
                value_equivalence={
                    "quantity": first["task"]["objective"]["quantity"],
                    "unit": first["task"]["objective"]["unit"],
                    "tolerance": 0,
                    "rule": indexed.EQUIVALENCE_RULE,
                },
            )
            export = export_questions(
                family,
                task,
                [{"index_value": i, "panel": first["reference"]} for i in (0, 1)],
            )
            material = {
                "schema": ep.INDEXED_F02,
                "scope": "SYNTHETIC_FIXTURE",
                "export_digest": export["export_digest"],
                "indices": [
                    {
                        "index_value": i,
                        "materials": ep.pb.seal_materials(
                            {
                                **{
                                    k: v
                                    for k, v in material.items()
                                    if k != "materials_digest"
                                },
                                "export_digest": ep.f02_view(export, i)[
                                    "export_digest"
                                ],
                            }
                        ),
                    }
                    for i in (0, 1)
                ],
            }
        method = "impulse-response"
    elif family == "battery-v3":
        actions = {
            f"p{i}-{j}": {"c1": a, "c2": b, "switch_v": 4, "cooling": 1}
            for i, a in enumerate((1, 1.5, 2))
            for j, b in enumerate((0.25, 0.375, 0.5))
        }
        band_tasks, refs = [], []
        for band in (5, 15, 25, 35, 40):
            task = plain_task(
                actions,
                {
                    "quantity": "minutes",
                    "unit": "min",
                    "sense": "min",
                    "aggregate": "worst",
                },
                {"quantity": "temperature", "unit": "degC", "op": "<=", "value": 45},
            )
            band_tasks.append({"index_value": band, "buyer_weight": 0.2, "task": task})
            refs.append(
                {
                    "index_value": band,
                    "panel": [
                        {
                            "candidate": c,
                            "condition": "context",
                            "values": {
                                "minutes": 30 - a["c1"] - a["c2"],
                                "temperature": band + a["c1"] + a["c2"],
                            },
                        }
                        for c, a in actions.items()
                    ],
                }
            )
        task = indexed.indexed_task(
            "battery-map",
            index_axis="ambient",
            indices=band_tasks,
            query_budget=45,
            value_equivalence={
                "quantity": "minutes",
                "unit": "min",
                "tolerance": 0,
                "rule": indexed.EQUIVALENCE_RULE,
            },
        )
        export, material, method = (
            export_questions(family, task, refs),
            None,
            "protocol",
        )
    else:
        actions = {
            f"m{i}": dict(zip(cb.MOTOR_FEATURES, (i + 1, 0.8, 0.5, 0.5, 0.2, 1, 0)))
            for i in range(5)
        }
        task = plain_task(
            actions,
            {
                "quantity": "mean_nm",
                "unit": "N.m",
                "sense": "max",
                "aggregate": "worst",
            },
            {"quantity": "cogging_nm", "unit": "N.m", "op": "<=", "value": 1},
        )
        curves = [
            {
                "candidate": c,
                "geometry_id": c,
                "coordinates": a,
                "loaded_nm": [6 + i, 7 + i, 8 + i],
                "cogging_nm": [-0.02, 0, 0.02],
            }
            for i, (c, a) in enumerate(actions.items())
        ]
        reference = [
            {
                "candidate": r["candidate"],
                "condition": "context",
                "values": cb.curve_observables(r["loaded_nm"], r["cogging_nm"]),
            }
            for r in curves
        ]
        export = export_questions(family, task, reference)
        material = {
            "export_digest": export["export_digest"],
            "sampling": "one-period-without-repeated-endpoint",
            "source_hashes": [sha(90)],
            "observer_version": "synthetic-observer-v1",
            "angle_deg": [0, 120, 240],
            "rows": curves,
        }
        method = "gaussian"
    raw = {
        "schema": ep.PREDICTIONS,
        "scope": "SYNTHETIC_FIXTURE",
        "export_digest": export["export_digest"],
        "model_id": "toy-carbon",
        "source_receipt_digest": sha(3),
        "rows": [
            {k: r[k] for k in ("band", "candidate", "condition", "values")}
            for r in cb._physical_rows(export)
        ],
    }
    baseline, env, _ = ep._baseline(export, material, method)
    carbon = ep._predictions(export, raw)
    jobs, bindings = [], []
    objective = None
    for entry in export["questions"]:
        truth = ep._assess(entry, {}, reference=True)
        first = next(iter(truth.values()))[0]
        weights = (
            {b: 0.2 for b in truth}
            if family == "battery-v3"
            else {b: 0.5 for b in truth} if indexed_f02 else None
        )
        objective = {
            "unit": first["objective"]["unit"],
            "direction": first["objective"]["sense"],
            **({"index_weights": weights} if family == "battery-v3" else {}),
        }
        ids = first["candidates"]
        choices = {c: {b: c for b in truth} for c in ids}
        ranks = {}
        for name, values, bounds in (
            ("model", carbon, None),
            ("baseline", baseline, env),
        ):
            assessed = ep._assess(entry, values, envelopes=bounds)
            # Fixture uses identical action ordering across the five bands.
            order = ep._order(*reversed(next(iter(assessed.values()))))
            ranks[name] = {c: i for i, c in enumerate(order)}
        candidates = [
            {
                "design_id": c,
                "reference": {
                    k: v
                    for k, v in ep._reference(truth, choices[c], weights).items()
                    if family == "battery-v3" or k != "per_index"
                },
                "solve_cost": {"wall_s": 2, "core_s": 4},
                "planning_bound": {"wall_s": 2, "core_s": 4},
                "screen_rank": {name: rank[c] for name, rank in ranks.items()},
            }
            for c in ids
        ]
        jobs.append(
            {
                "job_id": entry["case"],
                "cluster_id": entry["support_case"],
                "candidates": candidates,
                "solver_order": list(reversed(ids)),
                "screen_cost": {
                    name: {"wall_s": 0.1, "core_s": 0.1}
                    for name in ("model", "baseline")
                },
            }
        )
        bindings.append(
            {"job_id": entry["case"], "case": entry["case"], "candidates": choices}
        )
    replay = ep.eb.seal(
        {
            "schema": ep.eb.SCHEMA,
            "evidence_class": "DEVELOPMENT",
            "challenge": family,
            "source_digest": export["export_digest"],
            "decision_rule_id": "toy-v1",
            "objective": objective,
            "cost_basis": "ASSUMPTION",
            "execution_plan": "SERIAL_COMPLETE_PANELS",
            "budgets": [{"wall_s": 5, "core_s": 10}],
            "jobs": jobs,
            "registrations": {
                name: "toy-registration"
                for name in (
                    "solver_search",
                    "model_screen",
                    "baseline_screen",
                    "cost_plan",
                )
            },
        }
    )
    context = {
        "schema": ep.CONTEXT,
        "export_digest": export["export_digest"],
        "selection": {
            "carbon_model_id": "toy-carbon",
            "baseline_id": family,
            "selection_role": "TRAIN",
            "selection_receipt_digest": sha(4),
        },
        "folds": None,
        "speed": None,
        "item_1": None,
        "item_4": None,
    }
    documents = {
        "export": export,
        "comparator": material,
        "carbon": raw,
        "replay": replay,
        "bindings": {
            "schema": ep.BINDINGS,
            "export_digest": export["export_digest"],
            "jobs": bindings,
        },
        "context": context,
        "rule": None,
    }
    manifest = {
        "schema": ep.SCHEMA,
        "scope": "SYNTHETIC_FIXTURE",
        "family": family,
        "method": method,
        "files": {},
        "analysis": {"bootstrap_replicates": 100, "confidence": 0.95, "seed": 7},
    }
    return manifest, documents


def write_bundle(tmp_path, family="f02", *, indexed_f02=False):
    manifest, documents = bundle(family, indexed_f02=indexed_f02)
    for role, doc in documents.items():
        if doc is None:
            manifest["files"][role] = None
        else:
            raw = json.dumps(doc, allow_nan=False).encode()
            (tmp_path / f"{role}.json").write_bytes(raw)
            manifest["files"][role] = {"path": f"{role}.json", "sha256": ep._sha(raw)}
    path = tmp_path / "manifest.json"
    raw = json.dumps(manifest).encode()
    path.write_bytes(raw)
    return path, ep._sha(raw)


@pytest.mark.parametrize("family", ["f02", "motor", "battery-v3"])
def test_one_command_real_contract_end_to_end(tmp_path, family, capsys):
    path, digest = write_bundle(tmp_path, family)
    out = tmp_path / "result"
    assert (
        ep.main(
            [
                family,
                "--manifest",
                str(path),
                "--manifest-sha256",
                digest,
                "--output-dir",
                str(out),
            ]
        )
        == 0
    )
    receipt = json.loads((out / "receipt.json").read_text())
    assert receipt["reference_solves"] == 0 and receipt["qualifies_challenge"] is False
    assert receipt["value_status"] == "INSUFFICIENT_EVIDENCE"
    text = (out / "evidence.md").read_text()
    assert "SYNTHETIC FIXTURE" in text and "UNMEASURED" in text
    for name, pin in receipt["output_byte_pins"].items():
        assert ep._sha((out / name).read_bytes()) == pin
    assert "COMPLETED_DEVELOPMENT_ANALYSIS" in capsys.readouterr().out


def invoke(manifest, documents):
    return ep._stage(
        "pipeline",
        lambda: ep.run(manifest, documents, {"export": sha(1), "comparator": sha(2)}),
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ("truth", "REFERENCE_VALUE_MISMATCH"),
        ("rank", "SCREEN_ORDER_MISMATCH"),
        ("cluster", "CLUSTER_PROVENANCE_MISMATCH"),
        ("observer", "INVALID_OR_INCOMPLETE_INPUT"),
        ("carbon_pin", "SOURCE_IDENTITY_MISMATCH"),
        ("coverage", "INCOMPLETE_PREDICTION_INVENTORY"),
        ("context_pin", "SELECTION_IDENTITY_MISMATCH"),
        ("refinement", "REFINED_TRUTH_REQUIRED"),
    ],
)
def test_hop_mismatches_are_typed(change, reason):
    manifest, docs = bundle()
    if change == "truth":
        docs["replay"]["jobs"][0]["candidates"][0]["reference"]["value"] += 1
    elif change == "rank":
        rows = docs["replay"]["jobs"][0]["candidates"]
        rows[0]["screen_rank"]["baseline"], rows[1]["screen_rank"]["baseline"] = (
            rows[1]["screen_rank"]["baseline"],
            rows[0]["screen_rank"]["baseline"],
        )
    elif change == "cluster":
        docs["replay"]["jobs"][0]["cluster_id"] = "invented-independent-bank"
    elif change == "observer":
        docs["comparator"]["observer_versions"] = ["different-observer"]
    elif change == "carbon_pin":
        docs["carbon"]["export_digest"] = sha(123)
    elif change == "coverage":
        docs["carbon"]["rows"].pop()
    elif change == "context_pin":
        docs["context"]["export_digest"] = sha(123)
    elif change == "refinement":
        docs["export"]["questions"][0]["refinement_demand"] = True
        docs["export"] = producer_panels.seal_export(
            {k: v for k, v in docs["export"].items() if k != "export_digest"}
        )
    if change in ("truth", "rank", "cluster"):
        docs["replay"] = ep.eb.seal(
            {k: v for k, v in docs["replay"].items() if k != "panel_digest"}
        )
    with pytest.raises(ep.Refusal) as caught:
        invoke(manifest, docs)
    assert caught.value.code == reason


def test_byte_tampering_does_not_write_page_or_echo_payload(tmp_path, capsys):
    path, digest = write_bundle(tmp_path)
    (tmp_path / "carbon.json").write_text("SECRET INVALID PAYLOAD")
    out = tmp_path / "result"
    assert (
        ep.main(
            [
                "f02",
                "--manifest",
                str(path),
                "--manifest-sha256",
                digest,
                "--output-dir",
                str(out),
            ]
        )
        == 2
    )
    assert not out.exists()
    message = capsys.readouterr().out
    assert "BYTE_PIN_MISMATCH" in message and "SECRET" not in message


def test_existing_pack_is_not_overwritten(tmp_path):
    path, digest = write_bundle(tmp_path)
    out = tmp_path / "result"
    out.mkdir()
    (out / "evidence.md").write_text("retained")
    assert (
        ep.main(
            [
                "f02",
                "--manifest",
                str(path),
                "--manifest-sha256",
                digest,
                "--output-dir",
                str(out),
            ]
        )
        == 2
    )
    assert (out / "evidence.md").read_text() == "retained"


def test_battery_weights_and_partial_map_are_refused():
    manifest, docs = bundle("battery-v3")
    docs["bindings"]["jobs"][0]["candidates"]["p0-0"].pop("40")
    with pytest.raises(ep.Refusal, match="INCOMPLETE_INDEX_MAP"):
        invoke(manifest, docs)
    manifest, docs = bundle("battery-v3")
    docs["replay"]["objective"]["index_weights"] = {
        "5": 0.1,
        "15": 0.3,
        "25": 0.2,
        "35": 0.2,
        "40": 0.2,
    }
    docs["replay"] = ep.eb.seal(
        {k: v for k, v in docs["replay"].items() if k != "panel_digest"}
    )
    with pytest.raises(ep.Refusal, match="BUYER_WEIGHT_MISMATCH"):
        invoke(manifest, docs)


def test_missing_optimizer_route_is_a_named_gap():
    manifest, docs = bundle()
    manifest["family"] = "f13"
    with pytest.raises(ep.Refusal, match="FAMILY_ROUTE_NOT_IMPLEMENTED_BY_OPTIMIZER"):
        invoke(manifest, docs)


def test_fixture_cannot_be_relabelled_public():
    manifest, docs = bundle()
    manifest["scope"] = "PUBLIC_DEVELOPMENT"
    with pytest.raises(ep.Refusal, match="FIXTURE_SCOPE_MISMATCH"):
        invoke(manifest, docs)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}'])
def test_nonfinite_or_duplicate_json_is_refused(raw):
    with pytest.raises(ep.Refusal):
        ep._json(raw)


def test_indexed_f02_preserves_complete_buyer_job(tmp_path):
    path, digest = write_bundle(tmp_path, indexed_f02=True)
    out = tmp_path / "result"
    assert (
        ep.main(
            [
                "f02",
                "--manifest",
                str(path),
                "--manifest-sha256",
                digest,
                "--output-dir",
                str(out),
            ]
        )
        == 0
    )
    report = json.loads((out / "baseline.json").read_text())
    assert set(
        report["equal_budget_screening"]["candidate_rankings"][0]["per_index"]
    ) == {"0", "1"}
    assert set(report["costs"]["per_index"]) == {"0", "1"}
    manifest, docs = bundle(indexed_f02=True)
    docs["bindings"]["jobs"][0]["candidates"][
        next(iter(docs["bindings"]["jobs"][0]["candidates"]))
    ].pop("1")
    with pytest.raises(ep.Refusal, match="INCOMPLETE_INDEX_MAP"):
        invoke(manifest, docs)


def test_duplicate_abstention_cannot_hide_a_missing_prediction():
    manifest, docs = bundle()
    docs["carbon"]["rows"][0]["values"] = None
    docs["carbon"]["rows"][-1] = dict(docs["carbon"]["rows"][0])
    with pytest.raises(ep.Refusal, match="UNKNOWN_OR_DUPLICATE_PREDICTION"):
        invoke(manifest, docs)


def test_complete_negative_result_is_not_hidden():
    manifest, docs = bundle()
    docs["context"]["folds"] = {
        "schema": ep.vb.FOLDS_SCHEMA,
        "export_digest": docs["export"]["export_digest"],
        "folds": [
            {"fold_id": "A", "source_digest": sha(11), "questions": ["q1", "q2"]},
            {"fold_id": "B", "source_digest": sha(12), "questions": ["q3", "q4"]},
        ],
    }
    docs["rule"] = {
        "schema": ep.vb.RULE_SCHEMA,
        "rule_id": "synthetic-rule-only",
        "owner_record": "synthetic fixture, no live authority",
        "item_2": {"max_mean_regret_delta": 0.0},
        "item_3": None,
        "item_5": None,
    }
    outputs = invoke(manifest, docs)
    assert outputs["value-report.json"]["items"]["2"]["status"] == "FAIL"
    assert outputs["value-report.json"]["status"] == "FAIL"


def test_same_bank_cannot_masquerade_as_two_independent_folds():
    manifest, docs = bundle()
    docs["context"]["folds"] = {
        "schema": ep.vb.FOLDS_SCHEMA,
        "export_digest": docs["export"]["export_digest"],
        "folds": [
            {"fold_id": "A", "source_digest": sha(11), "questions": ["q1", "q3"]},
            {"fold_id": "B", "source_digest": sha(12), "questions": ["q2", "q4"]},
        ],
    }
    with pytest.raises(ep.Refusal, match="FOLDS_SHARE_REFERENCE_SUPPORT"):
        invoke(manifest, docs)


def test_unknown_speed_query_is_refused_even_without_owner_threshold():
    manifest, docs = bundle()
    docs["context"]["speed"] = {
        "schema": ep.vb.SPEED_SCHEMA,
        "export_digest": docs["export"]["export_digest"],
        "status": "MEASURED",
        "query_unit": "full_registered_decision_query",
        "route": "fixture-cpu",
        "pairs": [{"query": "invented", "reference_wall_s": 10, "carbon_wall_s": 1}],
    }
    with pytest.raises(ep.Refusal, match="UNKNOWN_OR_DUPLICATE_SPEED_QUESTION"):
        invoke(manifest, docs)


def test_indexed_material_scope_cannot_promote_a_fixture():
    manifest, docs = bundle(indexed_f02=True)
    docs["comparator"]["scope"] = "PUBLIC_DEVELOPMENT"
    with pytest.raises(ep.Refusal, match="FIXTURE_SCOPE_MISMATCH"):
        invoke(manifest, docs)


def test_public_evidence_cannot_replay_assumed_costs():
    manifest, docs = bundle()
    manifest["scope"] = docs["carbon"]["scope"] = "PUBLIC_DEVELOPMENT"
    docs["comparator"]["scope"] = "PUBLIC_DEVELOPMENT"
    docs["comparator"] = ep.pb.seal_materials(
        {k: v for k, v in docs["comparator"].items() if k != "materials_digest"}
    )
    with pytest.raises(ep.Refusal, match="MEASURED_COSTS_REQUIRED"):
        invoke(manifest, docs)


@pytest.mark.parametrize(
    "change,reason",
    [("escape", "LOCAL_RELATIVE_PATH_REQUIRED"), ("missing", "MISSING_CARBON")],
)
def test_loader_refuses_bad_paths_and_missing_roles(tmp_path, change, reason):
    path, _ = write_bundle(tmp_path)
    manifest = json.loads(path.read_text())
    if change == "escape":
        manifest["files"]["carbon"]["path"] = "../outside.json"
    else:
        manifest["files"]["carbon"] = None
    raw = json.dumps(manifest).encode()
    path.write_bytes(raw)
    with pytest.raises(ep.Refusal, match=reason):
        ep.load(path, ep._sha(raw))


def test_bootstrap_resource_bound_is_not_a_science_threshold():
    manifest, docs = bundle()
    manifest["analysis"]["bootstrap_replicates"] = 10001
    with pytest.raises(ep.Refusal, match="RESOURCE_LIMIT"):
        invoke(manifest, docs)


def test_indexed_f02_reference_is_not_a_flattened_single_context():
    _manifest, docs = bundle(indexed_f02=True)
    # Modify one context but leave the producer replay's old aggregate untouched.
    for row in docs["export"]["questions"][0]["reference"][1]["panel"]:
        row["values"]["metric"] += 0.01
    docs["export"] = producer_panels.seal_export(
        {k: v for k, v in docs["export"].items() if k != "export_digest"}
    )
    docs["bindings"]["export_digest"] = docs["export"]["export_digest"]
    docs["replay"]["source_digest"] = docs["export"]["export_digest"]
    docs["replay"] = ep.eb.seal(
        {k: v for k, v in docs["replay"].items() if k != "panel_digest"}
    )
    with pytest.raises(ep.Refusal, match="REFERENCE_VALUE_MISMATCH"):
        ep._verify_replay(
            docs["export"], docs["replay"], docs["bindings"], {}, {}, None
        )
