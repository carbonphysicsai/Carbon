"""The miner plan: Graphite's ranked research plan for one Challenge.

Schema `carbon.graphite.miner-plan.v1`. A plan ranks hypotheses, best first;
each has the hypothesis, its expected effect, a stopping rule, an optional
recipe and the literature cards it cites, each with its origin. It names the
pins it considered, its parent plan (a miner's edit of an earlier one) and who
wrote it (`planner` or `miner`).

A plan is guidance data. The Constructor reads it, labelled as such, in its
first observation; nothing in it changes a rule, a tool, a limit, the budget
or an authority, and its cards stay UNCHECKED literature.

`validate_plan` refuses, by closed code, a plan that is malformed
(`plan_invalid`), cites a card the literature does not hold
(`card_not_found`), cites a banned card (`card_banned`), names a card under
another origin than its own, or leaves out a pinned card (`plan_invalid`). A
miner's edit is a new plan with its own digest whose parent is the plan it
edits (`new_version`); a plan, once stored, never changes.
"""

from __future__ import annotations

import json
import re

from carbon.development_session.profile import canonical, digest

from .edition import ORIGINS

PLAN_SCHEMA = "carbon.graphite.miner-plan.v1"
CREATORS = ("planner", "miner")
#: Shape bounds. They keep a plan a readable document inside one tool call
#: and one observation; they are not research limits.
MAX_HYPOTHESES = 8
MAX_CITES = 12
MAX_PINS = 64
MAX_TEXT = 2000
#: A recipe is a JSON object of at most this many bytes, as the research
#: tools bound a tool argument (`research_agent_policy.MAX_TOOL_ARGUMENT_BYTES`).
MAX_RECIPE_BYTES = 16384
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CARD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
PLAN_FIELDS = frozenset(
    {"schema", "challenge", "hypotheses", "pins_considered", "parent", "created_by"}
)
HYPOTHESIS_FIELDS = frozenset(
    {"rank", "hypothesis", "expected_effect", "stopping_rule", "cites"}
)

PLAN_INVALID = "plan_invalid"
CARD_NOT_FOUND = "card_not_found"
CARD_BANNED = "card_banned"
PLAN_NOT_FOUND = "plan_not_found"


class PlanInvalid(ValueError):
    def __init__(self, code, field, reason, fix):
        super().__init__(code)
        self.code, self.field, self.reason, self.fix = code, field, reason, fix

    def refusal(self):
        return refusal(self.code, self.field, self.reason, self.fix)


def refusal(code, field, reason, fix):
    """A refused plan, answered: nothing was recorded."""
    return {
        "status": "REJECTED_BEFORE_DISPATCH",
        "code": code,
        "field": field,
        "reason": reason,
        "fix": fix,
        "detail": "Nothing was recorded. Correct the plan and record it again.",
        "authority_granted": False,
    }


def _text(value, field):
    if type(value) is not str or not 1 <= len(value.strip()) or len(value) > MAX_TEXT:
        raise PlanInvalid(
            PLAN_INVALID,
            field,
            f"{field} must be text of 1 to {MAX_TEXT} characters",
            f"write {field} as plain text",
        )
    return value


def _cites(value, field):
    if type(value) is not list or len(value) > MAX_CITES:
        raise PlanInvalid(
            PLAN_INVALID,
            field,
            f"cites is a list of at most {MAX_CITES} cards",
            "cite at most that many cards, each {card_id, origin}",
        )
    cites = []
    for item in value:
        if (
            type(item) is not dict
            or set(item) != {"card_id", "origin"}
            or type(item["card_id"]) is not str
            or not _CARD_ID.fullmatch(item["card_id"])
            or item["origin"] not in ORIGINS
        ):
            raise PlanInvalid(
                PLAN_INVALID,
                field,
                "each cite is {card_id, origin}, origin shared, miner_hunt or "
                "miner_import",
                "cite each card by its card_id with the origin lit_card shows",
            )
        cites.append({"card_id": item["card_id"], "origin": item["origin"]})
    return cites


def _pins(value):
    if type(value) is not list or len(value) > MAX_PINS:
        raise PlanInvalid(
            PLAN_INVALID,
            "pins_considered",
            f"pins_considered is a list of at most {MAX_PINS} cards",
            "name each pinned card once, with how you considered it",
        )
    pins = []
    for item in value:
        if (
            type(item) is not dict
            or set(item) != {"card_id", "consideration"}
            or type(item["card_id"]) is not str
            or not _CARD_ID.fullmatch(item["card_id"])
        ):
            raise PlanInvalid(
                PLAN_INVALID,
                "pins_considered",
                "each entry is {card_id, consideration}",
                "name each pinned card with how you considered it",
            )
        pins.append(
            {
                "card_id": item["card_id"],
                "consideration": _text(item["consideration"], "consideration"),
            }
        )
    if len({pin["card_id"] for pin in pins}) != len(pins):
        raise PlanInvalid(
            PLAN_INVALID,
            "pins_considered",
            "a card is named more than once",
            "name each pinned card once",
        )
    return pins


def _recipe(raw, field):
    if raw is None:
        return None
    from carbon.development_session.research_tools import _json

    if type(raw) is dict:
        raw = json.dumps(raw)
    try:
        if len(raw.encode()) > MAX_RECIPE_BYTES:
            raise ValueError("too large")
        return _json(raw)
    except (ValueError, AttributeError, RecursionError):
        raise PlanInvalid(
            PLAN_INVALID,
            field,
            "a recipe is one JSON object encoded as a string",
            "send recipe_json as a string holding the recipe object, or null",
        ) from None


def _challenge(challenge):
    if (
        type(challenge) is not dict
        or set(challenge) != {"id", "version"}
        or type(challenge["id"]) is not str
        or not challenge["id"]
    ):
        raise ValueError("a plan names its Challenge as {id, version}")
    return {"id": challenge["id"], "version": challenge["version"]}


def from_arguments(arguments, *, challenge, parent=None, created_by="planner"):
    """The plan the Planner's `graphite_record_plan` call records, or
    `PlanInvalid` naming the field to fix. Structure only; the literature
    checks are `validate_plan`'s."""
    if type(arguments) is not dict or set(arguments) != {
        "hypotheses",
        "pins_considered",
    }:
        raise PlanInvalid(
            PLAN_INVALID,
            "arguments",
            "a plan takes hypotheses and pins_considered only",
            "send exactly those two fields",
        )
    hypotheses = arguments["hypotheses"]
    if type(hypotheses) is not list or not 1 <= len(hypotheses) <= MAX_HYPOTHESES:
        raise PlanInvalid(
            PLAN_INVALID,
            "hypotheses",
            f"a plan ranks 1 to {MAX_HYPOTHESES} hypotheses",
            "rank between one and that many hypotheses, best first",
        )
    ranked = []
    for index, item in enumerate(hypotheses):
        field = f"hypotheses[{index}]"
        if type(item) is not dict or set(item) != {
            "hypothesis",
            "expected_effect",
            "stopping_rule",
            "recipe_json",
            "cites",
        }:
            raise PlanInvalid(
                PLAN_INVALID,
                field,
                "a hypothesis has hypothesis, expected_effect, stopping_rule, "
                "recipe_json and cites",
                "send each hypothesis with exactly those fields",
            )
        entry = {
            "rank": index + 1,
            "hypothesis": _text(item["hypothesis"], field + ".hypothesis"),
            "expected_effect": _text(
                item["expected_effect"], field + ".expected_effect"
            ),
            "stopping_rule": _text(item["stopping_rule"], field + ".stopping_rule"),
            "cites": _cites(item["cites"], field + ".cites"),
        }
        recipe = _recipe(item["recipe_json"], field + ".recipe_json")
        if recipe is not None:
            entry["recipe"] = recipe
        ranked.append(entry)
    return document(
        challenge=challenge,
        hypotheses=ranked,
        pins_considered=_pins(arguments["pins_considered"]),
        parent=parent,
        created_by=created_by,
    )


def document(*, challenge, hypotheses, pins_considered, parent, created_by):
    plan = {
        "schema": PLAN_SCHEMA,
        "challenge": _challenge(challenge),
        "hypotheses": hypotheses,
        "pins_considered": pins_considered,
        "parent": parent,
        "created_by": created_by,
    }
    check_shape(plan)
    return plan


def check_shape(plan):
    """A stored plan's closed shape, or `PlanInvalid`."""
    if type(plan) is not dict or set(plan) != PLAN_FIELDS:
        raise PlanInvalid(
            PLAN_INVALID, "plan", "not a miner plan", "send a miner plan document"
        )
    if plan["schema"] != PLAN_SCHEMA:
        raise PlanInvalid(
            PLAN_INVALID,
            "schema",
            "a plan is " + PLAN_SCHEMA,
            "send a plan in this schema",
        )
    try:
        _challenge(plan["challenge"])
    except ValueError:
        raise PlanInvalid(
            PLAN_INVALID,
            "challenge",
            "a plan names its Challenge as {id, version}",
            "name the campaign's Challenge",
        ) from None
    if plan["created_by"] not in CREATORS:
        raise PlanInvalid(
            PLAN_INVALID,
            "created_by",
            "created_by is planner or miner",
            "name who wrote the plan",
        )
    if plan["parent"] is not None and (
        type(plan["parent"]) is not str or not _DIGEST.fullmatch(plan["parent"])
    ):
        raise PlanInvalid(
            PLAN_INVALID,
            "parent",
            "parent is a plan digest or null",
            "name the plan this one edits by its digest",
        )
    hypotheses = plan["hypotheses"]
    if type(hypotheses) is not list or not 1 <= len(hypotheses) <= MAX_HYPOTHESES:
        raise PlanInvalid(
            PLAN_INVALID,
            "hypotheses",
            f"a plan ranks 1 to {MAX_HYPOTHESES} hypotheses",
            "rank between one and that many hypotheses, best first",
        )
    for index, item in enumerate(hypotheses):
        field = f"hypotheses[{index}]"
        if (
            type(item) is not dict
            or not HYPOTHESIS_FIELDS <= set(item) <= HYPOTHESIS_FIELDS | {"recipe"}
            or item["rank"] != index + 1
        ):
            raise PlanInvalid(
                PLAN_INVALID,
                field,
                "a ranked hypothesis has rank, hypothesis, expected_effect, "
                "stopping_rule, cites and optionally recipe, ranked from 1",
                "send each hypothesis with exactly those fields, in rank order",
            )
        for name in ("hypothesis", "expected_effect", "stopping_rule"):
            _text(item[name], field + "." + name)
        if _cites(item["cites"], field + ".cites") != item["cites"]:
            raise PlanInvalid(
                PLAN_INVALID, field + ".cites", "malformed cite", "cite as listed"
            )
        if "recipe" in item and (
            type(item["recipe"]) is not dict
            or len(canonical(item["recipe"])) > MAX_RECIPE_BYTES
        ):
            raise PlanInvalid(
                PLAN_INVALID,
                field + ".recipe",
                "a recipe is one JSON object",
                "send the recipe object",
            )
    if _pins(plan["pins_considered"]) != plan["pins_considered"]:
        raise PlanInvalid(
            PLAN_INVALID, "pins_considered", "malformed", "name each pin once"
        )
    return plan


def plan_digest(plan):
    """A plan's content address."""
    return digest(canonical(plan))


def _card(library, card_id):
    """The card `library` holds under `card_id`, or None. `library` is a
    `MinerLibrary` (`card(card_id)`), or anything with that method, including
    a literature view whose `card` answers a lit_card-shaped result."""
    try:
        found = library.card(card_id)
    except (KeyError, LookupError, ValueError):
        return None
    if type(found) is not dict:
        return None
    if type(found.get("card")) is dict:
        return found["card"] if found.get("status", "OK") == "OK" else None
    return found if found.get("card_id", card_id) == card_id else None


def validate_plan(plan, *, library, curation):
    """(True, None) for a plan the miner's literature supports, else
    (False, refusal) with its closed code (`refusal`).

    `curation` is the campaign's frozen `{pins, bans, digest}`: no cite may
    be banned, every pin must be in `pins_considered`, and every cited card
    must be one `library` holds, under its own origin."""
    try:
        check_shape(plan)
        bans = set(curation.get("bans") or ())
        pins = list(curation.get("pins") or ())
        for index, item in enumerate(plan["hypotheses"]):
            for cite in item["cites"]:
                field = f"hypotheses[{index}].cites"
                if cite["card_id"] in bans:
                    raise PlanInvalid(
                        CARD_BANNED,
                        field,
                        "the plan cites a card the miner banned: " + cite["card_id"],
                        "drop that card; a banned card is never cited",
                    )
                card = _card(library, cite["card_id"])
                if card is None:
                    raise PlanInvalid(
                        CARD_NOT_FOUND,
                        field,
                        "no card with this id: " + cite["card_id"],
                        "cite only cards lit_search or lit_card returned",
                    )
                if card.get("origin") != cite["origin"]:
                    raise PlanInvalid(
                        PLAN_INVALID,
                        field,
                        "the cited origin is not the card's own: " + cite["card_id"],
                        "cite each card with the origin lit_card shows",
                    )
        considered = {item["card_id"] for item in plan["pins_considered"]}
        missing = [pin for pin in pins if pin not in considered]
        if missing:
            raise PlanInvalid(
                PLAN_INVALID,
                "pins_considered",
                "the plan leaves out a pinned card: " + missing[0],
                "name every card the miner pinned in pins_considered, with how "
                "you considered it",
            )
        parent = plan["parent"]
        if parent is not None and callable(getattr(library, "plan", None)):
            try:
                found = library.plan(parent)
            except (KeyError, LookupError, ValueError):
                found = None
            if found is None:
                raise PlanInvalid(
                    PLAN_NOT_FOUND,
                    "parent",
                    "the parent plan is not in the miner's library",
                    "name a plan the library lists",
                )
    except PlanInvalid as invalid:
        return False, invalid.refusal()
    return True, None


def new_version(plan, *, parent, created_by="miner", **changes):
    """A miner's edit of `plan`: a new plan with `parent` (the edited plan's
    digest) and `created_by`, with `changes` (hypotheses, pins_considered)
    applied. Edited hypotheses are listed best first and ranked by their
    place in that list (a `rank` they carry is replaced). The edited plan
    itself is never changed."""
    if set(changes) - {"hypotheses", "pins_considered"}:
        raise PlanInvalid(
            PLAN_INVALID,
            "plan",
            "an edit changes hypotheses and pins_considered only",
            "edit only those fields",
        )
    check_shape(plan)
    hypotheses = changes.get("hypotheses", plan["hypotheses"])
    if type(hypotheses) is list and all(type(item) is dict for item in hypotheses):
        hypotheses = [
            {**item, "rank": index + 1} for index, item in enumerate(hypotheses)
        ]
    return document(
        challenge=plan["challenge"],
        hypotheses=hypotheses,
        pins_considered=changes.get("pins_considered", plan["pins_considered"]),
        parent=parent,
        created_by=created_by,
    )
