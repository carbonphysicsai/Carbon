# Carbon Agent Wave Status

**Current wave:** B
**State:** **active in bounded development scope**
**Wave A:** closed in bounded engineering scope
**Controlling register:** `.agent/WAVE_B.md` version 0.4
**Next selected ticket:** B-01
**B-01 status:** `in_progress`
**B-01 development:** bounded orientation/evidence candidate on `agent/b-01-orientation`
**Executor:** any (Codex / Hermes / human / …) — see `agent_pack/EXECUTION_PROTOCOL.md`  
**Build_Out:** **v1.4** §12 Wave A + `Design_Specs/Build_Out_Constitutional_Overlay.md`  
**Repository constitution:** `CONSTITUTION.md`  
**Scientific canon:** `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`  
**Long-horizon plan:** `Design_Specs/Agentic_Development_Master_Plan.md`  
**Agent constitution:** repo root `AGENTS.md`  
**Spec pin:** record commit SHA and current authority set in `.agent/ORIENTATION.md` at new major-wave orientation

> **Authority state.** PR #54 normally merged the independently reviewed,
> green seven-file Wave B governance change as
> `cce1efec19601d4e460676e9b422cc569b9d66d0`, tree
> `a270616e2d54401f5c73b408b469d8c9f6a8b1f9`. B-01 began later on its
> dedicated branch and is now `in_progress`. This status change authorizes no
> later Wave-B ticket or runtime implementation.

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
current authority → one ticket → baseline tests → implement → tests → review/merge → board evidence → next
```

- Sequential by default.
- Harness-native worktrees/branches preferred.
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

Merged PR #54 made [`WAVE_B.md`](./WAVE_B.md) version 0.4 the
controlling Wave B dependency board. Its architecture
contract remains version 0.3 at
[`Design_Specs/Miner_MCP_Wave_B_Research_Contract.md`](../Design_Specs/Miner_MCP_Wave_B_Research_Contract.md),
and sessions enter through
[`WAVE_B_CODEX_HANDOFF.md`](./WAVE_B_CODEX_HANDOFF.md). B-01 is the selected
`in_progress` ticket on its dedicated branch. B-02 and every later ticket
remain `todo` and unstarted.

No multi-role approval bundle, exact-byte activation approval, or separate
activation closeout is required before B-01 development. Authorization comes
from the active wave and selected ticket. Material decisions must be recorded
and delivered through the non-blocking lead-notification process in
`.agent/DECISIONS.md`, the Wave B board, and the handoff. Harshdeep Sharma
(`@harshaa765`) may amend, reject, or supersede such a decision; silence is not
a gate, while a lead `REQUEST_CHANGES` review or explicit `BLOCKED` direction
pauses the affected change. B-07R and B-07S remain later architecture and exact
service-protocol ratification gates. Scientific truth and qualification,
security acceptance, rights/legal policy, live economics, launch, production,
`LIVE`, frontier, product, settlement, chain, weight, and emission authority
remain unearned and human-owned where `AGENTS.md` reserves them.

A baseline-pinned program-level testnet-to-mainnet roadmap, with the Wave B effort rebaseline, is available at [`launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.3.md`](../launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.3.md); it does not replace this live ticket board or authorize launch.

## Notes

- Do not mark done without test/file/review evidence.
- Before/after each ticket: run the required baseline pytest/PoC smoke.
- Wave-A `done` state and `.agent/WAVE_A_REPORT.md` are authoritative through
  the normally merged PR #52 closeout, only in their bounded engineering scope.
- Do not convert fixture/stub success into scientific, security, network, commercial, or production qualification claims.
