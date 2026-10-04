"""One Challenge, as Graphite's attack campaigns see it (OWNER-GRAPHITE-ATTACKER-01;
the pattern of CHALLENGE-PROTOCOL-04's generalization, adapted to main).

Graphite's Attacker (phase 4) and the attack engine
(`carbon.agent_campaign.attack`) are Challenge-neutral. What is specific to
one Challenge comes from three places, and nowhere else:

- **Its Graphite record**, `challenges/<contract token>.json`:
  - its pipeline family and the label its brief uses;
  - its committed test suite v1 coverage report. The suite map it was run
    under is the suite's own record of the Challenge
    (`carbon/challenge_pipeline/suite_maps/<contract token>.json`);
  - any Challenge-specific wording of a suite vector (`attack_goals`);
  - the Attacker campaign: its identities and its grant. The grant binds the
    money and the elapsed time; there is no call cap.
- **Its attack adapter**, registered for the Challenge at its construction
  level (`attack.adapter.ADAPTERS[(challenge, level)]`). Besides the attack
  protocol it carries the session surface a Graphite session needs
  (`attack.adapter.SessionSurface`):
  - `permission_inventory()`: the construction permission inventory. Its
    `profile` (`level-N`) is the construction level the contract admits;
  - `public_identity()`: the public development Challenge's id and version;
  - `admission_refusals(strategy)`: Carbon's own admission gate, the refusal
    codes for a recipe object, empty when Carbon would rebuild it;
  - `code_run_seconds()`: the wall allowance one sandbox code run may ask
    for;
  - `recipe_outside_contract()`: a recipe its contract refuses, for the dry
    run.
- **Its pipeline record**, `carbon/challenge_pipeline/records/<family>.json`.
  Its `construction` block is the level the pipeline has recorded
  (`challenge_pipeline.ladder`). It must name the same contract and agree
  with the adapter's level and the inventory's profile, or nothing runs.

Battery is the first instance, not the design. A record grants nothing:
grants, ceilings and pipeline-stage gates keep their own authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from carbon.agent_campaign.attack import adapter as attack_adapters

SCHEMA = "carbon.graphite.challenge.v2"
HERE = Path(__file__).parent
RECORDS = HERE / "challenges"
REPOSITORY = HERE.parents[2]
PIPELINE_RECORDS = REPOSITORY / "carbon" / "challenge_pipeline" / "records"
KEYS = {
    "schema",
    "challenge",
    "family",
    "label",
    "suite_report",
    "attack_goals",
    "attacker_campaign",
}
CAMPAIGN_KEYS = {"campaign", "workspace", "credential_ref", "grant", "authority"}
SESSION_FUNCTIONS = attack_adapters.SESSION_FUNCTIONS
TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
GRANT_ID = re.compile(r"^[A-Z0-9][A-Z0-9-]*$")
LEVEL_PROFILE = re.compile(r"^level-([0-5])$")
#: Challenges registered in this process ahead of the records on disk: test
#: fixtures only. A live runner reads the records.
REGISTERED = {}


class ChallengeError(ValueError):
    """A Challenge's record, adapter or pipeline record is unusable. The
    message is a typed code."""


def _text(value):
    return isinstance(value, str) and value.strip() != ""


def _relative(value):
    if not _text(value):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in value


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

    @property
    def level(self):
        """The construction level the pipeline has recorded, which the
        adapter attacks."""
        return self.construction["level"]

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


def check_record(document):
    """A Graphite record's own shape, before any adapter is resolved. Returns
    the document; raises ChallengeError."""
    if type(document) is not dict or set(document) != KEYS:
        raise ChallengeError("challenge_record_keys")
    if document["schema"] != SCHEMA:
        raise ChallengeError("challenge_record_schema")
    token = document["challenge"]
    if not (isinstance(token, str) and TOKEN.match(token)):
        raise ChallengeError("challenge_is_a_contract_token")
    for key in ("family", "label"):
        if not _text(document[key]):
            raise ChallengeError("challenge_record_names_its_" + key)
    if not _relative(document["suite_report"]):
        raise ChallengeError("challenge_record_names_its_suite_report")
    goals = document["attack_goals"]
    if type(goals) is not dict or not all(
        re.fullmatch(r"A[1-8]", key) and _text(text) for key, text in goals.items()
    ):
        raise ChallengeError("attack_goals_reword_suite_vectors")
    campaign = document["attacker_campaign"]
    if type(campaign) is not dict or set(campaign) != CAMPAIGN_KEYS:
        # A call cap or a second copy of the grant's ceiling is refused: the
        # grant's money and elapsed time bind (OWNER-GRAPHITE-ATTACKER-01).
        raise ChallengeError("attacker_campaign_keys")
    for key in ("campaign", "workspace", "credential_ref", "authority"):
        if not _text(campaign[key]):
            raise ChallengeError("attacker_campaign_names_its_" + key)
    grant = campaign["grant"]
    if (
        type(grant) is not dict
        or set(grant) != {"id", "file"}
        or not (isinstance(grant["id"], str) and GRANT_ID.match(grant["id"]))
        or not _relative(grant["file"])
        or PurePosixPath(grant["file"]).name != grant["id"] + ".json"
    ):
        raise ChallengeError("attacker_grant_is_id_and_its_file")
    from carbon.agent_campaign.graphite import tools

    if tools.protected(_brief(document)):
        raise ChallengeError("challenge_record_brief_names_protected_material")
    return document


#: The record fields an Attacker brief may carry. The `attacker_campaign`
#: block (identities, credential reference, grant) is campaign configuration
#: for the driver; it never goes to a model or through the Graphite toolbox,
#: whose protected-material check refuses it.
BRIEF_KEYS = ("challenge", "label", "attack_goals")


def _brief(document):
    return {key: document[key] for key in BRIEF_KEYS}


def brief(document):
    """The brief-facing fields of a checked record. They pass
    `graphite.tools.protected`; nothing else from the record goes into an
    Attacker brief."""
    return _brief(check_record(document))


def from_record(document, adapter, construction):
    """A Challenge from its Graphite record, its attack adapter and its
    pipeline record's `construction` block. Raises ChallengeError."""
    check_record(document)
    token = document["challenge"]
    if type(construction) is not dict or construction.get("challenge") != token:
        raise ChallengeError("pipeline_record_names_another_contract")
    level = construction.get("level")
    if type(level) is not int:
        raise ChallengeError("pipeline_record_has_no_construction_level")
    try:
        attack_adapters.validate(adapter, held_out=False)
    except attack_adapters.AdapterError as refused:
        raise ChallengeError("attack_adapter_refused: " + refused.code) from None
    if (adapter.challenge_id, adapter.level) != (token, level):
        raise ChallengeError("attack_adapter_for_another_challenge_or_level")
    if not all(callable(getattr(adapter, name, None)) for name in SESSION_FUNCTIONS):
        raise ChallengeError("adapter_lacks_the_session_surface")
    return Challenge(
        token=token,
        family=document["family"],
        label=document["label"],
        suite_report=document["suite_report"],
        attack_goals=dict(document["attack_goals"]),
        campaign=dict(document["attacker_campaign"]),
        construction=dict(construction),
        adapter=adapter,
    )


def _read(path, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ChallengeError(code) from None


def pipeline_construction(family, records=None):
    """The `construction` block of a family's pipeline record."""
    if not (isinstance(family, str) and TOKEN.match(family)):
        raise ChallengeError("pipeline_family_unknown")
    records = PIPELINE_RECORDS if records is None else records
    record = _read(Path(records) / (family + ".json"), "pipeline_record_missing")
    construction = record.get("construction") if type(record) is dict else None
    if type(construction) is not dict:
        raise ChallengeError("pipeline_record_has_no_construction_block")
    return construction


def record_path(token):
    if not (isinstance(token, str) and TOKEN.match(token)):
        raise ChallengeError("challenge_is_a_contract_token")
    return RECORDS / (token + ".json")


def load_record(token):
    """A Challenge's Graphite record, checked."""
    path = record_path(token)
    if not path.is_file():
        raise ChallengeError("challenge_not_recorded")
    return check_record(_read(path, "challenge_record_unreadable"))


def get(token, *, pipeline_records=None):
    """The Challenge named by its contract token: a registered fixture, else
    its record on disk, its pipeline record and the attack adapter registered
    for it at the level that record names."""
    if token in REGISTERED:
        return REGISTERED[token]
    document = load_record(token)
    construction = pipeline_construction(document["family"], pipeline_records)
    level = construction.get("level")
    if construction.get("challenge") != token:
        raise ChallengeError("pipeline_record_names_another_contract")
    if type(level) is not int:
        raise ChallengeError("pipeline_record_has_no_construction_level")
    try:
        adapter = attack_adapters.get(token, level)
    except attack_adapters.AdapterError as refused:
        if refused.code == "adapter_not_registered":
            raise ChallengeError("attack_adapter_not_registered") from None
        # Any other refusal (a built-in adapter package that failed to
        # import) keeps its own code and its cause.
        raise ChallengeError("attack_adapter_unavailable: " + refused.code) from refused
    return from_record(document, adapter, construction)


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
