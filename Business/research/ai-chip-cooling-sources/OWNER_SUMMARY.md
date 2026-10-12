# Owner summary â€” AI-chip liquid-cooling inputs

**Research recommendation, 2026-10-11; no parameter adoption or new solve.**
Warm-water operation is credible. ASHRAE's classes W32/W40/W45 specify upper
temperature endpoints of 32/40/45Â°C; they do not certify a specific GPU or
make facility supply equal to cold-plate inlet. OCP's published secondary-
supply group is 40â€“45Â°C, and Lenovo documents systems using 45Â°C water.
Sources and the distinction between facility and technology loops are in
[SOURCE_REVIEW.md](SOURCE_REVIEW.md).

OCP's design guidance gives per-device flow 1â€“2 L/min and PG25 flow/heat
ratio low/base/high 1.25/1.5/2 L/min/kW. Higher-flow test examples also exist.
Published full-loop pressure drops of 7 and 10 psi (48.3 and 68.9 kPa), and
CoolIT's 8 psi (55.2 kPa) test loop, support allocating only part of that
budget to an interior cell. They do **not** source Carbon's proposed
20/25/30-kPa cell caps: those remain assumptions and owner decisions.

AMD's current MI350X/MI355X powers are 1000/1400 W at module scope. NVIDIA's
Blackwell Ultra datasheet distinguishes HGX B300 up to 1100 W and GB300 up
to 1400 W. None of these board/module figures is a measured lid heat map.
OCP provides a reproducible 1000-W, 30Ã—30-mm heater example (111 W/cmÂ²).
Actual current-product lid flux and power partition remain HUMAN_INPUT.

Recommend three **prospective representative cell** base points; all are
ASSUMPTION design choices inside Carbon's published domain, not vendor-
qualified products. Full low/base/high alternatives are in the JSON.

| Point | Cell inlet | Interface heat over 30Ã—30 mm | Flow | Proposed cell allocation | Role |
| --- | --- | --- | --- | --- | --- |
| A | 32Â°C | 750 W | 1.125 L/min | 20 kPa | Lower-power warm-water anchor |
| B | 40Â°C | 1000 W | 1.50 L/min | 25 kPa | Recommended central decision panel |
| C | 45Â°C | 1400 W | 2.80 L/min | 30 kPa | High-power stress; hold if feasibility/value fails |

Retain the owner's 85Â°C lid-side TIM2 proxy and current areal TIM resistance
5e-6 mÂ²K/W as developmental inputs. The vapor-chamber lid is still the
blocking characterization: Boyd advertises effective conductivity above
5000 W/m/K but supplies no transferable scalar law for this lid. A
2000/5000/10000 W/m/K sensitivity is ASSUMPTION only; it cannot create free
thermal headroom or physical credibility. Its source geometry, thickness,
anisotropy, power map, orientation and dryout limits must be fixed first.
Do not dispatch a bank from these recommended points until the complete
panel meets feasibility, contested-frontier and cheap-baseline value checks.
