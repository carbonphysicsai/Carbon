# Electrochemistry kit — PyBaMM

**PROPOSED reusable bundle; only narrow submodel code verification accepted.**
Reuse `carbon/battery/`, the hash-locked battery overlay and code-verification
particle/heat worker. The historical accepted execution image is
`sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940`;
base **plus overlay** identity is required, not the base digest alone.
PyBaMM 26.8.0.0 particle FV order and lumped-heat tolerance study do not verify
full DFN assembly, SEI/plating, ageing or a new cell's parameters. Store presence
and applicability to a changed package are UNKNOWN until operator checks.

## Once per applicable kit version

- Physics template: voltage/current/SOC traces, charge throughput, independent
  source/heat-loss/storage terms where supported, charging-only extrema and
  discharge diagnostics, plating margins and cycle-capacity observers. Pin sign,
  time origin, session-start-SOC and capacity normalisation. Do not construct both
  sides of charge/heat balances from the same predicted variable.
- Minimal output policy: current, heat and SOC on a registered trace grid can
  support charge/protocol checks; total heat alone cannot prove independently
  unexported reversible/irreversible heat splits. No full particle/electrolyte
  fields by default. The v-next contract is a proposal, not a changed live job.
- Verify observers/submodel assembly independently: charge-integral session time
  is not inferred from coarse voltage probes. Refine cold plating boundaries,
  charge thermal extrema and capacity ratio before resolving limits.
- Public kit: reuse own-seed generation, public TRAIN/reconstruction/practice and
  domain hooks for **their exact version**; maintain all eight provisions and
  explicit permitted-data rules.
- Comparator: calibrated SPMe/thermal models and conservative interpolated
  five-band maps, adaptive verified lookup and boundary refinement. Exact lookup
  is the correct CLOSED_BANK control, not evidence of generalisation.
- Equal budget: reuse `cheap-baselines/battery.md`, `carbon/design_search/`
  indexed tasks and budget registration. Charge map acquisition, fitting, all
  five band decisions and verification, not a separate model solve every fleet
  charging session.

## Per Challenge / reuse invalidators

Cell chemistry/geometry/material calibration, plating model applicability,
ageing history, cooling action, SOC and ambient distribution, buyer safety limits,
P/Q/w, five-band action map, question law and credibility witnesses remain
Challenge-specific. Battery v3 minimises fleet-mix-weighted session minutes;
charging 45 °C and plating 0 V remain hard; test-discharge heat is diagnostic.
Do not turn historical EV4's tiny menu into evidence about v3 or change EV5,
sealed journal 14, the live contract or safety limits.

New cell/reference validity, independent Tier-2/3 evidence and scientific
tolerances remain HUMAN_INPUT. First pilot: reused public v3 panel with grouped
action/band holdouts and cost accounting, not a new official campaign.
Sources: [register](../sources.md), [retro audit](../retrospective.md).
