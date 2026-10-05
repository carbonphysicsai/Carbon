"""Development score variants (VALIDATOR-09; OWNER-GRAPHITE-TEST-WAVE-08 §3).

A development score variant is a registered, digest-pinned candidate for how a
Challenge's score is assembled from its per-case components. It covers the
component weights and, optionally, a transform onto [0, 1], where closer to 1
is better (OWNER-TESTNET-WEIGHTS-01 §2a; `Design_Specs/Scoring.md` §6.2's
`tail_logistic`).

The tuning loop registers each candidate **before** it is computed: it is
committed in `development_score_variant_policies/` and pinned in its registry.
It is then re-scored from stored per-case rows (`rescore`), with no
retraining.

**Never served to miners.** No miner surface, validator, intake or registry
path imports this module (`tests/invariants/test_score_variants_unreachable`).
The Challenge's scoring declares, as data only, which components a variant
may weight (`ChallengeScoring.declared_score_components`).

**Not yet served:**
- set-level aggregate terms;
- gate overrides;
- comparison and important-region overrides.

Each is refused by name until its adapter path exists.

The shipped registry starts empty. A fixture document is refused there, and
tests use their own directory. DEVELOPMENT only: no qualification, weight,
reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

POLICY_DIR = Path(__file__).resolve().parent / "development_score_variant_policies"
SCHEMA = "carbon.development-score-variant.v1"
REGISTRY_SCHEMA = "carbon.development-score-variant-registry.v1"
SCOPE = "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS"
STATUSES = ("CANDIDATE", "SURVIVOR")
RESCORE_SCHEMA = "carbon.development-score-variant-rescore.v1"
_KEYS = frozenset(
    {
        "schema",
        "version",
        "challenge_id",
        "base_rule",
        "weights",
        "aggregate_terms",
        "gates",
        "comparison",
        "important_region",
        "transform",
        "scope",
        "status",
        "authority",
        "fixture",
    }
)


class ScoreVariantRefused(ValueError):
    """A typed refusal, by code."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _decimal(text):
    if type(text) is not str:
        raise ScoreVariantRefused("score_variant_malformed")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ScoreVariantRefused("score_variant_malformed") from None
    if not value.is_finite():
        raise ScoreVariantRefused("score_variant_malformed")
    return value


@dataclass(frozen=True)
class ScoreVariant:
    version: str
    digest: str
    challenge_id: str
    base_rule: str
    weights: tuple  # ((component, float), ...) in the document's order
    transform: dict | None
    status: str

    def identity(self):
        """What a result scored under this variant records."""
        return {
            "score_variant": self.version,
            "score_variant_digest": self.digest,
            "base_rule": self.base_rule,
            "label": "development_score_result:" + self.version,
        }


def _registry(directory):
    try:
        registry = json.loads((Path(directory) / "registry.json").read_text())
    except (OSError, ValueError):
        raise ScoreVariantRefused("score_variant_registry_unreadable") from None
    if (
        type(registry) is not dict
        or registry.get("schema") != REGISTRY_SCHEMA
        or type(registry.get("variants")) is not dict
    ):
        raise ScoreVariantRefused("score_variant_registry_malformed")
    return registry


def registered(directory=None):
    """Every registered version, by name."""
    return dict(_registry(POLICY_DIR if directory is None else directory)["variants"])


def _declared(challenge_id):
    from carbon.challenge_validator.scoring import scoring_for

    return tuple(scoring_for(challenge_id).declared_score_components)


def load_variant(version, *, directory=None, declared=None):
    """A registered variant, verified. `declared` overrides the Challenge's
    declared components (tests only). The shipped registry refuses a fixture
    document."""
    shipped = directory is None
    directory = POLICY_DIR if shipped else Path(directory)
    variants = _registry(directory)["variants"]
    if type(version) is not str or version not in variants:
        raise ScoreVariantRefused("score_variant_unregistered")
    try:
        document = json.loads((directory / f"{version}.json").read_text())
    except (OSError, ValueError):
        raise ScoreVariantRefused("score_variant_unreadable") from None
    pinned = variants[version]
    if digest(document) != pinned:
        raise ScoreVariantRefused("score_variant_altered")
    if (
        type(document) is not dict
        or set(document) != _KEYS
        or document["schema"] != SCHEMA
        or document["version"] != version
        or type(document["challenge_id"]) is not str
        or type(document["base_rule"]) is not str
        or document["scope"] != SCOPE
        or document["status"] not in STATUSES
        or type(document["fixture"]) is not bool
        or type(document["authority"]) is not dict
    ):
        raise ScoreVariantRefused("score_variant_malformed")
    if shipped and document["fixture"]:
        raise ScoreVariantRefused("score_variant_fixture_in_shipped_registry")
    for field, code in (
        ("aggregate_terms", "score_variant_aggregate_terms_not_served"),
        ("gates", "score_variant_gate_overrides_not_served"),
        ("comparison", "score_variant_comparison_not_served"),
        ("important_region", "score_variant_important_region_not_served"),
    ):
        if document[field] not in (None, [], {}):
            raise ScoreVariantRefused(code)
    declared = (
        _declared(document["challenge_id"]) if declared is None else tuple(declared)
    )
    weights = document["weights"]
    if type(weights) is not dict or not weights:
        raise ScoreVariantRefused("score_variant_malformed")
    if set(weights) - set(declared):
        raise ScoreVariantRefused("score_variant_component_not_declared")
    values = {name: _decimal(text) for name, text in weights.items()}
    if any(v <= 0 for v in values.values()) or sum(values.values()) != Decimal(1):
        # Strictly positive, exact decimal sum one (Scoring.md's weight rule).
        raise ScoreVariantRefused("score_variant_weights_not_unit_sum")
    transform = document["transform"]
    if transform is not None and (
        type(transform) is not dict
        or set(transform) != {"kind", "threshold", "sharpness"}
        or transform["kind"] != "tail_logistic"
        or _decimal(transform["threshold"]) <= 0
        or _decimal(transform["sharpness"]) <= 0
    ):
        raise ScoreVariantRefused("score_variant_transform_malformed")
    return ScoreVariant(
        version=version,
        digest=pinned,
        challenge_id=document["challenge_id"],
        base_rule=document["base_rule"],
        weights=tuple((name, float(values[name])) for name in weights),
        transform=transform,
        status=document["status"],
    )


def tail_logistic(error, threshold, sharpness):
    """`1 / (1 + exp(z))` with `z = sharpness * (error - threshold) /
    threshold`, overflow-safe as Scoring.md §6.2 states it. 1 is best."""
    z = sharpness * (error - threshold) / threshold
    if z >= 0:
        q = math.exp(-z)
        return q / (1.0 + q)
    return 1.0 / (1.0 + math.exp(z))


def case_error(variant, components):
    return math.fsum(weight * components[name] for name, weight in variant.weights)


def rescore(variant, rows):
    """A member's score under `variant`, from its stored per-case rows
    (`state`, `components`, `important`). A gate failure still makes it
    ineligible: mandatory failure is not compensated."""
    scored = [r for r in rows if r.get("state") == "SCORABLE"]
    failed = sum(1 for r in rows if r.get("state") == "GATE_FAILED")
    errors = [case_error(variant, r["components"]) for r in scored]
    important = [
        case_error(variant, r["components"]) for r in scored if r.get("important")
    ]
    error = math.fsum(errors) / len(errors) if errors else None
    out = {
        **variant.identity(),
        "eligible": failed == 0 and bool(scored),
        "n_scored": len(scored),
        "n_gate_failed": failed,
        "error": error,
        "important_error": (
            math.fsum(important) / len(important) if important else None
        ),
        "score": None,
    }
    if variant.transform is not None and error is not None:
        out["score"] = tail_logistic(
            error,
            float(variant.transform["threshold"]),
            float(variant.transform["sharpness"]),
        )
    return out


def rescore_directory(variant, rows_dir):
    """Every member's rows file in `rows_dir` (`<member>.json`), re-scored."""
    found = {}
    for path in sorted(Path(rows_dir).glob("*.json")):
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ScoreVariantRefused("score_variant_rows_not_owner_only")
        found[path.stem] = rescore(variant, json.loads(path.read_bytes()))
    return {"schema": RESCORE_SCHEMA, **variant.identity(), "members": found}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.scoring.development_score_variants"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    run = sub.add_parser("rescore", help="re-score stored per-case rows (operator)")
    run.add_argument("--version", required=True)
    run.add_argument("--rows", required=True)
    run.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            result = registered()
        else:
            document = rescore_directory(load_variant(args.version), args.rows)
            out = Path(args.out)
            fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as handle:
                json.dump(document, handle, sort_keys=True)
            result = {"members": len(document["members"]), "out": str(out)}
    except ScoreVariantRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
