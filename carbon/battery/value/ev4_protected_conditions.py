# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""EV4's conditions: material an external research agent must never receive.

EV4 runs under a frozen pre-registration (`BATTERY_ENGINEERING_VALUE_EV4.md`,
FROZEN 2026-10-01T20:09:26Z, branch `claude/ev4-optimizer`, §4 and the Problem C
optimizer section). Its verification and optimizer-verification conditions are
confirmation material for that study. Its development and model-query
conditions are protected too, so a separate optimizer experiment never shares a
condition with EV4 at all.

This file is deliberately outside every research checkout (its name matches the
`boundaries` denylist). `search_commitment` refuses any request or model query
that touches these conditions. Nothing here changes EV4.
"""

from __future__ import annotations

import numpy as np

SOURCE = (
    "docs/development/BATTERY_ENGINEERING_VALUE_EV4.md (frozen 2026-10-01T20:09:26Z), "
    "§4 conditions and the Problem C optimizer conditions"
)

EV4_DEVELOPMENT = tuple(
    (float(t), float(s)) for t in (5, 14, 24, 34) for s in (0.12, 0.33, 0.48)
)
EV4_VERIFICATION = tuple(
    (float(t), float(s)) for t in (9, 19, 29, 38) for s in (0.06, 0.22, 0.40)
)
EV4_MODEL = tuple(
    (float(t), float(s))
    for t in (5, 10, 15, 20, 25, 30, 35, 40)
    for s in (0.05, 0.20, 0.35, 0.50)
)
EV4_OPTIMIZER_VERIFICATION = tuple(
    (float(t), float(s))
    for t in np.linspace(5.0, 40.0, 18)
    for s in np.linspace(0.05, 0.50, 5)
)


def _key(t_amb, soc0):
    return (round(float(t_amb), 9), round(float(soc0), 9))


PROTECTED = frozenset(
    _key(t, s)
    for group in (
        EV4_DEVELOPMENT,
        EV4_VERIFICATION,
        EV4_MODEL,
        EV4_OPTIMIZER_VERIFICATION,
    )
    for t, s in group
)


def is_protected(t_amb, soc0):
    return _key(t_amb, soc0) in PROTECTED
