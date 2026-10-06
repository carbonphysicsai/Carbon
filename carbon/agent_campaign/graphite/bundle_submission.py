"""A Graphite phase-3 winning bundle, as the miner submission the Launchpad would make.

BUNDLE-TO-SUBMISSION-01. Phase 3 ends with a PR-ready bundle
(`delivery.deliver`); before this command nothing turned it into what a miner
submits. `convert` reads the bundle alone and writes the frozen-candidate
record the Launchpad's freeze writes (`selected-recipe.json`), byte for byte,
which is what the Launchpad's submit then reads and sends:

- **The published contract.** The digest compiled against is the one the
  Challenge's miner-facing description publishes
  (`challenge_registry.registry.describe(...)["contract_digest"]`), and the
  bundle's manifest and recipe must both name it.
- **The miner's path, not a parallel compiler.** The recipe goes through the
  Launchpad's own doors: check-design's verdict (`design_check.check_design`,
  the Launchpad's `_design_refusal`), the per-Challenge admission
  (`challenge_contracts.compile_submission` under the published digest), and
  the freeze's one record builder (`research_loop.candidate_record`), which
  `research_campaign.freeze_candidate` writes for a miner and the agent's
  SELECT writes for Carbon's agent.
- **Refusals**, typed, in this order, each before anything is written: a
  bundle whose files differ from its manifest (`bundle_tampered`); a result
  labelled by a development score variant (`score_variant_labelled`); a
  bundle built at a development level, Level 1 or above
  (`development_level_bundle`); any registered development-only variant's
  digest or name anywhere in the bundle (`development_variant_digest`,
  `capability_registry.is_development_variant`'s names); a Challenge the
  registry does not publish (`challenge_not_published`); a contract digest
  other than the published one (`contract_digest_not_published`); a recipe
  the published contract does not admit (`recipe_not_admitted`); a bundle
  Carbon does not rebuild from its files (`bundle_not_rebuilt`,
  `delivery.clean_rebuild`); a frozen record whose digests are not the
  bundle's (`submission_digest_mismatch`); and an output file that already
  holds other bytes (`output_exists`). A refused bundle produces nothing.
- **No network, no key.** The command never submits, signs, registers or
  reaches a chain or an intake. It writes the record and prints the next
  Launchpad step: submitting stays the miner's action.

The record's `reason` names the bundle by its manifest digest and rebuilt
artifact; `used_feedback` is False because a phase-3 session sees practice
feedback only, never a final exam's. The Launchpad's freeze given the same
strategy, reason and used_feedback writes the same bytes (pinned by
`tests/cpu/test_graphite_bundle_submission.py`).

DEVELOPMENT tooling: it grants no qualification, rank, weight or reward, and
it does not judge the recipe's value.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from . import delivery

REPORT_SCHEMA = "carbon.graphite.bundle-submission.v1"

BUNDLE_TAMPERED = "bundle_tampered"
SCORE_VARIANT_LABELLED = "score_variant_labelled"
DEVELOPMENT_LEVEL = "development_level_bundle"
DEVELOPMENT_VARIANT = "development_variant_digest"
CHALLENGE_NOT_PUBLISHED = "challenge_not_published"
CONTRACT_NOT_PUBLISHED = "contract_digest_not_published"
RECIPE_NOT_ADMITTED = "recipe_not_admitted"
BUNDLE_NOT_REBUILT = "bundle_not_rebuilt"
SUBMISSION_DIGEST_MISMATCH = "submission_digest_mismatch"
OUTPUT_EXISTS = "output_exists"
#: Every refusal, in the order they are checked.
REFUSALS = (
    BUNDLE_TAMPERED,
    SCORE_VARIANT_LABELLED,
    DEVELOPMENT_LEVEL,
    DEVELOPMENT_VARIANT,
    CHALLENGE_NOT_PUBLISHED,
    CONTRACT_NOT_PUBLISHED,
    RECIPE_NOT_ADMITTED,
    BUNDLE_NOT_REBUILT,
    SUBMISSION_DIGEST_MISMATCH,
    OUTPUT_EXISTS,
)

#: A phase-3 session sees practice feedback only, never a final exam's.
USED_FEEDBACK = False
#: What a development score variant writes into a result
#: (`development_score_variants.ScoreVariant.identity`, the session's label).
_SCORE_VARIANT_KEYS = frozenset(
    {"score_variant", "score_variant_digest", "score_label"}
)
_SCORE_VARIANT_LABEL = "development_score_result:"


class Refused(ValueError):
    """A bundle refused, by a closed code; nothing was written."""

    def __init__(self, code, detail=()):
        super().__init__(code)
        self.code, self.detail = code, [str(d)[:200] for d in detail][:16]


def _walk(value):
    """Every `(key, string)` in a JSON value: each object key with None, each
    string with its object key (or None)."""
    stack = [(None, value)]
    while stack:
        key, item = stack.pop()
        if type(item) is str:
            yield key, item
        elif type(item) is dict:
            for k, v in item.items():
                yield None, k
                stack.append((k, v))
        elif type(item) is list:
            stack.extend((key, v) for v in item)


def _keys(value):
    stack = [value]
    while stack:
        item = stack.pop()
        if type(item) is dict:
            yield from item
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)


def read_bundle(folder):
    """The bundle's manifest and documents, after its files are checked
    against the manifest (`delivery.verified_files`)."""
    manifest, differences = delivery.verified_files(folder)
    if differences:
        raise Refused(BUNDLE_TAMPERED, differences)
    if set(manifest.get("files") or {}) != set(delivery.FILES):
        raise Refused(BUNDLE_TAMPERED, ["not_a_phase3_bundle"])
    documents = {"manifest.json": manifest}
    for name in delivery.FILES:
        body = (folder / name).read_bytes()
        try:
            if name.endswith(".json"):
                documents[name] = json.loads(body)
            elif name.endswith(".jsonl"):
                documents[name] = [json.loads(x) for x in body.splitlines() if x]
        except ValueError:
            raise Refused(BUNDLE_TAMPERED, ["unreadable:" + name]) from None
    for name in ("strategy.json", "recipe.json", "score.json"):
        if type(documents[name]) is not dict:
            raise Refused(BUNDLE_TAMPERED, ["not_an_object:" + name])
    return manifest, documents


def check_score_variant(documents):
    """No result in the bundle was scored under a development score variant."""
    found = sorted(
        {
            name
            for name, document in documents.items()
            if _SCORE_VARIANT_KEYS & set(_keys(document))
            or any(s.startswith(_SCORE_VARIANT_LABEL) for _, s in _walk(document))
        }
    )
    if found:
        raise Refused(SCORE_VARIANT_LABELLED, found)


def check_level(documents):
    """Built at Level 0, the miner-facing contract: no development binding."""
    recipe, manifest = documents["recipe.json"], documents["manifest.json"]
    marks = [k for k in ("development", "development_record_sequence") if k in recipe]
    for name, document in (("manifest.json", manifest), ("recipe.json", recipe)):
        if document.get("level", 0) != 0:
            marks.append(name + ":level")
    if marks:
        raise Refused(DEVELOPMENT_LEVEL, marks)


def check_variant(documents):
    """No registered development-only variant - a contract variant or a
    score variant, by digest or version name - anywhere in the bundle: the
    names `capability_registry.is_development_variant` refuses, read once."""
    from carbon.reconstruction.capability_registry import (
        development_score_variant_names,
        development_variant_names,
    )

    names = development_variant_names() | development_score_variant_names()
    found = sorted(
        {
            name
            for name, document in documents.items()
            if any(s in names for _, s in _walk(document))
        }
    )
    if found:
        raise Refused(DEVELOPMENT_VARIANT, found)


def published_contract(documents):
    """`(challenge, version, digest)`: the contract digest the Challenge's
    miner-facing description publishes, which the bundle must name."""
    from carbon.challenge_registry import registry

    recipe, strategy = documents["recipe.json"], documents["strategy.json"]
    challenge = recipe.get("challenge")
    if type(challenge) is not dict:
        raise Refused(CHALLENGE_NOT_PUBLISHED, ["recipe_names_no_challenge"])
    identity, version = challenge.get("id"), challenge.get("version")
    if strategy.get("challenge_id") != identity:
        raise Refused(CHALLENGE_NOT_PUBLISHED, ["strategy_names_another_challenge"])
    try:
        published = registry.describe(identity, version)["contract_digest"]
    except registry.ResolutionError as refused:
        raise Refused(CHALLENGE_NOT_PUBLISHED, [refused.code]) from None
    named = {
        "manifest.json": documents["manifest.json"].get("contract_digest"),
        "recipe.json": recipe.get("contract_digest"),
    }
    differ = sorted(name for name, value in named.items() if value != published)
    if differ:
        raise Refused(CONTRACT_NOT_PUBLISHED, differ)
    return identity, version, published


def check_admitted(strategy, published):
    """The Launchpad's own doors for a recipe about to be frozen: its
    check-design verdict, then the per-Challenge admission under the
    published digest."""
    from carbon.development_session.design_check import check_design
    from carbon.reconstruction.challenge_contracts import compile_submission

    try:
        verdict = check_design({"strategy": strategy})["verdict"]
    except ValueError:
        raise Refused(RECIPE_NOT_ADMITTED, ["design_malformed"]) from None
    if verdict != "submittable":
        raise Refused(RECIPE_NOT_ADMITTED, ["design_" + str(verdict)])
    try:
        compile_submission(strategy, contract_digest=published)
    except (ValueError, TypeError) as refused:
        raise Refused(RECIPE_NOT_ADMITTED, [refused]) from None


def check_rebuilt(folder):
    """Carbon rebuilds the bundle from its files alone (`clean_rebuild`)."""
    check = delivery.clean_rebuild(folder)
    if check["status"] != "REBUILT":
        raise Refused(BUNDLE_NOT_REBUILT, check["differences"])


def reason_for(manifest):
    """The frozen record's reason: the bundle, by its manifest digest and,
    for a v3 bundle, the artifact it builds."""
    text = "Graphite phase-3 bundle, manifest " + digest(canonical(manifest))
    if manifest.get("artifact"):
        text += ", artifact " + str(manifest["artifact"])
    return text


def frozen_record(strategy, reason):
    """The record the Launchpad's freeze writes for this recipe: the one
    builder (`research_loop.candidate_record`)."""
    from carbon.development_session.research_loop import candidate_record

    try:
        return candidate_record(strategy, reason, USED_FEEDBACK)
    except (ValueError, TypeError) as refused:
        raise Refused(RECIPE_NOT_ADMITTED, [refused]) from None


def check_digests(record, documents, published):
    """The frozen record names exactly what the bundle built."""
    recipe, manifest = documents["recipe.json"], documents["manifest.json"]
    pairs = {
        "contract_digest": (record["contract_digest"], published),
        "strategy_hash": (record["strategy_hash"], recipe.get("strategy_hash")),
        "plan_digest": (
            record["construction_plan_digest"],
            recipe.get("plan_digest"),
        ),
        "recipe_digest": (
            record["reconstruction_profile_digest"],
            recipe.get("recipe_digest"),
        ),
        "manifest_recipe_digest": (
            record["reconstruction_profile_digest"],
            manifest.get("recipe_digest"),
        ),
    }
    differ = sorted(name for name, (a, b) in pairs.items() if a != b)
    if differ:
        raise Refused(SUBMISSION_DIGEST_MISMATCH, differ)


def check_output(out, body):
    """Nothing overwritten: `out` is absent, or already these exact bytes."""
    if out.is_symlink() or (out.exists() and out.read_bytes() != body):
        raise Refused(OUTPUT_EXISTS, [str(out)])


def next_step(challenge, version, out):
    return (
        "Submitting is your action, through the Launchpad. In a campaign for "
        f"{challenge} {version} where you select (agent none): practice this "
        "strategy (the Launchpad freezes only a practiced recipe); then "
        f"freeze_candidate with the strategy and reason in {out} and "
        "used_feedback false, which writes these same bytes as the epoch's "
        "selected-recipe.json; then submit. This command sent, signed and "
        "registered nothing."
    )


def convert(bundle, out):
    """Check `bundle` and write its submission record to `out`; the report.
    Raises `Refused` with nothing written."""
    folder, out = Path(bundle), Path(out)
    manifest, documents = read_bundle(folder)
    check_score_variant(documents)
    check_level(documents)
    check_variant(documents)
    challenge, version, published = published_contract(documents)
    strategy = documents["strategy.json"]
    check_admitted(strategy, published)
    check_rebuilt(folder)
    record = frozen_record(strategy, reason_for(manifest))
    check_digests(record, documents, published)
    body = canonical(record)
    check_output(out, body)
    out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_once(out, body)
    return {
        "schema": REPORT_SCHEMA,
        "status": "CONVERTED",
        "submission": str(out),
        "submission_digest": digest(body),
        "challenge": {"id": challenge, "version": version},
        "contract_digest": published,
        "strategy_hash": record["strategy_hash"],
        "recipe_digest": record["reconstruction_profile_digest"],
        "bundle": {
            "manifest_digest": digest(canonical(manifest)),
            "artifact": manifest.get("artifact"),
        },
        "submitted": False,
        "signed": False,
        "next_step": next_step(challenge, version, out),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bundle", required=True, help="the phase-3 bundle folder")
    parser.add_argument(
        "--out", required=True, help="where to write the submission record (JSON)"
    )
    args = parser.parse_args(argv)
    try:
        report = convert(args.bundle, args.out)
    except Refused as refused:
        report = {
            "schema": REPORT_SCHEMA,
            "status": "REFUSED",
            "code": refused.code,
            "detail": refused.detail,
            "written": False,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
