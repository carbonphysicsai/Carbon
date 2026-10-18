# Carbon — Agent Engineering Instructions

Carbon discovers, independently reconstructs and tests methods for making fast
physical models. Build small, coherent, testable changes that serve that goal.
Prefer working user flows and fewer active mechanisms over more code or process.
Repository-wide decision ownership lives in [CONSTITUTION.md](CONSTITUTION.md).

**Build toward [the Carbon operating vision](docs/development/CARBON_BUILD_TARGET.md).**
It is the owner-approved target for this migration, not a new approval layer.
A task should visibly advance that normal flow or remove a real obstacle to it.
Team owners make routine reversible decisions autonomously; Root coordinates
scope and genuine cross-team/reserved decisions. Do not create work to stay busy.

The current owner-authorized lean migration replaces construction-level,
backbone and change-combination permission ladders with one reproducible recipe:
pinned construction source/dependencies, fixed Challenge TRAIN, fresh model
construction, and separate Carbon-controlled evaluation. Preserve the working
Bittensor wiring. ScoreLab is a thin model-versus-solver workbench over the same
versioned scoring implementation used by validators: physics/constraints,
accuracy, then the Challenge's declared performance objective. This is a build
target, not a claim of implemented universal compatibility or qualification.

Public local experimentation does not require an official receiving validator.
Official submission separately requires the actual served contract. Recipe
resource identity is the Challenge's construction policy, not a private host
profile or operator TEST grant. Miner and validator each use their own compute.
Construction code never gains judge authority; pretrained model ingress is not
allowed. Broad source access is not proof that encoded pretrained information
can always be detected.

Development Hub files are frozen history (OWNER-WORKFLOW-SPEED-01). No Hub
map, event, declaration, regeneration or snapshot repin is required. Historical
decisions stay in `.agent/DECISIONS.md`; new durable decisions use separate files
under `.agent/decisions/`. Relevant existing Challenge research-environment,
training-budget, admission, development-rule and network authorizations retain
their exact domain scope. They are not prerequisites for unrelated development
or a grant of scientific, security, economic, deployment or public-network power.

---

# 1. Read the authority relevant to the task

At a new ticket or major change, read `CONSTITUTION.md`,
`.agent/INVARIANTS.md`, the current authorized task, and the domain specifications
for the behavior being changed. Check `.agent/WAVE.md` and relevant decisions
for dependencies and history; a new direct owner assignment may supersede an
older queue. Record that change in the existing task record, not another board.

Use `.agent/DELIVERY_PROTOCOL.md` for delivery and
`.agent/DELEGATED_DECISION_PROTOCOL.md` for decision ownership. These are single
sources, not extra approval stages. Refresh relevant reads when their version,
scope or authority changes; do not repeat unrelated repository archaeology.

Consult `Design_Specs/Build_Out.md` and its constitutional overlay when sequencing
or migration is affected. The Agentic Development Master Plan supplies relevant
future constraints, not extra implementation permission or current prerequisites.
Read Business authority for business/rights changes and
`docs/publications/README.md` for public claims. Verify repository evidence;
do not rely on an old orientation snapshot as current runtime truth.

---

# 2. Resolve authority by domain

`CONSTITUTION.md` maps domain owners. Scientific canon governs scientific
meaning; current domain specifications govern runtime behavior. Tickets and
current owner directions define authorized engineering scope. Publications and
historical plans cannot activate capabilities.

Identify a conflict as documentation lag, implementation lag, migration, or a
new owner decision. An already authorized migration is engineering work, not a
reason to ask the owner to authorize the same goal again. Select reversible
implementation details within scope and document material consequences.

For a genuinely reserved unresolved decision, stop only the affected behavior,
keep the missing value explicit and fail closed, and state the smallest decision
needed. Continue independent authorized work. Never resolve a conflict by
silently changing science, security acceptance, economics or historical meaning.
Current direct human instructions and actual enforced protections take precedence
over repository workflow defaults; this cleanup does not waive them.

---

# 3. Human ownership

Agents may implement software, interfaces, tests, infrastructure and explicitly
specified scientific logic. They do not independently grant scientific or
security qualification, choose production tolerances/populations, activate LIVE,
change live economics, decide rights/IP policy, authorize production deployment,
or assert commercial traction. Missing reserved values remain explicit.
An engineering test pass is not any of those decisions.

---

# 4. Inspect and reuse before adding

Trace the relevant canonical code, callers, public interfaces, persistence,
tests and CI. Consult `.agent/CODE_AUTHORITY.toml` and
`docs/history/LEGACY_CODE_INDEX.md` before deliberate archive reuse. Archive
presence is not implementation authority; use its exact recorded ref.
`.agent/ORIENTATION.md` is historical archaeology, not a live repository map.

Prefer **KEEP -> WRAP -> REPAIR -> REPLACE**. Remove an obsolete path with its
tested caller replacement. Do not create a parallel framework, per-library
permission system, duplicate tracker or extra handoff to avoid integrating the
working components. Compatibility code needs an identified consumer and explicit
historical semantics. Moving code to a legacy file is relocation, not deletion.
Each team has authority to perform this cleanup in its owned scope, including
replacing obsolete permission-contract tests with new behavior/boundary tests.
Do not delete a real failing invariant to obtain green. Coordinate shared paths
with their owner; no separate cleanup approval is needed.
Do not purge unrelated code, artifacts or worktrees to improve a line count.

---

# 5. Implement science; do not invent it

Reuse actual registered scientific decisions. Do not invent production physical
thresholds, solver tolerances, population/sampling laws, uncertainty floors,
qualification criteria or scoring coefficients. Do not reopen an unchanged
accepted value merely to wire software together.

Use `HUMAN_INPUT`, `None`, or a typed unresolved state for a missing reserved
value. Synthetic fixture values are allowed only in a structurally separated
non-production path. Missing production qualification does not prevent that
path from testing the software. Reference failure remains distinct from
candidate failure; never fabricate truth or silently alter the denominator.

---

# 6. Core implementation invariants

These bind current work; the historical Wave-A labels do not restrict an explicitly authorized migration.

1. **No hidden-evaluation leakage.** Official seeds, derived seeds, draw IDs, reversible IDs, protected samples, private metadata, or reconstruction-sensitive hidden state never appear in miner/public surfaces.
2. **Mock isolation.** Mock/light/estimate/scaffold/free execution never accesses official packs, seeds, protected exam data, or private validator state.
3. **Pinned official evaluation.** Official results bind immutable material versions/identities required by the active spec.
4. **Disclosure is allow-listed.** Internal fields remain private unless explicitly authorized for the target audience.
5. **LIVE requires human qualification.** No agent flips LIVE, signs qualification, or declares production scientific readiness.
6. **Untrusted execution is hostile.** Production miner-controlled workloads require explicit compute/memory/filesystem/network/process/wall-clock isolation.
7. **Infrastructure failure is not scientific failure.** Preserve typed `FAILED_INFRA`, retry, refund, and non-scientific semantics.
8. **Determinism / bounded reproducibility.** Identical registered execution should reproduce within documented tolerances.
9. **No placeholder LIVE.** Fixture/mock/stub values never become LIVE evidence, production ranking, frontier entitlement, or settlement.
10. **Historical evidence is versioned.** No silent rescore/reinterpretation under newer scientific contracts.
11. **Forbidden score inputs.** Prior similarity, estimate/light/mock metrics, exam fee, customer payment, or sponsor size never enter official score unless a future registered scientific contract explicitly gives a metric a legitimate scientific role.
12. **The free loop cannot become the official exam.** Practice signal stays intentionally incomplete.
13. **A8 fixture execution is not production authority.** Fixture/stub execution cannot create frontier, treasury, product, or production claims.
14. **A5 scoring does not own frontier/treasury policy.**
15. **A7 submission lifecycle does not own frontier/treasury state.**

16. **Complete research environments.** Every Challenge's mining environment provides research, hypothesize, train, generate and evaluate (OWNER-RESEARCH-ENVIRONMENT-01), plus compute, model and agent connected in setup on the miner's own machine and accounts (OWNER-MINER-ENVIRONMENT-01); gaps are declared, never silent.

See `.agent/INVARIANTS.md` for the always-on expanded list.

---

# 7. Integrated scientific invariants

Future work must preserve these even when current types do not yet implement them fully.

## 7.1 Exam qualification first

> **The exam must be qualified before it may qualify candidates.**

Generator determinism, successful execution, or a non-null config is not scientific adequacy.

## 7.2 Population semantics

The scientific task owns the population. `P(x)`, proposal/sampling `Q(x)`, and evidence/score weighting `w(x)` are separate where applicable.

Seed separation does not prove semantic decontamination.

## 7.3 Admissibility before ranking

> **Mandatory scientific failure cannot be compensated by soft performance.**

## 7.4 Measurement authority

Measurement definition, qualification, applicability, and score use are separate. A governing equation or symbolic representation does not certify a measurement implementation.

## 7.5 Reference failure separation

Reference/truth/generator failure must not be collapsed into candidate failure.

## 7.6 Challenge-bound score

A scalar Challenge score is not automatically comparable across Challenges.

## 7.7 Frontier promotion is separate

Leaderboard/rank may nominate. A future `FrontierAdvanceEvent` requires its own registered scientific evidence/policy.

> **A new leader is an evidence state, not a floating-point inequality.**

## 7.8 Science and settlement are separate

Treasury/network transport settles entitlement; it does not create scientific merit.

## 7.9 Construction and official evaluation are separate security domains

Future `ModelConstructionStrategy`, `ConstructionProgram`, reconstruction workers, or arbitrary participant code do not gain evaluator authority.

> **Carbon can widen what participants are allowed to discover without changing who controls the grade.**

## 7.10 Agent autonomy expands hypotheses, not authority

Landscape, priors, construction agents, or Physics Intelligence may propose. Registered contracts and independent experiments decide.

---

# 8. Report actual maturity

Use current code, tests and the authorized task to establish status. Old Wave-A
snapshots, future plans and inherited OPEN/EMPTY queues do not select work.
Distinguish SPECIFIED, IMPLEMENTED and TESTED from SCIENTIFICALLY_QUALIFIED,
SECURITY_QUALIFIED, NETWORK_QUALIFIED and PRODUCTION_QUALIFIED.

Library presence, direct model execution, normal Launchpad reconstruction,
ScoreLab custody, independent validator evaluation and qualification are
separate evidence states. Do not substitute component results for the normal
user flow. Preserve old failures, missing native state and versioned evidence.

---

# 9. Build one coherent task

Use coherent tasks and isolated branches/worktrees, with one integration owner
for disjoint team slices. Bundle helper tasks, fixes, tests, documentation and
formatting into the meaningful change's PR; do not create a PR per touch, run or
receipt. PR scope follows changed behavior and risk under the delivery policy.
Keep a short working contract and plan in the existing task when complexity
warrants it; no separate contract commit, design PR or checkpoint is required
for each slice.

Finish the authorized user flow, including replacement of obsolete callers.
A parser, schema, screen, direct probe or source-only adapter is not a completed
reconstruction workflow. Remove redundant machinery as part of the replacement;
do not preserve it as a hidden admission prerequisite.

Record material decisions once, notify affected authorized receivers and keep
working. Require an acknowledgement only when a dependent action actually needs
that receiver's artifact or custody, not for unrelated work. Routine choices
inside the contract do not need new owner phrases, reviews or receipts.
Delivery requirements live in `.agent/DELIVERY_PROTOCOL.md` only.

---

# 10. Validate the behavior changed

Run focused tests during implementation and the existing scope-required
canonical/CI checks before delivery. Use `scripts/dev/classify_changes.py` and
the maintained CI manifests; do not invent a second test quota or copy an old
suite into every ticket. Unknown changes retain the classifier's fail-closed
scope. Never weaken scientific, leakage, isolation or correctness assertions.

Use `./scripts/dev/canonical.sh` when available. Native output is diagnostic,
not canonical acceptance. Diagnose an unavailable runner before retrying; pinned
CI may supply acceptance. Trusted development dependency bootstrap and hostile
offline miner execution are distinct boundaries; do not apply one to the other.

Report what ran, what passed, what failed or was skipped, and the limits of the
result. Retest when a change, failure or unresolved risk warrants it; do not
repeat green work for reassurance. Relevant end-to-end checks must exercise the
actual submitted procedure, retained native state and common scoring semantics.
All material test models retain native state, original inputs/targets/predictions
and public source/environment/data/recipe/seed lineage in the existing ScoreLab
bank. A digest is not weights. Inert schema fixtures are not model campaigns.

---

# 11. Keep fixtures separate from authority

Synthetic, stubbed or incomplete backends may exercise lifecycle, schemas,
persistence, APIs, deterministic execution and disclosure. They cannot create
LIVE science, production ranking, frontier/treasury obligations, qualification
or claims of secure arbitrary-code execution. Authority must come from actual
provenance and policy, not a caller-supplied `emission_capable` flag.

---

# 12. Migrate interfaces explicitly

Treat MCP/HTTP fields, identities, persisted schemas, statuses, scores and
miner/validator behavior as contracts. An authorized replacement updates its
callers, tests and documentation together and versions material semantic changes
prospectively. Keep only the historical readers actually needed. Do not silently
rescore old evidence or preserve obsolete permission layers under new labels.

---

# 13. Security-sensitive work

High-risk areas include:

- validator/reconstruction execution;
- container/sandbox isolation;
- miner-supplied input/code;
- authentication/hotkeys;
- fee/payment logic;
- Bittensor integration;
- treasury/settlement;
- secrets;
- hidden evaluation persistence;
- Challenge activation;
- official evaluation orchestration;
- private/customer-hosted truth;
- customer confidential data.

Tests do not constitute a production security audit. Surface such work for dedicated review.

---

# 14. Bittensor, treasury, and economics

Agents may implement/test network integration only where specified.

Agents must not autonomously:

- deploy production mainnet infrastructure;
- activate real economic settlement;
- alter live economic parameters;
- infer missing treasury policy;
- create or change a revenue-to-Alpha mechanism without an owner decision (Carbon intends to use a share of revenue to support Alpha: OWNER-LAUNCH-STRATEGY-01);
- perform irreversible economic actions.

Current/legacy score-to-weight transport must not be mistaken for the long-term constitutional settlement design.

Target future separation:

```text
ScoreResult
→ contender nomination
→ frontier promotion
→ FrontierAdvanceEvent
→ SettlementObligation
→ treasury settlement
```

Implement only in the authorized future wave.

---

# 15. Business and commercial boundary

Business authority lives under `Business/`.

Agents may implement commercial systems when authorized, but business terms never alter scientific truth.

Hard rules:

- customer payment != score;
- commercial acceptance != scientific qualification;
- sponsor reward != scientific merit;
- revenue supports Alpha only through an explicit, owner-approved mechanism, and never through scoring;
- customer/private evidence reuse only where rights permit;
- architecture-specified products are not commercial traction.

---

# 16. Publications and claim discipline

Papers, README, decks, websites, and investor materials are explanatory layers.

Never convert:

```text
DESIGN → IMPLEMENTED
IMPLEMENTED → SCIENTIFICALLY QUALIFIED
TESTED → PRODUCTION SECURE
BUSINESS DESIGN → PAID TRACTION
NETWORK DESIGN → PROVEN NETWORK ADVANTAGE
```

without evidence.

---

# 17. Diagnose and escalate the actual blocker

Stop affected execution for a real security/approval rejection, unavailable
required credential/infrastructure, an invariant violation, or a reserved
unresolved decision. Do not retry a rejected action through another actor,
destination or route. Continue unaffected authorized work.

After two materially different failures with the same cause, diagnose and repair
that cause before another attempt. Do not loop on stale capacity or guessed APIs.
A concrete engineering defect is a repair task, not automatically a new owner
choice. A current explicitly authorized migration is not blocked solely because
an older ticket called it future work.

A blocker report names the action, evidence, cause, rule source and current
applicability, next repair or smallest reserved decision. Reuse an existing
pending question; silence is not approval. A wait must name a still-satisfiable
condition. Never turn an unsupported observation into a pass or scientific fail.

---

# 18. Git and delivery hygiene

Keep diffs coherent and reversible. Do not rewrite unrelated history, commit
secrets, silently change contracts, introduce unnecessary dependencies, or make
empty/evidence-only commits to retrigger validation. Preserve other worktrees
and uncommitted changes.

Use the designated integration/merge owner and current
`.agent/DELIVERY_PROTOCOL.md`; do not reconstruct delivery rules from old ticket
boilerplate. Actual expected-head, required-check, publication and current human
conditions remain binding. Ryan's 17 October delivery amendment supersedes the
earlier AGENTS engineering approval ceremonies: use regular PR testing
and proportionate risk review, without extra human/GPT receipts or Root
reapproval. Actual enforced checks and reserved human decisions remain binding.
This document changes no live ruleset or protected branch setting.

---

# 19. Completion report

Give one concise account of changed behavior and removed machinery, what was
reused, the checks and their actual results, earned maturity, limitations and
remaining owner decisions. Link existing artifacts when useful. No mandatory
section-per-check, duplicate report, copied SHA inventory or new tracker.
Do not describe unmerged or incomplete work as delivered.

---

# 20. Goal-first engineering

At each decision ask internally: "Is this how we should be doing this? Is there a
better way to accomplish this for Carbon's goals?" Prefer the smallest complete
useful path. This is judgment, not another checklist, permission gate or required
receipt. Remove rules that protect no current boundary within the authorized
scope; preserve the boundaries that do.

> **The search surface may widen. The authority boundary may not.**
