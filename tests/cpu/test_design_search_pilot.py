"""Graphite's Optimizer researcher and the equal-query design-search pilot
(GRAPHITE-ADMISSION-01 slice C).

Synthetic models and references only (the analytic cell of
`test_design_search_commitment`), on EV2's published development conditions:
no solver, no EV4 material, no live model.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import shutil
from pathlib import Path

import pytest
from graphite_fixtures import grant
from test_design_search_commitment import DEV, infer, reference

from carbon.agent_campaign.graphite import optimizer_research as orr
from carbon.agent_campaign.graphite.literature import FIXTURE_INDEX
from carbon.agent_campaign.graphite.model import ScriptedModel, text
from carbon.battery.value import design_search_adapter as dsa
from carbon.battery.value import design_search_pricing as pricing
from carbon.battery.value import search_commitment as sc
from carbon.battery.value.ev4_protected_conditions import EV4_VERIFICATION
from carbon.design_search import experiment as ex
from carbon.design_search import methods

REPOSITORY = Path(__file__).resolve().parents[2]
ADAPTER = dsa.adapter()
GRID = [
    (round(0.5 + 0.1 * i, 2), round(0.2 + 0.1 * j, 2))
    for i in range(16)
    for j in range(9)
]
MODEL = {"member": "synthetic-s0", "recipe_digest": "sha256:" + "1" * 64, "seed": 0}
SEED_POLICY = "deterministic; no randomness"
NOW = datetime.datetime(2026, 10, 2, 22, 0, tzinfo=datetime.UTC)


def conditions(rows=DEV):
    return [{"t_amb_c": t, "soc0": s} for t, s in rows]


def neutral(mode="PB-INV", designs=GRID, rows=DEV, budget=None, name="fixed_grid"):
    return ex.neutral_request(
        ADAPTER,
        mode=mode,
        model=MODEL,
        designs=dsa.designs(designs),
        conditions=conditions(rows),
        query_budget=budget or len(designs) * len(rows),
        verification_budget=3,
        method={
            "name": name,
            "code_digest": "sha256:" + "2" * 64,
            "configuration_digest": "sha256:" + "3" * 64,
        },
        seed_policy=SEED_POLICY,
    )


def run(method, parameters, request):
    engine, space = ADAPTER.request(request)
    oracle = ADAPTER.oracle(engine, space, infer)
    if method == "fixed_grid":
        return ADAPTER.baseline(oracle, engine, space), oracle, engine, space
    view = ADAPTER.view(engine, space)
    return methods.run(method, parameters, view, oracle), oracle, engine, space


# --- the registered methods, on battery's adapter -------------------------------------


def test_screen_then_confirm_finds_the_baselines_design_with_fewer_queries():
    baseline, full, *_ = run("fixed_grid", {}, neutral())
    assert baseline, "the synthetic cell has a feasible design"
    for screen in range(len(DEV)):
        found, oracle, *_ = run(
            "screen_then_confirm", {"screen_condition": screen}, neutral()
        )
        assert found == baseline
        assert oracle.used <= full.used == len(GRID) * len(DEV)
    assert (
        min(
            run("screen_then_confirm", {"screen_condition": s}, neutral())[1].used
            for s in range(len(DEV))
        )
        < full.used
    )


def test_coarse_to_fine_selects_by_the_baselines_rule():
    baseline, full, engine, space = run("fixed_grid", {}, neutral())
    found, oracle, *_ = run(
        "coarse_to_fine", {"stride": 3, "radius": 1, "top_k": 2}, neutral()
    )
    assert oracle.used < full.used
    (best,) = baseline
    (pick,) = found
    # Never better than the full grid's optimum; feasible at every condition.
    assert pick["predicted_worst_time_to_cv_s"] >= best["predicted_worst_time_to_cv_s"]
    table = {tuple(e["point"]): e["quantities"] for e in full.log}
    view = ADAPTER.view(engine, space)
    assert all(view.passes(table[(pick["c1"], pick["c2"], t, s)]) for t, s in DEV)


def test_coarse_to_fine_adversarial_ranks_by_margin_within_the_budget():
    baseline, full, *_ = run("fixed_grid", {}, neutral(mode="PB-ADV"))
    found, oracle, *_ = run(
        "coarse_to_fine", {"stride": 2, "radius": 1, "top_k": 3}, neutral(mode="PB-ADV")
    )
    assert 0 < len(found) <= 3 and oracle.used <= full.used
    margins = [p["predicted_margin_bands"] for p in found]
    assert margins == sorted(margins)
    assert set(found[0]) == set(baseline[0])
    # The full grid's smallest margin is a lower bound on what a subset finds.
    assert margins[0] >= baseline[0]["predicted_margin_bands"]


@pytest.mark.parametrize(
    "method, parameters",
    [
        ("screen_then_confirm", {"screen_condition": 1}),
        ("coarse_to_fine", {"stride": 2, "radius": 2, "top_k": 4}),
    ],
)
def test_a_method_stops_inside_a_small_budget(method, parameters):
    found, oracle, *_ = run(method, parameters, neutral(budget=30))
    assert oracle.used <= 30
    assert isinstance(found, list)


@pytest.mark.parametrize(
    "method, parameters, mode, code",
    [
        ("simulated_annealing", {}, "PB-INV", "method_not_registered"),
        (
            "screen_then_confirm",
            {"screen_condition": 4},
            "PB-INV",
            "parameter_outside_bounds",
        ),
        ("screen_then_confirm", {"screen_condition": 0}, "PB-ADV", "does_not_serve"),
        ("coarse_to_fine", {"stride": 1, "radius": 1, "top_k": 1}, "PB-INV", "outside"),
        ("coarse_to_fine", {"stride": 2, "radius": 1}, "PB-INV", "not_exactly"),
        (
            "coarse_to_fine",
            {"stride": 2.0, "radius": 1, "top_k": 1},
            "PB-INV",
            "outside",
        ),
    ],
)
def test_an_unregistered_method_or_parameter_is_refused(method, parameters, mode, code):
    with pytest.raises(methods.MethodError, match=code):
        methods.check(method, parameters, mode=mode, conditions=len(DEV))


def test_ev4_conditions_are_refused_through_the_neutral_request():
    with pytest.raises(sc.SearchError, match="protected_material_requested"):
        ADAPTER.request(neutral(rows=[EV4_VERIFICATION[0]]))


def test_the_neutral_request_uses_the_adapters_variables():
    with pytest.raises(ex.ExperimentError, match="variables_are_the_adapters"):
        ex.neutral_request(
            ADAPTER,
            mode="PB-INV",
            model=MODEL,
            designs=[{"rate": 1.0}],
            conditions=conditions(),
            query_budget=1,
            verification_budget=1,
            method={},
            seed_policy=SEED_POLICY,
        )
    with pytest.raises(ex.ExperimentError, match="mode_not_served"):
        neutral(mode="PB-XYZ")


# --- freeze and pilot ------------------------------------------------------------------


PANEL = [
    {**MODEL, "material": "DEVELOPMENT"},
    {
        "member": "synthetic-s1",
        "recipe_digest": "sha256:" + "4" * 64,
        "seed": 1,
        "material": "DEVELOPMENT",
    },
]
PROPOSALS = {
    "graphite": {"method": "screen_then_confirm", "parameters": {"screen_condition": 0}}
}


def frozen(repository=REPOSITORY, adapter=ADAPTER, **changes):
    fields = {
        "repository": repository,
        "mode": "PB-INV",
        "designs": dsa.designs(GRID),
        "conditions": conditions(),
        "query_budget": len(GRID) * len(DEV),
        "verification_budget": 3,
        "seed_policy": SEED_POLICY,
        "panel": PANEL,
        "proposals": PROPOSALS,
    }
    return ex.freeze(adapter, **{**fields, **changes})


def test_the_freeze_pins_the_comparison():
    manifest = frozen()
    assert manifest["freeze_digest"].startswith("sha256:")
    assert set(manifest["methods"]) == {"fixed_grid", "graphite"}
    assert set(manifest["code"]) == set(ex.NEUTRAL_CODE) | set(dsa.CODE_PATHS)
    assert "uv.lock" in manifest["dependencies"]
    for key in (
        "decision_contract",
        "initialization",
        "tie_policy",
        "stopping",
        "failure_handling",
        "seed_policy",
        "reference_allocation",
    ):
        assert manifest[key]
    assert frozen()["freeze_digest"] == manifest["freeze_digest"]


@pytest.mark.parametrize(
    "changes, code",
    [
        (
            {"panel": [{**MODEL, "material": "CONFIRMATION"}]},
            "panel_is_development_models_only",
        ),
        ({"panel": [PANEL[0], PANEL[0]]}, "panel_members_are_unique"),
        (
            {"proposals": {"fixed_grid": {"method": "fixed_grid", "parameters": {}}}},
            "the_baseline_is_declared_not_proposed",
        ),
    ],
)
def test_a_freeze_refuses_what_it_cannot_pin(changes, code):
    with pytest.raises(ex.ExperimentError, match=code):
        frozen(**changes)


def test_the_pilot_runs_every_method_at_equal_budgets_committing_first(tmp_path):
    events = []

    def commit(engine, selections, oracle, directory):
        events.append(("commit", engine["request_digest"]))
        return sc.commit(engine, selections, oracle, directory)

    def watching(jobs):
        events.append(("reference", len(jobs)))
        return reference(jobs)

    adapter = dataclasses.replace(ADAPTER, commit=commit)
    manifest = frozen(adapter=adapter)
    report = ex.pilot(
        manifest,
        adapter,
        repository=REPOSITORY,
        models={p["member"]: infer for p in PANEL},
        reference=watching,
        directory=tmp_path,
    )
    assert report["freeze_digest"] == manifest["freeze_digest"]
    for rows in report["members"].values():
        budgets = {row["query_budget"] for row in rows.values()}
        assert budgets == {len(GRID) * len(DEV)}
        assert rows["graphite"]["queries_used"] <= rows["fixed_grid"]["queries_used"]
        assert rows["graphite"]["selections"] == rows["fixed_grid"]["selections"]
    for index, event in enumerate(events):
        if event[0] == "reference":
            assert events[index - 1][0] == "commit"
    assert (
        report["summary"]["graphite"]["queries_used"]
        < report["summary"]["fixed_grid"]["queries_used"]
    )
    assert not any(report["claims"].values())


def _copy_repository(tmp_path):
    root = tmp_path / "repository"
    for relative in (*ex.NEUTRAL_CODE, *dsa.CODE_PATHS, *ex.DEPENDENCIES):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / relative, target)
    return root


def test_the_pilot_refuses_drifted_code_an_altered_freeze_or_another_panel(tmp_path):
    root = _copy_repository(tmp_path)
    manifest = frozen(repository=root)
    models = {p["member"]: infer for p in PANEL}
    with pytest.raises(ex.ExperimentError, match="models_are_exactly_the_frozen_panel"):
        ex.pilot(
            manifest,
            ADAPTER,
            repository=root,
            models={**models, "extra": infer},
            reference=reference,
            directory=tmp_path / "a",
        )
    altered = {**manifest, "query_budget": 10**6}
    with pytest.raises(ex.ExperimentError, match="freeze_manifest_altered"):
        ex.pilot(
            altered,
            ADAPTER,
            repository=root,
            models=models,
            reference=reference,
            directory=tmp_path / "b",
        )
    path = root / "carbon/design_search/methods.py"
    path.write_text(path.read_text() + "\n# changed after the freeze\n")
    with pytest.raises(ex.ExperimentError, match="frozen_code_changed"):
        ex.pilot(
            manifest,
            ADAPTER,
            repository=root,
            models=models,
            reference=reference,
            directory=tmp_path / "c",
        )


# --- a synthetic second Challenge ------------------------------------------------------


class ToyOracle:
    def __init__(self, budget, infer):
        self.budget, self.infer, self.used, self.elapsed, self.log = (
            budget,
            infer,
            0,
            0.0,
            [],
        )

    def query(self, points):
        if self.used + len(points) > self.budget:
            raise ValueError("query_budget_exhausted")
        self.used += len(points)
        return [self.infer(p) for p in points]


def toy_adapter():
    def request(neutral):
        space = [(d["a"], d["b"]) for d in neutral["designs"]]
        return {
            **neutral,
            "conditions": [(c["u"],) for c in neutral["conditions"]],
        }, space

    def baseline(oracle, engine, space):
        best = None
        for d in space:
            qs = oracle.query([(*d, *c) for c in engine["conditions"]])
            if all(q["ok"] for q in qs):
                key = (max(q["f"] for q in qs), d)
                best = key if best is None or key < best else best
        return (
            []
            if best is None
            else [{"a": best[1][0], "b": best[1][1], "worst": best[0]}]
        )

    def view(engine, space):
        return methods.View(
            mode=engine["mode"],
            designs=tuple(space),
            conditions=tuple(engine["conditions"]),
            verification_budget=engine["verification_budget"],
            passes=lambda q: q["ok"],
            objective=lambda q: q["f"],
            margin=lambda q: q["slack"],
            select_design=lambda d, worst: {"a": d[0], "b": d[1], "worst": worst},
            select_point=lambda d, c, q: {"a": d[0], "b": d[1], "u": c[0]},
        )

    def verify(commitment, reference):
        return {"verdicts": {"FEASIBLE": len(commitment["selections"])}, "rows": []}

    return ex.SearchAdapter(
        challenge="synthetic-heat-sink-v1",
        design_variables=("a", "b"),
        condition_variables=("u",),
        contract_digest="sha256:" + "5" * 64,
        modes=("PB-INV", "PB-ADV"),
        request=request,
        oracle=lambda engine, space, infer: ToyOracle(engine["query_budget"], infer),
        baseline=baseline,
        view=view,
        commit=lambda engine, selections, oracle, directory: {"selections": selections},
        verify=verify,
        code_paths=(),
        tie_policy="lowest worst f, then lower (a, b)",
    )


def toy_model(point):
    a, b, u = point
    return {"f": (a - 2) ** 2 + (b - 1) ** 2 + u, "ok": a + b <= 6, "slack": 6 - a - b}


def test_a_synthetic_second_challenge_runs_the_same_methods(tmp_path):
    toy = toy_adapter()
    manifest = ex.freeze(
        toy,
        repository=REPOSITORY,
        mode="PB-INV",
        designs=[{"a": a, "b": b} for a in range(6) for b in range(4)],
        conditions=[{"u": u} for u in range(3)],
        query_budget=6 * 4 * 3,
        verification_budget=2,
        seed_policy=SEED_POLICY,
        panel=[{**MODEL, "material": "DEVELOPMENT"}],
        proposals={
            "screen": {
                "method": "screen_then_confirm",
                "parameters": {"screen_condition": 0},
            },
            "coarse": {
                "method": "coarse_to_fine",
                "parameters": {"stride": 2, "radius": 1, "top_k": 2},
            },
        },
    )
    report = ex.pilot(
        manifest,
        toy,
        repository=REPOSITORY,
        models={MODEL["member"]: toy_model},
        reference=None,
        directory=tmp_path,
    )
    rows = report["members"][MODEL["member"]]
    assert rows["fixed_grid"]["selections"] == [{"a": 2, "b": 1, "worst": 2}]
    assert rows["screen"]["selections"] == rows["fixed_grid"]["selections"]
    assert rows["coarse"]["selections"] == rows["fixed_grid"]["selections"]
    assert rows["screen"]["queries_used"] < rows["fixed_grid"]["queries_used"]


# --- Graphite's proposal ---------------------------------------------------------------

RESULTS = (
    {
        "result_id": "dev-grid-001",
        "summary": "Synthetic development result: most grid designs fail at one condition",
        "ref": "synthetic fixture; no run",
    },
)


def brief():
    return orr.brief(
        ADAPTER,
        mode="PB-INV",
        designs=len(GRID),
        conditions=len(DEV),
        query_budget=len(GRID) * len(DEV),
        verification_budget=3,
        index=FIXTURE_INDEX,
        results=RESULTS,
    )


def reply(**changes):
    value = {
        "method": "screen_then_confirm",
        "parameters": {"screen_condition": 0},
        "rationale": "screening at one condition rejects most designs for one query each",
        "sources": ["card:fixture-design-0003", "result:dev-grid-001"],
        "expected_effect": "the baseline's design with fewer model queries",
    }
    value.update(changes)
    return text(json.dumps(value))


def researcher(tmp_path, step):
    model = ScriptedModel([step])
    job = orr.OptimizerResearcher(
        root=tmp_path / "optimizer",
        grant=grant(),
        model=model,
        clock=lambda: 1000.0,
        now=lambda: NOW,
        sleep=lambda seconds: None,
    )
    return job, model


def test_graphite_proposes_a_method_that_the_pilot_freezes_and_runs(tmp_path):
    document = brief()
    assert "conditions" in document and type(document["conditions"]) is int
    job, model = researcher(tmp_path, reply())
    summary = job.propose("proposal-1", document)
    assert summary["status"] == "PROPOSED" and summary["role"] == "optimizer_researcher"
    (request,) = model.requests
    assert (
        request["tools"] == [] and request["instructions"] == orr.METHOD_PROPOSAL_PROMPT
    )
    proposal = json.loads(
        (job.task.run_dir("proposal-1") / "method-proposal.json").read_text()
    )
    assert proposal["status"] == "PROPOSED"
    assert proposal["proposed_by"] == {
        "agent": "graphite",
        "role": "optimizer_researcher",
        "session": "proposal-1",
    }
    manifest = frozen(proposals={"graphite": proposal})
    report = ex.pilot(
        manifest,
        ADAPTER,
        repository=REPOSITORY,
        models={p["member"]: infer for p in PANEL},
        reference=reference,
        directory=tmp_path / "pilot",
    )
    assert set(report["summary"]) == {"fixed_grid", "graphite"}


@pytest.mark.parametrize(
    "step, code",
    [
        (reply(method="simulated_annealing"), "method_not_registered"),
        (
            reply(method="fixed_grid", parameters={}),
            "the_baseline_is_declared_not_proposed",
        ),
        (reply(parameters={"screen_condition": 9}), "parameter_outside_bounds"),
        (reply(query_budget=10**6), "reply_fields_not_exactly_the_proposal"),
        (reply(status="ACCEPTED"), "reply_fields_not_exactly_the_proposal"),
        (reply(sources=["card:not-in-the-brief"]), "source_not_in_brief"),
        (reply(sources=[]), "proposal_cites_no_source"),
        (text("Use Bayesian optimization."), "reply_not_json"),
    ],
)
def test_a_proposal_outside_the_rules_is_rejected(tmp_path, step, code):
    job, _model = researcher(tmp_path, step)
    summary = job.propose("proposal-1", brief())
    assert summary["status"] == "REJECTED" and summary["code"] == code
    assert not (job.task.run_dir("proposal-1") / "method-proposal.json").exists()


# --- priced choices --------------------------------------------------------------------


def test_the_priced_choices_page_is_current_and_chooses_nothing():
    page = (REPOSITORY / "docs/development/graphite/OPTIMIZER_CHOICES.md").read_text()
    for line in pricing.render().splitlines():
        if line:
            assert line in page
    rows = {r["k"]: r for r in pricing.k_choices()}
    assert (
        rows[50]["solves_per_panel"] == 250
        and rows[50]["usd_per_panel"] == "HUMAN_INPUT"
    )
    assert pricing.k_choices(usd_per_cpu_hour=1.0)[0]["usd_per_panel"] == 4.51
    grids = {
        (r["design_grid"][:6], r["condition_grid"][:6]): r
        for r in pricing.grid_choices()
    }
    assert grids[("EV3/EV", "EV4 mo")]["protected_conditions"] == 32
    assert not grids[("EV3/EV", "EV4 mo")]["usable_for_development"]
    assert grids[("EV3/EV", "offset")]["usable_for_development"]
