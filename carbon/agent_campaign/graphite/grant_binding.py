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
from pathlib import Path

from carbon.development_session.profile import canonical, digest
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
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
@dataclasses.dataclass(frozen=True)
class Phase3Grant:
    """One owner-approved phase-3 grant: its Challenge, its file, and whether
    a run accepts it only as main's committed blob."""

    grant_id: str
    challenge: str
    grant_file: str
    main_blob: bool


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
        )
    }
)
#: Challenges whose phase-3 runs accept only a grant registered for them.
#: Battery's runs keep accepting any valid Graphite grant, as before.
PHASE3_BOUND_CHALLENGES = frozenset({COLD_PLATE_CHALLENGE})


def tokens_only(grant):
    """True for a grant in `phase3.TOKENS_ONLY_GRANTS` (VALIDATOR-06): its
    runs have a pod money budget of 0 (`experiment.phase3_budget`), so a
    launch that would reserve pod money is refused `grant_allows_no_pods`."""
    from . import phase3

    return getattr(grant, "grant_id", None) in phase3.TOKENS_ONLY_GRANTS


def check_phase3_grant(path, grant, *, challenge, repository=REPOSITORY):
    """A live phase-3 run's grant, bound to the Challenge `--challenge`
    names (module docstring). `grant` is the `SpendingGrant` loaded from
    `path`. Returns its `Phase3Grant`, or None for an unregistered grant on a
    Challenge that is not bound."""
    entry = PHASE3_GRANTS.get(grant.grant_id)
    if entry is None:
        if challenge in PHASE3_BOUND_CHALLENGES:
            raise _refused("grant_is_not_a_phase3_grant_for_challenge")
        return None
    if entry.challenge != challenge:
        raise _refused("grant_is_for_another_challenge")
    if entry.main_blob:
        try:
            given = json.loads(Path(path).read_bytes())
        except (OSError, ValueError):
            raise _refused("phase3_grant_file_unreadable") from None
        check_committed_blob(given, repository, entry.grant_file, phase="phase3")
    return entry
