# Readiness observation — PKT-07

Schema: carbon.onboarding.evidence-readiness.v2

Observed 2026-10-12T19:25:16.795161+00:00; source main `092ecf506e608d831f84cc49007750eb95169f43`.

Candidate inspector against locally fetched main. Input indexes in this PR are
not merged inputs and do not change the main-only count until merged. Ranking
is engineering prerequisites only, not qualification, value or launch order.

| Family | Rank | YES/7 | Items 1–5 | Baseline | Equal budget |
| --- | ---: | ---: | --- | --- | --- |
| battery-v3 | 1 | 2 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | YES | YES |
| f02 | 1 | 2 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | YES | YES |
| f13 | 1 | 2 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | YES | YES |
| motor | 1 | 2 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | YES | YES |
| backward-facing-step | 5 | 1 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | YES | PROPOSED |
| cooling-cell | 5 | 1 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | YES | PROPOSED |
| f08 | 5 | 1 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | YES | PROPOSED |
| f17 | 5 | 1 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | YES | PROPOSED |
| metagrating-3d | 5 | 1 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | YES | PROPOSED |
| bolted-joint | 10 | 0 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | NO | NO |
| f06 | 10 | 0 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | NO | NO |
| package-warpage | 10 | 0 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | PLANNED | PROPOSED |
| seal-gland | 10 | 0 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | NO | NO |
| solenoid-pole | 10 | 0 | PLANNED, PLANNED, PLANNED, PLANNED, PLANNED | NO | NO |

## Candidate citation audit (not a main readiness claim)

The candidate indexes were audited against the source bytes on the main commit
above. Only reviewed public registration/MMS/kit metadata was inspected.
Every partial item remains UNKNOWN; none supplies all proof needed for YES.

### battery-v3

Candidate index SHA-256: `sha256:5df464cb356c64bb2f92a32bc115cb63219348681d5d1b8905a73d219ba3341f`.

1. UNKNOWN: Battery v3 public #965 manifest bab5ae97 and #1050 TRAIN registration/plan are on main; neither is a solved-TRAIN inventory; still required: Normalized physical tuples with all five current pins; Complete public COMPLETED and SCHEDULED reuse inventory with receipts
   Sources: [`docs/development/evidence/battery-feasibility-02/middle-bands/manifest.json`](../../../../docs/development/evidence/battery-feasibility-02/middle-bands/manifest.json) (`sha256:2aec860febd86fee6b68676d658cfda6fed8065509651b169817df5d4d9151b3`); [`carbon/development_comparison/campaign_entrypoints.py`](../../../../carbon/development_comparison/campaign_entrypoints.py) (`sha256:7ebb337fd30563732f115975c80cea78b450a3485b1e42172cdce65fab8b1ffc`)
2. UNKNOWN: Merged producer registration selects sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940; still required: Operator-supplied current presence observation bound to package/image; no host or Docker query performed
   Sources: [`carbon/development_comparison/campaign_entrypoints.py`](../../../../carbon/development_comparison/campaign_entrypoints.py) (`sha256:7ebb337fd30563732f115975c80cea78b450a3485b1e42172cdce65fab8b1ffc`)
3. UNKNOWN: OWNER-CODE-VERIFICATION-ACCEPT-01 accepts the cited pinned-image MMS discretisation results only; historical provisional verdicts are not rewritten; still required: Image- and case-family-bound convergence and conservation measurements with accepted criteria; Full normalized adequacy binding; MMS does not establish physical validity or Tier-2 agreement
   Sources: [`docs/development/evidence/battery-feasibility-02/code-verification/pybamm-verdict.json`](../../../../docs/development/evidence/battery-feasibility-02/code-verification/pybamm-verdict.json) (`sha256:783255a7fc2b540874953b928a48a4b6fdb1cc927ab0ed0bf127b72dbab9ff84`); [`docs/development/evidence/battery-feasibility-02/code-verification/pybamm.heat.json`](../../../../docs/development/evidence/battery-feasibility-02/code-verification/pybamm.heat.json) (`sha256:bd43327c2fbdbc14bf4943529875e2d6b0f337d49a40c8c3938109f032c0d538`); [`.agent/decisions/2026-10-11-OWNER-CODE-VERIFICATION-ACCEPT-01.md`](../../../../.agent/decisions/2026-10-11-OWNER-CODE-VERIFICATION-ACCEPT-01.md) (`sha256:64b32bf2225465c3b35a60dd2de41023bcce70279e3c0fff50339d6c0ba7fa25`)
4. UNKNOWN: Merged family kit and common domain_gaps hook exist; software presence is not actual panel/TRAIN support; still required: Exact kit-domain export against every panel action, condition and observable; no support inferred from panel extrema
   Sources: [`carbon/development_comparison/battery_v3_kit.py`](../../../../carbon/development_comparison/battery_v3_kit.py) (`sha256:8b8c942ebe57b1ed63f92e6dcd056222b5ed913ddc24924e275951632af2a7b4`); [`carbon/development_comparison/carbon_arm.py`](../../../../carbon/development_comparison/carbon_arm.py) (`sha256:3d1de72c58a885f1ffd125f37834f44b4266353f3cc9ba270470ec70eaa9f7ea`)
5. UNKNOWN: Public TRAIN generation is registered; no solved TRAIN or complete physical-disjointness proof inferred; still required: Public normalized TRAIN inventory and registration digest; Recomputed physical overlap against the complete panel, ignoring rung differences
   Sources: [`docs/development/evidence/battery-feasibility-02/v3-train-registry.json`](../../../../docs/development/evidence/battery-feasibility-02/v3-train-registry.json) (`sha256:d9a95d5421989b529bbe9af1d7ba78648d64dacafd9d4c6f0090d3a8ab6c4019`); [`docs/development/evidence/battery-feasibility-02/plans/v3-train-plan.json`](../../../../docs/development/evidence/battery-feasibility-02/plans/v3-train-plan.json) (`sha256:b42b41f149e317832c5b41d0c533b046ad16962f47416c553c63be8b7bcf60df`)

### motor

Candidate index SHA-256: `sha256:c77b7356e26338c3e5575006f4bb4d82a23a3b6a03e9c2779016c243ad5fb352`.

1. UNKNOWN: Motor #1114 reference stage binds the 230-case stages 1-3 holding plan; this is not full holding-plus-peak packet coverage; still required: Normalized physical tuples with all five current pins; Complete public COMPLETED and SCHEDULED reuse inventory with receipts
   Sources: [`docs/development/evidence/motor-feasibility-02/plans/reference-panel-plan.json`](../../../../docs/development/evidence/motor-feasibility-02/plans/reference-panel-plan.json) (`sha256:41e55a557544df3c6c2226c852427c5a0149767fae07c38bafc797396a0f379b`); [`carbon/development_comparison/campaign_entrypoints.py`](../../../../carbon/development_comparison/campaign_entrypoints.py) (`sha256:7ebb337fd30563732f115975c80cea78b450a3485b1e42172cdce65fab8b1ffc`)
2. UNKNOWN: Merged producer registration selects sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05; still required: Operator-supplied current presence observation bound to package/image; no host or Docker query performed
   Sources: [`carbon/development_comparison/campaign_entrypoints.py`](../../../../carbon/development_comparison/campaign_entrypoints.py) (`sha256:7ebb337fd30563732f115975c80cea78b450a3485b1e42172cdce65fab8b1ffc`)
3. UNKNOWN: OWNER-CODE-VERIFICATION-ACCEPT-01 accepts the cited pinned-image MMS discretisation results only; historical provisional verdicts are not rewritten; still required: Image- and case-family-bound convergence and conservation measurements with accepted criteria; Full normalized adequacy binding; MMS does not establish physical validity or Tier-2 agreement
   Sources: [`docs/development/evidence/motor-feasibility-02/code-verification/getdp-verdict.json`](../../../../docs/development/evidence/motor-feasibility-02/code-verification/getdp-verdict.json) (`sha256:942ee4536b159884897d3f7eca2e5a95a0adcb032d5d8f129fdfef5a5a264cfd`); [`docs/development/evidence/motor-feasibility-02/code-verification/getdp.flux.json`](../../../../docs/development/evidence/motor-feasibility-02/code-verification/getdp.flux.json) (`sha256:341737286869281794a87b6f4df71d0bf8ad9c301e89e9b777fae667737a12d9`); [`.agent/decisions/2026-10-11-OWNER-CODE-VERIFICATION-ACCEPT-01.md`](../../../../.agent/decisions/2026-10-11-OWNER-CODE-VERIFICATION-ACCEPT-01.md) (`sha256:64b32bf2225465c3b35a60dd2de41023bcce70279e3c0fff50339d6c0ba7fa25`)
4. UNKNOWN: Merged family kit and common domain_gaps hook exist; software presence is not actual panel/TRAIN support; still required: Exported exact domain/observer coverage against every registered panel row; Peak-command/full-packet coverage beyond the current holding stage
   Sources: [`carbon/development_comparison/motor_10p12s_kit.py`](../../../../carbon/development_comparison/motor_10p12s_kit.py) (`sha256:93a060afed66aa070fa718428abfbb6d55af899a63825b9f84272eda6ed26b40`); [`carbon/development_comparison/carbon_arm.py`](../../../../carbon/development_comparison/carbon_arm.py) (`sha256:3d1de72c58a885f1ffd125f37834f44b4266353f3cc9ba270470ec70eaa9f7ea`)
5. UNKNOWN: Public TRAIN generation is registered; no solved TRAIN or complete physical-disjointness proof inferred; still required: Public normalized TRAIN inventory and registration digest; Recomputed physical overlap against the complete panel, ignoring rung differences
   Sources: [`docs/development/evidence/motor-feasibility-02/plans/train-stage1-plan.json`](../../../../docs/development/evidence/motor-feasibility-02/plans/train-stage1-plan.json) (`sha256:4a067614ee921d20069504937e3913cebb30226cafe35c489d3a9356a2f4f2cd`)

### f02

Candidate index SHA-256: `sha256:7ae414e8b769610b42b872182c489832c23a610fb9f4272c5e16b2271cdaefc0`.

1. UNKNOWN: f02 menu v2 has 16 actions x 24 contexts (384 primary cases), prospectively adopted in F02-MENU-V2-REGISTRATION; still required: Normalized physical tuples with all five current pins; Complete public COMPLETED and SCHEDULED reuse inventory with receipts
   Sources: [`docs/development/evidence/reference-packages-01/f02-menu-v2/registry.json`](../../../../docs/development/evidence/reference-packages-01/f02-menu-v2/registry.json) (`sha256:62f529ce70f28772bb17bc74abad3a296fe4b342a419dc95f07885f19922c1d2`); [`docs/development/evidence/reference-packages-01/f02-menu-v2/decks-manifest.json`](../../../../docs/development/evidence/reference-packages-01/f02-menu-v2/decks-manifest.json) (`sha256:69ae549d7aa12add3ed410dd8534be4a4ab38c40fc578fd43394fa74e62074d7`); [`.agent/decisions/2026-10-11-F02-MENU-V2-REGISTRATION.md`](../../../../.agent/decisions/2026-10-11-F02-MENU-V2-REGISTRATION.md) (`sha256:aca2d8e95ffbff1e3683d826c8b23da90159bff0a454cbd1aaa20fc040155df6`); [`carbon/development_comparison/campaign_entrypoints.py`](../../../../carbon/development_comparison/campaign_entrypoints.py) (`sha256:7ebb337fd30563732f115975c80cea78b450a3485b1e42172cdce65fab8b1ffc`)
2. UNKNOWN: Merged producer registration selects sha256:6fab746f31257236da9e91b5be681bfbd2d25bd69f5dcd9a2e350394e8bcb675; still required: Operator-supplied current presence observation bound to package/image; no host or Docker query performed
   Sources: [`carbon/development_comparison/campaign_entrypoints.py`](../../../../carbon/development_comparison/campaign_entrypoints.py) (`sha256:7ebb337fd30563732f115975c80cea78b450a3485b1e42172cdce65fab8b1ffc`)
3. UNKNOWN: OWNER-CODE-VERIFICATION-ACCEPT-01 accepts the cited pinned-image MMS discretisation results only; historical provisional verdicts are not rewritten; still required: Image- and case-family-bound convergence and conservation measurements with accepted criteria; Full normalized adequacy binding; MMS does not establish physical validity or Tier-2 agreement
   Sources: [`docs/development/evidence/reference-packages-01/elmer-mms-heat-time-t0375.json`](../../../../docs/development/evidence/reference-packages-01/elmer-mms-heat-time-t0375.json) (`sha256:bf893b594591ca3bc3f2940d8aa568ef96a1824397a1140cb18d3ba63f997919`); [`docs/development/evidence/reference-packages-01/elmer-mms-heat.json`](../../../../docs/development/evidence/reference-packages-01/elmer-mms-heat.json) (`sha256:60edc8b1847d4a66c41601c03f78b8beccdf4fd3a05bc81629e0b64f1d70726e`); [`docs/development/challenge_pipeline/code-verification/specs.json`](../../../../docs/development/challenge_pipeline/code-verification/specs.json) (`sha256:cc79e68a8d85020a866e4ed02237fc3d87a06cd844d5ab77e2a17965d635a971`); [`.agent/decisions/2026-10-11-OWNER-CODE-VERIFICATION-ACCEPT-01.md`](../../../../.agent/decisions/2026-10-11-OWNER-CODE-VERIFICATION-ACCEPT-01.md) (`sha256:64b32bf2225465c3b35a60dd2de41023bcce70279e3c0fff50339d6c0ba7fa25`)
4. UNKNOWN: Merged family kit and common domain_gaps hook exist; software presence is not actual panel/TRAIN support; still required: Exact kit-domain export against every panel action, condition and observable; no support inferred from panel extrema
   Sources: [`carbon/development_comparison/f02_kit.py`](../../../../carbon/development_comparison/f02_kit.py) (`sha256:adfb952f13bcabd8e334f2f6a7f165e9cf62a3531d23e12d757bacfed37338d4`); [`carbon/development_comparison/carbon_arm.py`](../../../../carbon/development_comparison/carbon_arm.py) (`sha256:3d1de72c58a885f1ffd125f37834f44b4266353f3cc9ba270470ec70eaa9f7ea`)
5. UNKNOWN: Public TRAIN generation is registered; no solved TRAIN or complete physical-disjointness proof inferred; still required: Public normalized TRAIN inventory and registration digest; Recomputed physical overlap against the complete panel, ignoring rung differences
   Sources: [`docs/development/evidence/reference-packages-01/f02-menu-v2/train-registry.json`](../../../../docs/development/evidence/reference-packages-01/f02-menu-v2/train-registry.json) (`sha256:676fa53422b112de15c5e129affa2ae27ea1ae8892772bbad5699e93c6bd9671`); [`docs/development/evidence/reference-packages-01/f02-menu-v2/train-decks-manifest.json`](../../../../docs/development/evidence/reference-packages-01/f02-menu-v2/train-decks-manifest.json) (`sha256:5763d244d15a3a485bf4ad046a0c482f47b698d1051735dcd238d5f907b6d281`)

## Limits and next action

No solver runs, hidden/sealed reads, host/store queries or spend. No automatic
paid-output exception or grant. Data Collection exports the missing normalized
reuse, image-presence, adequacy, domain and TRAIN proofs. Accepted MMS alone does
not qualify the reference. Re-run `onboarding readiness` after merge; preserve
the historical initial-report.json unchanged.
