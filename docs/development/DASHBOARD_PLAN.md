# Carbon Dashboard: plan

**Ticket:** [DASHBOARD-01](../../.agent/tickets/DASHBOARD-01_leaders_and_showcase.md).
**Authority:** [OWNER-DASHBOARD-01](../../.agent/decisions/2026-10-08-OWNER-DASHBOARD-01.md),
the owner, 2026-10-08.
**Status:** PLAN. No code ships in this PR.
**Maturity ceiling:** DEVELOPMENT / TESTNET display software. Nothing here
qualifies a model, a Challenge, an exam or a design. Nothing here creates
score, rank, frontier, weight, settlement or product authority.

The owner asked for two things:

1. **Leaders and their scores.** A public dashboard per Challenge and device
   class, showing standing, the incumbent against challengers, each miner's
   rounded per-section scores, and trends.
2. **A live design showcase.** The current leader's model drives Carbon's
   registered design optimizer on a public design task, and is shown against
   the reference solver's truth, including where the model is wrong.

The dashboard is a **reader**. The validator decides what a score is, what is
released and who the incumbent is. The dashboard checks what it is given,
drops anything not on its allow-list, refuses anything that breaks a
disclosure rule, and draws the rest.

## 1. Sources and what each may contribute

| Source | Owner | What the dashboard takes | State |
|---|---|---|---|
| Score feed `carbon.validator.score-feed.v1`, `GET /carbon/v1/feed/<challenge>` | Carbon Validator, [VALIDATOR-29](https://github.com/carbonphysicsai/Carbon/pull/854) | leaders, standing, incumbent, challengers, rounded sections, history, released per-case detail, labels | draft schema; no code yet |
| Public design contract, e.g. EV4 `carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json` | committed, `data_scope: PUBLIC_SYNTHETIC` | decision, grid, conditions, objective, limits, minimum useful improvement | on main |
| Public reference solves, e.g. `docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz` (pinned by `references.sha256`) | committed evidence | reference truth for every candidate in the showcase bank | on main |
| `carbon.design_search` (`tasks`, `optimizer`, `controls`) | Carbon | the registered optimizer, `judge`, synthetic control predictors | on main |
| Leader predictions on the public showcase task | **dependency, see §5.4** | a committed prediction panel for the showcase task | not built |

The dashboard reads nothing else. It never reads the validator's state
directory, the pool store, bank draws, quiz or seed journals, private readers
(`tuning._read_private` and the like), or any hidden or live material.

## 2. Disclosure rules the dashboard enforces

These are checks the dashboard runs again on every document, after the
validator's own. They do not replace the validator's checks.

1. **Pinned schema.** Only `carbon.validator.score-feed.v1` is accepted.
   Anything else is refused whole, never partly drawn.
2. **Signature against a pinned key.** The feed's Ed25519 signature is checked
   against the validator feed key pinned in the dashboard's configuration. The
   `feed_key` inside the document is informational. A document signed by any
   other key is refused.
3. **Allow-list projection.** Only the fields named in the v1 schema are
   carried forward. Unknown fields are dropped, never shown.
4. **No live values.** A document carrying `live` is refused until VALIDATOR-29
   item 1 has its owner record and the dashboard pins that record.
5. **Rounded only.** Every section value must be a whole multiple of
   `values.precision` for its section. A value that is not refuses the
   document, since it may be a raw value.
6. **Case level only when released.** Every key of `detail` must be a
   fingerprint in `released_windows`. One that is not refuses the document.
   Per-case fields are allow-listed (`case_id` and the declared per-case
   values); any other per-case field is dropped.
7. **One device class.** A feed is one Challenge and one device class. Feeds
   with different classes are never drawn in one table or ranked together.
   CPU rehearsal feeds carry their own label.
8. **Labels on every view.** `DEVELOPMENT` is always shown, and `TESTNET` when
   the feed says so, on every page and every exported image.
9. **Identity.** A miner is shown by its public hotkey (on-chain, public) and
   its UID when the feed gives one. Nothing else about the hotkey's owner is
   shown: no IP, endpoint, coldkey, wallet, compute provider or contact.
10. **No recipes.** Model architectures, training recipes and construction
    programs are never shown. A future opt-in needs a feed field the validator
    adds and an owner record. Until then the miner page reads "Recipe not
    disclosed".
11. **Claim discipline.** No page says or implies "qualified", "validated",
    "matches reality", "production", "certified" or "accurate" about a model,
    a Challenge or a design. A copy check in the tests rejects those words in
    the shipped page text, outside the fixed disclaimer.

A refused document is shown as "Feed unavailable: <reason code>", and the last
accepted version stays visible with its block and age. A refusal is never
replaced by fixture data.

## 3. Leaderboard and miner pages (slice 1)

One page per Challenge and device class, built only from the feed:

- **Header:** Challenge id, version and rule (with digest), device class,
  labels, feed version, and "released through block N". VALIDATOR-29 releases
  a score only when every window it used is retired and published, so the
  board is **lagged**. The page says so in plain words. The owner's "live" is
  VALIDATOR-29 item 1, which is reserved; the board switches to live only when
  that ships.
- **Incumbent and challengers:** the incumbent and the block it holds from,
  with its rounded sections, and each challenger's state (`NOMINATED`,
  `FINAL_PENDING`, `FINAL_LOST`, `FINAL_WON`) as the validator states it. The
  dashboard never works out an incumbent or a winner from score order: a new
  leader is an evidence state (invariant 22).
- **Standing:** the validator's rank, with the Ladder best per section and the
  block it was set. Section names, units and the "higher or lower is better"
  sense come from the feed; nothing is assumed per Challenge.
- **Sections:** `accuracy`, `design_q`, `gates` (pass/fail per gate) and
  `near_limit`, drawn as rounded numbers and small bars. A gate failure is
  shown first and is never offset by another section (invariant 18).
- **Trends:** each hotkey's `history` as a step line by block. A
  leaderboard-wide chart shows the Ladder best per section over time.
- **Miner page** (`/c/<challenge>/<device>/m/<hotkey>`): the miner's submissions
  with state, sections and windows used, its trend, its standing history, and
  a per-case table **only** for released windows (`detail`).
- **Feed health:** the feed version, signature status, block and age, and
  `excluded.canary_hotkeys` as a count.

Until VALIDATOR-29's feed ships, the pages run on **synthetic fixture feeds**.
They are built and signed by a test key in `tests/`, carry the label
`FIXTURE`, and use made-up hotkeys that cannot be valid SS58 addresses. A
fixture can never be loaded by the production configuration; the loader takes
the pinned production key and the fixture key from different settings.

## 4. The design showcase (slice 2)

### 4.1 What it shows

One public design decision at a time, e.g. EV4's two-stage fast-charge
protocol on a 7 × 5 (c1, c2) grid for one operating condition. The animation
replays, step by step:

1. **The search path.** Each candidate the registered optimizer asks the model
   about, in the order asked, drawn on the (c1, c2) grid.
2. **Prediction against truth at each step.** The model's predicted objective
   (time to CV onset, s) and its predicted safety margins (e.g. plating margin,
   V) beside the reference solver's values for the same candidate. The error
   is drawn, not hidden.
3. **The running pick.** What the optimizer would pick from the model's
   predictions so far.
4. **The final pick against the true best-in-bank.** The committed pick, the
   reference's best feasible candidate, and the full truth surface revealed at
   the end (infeasible cells hatched).
5. **Regret in buyer units.** Regret in the objective's unit (s), and in
   multiples of the contract's `minimum_useful_improvement_s` (120 s for EV4),
   which is the contract's own buyer-facing unit. A dollar figure is **not**
   shown: the only dollar assumptions are prose in the value-cost notes, not a
   registered conversion (HUMAN_INPUT).
6. **Safety misses, highlighted.** A step where the model predicts a limit is
   met but the reference says it is not is flagged in the accent colour. A
   reference-infeasible final pick is shown as a **false-feasible**: counted,
   never priced as regret, exactly as `tasks.judge` classifies it. A
   reference-UNRESOLVED value is shown as unresolved, never as pass or fail.

The replay can be paused, stepped, scrubbed and sped up, and has a plain table
of every step for keyboard and screen-reader users.

### 4.2 How a replay is made (server-side, precomputed)

`carbon/dashboard/showcase.py` builds a replay document
`carbon.dashboard.showcase-replay.v1` from public inputs only:

1. **Register the task.** Build a runnable `carbon.design-task.v2` task from
   the public contract: the grid as the action grammar, the scenario's
   conditions, the objective and limits copied verbatim. A value the contract
   does not state is not filled in: the build refuses.
2. **Run the optimizer unchanged.** Call `design_search.tasks.run_optimizer`
   with the model's predictor wrapped in a recorder. The recorder notes each
   query (candidate, condition, predicted quantities) in order and passes the
   value through untouched. The optimizer, its starts, seed and budget are
   not changed or reimplemented (WRAP, not REPLACE). The commitment is made
   before any reference is read, as in the real path.
3. **Judge.** Call `tasks.judge` with the reference values, then attach the
   reference values for each visited candidate and for the whole bank.
4. **Seal.** The document records the contract digest, the task digest, the
   reference file's sha256 (checked against the committed pin), the predictor
   identity, and the commitment digest. A replay that fails any check is not
   written.

The builder refuses any input path outside an allow-list of committed public
files, and checks each against its committed digest. A test asserts the
module imports nothing from the validator's state, pool store, bank draws or
private readers.

### 4.3 Which model drives it

- **Now (fixtures):** Carbon's synthetic **controls** (`design_search.controls`:
  edge optimist, over-cautious, localized sign error), applied to the public
  references. Each is labelled "CONTROL MODEL (synthetic, not a miner)". They
  show the honest failure modes the page is built to expose.
- **When the leader exists:** the incumbent named by the feed, its model rebuilt
  by Carbon (Carbon rebuilds every model; the miner's code never runs on the
  dashboard), queried on the public showcase task only. The dashboard receives
  a committed prediction panel and replays it. Who produces that panel is a
  dependency (§5.4).

The showcase names the model by hotkey and shows predictions only, never its
architecture or recipe.

### 4.4 Streaming or replay

A replay is a static JSON file. The page fetches it and animates it on the
client. "Live" means a new replay appears whenever the incumbent changes and
its panel is produced. There is no server-side model execution behind the
page.

## 5. Delivery

### 5.1 Code layout

- `carbon/dashboard/`: Python. `feed.py` (verify, project, refuse),
  `showcase.py` (task, recorder, judge, replay), `build.py` (writes the static
  site and data from fixtures or a fetched feed), `__main__.py` (`build`, and
  `serve` for a local preview). Added to `.agent/CODE_AUTHORITY.toml`.
- `carbon/dashboard/web/`: the static app (`index.html`, `dashboard.js`,
  `showcase.js`, `style.css`). It uses the Launchpad's tokens and type, adapted
  from `scripts/dev/miner_launchpad/style.css`. Montreal (`neue-0.otf`,
  `neue-1.otf`) is copied from the verified website asset set, with digests
  checked against `website/ask-carbon/production-baseline.manifest.json`. No
  CDN, no third-party script, no analytics, no cookies.
- Pure view-model functions in the JS are tested with a Node check, following
  the `tests/cpu/research_charts_check.cjs` pattern. Python tests live in
  `tests/cpu/test_dashboard_*.py`.

### 5.2 Slices (one PR each, to PR Head)

| PR | Scope | Depends on |
|---|---|---|
| D0 | This plan, the ticket, the owner record | — |
| D1 | Feed reader (`feed.py`) with every §2 check and its refusal tests; signed synthetic fixture feeds; leaderboard, miner and trend pages; local `serve` | the VALIDATOR-29 draft schema |
| D2 | Showcase builder and replay player on EV4's public references with the synthetic controls; safety-miss and false-feasible display; regret in s and in minimum-useful-improvement units | D1 shell |
| D3 | Wire the real feed once VALIDATOR-29 slice 3 serves it (pin its feed key); replay the incumbent's panel once §5.4 exists; deployment package for the owner's chosen host (no deploy) | VALIDATOR-29 slices 2–3, §5.4, §6 decision |

### 5.3 Acceptance per slice

- Focused Python tests: every refusal in §2 (unknown schema, wrong key,
  `live` present, unrounded value, `detail` for an unreleased window, mixed
  device class), the allow-list projection, and the showcase's
  commit-before-reference order, judge agreement with `tasks.judge`, and
  input allow-list.
- A Node check of the view-models (no markup from data; labels on every view).
- A browser check of the built pages in the in-app preview, at desktop and
  phone width, with a screenshot in the PR.
- The repository's quality gate and one canonical focused run per PR.

### 5.4 Dependencies outside the dashboard

1. **VALIDATOR-29** (Carbon Validator): the feed. Schema notes sent with this
   plan:
   - pin the feed key out of band; the in-document key is not trust;
   - state the canonical bytes that are signed (e.g. sorted keys, `,`/`:`
     separators, UTF-8, `signature` removed), as `tasks.digest` does;
   - give each section its display name, unit and sense (Rule v2 ranks lower
     as better, A-Q higher as better);
   - list the allowed per-case fields in `detail`;
   - add `generated_at` (UTC) beside the block numbers.
2. **The leader's showcase panel.** Someone has to run the incumbent's rebuilt
   model on the public showcase task and commit the predictions. The validator
   already rebuilds models. Proposed: a small validator or producer job, public
   inputs only, writing a signed prediction panel. That is new scope for its
   owner, and the Test Lead routes it.
3. **The values.** Precision and display threshold are registered by the Test
   Lead for VALIDATOR-29. The dashboard adds none of its own.

## 6. Hosting and deployment (owner decision; proposed, no spend)

**Recommended: Cloudflare Workers with static assets, on Carbon's existing
Cloudflare account.**
- **Shape.** A new Worker `carbon-dashboard` serves the static app and the
  replay files. For the feed, it fetches the validator's feed server-side,
  checks the signature against the pinned key, caches it briefly at the edge,
  and serves it same-origin.
  - The browser then never talks to the validator door directly.
  - The validator door needs no CORS change.
  - No deploy credential sits on the validator host.
- **Route.** `dashboard.carbonphysics.ai`, or `carbonphysics.ai/dashboard`. The
  owner picks.
- **Cost.** Expected USD 0 on the Workers Free plan. Static asset requests are
  not billed, and the feed proxy uses Worker requests, which have a daily free
  allowance. Check the current published limits before deploying. Going past
  the allowance would need the paid plan, which is a spend decision for the
  owner. Nothing in this plan spends.
- **Custody.**
  - The Cloudflare account and its deploy token stay with the owner, as they
    do for `carbonwebsite` today.
  - Deploys are by hand with `wrangler deploy`, as in
    `website/ask-carbon/DEPLOY_PACKAGE_2026_10_01.md`.
  - The repository holds no token.
- **Alternatives.**
  - **GitHub Pages**: static only and free, under GitHub org custody. The
    browser would have to fetch the feed cross-origin, and verify it in the
    browser, so the validator door needs CORS.
  - **Serving from the validator's public door**: no new host, but it adds a
    public web UI to the hardened listener. Not recommended.

Until the owner decides, the dashboard runs locally (`python -m
carbon.dashboard serve`) and in PR previews. Nothing is published.

## 7. Open owner and lead decisions (fail closed until made)

| Decision | Owner | Until decided |
|---|---|---|
| Hosting, route and deploy (§6) | owner | local only |
| Live per-section scores on unretired windows (VALIDATOR-29 item 1) | owner, confirmed directly | lagged board, released windows only |
| Feed precision and display threshold | Test Lead (VALIDATOR-29) | feed refuses to publish, so the board shows "Feed unavailable" |
| Recipe opt-in (field and record) | owner | "Recipe not disclosed" |
| Who produces the leader's showcase panel (§5.4) | Test Lead routes | controls only, labelled synthetic |
| Showcase task choice beyond EV4 (other Challenges' public contracts) | Test Lead | EV4 only |
| A dollar conversion for regret | owner (HUMAN_INPUT) | s and minimum-useful-improvement units only |
