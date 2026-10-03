"""Battery's adapter for the Challenge-neutral design search (GRAPHITE-ADMISSION-01 slice C).

`carbon.design_search` runs Graphite's proposed search methods against a
Challenge's fixed baseline at equal budgets. This module is what battery
supplies, over the #475 commitment layer (`search_commitment`), which it uses
unchanged:

- the design variables `c1`, `c2` and the condition variables `t_amb_c`,
  `soc0`;
- the engine: `search_commitment.request` (development material only, the
  contract's envelope, EV4's protected conditions refused), its budgeted
  `Oracle`, `commit` before any reference access, and `verify`;
- the fixed baseline: `search_commitment.fixed_grid`, which reproduces EV4's
  `optimizer.mode_d` and `optimizer.mode_x` rules (conformance test in
  `tests/cpu/test_design_search_commitment.py`);
- the view the neutral methods read: feasibility, the objective (time to CV
  onset) and the band-normalised binding margin, as `fixed_grid` computes
  them;
- the files a freeze pins.

Nothing here changes EV4, its contract, its panel or `optimizer.py`.
"""

from __future__ import annotations

from carbon.design_search.experiment import SearchAdapter
from carbon.design_search.methods import View
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

from . import contract as ev
from . import search_commitment as sc

RESULT_SCHEMA = "carbon.design-search.neutral-result.v1"
CONTRACT_PATH = ev.CONTRACTS / "ev2-charge-protocol-selection.v1.json"
DESIGN_VARIABLES = ("c1", "c2")
CONDITION_VARIABLES = ("t_amb_c", "soc0")
CODE_PATHS = (
    "carbon/battery/value/design_search_adapter.py",
    "carbon/battery/value/search_commitment.py",
    "carbon/battery/value/optimizer.py",
    "carbon/battery/value/decision.py",
    "carbon/battery/value/contract.py",
    "carbon/battery/value/ev4_protected_conditions.py",
)
TIE_POLICY = (
    "PB-INV: lowest worst-case predicted time to CV onset, then lower c1, then "
    "lower c2 (the contract's tie rule); PB-ADV: smallest band-normalised "
    "margin, then c1, c2, t_amb_c, soc0"
)


def designs(grid=sc.GRID):
    return [{"c1": c1, "c2": c2} for c1, c2 in grid]


def adapter(contract=None):
    """The battery adapter over a decision contract (EV2's by default)."""
    if contract is None:
        contract, contract_digest = ev.load(CONTRACT_PATH)
    else:
        contract_digest = ev.digest(contract)

    def request(neutral):
        return sc.request(
            contract=contract,
            model=neutral["model"],
            mode=neutral["mode"],
            conditions=[[c["t_amb_c"], c["soc0"]] for c in neutral["conditions"]],
            query_budget=neutral["query_budget"],
            verification_budget=neutral["verification_budget"],
            optimizer=neutral["method"],
            seed_policy=neutral["seed_policy"],
            designs=[(d["c1"], d["c2"]) for d in neutral["designs"]],
            material=neutral["material"],
        )

    def margins(q):
        return sc.margins(contract, q)

    def margin(q):
        return min(margins(q).values())

    def binding(q):
        values = margins(q)
        return min(values, key=lambda name: (values[name], name))

    def view(engine, space):
        return View(
            mode=engine["mode"],
            designs=tuple(tuple(x) for x in space),
            conditions=tuple(tuple(c) for c in engine["conditions"]),
            verification_budget=engine["verification_budget"],
            passes=lambda q: sc._passes(contract, q),
            objective=lambda q: q["time_to_cv_onset_s"],
            margin=margin,
            select_design=lambda d, worst: {
                "c1": d[0],
                "c2": d[1],
                "predicted_worst_time_to_cv_s": worst,
            },
            select_point=lambda d, c, q: {
                "c1": d[0],
                "c2": d[1],
                "t_amb_c": c[0],
                "soc0": c[1],
                "predicted_margin_bands": margin(q),
                "binding_constraint": binding(q),
            },
        )

    def verify(commitment, reference):
        result = sc.verify(contract, commitment, reference)
        return {
            "schema": RESULT_SCHEMA,
            "challenge": BATTERY_CHALLENGE,
            "engine_schema": result["schema"],
            "commitment_digest": result["commitment_digest"],
            "request_digest": result["request_digest"],
            "mode": result["mode"],
            "status": result["status"],
            "reference_jobs": result["reference_jobs"],
            "verdicts": result["verdicts"],
            "rows": [
                {
                    "case_id": row["case_id"],
                    "design": {"c1": row["c1"], "c2": row["c2"]},
                    "condition": {"t_amb_c": row["t_amb_c"], "soc0": row["soc0"]},
                    "verdict": row["verdict"],
                    "reference": row["reference"],
                }
                for row in result["rows"]
            ],
            "claims": result["claims"],
        }

    return SearchAdapter(
        challenge=BATTERY_CHALLENGE,
        design_variables=DESIGN_VARIABLES,
        condition_variables=CONDITION_VARIABLES,
        contract_digest=contract_digest,
        modes=sc.MODES,
        request=request,
        oracle=lambda engine, space, infer: sc.Oracle(contract, infer, engine, space),
        baseline=lambda oracle, engine, space: sc.fixed_grid(
            contract, oracle, engine, space
        ),
        view=view,
        commit=sc.commit,
        verify=verify,
        code_paths=CODE_PATHS,
        tie_policy=TIE_POLICY,
    )
