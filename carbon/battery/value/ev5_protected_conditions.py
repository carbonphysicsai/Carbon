"""EV5's conditions: material an external research agent must never receive.

EV5 (`BATTERY_ENGINEERING_VALUE_EV5.md`, DRAFT) confirms once on fresh
conditions. Its verification conditions are its confirmation material. Its
development conditions are protected too, as EV4's are
(`ev4_protected_conditions`), so a separate optimizer experiment never shares
a condition with EV5.

The values are the draft's §3 proposal, an engineering choice open until the
freeze; a change before the freeze is made here. Nothing here changes EV4.

This file is deliberately outside every research checkout (its name matches
the `boundaries` denylist). `search_commitment` refuses any request or model
query that touches these conditions.
"""

from __future__ import annotations

SOURCE = (
    "docs/development/BATTERY_ENGINEERING_VALUE_EV5.md (DRAFT), "
    "§3 proposed fresh conditions"
)

T_AMB_DEVELOPMENT = (6, 16, 26, 35)
SOC0_DEVELOPMENT = (0.10, 0.30, 0.46)
T_AMB_VERIFICATION = (10, 20, 30, 39)
#: 0.24, not 0.20: OWNER-EV5-Q1-01 counts EV4's protected optimizer grid
#: (soc0 0.05/0.20/0.35/0.50) as EV4 conditions.
SOC0_VERIFICATION = (0.07, 0.24, 0.38)

EV5_DEVELOPMENT = tuple(
    (float(t), float(s)) for t in T_AMB_DEVELOPMENT for s in SOC0_DEVELOPMENT
)
EV5_VERIFICATION = tuple(
    (float(t), float(s)) for t in T_AMB_VERIFICATION for s in SOC0_VERIFICATION
)


#: EV5's optimizer grids (OWNER-EV5-Q2-01): EV4's shape (8 x 4 model, 18 x 5
#: verification), so its maxima and cost are unchanged, at soc0 values that no
#: EV1, EV2, EV4 or EV5 condition uses. OWNER-EV5-Q1-01 counts EV4's grids as
#: EV4 conditions, so EV5 cannot reuse them; and the panel recipes and seeds
#: are EV4's, so a reused grid would repeat EV4's predictions and solves.
T_AMB_MODEL = (5, 10, 15, 20, 25, 30, 35, 40)
SOC0_MODEL = (0.055, 0.21, 0.36, 0.495)
T_AMB_OPTIMIZER_VERIFICATION = tuple(round(5.0 + 35.0 * i / 17, 9) for i in range(18))
SOC0_OPTIMIZER_VERIFICATION = (0.052, 0.165, 0.27, 0.385, 0.498)

EV5_MODEL = tuple((float(t), float(s)) for t in T_AMB_MODEL for s in SOC0_MODEL)
EV5_OPTIMIZER_VERIFICATION = tuple(
    (float(t), float(s))
    for t in T_AMB_OPTIMIZER_VERIFICATION
    for s in SOC0_OPTIMIZER_VERIFICATION
)


def _key(t_amb, soc0):
    return (round(float(t_amb), 9), round(float(soc0), 9))


PROTECTED = frozenset(
    _key(t, s)
    for group in (
        EV5_DEVELOPMENT,
        EV5_VERIFICATION,
        EV5_MODEL,
        EV5_OPTIMIZER_VERIFICATION,
    )
    for t, s in group
)


def is_protected(t_amb, soc0):
    return _key(t_amb, soc0) in PROTECTED
