# Mock Practice Execution Contract

**Status:** B-07C bounded implementation contract
**Authority ceiling:** in-process, synthetic, fixture-only, `MOCK_ONLY`
**Wire authority:** `Miner_MCP_Wave_B_Service_Protocol.md` and B-07S
**Research authority:** `Miner_MCP_Wave_B_Research_Contract.md` §6
**Implementation:** `carbon.practice`; lifecycle integration in `carbon.research`

## 1. Ownership

`carbon.practice` owns `MockTrainEvalService`, `PracticeScopeStatement`,
`PracticeMeasurementPack`, the versioned mock-pack registry, and the
non-champion scaffold provider. It consumes the exact B-07A/B-07S wire records;
it does not define another wire vocabulary.

B-07B remains the only owner of research task identity, idempotency, state,
cancellation, retries, private `ExperimentRecord`, and terminal
`ResearchReceipt`. B-02B remains the owner of resolved construction plans and
registered abstract randomness purposes. B-02C remains the owner of resource
policy decisions and observed resource receipts. A4 remains the owner of mock
entropy derivation. A5-A7 are outside this service.

## 2. Closed execution scope

The service supports only the four ratified task kinds:

- `RECONSTRUCTION_REHEARSAL` reconstructs synthetic artifacts and reports
  structural completion only.
- `PRACTICE` reports one bounded aggregate and observed range under the exact
  synthetic pack policy.
- `PAIRED_PRACTICE` requires two different Strategy hashes and B-07B's exactly
  one independently computed resolved-plan difference. Both strategies use the
  same fresh evaluation cases.
- `RESOURCE_CALIBRATION` has no practice-scope reference, performs no
  scientific comparison, and records observed resource facts only.

Task completion is operational completion, not scientific success.
Reference and measurement failures remain typed scientific non-results;
infrastructure and resource-limit failures remain non-scientific.

## 3. Exact identity and entropy

Every execution binds the exact Interaction Manifest, Challenge, Strategy and
resolved plan, compiler identity and environment, mock pack, measurement
contract and nominal practice measurement pack, resource policy/class, and
practice scope where applicable. The registry resolves exact content-addressed
versions and provides no `latest` alias or fallback.

The executor accepts only the exact nominal A4 `MockContext`. A private
process root and B-07B task identity provide fresh experiments and reproducible
replay of one pinned task. Training draws use the resolved plan's registered
abstract randomness purposes. Training, evaluation, and reference roles are
separated; paired evaluation cases are common. Start replay and polling do not
execute or resample.

Official and fixture-official contexts, entropy, packs, references, and seeds
are not accepted. Miners cannot supply seeds or select a mode, provider,
filesystem path, transport, credential, or executable.

## 4. Measurement, evidence, and disclosure

A `PracticeMeasurementPack` may name an existing public measurement contract
and implementation only with exact rights and separate non-authoritative
configuration identities. It cannot carry an official Score Pack, threshold,
weight, A5 invocation, or qualification claim.

Case-level draws, seeds, artifacts, references, and raw exceptions remain
private. The public receipt projector consumes only a pre-registered finding
definition plus a finite numeric observed band. The registered claim,
measurement identity, evidence class, and limitations are not supplied by the
executor or miner. Resource and reconstruction results do not create public
scientific findings.

The fixture policy permits only observed ranges, explicitly not confidence
intervals. Real population relationships, omissions, uncertainty, reference
adequacy, numerical floors, thresholds, disclosure, and qualification require
human authority and remain unresolved.

## 5. Mechanical non-authority

`carbon.practice` has no dependency on scoring, cards/publication, fees,
leaderboard, chain, TrainEval official execution, or MCP transport packages.
Practice objects and private aggregates are not A5 inputs, A6 publication
material, A7 evaluation authority, or evidence for leaderboard, frontier,
network, treasury, settlement, weight, or emission decisions.

Passing the fixture suite demonstrates an in-process engineering path only.
It does not qualify a production sandbox, real practice population, scientific
policy, security posture, rights posture, production operation, or LIVE use.
