# COOLING-MOTOR-L0-READINESS-EVIDENCE-01 working decision

**Decision:** register Level-0 readiness evidence for `chip-cold-plate` and
`electric-motor-magnetics` for the five level-scoped items (P3, R7, A2, A3,
S2), name a covering assertion for every attack family the Attacker cannot
reach at Level 0, and register motor's existing validator boundary test for
P7. The evidence comes from one new parametrized file,
`tests/cpu/test_graphite_readiness_level0_evidence.py`, the Level-0
counterpart of battery's `test_graphite_readiness_level_evidence.py`.

**Reason:** the owner asked for the queued Challenges to be ready to enter
testing as soon as battery finishes. These items were NOT_BUILT only because
no Level-0 assertion was recorded for them. Each now runs on the Challenge's
own registered scoring and attack adapter and prints the
`READINESS_LEVEL_EVIDENCE` line the gate requires. Level 0 is the recorded
miner-facing contract, so no development variant is named.

**Basis per item:**

- P3: Phase-3 dry run at Level 0 with no pod, key, network or spend; the
  delivered recipe names this Challenge and the `kernel_ridge` backbone.
- R7: constructor and attacker turn text is computed from the ledger,
  supplemented by battery's Challenge-neutral turn-status tests.
- A2: every reachable family is an adapter family; every unreachable family
  points at that adapter's `test_every_attack_is_held_and_every_specimen_fires`
  case for the family.
- A3: the Level-0 provider records stop rule v3 (k = 3) and withholds finish
  until every reachable family has k attempts.
- S2: Graphite never delivers a gate-failing proposal, whatever its score,
  plus each Challenge's existing frozen-rule ineligibility tests.

**Result:** the Level-0 gate moved P3, R7, A2, A3 and S2 from NOT_BUILT to
PASS for both Challenges, and P7 from NOT_BUILT to PASS for motor. Neither
Challenge is green: 17 PASS each, with the rest below.

**Not changed, still blocked:**

- Host-only: R1, R3, R6 need the operator host's image manifests and drive
  measurement.
- Owner values or grants: motor has no Phase-4 grant (R1, R5); cooling R5
  needs pricing headroom; S1 noise provenance, S3 gate margins and H2 tuning
  overlap stay HUMAN_INPUT.
- Operator identity: A4 controller identity is unrecorded for both.
- Recorded reviews: O1, S4, V3, and A5 (cooling A5 also needs
  `cooling-candidate-fault-v2` registered).
- Owners not yet assigned work: R2 containment lane (Test Lead), R4 per-role
  model registration (Test Engineer).
- Data Collection studies D1 to D6, and the Q1 alignment report for V1/V2.
- Hidden pool H1, H3, H4: VALIDATOR-13 serves battery only. Extending it is
  hidden-evaluation persistence and is left to Carbon Validator.

**Reserved:** this records engineering evidence only. It earns no scientific,
security or production qualification and sets no threshold.
