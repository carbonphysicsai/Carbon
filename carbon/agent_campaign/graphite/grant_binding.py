"""Graphite grants bound to their Challenge and to main's committed blob.

An owner-approved Graphite grant is accepted for a live run only as the
blob the owner approved: the committed file at a pushed HEAD, equal to the
blob on main, with the grants directory clean (`check_committed_blob`). The
grant format (`carbon.agent-campaign.spending-grant.v1`) has no Challenge
field, so the runners bind each grant to its Challenge here and in
`phase4.PHASE4_GRANTS` (GRAPHITE-GRANT-BINDING-01).

**Phase 3 (the Constructor).** `PHASE3_GRANTS` names each owner-approved
phase-3 grant, its Challenge, and whether a run accepts it only as main's
committed blob:

- GRAPHITE-GRANT-PHASE3, GRAPHITE-GRANT-PHASE3-R2 and GRAPHITE-GRANT-PHASE3-R3
  are battery's. They are accepted as before (no main-blob check;
  OWNER-GRAPHITE-03, OWNER-GRAPHITE-PHASE3-REFUND-01,
  OWNER-GRAPHITE-PHASE3-R3-01), and only for battery.
- GRAPHITE-GRANT-PHASE3-COOLING-CPU is cooling's CPU-lane Constructor grant
  (OWNER-GRAPHITE-TEST-WAVE-06 §3): bound to `chip-cold-plate` and to main's
  committed blob, tokens only. Which grants are tokens-only is
  VALIDATOR-06's `phase3.TOKENS_ONLY_GRANTS` (`tokens_only`), not a list
  here. A tokens-only run's pod money budget is 0
  (`Phase3Budget.tokens_only`), so `experiment.Experiment` refuses every
  launch that would reserve pod money, every RunPod pod, with
  `grant_allows_no_pods` before anything is reserved or created. The CPU
  carrier lane, which costs no provider money (`carrier_pods`, rate 0), is
  where its proposals run.

- GRAPHITE-GRANT-PHASE3-R4 is battery's top-rung grant
  (OWNER-GRAPHITE-PHASE3-R4-01): bound to battery and to main's committed
  blob, for construction Level 1 and above only. Its entry registers three
  run conditions, which no other grant has, so every other grant behaves
  exactly as before:
  - `min_level` 1: a Level 0 run under it is refused
    `grant_requires_construction_level_1_or_above` (`level_refusal`), so
    Level 0 keeps today's start rungs and stays the cheap-model baseline;
  - `start_model` kimi-k3, the top Engy rung: the Constructor's (and the
    Planner's) ladder starts there (`start_rungs`), and a session that would
    open below it is refused `start_model_below_the_grants_start_rung`
    (`start_model_refusal`). The escalation rule is unchanged; there is no
    rung above the top (`ladder_top`);
  - `token_share_usd` 11.93: the run's token share is that amount, and its
    pods get the rest of the run cost (`experiment.phase3_budget`), so a
    full-window kimi-k3 call (USD 2.0646912 reserved) is admitted.
  A new session records them as its `run_conditions` (`run_conditions`).

**Studies (OWNER-RATE-STUDY-TOKENS-01).** `STUDY_GRANTS` binds each
owner-approved study grant to its study, its Challenge and main's committed
blob, with the record's limits. A study run names its study (`phase3 run
--study`), and `check_study_grant` accepts only the grant registered for that
study, carrying exactly the record's ceiling, per-run cost, run count and
wall-clock, and a submission cap that is one of the study's frozen arm caps
and never above the grant's. A run that names no study, or a study with no
binding, is refused `grant_is_not_bound_to_study`. A study grant is never a
phase-3 grant: outside its study it is refused `grant_is_bound_to_a_study`.

- GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR and GRAPHITE-GRANT-STAGE-A-ATTACKER are
  the Graphite ladder wave's stage A (OWNER-GRAPHITE-STAGE-A-01): battery,
  main's committed blob, start model kimi-k3. The Constructor grant admits
  Level 0 and above (`min_level` 0) with R4's token share; the Attacker grant
  starts the Attacker on kimi-k3 and runs only through phase 4 (`runner`):
  a phase-3 run refuses it (`grant_is_not_a_phase3_grant`), and phase 4
  accepts it by its id for battery (`phase4.check_committed_grant`).

- GRAPHITE-GRANT-STAGE-B-CONSTRUCTOR and GRAPHITE-GRANT-STAGE-B-ATTACKER are
  stage B (OWNER-GRAPHITE-STAGE-B-01): stage A's shape at Levels 2 and 3
  only. The Constructor grant registers `min_level` 2 and `max_level` 3 (a
  run outside them is `grant_level_outside_the_grants_levels`); the
  Attacker grant's levels are phase 4's (`Phase4Grant.levels`).
- GRAPHITE-GRANT-STAGE-C-CONSTRUCTOR and GRAPHITE-GRANT-STAGE-C-ATTACKER are
  stage C (OWNER-GRAPHITE-STAGE-C-01): the same shape at Level 4 only.
  The grant authorizes spend, never a Level 4 run: whether one runs stays
  the owner's and the security owner's.

A registered grant named for another Challenge is
`grant_is_for_another_challenge`. A Challenge in `PHASE3_BOUND_CHALLENGES`
accepts only a grant registered for it
(`grant_is_not_a_phase3_grant_for_challenge`).

This module grants nothing and spends nothing. Not security acceptance.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import types
from decimal import Decimal
from pathlib import Path

from carbon.development_session.profile import canonical, digest
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
    MOTOR_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[3]
#: The directory the owner's grants are committed under; a live run refuses
#: when anything in it differs from HEAD.
GRANTS_DIR = "docs/development/graphite/grants"
#: The typed refusal of a paid pod launch under a tokens-only grant.
NO_PODS = "grant_allows_no_pods"


def _refused(code):
    # The runners' typed refusal; imported here to keep this module free of
    # the phase-3 runner at import time (`experiment` imports this module).
    from .phase3 import RunnerRefused

    return RunnerRefused(code)


def grant_digest(document):
    """The canonical digest of a grant document (every field)."""
    return digest(canonical(document))


def _git(repository, *args):
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        check=False,
    )


def check_committed_blob(given, repository, grant_file, *, phase):
    """`given`, a grant document, must be the committed `grant_file`, field for
    field, as HEAD holds it: never the working tree, which an operator could
    edit together with the copy passed in. `phase` ("phase3", "phase4") names
    the refusals that are the phase's own.

    - The committed blob is read from git (`git show HEAD:<grant_file>`);
      none is `<phase>_grant_not_committed`.
    - The given copy's canonical digest must equal the committed blob's: any
      amount, run count, runtime or identity changed is
      `grant_differs_from_the_committed_<phase>_grant`.
    - HEAD must already be on a remote branch (`git branch -r --contains
      HEAD`): `grant_commit_not_pushed`.
    - The committed blob must be the one on main, which is what the owner
      approved: a pushed feature branch carrying an edited grant is not.
      `origin main` is fetched and the two blob ids compared; a fetch or a
      main without the grant is `main_grant_unavailable`, a different blob
      `grant_differs_from_main`.
    - The grants directory must match HEAD (no change, staged or not, and no
      untracked file): `grants_directory_has_uncommitted_changes`.

    Returns the committed grant's canonical digest."""
    shown = _git(repository, "show", "HEAD:" + grant_file)
    if shown.returncode != 0:
        raise _refused(phase + "_grant_not_committed")
    try:
        committed = json.loads(shown.stdout)
    except ValueError:
        raise _refused(phase + "_grant_file_unreadable") from None
    if grant_digest(given) != grant_digest(committed):
        raise _refused("grant_differs_from_the_committed_" + phase + "_grant")
    pushed = _git(repository, "branch", "-r", "--contains", "HEAD")
    if pushed.returncode != 0 or not pushed.stdout.strip():
        raise _refused("grant_commit_not_pushed")
    fetched = _git(repository, "fetch", "--quiet", "origin", "main")
    on_main = _git(repository, "rev-parse", "--verify", "origin/main:" + grant_file)
    if fetched.returncode != 0 or on_main.returncode != 0:
        raise _refused("main_grant_unavailable")
    at_head = _git(repository, "rev-parse", "--verify", "HEAD:" + grant_file)
    if at_head.returncode != 0 or at_head.stdout.strip() != on_main.stdout.strip():
        raise _refused("grant_differs_from_main")
    status = _git(
        repository, "status", "--porcelain", "--untracked-files=all", "--", GRANTS_DIR
    )
    if status.returncode != 0 or status.stdout.strip():
        raise _refused("grants_directory_has_uncommitted_changes")
    return grant_digest(committed)


# -- phase 3 ------------------------------------------------------------------------------
#: The Graphite ladder wave's stage A (#889 section 4), approved by the owner.
STAGE_A_AUTHORITY = "OWNER-GRAPHITE-STAGE-A-01"
#: Stage B (GRAPHITE_LADDER_STAGE_B_PLAN.md section 7), approved by the owner.
STAGE_B_AUTHORITY = "OWNER-GRAPHITE-STAGE-B-01"
#: Stage C, Level 4 (GRAPHITE_LADDER_WAVE_PLAN.md section 4), approved by the owner.
STAGE_C_AUTHORITY = "OWNER-GRAPHITE-STAGE-C-01"


@dataclasses.dataclass(frozen=True)
class Phase3Grant:
    """One owner-approved phase-3 grant: its Challenge, its file, whether a
    run accepts it only as main's committed blob, and its run conditions (the
    defaults: none, every grant as before)."""

    grant_id: str
    challenge: str
    grant_file: str
    main_blob: bool
    #: The lowest construction level a run under this grant may run at.
    min_level: int = 0
    #: The rung the grant's start roles open on; None: each role's own.
    start_model: str | None = None
    #: The run's token share in USD; None: the run cost less the pods.
    token_share_usd: Decimal | None = None
    #: The roles `start_model` applies to (`roles.RoleName` values).
    start_roles: tuple = ("constructor", "planner")
    #: The decision the run conditions record.
    authority: str = "OWNER-GRAPHITE-PHASE3-R4-01"
    #: The highest construction level a run under this grant may run at;
    #: None: no upper bound (every grant before stage B).
    max_level: int | None = None
    #: The runner that spends the grant: "phase3" (Constructor sessions) or
    #: "phase4" (Attacker sessions, `phase4.PHASE4_STAGE_GRANTS`).
    runner: str = "phase3"


PHASE3_GRANTS = types.MappingProxyType(
    {
        entry.grant_id: entry
        for entry in (
            Phase3Grant(
                grant_id="GRAPHITE-GRANT-PHASE3",
                challenge=BATTERY_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-PHASE3.json",
                main_blob=False,
            ),
            Phase3Grant(
                grant_id="GRAPHITE-GRANT-PHASE3-R2",
                challenge=BATTERY_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-PHASE3-R2.json",
                main_blob=False,
            ),
            Phase3Grant(
                grant_id="GRAPHITE-GRANT-PHASE3-R3",
                challenge=BATTERY_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-PHASE3-R3.json",
                main_blob=False,
            ),
            Phase3Grant(
                grant_id="GRAPHITE-GRANT-PHASE3-COOLING-CPU",
                challenge=COLD_PLATE_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-PHASE3-COOLING-CPU.json",
                main_blob=True,
            ),
            Phase3Grant(
                grant_id="GRAPHITE-GRANT-PHASE3-R4",
                challenge=BATTERY_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-PHASE3-R4.json",
                main_blob=True,
                min_level=1,
                start_model="kimi-k3",
                token_share_usd=Decimal("11.93"),
            ),
            Phase3Grant(
                grant_id="GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR",
                challenge=BATTERY_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR.json",
                main_blob=True,
                min_level=0,
                start_model="kimi-k3",
                token_share_usd=Decimal("11.93"),
                authority=STAGE_A_AUTHORITY,
            ),
            Phase3Grant(
                grant_id="GRAPHITE-GRANT-STAGE-A-ATTACKER",
                challenge=BATTERY_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-STAGE-A-ATTACKER.json",
                main_blob=True,
                start_model="kimi-k3",
                start_roles=("attacker",),
                authority=STAGE_A_AUTHORITY,
                runner="phase4",
            ),
            Phase3Grant(
                grant_id="GRAPHITE-GRANT-STAGE-B-CONSTRUCTOR",
                challenge=BATTERY_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-STAGE-B-CONSTRUCTOR.json",
                main_blob=True,
                min_level=2,
                max_level=3,
                start_model="kimi-k3",
                token_share_usd=Decimal("11.93"),
                authority=STAGE_B_AUTHORITY,
            ),
            Phase3Grant(
                grant_id="GRAPHITE-GRANT-STAGE-B-ATTACKER",
                challenge=BATTERY_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-STAGE-B-ATTACKER.json",
                main_blob=True,
                start_model="kimi-k3",
                start_roles=("attacker",),
                authority=STAGE_B_AUTHORITY,
                runner="phase4",
            ),
            Phase3Grant(
                grant_id="GRAPHITE-GRANT-STAGE-C-CONSTRUCTOR",
                challenge=BATTERY_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-STAGE-C-CONSTRUCTOR.json",
                main_blob=True,
                min_level=4,
                max_level=4,
                start_model="kimi-k3",
                token_share_usd=Decimal("11.93"),
                authority=STAGE_C_AUTHORITY,
            ),
            Phase3Grant(
                grant_id="GRAPHITE-GRANT-STAGE-C-ATTACKER",
                challenge=BATTERY_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-STAGE-C-ATTACKER.json",
                main_blob=True,
                start_model="kimi-k3",
                start_roles=("attacker",),
                authority=STAGE_C_AUTHORITY,
                runner="phase4",
            ),
        )
    }
)
#: Challenges whose phase-3 runs accept only a grant registered for them.
#: Battery's runs keep accepting any valid Graphite grant, as before.
PHASE3_BOUND_CHALLENGES = frozenset({COLD_PLATE_CHALLENGE})
#: The roles a grant's `start_model` applies to (OWNER-GRAPHITE-PHASE3-R4-01:
#: the Constructor, and the Planner when used), by `roles.RoleName` value.
START_ROLES = ("constructor", "planner")
#: The run-conditions record a new session freezes (`run_conditions`).
RUN_CONDITIONS_SCHEMA = "carbon.graphite.phase3.run-conditions.v1"
RUN_CONDITIONS_AUTHORITY = "OWNER-GRAPHITE-PHASE3-R4-01"
LEVEL_REFUSED = "grant_requires_construction_level_1_or_above"
LEVEL_RANGE_REFUSED = "grant_level_outside_the_grants_levels"
START_MODEL_REFUSED = "start_model_below_the_grants_start_rung"


def entry_of(grant):
    """The `Phase3Grant` registered for `grant`, or None."""
    return PHASE3_GRANTS.get(getattr(grant, "grant_id", None))


def level_refusal(grant, level):
    """The typed refusal of a run at construction `level` under `grant`, or
    None. Only a grant registering a `min_level` refuses anything; a level
    that is not a whole number refuses under one (fail closed)."""
    entry = entry_of(grant)
    if entry is not None and entry.max_level is not None:
        # A grant bound to a range of levels (stage B) refuses either side.
        if type(level) is not int or not entry.min_level <= level <= entry.max_level:
            return LEVEL_RANGE_REFUSED
        return None
    if entry is None or entry.min_level == 0:
        return None
    if type(level) is not int or level < entry.min_level:
        return LEVEL_REFUSED
    return None


def start_rungs(grant):
    """`{RoleName: rung}`: the ladder rung each start role opens on under
    `grant` (`ladder.Ladder(start_rungs=...)`); empty for a grant that
    registers no start model."""
    from carbon.development_session.model_provider import ENGY_LADDER

    from .roles import RoleName

    entry = entry_of(grant)
    if entry is None or entry.start_model is None:
        return {}
    rung = ENGY_LADDER.index(entry.start_model)
    return {RoleName(name): rung for name in entry.start_roles}


def start_model_refusal(grant, role, model_id):
    """The typed refusal of a session of `role` opening on `model_id` under
    `grant`, or None: a start role may never open below the grant's start
    rung, whatever the ladder says. Read from the registry itself, not from
    `start_rungs`, so the two guards stand independently."""
    from carbon.development_session.model_provider import ENGY_LADDER

    entry = entry_of(grant)
    if entry is None or entry.start_model is None:
        return None
    if getattr(role, "value", None) not in entry.start_roles:
        return None
    floor = ENGY_LADDER.index(entry.start_model)
    if model_id not in ENGY_LADDER or ENGY_LADDER.index(model_id) < floor:
        return START_MODEL_REFUSED
    return None


def run_conditions(grant):
    """The run conditions a new session under `grant` records, or None for
    a grant that registers none (its records stay exactly as before)."""
    entry = entry_of(grant)
    if entry is None or (
        entry.start_model is None
        and entry.min_level == 0
        and entry.token_share_usd is None
    ):
        return None
    return {
        "schema": RUN_CONDITIONS_SCHEMA,
        "authority": entry.authority,
        "grant_id": entry.grant_id,
        "min_construction_level": entry.min_level,
        "start_model": entry.start_model,
        "start_roles": list(entry.start_roles),
        "token_share_usd": (
            None if entry.token_share_usd is None else str(entry.token_share_usd)
        ),
    }


# -- the model provider a grant pays ------------------------------------------------------
#: The model provider each grant's token spend is bound to
#: (GRAPHITE-SPUR-PROVIDER-01). The grant format names its campaign provider
#: (`graphite`), not the inference provider it pays, so the binding is
#: registered here, as the Challenge binding is. A grant not listed pays
#: `DEFAULT_MODEL_PROVIDER`, Engy: every grant approved so far. No grant is
#: bound to SPUR: the owner approves its amounts later, by committing a grant
#: and listing it here, so until then every SPUR run is refused.
MODEL_PROVIDER_GRANTS = types.MappingProxyType({})
DEFAULT_MODEL_PROVIDER = "engy"
MODEL_PROVIDER_REFUSED = "grant_does_not_name_the_model_provider"


def model_provider_of(grant):
    """The model provider `grant` names (`MODEL_PROVIDER_GRANTS`)."""
    return MODEL_PROVIDER_GRANTS.get(
        getattr(grant, "grant_id", None), DEFAULT_MODEL_PROVIDER
    )


def model_provider_refusal(grant, model_provider):
    """`MODEL_PROVIDER_REFUSED` unless `grant` names `model_provider`, else
    None: a SPUR run refuses any grant that does not name SPUR, and an Engy
    run any grant bound to another provider."""
    if type(model_provider) is not str or model_provider_of(grant) != model_provider:
        return MODEL_PROVIDER_REFUSED
    return None


def tokens_only(grant):
    """True for a grant in `phase3.TOKENS_ONLY_GRANTS` (VALIDATOR-06): its
    runs have a pod money budget of 0 (`experiment.phase3_budget`), so a
    launch that would reserve pod money is refused `grant_allows_no_pods`."""
    from . import phase3

    return getattr(grant, "grant_id", None) in phase3.TOKENS_ONLY_GRANTS


def check_phase3_grant(path, grant, *, challenge, level=0, repository=REPOSITORY):
    """A live phase-3 run's grant, bound to the Challenge `--challenge`
    names (module docstring) and to the construction level `--level` names
    (`level_refusal`). `grant` is the `SpendingGrant` loaded from `path`.
    Returns its `Phase3Grant`, or None for an unregistered grant on a
    Challenge that is not bound. A study's grant is refused here: it spends
    only through its study (`check_study_grant`)."""
    if any(s.grant_id == grant.grant_id for s in STUDY_GRANTS.values()):
        raise _refused(STUDY_GRANT_OUTSIDE)
    entry = PHASE3_GRANTS.get(grant.grant_id)
    if entry is not None and entry.runner != "phase3":
        # An Attacker's grant (stage A) is spent only through phase 4.
        raise _refused("grant_is_not_a_phase3_grant")
    if entry is None:
        if challenge in PHASE3_BOUND_CHALLENGES:
            raise _refused("grant_is_not_a_phase3_grant_for_challenge")
        return None
    if entry.challenge != challenge:
        raise _refused("grant_is_for_another_challenge")
    refused = level_refusal(grant, level)
    if refused is not None:
        raise _refused(refused)
    if entry.main_blob:
        try:
            given = json.loads(Path(path).read_bytes())
        except (OSError, ValueError):
            raise _refused("phase3_grant_file_unreadable") from None
        check_committed_blob(given, repository, entry.grant_file, phase="phase3")
    return entry


# -- studies (OWNER-RATE-STUDY-TOKENS-01) -------------------------------------------------
@dataclasses.dataclass(frozen=True)
class StudyGrant:
    """One owner-approved study grant: its study, Challenge, file and the
    record's limits. The grant file must carry exactly these values, so a
    grant edited after approval, or another grant, never binds."""

    study_id: str
    grant_id: str
    challenge: str
    grant_file: str
    monetary_ceiling: Decimal
    worst_case_run_cost: Decimal
    permitted_runs: int
    max_runtime_s: int
    max_submissions: int
    #: The scored-submission caps the study's arms may freeze (plan section 9);
    #: a run's cap is one of these, from the frozen manifest.
    submission_caps: tuple[int, ...]


STUDY_GRANTS = types.MappingProxyType(
    {
        entry.study_id: entry
        for entry in (
            StudyGrant(
                study_id="SUBMISSION-RATE-STUDY-01",
                grant_id="GRAPHITE-GRANT-RATE-STUDY-TOKENS",
                challenge=BATTERY_CHALLENGE,
                grant_file=GRANTS_DIR + "/GRAPHITE-GRANT-RATE-STUDY-TOKENS.json",
                monetary_ceiling=Decimal("30.00"),
                worst_case_run_cost=Decimal("4.91"),
                permitted_runs=6,
                max_runtime_s=39600,
                max_submissions=144,
                submission_caps=(36, 72, 144),
            ),
        )
    }
)
STUDY_UNBOUND = "grant_is_not_bound_to_study"
STUDY_GRANT_OUTSIDE = "grant_is_bound_to_a_study"
STUDY_LIMITS_DIFFER = "study_grant_limits_differ_from_the_record"
STUDY_CAP_REFUSED = "study_submission_cap_not_a_frozen_arm_cap"


def check_study_grant(
    path, grant, *, study, challenge, submission_cap, repository=REPOSITORY
):
    """A live study run's grant (`phase3 run --study`). Refused, typed:

    - `grant_is_not_bound_to_study`: no study named, a study with no binding,
      or a grant that is not the one bound to it;
    - `grant_is_for_another_challenge`;
    - `study_grant_limits_differ_from_the_record`: the ceiling, per-run cost,
      run count, wall-clock or submission maximum is not the record's;
    - `study_submission_cap_not_a_frozen_arm_cap`: the run's cap is not one
      of the study's arm caps, or exceeds the grant's maximum;
    - every `check_committed_blob` refusal: the grant must be main's blob.

    Returns the `StudyGrant`. The controller then enforces the grant's
    amounts, runs and wall-clock as for any grant."""
    entry = STUDY_GRANTS.get(study) if isinstance(study, str) else None
    if entry is None or grant.grant_id != entry.grant_id:
        raise _refused(STUDY_UNBOUND)
    if entry.challenge != challenge:
        raise _refused("grant_is_for_another_challenge")
    if (
        grant.monetary_ceiling != entry.monetary_ceiling
        or grant.worst_case_run_cost != entry.worst_case_run_cost
        or grant.permitted_runs != entry.permitted_runs
        or grant.max_runtime_s != entry.max_runtime_s
        or grant.max_submissions != entry.max_submissions
    ):
        raise _refused(STUDY_LIMITS_DIFFER)
    if (
        type(submission_cap) is not int
        or submission_cap not in entry.submission_caps
        or submission_cap > grant.max_submissions
    ):
        raise _refused(STUDY_CAP_REFUSED)
    try:
        given = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        raise _refused("study_grant_file_unreadable") from None
    check_committed_blob(given, repository, entry.grant_file, phase="study")
    return entry


# -- dedicated admission controllers (A4-DEDICATED-ADMISSION-CONTROLLERS-01) ---------------
#: Each Challenge's owner-approved zero-spend admission-controller grant, by
#: Challenge token. The grant binds only the dedicated controller's identity;
#: it authorizes no spend (`SpendingGrant.zero_spend`).
ADMISSION_CONTROLLER_GRANTS = types.MappingProxyType(
    {
        BATTERY_CHALLENGE: GRANTS_DIR
        + "/GRAPHITE-GRANT-ADMISSION-CONTROLLER-BATTERY.json",
        COLD_PLATE_CHALLENGE: GRANTS_DIR
        + "/GRAPHITE-GRANT-ADMISSION-CONTROLLER-COOLING.json",
        MOTOR_CHALLENGE: GRANTS_DIR + "/GRAPHITE-GRANT-ADMISSION-CONTROLLER-MOTOR.json",
    }
)


def admission_grant_refusal(grant, challenge, repository=None):
    """The typed refusal of `grant` as `challenge`'s dedicated admission
    controller's grant, or None. It must be zero-spend, and field for field
    the committed file registered for `challenge`:

    - `admission_grant_must_be_zero_spend`;
    - `admission_grant_not_registered_for_challenge`: no file is registered;
    - `admission_grant_file_unreadable`;
    - `admission_grant_differs_from_the_committed_grant`: another grant, or
      an edited copy."""
    if not grant.zero_spend:
        return "admission_grant_must_be_zero_spend"
    relative = ADMISSION_CONTROLLER_GRANTS.get(challenge)
    if relative is None:
        return "admission_grant_not_registered_for_challenge"
    repository = REPOSITORY if repository is None else repository
    try:
        committed = json.loads((Path(repository) / relative).read_bytes())
    except (OSError, ValueError):
        return "admission_grant_file_unreadable"
    if grant_digest(grant.document()) != grant_digest(committed):
        return "admission_grant_differs_from_the_committed_grant"
    return None
