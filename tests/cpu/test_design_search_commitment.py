"""Design-search requests, commitment before reference access, and the
separate-experiment comparison harness. Synthetic analytic model and reference:
no solver, no EV4 material."""

from __future__ import annotations

import json

import pytest

from carbon.battery.value import contract as ev
from carbon.battery.value import decision as d
from carbon.battery.value import search_commitment as sc
from carbon.battery.value.ev4_protected_conditions import (
    EV4_OPTIMIZER_VERIFICATION,
    EV4_VERIFICATION,
)

CONTRACT, _ = ev.load(ev.CONTRACTS / "ev2-charge-protocol-selection.v1.json")
DEV = [list(c) for s in CONTRACT["scenarios"]["development"] for c in s["conditions"]][
    2:6
]
SMALL = [(c1, c2) for c1 in (0.5, 1.0, 1.5, 2.0) for c2 in (0.2, 0.6, 1.0)]


def outputs(c1, c2, t_amb, soc0, plating_shift=0.0):
    """A synthetic cell: faster charge reaches CV sooner, plates and heats more."""
    onset = 120.0 + 2400.0 * (1.0 - soc0) / (c1 + 0.5 * c2)
    voltage = [3.5 + 0.69 * min(1.1, (i * 30.0) / onset) for i in range(121)]
    return {
        "voltage_v": voltage,
        "temperature_c": [t_amb + 8.0 * c1 * min(1.0, i / 60) for i in range(121)],
        "plating_margin_v": 0.03 - 0.02 * c1 + 0.0005 * (t_amb - 20) + plating_shift,
    }


def infer(inputs):
    return {
        k: outputs(v["c1"], v["c2"], v["t_amb_c"], v["soc0"]) for k, v in inputs.items()
    }


def reference(jobs):
    # The reference plates slightly more than the model believes.
    return {
        j["case_id"]: {
            "status": "OK",
            "outputs": outputs(j["c1"], j["c2"], j["t_amb_c"], j["soc0"], -0.004),
        }
        for j in jobs
    }


def base(mode="PB-INV", budget=None, conditions=DEV, designs=SMALL):
    return {
        "model": {
            "member": "synthetic-s0",
            "recipe_digest": "sha256:" + "1" * 64,
            "seed": 0,
        },
        "mode": mode,
        "conditions": conditions,
        "query_budget": budget or len(designs) * len(conditions),
        "verification_budget": 3,
        "optimizer": {
            "name": "fixed_grid",
            "code_digest": "sha256:" + "2" * 64,
            "configuration_digest": "sha256:" + "3" * 64,
        },
        "seed_policy": "deterministic; no randomness",
        "designs": designs,
    }


def run(tmp_path, mode="PB-INV"):
    req, space = sc.request(contract=CONTRACT, **base(mode))
    oracle = sc.Oracle(CONTRACT, infer, req, space)
    selections = sc.fixed_grid(CONTRACT, oracle, req, space)
    return req, oracle, selections, sc.commit(req, selections, oracle, tmp_path)


def test_request_is_versioned_and_binds_every_identity():
    req, space = sc.request(contract=CONTRACT, **base())
    assert req["schema"] == sc.REQUEST_SCHEMA and "not EV4" in req["experiment"]
    assert req["contract_digest"] == ev.digest(CONTRACT)
    assert req["candidate_space"]["designs"] == len(space) == len(SMALL)
    assert req["request_digest"].startswith("sha256:")
    assert len(sc.GRID) == 31 * 33


@pytest.mark.parametrize(
    "condition",
    [EV4_VERIFICATION[0], EV4_OPTIMIZER_VERIFICATION[7], (24.0, 0.33)],
)
def test_ev4_material_is_refused(condition):
    with pytest.raises(sc.SearchError, match="protected_material_requested"):
        sc.request(contract=CONTRACT, **base(conditions=[list(condition)]))


@pytest.mark.parametrize(
    "changes, code",
    [
        ({"conditions": [[41.0, 0.2]]}, "outside_envelope"),
        ({"designs": [(2.5, 0.2)]}, "generator_bounds"),
        ({"mode": "PB-XYZ"}, "unknown_mode"),
        ({"query_budget": 0}, "budget"),
        (
            {
                "optimizer": {
                    "name": "x",
                    "code_digest": "HUMAN_INPUT",
                    "configuration_digest": "sha256:",
                }
            },
            "unpinned",
        ),
    ],
)
def test_malformed_requests_are_refused(changes, code):
    with pytest.raises(sc.SearchError, match=code):
        sc.request(contract=CONTRACT, **{**base(), **changes})


def test_confirmation_material_class_is_refused():
    with pytest.raises(sc.SearchError, match="development_material_only"):
        sc.request(contract=CONTRACT, material="CONFIRMATION", **base())


def test_oracle_enforces_budget_and_declared_points():
    req, space = sc.request(contract=CONTRACT, **base(budget=2))
    oracle = sc.Oracle(CONTRACT, infer, req, space)
    t, s = DEV[0]
    oracle.query([(0.5, 0.2, t, s)])
    with pytest.raises(sc.SearchError, match="undeclared_condition"):
        oracle.query([(0.5, 0.2, 25.0, 0.3)])
    with pytest.raises(sc.SearchError, match="undeclared_design"):
        oracle.query([(0.55, 0.2, t, s)])
    with pytest.raises(sc.SearchError, match="query_budget_exhausted"):
        oracle.query([(0.5, 0.2, t, s), (1.0, 0.2, t, s)])
    assert oracle.used == 1 and len(oracle.log) == 1


def test_commitment_precedes_reference_access(tmp_path):
    req, oracle, selections, commitment = run(tmp_path)
    assert commitment.path.exists()
    on_disk = json.loads(commitment.path.read_text())
    assert on_disk["queries_used"] == len(SMALL) * len(DEV)
    seen = []

    def watching(jobs):
        # The commitment exists before the reference sees a single job.
        assert json.loads(commitment.path.read_text()) == on_disk
        seen.extend(jobs)
        return reference(jobs)

    result = sc.verify(CONTRACT, commitment, watching)
    assert len(seen) == len(DEV) * len(selections)
    assert result["commitment_digest"] == on_disk["commitment_digest"]
    with pytest.raises(FileExistsError):
        sc.commit(req, selections, oracle, tmp_path)


def test_a_raw_commitment_document_is_refused(tmp_path):
    _req, _oracle, _sel, commitment = run(tmp_path)
    with pytest.raises(sc.SearchError, match="commitment_only_from_commit"):
        sc.verify(CONTRACT, commitment.document, reference)
    with pytest.raises(sc.SearchError, match="commitment_only_from_commit"):
        sc.Commitment(object(), commitment.path, commitment.document)


def test_editing_a_commitment_after_commit_is_refused(tmp_path):
    _req, _oracle, _sel, commitment = run(tmp_path)
    document = json.loads(commitment.path.read_text())
    document["selections"] = [
        {"c1": 0.5, "c2": 0.2, "predicted_worst_time_to_cv_s": 1.0}
    ]
    commitment.path.write_text(json.dumps(document))
    with pytest.raises(sc.SearchError, match="changed_after_commit"):
        sc.verify(CONTRACT, commitment, reference)


def test_unresolved_and_unavailable_references_stay_unresolved(tmp_path):
    _req, _oracle, selections, commitment = run(tmp_path, mode="PB-ADV")
    jobs = sc._jobs(commitment.document)
    bands = CONTRACT["reference"]["uncertainty"]["bands"]

    def mixed(jobs):
        records = {}
        for index, j in enumerate(jobs):
            if index == 0:
                records[j["case_id"]] = {"status": "REFERENCE_TIMEOUT"}
                continue
            out = outputs(j["c1"], j["c2"], j["t_amb_c"], j["soc0"])
            if index == 1:  # inside the plating band: UNRESOLVED, never pass/fail
                out["plating_margin_v"] = bands["plating_margin_v"] / 2
            records[j["case_id"]] = {"status": "OK", "outputs": out}
        return records

    result = sc.verify(CONTRACT, commitment, mixed)
    verdicts = [r["verdict"] for r in result["rows"]]
    assert verdicts[0] == d.UNAVAILABLE and verdicts[1] == d.UNRESOLVED
    assert len(jobs) == len(selections) <= 3
    assert result["claims"]["unresolved_counted_as_safe_or_unsafe"] is False


def test_abstention_is_committed_and_verifies_nothing(tmp_path):
    hot = [[37.0, 0.08]]

    def unsafe(inputs):
        return {
            k: outputs(v["c1"], v["c2"], v["t_amb_c"], v["soc0"], plating_shift=-1.0)
            for k, v in inputs.items()
        }

    req, space = sc.request(contract=CONTRACT, **base(conditions=hot))
    oracle = sc.Oracle(CONTRACT, unsafe, req, space)
    selections = sc.fixed_grid(CONTRACT, oracle, req, space)
    commitment = sc.commit(req, selections, oracle, tmp_path)
    result = sc.verify(CONTRACT, commitment, reference)
    assert result["status"] == "ABSTAIN" and result["reference_jobs"] == 0


def test_comparison_runs_methods_at_equal_budgets_and_needs_the_baseline(tmp_path):
    def first_feasible(contract, oracle, req, space):
        # A cheaper proposed search: one condition first, then confirm.
        conditions = [tuple(c) for c in req["conditions"]]
        for c1, c2 in space:
            qs = oracle.query([(c1, c2, *conditions[0])])
            if sc._passes(contract, qs[0]):
                rest = oracle.query([(c1, c2, t, s) for t, s in conditions[1:]])
                if all(sc._passes(contract, q) for q in rest):
                    worst = max(q["time_to_cv_onset_s"] for q in [*qs, *rest])
                    return [{"c1": c1, "c2": c2, "predicted_worst_time_to_cv_s": worst}]
        return []

    with pytest.raises(sc.SearchError, match="baseline_required"):
        sc.compare(
            CONTRACT,
            infer,
            reference,
            {"proposed": first_feasible},
            base=base(),
            directory=tmp_path,
        )
    report = sc.compare(
        CONTRACT,
        infer,
        reference,
        {"fixed_grid": sc.fixed_grid, "proposed": first_feasible},
        base=base(),
        directory=tmp_path,
    )
    rows = report["methods"]
    assert rows["fixed_grid"]["query_budget"] == rows["proposed"]["query_budget"]
    assert rows["proposed"]["queries_used"] <= rows["fixed_grid"]["queries_used"]
    assert all(r["search_seconds"] >= 0 for r in rows.values())
    assert "separate" in report["separate_experiments"]


def test_fixed_grid_reproduces_the_ev4_optimizer_when_present():
    optimizer = pytest.importorskip("carbon.battery.value.optimizer")
    # Conformance on synthetic predictions over EV4's model grid; only the
    # rule is compared, no EV4 material reaches a request.
    grid = {
        "quantities": {
            q: [[None] * len(optimizer.MODEL_CONDITIONS) for _ in optimizer.DESIGNS]
            for q in optimizer.QUANTITIES
        }
    }
    table = {}
    for di, (c1, c2) in enumerate(optimizer.DESIGNS):
        for ci, (t, s) in enumerate(optimizer.MODEL_CONDITIONS):
            q = d.measure(CONTRACT, outputs(c1, c2, t, s))
            table[(c1, c2, t, s)] = q
            for name in optimizer.QUANTITIES:
                grid["quantities"][name][di][ci] = q[name]
    expected = optimizer.mode_d(CONTRACT, grid)
    conditions = [optimizer.MODEL_CONDITIONS[ci] for ci in optimizer.MODE_D_CONDITIONS]

    class Table:
        used = 0

        def query(self, points):
            return [table[tuple(p)] for p in points]

    req = {"mode": "PB-INV", "conditions": conditions, "verification_budget": 50}
    got = sc.fixed_grid(CONTRACT, Table(), req, list(sc.GRID))
    if expected["status"] == "ABSTAIN":
        assert got == []
    else:
        assert (got[0]["c1"], got[0]["c2"]) == (expected["c1"], expected["c2"])
    req = {
        "mode": "PB-ADV",
        "conditions": optimizer.MODEL_CONDITIONS,
        "verification_budget": 50,
    }
    got = sc.fixed_grid(CONTRACT, Table(), req, list(sc.GRID))
    assert [(p["c1"], p["c2"], p["t_amb_c"], p["soc0"]) for p in got] == [
        (p["c1"], p["c2"], p["t_amb_c"], p["soc0"])
        for p in optimizer.mode_x(CONTRACT, grid)
    ]
