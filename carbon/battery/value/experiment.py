"""EV1: the fixed-candidate engineering-value experiment, as one operator path.

    python -m carbon.battery.value run    --root DIR [--contract PATH] [--workers N]
    python -m carbon.battery.value resume --root DIR [--workers N]
    python -m carbon.battery.value status --root DIR
    python -m carbon.battery.value export --root DIR --out DIR

Stages. Each is resumable, and none repeats work that is already recorded:

1. **freeze**: the contract, its digest, the candidate set, the scenarios,
   the panel and the scoring-set identity are written once. A different
   contract under the same root is refused (`contract_mismatch`).
2. **references**: the decision cases are solved by the battery truth service
   (resumable records; `FAILED_INFRA` is retried, terminal records are kept).
   Without the pinned PyBaMM runtime here, the jobs file and the exact
   truth-container command are written instead and the stage reports
   `MISSING_PREREQUISITE`. `import-references` ingests records solved
   elsewhere.
3. **panel**: each member is reconstructed from its recipe and seed through
   the battery worker backend, then asked for predictions on the scoring set
   and the decision inputs. Members see only inputs, never a reference.
   Each member's predictions are written once, so an interrupted run resumes
   at the next member.
4. **evaluate**: every member makes the same deterministic selection. It is
   verified against the reference, scored by every candidate rule, and the
   rules are compared with the verified decision outcomes. The development
   scenarios choose the rule, which is then frozen and assessed on the
   verification scenarios.

Everything here is off-chain public synthetic DEVELOPMENT evidence. The
approved testnet exam and its rule are untouched.
"""

from __future__ import annotations

import contextlib
import fcntl
import gzip
import json
import os
import time
from pathlib import Path

from carbon.development_session.data import write_once

from . import contract as ev
from . import decision as d
from . import panel as pn
from . import scoring as sc

REPOSITORY = Path(__file__).resolve().parents[3]
SCHEMA = "carbon.engineering-value-experiment.v1"
RESULT_SCHEMA = "carbon.engineering-value-results.v1"


class ExperimentError(RuntimeError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def _gzip_json(value):
    return gzip.compress(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode(), mtime=0
    )


class Experiment:
    def __init__(self, root, *, repository=REPOSITORY):
        self.root = Path(root)
        self.repository = Path(repository)

    # --- layout and locking ------------------------------------------------------

    def _dir(self, *parts):
        path = self.root.joinpath(*parts)
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        return path

    @contextlib.contextmanager
    def lock(self):
        """One runner per experiment root, across processes."""
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self.root / ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ExperimentError("experiment_busy") from None
            yield
        finally:
            os.close(fd)

    @property
    def manifest_path(self):
        return self.root / "manifest.json"

    def manifest(self):
        if not self.manifest_path.exists():
            raise ExperimentError("not_frozen")
        return json.loads(self.manifest_path.read_bytes())

    def contract(self):
        manifest = self.manifest()
        document = ev.validate(manifest["contract"])
        if ev.digest(document) != manifest["contract_digest"]:
            raise ExperimentError("contract_mismatch", "manifest contract changed")
        return document

    # --- 1. freeze -----------------------------------------------------------------

    def freeze(self, contract_path=None):
        document, contract_digest = ev.load(contract_path)
        if self.manifest_path.exists():
            if self.manifest()["contract_digest"] != contract_digest:
                raise ExperimentError(
                    "contract_mismatch", "this root was frozen with another contract"
                )
            return self.manifest()
        from ..contracts import implementation_digest

        _store, _case_ids, scoring_identity = sc.scoring_set(self.repository)
        manifest = {
            "schema": SCHEMA,
            "contract_digest": contract_digest,
            "contract": document,
            "candidates": ev.candidates(document),
            "decision_cases": len(ev.decision_cases(document)),
            "panel": [
                {"member": m, "family": f, "strategy": s, "seed": seed}
                for m, f, s, seed in pn.members()
            ],
            "controls": list(pn.CONTROLS),
            "scoring_set": scoring_identity,
            "implementation_digest": implementation_digest(),
            "frozen_unix": int(time.time()),
        }
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        write_once(self.manifest_path, _json_bytes(manifest))
        return manifest

    # --- 2. references -----------------------------------------------------------------

    @property
    def references_path(self):
        return self._dir("references") / "decision.jsonl"

    def _jobs(self):
        return [
            {k: job[k] for k in ("case_id", "c1", "c2", "t_amb_c", "soc0")}
            for job in ev.decision_cases(self.contract())
        ]

    def references(self, *, workers=1, timeout_s=1200.0, solver=None):
        """Solve the decision cases (resumable), or report what is missing."""
        from ..truth import TruthService
        from ..truth_env import (
            TruthEnvironmentError,
            require_truth_runtime,
            solve_command,
        )

        jobs = self._jobs()
        if solver is None:
            try:
                require_truth_runtime(self.repository)
            except TruthEnvironmentError as missing:
                work = self._dir("references", "solve")
                write_once(
                    work / "jobs.json",
                    _json_bytes({"fingerprint": "ev1", "jobs": jobs}),
                )
                return {
                    "status": "MISSING_PREREQUISITE",
                    "code": "truth_runtime_unavailable",
                    "detail": str(missing),
                    "jobs": len(jobs),
                    "solve_command": solve_command(
                        "<verified truth overlay>", work, repository=self.repository
                    ),
                }
            service = TruthService(
                self.references_path, workers=workers, timeout_s=timeout_s
            )
        else:
            service = TruthService(
                self.references_path,
                solver=solver,
                workers=workers,
                timeout_s=timeout_s,
            )
        if not self.references_path.exists():
            self.references_path.touch(mode=0o600)
        summary = service.run(jobs)
        return {"status": "SOLVED", **summary}

    def import_references(self, records_path):
        """Ingest records solved elsewhere (the truth container). Only this
        experiment's case ids are kept; nothing already recorded is replaced."""
        wanted = {job["case_id"]: job for job in self._jobs()}
        have = {r["case_id"] for r in self._reference_records()}
        added = 0
        with self.references_path.open("a") as out:
            for line in Path(records_path).read_text().splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                job = wanted.get(record.get("case_id"))
                if job is None or record["case_id"] in have or record.get("refined"):
                    continue
                inputs = record.get("inputs") or {}
                if any(
                    abs(float(inputs.get(k, float("nan"))) - job[k]) > 1e-12
                    for k in ("c1", "c2", "t_amb_c", "soc0")
                ):
                    raise ExperimentError(
                        "reference_inputs_mismatch", record["case_id"]
                    )
                out.write(json.dumps(record, sort_keys=True) + "\n")
                have.add(record["case_id"])
                added += 1
        self.references_path.chmod(0o600)
        return {"imported": added}

    def _reference_records(self):
        if not self.references_path.exists():
            return []
        return [
            json.loads(line)
            for line in self.references_path.read_text().splitlines()
            if line.strip()
        ]

    def reference_map(self):
        """Terminal reference records by case id (the latest terminal wins;
        FAILED_INFRA is never a reference)."""
        terminal = {"OK", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT"}
        out = {}
        for record in self._reference_records():
            if record.get("status") in terminal and not record.get("refined"):
                out[record["case_id"]] = record
        return out

    # --- 3. panel -------------------------------------------------------------------------

    def _prediction_path(self, member):
        return self._dir("predictions") / f"{member}.json.gz"

    def panel(self, *, backend=None, only=None):
        """Reconstruct and predict for each member not yet recorded."""
        if backend is None:
            from ..worker import DirectBackend

            backend = DirectBackend(self.repository)
        from ..compile import compile_recipe

        store, scoring_ids, _ = sc.scoring_set(self.repository)
        decision_inputs = {
            job["case_id"]: {k: job[k] for k in ("c1", "c2", "t_amb_c", "soc0")}
            for job in ev.decision_cases(self.contract())
        }
        scoring_inputs = {
            c: dict(store.refs[c]["inputs"])
            for c in scoring_ids
            if store.refs[c].get("inputs")
        }
        done = []
        for member, _family, strategy, seed in pn.members():
            if only is not None and member not in only:
                continue
            path = self._prediction_path(member)
            if path.exists():
                continue
            _, recipe = compile_recipe(strategy)
            started = time.monotonic()
            state, stats = backend.reconstruct(f"ev1-rec-{member}", recipe, seed)
            trained = time.monotonic() - started
            started = time.monotonic()
            predictions = backend.infer(
                f"ev1-inf-{member}", state, {**scoring_inputs, **decision_inputs}
            )
            predicted = time.monotonic() - started
            write_once(
                path,
                _gzip_json(
                    {
                        "member": member,
                        "recipe_digest": recipe.recipe_digest,
                        "seed": seed,
                        "reconstruction": dict(backend.identity),
                        "fit": stats,
                        "seconds": {"reconstruction": trained, "prediction": predicted},
                        "predictions": predictions,
                    }
                ),
            )
            done.append(member)
        return {"reconstructed": done}

    def _member_predictions(self, member):
        path = self._prediction_path(member)
        if not path.exists():
            return None
        return json.loads(gzip.decompress(path.read_bytes()))

    # --- 4. evaluate ------------------------------------------------------------------------

    def _missing(self):
        contract = self.contract()
        refs = self.reference_map()
        jobs = ev.decision_cases(contract)
        unsolved = [j["case_id"] for j in jobs if j["case_id"] not in refs]
        members = [m for m, *_ in pn.members() if not self._prediction_path(m).exists()]
        return unsolved, members

    def evaluate(self):
        unsolved, members = self._missing()
        if unsolved or members:
            raise ExperimentError(
                "prerequisites_missing",
                f"{len(unsolved)} decision references, {len(members)} members",
            )
        from ..compile import compile_recipe

        bundles = {}
        for member, _family, strategy, seed in pn.members():
            bundle = self._member_predictions(member)
            _, recipe = compile_recipe(strategy)
            if (
                bundle["recipe_digest"] != recipe.recipe_digest
                or bundle["seed"] != seed
            ):
                # Retained predictions from another recipe or seed are never
                # silently reinterpreted under this contract.
                raise ExperimentError("artifact_mismatch", member)
            bundles[member] = bundle
        results = evaluate(
            self.contract(), self.reference_map(), bundles, self.repository
        )
        results["manifest_digest"] = ev.digest(self.manifest())
        out = self._dir("results")
        (out / "results.json").write_bytes(_json_bytes(results))
        (out / "results.json").chmod(0o600)
        from .report import render

        (out / "report.md").write_text(render(results))
        (out / "report.md").chmod(0o600)
        return results

    # --- run / status / export -------------------------------------------------------------

    def run(self, *, contract_path=None, workers=1, backend=None, solver=None):
        with self.lock():
            if contract_path is not None or not self.manifest_path.exists():
                self.freeze(contract_path)
            refs = self.references(workers=workers, solver=solver)
            panel = self.panel(backend=backend)
            unsolved, members = self._missing()
            if unsolved or members:
                return {
                    "status": "INCOMPLETE",
                    "references": refs,
                    "panel": panel,
                    "missing": {"references": len(unsolved), "members": members},
                }
            results = self.evaluate()
            return {"status": "EVALUATED", "summary": results["summary"]}

    def status(self):
        if not self.manifest_path.exists():
            return {"status": "NOT_FROZEN"}
        manifest = self.manifest()
        refs = self.reference_map()
        records = self._reference_records()
        unsolved, members = self._missing()
        seconds = {"reference_solves": 0.0, "reconstruction": 0.0, "prediction": 0.0}
        for record in records:
            seconds["reference_solves"] += float(record.get("wall_s") or 0.0)
        for member, *_ in pn.members():
            path = self._prediction_path(member)
            if path.exists():
                meta = json.loads(gzip.decompress(path.read_bytes()))["seconds"]
                seconds["reconstruction"] += meta["reconstruction"]
                seconds["prediction"] += meta["prediction"]
        counts = {}
        for record in refs.values():
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        results = self.root / "results" / "results.json"
        return {
            "status": (
                "EVALUATED"
                if results.exists() and not (unsolved or members)
                else "IN_PROGRESS"
            ),
            "challenge": manifest["contract"]["challenge"],
            "contract": {
                "id": manifest["contract"]["contract_id"],
                "version": manifest["contract"]["version"],
                "digest": manifest["contract_digest"],
            },
            "candidates": len(manifest["candidates"]),
            "decision_cases": manifest["decision_cases"],
            "references": {
                "terminal": len(refs),
                "by_status": counts,
                "missing": len(unsolved),
                "infra_attempts": sum(
                    1 for r in records if r.get("status") == "FAILED_INFRA"
                ),
            },
            "panel": {
                "members": len(pn.members()),
                "missing": members,
            },
            "resources_seconds": seconds,
            "paid_resources": "none (local CPU)",
        }

    def export(self, out):
        results = self.root / "results"
        if not (results / "results.json").exists():
            raise ExperimentError("not_evaluated")
        out = Path(out)
        out.mkdir(mode=0o700, parents=True, exist_ok=False)
        for name in ("results.json", "report.md"):
            write_once(out / name, (results / name).read_bytes())
        write_once(out / "manifest.json", self.manifest_path.read_bytes())
        return {
            "directory": str(out),
            "files": ["manifest.json", "results.json", "report.md"],
        }


# --- the evaluation, a pure function of its inputs -------------------------------------------


def _quantities(contract, predictions, scenario, candidates):
    """A member's predicted decision quantities, from predictions only."""
    out = {}
    for candidate in candidates:
        for index in range(len(scenario["conditions"])):
            case_id = f"ev1:{scenario['id']}:{candidate['id']}:{index}"
            outputs = predictions.get(case_id)
            if outputs is None:
                return None
            out[(candidate["id"], index)] = d.measure(contract, outputs)
    return out


def _decide(contract, scenario, candidates, predictions, reference, baseline_id):
    started = time.monotonic()
    quantities = _quantities(contract, predictions, scenario, candidates)
    if quantities is None:
        best = d.best_in_set(candidates, reference)
        loss = contract["mistake_costs"]["missed_opportunity"] if best else 0.0
        return {
            "kind": "MODEL_OUTPUT_MISSING",
            "selected": None,
            "best_in_tested_set": best,
            "decision_loss": loss,
        }, None
    predicted = d.assess_predicted(contract, scenario, candidates, quantities)
    selection = d.select(candidates, predicted)
    seconds = time.monotonic() - started
    result = d.outcome(contract, candidates, selection, reference, baseline_id)
    result["selection_seconds"] = seconds
    return result, d.classification(candidates, predicted, reference)


def _mean(values):
    values = [v for v in values if v is not None]
    return None if not values else sum(values) / len(values)


def evaluate(
    contract, reference_records, member_predictions, repository, controls=True
):
    """Every member's decisions, every rule's scores, and their comparison."""
    candidates = ev.candidates(contract)
    baseline_id = ev.candidate_id(contract["baseline"]["protocol"])
    store, scoring_ids, scoring_identity = sc.scoring_set(repository)
    predictions = {
        member: bundle["predictions"] for member, bundle in member_predictions.items()
    }
    kinds = {member: "RECONSTRUCTED" for member in predictions}
    if controls:
        decision_refs = {
            c: r for c, r in reference_records.items() if r.get("status") == "OK"
        }
        for control in pn.CONTROLS:
            name = f"control-{control}"
            predictions[name] = {
                **pn.control_predictions(control, store.refs),
                **pn.control_predictions(control, decision_refs),
            }
            kinds[name] = "SYNTHETIC_CONTROL"
    decisions = {member: {} for member in predictions}
    references = {}
    for scenario in ev.scenarios(contract):
        refs = {}
        for candidate in candidates:
            for index in range(len(scenario["conditions"])):
                case_id = f"ev1:{scenario['id']}:{candidate['id']}:{index}"
                if case_id in reference_records:
                    refs[(candidate["id"], index)] = reference_records[case_id]
        reference = d.assess_reference(contract, scenario, candidates, refs)
        references[scenario["id"]] = {
            "split": scenario["split"],
            "best_in_tested_set": d.best_in_set(candidates, reference),
            "baseline_status": reference[baseline_id]["status"],
            "status_counts": {
                s: sum(1 for c in candidates if reference[c["id"]]["status"] == s)
                for s in (d.FEASIBLE, d.INFEASIBLE, d.UNRESOLVED, d.UNAVAILABLE)
            },
        }
        for member, member_preds in predictions.items():
            outcome, agreement = _decide(
                contract, scenario, candidates, member_preds, reference, baseline_id
            )
            decisions[member][scenario["id"]] = {
                "split": scenario["split"],
                "outcome": outcome,
                "agreement": agreement,
            }
    components = {
        member: sc.components(preds, scoring_ids, store)
        for member, preds in predictions.items()
    }
    scores = {member: sc.rule_scores(contract, c) for member, c in components.items()}
    rules = [sc.CONTROL] + [
        p["id"] for p in contract["scoring_candidates"]["weight_profiles"]
    ]

    def loss(member, split):
        return _mean(
            v["outcome"]["decision_loss"]
            for v in decisions[member].values()
            if v["split"] == split
        )

    def agreement(rule, split, pool):
        pairs = []
        for member in pool:
            score, member_loss = scores[member][rule], loss(member, split)
            if isinstance(score, str) or member_loss is None:
                return None
            pairs.append((float("-inf") if score is None else score, -member_loss))
        if len(pairs) < 3:
            return None
        return d.kendall_tau_b([p[0] for p in pairs], [p[1] for p in pairs])

    reconstructed = sorted(m for m in predictions if kinds[m] == "RECONSTRUCTED")
    everyone = sorted(predictions)
    comparison = {}
    for rule in rules:
        measurable = not any(isinstance(scores[m][rule], str) for m in everyone)
        comparison[rule] = {
            "measurable": measurable,
            "tau_development": (
                agreement(rule, "development", reconstructed) if measurable else None
            ),
            "tau_verification": (
                agreement(rule, "verification", reconstructed) if measurable else None
            ),
            "tau_development_with_controls": (
                agreement(rule, "development", everyone) if measurable else None
            ),
            "not_measurable": sorted(
                {scores[m][rule] for m in everyone if isinstance(scores[m][rule], str)}
            ),
        }

    candidates_for_choice = [
        r for r in rules if comparison[r]["tau_development"] is not None
    ]
    chosen = max(
        candidates_for_choice,
        key=lambda r: (comparison[r]["tau_development"], r == sc.CONTROL),
        default=None,
    )
    stability = _stability(
        contract, predictions, scoring_ids, store, rules, reconstructed, scores
    )
    families = {}
    for member in reconstructed:
        family = member.rsplit("-s", 1)[0]
        families.setdefault(family, []).append(member)
    seed_variation = {
        family: {
            split: {
                "mean": _mean(loss(m, split) for m in members),
                "min": min(
                    (loss(m, split) for m in members if loss(m, split) is not None),
                    default=None,
                ),
                "max": max(
                    (loss(m, split) for m in members if loss(m, split) is not None),
                    default=None,
                ),
                "seeds": len(members),
            }
            for split in ("development", "verification")
        }
        for family, members in families.items()
    }
    summary = {
        "question": contract["acceptance"]["success_condition"],
        "chosen_rule_on_development": chosen,
        "chosen_rule_tau_verification": (
            None if chosen is None else comparison[chosen]["tau_verification"]
        ),
        "control_tau_verification": comparison[sc.CONTROL]["tau_verification"],
        "members": {
            m: {
                "kind": kinds[m],
                "loss_development": loss(m, "development"),
                "loss_verification": loss(m, "verification"),
                "eligible": components[m]["eligible"],
            }
            for m in everyone
        },
    }
    return {
        "schema": RESULT_SCHEMA,
        "contract_digest": ev.digest(contract),
        "scoring_set": scoring_identity,
        "references": references,
        "decisions": decisions,
        "components": components,
        "rule_scores": scores,
        "comparison": comparison,
        "stability": stability,
        "seed_variation": seed_variation,
        "summary": summary,
        "claims": {
            "best_in_tested_set_is_global_optimum": False,
            "optimal_weight_ratio_claimed": False,
            "testnet_rule_changed": False,
            "evidence_class": "PUBLIC_SYNTHETIC_DEVELOPMENT",
        },
    }


def _stability(contract, predictions, scoring_ids, store, rules, reconstructed, scores):
    """Leave-one-batch-out: does each rule's top reconstructed member change?"""
    groups = sc.batches(scoring_ids)
    partial = {}
    for name, ids in groups.items():
        excluded = set(ids)
        kept = [c for c in scoring_ids if c not in excluded]
        partial[name] = {
            m: sc.rule_scores(contract, sc.components(predictions[m], kept, store))
            for m in reconstructed
        }

    def top(rule, table):
        return min(
            reconstructed,
            key=lambda m: (table[m][rule] is None, -(table[m][rule] or 0.0), m),
        )

    out = {}
    for rule in rules:
        if any(isinstance(scores[m][rule], str) for m in reconstructed):
            out[rule] = None
            continue
        full_top = top(rule, scores)
        same = sum(top(rule, table) == full_top for table in partial.values())
        out[rule] = {
            "top_member": full_top,
            "leave_one_batch_out_same_top": same,
            "batches": len(groups),
        }
    return out
