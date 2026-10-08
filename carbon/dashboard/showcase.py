"""The design showcase: a model drives Carbon's registered optimizer on a public
design task, replayed step by step against the reference solver's truth.

DASHBOARD_PLAN.md §4. Public material only:

- the task is EV4's public charge-protocol decision
  (`ev4-charge-protocol-selection.v1`, `data_scope: PUBLIC_SYNTHETIC`): pick
  the (c1, c2) two-stage protocol from a fixed 7 × 5 grid that reaches CV
  soonest while meeting every limit, for one operating condition;
- the truth is EV4's committed public reference solves
  (`decision-references.jsonl.gz`), checked against the committed pin
  `references.sha256` before use.

How a replay is made:

1. **Register** a runnable `carbon.design-task.v2` task from the contract:
   the grid as the action grammar, the objective, the limits and the
   reference bands copied from the contract. The task matches battery Q3's
   neutral task (`battery_q3_v8._neutral_task`) on EV4's coarse grid.
2. **Run** `design_search.tasks.run_optimizer` unchanged, with the model's
   predictor wrapped in a recorder that notes every query in order and
   passes the value through untouched. The commitment is made before
   `judge` reads any reference.
3. **Judge** with `tasks.judge`, then attach the truth for each visited
   candidate and for the whole bank, so the page can draw the error.

The models here are Carbon's synthetic **controls** (`design_search.controls`):
reference rows with registered limit errors, labelled as controls, never as a
miner. They exist to show the failure modes the page must expose. A leader's
real predictions replace them once a prediction panel for this public task is
produced (DASHBOARD_PLAN.md §5.4).

The control severities and the optimizer's starts, budget and seed below are
display registrations for this showcase, chosen by DASHBOARD-01. They are not
score, gate or qualification values, and nothing outside the showcase reads
them.

DEVELOPMENT display only: no score, rank, qualification or "matches reality"
authority.
"""

from __future__ import annotations

import gzip
import hashlib
import itertools
import json
from pathlib import Path

from carbon.battery.value import contract as ev
from carbon.battery.value import decision as bd
from carbon.design_search import controls, tasks

REPLAY_SCHEMA = "carbon.dashboard.showcase-replay.v1"
INDEX_SCHEMA = "carbon.dashboard.showcase-index.v1"
REPOSITORY = Path(__file__).resolve().parents[2]
CONTRACT = "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
REFERENCES = "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"
REFERENCES_PIN = "docs/development/evidence/ev4-2026-10-01/references.sha256"
RESULTS = "docs/development/evidence/ev4-2026-10-01/results.json"
# The only files a replay may read. Each is committed public evidence.
PUBLIC_INPUTS = (CONTRACT, REFERENCES, REFERENCES_PIN, RESULTS)
CONDITION = "condition-0"
OBSERVER = "dashboard-showcase-ev4-projection.v1"
# Display registration for the showcase path (not a score value).
OPTIMIZER = {
    "class": "multi_start_local",
    "version": "v1",
    "starts": ["c1=0.75,c2=0.6", "c1=2,c2=1", "c1=1.25,c2=0.2"],
}
QUERY_BUDGET = 24
SEED = 0
_CONTROL_QUANTITIES = ("plating_margin_v", "peak_temperature_c")
# Synthetic control severities, in each limit's unit (display registration).
CONTROL_SEVERITIES = {
    "edge": {"plating_margin_v": 0.01, "peak_temperature_c": 2.0},
    "caution": {"plating_margin_v": 0.01, "peak_temperature_c": 2.0},
    "sign": {"plating_margin_v": 0.01, "peak_temperature_c": 2.0},
}
CONTROL_LABELS = {
    "edge": "Edge optimist: reads near-limit breaches as safe",
    "caution": "Over-cautious: reads near-limit safe designs as breaches",
    "sign": "Sign error at high first-stage rate (c1 1.5 to 2.0 C)",
}
LIMIT_LABELS = {
    "reach_class": "Reaches CV within the window",
    "plating_margin_v": "Plating margin",
    "peak_temperature_c": "Peak temperature",
}


class ShowcaseError(ValueError):
    pass


def _read(relative):
    if relative not in PUBLIC_INPUTS:
        raise ShowcaseError(f"not a registered public input: {relative}")
    return (REPOSITORY / relative).read_bytes()


def load_public():
    """The contract and reference rows, each checked against its pin."""
    contract, contract_digest = ev.load(REPOSITORY / CONTRACT)
    _read(CONTRACT)
    results = json.loads(_read(RESULTS))
    if results.get("contract_digest") != contract_digest:
        raise ShowcaseError("EV4 contract does not match its committed results")
    pinned = _read(REFERENCES_PIN).decode().split()[0]
    body = gzip.decompress(_read(REFERENCES))
    if hashlib.sha256(body).hexdigest() != pinned:
        raise ShowcaseError("EV4 references do not match their committed pin")
    if contract["data_scope"]["classification"] != "PUBLIC_SYNTHETIC":
        raise ShowcaseError("the showcase runs on public material only")
    rows = [json.loads(line) for line in body.decode().splitlines() if line]
    return {
        "contract": contract,
        "contract_digest": contract_digest,
        "references_sha256": pinned,
        "rows": {row["case_id"]: row for row in rows},
    }


def projection(contract, record):
    """Decision quantities from one reference record, as battery Q3 projects
    them (`battery_q3_v8._projection`; a test holds the two equal).

    An unreached CV keeps the optimizer's internal surrogate (window + 1 s)
    with `reach_class` -1. The replay never shows the surrogate as a time.
    """
    if record is None or record.get("status") != "OK" or not record.get("outputs"):
        return None
    measured = bd.measure(contract, record["outputs"])
    time = measured["time_to_cv_onset_s"]
    window = contract["objective"]["window_s"] - contract["objective"]["charge_start_s"]
    band = contract["reference"]["uncertainty"]["bands"]["time_to_cv_onset_s"]
    return {
        "time_to_cv_onset_s": window + 1 if time is None else time,
        "reach_class": -1 if time is None else (0 if time > window - band else 1),
        "plating_margin_v": measured["plating_margin_v"],
        "peak_temperature_c": measured["peak_temperature_c"],
    }


def _grammar(contract):
    variables = []
    for name in ("c1", "c2"):
        allowed = sorted(contract["design_variables"][name]["allowed"])
        steps = {round(b - a, 9) for a, b in itertools.pairwise(allowed)}
        if len(steps) != 1:
            raise ShowcaseError(f"{name} grid is not evenly spaced")
        variables.append(
            {
                "name": name,
                "type": "number",
                "min": allowed[0],
                "max": allowed[-1],
                "step": steps.pop(),
            }
        )
    return {
        "schema": tasks.GRAMMAR_SCHEMA,
        "version": "ev4-coarse-lattice.v1",
        "variables": variables,
        "rules": [],
    }


def register_task(public, scenario):
    """The runnable task for one public EV4 scenario."""
    contract = public["contract"]
    if len(scenario["conditions"]) != 1:
        raise ShowcaseError("the showcase task has one condition per scenario")
    candidates = ev.candidates(contract)
    bands = contract["reference"]["uncertainty"]["bands"]
    thermal = next(
        c["threshold"] for c in contract["constraints"] if c["id"] == "peak_temperature"
    )
    return tasks.task(
        f"showcase:{scenario['id']}",
        identity={
            "challenge": contract["challenge"]["id"],
            "contract_version": contract["version"],
            "action_grammar": _grammar(contract),
            "optimizer": OPTIMIZER,
            "query_budget": QUERY_BUDGET,
            "seed": SEED,
            "observer_version": OBSERVER,
            "reference_bank": "sha256:" + public["references_sha256"],
        },
        conditions=[{"id": CONDITION, "stratum": "scenario"}],
        strata={"scenario": {"p": 1.0, "q": 1.0, "w": 1.0}},
        candidates=[c["id"] for c in candidates],
        actions={c["id"]: {"c1": c["c1"], "c2": c["c2"]} for c in candidates},
        objective={
            "quantity": "time_to_cv_onset_s",
            "unit": "s",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[
            {
                "quantity": "reach_class",
                "unit": "verdict",
                "op": ">=",
                "value": 0,
                "band": 0.5,
            },
            {
                "quantity": "plating_margin_v",
                "unit": "V",
                "op": ">=",
                "value": 0,
                "band": bands["plating_margin_v"],
            },
            {
                "quantity": "peak_temperature_c",
                "unit": "degC",
                "op": "<=",
                "value": thermal,
                "band": bands["peak_temperature_c"],
            },
        ],
    )


def truth(public, task, scenario):
    """Reference quantities per candidate (None where the reference failed)."""
    contract = public["contract"]
    out = {}
    for candidate in ev.candidates(contract):
        case = ev.case_id(contract, scenario, candidate, 0)
        out[candidate["id"]] = projection(contract, public["rows"].get(case))
    return out


def control_specs(task):
    units = {limit["quantity"]: limit["unit"] for limit in task["limits"]}

    def severity(name):
        return {
            q: {"value": CONTROL_SEVERITIES[name][q], "unit": units[q]}
            for q in _CONTROL_QUANTITIES
        }

    specs = [
        {
            "schema": controls.CONTROL_SCHEMA,
            "name": "edge",
            "kind": "edge_optimist",
            "severity": severity("edge"),
            "limit_quantities": list(_CONTROL_QUANTITIES),
        },
        {
            "schema": controls.CONTROL_SCHEMA,
            "name": "caution",
            "kind": "over_cautious",
            "severity": severity("caution"),
            "limit_quantities": list(_CONTROL_QUANTITIES),
        },
        {
            "schema": controls.CONTROL_SCHEMA,
            "name": "sign",
            "kind": "localized_sign_error",
            "severity": severity("sign"),
            "limit_quantities": list(_CONTROL_QUANTITIES),
            "region": {"action": {"c1": {"min": 1.5, "max": 2.0}}, "strata": []},
        },
    ]
    registration = controls.register_controls(specs)
    controls.validate_controls(registration, task=task)
    return registration["controls"]


def control_predictor(task, spec, reference):
    """A synthetic control: the reference row with the control's registered
    limit errors. A failed reference row is a model failure the optimizer
    counts, never a guess."""
    by_action = {tasks.digest(a): c for c, a in task["actions"].items()}

    def predict(action, condition):
        row = reference[by_action[tasks.digest(action)]]
        if row is None:
            raise ValueError("reference unavailable for this control")
        return controls.task_control_prediction(task, spec, action, condition, row)

    return predict


def _margins(task, row):
    """Signed margin per limit (positive is inside the limit)."""
    out = {}
    for limit in task["limits"]:
        value = row[limit["quantity"]]
        out[limit["quantity"]] = (
            value - limit["value"] if limit["op"] == ">=" else limit["value"] - value
        )
    return out


def _view(task, row, *, reference):
    if row is None:
        return None
    assessed = tasks.assess(
        {**task, "candidates": ["x"]}, {("x", CONDITION): row}, reference=reference
    )["x"]
    reached = row["reach_class"] >= 0
    return {
        "time_to_cv_onset_s": row["time_to_cv_onset_s"] if reached else None,
        "reached": reached,
        "plating_margin_v": row["plating_margin_v"],
        "peak_temperature_c": row["peak_temperature_c"],
        "margins": _margins(task, row),
        "feasible": assessed["feasible"],
    }


def replay(public, scenario, *, model, predictor):
    """Run the registered optimizer with a recording predictor; judge after
    commitment; return the replay document."""
    task = register_task(public, scenario)
    queries = []

    def recorder(action, condition):
        entry = {"action": dict(action), "condition": condition["id"]}
        queries.append(entry)
        try:
            value = predictor(action, condition)
        except Exception:
            entry["failed"] = True
            raise
        entry["predicted"] = dict(value) if isinstance(value, dict) else None
        return value

    run = tasks.run_optimizer(task, recorder, model_id=model["id"])
    commitment = run["commitment"]
    # Only now is the reference read for judging and display.
    reference = truth(public, task, scenario)
    judged = tasks.judge(
        task,
        commitment,
        {(c, CONDITION): row for c, row in reference.items() if row is not None},
    )
    by_action = {tasks.digest(a): c for c, a in task["actions"].items()}
    steps = []
    predicted_so_far = {}
    for index, query in enumerate(queries):
        candidate = by_action[tasks.digest(query["action"])]
        predicted = query.get("predicted")
        if predicted is not None and not query.get("failed"):
            predicted_so_far[(candidate, CONDITION)] = predicted
        assessed = tasks.assess(task, predicted_so_far)
        p_view = (
            None
            if query.get("failed") or predicted is None
            else _view(task, predicted, reference=False)
        )
        t_view = _view(task, reference[candidate], reference=True)
        steps.append(
            {
                "step": index + 1,
                "candidate": candidate,
                "action": query["action"],
                "predicted": p_view,
                "truth": t_view,
                "model_failed": bool(query.get("failed")),
                "safety_miss": bool(
                    p_view
                    and t_view
                    and p_view["feasible"] is True
                    and t_view["feasible"] is False
                ),
                "running_pick": tasks.select(task, assessed),
            }
        )
    contract = public["contract"]
    unit_s = contract["minimum_useful_improvement_s"]
    regret = judged["regret"]
    return {
        "schema": REPLAY_SCHEMA,
        "labels": ["DEVELOPMENT", "PUBLIC_SYNTHETIC", model["kind"]],
        "model": model,
        "scenario": {
            "id": scenario["id"],
            "split": scenario["split"],
            "t_amb_c": scenario["conditions"][0][0],
            "soc0": scenario["conditions"][0][1],
        },
        "decision": contract["decision"]["statement"],
        "grid": {
            v["name"]: sorted(contract["design_variables"][v["name"]]["allowed"])
            for v in task["identity"]["action_grammar"]["variables"]
        },
        "units": {
            "time_to_cv_onset_s": "s",
            "plating_margin_v": "V",
            "peak_temperature_c": "degC",
            "regret_buyer_unit": f"minimum useful improvement ({unit_s:g} s)",
        },
        "limits": [
            {
                "quantity": limit["quantity"],
                "label": LIMIT_LABELS[limit["quantity"]],
                "unit": limit["unit"],
                "op": limit["op"],
                "value": limit["value"],
                "band": limit["band"],
            }
            for limit in task["limits"]
        ],
        "optimizer": {
            **task["identity"]["optimizer"],
            "query_budget": task["identity"]["query_budget"],
            "seed": task["identity"]["seed"],
            "accounting": run["accounting"],
        },
        "steps": steps,
        "bank": [
            {
                "candidate": c,
                "action": task["actions"][c],
                "truth": _view(task, reference[c], reference=True),
            }
            for c in task["candidates"]
        ],
        "result": {
            "kind": judged["kind"],
            "selected": judged["selected"],
            "best": judged["best"],
            "reference_state": judged["reference_state"],
            "reference_resolved": judged["reference_resolved"],
            "regret_s": regret,
            "regret_buyer_units": None if regret is None else regret / unit_s,
            "false_feasible": judged["kind"] == "SELECTED_INFEASIBLE",
            "safety_misses": sum(s["safety_miss"] for s in steps),
        },
        "provenance": {
            "contract": CONTRACT,
            "contract_digest": public["contract_digest"],
            "references": REFERENCES,
            "references_sha256": public["references_sha256"],
            "task_digest": task["task_digest"],
            "commitment_digest": commitment["commitment_digest"],
            "registration": "DASHBOARD-01 showcase display registration",
            "control_severities": CONTROL_SEVERITIES.get(model.get("control")),
        },
    }


def panel_predictor(public, scenario, panel):
    """The leader's predictions from the validator's signed showcase panel. A
    case the model gave no output for is a model failure the optimizer counts,
    never filled in."""
    contract = public["contract"]
    by_action = {
        tasks.digest({"c1": c["c1"], "c2": c["c2"]}): ev.case_id(
            contract, scenario, c, 0
        )
        for c in ev.candidates(contract)
    }

    def predict(action, condition):
        row = panel["predictions"].get(by_action[tasks.digest(action)])
        if row is None:
            raise ValueError("the model gave no prediction for this case")
        return dict(row)

    return predict


def _check_panel(public, panel):
    """The panel must be for this exact public contract."""
    contract_sha = hashlib.sha256(_read(CONTRACT)).hexdigest()
    if (
        panel["task"]["contract"] != CONTRACT
        or panel["task"]["contract_sha256"] != contract_sha
        or panel["contract_digest"] != public["contract_digest"]
    ):
        raise ShowcaseError("the showcase panel is for another contract")


def _write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _entry(name, scenario, model, document):
    result = document["result"]
    return {
        "file": name,
        "scenario": scenario["id"],
        "split": scenario["split"],
        "model": model["id"],
        "kind": model["kind"],
        "label": model["label"],
        "outcome": result["kind"],
        "safety_misses": result["safety_misses"],
        "regret_s": result["regret_s"],
    }


def build_all(out_dir, leaders=()):
    """Every public EV4 scenario for every control, plus each released
    incumbent's panel (`leaders`: `(board, panel)` pairs from the checked feed)
    on the development scenarios, and an index."""
    public = load_public()
    out_dir = Path(out_dir)
    entries = []
    unavailable = []
    for board, panel in leaders:
        if panel["state"] != "PREDICTED":
            unavailable.append(
                {
                    "board": board["slug"],
                    "hotkey": panel["model"]["hotkey"],
                    "code": panel["code"],
                }
            )
            continue
        _check_panel(public, panel)
        hotkey = panel["model"]["hotkey"]
        model = {
            "id": f"LEADER-{board['slug']}",
            "kind": "LEADER",
            "hotkey": hotkey,
            "submission_id": panel["model"]["submission_id"],
            "board": board["slug"],
            "device_class": board["device_class"],
            "label": f"Incumbent {hotkey[:6]}…{hotkey[-4:]} ({board['challenge']['id']}, {board['device_class']})",
            "note": "The released incumbent's model, rebuilt by Carbon and queried by the validator on public cases. Predictions only.",
        }
        for scenario in ev.scenarios(public["contract"], "development"):
            document = replay(
                public,
                scenario,
                model=model,
                predictor=panel_predictor(public, scenario, panel),
            )
            document["labels"] = [
                "DEVELOPMENT",
                *(["TESTNET"] if "TESTNET" in board["labels"] else []),
                "PUBLIC_SYNTHETIC",
                "LEADER",
                *(["FIXTURE"] if board["fixture"] else []),
            ]
            name = f"{scenario['id']}--leader--{board['slug']}.json".lower()
            _write(out_dir / name, document)
            entries.append(_entry(name, scenario, model, document))
    for scenario in ev.scenarios(public["contract"]):
        task = register_task(public, scenario)
        reference = truth(public, task, scenario)
        for spec in control_specs(task):
            model = {
                "id": f"CONTROL-{spec['name']}",
                "kind": "CONTROL",
                "control": spec["name"],
                "label": CONTROL_LABELS[spec["name"]],
                "note": "Synthetic control model, not a miner.",
            }
            document = replay(
                public,
                scenario,
                model=model,
                predictor=control_predictor(task, spec, reference),
            )
            name = f"{scenario['id']}--{spec['name']}.json".lower()
            _write(out_dir / name, document)
            entries.append(_entry(name, scenario, model, document))
    index = {
        "schema": INDEX_SCHEMA,
        "labels": ["DEVELOPMENT", "PUBLIC_SYNTHETIC"],
        "leaders_unavailable": unavailable,
        "replays": entries,
    }
    (out_dir / "index.json").write_text(
        json.dumps(index, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return index
