"""A Challenge's construction levels, read from data, for both doors.

LAUNCHPAD-LEVELS-01 S1 (OWNER-LADDER-THROUGH-LAUNCHPAD-01). One generic view
answers "what does each construction level of this Challenge admit, and who
may use it?". It names no Challenge and no level has code of its own. Every
value is copied from data the repository already holds:
- the ladder (`carbon.challenge_pipeline.ladder`): each level's text, the
  states and the launch steps; and the Challenge's pipeline record, read
  through its validating loader (`state.load_state`);
- Graphite's accepted level proposals (`proposals.load_proposals`): each
  capability's id, what it adds and its stated bounds, and what the level
  leaves out;
- the development-variant registry, as data only: each level's current
  variant (name, pinned digest, arm) and each widened capability's surface,
  families and machine bounds, from the pinned variant documents;
- the Challenge's construction contract envelope: its `compute_budget`, or
  NOT_SET. Nothing is invented.

**Read only.** The view offers nothing for submission: choosing a level at
freeze is S2, and the validator decides what it serves. A variant's
widened capabilities are shown only when its document matches its pinned
digest and its base is the live contract; otherwise the variant is named
with its refusal code and nothing it widens is shown.

**Why the variant documents are read here as data.** No miner surface may
import the variant module (`tests/invariants/
test_development_variants_unreachable.py`), so this reads the registry
through `capability_registry` and checks each document against its pinned
digest itself. The few closed codes and the level range below are the
variant module's own; `tests/cpu/test_launchpad_ladder_view.py` holds them
equal and holds this view's identities equal to the module's own lookup.
"""

from __future__ import annotations

import functools
import json

SCHEMA = "carbon.launchpad.construction-ladder.v1"

#: The levels a development variant may serve, and its closed codes: the
#: variant module's own values, held equal by the view's tests.
VARIANT_LEVELS = (1, 2, 3)
VARIANT_SCOPE = "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS"
UNREGISTERED = "development_variant_unregistered"
NEEDS_ISOLATION = "development_variant_level_requires_isolation"
BASE_STALE = "development_variant_base_stale"
ALTERED = "development_variant_altered"
MALFORMED = "development_variant_malformed"

#: Who a level is for. MINER_FACING only where the ladder record names it
#: chosen; DEVELOPMENT only above a named deployment's own level.
MINER_FACING = "MINER_FACING"
DEVELOPMENT = "DEVELOPMENT"
NOT_OFFERED = "NOT_OFFERED"

ON_LADDER = "ON_LADDER"
NOT_YET_DEFINED = "NOT_YET_DEFINED"
UNAVAILABLE = "UNAVAILABLE"

#: A Launchpad campaign compiles against the Challenge's registered contract,
#: which is construction Level 0; a variant digest is refused on every
#: miner-facing door. Launching at another level is S2.
CAMPAIGN_LEVEL = 0

AUDIENCE_BASIS = (
    "MINER_FACING is the level the ladder record names as chosen, the one "
    "miners get after the owners lock it. DEVELOPMENT is every level above "
    "the target deployment's own level, and only when a deployment is named; "
    "no deployment declares its level yet, so this view names none. Every "
    "other level is NOT_OFFERED."
)
READ_ONLY = (
    "Display only. No level here can be chosen or submitted from this view, "
    "and no level's bounds, gates or scoring change: the validator decides "
    "what it serves."
)


class SourcesUnavailable(Exception):
    """One of the view's sources could not be read; the code names which."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


# ---- Reading the sources.


def _record_construction(challenge):
    """The construction block of the pipeline record that names this
    Challenge, through the pipeline's validating loader; None when no record
    names it; and the protocol the proposals are checked against."""
    from carbon.challenge_pipeline.state import load_state

    try:
        _families, protocol, _rubric, records = load_state()
    except Exception:  # noqa: BLE001 - an unreadable record is shown as such
        raise SourcesUnavailable("ladder_record_unreadable") from None
    found = [
        r["construction"]
        for r in records.values()
        if r["construction"]["challenge"] == challenge and r["construction"]["levels"]
    ]
    if len(found) > 1:
        raise SourcesUnavailable("ladder_record_ambiguous")
    return (found[0] if found else None), protocol


def _proposals(challenge, protocol):
    from carbon.challenge_pipeline.proposals import load_proposals

    try:
        every = load_proposals(protocol)
    except Exception:  # noqa: BLE001
        raise SourcesUnavailable("proposals_unreadable") from None
    return {level: p for (token, level), p in every.items() if token == challenge}


def _surface(value):
    if value is None:
        return None
    group, kind, low, high, default = value
    return {
        "group": group,
        "kind": kind,
        "minimum_or_choices": low,
        "maximum": high,
        "default": default,
    }


def _variant_refusal(document, entry, pinned, challenge):
    """None for a current variant this view may show; else its closed code."""
    from carbon.reconstruction import expansion_record
    from carbon.reconstruction.capability_registry import CONTRACTS

    if type(document) is not dict or expansion_record.digest_of(document) != pinned:
        return ALTERED
    base = document.get("base_contract")
    if (
        document.get("version") != entry["version"]
        or document.get("challenge") != challenge
        or document.get("level") != entry["level"]
        or document.get("scope") != VARIANT_SCOPE
        or document.get("participant_code") is not False
        or type(document.get("widened")) is not list
        or type(base) is not dict
    ):
        return MALFORMED
    if entry["level"] not in VARIANT_LEVELS:
        return NEEDS_ISOLATION
    # The base is the live contract, pinned by the newest expansion record.
    history = expansion_record.records(challenge)
    newest = history[-1] if history else {}
    live = CONTRACTS[challenge].digest if challenge in CONTRACTS else None
    if not (
        live == base.get("digest")
        and newest.get("contract_digest") == base.get("digest")
        and newest.get("sequence") == base.get("record_sequence")
    ):
        return BASE_STALE
    return None


def _variants(challenge):
    """{level: [variant]} for this Challenge's current registered variants,
    the level's own first, then its named arms."""
    from carbon.reconstruction.capability_registry import (
        DEVELOPMENT_VARIANT_DIR,
        development_variant_registry,
    )

    try:
        registry = development_variant_registry()
    except RuntimeError:
        raise SourcesUnavailable("variant_registry_unreadable") from None
    out = {}
    for entry in registry["current"]:
        if entry["challenge"] != challenge:
            continue
        name, pinned = entry["version"], registry["versions"][entry["version"]]
        try:
            document = json.loads(
                (DEVELOPMENT_VARIANT_DIR / f"{name}.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            document = None
        refusal = _variant_refusal(document, entry, pinned, challenge)
        out.setdefault(entry["level"], []).append(
            {
                "name": name,
                "digest": pinned,
                "arm": entry.get("arm"),
                "status": document.get("status") if refusal is None else None,
                "scope": VARIANT_SCOPE,
                "refusal": refusal,
                "widened": []
                if refusal is not None
                else [
                    {
                        "id": w["id"],
                        "summary": w["summary"],
                        "surface": _surface(w["surface"]),
                        "applies_to": w["applies_to"],
                        "bounds": w["bounds"],
                    }
                    for w in document["widened"]
                ],
            }
        )
    for found in out.values():
        found.sort(key=lambda v: (v["arm"] is not None, v["arm"] or ""))
    return out


def _compute_budget(challenge):
    """The contract envelope's compute budget, or NOT_SET; never invented."""
    from carbon.reconstruction.capability_registry import CONTRACTS
    from carbon.reconstruction.challenge_contracts import COMPUTE_BUDGET

    if challenge not in CONTRACTS:
        # No construction contract, so no envelope declares a budget.
        return {"status": "NOT_SET"}
    try:
        envelope = dict(CONTRACTS[challenge].document()["envelope"])
    except Exception:  # noqa: BLE001
        raise SourcesUnavailable("contract_unreadable") from None
    budget = envelope.get(COMPUTE_BUDGET)
    if budget is None:
        return {"status": "NOT_SET"}
    if not (
        type(budget) is dict
        and set(budget) == {"unit", "value"}
        and type(budget["unit"]) is str
        and type(budget["value"]) in (int, float)
    ):
        return {"status": "MALFORMED"}
    return {"status": "SET", "unit": budget["unit"], "value": budget["value"]}


def read_sources(challenge):
    """Everything the view shows for one Challenge, read from the repository.
    Raises `SourcesUnavailable` naming the source that could not be read."""
    construction, protocol = _record_construction(challenge)
    return {
        "construction": construction,
        "proposals": _proposals(challenge, protocol),
        "variants": _variants(challenge),
        "compute_budget": _compute_budget(challenge),
    }


@functools.lru_cache(maxsize=16)
def _repository_view(challenge):
    try:
        return json.dumps(build(challenge, read_sources(challenge)))
    except SourcesUnavailable as error:
        return json.dumps(unavailable(challenge, error.code))


# ---- Building the view.


def unavailable(challenge, reason):
    return {
        "schema": SCHEMA,
        "challenge": challenge,
        "status": UNAVAILABLE,
        "reason": reason,
        "levels": [],
        "read_only": READ_ONLY,
    }


def audience(level, chosen, deployment_level):
    if chosen is not None and level == chosen:
        return MINER_FACING
    if deployment_level is not None and level > deployment_level:
        return DEVELOPMENT
    return NOT_OFFERED


def _capabilities(proposal, variants):
    """Proposal capabilities in the proposal's order, each merged with what
    a shown variant widens under the same id; then variant-only ones."""
    rows, by_id = [], {}
    for item in (proposal or {}).get("capabilities", []):
        row = {
            "id": item["id"],
            "summary": item["adds"],
            "proposal": {"adds": item["adds"], "bounds": item["bounds"]},
            "widened": [],
        }
        rows.append(row)
        by_id[item["id"]] = row
    for found in variants:
        for w in found["widened"]:
            row = by_id.get(w["id"])
            if row is None:
                row = {"id": w["id"], "summary": w["summary"], "proposal": None, "widened": []}
                rows.append(row)
                by_id[w["id"]] = row
            row["widened"].append({"variant": found["name"], "arm": found["arm"], **w})
    return rows


def _identity(found):
    return {
        key: found[key] for key in ("name", "digest", "arm", "status", "scope", "refusal")
    }


def build(challenge, sources, deployment_level=None):
    """The view from already-read sources. Generic: every level is drawn by
    the same code from the same keys."""
    from carbon.challenge_pipeline import ladder

    construction = sources["construction"]
    chosen = construction["chosen"] if construction else None
    levels = []
    for level, text in sorted(ladder.LEVELS.items()):
        proposal = sources["proposals"].get(level)
        variants = sources["variants"].get(level, [])
        own = [v for v in variants if v["arm"] is None]
        if level == 0:
            refusal = None
        elif level not in VARIANT_LEVELS:
            refusal = NEEDS_ISOLATION
        elif not own:
            refusal = UNREGISTERED
        else:
            refusal = own[0]["refusal"]
        levels.append(
            {
                "level": level,
                "text": text,
                "state": ladder.state_of(construction, level)
                if construction
                else ladder.NOT_RUN,
                "audience": audience(level, chosen, deployment_level),
                "proposal_status": proposal["status"] if proposal else None,
                "capabilities": _capabilities(proposal, variants),
                "left_out": list(proposal["left_out"]) if proposal else [],
                "variant": _identity(own[0]) if own else None,
                "arms": [_identity(v) for v in variants if v["arm"] is not None],
                "variant_refusal": refusal,
                "compute_budget": dict(sources["compute_budget"]),
            }
        )
    return {
        "schema": SCHEMA,
        "challenge": challenge,
        "status": ON_LADDER if construction else NOT_YET_DEFINED,
        "ladder": None
        if construction is None
        else {"level": construction["level"], "chosen": chosen},
        "deployment_level": deployment_level,
        "audience_basis": AUDIENCE_BASIS,
        "states": [*ladder.STATES, ladder.NOT_RUN],
        "launch": list(ladder.LAUNCH),
        "levels": levels,
        "read_only": READ_ONLY,
    }


def ladder_view(challenge_id, deployment_level=None):
    """One Challenge's construction levels, from the repository's data."""
    value = json.loads(_repository_view(challenge_id))
    if deployment_level is None or value["status"] == UNAVAILABLE:
        return value
    chosen = (value["ladder"] or {}).get("chosen")
    value["deployment_level"] = deployment_level
    for row in value["levels"]:
        row["audience"] = audience(row["level"], chosen, deployment_level)
    return value


def construction_slot(challenge_id):
    """The Contract view's `construction_level` (RSURF-D10), from the ladder:
    the campaign's own level and that level's place on the ladder. Without
    ladder data it stays NOT_YET_DEFINED; it is never inferred."""
    try:
        value = ladder_view(challenge_id)
    except Exception:  # noqa: BLE001 - the rest of the contract still shows
        value = unavailable(challenge_id, "ladder_unreadable")
    if value["status"] == UNAVAILABLE:
        return {
            "level": None,
            "status": UNAVAILABLE,
            "basis": "This Challenge's construction ladder could not be read.",
        }
    if value["status"] != ON_LADDER:
        return {
            "level": None,
            "status": NOT_YET_DEFINED,
            "basis": (
                "No pipeline record places this Challenge on the construction "
                "ladder yet. This slot is filled from its data when one does."
            ),
        }
    row = value["levels"][CAMPAIGN_LEVEL]
    return {
        "level": CAMPAIGN_LEVEL,
        "status": "DEFINED",
        "basis": (
            "Your campaign compiles against this Challenge's registered "
            "contract, construction Level 0. The ladder's record gives the "
            "level's state; choosing another level at freeze is not offered yet."
        ),
        "text": row["text"],
        "state": row["state"],
        "audience": row["audience"],
        "ladder": dict(value["ladder"]),
    }


def for_request(request):
    """`ladder`: one registered Challenge's construction levels."""
    from carbon.challenge_registry.campaigns import challenge_ref
    from scripts.dev.miner_launchpad.controller import Rejected

    challenge_id, version = request["challenge"], request.get("challenge_version")
    if type(challenge_id) is not str or (
        version is not None and type(version) is not str
    ):
        raise Rejected("challenge_required")
    ref = challenge_ref(challenge_id)
    if ref["version"] is None or version not in (None, ref["version"]):
        raise Rejected("challenge_unknown", 404)
    return {**ladder_view(challenge_id), "version": ref["version"]}
