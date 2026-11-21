"""The crown pieces that live paths use, apart from the crown multi-rebuild average (over-broad rules audit S7, crown
delete stage 2a; case-procs, 21 Nov 2026).

Official-score crowns are the default for every served version (`crown_official`), and installing them leaves the
averaging decision machinery in `crown_average` unreachable. These names were defined there but are read by live paths
that never average, so they live here and `crown_average` re-exports them unchanged (same values, same classes):

- ``HOST_OWNER``: the synthetic owner of the validator's own rebuild tasks (the king's rebuild, route (b));
- the margin registry reader (`load_rule`, `Rule`, ``REGISTRY``, ``SCHEMA``): `koth_registry.registered_floor` binds
  each crown floor to the registered margin measurement;
- the reason codes a filed crown decision may carry (``MARGIN_UNREGISTERED``, ``KING_UNMEASURED``,
  ``REBUILD_UNAVAILABLE``, ``REBUILD_IN_PROGRESS``): `lean_recipe_retention._file_if_paused` and `crown_pause_sweep`;
- `RebuildInfra`: a derived rebuild that failed for an infrastructure reason (`lean_recipe_retention._derived_build`);
- `CrownAverageInvalid`: the registry's and the crown key file's typed refusal (`crown_average_host.read_crown_key`).

Nothing here decides a crown. The codes and the registry schema keep their historical spelling (``crown_average_*``,
``carbon.crown.average-rule.v1``) so every record already written reads as before.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from carbon.challenge_validator import registry_version
from carbon.challenge_validator.interface import is_digest

SCHEMA = "carbon.crown.average-rule.v1"
REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "crown_average.json"
)
#: The synthetic owner of the validator's averaging-rebuild tasks. Not an ss58 address and never a registered hotkey, so
#: it can never be in a metagraph snapshot or receive weight; a derived task is its alone, never a miner's.
HOST_OWNER = "carbon-crown-average-host"
MARGIN_UNREGISTERED = "crown_average_margin_unregistered"
#: A king whose mean was never measured (it was crowned by a single grade): crowns for the Challenge stay paused
#: until it is re-measured at switch-over. A single grade is never compared as if it were a mean.
KING_UNMEASURED = "crown_average_king_unmeasured"
REBUILD_UNAVAILABLE = "crown_average_rebuild_unavailable"
#: A stepwise crown decision ran ONE new rebuild and stopped (`Active.decide` with ``stepwise``): the contender is filed for the
#: sweep, which resumes it on its next tick from the rebuilds kept so far. Not a failure of anything: no attempt is counted,
#: no retry spacing applies and nothing is alerted.
REBUILD_IN_PROGRESS = "crown_average_rebuild_in_progress"
#: An engineering bound, not a scientific value: a rule asking for more rebuilds than this is a typo.
MAX_N = 1000


class CrownAverageInvalid(ValueError):
    """The registry, the key file or an input is not exactly the registered shape."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class RebuildInfra(Exception):
    """A rebuild failed for a reason that says nothing about the model (infrastructure): retried, never counted
    against the miner."""


class Rule:
    """The loaded registry: N (per Challenge), the seed range and each Challenge's registered margin."""

    def __init__(self, document):
        self.version = document["rule_version"]
        self.seed_range = document["seed_range"]
        self._n = document["n"]
        self._override = document["challenge_n"]
        self._margins = document["margins"]

    def n_for(self, challenge_id, version=None):
        found = registry_version.find(self._override, challenge_id, version)
        return self._n if found is None else found

    def margin_digest_for(self, challenge_id, version=None):
        entry = registry_version.find(self._margins, challenge_id, version)
        return None if entry is None else entry["measurement_digest"]

    def margin_for(self, challenge_id, version=None):
        """The registered margin_N of ``challenge_id`` (a version's own entry first: `registry_version`) at the N now
        configured for it, or None: absent, or measured at a different N (a stale margin is never used).
        """
        entry = registry_version.find(self._margins, challenge_id, version)
        if entry is None or entry["n"] != self.n_for(challenge_id, version):
            return None
        return entry["value"]


def _count(value, code, minimum=2):
    if type(value) is not int or not minimum <= value <= MAX_N:
        raise CrownAverageInvalid(code)
    return value


def load_rule(path=REGISTRY):
    document = json.loads(Path(path).read_bytes())
    names = {
        "schema",
        "rule_version",
        "n",
        "challenge_n",
        "seed_range",
        "margins",
    }
    if (
        type(document) is not dict
        or set(document) != names
        or document["schema"] != SCHEMA
        or type(document["rule_version"]) is not str
        or not document["rule_version"]
        or type(document["challenge_n"]) is not dict
        or type(document["margins"]) is not dict
    ):
        raise CrownAverageInvalid("crown_average_registry_invalid")
    _count(document["n"], "crown_average_n_invalid")
    # 2 and the top of the 32-bit positive range at least: a range this small has no seed to give.
    if type(document["seed_range"]) is not int or document["seed_range"] < 2**16:
        raise CrownAverageInvalid("crown_average_seed_range_invalid")
    from carbon.challenge_validator.exam_cap import registered_challenges

    known = registered_challenges()
    for challenge, n in document["challenge_n"].items():
        if not registry_version.known_key(challenge, known):
            raise CrownAverageInvalid("crown_average_challenge_unknown")
        _count(n, "crown_average_n_invalid")
    for challenge, entry in document["margins"].items():
        if (
            not registry_version.known_key(challenge, known)
            or type(entry) is not dict
            or set(entry) != {"value", "n", "measurement_digest"}
            or type(entry["value"]) not in (int, float)
            or isinstance(entry["value"], bool)
            or not math.isfinite(entry["value"])
            or entry["value"] < 0
            or not is_digest(entry["measurement_digest"])
        ):
            raise CrownAverageInvalid("crown_average_margin_invalid")
        _count(entry["n"], "crown_average_n_invalid")
    return Rule(document)
