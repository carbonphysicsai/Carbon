"""Pooled disclosure through the Test Engineer's grain reference.

Missing registration or noise evidence keeps the display sealed. Case errors
and regrets are consumed only here, never returned through the public allow-list.
"""

import hashlib
import json
import math
from pathlib import Path

GRAIN_DIR = "docs/development/evidence/battery-screening-grain"


def _registration_digest(doc):
    """Identity of the public canonical registration document, not case data."""
    body = json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def rule_name(rule):
    """The registered name of a deployment's exam rule (`exam.RULES`), or None.

    A rule dict carries no name, and its `rule_version` is the exam rule's
    version (2 for both v2-bank-sched and v3-bank-sched), not its name, so the
    grain file's `match.rule` is matched against the name this recovers. A
    registered-score rule carries the deployment's own score term in place of
    the registry's placeholder, so the term is set aside on both sides. Exactly
    one registered rule must match; anything else seals."""
    from carbon.battery import exam

    if type(rule) is not dict:
        return None
    body = {k: v for k, v in rule.items() if k != "score"}
    hits = [
        name
        for name, registered in exam.RULES.items()
        if {k: v for k, v in registered.items() if k != "score"} == body
        and ("score" in registered) == ("score" in rule)
    ]
    return hits[0] if len(hits) == 1 else None


def load_grain(repository, identities, rule):
    """Latest registered policy and exactly one deployment match, or None.

    The reference module and its files ship together in #1205. Until then this
    additive feed path remains usable and sealed; it has no fallback policy.
    """
    try:
        from . import screening_grain as sg

        doc = sg.load(Path(repository) / GRAIN_DIR)
        term = rule.get("score")
        deployment = {
            "rule": rule_name(rule),
            "rule_digest": identities["rule_digest"],
            "score_section": "accuracy" if term is None else "registered",
        }
        if term is not None:
            deployment.update(
                score_candidate=term["candidate"],
                registry_sha256=term["registry_sha256"],
            )
        if (
            type(doc) is not dict
            or doc.get("schema") != "carbon.battery.screening-grain.v1"
            or doc.get("challenge") != identities["challenge"]["id"]
            or doc.get("display_grid") != "geometric"
            or type(doc.get("noise_floor")) is not dict
            or type(doc.get("version")) is not int
            or doc["version"] < 1
            or type(doc.get("entries")) is not list
            or any(
                type(e) is not dict or type(e.get("match")) is not dict
                for e in doc["entries"]
            )
        ):
            return None
        entry = sg.entry_for(doc, deployment)
        sense = "lower_is_better" if term is None else "higher_is_better"
        if entry is None or entry.get("sense") != sense:
            return None
        if not (set(deployment) - {"rule_digest"}) <= set(entry["match"]):
            return None
        grain, pct, se = entry["grain"], entry["grain_pct"], entry["measured_se"]
        if any(
            type(v) not in (int, float) or not math.isfinite(v)
            for v in (grain, pct, se)
        ):
            return None
        if (
            grain <= 0
            or se < 0
            or grain != sg.round_up(se)
            or not math.isclose(pct, grain * 100, rel_tol=1e-15)
        ):
            return None
        for name in ("min_cases", "min_design_questions"):
            if (
                type(doc["noise_floor"].get(name)) is not int
                or doc["noise_floor"][name] < 2
            ):
                return None
        _registration_digest(doc)
        return sg, doc, entry
    except (
        ImportError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        ArithmeticError,
        RecursionError,
    ):
        return None


def ladder(rows, owners, policy, rule):
    """Replay immutable records in scoring order, grouped by chain coldkey.

    Each decision measures that submission's own noise. No pooling across
    members or historical attempts, and no noise inputs in the returned block.
    """
    held = {}
    for row in rows:
        coldkey = owners.get(row["hotkey"])
        if coldkey is None:
            continue
        current = held.setdefault(
            coldkey,
            {
                "coldkey": coldkey,
                "hotkeys": set(),
                "rank": None,
                "displayed_score": None,
                "status": "SEALED_UNTIL_GRAIN",
                "best_submission_id": None,
                "displayed_at_block": None,
            },
        )
        current["hotkeys"].add(row["hotkey"])
        if policy is None:
            continue
        sg, doc, entry = policy
        score = row["score"]
        if type(score) not in (int, float) or not math.isfinite(score) or score <= 0:
            continue
        try:
            noise = row.get("noise")
            if type(noise) is not dict:
                continue
            errors, regrets = noise["errors"], noise.get("regrets", [])
            if (
                type(errors) is not list
                or type(regrets) is not list
                or any(
                    type(x) not in (int, float) or not math.isfinite(x) or x < 0
                    for x in [*errors, *regrets]
                )
            ):
                continue
            own, n, m = sg.coldkey_own_se(
                rule["rule_version"],
                [{"coldkey": coldkey, "errors": errors, "regrets": regrets}],
                coldkey,
            )
            if own is not None and (not math.isfinite(own) or own < 0):
                continue
            state, shown = sg.update(
                doc, entry, current["displayed_score"], score, own, n, m
            )
            if state == sg.UPDATE:
                # Never overstate, even at a floating-point grid edge.
                if (
                    not math.isfinite(shown)
                    or shown <= 0
                    or (
                        shown < score
                        if entry["sense"] == "lower_is_better"
                        else shown > score
                    )
                ):
                    continue
                current.update(
                    displayed_score=shown,
                    status="SHOWN",
                    best_submission_id=row["submission_id"],
                    displayed_at_block=row["block"],
                )
            elif current["displayed_score"] is not None:
                current["status"] = "NO_IMPROVEMENT_BEYOND_GRAIN"
        except (KeyError, TypeError, ValueError, ArithmeticError):
            continue
    sense = None if policy is None else policy[2]["sense"]
    displayed = [r for r in held.values() if r["displayed_score"] is not None]
    displayed.sort(
        key=lambda r: (
            (
                r["displayed_score"]
                if sense == "lower_is_better"
                else -r["displayed_score"]
            ),
            (
                r["displayed_at_block"]
                if r["displayed_at_block"] is not None
                else math.inf
            ),
            r["coldkey"],
        )
    )
    for rank, row in enumerate(displayed, 1):
        row["rank"] = rank
    return {
        "grain_pct": None if policy is None else policy[2]["grain_pct"],
        "display_grid": "geometric",
        "sense": sense,
        "grain_version": None if policy is None else policy[1].get("version"),
        "grain_registration_digest": (
            None if policy is None else _registration_digest(policy[1])
        ),
        "coldkeys": [
            {**row, "hotkeys": sorted(row["hotkeys"])}
            for row in sorted(
                held.values(), key=lambda r: (r["rank"] or math.inf, r["coldkey"])
            )
        ],
    }
