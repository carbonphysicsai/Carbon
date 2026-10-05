"""Graphite phase 3 delivery: a PR-ready bundle, and Carbon's clean rebuild of it.

When a session's proposal clears the frozen rule against its baseline (an
`IMPROVEMENT` under the paired comparison), Carbon prepares what a pull
request would carry (plan §5 step 6): the recipe, the run logs, ablations, a
write-up and the rebuild instructions. The runner opens no pull request; the
bundle is a directory under the run's private root that a person may turn into
one.

- **Which proposal.** Carbon's rule chooses, not the agent: the eligible
  `IMPROVEMENT` with the lowest frozen-rule score; ties go to the earlier one.
  The agent's own selection, if it made one, is recorded beside it.
- **Ablations.** Each change from the baseline is removed one at a time (its
  field set back to the baseline's value, or dropped when the baseline does
  not set it), run on a pod and scored like any proposal, while the session
  has pods left. An ablation Carbon cannot rebuild is recorded as such. When
  the proposal changes the model family, a field-by-field ablation is
  undefined and none is run.
- **Next-level proposals.** The bundle carries the run's PROPOSED
  next-level records (`next-level-proposals.json`, GRAPHITE-D30), possibly
  none. They are requests for the owner: the rebuild ignores them and they
  widen nothing.
- **The write-up** is generated from the records, so it claims nothing the
  records do not show. No model writes it in phase 3.
- **Clean rebuild** (`clean_rebuild`) reads the bundle alone: every file is
  checked against the bundle manifest, the strategy is compiled afresh under
  the recorded construction contract, and every digest of what Carbon would
  build is compared with the bundle's. A difference is a `REBUILD_MISMATCH`
  finding. Numerical reproduction is not judged: its tolerance is
  science-reserved (plan §9) and stays `HUMAN_INPUT`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from . import experiment as ex

#: v2 adds `next-level-proposals.json` (GRAPHITE-D30).
BUNDLE_SCHEMA = "carbon.graphite.phase3.pr-bundle.v2"
REBUILD_SCHEMA = "carbon.graphite.phase3.clean-rebuild.v1"
FILES = (
    "strategy.json",
    "recipe.json",
    "score.json",
    "rows.json",
    "baseline.json",
    "ablations.json",
    "run-log.jsonl",
    "WRITEUP.md",
    "REBUILD.md",
    "next-level-proposals.json",
)
NUMERICAL = {
    "status": "NOT_JUDGED",
    "tolerance": "HUMAN_INPUT",
    "basis": (
        "Reconstruction tolerances are science-reserved (Graphite plan §9). "
        "The clean rebuild checks every digest of what Carbon builds; it does "
        "not judge a retrained model's numbers."
    ),
}


def ablations(baseline, proposal):
    """`(field, strategy)` for each change from the baseline, removed alone;
    `None` with a reason when the families differ."""
    if baseline.get("backbone") != proposal.get("backbone"):
        return None, "the proposal changes the model family"
    before = baseline.get("parameters") or {}
    after = proposal.get("parameters") or {}
    out = []
    for field in sorted(set(before) | set(after)):
        if before.get(field) == after.get(field) and (field in before) == (
            field in after
        ):
            continue
        ablated = copy.deepcopy(proposal)
        if field in before:
            ablated["parameters"][field] = before[field]
        else:
            del ablated["parameters"][field]
        out.append((field, ablated))
    return out, None


def best_improvement(records):
    found = [
        r
        for r in records
        if r["kind"] == "proposal"
        and r["status"] == "SCORED"
        and (r.get("against_baseline") or {}).get("outcome") == "IMPROVEMENT"
        and r["frozen_rule"]["eligible"]
    ]
    if not found:
        return None
    return min(found, key=lambda r: (r["frozen_rule"]["score"], r["ordinal"]))


def _strategy(experiment, pid):
    folder = experiment.root / "proposals" / pid
    return json.loads((folder / "intent.json").read_bytes())["strategy"]


def deliver(experiment, directory, *, selection=None, proposals=()):
    """Ablate and bundle the session's best improvement; returns the outcome.

    Idempotent: every ablation is an experiment record and every bundle file
    is written once."""
    record = best_improvement(experiment.records("proposal"))
    if record is None:
        return {"status": "NO_IMPROVEMENT", "bundle": None}
    pid = record["proposal_id"]
    proposal = _strategy(experiment, pid)
    baseline = _strategy(experiment, "baseline")
    changes, undefined = ablations(baseline, proposal)
    scorer = experiment._scorer()
    rows = experiment.rows(pid)
    results = []
    for index, (field, strategy) in enumerate(changes or ()):
        child = f"a-{pid[2:]}-{index:02d}"
        if experiment.record(child) is None and experiment.pods_left() <= 0:
            results.append({"field": field, "status": "NOT_RUN_NO_PODS_LEFT"})
            continue
        result = experiment.run(
            child,
            "ablation",
            strategy,
            why={"ablation_of": pid, "field": field},
            parent=pid,
        )
        entry = {
            "field": field,
            "proposal_id": child,
            "status": result["status"],
            "strategy_digest": result["strategy_digest"],
        }
        if result["status"] == "SCORED":
            against = scorer.compare(
                rows, experiment.rows(child), bool(result["frozen_rule"]["eligible"])
            )
            entry["frozen_rule"] = result["frozen_rule"]
            entry["against_proposal"] = {
                k: against.get(k) for k in ("outcome", "reason", "mean_delta", "ci")
            }
            entry["against_baseline"] = result.get("against_baseline")
        results.append(entry)
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    expected = json.loads(
        (experiment.root / "proposals" / pid / "expected.json").read_bytes()
    )
    # The session's baseline: its retry when the first did not score
    # (`baseline_retry`); the run log carries both.
    baseline_id = experiment.baseline_id()
    baseline_record = experiment.record(baseline_id)
    involved = {pid, "baseline", baseline_id} | {r.get("proposal_id") for r in results}
    # Kept pod logs are operator evidence only (`pod_logs`): not even their
    # index rows enter a bundle.
    log = [
        row
        for row in experiment.ledger.rows()
        if row.get("proposal") in involved and row.get("event") != "pod_logs_kept"
    ]
    bodies = {
        "strategy.json": canonical(proposal),
        "recipe.json": canonical(expected),
        "score.json": canonical(record),
        "rows.json": canonical(rows),
        "baseline.json": canonical({"strategy": baseline, "result": baseline_record}),
        "ablations.json": canonical({"undefined": undefined, "ablations": results}),
        "run-log.jsonl": b"".join(canonical(row) + b"\n" for row in log),
        "WRITEUP.md": writeup(
            record, baseline_record, results, undefined, selection
        ).encode(),
        "REBUILD.md": rebuild_text(pid).encode(),
        "next-level-proposals.json": canonical(
            {
                "proposals": list(proposals),
                "note": (
                    "PROPOSED next-level records for the owner; none widens the "
                    "construction contract or affects a score"
                ),
            }
        ),
    }
    for name in FILES:
        write_once(folder / name, bodies[name])
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "proposal_id": pid,
        "run_id": experiment.run_id,
        "files": {name: digest(bodies[name]) for name in FILES},
        "contract_digest": expected["contract_digest"],
        "record_sequence": expected["record_sequence"],
        "recipe_digest": expected["recipe_digest"],
        "authority_granted": False,
        "official_eligible": False,
    }
    write_once(folder / "manifest.json", canonical(manifest))
    check = clean_rebuild(folder, repository=experiment.repository)
    if check["status"] != "REBUILT":
        check["finding"] = experiment._finding(
            "REBUILD_MISMATCH", pid, {"clean_rebuild": check["differences"]}
        )
    return {
        "status": "BUNDLED",
        "proposal_id": pid,
        "bundle": str(folder),
        "manifest_digest": digest(canonical(manifest)),
        "clean_rebuild": check,
        "next_level_proposals": [p["proposal_id"] for p in proposals],
    }


def clean_rebuild(directory, *, repository=ex.REPOSITORY):
    """Rebuild a bundle from its files alone. Never reads the run that made it."""
    folder = Path(directory)
    differences = []
    try:
        manifest = json.loads((folder / "manifest.json").read_bytes())
    except (OSError, ValueError):
        return _rebuild_result(["manifest_unreadable"], None)
    present = sorted(
        p.name for p in folder.iterdir() if p.is_file() and p.name != "manifest.json"
    )
    if manifest.get("schema") != BUNDLE_SCHEMA:
        differences.append("manifest_schema")
    if present != sorted(manifest.get("files") or {}):
        differences.append("bundle_files_differ_from_manifest")
    for name, expected in sorted((manifest.get("files") or {}).items()):
        path = folder / name
        if path.is_symlink() or not path.is_file():
            differences.append("missing:" + name)
        elif digest(path.read_bytes()) != expected:
            differences.append("digest:" + name)
    if differences:
        return _rebuild_result(differences, manifest)
    strategy = json.loads((folder / "strategy.json").read_bytes())
    recipe = json.loads((folder / "recipe.json").read_bytes())
    score = json.loads((folder / "score.json").read_bytes())
    variant = None
    if "development" in recipe:
        # Built at a development level: rebuilt through the registered
        # variant its recipe names (GRAPHITE-DEV-VARIANTS-01), never Level 0.
        from carbon.reconstruction import development_variants

        try:
            variant = development_variants.registered(
                (recipe["development"] or {}).get("variant_digest")
            )
        except (development_variants.VariantRefused, AttributeError) as refused:
            return _rebuild_result(["not_rebuildable:" + str(refused)], manifest)
    try:
        level = {} if variant is None else {"variant": variant}
        rebuilt = ex.admit(strategy, recipe.get("seed"), repository, **level)
    except (ex.Unrebuildable, ex.NotServed, ValueError, TypeError) as refused:
        return _rebuild_result(["not_rebuildable:" + str(refused)], manifest)
    differences = ex.rebuild_differences(recipe, rebuilt) + ex.development_differences(
        recipe, rebuilt
    )
    for name, value in (
        ("score_recipe_digest", score.get("recipe_digest")),
        ("manifest_recipe_digest", manifest.get("recipe_digest")),
    ):
        if value != rebuilt["recipe_digest"]:
            differences.append(name)
    if manifest.get("contract_digest") != rebuilt["contract_digest"]:
        differences.append("manifest_contract_digest")
    return _rebuild_result(differences, manifest, rebuilt)


def _rebuild_result(differences, manifest, rebuilt=None):
    return {
        "schema": REBUILD_SCHEMA,
        "status": "REBUILT" if not differences else "REBUILD_MISMATCH",
        "differences": differences,
        "proposal_id": (manifest or {}).get("proposal_id"),
        "recipe_digest": None if rebuilt is None else rebuilt["recipe_digest"],
        "numerical": NUMERICAL,
    }


def _number(value):
    return "not stated" if value is None else f"{value:.6g}"


def writeup(record, baseline, ablated, undefined, selection):
    rule = record["frozen_rule"]
    against = record["against_baseline"]
    # The Challenge's own rule identity: never another Challenge's wording.
    identity = record.get("rule") or {}
    lines = [
        f"# Graphite phase 3 proposal {record['proposal_id']}",
        "",
        "Internal DEVELOPMENT evidence (GRAPHITE-01 phase 3, Constructor Level 0).",
        "It is not an exam result, a qualification or a claim of physical",
        "validity. Graphite proposed this recipe; Carbon ran, scored and rebuilt it.",
        "",
        "## What changed",
        "",
        "The recipe in `strategy.json`, compiled by Carbon to `recipe.json`",
        f"(recipe digest `{record['recipe_digest']}`), against the baseline in",
        "`baseline.json`.",
        "",
        "## Evidence",
        "",
        (
            "Scored by the Challenge's frozen practice rule"
            f" (`{identity.get('rule', 'not stated')}`) on its"
        ),
        "public PRACTICE cases (adaptively seen development feedback):",
        "",
        (
            f"- eligible: {rule['eligible']}; score {_number(rule['score'])};"
            f" important-region score {_number(rule.get('important_score'))}"
        ),
        (
            f"- baseline: eligible {baseline['frozen_rule']['eligible']}; score"
            f" {_number(baseline['frozen_rule']['score'])}"
        ),
        (
            "- comparison with the baseline under the rule's registered"
            f" comparison: {against['outcome']}, {against['reason']}"
        ),
        "",
        "## Ablations",
        "",
    ]
    if undefined:
        lines.append(f"None run: {undefined}.")
    elif not ablated:
        lines.append("None: the proposal makes no change from the baseline.")
    for entry in ablated:
        outcome = (entry.get("against_proposal") or {}).get("outcome")
        lines.append(
            f"- `{entry['field']}` removed: {entry['status']}"
            + (f"; against the proposal: {outcome}" if outcome else "")
        )
    lines += [
        "",
        "## Limits",
        "",
        "- Development feedback on public cases the session saw; held-out",
        "  confirmation is a later, pre-registered step (plan §6).",
        "- Selected as the best of the session's proposals, so the comparison",
        "  carries selection bias.",
        "- The clean rebuild checks every digest of what Carbon builds; numerical",
        "  reproduction has no registered tolerance (HUMAN_INPUT).",
    ]
    if selection is not None:
        lines += [
            "",
            (
                "The agent's own selection, recorded as data:"
                f" strategy digest `{selection.get('strategy_digest')}`."
            ),
        ]
    lines += ["", "## Rebuild", "", "See `REBUILD.md`.", ""]
    return "\n".join(lines)


def rebuild_text(pid):
    return "\n".join(
        [
            f"# Rebuilding proposal {pid} without the agent",
            "",
            "From a Carbon checkout at any commit whose construction contract for",
            "the bundle's Challenge is the one `manifest.json` names:",
            "",
            "    python -m carbon.agent_campaign.graphite.phase3 rebuild --bundle DIR",
            "",
            "It checks every bundle file against `manifest.json`, compiles",
            "`strategy.json` afresh under the recorded contract, and compares every",
            "digest of the recipe, the staged files and the program with",
            "`recipe.json`. The practice program and its staged files are then",
            "exactly those a pod ran (`pod_phase.built_record`).",
            "",
        ]
    )
