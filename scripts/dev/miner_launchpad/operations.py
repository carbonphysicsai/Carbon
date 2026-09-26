"""Every miner operation and its gates, defined once. The doors are callers.

A miner reaches Carbon through a browser, through their own MCP client, or by
letting Carbon's autonomous agent work. Each is a caller of this table: the
browser's routes and the MCP tools are generated from it, and the agent's
selection goes through the same freeze-and-submit a person's does. A door
cannot hold an operation or a gate the others lack, because a door has no
operations of its own to hold.

Gates run in one fixed order, and registration comes before any operation
that writes. That is enforced when the table is built, not checked afterward:
an operation declared without registration ahead of its body fails at import.
The body receives an `Admitted`, which only `perform` can construct, so there
is no way to reach a body with the gates skipped.

The DEVELOPMENT submit here is a signed message to the local development
service. It writes nothing to the chain. Official submission is not an
operation on either door.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# One refusal type for every door: a browser sees its status, MCP its code.
from scripts.dev.miner_launchpad.controller import Rejected

#: Every request field any operation takes, with its JSON type and meaning.
#: Both doors read these: the browser validates bodies against them and MCP
#: builds its tool schemas from them, so a field cannot mean two things.
FIELDS = {
    "agent": ("string", "Who selects: autonomous (Carbon's agent) or none (you)."),
    "idempotency_key": ("string", "16-80 letters, digits, - or _; a retry replays."),
    "budget": ("object", "Optional ceilings, elapsed_seconds or final_reserve."),
    "review_digest": ("string", "The launch review you accepted, when one applies."),
    "profile": ("string", "Your runner profile id, to confirm which one."),
    "campaign": ("string", "The campaign id."),
    "strategy": (
        "object",
        "A recipe: schema_version, challenge_id, backbone, parameters.",
    ),
    "reason": ("string", "Why this candidate: what your practice showed."),
    "used_feedback": ("boolean", "Whether prior final feedback informed it."),
    "hypothesis": ("string", "What this trial tests."),
    "expected_effect": ("string", "What you expect it to show."),
    "action": ("string", "stop, pause or reconcile."),
    "challenge": (
        "string",
        (
            "The Challenge id to research (carbon_challenges_v1__list). "
            "Required: there is no default Challenge."
        ),
    ),
    "challenge_version": ("string", "The exact version of that Challenge."),
}

#: The gates, in the only order they run. `replay` is read-only and precedes
#: registration so a lost response replays without a chain read.
GATE_ORDER = ("request", "profile", "replay", "registration", "campaign")
_TOKEN = object()


@dataclass(frozen=True)
class Admitted:
    """Proof that every gate of an operation passed. Only `perform` builds one."""

    token: object
    host: object
    profile: dict
    miner: object
    campaign: object

    def __post_init__(self):
        if self.token is not _TOKEN:
            raise TypeError("an Admitted comes only from perform()")


@dataclass(frozen=True)
class Operation:
    name: str
    summary: str
    required: frozenset
    optional: frozenset
    gates: tuple
    #: Whether the operation starts or extends work - a campaign, a trial, a
    #: submission. Every one that does is admitted by registration before its
    #: body runs. One that only reads or withdraws (observe, halt) is not:
    #: a miner can always see and stop their own campaign.
    admits_work: bool = True

    def __post_init__(self):
        if not self.required | self.optional <= set(FIELDS):
            raise ValueError(f"{self.name}: every field is declared in FIELDS")
        if list(self.gates) != [g for g in GATE_ORDER if g in self.gates]:
            raise ValueError(f"{self.name}: gates run in the fixed order")
        if self.gates[:2] != ("request", "profile"):
            raise ValueError(f"{self.name}: request and profile gates come first")
        if self.admits_work and "registration" not in self.gates:
            raise ValueError(f"{self.name}: registration admits all new work")


OPERATIONS = {
    op.name: op
    for op in (
        Operation(
            "launch",
            "Create a research campaign. agent=autonomous lets Carbon's agent "
            "research, select and submit; agent=none leaves every step to you.",
            frozenset({"agent", "idempotency_key"}),
            frozenset(
                {"budget", "review_digest", "profile", "challenge", "challenge_version"}
            ),
            ("request", "profile", "replay", "registration"),
        ),
        Operation(
            "options",
            "Every launch-time choice with its true availability now: who "
            "selects, each model family's registry verdict, and the research "
            "lanes this host has. Reads only.",
            frozenset(),
            frozenset(),
            ("request", "profile"),
            admits_work=False,
        ),
        Operation(
            "observe",
            "The campaign's state, epochs, practice results and any frozen "
            "candidate or final feedback. Reads only.",
            frozenset({"campaign"}),
            frozenset(),
            ("request", "profile", "campaign"),
            admits_work=False,
        ),
        Operation(
            "practice",
            "Run one practice trial of a registered recipe in the campaign: "
            "real training on public TRAIN data, self-reported. A candidate "
            "must have a practice result before it can be frozen.",
            frozenset({"campaign", "strategy", "hypothesis"}),
            frozenset({"expected_effect"}),
            ("request", "profile", "registration", "campaign"),
        ),
        Operation(
            "halt",
            "Stop, pause or reconcile a campaign. Always available to its "
            "owner: withdrawing work never needs registration.",
            frozenset({"campaign", "action"}),
            frozenset(),
            ("request", "profile", "campaign"),
            admits_work=False,
        ),
        Operation(
            "resume",
            "Resume a paused or interrupted campaign.",
            frozenset({"campaign"}),
            frozenset(),
            ("request", "profile", "registration", "campaign"),
        ),
        Operation(
            "freeze_candidate",
            "Freeze a recipe you have practiced as this epoch's candidate. "
            "Refused for a recipe with no practice result.",
            frozenset({"campaign", "strategy", "reason"}),
            frozenset({"used_feedback"}),
            ("request", "profile", "registration", "campaign"),
        ),
        Operation(
            "submit",
            "DEVELOPMENT submit of your frozen candidate: an independent "
            "reconstruction and comparison with the control, against the local "
            "development service. Nothing reaches the chain.",
            frozenset({"campaign"}),
            frozenset(),
            ("request", "profile", "registration", "campaign"),
        ),
    )
}


def _closed(op, request):
    if type(request) is not dict:
        raise Rejected("closed_request_required")
    keys = set(request)
    if not op.required <= keys <= op.required | op.optional:
        raise Rejected("closed_request_required")


def _registered(host, profile):
    from carbon.development_session.chain_onboarding import OnboardingFailure

    try:
        return host.registration(profile)
    except OnboardingFailure as failure:
        raise Rejected(
            *{
                "NOT_REGISTERED": ("registration_required", 403),
                "CHAIN_UNAVAILABLE": ("registration_unreadable", 503),
                "WRONG_NETWORK": ("registration_wrong_network", 409),
            }.get(failure.reason, ("registration_unreadable", 503))
        ) from None


def perform(host, name, request):
    """Run one operation for one principal through its gates, in order.

    `host` is the campaign host both doors share (`RunnerAdapter`): it
    supplies the profile, the registration read, campaign lookup and the
    bodies' effects. Returns the operation's result or raises `Rejected`.
    """
    op = OPERATIONS.get(name)
    if op is None:
        raise Rejected("unknown_operation", 404)
    profile = miner = campaign = None
    for gate in op.gates:
        if gate == "request":
            _closed(op, request)
        elif gate == "profile":
            try:
                # New work needs an enabled, runnable profile. Reading and
                # withdrawing need only to know whose campaigns these are, so
                # a disabled profile can still see and stop its campaigns.
                profile = host.configured() if op.admits_work else host.owner()
            except Rejected:
                raise
            except Exception:  # noqa: BLE001 - an unreadable profile, never its content
                raise Rejected("research_profile_unavailable", 409) from None
            if "profile" in request and request["profile"] != profile["profile_id"]:
                raise Rejected("research_profile_mismatch", 409)
        elif gate == "replay":
            replayed = host.replayed(profile, request)
            if replayed is not None:
                return replayed
        elif gate == "registration":
            miner = _registered(host, profile)
        elif gate == "campaign":
            campaign = host.owned_campaign(request["campaign"])
            # A retired-grant campaign stays observable and can be stopped and
            # cleaned up, but no new work is ever admitted to it.
            if op.admits_work and campaign["kind"] != "product":
                raise Rejected("retired_grant_campaign", 409)
    # The body is the host's `<operation>_admitted`, found by name: the table
    # names it, and no door supplies one of its own.
    body = getattr(host, op.name + "_admitted")
    return body(Admitted(_TOKEN, host, profile, miner, campaign), request)


def describe():
    """The public shape of every operation, for both doors' listings."""
    return [
        {
            "operation": op.name,
            "summary": op.summary,
            "required": sorted(op.required),
            "optional": sorted(op.optional),
            "gates": list(op.gates),
            "admits_work": op.admits_work,
        }
        for op in OPERATIONS.values()
    ]


def campaign_root(admitted):
    """The admitted campaign's root."""
    return Path(admitted.campaign["root"])


def strategy_value(request):
    """A strategy supplied as an object, or as the JSON text MCP clients send."""
    value = request["strategy"]
    if type(value) is str:
        try:
            value = json.loads(value)
        except ValueError:
            raise Rejected("strategy_json_invalid") from None
    if type(value) is not dict:
        raise Rejected("strategy_object_required")
    return value
