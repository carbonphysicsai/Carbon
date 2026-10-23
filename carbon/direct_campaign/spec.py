"""Per-Challenge facts for the direct-recipe campaigns, and their research keys.

Each `Spec` names only registered identities: the Challenge id, its served
direct versions (`served_versions.CATALOG`, the graph adapter's `SPECS`), its
public construction module and its practice provenance. A version is always
named: `research_key` refuses when no key is in force (there is no default
version), and `key_for` refuses a version the Challenge does not serve here.
"""

from __future__ import annotations

import contextlib
import contextvars
import importlib
from dataclasses import dataclass, field

from carbon.challenge_kit import version_registry

#: The literal every unresolved owner/Validator decision carries.
HUMAN_INPUT = "HUMAN_INPUT"


@dataclass(frozen=True)
class Spec:
    challenge_id: str
    #: The code used in identifiers, refusal codes and file names ("f08").
    prefix: str
    #: The owner-facing name ("Ribbed Bracket").
    title: str
    #: The direct-recipe versions this campaign serves, each exactly.
    versions: tuple
    #: The public construction module (`carbon.challenge_kit.<prefix>_public`).
    public_module: str
    practice_provenance: str
    #: The research key in force for this Challenge (`keyed`); None outside.
    key_var: contextvars.ContextVar = field(compare=False, repr=False)

    @property
    def feedback_schema(self):
        return "carbon." + self.prefix + ".permitted-feedback.v1"

    @property
    def practice_schema(self):
        # v2 (C13): adds the shared practice_dual block; v1 had none.
        return "carbon." + self.prefix + ".direct-practice-feedback.v2"

    def public(self):
        return importlib.import_module(self.public_module)


F08 = Spec(
    "f08-ribbed-bracket",
    "f08",
    "Ribbed Bracket",
    version_registry.versions("f08-ribbed-bracket", campaign="direct"),
    "carbon.challenge_kit.f08_public",
    "F08_PUBLIC_PRACTICE",
    contextvars.ContextVar("carbon_f08_research_key", default=None),
)
F02 = Spec(
    "f02",
    "f02",
    "Burst Thermal",
    version_registry.versions("f02", campaign="direct"),
    "carbon.challenge_kit.f02_public",
    "F02_PUBLIC_PRACTICE",
    contextvars.ContextVar("carbon_f02_research_key", default=None),
)
SPECS = {spec.challenge_id: spec for spec in (F08, F02)}


def key_for(spec, version):
    """The spec's key at exactly `version`; there is no default version."""
    from carbon.registry import ChallengeKey

    if type(version) is not str or version not in spec.versions:
        raise ValueError(spec.prefix + " direct campaign version required")
    return ChallengeKey(spec.challenge_id, version)


def research_key(spec):
    key = spec.key_var.get()
    if key is None:
        raise ValueError(spec.prefix + " research key required (no default version)")
    return key


@contextlib.contextmanager
def keyed(spec, key):
    if key != key_for(spec, getattr(key, "version", None)):
        raise ValueError(spec.prefix + " direct campaign version required")
    token = spec.key_var.set(key)
    try:
        yield key
    finally:
        spec.key_var.reset(token)
