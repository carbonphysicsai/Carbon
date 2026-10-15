# GRAPHITE-PUBLIC-MODEL-RETENTION-01

Status: in progress; Root-assigned bounded public DEVELOPMENT test repair.
Starting base: `3ee7144aa0bd35b0f693d9a154e07bea553eff29`.

## Working contract and plan

Ryan requested all Graphite-testing models for ScoreLab. Root delegates source,
focused tests and remote CI; Root alone owns runtime/build/publication/extraction.
The actual path is Launchpad Graphite -> battery.campaign.compose -> BatteryPractice.
Standalone Graphite executors/pod collectors and other Challenges are out of scope.

1. KEEP existing practice/GPU program bytes, recipes.state_bytes/model_from_bytes,
   carrier output parsing/accounting and miner workspace storage. No new serializer.
2. WRAP only an explicitly opted-in local public Graphite test campaign. Freeze
   its exact opt-in descriptor at launch; resumes use the frozen descriptor.
3. Retain state.npz, compiled recipe, fit, predictions and a provenance sidecar in
   the existing operation snapshot. Bind exact staged bytes/program/image, TRAIN,
   OCV and public input hashes; keep recipe/parameter/serialized-state hashes distinct.
4. Keep one owner-only workspace roster record per trial, including failed,
   refused, incomplete and untrained trials, independently of winner selection.
5. Add focused positive/negative tests; run static checks here and canonical CI
   remotely. Local application imports/tests/WSL/Docker/models/provider are forbidden
   in this author lane by Root. No local runtime baseline is claimed.

Opt-in is a local, bounded JSON document, never a network upload or evaluator
capability. Its scope is public battery practice only; existing program/staging
allowlists establish the material scope, not a caller Boolean. Defaults are unchanged.
Historical missing weights stay NOT_RETAINED. No refit, EVAL/hidden access, truth
join, fixed18 ScoreLab cohort expansion, official result, qualification or rights
policy is authorized. Original four-input/four-output semantics remain explicit.

DoD: reviewable source/tests/contract, required CI on exact head, delivered to
Root and Optimizer with consumer ACK and exact opt-in/extraction instructions.
Actual runtime retention and ScoreLab compatibility/admission remain unperformed
until Root supplies actual files and the consumer verifies them.

Hub impact: none; retired under OWNER-WORKFLOW-SPEED-01 / current OWNER-DX-03.
