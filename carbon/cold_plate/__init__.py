"""AI-chip liquid cold plate DEVELOPMENT Challenge (#342).

A straight-microchannel copper cold plate cooled by PG25, under the
provisional design basis in `scripts/dev/cold_plate/DESIGN_BASIS.md`. The
owner delegated its material, coolant, ranges and interface assumption on
2026-09-29 (OWNER-BATTERY-V2-DISCLOSURE-01 items 10-12) and its design flow on
2026-10-01 (OWNER-CHALLENGE-DESIGN-01).

Nothing here is scientifically, security or production qualified, and no
value here is a production threshold.

`customer_decision` adds a DEVELOPMENT-only customer decision experiment over
this exact periodic-cell scope. It requires caller-supplied limits, commits a
proposal before reference access and does not make the plate, manifold or
customer decision qualified.
"""
