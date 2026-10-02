"""One Challenge, as Graphite's staged campaigns see it (CHALLENGE-PROTOCOL-04,
generalization; OWNER-CHALLENGE-ROADMAP-03).

The stage profile (`stage.py`), the Attacker (`attack.py`) and its runner
(`phase4.py`) are Challenge-neutral. What is specific to one Challenge comes
from three places, and nowhere else:

- **Its Graphite record**, `challenges/<contract token>.json`:
  - its pipeline family and the label its brief uses;
  - its committed test suite v1 coverage report. The suite map it was run
    under is the suite's own record of the Challenge
    (`carbon/challenge_pipeline/suite_maps/<contract token>.json`);
  - any Challenge-specific wording of a suite vector;
  - the Attacker campaign: identities, grant, ceiling and per-session call
    cap.
- **Its adapter**, the module the record names under `adapters/`, with these
  functions:
  - `permission_inventory()`: the construction permission inventory. Its
    `profile` (`level-N`) is the construction level the contract admits.
  - `public_identity()`: the public development Challenge's id and version,
    shown to the agent.
  - `admission_refusals(strategy)`: Carbon's own admission gate. It returns
    the refusal codes for a recipe object, empty when Carbon would rebuild
    it. A gate that cannot tell because its contract record is not current
    returns `construction_contract_unrecorded` first.
  - `code_run_seconds()`: the wall allowance one sandbox code run may ask
    for.
  - `recipe_outside_contract()`: a recipe its contract refuses, for the dry
    run.
- **Its pipeline record**, `carbon/challenge_pipeline/records/<family>.json`.
  Its `construction` block is the level the pipeline has recorded
  (`challenge_pipeline.ladder`). It must name the same contract and agree
  with the inventory's level, or nothing runs.

Battery is the first instance (`adapters/battery.py`), not the design. A
record grants nothing: grants, ceilings and stage gates keep their own
authority.
"""

from __future__ import annotations

import importlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCHEMA = "carbon.graphite.challenge.v1"
HERE = Path(__file__).parent
RECORDS = HERE / "challenges"
REPOSITORY = HERE.parents[2]
PIPELINE_RECORDS = REPOSITORY / "carbon" / "challenge_pipeline" / "records"
ADAPTERS = "carbon.agent_campaign.graphite.adapters."
KEYS = {
    "schema",
    "challenge",
    "family",
    "label",
    "adapter",
    "suite_report",
    "attack_goals",
    "attacker_campaign",
}
CAMPAIGN_KEYS = {
    "campaign",
    "workspace",
    "credential_ref",
    "grant",
    "ceiling_usd",
    "session_turns",
    "authority",
}
ADAPTER_FUNCTIONS = (
    "permission_inventory",
    "public_identity",
    "admission_refusals",
    "code_run_seconds",
    "recipe_outside_contract",
)
TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
LEVEL_PROFILE = re.compile(r"^level-([0-5])$")
#: Challenges registered in this process ahead of the records on disk: test
#: fixtures only. A live runner reads the records.
REGISTERED = {}


class ChallengeError(ValueError):
    """A Challenge's record, adapter or pipeline record is unusable. The
    message is a typed code."""


def _text(value):
    return isinstance(value, str) and value.strip() != ""


@dataclass(frozen=True, eq=False)
class Challenge:
    token: str
    family: str
    label: str
    suite_report: str
    attack_goals: dict
    campaign: dict
    construction: dict
    adapter: object

    def permission_inventory(self):
        inventory = self.adapter.permission_inventory()
        if type(inventory) is not dict or inventory.get("challenge") != self.token:
            raise ChallengeError("inventory_for_another_challenge")
        return inventory

    def construction_level(self, inventory=None):
        """The construction level the campaign runs at: the inventory's
        profile, which must be the level the pipeline record has recorded."""
        inventory = self.permission_inventory() if inventory is None else inventory
        match = LEVEL_PROFILE.match(str(inventory.get("profile")))
        if not match:
            raise ChallengeError("inventory_profile_not_a_ladder_level")
        level = int(match.group(1))
        if self.construction.get("level") != level:
            raise ChallengeError("construction_level_disagrees_with_pipeline_record")
        return level

    def public_identity(self):
        identity = self.adapter.public_identity()
        if type(identity) is not dict or set(identity) != {"id", "version"}:
            raise ChallengeError("public_identity_is_id_and_version")
        return identity

    def admission_refusals(self, strategy):
        refusals = self.adapter.admission_refusals(strategy)
        if not isinstance(refusals, list | tuple) or not all(
            _text(code) for code in refusals
        ):
            raise ChallengeError("admission_refusals_are_codes")
        return list(refusals)

    def code_run_seconds(self):
        seconds = self.adapter.code_run_seconds()
        if type(seconds) is not int or seconds < 1:
            raise ChallengeError("code_run_seconds_is_a_positive_integer")
        return seconds

    def recipe_outside_contract(self):
        return self.adapter.recipe_outside_contract()


def from_record(document, adapter, construction):
    """A Challenge from its Graphite record, its adapter and its pipeline
    record's `construction` block. Raises ChallengeError."""
    if type(document) is not dict or set(document) != KEYS:
        raise ChallengeError("challenge_record_keys")
    if document["schema"] != SCHEMA:
        raise ChallengeError("challenge_record_schema")
    token = document["challenge"]
    if not (isinstance(token, str) and TOKEN.match(token)):
        raise ChallengeError("challenge_is_a_contract_token")
    for key in ("family", "label", "suite_report"):
        if not _text(document[key]):
            raise ChallengeError("challenge_record_names_its_" + key)
    goals = document["attack_goals"]
    if type(goals) is not dict or not all(
        re.fullmatch(r"A[1-8]", key) and _text(text) for key, text in goals.items()
    ):
        raise ChallengeError("attack_goals_reword_suite_vectors")
    campaign = document["attacker_campaign"]
    if type(campaign) is not dict or set(campaign) != CAMPAIGN_KEYS:
        raise ChallengeError("attacker_campaign_keys")
    for key in ("campaign", "workspace", "credential_ref", "authority"):
        if not _text(campaign[key]):
            raise ChallengeError("attacker_campaign_names_its_" + key)
    grant = campaign["grant"]
    if type(grant) is not dict or set(grant) != {"id", "file"}:
        raise ChallengeError("attacker_grant_is_id_and_file")
    try:
        ceiling = Decimal(campaign["ceiling_usd"])
    except (InvalidOperation, TypeError):
        raise ChallengeError("attacker_ceiling_is_decimal_usd") from None
    if not ceiling > 0:
        raise ChallengeError("attacker_ceiling_is_decimal_usd")
    turns = campaign["session_turns"]
    if type(turns) is not int or turns < 1:
        raise ChallengeError("attacker_session_turns_is_a_positive_integer")
    if not all(callable(getattr(adapter, name, None)) for name in ADAPTER_FUNCTIONS):
        raise ChallengeError("adapter_lacks_a_function")
    if type(construction) is not dict or construction.get("challenge") != token:
        raise ChallengeError("pipeline_record_names_another_contract")
    return Challenge(
        token=token,
        family=document["family"],
        label=document["label"],
        suite_report=document["suite_report"],
        attack_goals=dict(goals),
        campaign=dict(campaign),
        construction=dict(construction),
        adapter=adapter,
    )


def _read(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ChallengeError(code) from None


def pipeline_construction(family, records=PIPELINE_RECORDS):
    """The `construction` block of a family's pipeline record."""
    if not (isinstance(family, str) and TOKEN.match(family)):
        raise ChallengeError("pipeline_family_unknown")
    record = _read(Path(records) / (family + ".json"), "pipeline_record_missing")
    construction = record.get("construction") if type(record) is dict else None
    if type(construction) is not dict:
        raise ChallengeError("pipeline_record_has_no_construction_block")
    return construction


def record_path(token):
    if not (isinstance(token, str) and TOKEN.match(token)):
        raise ChallengeError("challenge_is_a_contract_token")
    return RECORDS / (token + ".json")


def get(token):
    """The Challenge named by its contract token: a registered fixture, else
    its record on disk with its adapter and pipeline record."""
    if token in REGISTERED:
        return REGISTERED[token]
    path = record_path(token)
    if not path.is_file():
        raise ChallengeError("challenge_not_recorded")
    document = _read(path, "challenge_record_unreadable")
    name = document.get("adapter") if type(document) is dict else None
    if not (isinstance(name, str) and name.startswith(ADAPTERS)):
        raise ChallengeError("adapter_outside_the_adapters_package")
    try:
        adapter = importlib.import_module(name)
    except ImportError:
        raise ChallengeError("adapter_not_importable") from None
    return from_record(document, adapter, pipeline_construction(document["family"]))


def resolve(challenge):
    """A Challenge, given one or its contract token."""
    return challenge if isinstance(challenge, Challenge) else get(challenge)


def recorded():
    """The contract tokens with a Graphite record, sorted."""
    return sorted(path.stem for path in RECORDS.glob("*.json"))


def protocol_challenge():
    """The Challenge that defines the protocol in Phase 1: the one whose
    pipeline family is the pipeline's protocol family."""
    from carbon.challenge_pipeline.state import PROTOCOL_FAMILY

    for token in recorded():
        document = _read(record_path(token), "challenge_record_unreadable")
        if type(document) is dict and document.get("family") == PROTOCOL_FAMILY:
            return get(token)
    raise ChallengeError("no_recorded_challenge_defines_the_protocol")
