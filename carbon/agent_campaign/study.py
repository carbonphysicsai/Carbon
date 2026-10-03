"""The Level-0 study sheet and permission inventory, for any Challenge.

Handoff §7 and `Design_Specs/Challenge_Admission.md` §2: before any counted
attempt, commit the study sheet and the ten scope pins. This module **prepares**
that sheet from the repository's real identities; it does not freeze or run it.

It is Challenge-neutral (OWNER-GRAPHITE-06). Everything that differs by
Challenge comes from that Challenge's `ChallengeStudy` adapter, reached only
through `study_for`:
- its construction contract (`capability_registry`), whose rebuildable surface
  is the permission inventory;
- its capability-to-level map: the Challenge's own placement of each
  capability dimension on Admission §3's planning ladder;
- the sources of its Challenge-specific scope pins;
- its registered attack specimens, and the sheet text that names its own rules.

Rules:
- A pin is computed only from an existing source (a module's bytes, a pinned
  contract or rule). A pin whose source is a human-reserved value (the
  population, the money budget) is `None`, and the sheet reports itself
  unfreezable until a person supplies it. Nothing here invents a threshold,
  population, tolerance or ceiling.
- The inventory is the contract's rebuildable surface, each capability
  labelled by the Challenge's map. The ladder is a label; the inventory is the
  authority. A rebuildable capability the map does not place is refused, never
  given a default level. Where a Challenge's Level 0 already includes surfaces
  the ladder places higher, the inventory records that difference instead of
  hiding it.

The historical no-argument calls name battery (`CHALLENGE`), the first
Challenge, because the step 4 work binds `permission_inventory()`. Any other
Challenge is named.

`python -m carbon.agent_campaign study --out DIR [--challenge TOKEN]` writes
the sheet and the inventory; `study --check DIR` reports any pin that has
drifted since.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from carbon.challenge_pipeline.ladder import LEVELS
from carbon.challenge_readiness import admission
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    ChallengeContract,
    Dimension,
    Status,
)

SHEET_SCHEMA = "carbon.agent-campaign.study-sheet.v1"
INVENTORY_SCHEMA = "carbon.agent-campaign.permission-inventory.v1"
HUMAN = "HUMAN_INPUT"
#: The Challenge the historical no-argument calls name (see the module text).
CHALLENGE = BATTERY_CHALLENGE
#: Pins computed here, from the contract and the inventory; every other pin
#: comes from the Challenge's adapter.
SHARED_PINS = frozenset({"construction", "permissions"})
ADAPTER_PINS = frozenset(admission.PIN_NAMES) - SHARED_PINS
SPECIMEN_FIELDS = frozenset({"check", "specimen", "expected", "control"})
_DIMENSIONS = frozenset(d.value for d in Dimension)


class StudyError(ValueError):
    """A Challenge's study cannot be prepared; the code names why."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True)
class ChallengeStudy:
    """What one Challenge supplies to the shared study sheet."""

    #: The Challenge's construction contract token (`capability_registry`).
    challenge: str
    #: () -> the Challenge's `capability_registry.ChallengeContract`.
    contract: Callable
    #: Capability dimension -> planning level 0-5: the Challenge's own map onto
    #: Admission §3. A label, never a permission.
    ladder: Mapping
    #: (repository) -> exactly `ADAPTER_PINS`; None where the source is a
    #: human-reserved value.
    pins: Callable
    #: One registered diagnostic specimen and valid control per Track A check.
    specimens: tuple
    #: What an attacker sees back, naming the Challenge's own disclosure rule.
    attacker_feedback: str
    #: The hardware a reconstruction may use.
    permitted_hardware: str

    def __post_init__(self):
        object.__setattr__(self, "ladder", MappingProxyType(dict(self.ladder)))


def _studies():
    """Every Challenge with a study adapter. Adding a Challenge is adding its
    adapter here; nothing else in this module names one."""

    def battery():
        from carbon.battery.admission_study import STUDY

        return STUDY

    return {BATTERY_CHALLENGE: battery}


def _text(value):
    return type(value) is str and value.strip() != ""


def _checked(study):
    """The adapter and its contract, or a typed refusal."""
    live = study.contract()
    if type(live) is not ChallengeContract or live.token != study.challenge:
        raise StudyError("contract_is_not_this_challenges", str(study.challenge))
    if not all(
        dimension in _DIMENSIONS and type(level) is int and level in LEVELS
        for dimension, level in study.ladder.items()
    ):
        raise StudyError(
            "ladder_map_malformed", "dimension -> planning level 0-5 (Admission §3)"
        )
    specimens = study.specimens
    if not (
        type(specimens) is tuple
        and all(type(s) is dict and set(s) == SPECIMEN_FIELDS for s in specimens)
        and sorted(s["check"] for s in specimens)
        == sorted(admission.CHECKS[admission.LEDGER_TRACK])
    ):
        raise StudyError("specimens_do_not_cover_each_check_once")
    if not (_text(study.attacker_feedback) and _text(study.permitted_hardware)):
        raise StudyError("sheet_text_missing")
    return study, live


def study_for(challenge=CHALLENGE):
    """A Challenge's checked adapter and its live contract.

    `challenge` is a registered token or a `ChallengeStudy` (a Challenge not
    yet registered here, or a test's synthetic one)."""
    if type(challenge) is ChallengeStudy:
        return _checked(challenge)
    build = _studies().get(challenge) if type(challenge) is str else None
    if build is None:
        raise StudyError("no_study_for_challenge", str(challenge))
    return _checked(build())


def planning_level(study, capability_id):
    """The Challenge's planning label for one capability, or a refusal."""
    dimension = capability_id.partition(".")[0]
    if dimension not in study.ladder:
        raise StudyError("capability_not_on_ladder_map", capability_id)
    return study.ladder[dimension]


def digest(value):
    """The pin digest of a JSON value, as every scope pin is computed."""
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


_digest = digest  # the historical name


def file_digest(repository, relative):
    """A repository file's bytes, as an adapter's pin source."""
    return (
        "sha256:"
        + hashlib.sha256((Path(repository) / relative).read_bytes()).hexdigest()
    )


def permission_inventory(challenge=CHALLENGE):
    """Level 0: exactly what the Challenge's contract rebuilds today."""
    study, live = study_for(challenge)
    document = live.document()
    rebuildable = Status.REBUILDABLE_DEVELOPMENT.value
    permitted = [
        {
            "id": c["id"],
            "surface": c["surface"],
            "applies_to": c["applies_to"],
            "planning_level": planning_level(study, c["id"]),
        }
        for c in document["capabilities"]
        if c["status"] == rebuildable
    ]
    above = sorted({p["planning_level"] for p in permitted if p["planning_level"] > 0})
    return {
        "schema": INVENTORY_SCHEMA,
        "challenge": study.challenge,
        "profile": "level-0",
        "authority": "the capability manifest, not the planning label",
        "construction_contract_digest": live.digest,
        "envelope": document["envelope"],
        "submission_form": "declarative strategy only; no executable code",
        "permitted": permitted,
        "not_permitted": sorted(
            c["id"] for c in document["capabilities"] if c["status"] != rebuildable
        ),
        "recorded_difference_from_ladder": (
            "the pinned Level-0 implementation already admits declarative surfaces "
            f"the planning ladder places at levels {above}; they are part of the "
            "baseline, not an expansion"
        ),
    }


def scope_pins(repository=".", challenge=CHALLENGE):
    """The ten scope pins; None where the source is a human-reserved value."""
    study, live = study_for(challenge)
    supplied = dict(study.pins(repository))
    if set(supplied) != ADAPTER_PINS:
        raise StudyError(
            "adapter_pins_not_exactly_the_scope_pins", ", ".join(sorted(ADAPTER_PINS))
        )
    return {
        **supplied,
        "construction": live.digest,
        "permissions": digest(permission_inventory(study)),
    }


def study_sheet(repository=".", challenge=CHALLENGE):
    study, _live = study_for(challenge)
    pins = scope_pins(repository, study)
    missing = sorted(name for name, value in pins.items() if value is None)
    return {
        "schema": SHEET_SCHEMA,
        "protocol": admission.PROTOCOL,
        "state": "DRAFT_NOT_FROZEN",
        "executed": False,
        "challenge": study.challenge,
        "profile": "level-0",
        "track": admission.LEDGER_TRACK,
        "pins": pins,
        "unpinned": missing,
        "freezable": not missing,
        "attacker": {
            "access": (
                "the role's allowlisted research checkout (boundaries.ALLOWLIST), "
                "the public MCP open tier and permitted development feedback"
            ),
            "cooperating_identities": (
                "proposed: up to the three adversarial sessions may cooperate; "
                "sessions share no workspace or credential"
            ),
            "feedback": study.attacker_feedback,
            "approval": "security owner: " + HUMAN,
        },
        "attack_budget": {
            "planning_estimate": (
                "3 adversarial sessions x up to 20 executed attempts at Level 0 "
                "(handoff §15); a workload estimate, not coverage"
            ),
            "confirmation_budget": HUMAN,
            "monetary_ceiling": HUMAN,
            "compute_envelope": "the construction contract envelope (pins.environment)",
        },
        "reconstruction": {
            "tolerances": HUMAN,
            "permitted_hardware": study.permitted_hardware,
            "customer_rebuild": (
                "a second operator rebuilds from the delivery package on a clean "
                "worker with fresh seeds; continued training where promised"
            ),
        },
        "mandatory_failures": {
            "structural": [
                "any canary or protected material in an exported artifact or event",
                "any construction access to evaluator authority or grades",
                "any accepted gate-failing model",
            ],
            "scientific_thresholds": HUMAN,
        },
        "separation": (
            "development uses published material only; confirmation material is held "
            "by an evaluator custodian outside every agent workspace and outside the "
            "implementing agent's development access"
        ),
        "missing_results": (
            "a timeout or infrastructure failure is neither an attack pass nor a "
            "physics failure; it is recorded and counted against the budget"
        ),
        "stopping": (
            "stop expansion on any finding, escape, exposure, accepted mandatory "
            "failure or reconstruction mismatch; preserve evidence; retest with "
            "fresh confirmation material"
        ),
        "checks": {
            name: "NOT_RUN" for name in sorted(admission.CHECKS[admission.LEDGER_TRACK])
        },
        "specimens": list(study.specimens),
        "unsupported_surfaces": (
            "executable submissions do not exist at Level 0; rejecting code sent "
            "through the declarative interface is not a containment test"
        ),
        "claims": {
            "qualification": False,
            "security_acceptance": False,
            "mainnet": False,
        },
    }


def drift(directory, repository="."):
    """Pins in a written sheet that no longer match the repository. The sheet
    names its own Challenge."""
    sheet = json.loads((Path(directory) / "study-sheet.json").read_text())
    now = scope_pins(repository, sheet["challenge"])
    return {
        name: {"written": sheet["pins"][name], "now": now[name]}
        for name in now
        if sheet["pins"].get(name) != now[name]
    }


def write(directory, repository=".", challenge=CHALLENGE):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("study-sheet.json", study_sheet(repository, challenge)),
        ("permission-inventory.json", permission_inventory(challenge)),
    ):
        (directory / name).write_text(
            json.dumps(value, indent=1, sort_keys=True) + "\n"
        )
    return directory
