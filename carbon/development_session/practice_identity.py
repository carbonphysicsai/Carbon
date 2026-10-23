"""A practice-only campaign's admission (LP practice-only).

The practice identity itself - its owner-only key, its signer, the
local-practice context and snapshot - is `carbon.chain.practice`. This is
what admits a campaign with it: `PracticeMiner`, whose manifest record is
typed PRACTICE_ONLY, which the ledger admits for research and reports only.
"""

from __future__ import annotations

from carbon.chain.practice import (  # noqa: F401 - the identity, re-exported
    KEY_FILE,
    LOCAL_PRACTICE,
    PRACTICE_ONLY,
    PRINCIPAL,
    REGISTRATION_REQUIRED,
    PracticeIdentityRefused,
    PracticeSigner,
    context,
    create,
    is_local_practice,
    is_practice_principal,
    load,
    principal,
    refuse_local_practice,
    snapshot,
)


class PracticeMiner:
    """A practice-only campaign's admission: the practice identity, never a
    registration. Its manifest record is typed PRACTICE_ONLY, which the
    ledger admits for research and reports only."""

    __slots__ = ("identity",)

    def __init__(self, signer: PracticeSigner):
        if type(signer) is not PracticeSigner:
            raise TypeError("a practice miner is a loaded practice identity")
        self.identity = signer.public_key.hex()

    @property
    def principal(self) -> str:
        return "practice:" + self.identity

    def record(self) -> dict:
        return {
            "admission": PRACTICE_ONLY,
            "network": LOCAL_PRACTICE,
            "identity": self.identity,
        }


def is_practice_admission(manifest) -> bool:
    """Whether a campaign manifest was admitted PRACTICE_ONLY."""
    admission = manifest.get("admission") if type(manifest) is dict else None
    return type(admission) is dict and admission.get("admission") == PRACTICE_ONLY
