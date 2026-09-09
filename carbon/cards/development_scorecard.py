"""A6-owned v1 fixture scorecard allow-list; no real disclosure authorization."""

import json
import math
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from carbon.scoring.pack import LoadedScorePack


def alias(value):
    if (
        type(value) is not str
        or not 1 <= len(value) <= 64
        or not all(c.isascii() and (c.isalnum() or c in "-_") for c in value)
    ):
        raise ValueError("INVALID_PUBLIC_ALIAS")
    return value


def coefficients(pack, challenge_alias, opens_ms):
    """Publish the loaded registered coefficients, never caller-selected weights."""
    if (
        type(pack) is not LoadedScorePack
        or pack.ready is not True
        or pack.pack_pin.fixture_origin is not True
    ):
        raise ValueError("FIXTURE_SCORE_PACK_REQUIRED")
    weights = pack.top_level_weights
    # The verified loader owns exact unit-sum validation; do not invent another
    # scientific tolerance when projecting its binary64 coefficients.
    if (
        type(weights) is not tuple
        or len(weights) != 3
        or any(type(w) is not float or not math.isfinite(w) or w <= 0 for w in weights)
    ):
        raise ValueError("INVALID_REGISTERED_COEFFICIENTS")
    if type(opens_ms) is not int or not 0 <= opens_ms < 2**63:
        raise ValueError("INVALID_OPENING")
    return {
        "schema": "carbon.development.scorecard.coefficients.v1",
        "maturity": "SYNTHETIC_ONLY",
        "challenge": alias(challenge_alias),
        "opens_ms": opens_ms,
        "composition": "weighted_geometric_logspace",
        "coefficients": {
            name: str(value)
            for name, value in zip(
                ("physics", "robustness", "accuracy"), weights, strict=True
            )
        },
        "display_decimals": 3,
    }


def accepted_scorecard(
    challenge_alias, miner_alias, result_alias, combined, components, release_ms
):
    """Private accepted adapter supplies values; output contains only this list.

    Pure fixture projection is not an acceptance operation or permission to
    release a real exam. Cadence/accounting belongs to its durable caller.
    """
    if type(components) is not tuple or len(components) != 3:
        raise ValueError("INVALID_AGGREGATE_SCORES")
    values = (combined, *components)
    if any(
        type(value) is not float or not math.isfinite(value) or not 0 <= value <= 1
        for value in values
    ):
        raise ValueError("INVALID_AGGREGATE_SCORES")
    if type(release_ms) is not int or not 0 <= release_ms < 2**63:
        raise ValueError("INVALID_RELEASE_TIME")
    with localcontext() as context:
        context.prec = 80
        scores = {
            name: format(
                Decimal(str(value)).quantize(Decimal(".001"), rounding=ROUND_HALF_EVEN),
                "f",
            )
            for name, value in zip(
                ("combined", "physics", "robustness", "accuracy"), values, strict=True
            )
        }
    return {
        "schema": "carbon.development.scorecard.accepted.v1",
        "maturity": "SYNTHETIC_ONLY",
        "challenge": alias(challenge_alias),
        "miner": alias(miner_alias),
        "accepted_result": alias(result_alias),
        "release_ms": release_ms,
        "scores": scores,
        "comparison_source": "private accepted scientific bytes",
    }


def checked_document(value):
    """Recheck persisted public rows at release; never forward added fields."""
    if type(value) is not dict or value.get("maturity") != "SYNTHETIC_ONLY":
        raise ValueError("DISCLOSURE_SCHEMA")
    schema = value.get("schema")
    if schema == "carbon.development.scorecard.coefficients.v1":
        keys = {
            "schema",
            "maturity",
            "challenge",
            "opens_ms",
            "composition",
            "coefficients",
            "display_decimals",
        }
        scores = value.get("coefficients")
        if (
            set(value) != keys
            or value["composition"] != "weighted_geometric_logspace"
            or value["display_decimals"] != 3
            or type(scores) is not dict
            or set(scores) != {"physics", "robustness", "accuracy"}
        ):
            raise ValueError("DISCLOSURE_SCHEMA")
        for score in scores.values():
            if type(score) is not str or len(score) > 32:
                raise ValueError("DISCLOSURE_SCHEMA")
            try:
                numeric = float(score)
            except ValueError:
                numeric = math.nan
            if (
                not math.isfinite(numeric)
                or not 0 < numeric <= 1
                or str(numeric) != score
            ):
                raise ValueError("DISCLOSURE_SCHEMA")
        when = value["opens_ms"]
    elif schema == "carbon.development.scorecard.accepted.v1":
        keys = {
            "schema",
            "maturity",
            "challenge",
            "miner",
            "accepted_result",
            "release_ms",
            "scores",
            "comparison_source",
        }
        scores = value.get("scores")
        if (
            set(value) != keys
            or value["comparison_source"] != "private accepted scientific bytes"
            or type(scores) is not dict
            or set(scores) != {"combined", "physics", "robustness", "accuracy"}
        ):
            raise ValueError("DISCLOSURE_SCHEMA")
        for score in scores.values():
            if (
                type(score) is not str
                or len(score) != 5
                or score[1] != "."
                or not (score[0] + score[2:]).isascii()
                or not (score[0] + score[2:]).isdigit()
                or not 0 <= float(score) <= 1
            ):
                raise ValueError("DISCLOSURE_SCHEMA")
        alias(value["miner"])
        alias(value["accepted_result"])
        when = value["release_ms"]
    else:
        raise ValueError("DISCLOSURE_SCHEMA")
    alias(value["challenge"])
    if type(when) is not int or not 0 <= when < 2**63:
        raise ValueError("DISCLOSURE_SCHEMA")
    return json.loads(json.dumps(value, allow_nan=False))
