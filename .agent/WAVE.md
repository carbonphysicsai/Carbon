# Carbon Agent Wave Status

**Current wave:** B
**State:** **active in bounded development scope**
**Wave A:** closed in bounded engineering scope
**Controlling register:** `.agent/WAVE_B.md` version 1.1
**Selected ticket:** B-04 — `in_progress`
**Selected phase:** runtime implementation only after B-01F's conditional
completion gate; paused before that gate
**B-01F status:** `done` only after its exact reviewed normal merge, exact-main
`Merge gate`, and posted completed external receipt; before that predicate it
is the owner-directed `in_progress` insertion
**B-01G status:** `todo`; non-blocking for B-04
**B-04 contract:** ratified bounded engineering contract; implementation and
all qualification remain unearned
**B-03 status:** `done` in bounded merged engineering scope
**B-01E status:** `done` only under the closeout authority gate below
**B-01 dependency:** `done`
**B-02A status:** `done` in bounded merged engineering scope
**B-07R status:** `done` in bounded merged engineering-architecture scope
**B-02B status:** `done` in bounded merged engineering scope
**B-02C status:** `done` in bounded merged engineering scope
**Executor:** any (Codex / Hermes / human / …) — see `agent_pack/EXECUTION_PROTOCOL.md`  
**Build_Out:** **v1.5** §12 Wave A + `Design_Specs/Build_Out_Constitutional_Overlay.md`
**Repository constitution:** `CONSTITUTION.md`  
**Scientific canon:** `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`  
**Long-horizon plan:** `Design_Specs/Agentic_Development_Master_Plan.md`  
**Agent constitution:** repo root `AGENTS.md`  
**Spec pin:** record commit SHA and current authority set in `.agent/ORIENTATION.md` at new major-wave orientation

> **B-02A closed.** PR #60 normally merged exact reviewed head
> `f285399138ecfe95352d429bc26051b0a5fecbcf`, tree
> `61a4463ac459f7fe96545f2746511d6940246f57`, as
> `58ea866de52e3853b0b45e3217ee0625302aa663` with the same tree. Exact-head
> CI `33341717012`, Greptile 5/5 with no blocking failure and zero unresolved
> threads, and exact-main CI `33342015346` passed. Issue #42 comment
> `5470746417` delivered B-02A-D1 through B-02A-D11. B-02A is `done` only in
> its bounded contract, implementation, and engineering-test scope.

> **B-07R closed.** PR #62 normally merged exact reviewed head
> `038aa3ffe51aaafe99803553380c396429144977`, tree
> `5cf1aaf1fd11ef4775c170dd938c3190fa14145b`, as
> `6e2a2640a6bd26755064acb0616382c8dcc0ba37` with the same tree. Exact-head
> CI `33347664046`, Greptile 5/5 with no blocking failure and zero unresolved
> threads, and exact-main CI `33347826166` passed. Issue #42 completion comment
> `5472621851` records the external completion predicate. B-07R is `done` only
> for the bounded working engineering architecture; B-07S still owns exact
> protocol mechanics.

> **Authority state.** PR #54 activated Wave B governance; PRs #57–#59 closed
> B-01/B-01E and selected B-02A; PR #60 closed B-02A with the exact evidence
> above. Governance PR #61 superseded the former affirmative
> pre-implementation contract gate:
> agent-authorized engineering decisions are selected, recorded, notified,
> implemented, tested, and independently reviewed before merge. A human-
> reserved value stops its affected behavior and remains fail closed; it stops
> the whole ticket only when no correct bounded continuation exists. B-07R's
> exact completion predicate has passed at the identities above.

> **B-02B closed.** PR #64 normally merged exact reviewed head
> `68189e7068715a5d8054f0f7e64dc981ae1c37aa`, tree
> `45273c527684b94afeb2f01b66a774b5426b6e0e`, as
> `b10b6e74fb3f8ab8a7427a6763c7db4f41341083` with the same tree and ordered
> parents `1c012468545f448aa758daf7dec17e409bb13bbc`,
> `68189e7068715a5d8054f0f7e64dc981ae1c37aa`. Exact-head CI `33362051770`,
> Greptile 5/5 on exact-head check `99413062552` with no blocking failure and
> zero unresolved threads, and exact-main CI `33368352662` passed. B-02B is
> `done` only in its bounded contract, implementation, and engineering-test
> scope.

> **B-02C closed.** PR #66 normally merged repaired exact reviewed head
> `a30865d2349f1cc6e725f1ea15e923f8d7893e4c`, tree
> `eb9b0c9b899cc4be9c8e9b22c16a5a3a48406a12`, as
> `1dc41288e2d0e516de21d05dc168b188791c39f5` with the same tree and ordered
> parents `319a765860ac6e93018124bd57a84bfd6679672e`,
> `a30865d2349f1cc6e725f1ea15e923f8d7893e4c`. Repaired exact-head CI
> `33388174967`, Greptile 5/5 on exact-head check `99475440630` with zero
> comments, annotations, or unresolved threads, and exact-main CI
> `33388595061` passed. B-02C is `done` only in its bounded contract,
> implementation, and engineering-test scope.

> **B-03 closed.** PR #69 normally merged exact reviewed head
> `702bf274b1a0c4bfefa075d8da08d3e7217a53d1`, tree
> `65dc9f5da4368482ad8ece155a63ff24ef46bf24`, as
> `d5d1372f1311132ed9d60e10e36c4fb7d43a2473` with the same tree and ordered
> parents `b86daa5d8b0f8b3e86bb82c2661f405747a200df`,
> `702bf274b1a0c4bfefa075d8da08d3e7217a53d1`. Exact-head CI
> `33452836347`, Greptile check `99686337091` on the exact reviewed head with
> zero comments and unresolved threads, and exact-main push CI `33460078744`
> passed. Issue #42 closeout comment `5487728238` records the immutable merge
> evidence. B-03 is `done` only in bounded merged engineering scope. Version
> 1.0 selected B-04 `in_progress` for working-contract authoring only and
> prohibited implementation until the exact contract tree normally merged and
> exact-main CI succeeded. PR #72's external receipt now establishes that
> historical contract gate.

> **B-04 contract ratified; B-01F inserted.** PR #72's external completion
> receipt establishes the exact reviewed contract, required exact-head checks
> and Greptile, normal reviewed-tree-preserving merge, and exact-main checks.
> B-04 retains `SPECIFIED: YES`, `RATIFIED_ENGINEERING_CONTRACT: YES`, and
> `IMPLEMENTED: NO`; every qualification and `LIVE` state remains `NO`.
> `OWNER-DX-01` temporarily inserts B-01F before B-04 runtime without amending
> the contract and queues B-01G as non-blocking `todo`. This candidate's B-01F
> `done` and B-04 runtime selection become effective only after the exact B-01F
> final head/tree passes scope-required checks, `Merge gate`, and Greptile;
> normally merges with reviewed-tree preservation; and passes exact-main
> `Merge gate`; and its completed normalized external receipt is posted.
> Until then B-04 runtime remains paused.

> **Authoritative Wave-A closeout evidence:** A-1 and A0-A12 are `done` only in
> their recorded bounded engineering scopes. PR #50 ratified A12-R1 through
> A12-R12; PR #51 merged the bounded invariant-judge implementation; and PR #52
> normally merged the exact reviewed Wave-A closeout head
> `f7efe935601db862e9a27947c1f100e69452d05e` as signed merge
> `62f52065b6695fc5f0e1e77562da4b3774eaaf3e`, tree
> `0cc4fc8661663b29d954eb617323cc4fefc6c9cb`. GitHub Actions run
> `33255939632`, attempt 2, passed the exact 28-test invariant lane, all 2310
> CPU tests, and the no-new-debt quality gate on that merge. The closeout audit
> passed `24/24` A12 ticket criteria and `9/9` Build Out Wave-A acceptance
> bullets; `.agent/WAVE_A_REPORT.md` records the bounded evidence and ceilings.
> Wave A closure creates no scientific, security, network, commercial,
> production, `LIVE`, launch, frontier, settlement, weight, or emission
> authority.

## Workflow

```text
current authority
→ one ticket / one PR by default
→ working contract and vertical implementation slices
→ canonical validation
→ exact-head Merge gate and Greptile
→ repair valid findings / zero unresolved threads
→ normal exact-expected-head merge
→ reviewed-tree and exact-main verification
→ external completion receipt / next ready ticket
```

- Sequential by default.
- Dedicated worktrees/branches required by default; use
  `./scripts/dev/canonical.sh` on noncanonical hosts.
- Model routing is **not** part of this board (optional under `agent_pack/executors/`).
- Future waves in the Agentic Master Plan are planning authority, not current implementation authorization.

## Wave A checklist

| ID | Build_Out | Item | Status | Evidence |
|----|-----------|------|--------|----------|
| A-1 | — | Orientation — repo map, KEEP/WRAP table, ORIENTATION.md | done | `.agent/ORIENTATION.md` audits `0eed4e9`; DoD checked in `.agent/tickets/A-1_orientation.md`; maintainer dispositions in `.agent/DECISIONS.md` |
| A0 | C0 | Package layout (audit-first; map poc/Carbon_Logic) | done | Root `carbon/` + 14 reserved roles; isolated `pip install --no-deps -e` and outside-tree imports pass; exact base/head workflow delta has no A0 regression; evidence in `.agent/DECISIONS.md` |
| A1 | C0 | CI skeleton (pytest, CPU) + preserve existing CI | done | Corrective PR #9 merged as `819da3c163c2fb9476a6881aab8740cc6984066e` after independent rereview; final-head CI run `32326384939` passed 27 CPU tests and the code-quality gate |
| A2 | C2 | Strategy schema + dry_validate | done | PR #12 reviewed final head `d73f697ebd9df9b8c96b7a46fd4c9986444f0928` merged as `bfc0b97e1b16625141de3950428bc2fdf69f42ea`; post-merge main CI run `32360050671` passed 258 default CPU tests and the code-quality job |
| A3 | C1 | Challenge registry + LIVE qualification **hash** gate | done | Exact base `e6fb20b1dc361ded442fcf41d118cea5f2c775cd`; independently reviewed/rereviewed final head `149f9a74351b02a9b615d0015c22b74187ab0f55` passed PR CI `32377387086`, merged as `69b938d1c4fd0aca58276940d15df50b1b68e5d1`, and is ancestral to current `main`; post-merge push CI `32379421897` passed 392 CPU tests and Code quality at unchanged `Ruff 757/776; Black 62/68` with no new debt and changed files clean; at A3 closeout, A4 remained `todo` and had not started |
| A4 | C6 | Seeding domains + leakage tests | done | Exact base `e13baf312b811e2fd6784856c56d851a15f153fd`; independently reviewed head `b0f79cf96b7cd489a97a7a4dd49285d762c962aa` passed PR CI `32440327141`, merged normally in PR #17 as `120eab02e406bda280d9c361bbbb7d8ef7a08330`, and is ancestral to current `main`; post-merge push CI `32444857456` passed 622 CPU tests and Code quality at unchanged `Ruff 757/776; Black 62/68`, with no new debt and all eight implementation Python files clean |
| A5 | C5 | Scoring engine + fixture Score Pack | done | Reviewed head `fc2f27a7150d5ed0e374e7cd79eea40ef7ede556` from base `af43d68ec3b9dcfd8818a61ab219759b2c859d78` passed PR CI `32474141634` (`923` CPU tests in `9.57s`; Code quality `Ruff 757/776; Black 62/68`, removed debt `Ruff 19, Black 6`, eight changed Python files, no new debt/all clean) and merged normally in PR #20 as `6f813e979ef6edde2b8f1821d1ac26f62938633a`; the head is ancestral to `main` and its tree `54e3472e34731b64d796f8db7d091da70c6afd43` equals the merge tree; post-merge push CI `32494936120` passed `923` CPU tests in `10.23s` with the same quality inventory and no new debt; fixture `tests/fixtures/score_packs/a5_fixture_v1.json` remains 2,126 bytes at `sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57`; TESTED is bounded fixture-CPU-only and PRODUCTION-QUALIFIED remains NO |
| A6 | C12 | Card store + Phase 0 disclosure filter | done | Reviewed implementation `569d450cce5943089874ad89f62f80ab5182d97a` from exact base `bfb8412d9aae3782d59e9814fc5b3a8c6379f86f`, synchronized at `20a1d2f74f10b24ddb8922c6b87c7325828299b3`, and merged normally in PR #23 as `5c7c3a924d305a386ed92d6f054981761d5c74b7`; merge tree `d302aaf46f211030faf81920deee4dff27eac4a4` equals the synchronized-head tree, reviewed ancestry and all five implementation blobs are preserved; PR CI `32550337528` and post-merge CI `32551173696` passed; focused `181`, related `499`, full `1104`, and fresh-wheel/outside-tree `1` passed; quality remained `Ruff 757/776; Black 62/68`, four changed Python files clean, no new debt; TESTED only to the bounded CPU/security/import scope; PRODUCTION-QUALIFIED: NO |
| A7 | C13 | Fees + submission_id + FSM (**CANCELLED**, FAILED_INFRA refund) | done | Exact base `f8cf1a030415778f519d55b85d8e287f09cdeba2` and reviewed head `f5ec1315a5ae501c2726fc0fbd6d0fa85c56b4b9` merged normally in PR #26 as `5b7b38a4db3b0a7bbf2d97ae872a28a3d885d77d`; reviewed/merge tree `803fcf53ed99399c141e73d050f962847aeb36f8` is identical; post-merge push run `32622988239` passed `1423` CPU tests in `26.75s` with unchanged `Ruff 757/776; Black 62/68`, seven changed Python files clean, and no new debt; IMPLEMENTED only for the bounded fixture-capable, process-local scope; TESTED only for the recorded CPU/security/concurrency/import/wheel/quality scope; PRODUCTION-QUALIFIED: NO |
| A8 | §5 | TrainEvalAPI **fixture stub** (structurally non-production/non-emission) | done | PR #28 ratified A8-R1–A8-R15 by normal merge `872be272fe80df19c28611388fc4e1ebcd7b4900`. Original implementation `e16677b54e6523b1203d09c7807a736909041ac9` synchronized as reviewed head `872736cdee0b4149856a68229b34c69e2b2f0490`, tree `9d7f5ee3e78edbc72dc75391fafb87373ae3019d`, and merged normally in PR #29 as `d0011e959622b65f6ae737db7477062104bafa33`; push CI `32676389502` passed `1562` CPU tests. Independent closeout review then blocked on direct A8 construction of A5 `InternalResult` and silent normalization/omitted perturbation of malformed `SeedPin.seed_scheme`; the corrective repair also broadened the A5-construction guard from `service.py` to every A8 module. Corrective head `eb1af294edc35b25ea36a699968092470e5d2afa` merged normally in PR #30 as current main `b30c3f5fc2a53df0611d5e8b80120fbf4b64531c`, tree `db94ca592af2ee808976c615b97065dbcbeb7f24`, with exact second-parent/tree equality. Post-corrective push CI `32686140393` passed `1584` CPU tests in `42.19s`; quality remained `Ruff 757/776; Black 62/68`, removed debt `Ruff 19, Black 6`, six changed Python files clean, and no new debt. Recorded evidence includes focused `649`, related `1197`, full `1584`, unchanged golden selection `17` with exact combined `0.8947523571654831`, and fresh Python 3.11.11 wheel/outside-tree `-I` import with exact six exports, zero blocked optional-heavy/later modules, SHA-256 `a37f4d0f1545582ae42a2a4de0a1d56276de4c64fbd5b9bc547fd63cfb408f25`. All `25/25` bounded implementation criteria are checked; this documentation-only candidate makes `done` authoritative only after independent review, explicit human authorization, and merge. SPECIFIED / RATIFIED: YES; IMPLEMENTED: YES only for the bounded fixture-official, deterministic, process-local stub scope including the reviewed repair; TESTED: YES only for the exact recorded CPU/security/import/wheel/quality scope; SCIENTIFICALLY_QUALIFIED: NO; SECURITY_QUALIFIED: NO; NETWORK_QUALIFIED: NO; COMMERCIALLY_VALIDATED: NO; PRODUCTION_QUALIFIED: NO. No mock/light or production adapter, real training/miner-code execution, sandbox/container qualification, authenticated provenance, LIVE science, evidence, frontier, treasury, chain, weight, or emission authority exists. |
| A9 | C9 | MCP tools: get_challenge_info, get_prior, get_mock_scaffold, dry_validate, estimate, submit, get_submission_result | done | PR #32 ratified A9-R1–A9-R15 by normal merge `47a62b2397b4125bb608eb69bf0e3dc6360c519d`, tree `4f55d28d06ef6f06cf521fd8f04bbf3881e58379`, with exact reviewed-head/tree equality and empty diff. PR #33 implemented the seven-tool, exact-34-export bounded skeleton from exact reviewed implementation head `c9c324d1192c9c52009b15970e371d076a0b3e89` by normal merge `97d835f495cb7e3f194364cb4e674e2416531936`, tree `46e8a2d96e15f8bec58e3fb7b9fd28f0684f00b6`, again with exact reviewed-head/tree equality and empty diff. Independent repair `aea3f5db86dde5851f5ea02994e5f91866f477d1`, synchronization `1f921c1223f94cad87b9e52a0773c1299d2980a5`, computed-key repair `0830f479ec765905a016e86ea6a366bbc136e873`, variable-bound-key repair `ddca0d3c7c71361b80aacb5489c56e7f36e0783e`, and exact final repaired head/synchronization `dc88336f5edb544af5d4f4a82661f3f031de7603` were merged normally in PR #34 as `0099a198bf19845390a0a12825eac0eeef06ffd2`, tree `f934ea4f3c4f63b26e890a26f4c941f73519b73b`; the exact head/tree equals the merge, its diff is empty, and its prior-main manifest is only `tests/cpu/test_mcp_skeleton.py`, `+652/-20`, with all four production blobs unchanged. Greptile's exact-head summary states `Confidence Score: 5/5` and `No blocking failure remains.`; both substantive threads are resolved, unresolved count is zero, all four formal reviews remain `COMMENTED`, and review decision is empty. Post-merge CI runs `32713700257`, `32733665726`, and `32809955531` passed CPU totals `1584`, `1697`, and `1727`; their quality jobs retained `Ruff 757/776; Black 62/68`, removed debt `Ruff 19, Black 6`, and found respectively zero, five, and one changed Python files clean with no new debt. Fresh focused `143`, related `935`, combined `1078`, and full CPU `1727` passed. Recorded/fresh wheel SHA-256 values are `71cb3706e4bad091b5a5290210a666fccb07d296d83274548288a29a422d18fd` and `0f33d38334e9de15b7a28188e856180c55934129b9c92d473330326285359263`; fresh Python 3.11.11 outside-tree `-I` wheel import exposed exact 34 exports and loaded zero forbidden optional-heavy/later-wave modules. Independent closeout audit is `29/29 PASS`, `0 FAIL`. This documentation-only `done` becomes authoritative only after independent review, explicit human authorization, and normal merge. `SPECIFIED / RATIFIED: YES`; `IMPLEMENTED: YES` only for the bounded, process-local, in-process control/disclosure skeleton; `TESTED: YES` only for the exact recorded CPU/hostile-input/resource/concurrency/disclosure/dependency/import/wheel/quality engineering scope; `SCIENTIFICALLY_QUALIFIED: NO`; `SECURITY_QUALIFIED: NO`; `NETWORK_QUALIFIED: NO`; `COMMERCIALLY_VALIDATED: NO`; `PRODUCTION_QUALIFIED: NO`. No production provider/content/policy, prior publication, scaffold body, value authority, authentication, network/MCP-SDK transport, mock/light or real training execution, production context/backend, LIVE science, evidence/signature, A10+ leaderboard, A11 logging, A12 invariant, frontier, Product Qualification, treasury/settlement, chain, weight, or emission authority exists. |
| A10 | C14 | Leaderboard (public fields only) | done | PR #37 merged the bounded implementation as `3b2d96e287f06c24cc4d57b46dfc418359a9e97f` from reviewed head `6f505d5cffd69f0c3d4d0e6d71bb91233c0ce6b1`; reviewed and merge trees are exactly `6a6e95262773b9b2e22ad5c43837194f06e070a6` and their file diff is empty. Push run `32941840184` passed `1973` CPU tests and quality at `Ruff 757/776; Black 62/68`, removed debt `19/6`, five changed Python files clean, no new debt. Independent closeout audit: `57/57 PASS`, `0 FAIL`; documentation closeout merged normally in PR #38 as `404c039596b487cf2649bb1d73b80e9b49baaced`. Scope remains fixture-only, non-official, non-LIVE, non-emitting, non-frontier, non-product, non-network, and non-production; leaderboard rank is not a `FrontierAdvanceEvent` or Product Qualification. |
| A11 | C16 | Logging **+ metrics** / redaction / failure tags | done | A11-R1–A11-R18 ratified; reviewed head `e5ed60c4043abb3bfd2af945b5dd45b8e1996fcb` merged normally in PR #46 as signed commit `e2496e92eeae31befdaa430501bb9f00b0e6339e`, with identical reviewed/merge tree `3d6682803422497efc6bff26451c12d9c306f96c`; post-merge run `33199541335` passed `2310` CPU tests and quality; independent closeout audit `66/66 PASS`; bounded in-process IMPLEMENTED/TESTED only, all qualification ceilings remain NO |
| A12 | §2 | Invariant suite green in CI | done | A12-R1–A12-R12 were ratified in PR #50; bounded implementation merged in PR #51 as `2a8b273a1167588efb4a11159da5224264d5b37a`; and the exact reviewed closeout head merged normally in PR #52 as `62f52065b6695fc5f0e1e77562da4b3774eaaf3e`. Exact lane: `28` tests (`12` unique dedicated + `16` infrastructure); independent closeout: `24/24` ticket criteria and `9/9` Wave-A acceptance bullets; exact-main run `33255939632`, attempt 2, passed invariant, `2310` CPU, and quality. All qualification ceilings remain NO. |

**Statuses:** `todo` | `in_progress` | `done` | `blocked`

## Suggested order

```text
A-1 → A0 → A1 → A2 → A3 → A4 → A5 → A6 → A7 → A8 → A9 → A10 → A11 → A12
```

Recommended gate: human review after **A3**, then continue. A8 onward now also uses the constitutional reconciliation guard.

A9 depends on A2, A6, A7, A8. A12 depends on A4–A11.

## Post-Wave-A interpretation

The long-horizon canonical plan is
`Design_Specs/Agentic_Development_Master_Plan.md`. Its later waves remain
planning and sequencing authority until a prospective, reviewed, green, and
normally merged `.agent/WAVE.md` transition selects them. A future-wave plan
does not authorize implementation by itself.

Merged PR #54 made [`WAVE_B.md`](./WAVE_B.md) version 0.4 the initial
controlling Wave B dependency board. Version 0.5 recorded the owner-directed
B-01E insertion. Version 0.6 recorded proven B-02A closeout and B-07R's
delegated engineering ratification and conditional completion mechanism.
Version 0.7 records that the B-07R predicate passed and selected B-02B.
Version 0.8 records B-02B's exact reviewed merge and exact-main CI and selects
B-02C `in_progress`. Version 0.9 recorded B-02C's repaired exact reviewed
normal merge and exact-main CI and selected B-03. Version 1.0 records B-03's
exact reviewed-tree-preserving normal merge and exact-main CI and selects B-04
`in_progress` in contract phase. Version 1.1 records the B-04 contract's
ratified engineering maturity, inserts owner-directed B-01F before runtime,
queues non-blocking B-01G, and prepares the conditional B-01F `done` / B-04
runtime selection. That transition is authoritative only after the exact
B-01F reviewed tree normally merges, exact-main `Merge gate` passes, and the
completed normalized external receipt is posted. The
architecture
contract is version 0.4 at
[`Design_Specs/Miner_MCP_Wave_B_Research_Contract.md`](../Design_Specs/Miner_MCP_Wave_B_Research_Contract.md),
and sessions enter through
[`WAVE_B_CODEX_HANDOFF.md`](./WAVE_B_CODEX_HANDOFF.md). PR #59 normally merged
the closeout transition `B-01 done → B-01E done → B-02A next selected/todo`,
and its exact-main CI passed. B-01E owns only the canonical development
environment and legacy executable quarantine. PR #61 then normally merged the
delegated-decision governance described above, and PR #60 closed B-02A using
that model. B-07R's, B-02B's, and B-02C's external review, merge, and
exact-main-CI facts are recorded above and in their evidence records. B-04's
bounded engineering contract is ratified; real reference methods,
support, uncertainty, disagreement, qualification, security, operations,
production, and LIVE values remain unavailable.

No multi-role approval bundle, exact-byte activation approval, or separate
activation closeout is required before B-01 development. Authorization comes
from the active wave and selected ticket. Material decisions must be recorded
and delivered through the non-blocking lead-notification process in
`.agent/DECISIONS.md`, the Wave B board, and the handoff. Harshdeep Sharma
(`@harshaa765`) may amend, reject, or supersede such a decision; silence is not
a gate, while a lead `REQUEST_CHANGES` review or explicit `BLOCKED` direction
pauses the affected change. B-07R owns the merged working engineering
architecture under its completion predicate; B-07S remains the exact service-
protocol ratification gate. Scientific truth and qualification,
security acceptance, rights/legal policy, live economics, launch, production,
`LIVE`, frontier, product, settlement, chain, weight, and emission authority
remain unearned and human-owned where `AGENTS.md` reserves them.

The current program-level post-Wave-B testnet-to-mainnet roadmap is available
at [`launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.4.md`](../launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.4.md).
It begins real Bittensor integration only after Wave B and does not replace
this live ticket board, change the selected B-04 sequence/status, select a
future ticket, or authorize implementation or launch.

## Notes

- Do not mark done without exact-head test/file/`Merge gate`/Greptile evidence,
  normal reviewed-tree-preserving merge, exact-main `Merge gate`, and the
  posted completed external receipt.
- B-01E implementation evidence is recorded in
  `.agent/evidence/wave_b/b-01e.md`. Ordinary ticket evidence runs through
  `./scripts/dev/ci.sh` in the canonical Linux environment. On a noncanonical
  host use `./scripts/dev/canonical.sh`. Native-Windows
  diagnostics and archived PoC, Julia, network, JAX, chain, GPU, or other
  legacy validation are required only when the selected ticket explicitly
  owns that environment or archived component.
- Wave-A `done` state and `.agent/WAVE_A_REPORT.md` are authoritative through
  the normally merged PR #52 closeout, only in their bounded engineering scope.
- Do not convert fixture/stub success into scientific, security, network, commercial, or production qualification claims.
