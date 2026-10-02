"""The challenge-pipeline stage, and the construction level, a Graphite
campaign runs at.

The Challenge Roadmap gives Graphite a per-stage permission ledger
(`carbon/challenge_pipeline/graphite_ledger.json`, protocol draft §6): which
of Graphite's roles may act at which stage, with the frozen run admitting
none. A stage profile binds, for one Challenge (`challenge.py`):
- one stage of that ledger, and the ledger's exact bytes;
- the Challenge's construction permission inventory, by digest;
- the construction level the campaign runs at (Challenge Roadmap rev 2.2, the
  construction ladder): the inventory's profile, which must agree with the
  level the Challenge's pipeline record has recorded;
- the runner's own permission profile, when it has one (`runner_profile`):
  for #504's Constructor, its Level-0 profile (`phase3.permission_profile`).
  It must name the same level, and the same Challenge if it names one. The
  Attacker has none beyond its role's closed tool manifest, which its brief
  pins (OWNER-CHALLENGE-STEP4-01, third amendment: revision 1, PROTO4-D11).

Its digest is the campaign's profile in the controller (`register_campaign`
and `TaskSpec.profile_digest`). `GraphiteProvider(stage_profile=...)` then
refuses a role the stage does not admit, a task carrying another profile, a
ledger that has changed under it, and a session whose recorded level or
permissions differ from the Challenge's inventory now (CHALLENGE-PROTOCOL-04,
PROTO4-D1 and PROTO4-D9). Whether a runner's own profile is still current is
that runner's check. Nothing here is specific to one Challenge.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from carbon.challenge_pipeline.graphite_ledger import LEDGER, load_ledger
from carbon.development_session.profile import canonical, digest

from . import challenge as challenges

SCHEMA = "carbon.graphite.stage-profile.v3"
KEYS = {
    "schema",
    "challenge",
    "stage",
    "construction_level",
    "ledger_digest",
    "permissions_digest",
    "runner_profile",
}


def ledger_digest(path=LEDGER):
    return digest(Path(path).read_bytes())


def permissions_digest(inventory):
    """The permission inventory's digest, as the study sheet pins it."""
    body = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def stage_profile(stage, challenge, *, runner_profile=None, ledger_path=LEDGER):
    """The profile for one stage of one Challenge (a `challenge.Challenge` or
    its contract token), composed with the runner's own permission profile
    when it has one."""
    challenge = challenges.resolve(challenge)
    if stage not in load_ledger(ledger_path)["stages"]:
        raise ValueError("unknown stage: " + str(stage))
    inventory = challenge.permission_inventory()
    profile = {
        "schema": SCHEMA,
        "challenge": challenge.token,
        "stage": stage,
        "construction_level": challenge.construction_level(inventory),
        "ledger_digest": ledger_digest(ledger_path),
        "permissions_digest": permissions_digest(inventory),
        "runner_profile": runner_profile,
    }
    _check_runner(profile)
    return profile


def _check_runner(profile):
    """A runner's own profile constructs at the stage profile's level, for
    its Challenge: never wider, never another."""
    runner = profile["runner_profile"]
    if runner is None:
        return
    if type(runner) is not dict or type(runner.get("level")) is not int:
        raise ValueError("runner_profile_names_no_level")
    if runner["level"] != profile["construction_level"]:
        raise ValueError("runner_profile_level_differs")
    contract = runner.get("construction_contract")
    if type(contract) is dict and contract.get("challenge") != profile["challenge"]:
        raise ValueError("runner_profile_for_another_challenge")


def profile_digest(profile):
    return digest(canonical(profile))


def check(profile, *, ledger_path=LEDGER):
    """A well-formed profile whose ledger is the one on disk and whose level
    and permissions are the Challenge's now. Returns the ledger. Raises
    ValueError with a typed code otherwise."""
    if (
        type(profile) is not dict
        or set(profile) != KEYS
        or profile["schema"] != SCHEMA
        or type(profile["construction_level"]) is not int
    ):
        raise ValueError("stage_profile_malformed")
    ledger = load_ledger(ledger_path)
    if profile["ledger_digest"] != ledger_digest(ledger_path):
        raise ValueError("stage_ledger_changed")
    if profile["stage"] not in ledger["stages"]:
        raise ValueError("stage_unknown")
    challenge = challenges.get(profile["challenge"])
    inventory = challenge.permission_inventory()
    if challenge.construction_level(inventory) != profile["construction_level"]:
        raise ValueError("construction_level_mismatch")
    if permissions_digest(inventory) != profile["permissions_digest"]:
        raise ValueError("stage_permissions_changed")
    _check_runner(profile)
    return ledger
