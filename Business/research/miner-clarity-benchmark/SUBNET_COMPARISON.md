# Public subnet miner communication: a desk benchmark

Reviewed 2026-10-11 against immutable Git snapshots in [SOURCES](SOURCES.md). This compares documentation and observed public rendering, not miner installation, economic performance, correctness of another subnet's judge or confidential community discussions.

## Sampling and what “successful” can mean

The owner asks to learn from successful subnets. No primary, comparable series of active miner retention, net profitability, installation completion or support resolution was available in the reviewed sources. We therefore select **visible systems with public product/code surfaces and contrasting miner jobs**, rather than inventing a success league table. Chutes has an inference product; Gradients exposes training and miner routes; Crusades exposes performance competition; Distil documents distillation; Affine publishes a current miner/epoch workflow. Templar's completed training programme is included solely as a historical transition case. None supplies causal evidence that documentation produced adoption.

Desk criteria: a named miner deliverable, score/win explanation, prerequisites/cost responsibility, public rehearsal, commitment/entry steps, status/reason/next-action feedback, and current-versus-historical rule/version. “Documented” means found in the inspected source, not independently verified operational.

## What to borrow and what to avoid

| Case / entry source | Structure, posted target and feedback | Practice/testnet and cost responsibility | Carbon lesson |
| --- | --- | --- | --- |
| **Chutes SN64**, [pinned miner README](https://github.com/chutesai/chutes-miner/blob/44c6603ced87c5108359a30fa1e1e6c12f864557/README.md) | Task summary, component map, ordered setup, monitoring and symptom/fix table. Incentive explanation is compute contribution rather than a model accuracy contest | Miner supplies infrastructure; current README requires TDX TEE workers and separates control-plane provisioning from worker tooling. No measured setup-time cohort found | Borrow prerequisites before purchase and fault diagnostics. A simple customer API quickstart is not a simple GPU-miner deployment |
| **Gradients SN56**, [pinned Miner Guide](https://github.com/gradients-ai/G.O.D/blob/de5ea9cd90bfff32d59a8403cb62433a8ce46bab/docs/miner.md) | Starts with entry checklist; describes recipe/commit, runtime/output contract, UTC schedule, scoring and common failure modes | Public local test examples and explicit mainnet/testnet route; validators run tournament compute, miner maintains its endpoint and satisfies entry requirements. Winners' code publication is disclosed | Closest match to Carbon's submitted-recipe workflow. Put exact artifact/contract and local validation before entry; link costs and rights beside Submit |
| **Crusades SN3**, [pinned README](https://github.com/one-covenant/crusades/blob/5b9a0c25a705afcd70bfbf135cd79095ba7bebe2/README.md) | Single training-file interface, MFU objective, examples and TUI with scores/status/history | Public validator-container rehearsal and local/test network route; hardware equivalence caveat. No measured onboarding duration | Borrow contract-matching public preflight, not hidden exam content. The same README describes a smaller model early and a larger model later: machine-resolved current configuration should override duplicated prose |
| **Distil SN97**, [pinned FAQ](https://github.com/unarbos/distil/blob/88751532bea283d812df98c0b8e304465344eed0/docs/MINER_FAQ.md), [README](https://github.com/unarbos/distil/blob/88751532bea283d812df98c0b8e304465344eed0/README.md) | Getting-started, axis playbook, disqualification reasons, API status and pre-commit checking | Public model checks and king comparison; weights/hosting and immutable submission rules disclosed. Documentation is detailed, not a short path | Borrow a symptom→cause→fix table and pre-commit validation. README/FAQ settings diverge; [configuration](https://github.com/unarbos/distil/blob/88751532bea283d812df98c0b8e304465344eed0/frontend/src/lib/subnet-config.json) explicitly controls. The linked dashboard rendered an Arbos agent login here, so dashboard availability is **unverified**, not a measured outage |
| **Affine SN120**, [pinned quickstart](https://github.com/AffineFoundation/affine/blob/d59a6bde8bc88c975b3b2523732b2d2af9a857a0/docs/MINER_QUICKSTART.md) | Current signed opening/source governs; distinguishes Git research from deployed client and includes update/recovery steps | Local activation preview and mock/check routes; runtime/hardware profile and deadlines explicit. Public [dashboard](https://affine.io/) showed loading/unavailable text in the web rendering; live client data not verified | Borrow active contract/source identification and restart-safe diagnostic guidance. Cached search results pointed to removed older files and a different miner workflow; source dates alone cannot prove an operational contract |
| **Templar, historical SN3**, [pinned README](https://github.com/one-covenant/templar/blob/0fefc2ad763cd4cfda080e58267fe562455f3b45/README.md) | Clearly says dormant and links Crusades; legacy miner guide still has an older burn/“coming soon” message | Old GPU training setup must not be treated as current entry instructions | Put a front-page availability banner and successor link on every retired guide; one accurate root page does not repair every search landing page |

These are **communication observations**, not claims of equivalent scientific credibility or adoption. Carbon should match the useful entry/feedback patterns, while retaining its own hidden-seed, grading and submitted-work rules. Model weights, code or exact eval-data publication in another subnet are not permission for Carbon to expose protected material.

## Onboarding time: what the numbers actually describe

| Case | Public timing fact | Time from new miner to valid first entry |
| --- | --- | --- |
| Chutes | README describes a **7-day** compute aggregation window (SOURCED fixed point) | **HUMAN_INPUT**; reward averaging is not install time |
| Gradients | Guide requires registration/Fiber posting at least **1 hour** before scheduled tournament start (SOURCED minimum, no upper bound); explicit UTC schedule | **HUMAN_INPUT**; entry lead time is not engineering setup time |
| Crusades | Local benchmark/container path, no numerical complete-onboarding promise in inspected README | **HUMAN_INPUT**; downloads/build, compatible hardware and preflight remain work |
| Distil | Pre-submission checks, immutable commitment and evaluation-status API | **HUMAN_INPUT**; self-check success is not official score latency |
| Affine | Epoch and deadline-aware current client guidance | **HUMAN_INPUT**; signed activation and admitted source are separate steps |
| Carbon copied draft | Public screening feed **about 18 hours** later; own status described as immediate (DRAFT claim) | **HUMAN_INPUT**; current [MCP](https://github.com/carbonphysicsai/Carbon/blob/ca71b8ecf500250f57c9dfd731950e1ff5e1f731/carbon/miner_mcp/README.md) distinguishes open reads, admitted research and available intake |

The quantitative ledger preserves fixed source facts as equal triplets, one-sided bounds as null where appropriate, and proposed targets as ASSUMPTION. No “mine in minutes” inference follows from a customer-side API demo.

## Public friction evidence, with honest limits

[Chutes issue 135](https://github.com/chutesai/chutes-miner/issues/135) reports verification/authentication failing before the GPU check; [issue 127](https://github.com/chutesai/chutes-miner/issues/127) reports an advertised-hardware/runtime mismatch; [issue 102](https://github.com/chutesai/chutes-miner/issues/102) reports transient contradictory activation state. These are **reporters' historical claims**, not reproduced bugs or proof of today's TEE path failing. A current protocol migration can supersede the affected path.

[Templar issue 693](https://github.com/one-covenant/templar/issues/693) asks whether an ARM/GB10 host produces compatible results; it is a compatibility question, not measured failure. Gradients' common-failure list covers commit identity, private repository access, runtime/output constraints and invalid dependencies. Distil's FAQ documents disqualification/recovery and warns about historical scoring failures. The latter are **maintainer-curated explanations**, not a representative complaint survey.

The transferable categories are: environment mismatch, entry/commit mismatch, ambiguous pending status, delayed/missing score, unexpected rights/cost, and obsolete landing pages. This bounded sample does **not** estimate frequency or prevalence. No public Carbon miner cohort or support log was measured.

## A clarity test Carbon can run later

Observe a fresh supported miner, human or agent, answer what to build, what passes, what wins, what costs, what becomes public, and what to do next. Record clicks, elapsed active/setup/waiting time, incorrect answers, preflight failures and abandoned stages. Include a new user and an experienced miner; keep each receipt separate instead of averaging away blockers.

Proposed targets **ASSUMPTION low/base/high**: rule comprehension **2/3/5 minutes**; small public preflight on an already configured supported host **15/30/60 minutes**. Success is correct understanding plus a valid public-practice receipt; it is not an official score, reward or physics qualification. Cold installation, registration and evaluation latency need separate observed ranges. Owner chooses acceptance targets; no walkthrough or miner execution was run for this research.
