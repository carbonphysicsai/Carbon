"""A construction level's compile and Level 4 checks, in a process of its own.

LAUNCHPAD-LEVELS-01 S2 and S3 (OWNER-LADDER-THROUGH-LAUNCHPAD-01). A
Launchpad campaign launched at a construction level N >= 1 compiles its
recipes with `development_variants.compile_development` under that level's
registered variant. No miner surface may import the variant module
(`tests/invariants/test_development_variants_unreachable.py`), so the
Launchpad never does: its client (`carbon.development_session.
construction_level`) runs this module as a child process, as the campaign
runs practice in a carrier, and reads back one JSON answer.

This module belongs to the development door, beside `carbon.battery.
dev_submit`: nothing a miner surface imports may import it. It reads one
JSON request on standard input and writes one JSON answer on standard
output:

- `{"op": "compile", "challenge", "level", "arm", "strategy"}`: the level's
  current registered variant (`variant`), then `compile_development`. The
  answer names the variant, its digest, the fields it widens, the base
  construction's strategy hash and recipe digest, and the development
  binding. A refusal is `{"ok": false, "code", "issues"}` with the variant
  module's or the base compiler's own code.
- `{"op": "level4", ..., "directory"}`: a Level 4 submission lowered on the
  miner's machine, checked against the Level 4 variant before freeze
  (`level4`).

Nothing here chooses a bound: a Level 4 size bound is the variant's pinned
`caps.document_bytes`, and while it is not a positive integer the check is
refused `level4_size_bound_not_set`.
"""

from __future__ import annotations

import json
import sys


def _battery_level4():
    from carbon.battery import level4

    return level4


#: Each Challenge's Level 4 adapter, loaded by a static import when asked:
#: the module that gives a recipe's Level 4 interface
#: (`interface(strategy).digest()`) and its training batch
#: (`training_batch(strategy)`). Development only.
LEVEL4_ADAPTERS = {
    "battery-fastcharge-ageing-development-v1": _battery_level4,
}

NOT_REGISTERED = "level_not_registered"
SIZE_BOUND_NOT_SET = "level4_size_bound_not_set"
NOT_LEVEL4 = "level4_needs_a_level4_variant"
ADAPTER_MISSING = "level4_adapter_missing"
ALLOWLIST_MISMATCH = "level4_allowlist_mismatch"
SUBMISSION_NOT_IN_STRATEGY = "level4_submission_not_in_strategy"
INTERFACE_MISMATCH = "level4_interface_mismatch"
BATCH_MISMATCH = "level4_batch_mismatch"
SUBMISSION_REFUSED = "level4_submission_refused"
STRATEGY_REFUSED = "level_strategy_refused"


class Refused(Exception):
    def __init__(self, code, issues=()):
        super().__init__(code)
        self.code, self.issues = code, list(issues)


def _variant(request):
    from carbon.reconstruction import development_variants as dv

    try:
        return dv.variant(request["challenge"], request["level"], request.get("arm"))
    except dv.VariantRefused as refused:
        raise Refused(NOT_REGISTERED, [{"code": refused.code}]) from None


def _issues(error):
    issues = getattr(error, "issues", None)
    if issues is None:
        issues = getattr(getattr(error, "rejected", None), "issues", ())
    out = []
    for issue in issues or ():
        if type(issue) is tuple:
            out.append({"code": str(issue[0]), "path": str(issue[1])})
        else:
            out.append(
                {
                    "code": str(getattr(issue, "code", issue)),
                    "path": str(getattr(issue, "path", "")),
                }
            )
    return out


def compile_level(request):
    """The level's compile of `strategy`, as plain JSON."""
    from carbon.reconstruction import development_variants as dv

    found = _variant(request)
    try:
        compiled = dv.compile_development(request["strategy"], found)
    except dv.VariantRefused as refused:
        raise Refused(STRATEGY_REFUSED, [{"code": refused.code}, *_issues(refused)])
    except ValueError as refused:  # SubmissionRefused, RecipeRejected
        raise Refused(
            STRATEGY_REFUSED,
            [{"code": getattr(refused, "code", type(refused).__name__)}]
            + _issues(refused),
        ) from None
    plan = compiled.compiled.construction_plan
    return {
        "ok": True,
        "challenge": found.challenge,
        "level": found.level,
        "arm": request.get("arm"),
        "variant": found.version,
        "variant_digest": found.digest,
        "base_contract_digest": compiled.contract_digest,
        "widened_fields": sorted(found.fields()),
        "strategy_hash": plan.strategy_hash.value,
        "construction_plan_digest": plan.to_ref().content_digest,
        "commitment_strategy_hash": compiled.construction.strategy_hash,
        "recipe_digest": compiled.construction.recipe_digest,
        "development": compiled.development,
    }


def _level4_bounds(found):
    """`(allowlist pin, max_bytes)` from the Level 4 variant's one widening."""
    (widened,) = found.widened
    bounds = json.loads(widened.bounds_json)
    caps = bounds.get("caps")
    size = caps.get("document_bytes") if type(caps) is dict else None
    if type(size) is not int or type(size) is bool or size <= 0:
        raise Refused(SIZE_BOUND_NOT_SET)
    return bounds["allowlist"], size, widened.name


def level4(request):
    """A lowered Level 4 submission, checked before freeze: the variant's
    pinned allowlist and size bound, the strategy's Level 4 field naming the
    submission, `submission.verify` against the Challenge and the recipe's
    interface, and the forward graph's batch against the recipe's. Answers
    the staging envelope (`staging.envelope`), the bytes as read."""
    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import graph, staging, submission, validate

    found = _variant(request)
    if found.level != 4:
        raise Refused(NOT_LEVEL4)
    pin, max_bytes, field = _level4_bounds(found)
    strategy = request["strategy"]
    try:
        digest, raw_manifest, files = staging.read_directory(request["directory"])
    except graph.GraphRefused as refused:
        raise Refused(SUBMISSION_REFUSED, [{"code": refused.code}]) from None
    except OSError:
        raise Refused(SUBMISSION_REFUSED, [{"code": "directory_unreadable"}]) from None
    parameters = strategy.get("parameters") if type(strategy) is dict else None
    if type(parameters) is not dict or parameters.get(field) != digest:
        raise Refused(SUBMISSION_NOT_IN_STRATEGY, [{"code": field}])
    loaded = allowlist_module.load()
    if {"version": loaded.version, "digest": loaded.digest} != pin:
        raise Refused(ALLOWLIST_MISMATCH)
    load = LEVEL4_ADAPTERS.get(found.challenge)
    if load is None:
        raise Refused(ADAPTER_MISSING)
    adapter = load()
    base = {
        **strategy,
        "parameters": {k: v for k, v in parameters.items() if k != field},
    }
    interface = adapter.interface(base)
    try:
        _manifest, parsed = submission.verify(
            raw_manifest,
            files,
            allowlist=loaded,
            challenge=found.challenge,
            interface=interface.digest(),
            max_bytes=max_bytes,
        )
    except graph.GraphRefused as refused:
        code = INTERFACE_MISMATCH if refused.code == "submission_interface" else None
        raise Refused(code or SUBMISSION_REFUSED, [{"code": refused.code}]) from None
    try:
        declared = validate.check_interface(parsed["forward"], interface)
    except graph.GraphRefused as refused:
        raise Refused(INTERFACE_MISMATCH, [{"code": refused.code}]) from None
    if declared != adapter.training_batch(base):
        raise Refused(BATCH_MISMATCH)
    return {
        "ok": True,
        "variant": found.version,
        "variant_digest": found.digest,
        "submission": digest,
        "max_bytes": max_bytes,
        "envelope": staging.envelope(raw_manifest, files),
    }


OPERATIONS = {"compile": compile_level, "level4": level4}


def answer(request):
    if type(request) is not dict or request.get("op") not in OPERATIONS:
        return {"ok": False, "code": "level_request_malformed", "issues": []}
    try:
        return OPERATIONS[request["op"]](request)
    except Refused as refused:
        return {"ok": False, "code": refused.code, "issues": refused.issues}


def main():
    try:
        request = json.loads(sys.stdin.read())
    except ValueError:
        request = None
    sys.stdout.write(json.dumps(answer(request), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
