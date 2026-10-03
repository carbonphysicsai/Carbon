"""Equal-query design-search experiments for any Challenge (handoff §11-12).

A proposed search method is compared with the Challenge's fixed baseline at
equal query and verification budgets, on development models only, under one
frozen configuration for the whole panel.

- **The adapter** (`SearchAdapter`) is everything Challenge-specific: its
  design and condition variables, its commitment engine (request, budgeted
  oracle, commitment, verification), its fixed baseline, and the code the
  freeze pins. Battery's is `carbon/battery/value/design_search_adapter.py`,
  over `search_commitment`. The adapter refuses non-development material and
  any protected condition (battery: EV4's).
- **The neutral request** names designs and conditions as variable maps, the
  mode, the model identity, the budgets, the method identity and the seed
  policy. The adapter turns it into its own engine request.
- **The freeze manifest** (`freeze`) pins, before any comparison: the code
  and dependency digests, the decision contract, the mode, the design and
  condition sets, the initialization and tie policy, the budgets, the
  stopping and failure handling, the seed policy, the reference allocation,
  every method's configuration and the panel. `pilot` refuses to run if any
  pinned code changed. No member gets its own configuration.
- **Commitment before reference access** is the adapter's engine's rule
  (battery: `search_commitment.verify` accepts only a commitment written
  before it calls the reference).

Nothing here chooses a K, a grid, a policy or a winner, and nothing replaces
the declared baseline. Equal-time and adaptive searches are separate
experiments.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import methods as m

REQUEST_SCHEMA = "carbon.design-search.neutral-request.v1"
FREEZE_SCHEMA = "carbon.design-search.freeze.v1"
PILOT_SCHEMA = "carbon.design-search.pilot.v1"
BASELINE = "fixed_grid"
NEUTRAL_CODE = (
    "carbon/design_search/methods.py",
    "carbon/design_search/experiment.py",
)
DEPENDENCIES = ("uv.lock",)


class ExperimentError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _file(repository, relative):
    path = Path(repository) / relative
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class SearchAdapter:
    """What one Challenge supplies to the neutral design search."""

    challenge: str
    design_variables: tuple
    condition_variables: tuple
    contract_digest: str
    modes: tuple
    #: (neutral request) -> (engine request, space)
    request: Callable
    #: (engine request, space, infer) -> oracle (.query, .used, .budget, .elapsed)
    oracle: Callable
    #: (oracle, engine request, space) -> selections: the declared baseline
    baseline: Callable
    #: (engine request, space) -> methods.View
    view: Callable
    #: (engine request, selections, oracle, directory) -> commitment
    commit: Callable
    #: (commitment, reference) -> a neutral result
    verify: Callable
    #: Repository files the freeze pins for this Challenge.
    code_paths: tuple
    tie_policy: str


def neutral_request(
    adapter,
    *,
    mode,
    model,
    designs,
    conditions,
    query_budget,
    verification_budget,
    method,
    seed_policy,
):
    """A versioned neutral request; variable names are the adapter's."""
    if mode not in adapter.modes:
        raise ExperimentError("mode_not_served", str(mode))
    for rows, names in (
        (designs, adapter.design_variables),
        (conditions, adapter.condition_variables),
    ):
        if not rows or any(
            type(r) is not dict or tuple(sorted(r)) != tuple(sorted(names))
            for r in rows
        ):
            raise ExperimentError("variables_are_the_adapters", ", ".join(names))
    body = {
        "schema": REQUEST_SCHEMA,
        "challenge": adapter.challenge,
        "material": "DEVELOPMENT",
        "mode": mode,
        "model": dict(model),
        "designs": [dict(d) for d in designs],
        "conditions": [dict(c) for c in conditions],
        "query_budget": query_budget,
        "verification_budget": verification_budget,
        "method": dict(method),
        "seed_policy": seed_policy,
    }
    return {**body, "request_digest": digest(body)}


def code_digests(adapter, repository):
    paths = (*NEUTRAL_CODE, *adapter.code_paths)
    code = {p: _file(repository, p) for p in paths if (Path(repository) / p).is_file()}
    missing = [p for p in paths if p not in code]
    if missing:
        raise ExperimentError("frozen_code_missing", ", ".join(missing))
    dependencies = {
        p: _file(repository, p)
        for p in DEPENDENCIES
        if (Path(repository) / p).is_file()
    }
    return code, dependencies


def freeze(
    adapter,
    *,
    repository,
    mode,
    designs,
    conditions,
    query_budget,
    verification_budget,
    seed_policy,
    panel,
    proposals,
):
    """The freeze manifest, written before any comparison.

    `panel` lists development model identities ({member, recipe_digest, seed,
    material}); `proposals` maps a name to a checked method proposal
    ({method, parameters})."""
    if not panel or any(
        set(p) != {"member", "recipe_digest", "seed", "material"}
        or p["material"] != "DEVELOPMENT"
        for p in panel
    ):
        raise ExperimentError("panel_is_development_models_only")
    if len({p["member"] for p in panel}) != len(panel):
        raise ExperimentError("panel_members_are_unique")
    if BASELINE in proposals:
        raise ExperimentError("the_baseline_is_declared_not_proposed")
    configured = {BASELINE: {"method": BASELINE, "parameters": {}}}
    for name, proposal in sorted(proposals.items()):
        m.check(
            proposal["method"],
            proposal["parameters"],
            mode=mode,
            conditions=len(conditions),
        )
        configured[name] = {
            "method": proposal["method"],
            "parameters": dict(proposal["parameters"]),
        }
    for spec in configured.values():
        spec["configuration_digest"] = digest(
            {"method": spec["method"], "parameters": spec["parameters"]}
        )
    code, dependencies = code_digests(adapter, repository)
    document = {
        "schema": FREEZE_SCHEMA,
        "challenge": adapter.challenge,
        "decision_contract": adapter.contract_digest,
        "material": "DEVELOPMENT",
        "mode": mode,
        "designs": [dict(d) for d in designs],
        "conditions": [dict(c) for c in conditions],
        "objective_and_constraints": "the decision contract's, pinned above",
        "initialization": "deterministic; no method draws a random number",
        "tie_policy": adapter.tie_policy,
        "query_budget": query_budget,
        "verification_budget": verification_budget,
        "stopping": (
            "a method stops by its own rule or when its next query would exceed "
            "the query budget, and selects from what it queried"
        ),
        "failure_handling": (
            "an unavailable or unresolved reference result stays exactly that; "
            "a model or oracle failure ends that run and is recorded"
        ),
        "seed_policy": seed_policy,
        "reference_allocation": (
            "the verification budget per method and member, committed before any "
            "reference access"
        ),
        "methods": configured,
        "panel": [dict(p) for p in panel],
        "code": code,
        "dependencies": dependencies,
    }
    return {**document, "freeze_digest": digest(document)}


def check_frozen(manifest, adapter, repository):
    body = {k: v for k, v in manifest.items() if k != "freeze_digest"}
    if digest(body) != manifest.get("freeze_digest"):
        raise ExperimentError("freeze_manifest_altered")
    if manifest["challenge"] != adapter.challenge:
        raise ExperimentError("freeze_is_for_another_challenge")
    code, dependencies = code_digests(adapter, repository)
    for kind, now in (("code", code), ("dependencies", dependencies)):
        changed = sorted(
            p
            for p in set(now) | set(manifest[kind])
            if now.get(p) != manifest[kind].get(p)
        )
        if changed:
            raise ExperimentError("frozen_" + kind + "_changed", ", ".join(changed))


def pilot(manifest, adapter, *, repository, models, reference, directory):
    """Every frozen method on every panel member, at equal budgets.

    `models` maps each frozen member to its prediction function; there is no
    per-member configuration to pass."""
    check_frozen(manifest, adapter, repository)
    panel = manifest["panel"]
    if set(models) != {p["member"] for p in panel}:
        raise ExperimentError("models_are_exactly_the_frozen_panel")
    code_digest = digest(manifest["code"])
    members = {}
    for identity in panel:
        member = identity["member"]
        members[member] = {}
        for name, spec in sorted(manifest["methods"].items()):
            neutral = neutral_request(
                adapter,
                mode=manifest["mode"],
                model={k: identity[k] for k in ("member", "recipe_digest", "seed")},
                designs=manifest["designs"],
                conditions=manifest["conditions"],
                query_budget=manifest["query_budget"],
                verification_budget=manifest["verification_budget"],
                method={
                    "name": name,
                    "code_digest": code_digest,
                    "configuration_digest": spec["configuration_digest"],
                },
                seed_policy=manifest["seed_policy"],
            )
            engine, space = adapter.request(neutral)
            oracle = adapter.oracle(engine, space, models[member])
            start = time.perf_counter()
            if spec["method"] == BASELINE:
                selections = adapter.baseline(oracle, engine, space)
            else:
                selections = m.run(
                    spec["method"],
                    spec["parameters"],
                    adapter.view(engine, space),
                    oracle,
                )
            seconds = time.perf_counter() - start
            commitment = adapter.commit(
                engine, selections, oracle, Path(directory) / member / name
            )
            members[member][name] = {
                "request_digest": neutral["request_digest"],
                "queries_used": oracle.used,
                "query_budget": manifest["query_budget"],
                "search_seconds": seconds,
                "model_seconds": oracle.elapsed,
                "selections": selections,
                "result": adapter.verify(commitment, reference),
            }
    summary = {}
    for name in sorted(manifest["methods"]):
        rows = [members[p["member"]][name] for p in panel]
        verdicts = {}
        for row in rows:
            for verdict, count in row["result"]["verdicts"].items():
                verdicts[verdict] = verdicts.get(verdict, 0) + count
        summary[name] = {
            "queries_used": sum(r["queries_used"] for r in rows),
            "abstentions": sum(not r["selections"] for r in rows),
            "verdicts": verdicts,
            "search_seconds": sum(r["search_seconds"] for r in rows),
        }
    return {
        "schema": PILOT_SCHEMA,
        "challenge": adapter.challenge,
        "freeze_digest": manifest["freeze_digest"],
        "baseline": BASELINE,
        "basis": (
            "equal query and verification budgets; one frozen configuration for "
            "the whole panel; measured wall-clock runtime"
        ),
        "members": members,
        "summary": summary,
        "separate_experiments": (
            "equal-time budgets and adaptive agent search are separate experiments "
            "and are labelled as such when run"
        ),
        "claims": {
            "baseline_replaced": False,
            "best_design_is_global_optimum": False,
            "unresolved_counted_as_safe_or_unsafe": False,
            "qualification": False,
        },
    }
