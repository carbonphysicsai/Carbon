"""The challenge-pipeline stage a Graphite campaign runs at.

The Challenge Roadmap gives Graphite a per-stage permission ledger
(`carbon/challenge_pipeline/graphite_ledger.json`, protocol draft §6): which
of Graphite's roles may act at which stage, with the frozen run admitting
none. A stage profile binds three things:
- one stage of that ledger;
- the ledger's exact bytes;
- the challenge's construction permission inventory.

Its digest is the campaign's profile in the controller (`register_campaign`
and `TaskSpec.profile_digest`). `GraphiteProvider(stage_profile=...)` then
refuses a role the stage does not admit, a task carrying another profile,
and a ledger that has changed under it (CHALLENGE-PROTOCOL-04, PROTO4-D1).
"""

from __future__ import annotations

from pathlib import Path

from carbon.challenge_pipeline.graphite_ledger import LEDGER, load_ledger
from carbon.development_session.profile import canonical, digest

SCHEMA = "carbon.graphite.stage-profile.v1"
KEYS = {"schema", "challenge", "stage", "ledger_digest", "permissions_digest"}


def ledger_digest(path=LEDGER):
    return digest(Path(path).read_bytes())


def stage_profile(stage, *, ledger_path=LEDGER):
    """The profile for one stage, for battery: the only challenge whose
    permission inventory is defined (`study.permission_inventory`)."""
    from carbon.agent_campaign import study

    if stage not in load_ledger(ledger_path)["stages"]:
        raise ValueError("unknown stage: " + str(stage))
    return {
        "schema": SCHEMA,
        "challenge": study.CHALLENGE,
        "stage": stage,
        "ledger_digest": ledger_digest(ledger_path),
        "permissions_digest": study._digest(study.permission_inventory()),
    }


def profile_digest(profile):
    return digest(canonical(profile))


def check(profile, *, ledger_path=LEDGER):
    """A well-formed profile whose ledger is the one on disk. Returns the
    ledger. Raises ValueError otherwise."""
    if type(profile) is not dict or set(profile) != KEYS or profile["schema"] != SCHEMA:
        raise ValueError("stage_profile_malformed")
    ledger = load_ledger(ledger_path)
    if profile["ledger_digest"] != ledger_digest(ledger_path):
        raise ValueError("stage_ledger_changed")
    if profile["stage"] not in ledger["stages"]:
        raise ValueError("stage_unknown")
    return ledger
