# Carbon Agent Wave Status

**Current wave:** A  
**Executor:** any (Codex / Hermes / human / …) — see `agent_pack/EXECUTION_PROTOCOL.md`  
**Build_Out:** **v1.4** §12 Wave A + `Design_Specs/Build_Out_Constitutional_Overlay.md`  
**Repository constitution:** `CONSTITUTION.md`  
**Scientific canon:** `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`  
**Long-horizon plan:** `Design_Specs/Agentic_Development_Master_Plan.md`  
**Agent constitution:** repo root `AGENTS.md`  
**Spec pin:** record commit SHA and current authority set in `.agent/ORIENTATION.md` at new major-wave orientation

> **2026-08-23 constitutional reconciliation, with current A8 evidence:** A0–A7 remain accepted bounded foundations. A8's bounded fixture-official implementation is merged on current `main`, but A8 remains `in_progress`: administrative closeout was blocked by two contract-conformance defects now addressed only by the unmerged corrective candidate described below. A9 has not begun, A9–A12 remain `todo`, and no ticket is relabeled as scientifically, security, network, commercially, or production qualified. A8–A12 must follow the constitutional overlay; later-wave frontier, treasury, business, generalized-construction, and Physics-Intelligence architecture must not be smuggled into Wave A.

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
| A8 | §5 | TrainEvalAPI **fixture stub** (structurally non-production/non-emission) | in_progress | PR #29 merged the bounded fixture-official implementation on current `main` as `d0011e959622b65f6ae737db7477062104bafa33`, tree `9d7f5ee3e78edbc72dc75391fafb87373ae3019d`; post-merge CI `32676389502` passed `1562` CPU tests and the quality gate. Administrative closeout was blocked when independent review found two `IMPLEMENTATION_LAG` defects: A8 directly reconstructed A5 `InternalResult`, and malformed `SeedPin.seed_scheme` identity was silently normalized while A8 omitted that perturbation. `agent/a8-corrective-repair` is the unmerged corrective candidate: A5 owns recursive result copying, A4 rejects malformed current scheme identity, A8 delegates the copy, and the source guard scans every A8 module. Fresh candidate evidence: focused `649 passed in 7.08s`; related `1197 passed in 29.66s`; full `1584 passed in 34.33s`; unchanged oracle/golden/identity/retry/concurrency selection `17 passed in 0.16s`, retaining all nine literal synthetic scalars, literal leg scores, and exact combined `0.8947523571654831`; fresh Python 3.11.11 wheel/outside-tree `-I` import preserved the exact six exports with zero loaded blocked optional-heavy/later modules, SHA-256 `a37f4d0f1545582ae42a2a4de0a1d56276de4c64fbd5b9bc547fd63cfb408f25`; quality `Ruff 757/776; Black 62/68`, six changed Python files clean, no new debt. Full `25/25` acceptance and administrative closeout remain pending independent review, explicit human-authorized merge of the repair, and a later closeout; all ticket boxes remain unchecked. SPECIFIED / RATIFIED: YES; IMPLEMENTED: YES only for the bounded fixture-official, deterministic, process-local scope, with this conformance repair still a candidate; TESTED: current-main evidence exists, but full closure remains pending corrective review/merge; SCIENTIFICALLY_QUALIFIED: NO; SECURITY_QUALIFIED: NO; NETWORK_QUALIFIED: NO; COMMERCIALLY_VALIDATED: NO; PRODUCTION_QUALIFIED: NO. Future ReconstructionProtocol remains out of A8 scope. |
| A9 | C9 | MCP tools: info, prior, scaffold, dry_validate, estimate, submit, get_submission_result | todo | Free/mock signal must remain non-oracle and non-score-bearing |
| A10 | C14 | Leaderboard (public fields only) | todo | Leaderboard rank is not a `FrontierAdvanceEvent` or Product Qualification |
| A11 | C16 | Logging **+ metrics** / redaction / failure tags | todo | Preserve scientific/reference/reconstruction/infra separation where current types permit |
| A12 | §2 | Invariant suite green in CI | todo | Must include current enforceable constitutional invariants without pretending future frontier/treasury types exist |

**Statuses:** `todo` | `in_progress` | `done` | `blocked`

## Suggested order

```text
A-1 → A0 → A1 → A2 → A3 → A4 → A5 → A6 → A7 → A8 → A9 → A10 → A11 → A12
```

Recommended gate: human review after **A3**, then continue. A8 onward now also uses the constitutional reconciliation guard.

A9 depends on A2, A6, A7, A8. A12 depends on A4–A10.

## Post-Wave-A interpretation

The long-horizon canonical plan is `Design_Specs/Agentic_Development_Master_Plan.md`. Existing Build Out Waves B–G remain active sequencing concepts. Later Waves H–N in the Master Plan express the integrated destination architecture and require explicit owner authorization before implementation.

## Notes

- Do not mark done without test/file/review evidence.
- Before/after each ticket: run the required baseline pytest/PoC smoke.
- After all `done`, write `.agent/WAVE_A_REPORT.md`.
- Do not convert fixture/stub success into scientific, security, network, commercial, or production qualification claims.
