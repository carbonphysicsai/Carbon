"""F08 1.7: the owner's prospective frequency-band gate correction.

OWNER-F08-FREQUENCY-BAND-DROP-01 removes only the 80–600 Hz per-answer
band. This adapter supplies the explicit rule to the existing sealed scorer;
accuracy, laws, design feasibility and the pool grader remain the same engines.
The band remains recorded as historical/design context, never a widened gate.
"""

from __future__ import annotations

import sys

from carbon.scoring import f08_dual_measurement as fdm
from carbon.scoring import f08_sealed_dual_pack as sealed
from carbon.scoring import physical_dual_pack as physical

FILES = (*sealed.FILES, "f08_sanity_dual_pack.py", "pool_adapters.py")


def definition(*, bank, train_raw):
    return {
        **sealed.definition(bank=bank, train_raw=train_raw),
        "native_summary_rule": fdm.SANITY_RULE,
    }


def validate_definition(value):
    sealed.validate_definition(value, native_summary_rule=fdm.SANITY_RULE)
    return value


def measure(**kwargs):
    validate_definition(kwargs["definition"])
    return sealed.measure(**kwargs, native_summary_rule=fdm.SANITY_RULE)


def producer_digest():
    """The prospective adapter's identity, including its wrapper and pool hook."""
    return physical.producer_digest(sys.modules[__name__])


def __getattr__(name):
    return getattr(sealed, name)
