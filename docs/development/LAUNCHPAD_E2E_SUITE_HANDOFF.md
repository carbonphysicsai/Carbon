# Launchpad end-to-end testing suite: handoff and execution guidance

**Status.** Handoff and plan, not a decision record. The owner decision it
serves is **`.agent/decisions/2026-10-15-OWNER-LAUNCHPAD-E2E-SUITE-01.md`**,
recorded by Platform2 on its T-07 branch (`codex/launchpad-t07-base-first`,
commit `018818453`, record sha256 `9f431e87…`), which carries the owner's
D1–D6 and R1–R3 answers verbatim and Platform2's immediate dispositions. Where
this document and that record differ, the record governs. §3A below repeats
the same answers for reading convenience only.

**Authority for the handoff itself.** The owner, 2026-10-15, in his own Claude
Code session, asked for this handoff and then for the §3 answers ("Do the
same for the Launchpad answers"), and asked for it to be recorded. Nothing in
it creates a grant figure, scientific threshold, security acceptance, LIVE,
reward, mainnet or production authority.

**From:** the owner (Ryan), 2026-10-15. **To:** Launchpad (Platform lanes),
Test Lead, Carbon Validator, Graphite Testing Manager, PR Head / Root.
**Basis:** `origin/main` at `bc465b1d` (#1368). DEVELOPMENT only.
**Standing rules this keeps:** OWNER-MINER-COMPUTE-LINK-ONLY-01 (Carbon rents
no miner compute), OWNER-MINER-SETUP-AGENT-FIRST-01 (keys by file path; signer
start and signing stay human), OWNER-COMMITMENT-POSTER-01 D1–D10,
OWNER-LAUNCHPAD-PROD-02, OWNER-GRAPHITE-05 (grants proposed, then approved),
OWNER-LADDER-THROUGH-LAUNCHPAD-01, the §3.7 release rule ("nothing untested is
offered as tested"), and the evidence conventions in
`docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md` §2.

**The one-sentence goal.** Every capability the Launchpad offers on either
door is covered by an automated test where automation is possible, by a
recorded real-infrastructure cell where it is not, and the release check can
compute, not eyeball, whether the Launchpad may ship.

---

## 0. Where it actually stands

What exists is good and more than most people think. What's missing is the
bookkeeping that turns runs into a verdict.

**Exists**

| Layer | What | Where | In CI? |
|---|---|---|---|
| L0 unit / contract | 47 Launchpad and Control Center test files (doors, gates, refusals, commitment, multi-intake, ladder view, supervisor, signer honesty, offline coverage…) | `tests/cpu/test_launchpad_*`, `test_control_center_*`, `test_miner_launchpad_*` | Yes, canonical shards (`scripts/dev/ci.sh`) |
| L1 page without a browser | The real `index.html` + `app.js`, `research_view.js`, `research_tools.js`, `library_view.js` driven on a fake DOM and fake clock against a scripted controller | `tests/cpu/control_center_dom.cjs`, `test_control_center_live_page.py` | Yes |
| L2 real browser | Chromium over CDP against the real HTTP controller; no research or provider execution | `scripts/dev/miner_launchpad/browser_smoke.py` | **Confirmed NOT in normal CI** (Platform2 disposition, source `27f74451`): runs only on shard 4 with `CARBON_LAUNCHPAD_SMOKE=1`, which the workflow does not set. Fix in flight: `codex/launchpad-t01-ci-coverage` (LAUNCHPAD-T01-CI-COVERAGE-01), Platform3 |
| L3 service journey | Eight-stage miner journey through both doors: real MCP SDK client + stdio servers, real HTTP door, real campaign host/gates/supervision/ledger, battery research service, practice in a subprocess, intake + worker + validator daemon on loopback. Fixtures only for provider transport, chain, signer, campaign prep | `tests/service/test_launchpad_production_journey.py` (+16 other service files) | **Confirmed NOT in `ci.sh`'s service lane** (same disposition). Same fix: journey on shard 3 under LAUNCHPAD-T01-CI-COVERAGE-01 |
| L4 real acceptance | The matrix: 14 flows × 9 compute × 7 inference × 5 agents as a covering design, fresh-machine run, submit-to-verdict, traffic switch, levels L1–L4 | `LAUNCHPAD_ACCEPTANCE_PLAN.md` §3–§6, §3.8 | Manual, owner-in-the-loop by design |
| L5 Graphite as first heavy user | Graphite's miner edition drives the Launchpad through MCP; every gap it hits goes to `FINDINGS.md` | `carbon/agent_campaign/graphite/miner/` | Campaign runs, not CI |

**Real runs that have happened (all on `carbon-fresh`, the owner's clean WSL2 distro)**

- F01 install: run 1 FAIL (LA-F1), run 2 PASS at `f1dd652debdf`, 2026-10-07.
- F03 registration: minerB registered (UID 4); LA-F3 found and fixed.
- A Graphite smoke campaign on 2026-10-08 (`14d573bb…`): found LA-F8, LA-F9.
- Two installs on one checkout (minerA/minerB): found LA-F15–F16.
- 16 findings recorded, LA-F1 to LA-F19. **13 fixed. 3 open:** LA-F10
  (practice on released worker images needs a release cut), LA-F11
  (own-agent campaigns refuse practice for a key they never use; fix pending),
  LA-F17 (local bootstrap signs for the subnet publisher; proposal only,
  security-adjacent).
- Critical-path code for A1–A4 landed: LAUNCHPAD-ACCEPT-02 (commit op),
  -03 (receiver pinned and checked), -04 (tunnel target + readback), and
  LP-04 (multi-intake) on top.

**Missing — and this is why it feels unfinished**

1. **There is no `cells/` directory.** `docs/development/evidence/launchpad-acceptance-2026-10-07/`
   holds `FINDINGS.md` only. Every run above produced findings but **no
   `carbon.launchpad.acceptance-cell.v1` record**, so the completion predicate
   (§3.6) and the release check (§3.7) have nothing to read. The matrix is
   effectively at 0/14 flows recorded even though F01 and F03 passed.
2. **No real submit → verdict through the Launchpad has been recorded** (A5).
   `published_endpoints.json` is empty by design (AX42 stays private); the
   tunnel target path exists in code; nobody has run it and written F11/F12.
3. **The release check (§3.7) is not built.** It's a slice of ACCEPT-01 and
   it's the thing that makes "untested" a computed label rather than a promise.
4. **The plan predates three capabilities** that now need cells and tests:
   multi-intake submit (LP-04), Torch GPU practice on the miner carrier
   (PLT-30), and the explicit NVIDIA device-request driver (LP-05).
5. **Levels L1–L4 cells are BLOCKED** on VALIDATOR-25 publishing
   `served_contracts` and the `battery-dev-ladder` deployment on valV2.
6. **Agent snippets:** Claude Code / Codex / Hermes `mcp_connect` snippets
   are still UNVERIFIED unless A3/A4/A5 ran; nothing records that they did.
7. **Compute and inference cells C2–C9, I1–I7:** grant approved
   (OWNER-LAUNCHPAD-ACCEPTANCE-GRANT-01, USD 13.55 full), none recorded.

---

## 1. The capability inventory the suite must cover

Derived from `capabilities.py` (`carbon.control-center.capabilities.v1`), the
shared `OPERATIONS` table, the setup operations and the HTTP routes. This is
the checklist; every row ends up with a test or a cell, or a reason.

**Install and lifecycle.** `install_miner.sh` (plain, `--gpu`, `--service`,
`--update`, `--ref`, second install with `CARBON_STATE_DIR` + `--port`),
linger / reboot recovery (MINER-SURVIVE-REBOOT-01), image tagging by id
(LA-F2), docker-group-from-the-manager check (LA-F6), refuse a dirty checkout,
refuse a running update.

**Setup (both doors).** `status`, `begin`, registration prepare (btcli form
that ran, LA-F3), signer probe, inference `quote` → `inference` check with
`consent.max_cost_nano`, compute check (this-machine CPU / GPU; remote cards
runpod, lium, targon, vast, lambda, own-server over ssh-docker /
ssh-container; send-worker; prepare), `review` (profile v2, `intakes`,
pinned `receivers`, `intake_targets` for multi-intake, published endpoint
import), `after_install`, Hermes profile setup, `mcp_connect` snippets, the
`reboot_recovery_off` warning.

**Capabilities contract.** `/api/v1/capabilities` built from runtime truth;
every unavailable choice carries `reason` + `next_action` + PLAIN sentence;
`options` versioned and registry-driven; nothing hard-coded.

**Shared operations (27, one table, both doors).** `launch options observe
campaign_view note messages toolbox ladder budget_status run_output practice
halt resume freeze_candidate submit commit library_search library_card
library_list plan_list plan_get library_pin library_unpin library_ban
library_unban library_import plan_edit`. Gates in order: request, profile,
replay, registration + signer probe, campaign. Owner-lock semantics
(`takes_owner_lock`). Idempotency on launch (replay gate + digest conflict),
and **confirmed closed for practice / freeze / submit** (Platform2 disposition
of R3: keyed operations under the replay gate, `launchpad_operation_keys`
persisted in SQLite by principal and request key, request-digest conflict
check, replay without redispatch; `tests/cpu/test_miner_operation_idempotency.py`).
A caller that omits or changes the key gets no idempotency promise.

**Agents.** `graphite` (RESEARCH / BUILD / FULL; `research_share`, `hunt`,
`plan`, ceilings predicate LA-F4, output cap decision, input-window advisory
LA-F8, public practice exemption LA-F9), `none` / own-agent over MCP
(Claude Code, Codex, Hermes), Carbon's older autonomous agent for recorded
launches only.

**Construction levels.** `construction_level` 0–4, `arm`, level proposals
from data, `construction_variant_digest` (standalone graph v3, L4-LAUNCHPAD-
STANDALONE-V3), ladder view, gate breakdown, budget status
(`NOT_SET / SET / MALFORMED / UNMEASURABLE / NO_ADAPTER / UNIT_NOT_CALIBRATED`),
`level_not_registered`, `level_not_served_by_target`,
`level4_envelope_transport_unavailable`, Level 4 parts transport.

**Compute backends.** `CPU`, `ISOLATED_CARRIER_GPU` (JAX), Torch GPU worker
on the miner carrier (PLT-30, v2-torch scope), `REMOTE_GPU`, device request
`--gpus driver=nvidia,device=<uuid>` (LP-05), cleanup (`carbon-job-*`,
`/tmp/carbon-job-*`), the watchdog/reaper.

**Submit path.** freeze → commit (plan digest = `daemon.commitment_digest`,
TTY confirm last-8, one per hotkey per tempo) → receiver check before any
signing (`intake_receiver_mismatch`, `intake_receiver_not_pinned`) → intake
(own loopback/tunnel, published, or up to 32 `intake_targets` with
per-pair journals) → 202 + submission id → status/verdict readback on both
doors (LA-F18) → sealed DEVELOPMENT outcome labelled CPU, no hidden
score/case/seed on either door.

**Recovery.** Pause on close (never stop), resume from journal, restart flags
no idle campaign, reconcile for unknown-outcome calls, typed interruption
codes (never bare `ValueError`), frozen-on-old-revision submit typed (LA-F19),
profile change that does not matter survives resume.

**Refusals.** 239 closed codes in `supervisor.py`'s catalog, ~90 distinct in
the Launchpad modules. Every one must be producible by a test, carry a
`next_step`, and be identical on both doors.

**Disclosure and security.** Session token only in `control-center.log`
(owner-only), never printed; keys only by file path, never in a log, page,
MCP result or evidence; no address, balance or profile contents in evidence;
hardened listener (#829, OWNER-DOOR-HARDENING-ACCEPT-01); every
authentication-adjacent change needs the owner's security acceptance.

**Views.** Campaign, research charts, library, ladder, budget, gate
breakdown, run output, guide, FAQ, Connections (real MCP command), Tools tab.

---

## 2. The suite, layer by layer: what to build

### T-01 — Put the existing layers in CI and know it

- Confirm which `ci.sh` lane runs `tests/service/test_launchpad_production_journey.py`
  and the other 16 service files. If none, add a lane. The journey test is
  the single most valuable automated artifact in this area and it must run
  on every `RUNTIME_FULL` candidate.
- Run `browser_smoke.py` in the canonical image (Chromium is pinned there for
  Playwright elsewhere; confirm CDP works) on every candidate that touches
  `scripts/dev/miner_launchpad/`. If it can't be made deterministic, nightly
  on main with an uploaded artifact.
- Done when: a PR that breaks the journey or the browser smoke goes red.

### T-02 — Door parity, generated from the table

- One table-driven conformance test (there is a `tests/conformance/` tree)
  that iterates `operations.describe()` and, for every operation, asserts:
  the browser route and the MCP tool exist; a malformed request yields the
  same closed code and `next_step` on both; a request refused at each gate
  (request / profile / replay / registration / campaign) yields the same
  code on both; `admits_work` matches.
- Add the same for setup operations and `onboarding`.
- Done when: adding an operation without both doors fails the test.

### T-03 — Refusal catalog coverage report

- Build `scripts/dev/launchpad_refusal_coverage.py`: enumerate every closed
  code in `supervisor.py` and the Launchpad/MCP modules; map each to the
  test(s) that produce it (grep for the literal under `tests/`); emit
  `docs/development/launchpad/REFUSAL_COVERAGE.md` with reached / unreached.
- Gate: no **new** code may land unreached. Existing unreached codes get a
  ticket each, prioritised by whether a miner can hit them from a product
  door.
- Done when: the report is in CI and the unreached count only goes down.

### T-04 — Extend the service journey to the capabilities the plan predates

Add stages to `test_launchpad_production_journey.py`, each through both doors:
9. commit → submit ordering: submit before commit refused
   `commitment_required`; second commit in the same tempo refused; the plan's
   digest equals `daemon.commitment_digest(...)`.
10. receiver check: a profile with no pinned receiver warns
    `intake_receiver_not_pinned`; a mismatched intake refuses
    `intake_receiver_mismatch` with nothing signed.
11. multi-intake (LP-04): two loopback throwaway validators as
    `intake_targets`; one refuses, the other admits; both journals present;
    no averaging or ranking of verdicts.
12. levels: `construction_level: 1..3` against a fixture ladder deployment
    whose public facts list `served_contracts`; `level_not_served_by_target`
    against one that doesn't; L4 parts transport refused
    `level4_envelope_transport_unavailable` when the tools list lacks parts.
13. Torch scope: a v2-torch recipe on a CPU-only host refuses before
    dispatch with its closed code; the JAX scope is unchanged.
14. LA-F19: a campaign frozen on an older revision gets a typed refusal at
    submit, not a traceback.
15. budget status on both doors equals `check_compute_budget`'s verdict for
    the same strategy (NOT_SET today).
- Keep the test's own rule: no paid call; provider transport is `Script`;
  state under `tmp_path`; listeners loopback.

### T-05 — The acceptance matrix, made computable

- Create `scripts/dev/launchpad_acceptance/` with:
  - `cell.py`: write/validate `carbon.launchpad.acceptance-cell.v1`
    (`cell, date, revision, machine_kind, result, refusal_code, evidence,
    within_cap, actor`). Refuses a key, address, balance or profile content
    anywhere in `evidence`.
  - `matrix.py`: the covering design from plan §3 as data (flows, compute,
    inference, agents, levels), each cell with its "pass means" predicate
    text and required evidence fields.
  - `status.py`: reads `docs/development/evidence/launchpad-acceptance-*/cells/`
    and prints the matrix with PASS / FAIL / BLOCKED / UNRUN per cell at the
    newest revision, and evaluates §3.6 line by line.
- **Backfill the runs that already happened** as cells, truthfully: F01
  (run 1 FAIL `exit 126` LA-F1; run 2 PASS at `f1dd652debdf`), F03 PASS,
  the 2026-10-08 Graphite smoke as F07 with whatever result it had and its
  findings linked. Dates and revisions from `fresh-miner-2026-10-07/README.md`.
- Add cells for the three new capabilities: F15 multi-intake submit, C10
  Torch GPU practice (this-machine-gpu), C11 device-request driver.
- Done when: `python -m scripts.dev.launchpad_acceptance status` prints the
  matrix and the §3.6 verdict, and the three findings-only runs appear in it.

### T-06 — The release check (§3.7)

- `scripts/dev/launchpad_acceptance/release_check.py`: compare what both
  doors offer (setup `choices()`, `REMOTE_GUIDES`, `INFERENCE_ORDER`, agent
  choices, `mcp_connect` snippets, construction levels, compute backends)
  against the newest PASS cells. Any option without a PASS cell at this
  revision or an earlier revision the cell names must be **hidden or labelled
  "untested"** on both doors, as a closed field the MCP door returns too.
- Default is "untested" for everything; passes flip options one cell at a
  time. A BLOCKED or FAIL cell can never show as tested.
- Wire it into the release rehearsal workflow so a release is refused until
  the labels are truthful.
- Done when: today's main runs the check and labels everything "untested"
  except F01/F03's options, and that is correct.

### T-07 — Run the critical path for real (A5) and record it

Order from plan §1, stage A. All code landed; this is runs + cells.
1. Owner opens the tunnel to valV2 (`ssh -N -L 18467:127.0.0.1:8467 …`),
   names it at Review as own intake with the validator's receiver.
2. Agent (this session or the Graphite executor) drives: F05 review → F07
   one-epoch Graphite BUILD on `engy-chat`, CPU, cap ≈ USD 0.50 → F08
   practice (backend `CPU`) → F09 freeze → F10 commit (owner types last-8 on
   the signer TTY) → F11 submit (202, receiver equals pinned) → F12 observe
   to a sealed DEVELOPMENT verdict labelled CPU → F13 the seven refusal
   cells on the real chain and validator → F14 pause/resume/restart.
3. Write every cell. Link every new finding.
- Then A6: Graphite's testnet traffic moves onto the Launchpad; the Test
  Lead is told once; from then on Graphite runs are L5 evidence.
- Done when: F01–F14 are recorded on the base configuration.

### T-08 — Compute, inference, agent cells (plan §3.3–3.5)

- Tier 1 first, all zero-cost before paid: C1 (this-machine CPU), C2
  (this-machine GPU, RTX 3060), C3 (own-server ssh-docker to the main
  distro), then C4 RunPod and C5 Vast under the approved grant (T1-a USD
  1.00 worst case, T1-b USD 0.80). Owner starts/stops every machine; the
  cell records provider and machine kind, never an address.
- I1 engy-chat (F07 is its campaign), I2 chutes (one 1-epoch BUILD, cap
  USD 0.50), I3–I7 check-only or BLOCKED-by-key with the owner aware.
- A1 Graphite (F07 + a second BUILD that freezes, commits, submits), A3
  Claude Code and A4 Codex (paste the snippet **verbatim**; on FAIL the
  snippet is fixed or marked unsupported, never left UNVERIFIED), A2/A5
  Hermes.
- Done when: §3.6 lines 2–5 hold.

### T-09 — Levels L1–L4 through the Launchpad (plan §3.8)

- Blocked on the Carbon Validator: VALIDATOR-25 slice 2 publishing
  `served_contracts`, and the `battery-dev-ladder` deployment on valV2.
  Until then every level cell is BLOCKED with that reason, on both doors —
  which is the truthful label and is what T-06 will show.
- When unblocked: from `carbon-rehearsal-minerC` only, each level freeze →
  commit → submit → verdict, plus the three refusal cells per level.

### T-10 — Close the open findings

- LA-F11 own-agent key (fix pending): finish, test, cell.
- LA-F10 practice on released worker images: needs a release cut after the
  commit op — ask the owner to schedule the cut; cell waits.
- LA-F17 bootstrap signs for the subnet publisher: proposal only and
  security-adjacent → owner decision (§3-D1).

### T-11 — Keep Graphite as the heavy user

- Every Graphite campaign on the Launchpad that hits a gap writes a
  `FINDINGS.md` entry with cell, closed code, cause, fix PR. One finding →
  one ticket → one PR → the cell reruns. No finding is closed by prose.

---

## 3. Owner decisions, with recommended answers

**D1. LA-F17** — does the local bootstrap signing for the subnet publisher
stay as-is, change per the proposal, or get its own ticket with a security
review? *Recommended: own ticket, Carbon Validator reviews, owner accepts per
AGENTS.md §13. Not a launch blocker; label the path accordingly.*

**D2. Release cut for LA-F10** — schedule one worker-image release after the
commit op so practice can run on released images. *Recommended: yes, this
week; it unblocks F08 on released images and the `--update` cell F02.*

**D3. Owner hands.** Every real cell needs you: keys, signer TTY, tunnel,
starting and stopping machines. The matrix cannot progress on agent time
alone. *Recommended: two 90-minute blocks a week on `carbon-fresh`, agenda
written by the Launchpad lane the day before, cells written during the
block.*

**D4. "Untested" default at release.** Confirm T-06's rule: anything without
a PASS cell is hidden or labelled "untested" on both doors, starting from
everything. *Recommended: confirm; it is your 2026-10-07 rule.*

**D5. VALIDATOR-25 dev-ladder priority** — the Carbon Validator's
`served_contracts` + `battery-dev-ladder` on valV2 gate every level cell.
*Recommended: schedule after T-07's first verdict; levels are not needed for
the base acceptance.*

**D6. Multi-intake acceptance.** LP-04 added `intake_targets` after the plan
was written. *Recommended: add F15 (two real targets) to the base
configuration; it is the mainnet shape.*

---

## 3A. Owner answers, 2026-10-15

- **D1 — LA-F17: OWN TICKET, NOT A LAUNCH BLOCKER.** Carbon Validator reviews;
  owner accepts per AGENTS.md §13. Until accepted, the release check labels
  that path "untested" and its cell stays BLOCKED with this reason.
- **D2 — Release cut for LA-F10: YES, THIS WEEK.** One worker-image release
  after the commit op, unblocking F08 on released images and the `--update`
  cell F02.
- **D3 — Owner hands: TWO 90-MINUTE BLOCKS A WEEK, STARTING THIS WEEK**, on
  `carbon-fresh`. The Launchpad lane writes the agenda the day before. Cells
  are written during the block. The first block is T-07 end to end. If a block
  cannot produce cells because something is broken, the block is spent writing
  findings, not retrying; the finding is the output.
- **D4 — "Untested" by default: CONFIRMED.** Anything without a PASS cell at
  this revision, or an earlier revision the cell names, is hidden or labelled
  "untested" on both doors, as a closed field the MCP door returns. A BLOCKED
  or FAIL cell never shows as tested.
- **D5 — VALIDATOR-25 dev-ladder: AFTER THE FIRST REAL VERDICT, NOT BEFORE.**
  Scheduled the week after T-07 lands F12. Until then every level cell is
  BLOCKED with that reason on both doors.
- **D6 — Multi-intake in the base configuration: YES.** Add F15: two real
  receiver-paired targets, one admits, one refuses, both journals present,
  no averaging of verdicts.

**Riders.**

- **R1 — The first owner block is T-07, nothing else.** One real submit →
  verdict through the Launchpad is the cell that proves the path exists;
  everything after is coverage.
- **R2 — Backfill is mandatory before new runs.** F01 (run 1 FAIL, run 2 PASS
  at `f1dd652debdf`), F03 PASS, and the 2026-10-08 Graphite smoke as F07 are
  written as cells first, truthfully, with their findings linked.
- **R3 — The two "confirm" items are week-1 deliverables, not questions.**
  Whether the service journey and `browser_smoke.py` run in CI, and whether
  practice / freeze / submit have durable idempotency keys. Each is confirmed
  with a pointer to the lane or test, or becomes T-01 / a correctness ticket.

## 4. Execution guidance

**Validation runs through the canonical wrapper.** `./scripts/dev/canonical.sh --focused tests/cpu/test_launchpad_<x>.py`
for a slice; `./scripts/dev/canonical.sh --full` before handing off. Native
runs are diagnostics. CI at the exact PR head is the acceptance source; never
label an unrun test passed.

**Every real cell follows plan §2.** One folder per acceptance date; one JSON
per cell; `FINDINGS.md` is the defect register. Never in evidence: keys,
tokens, account ids, balances or spend totals (record `within_cap` only),
remote addresses, profile contents (record the digest), hidden material or
any per-case or hidden score. Keys reach Carbon by owner-only file path. An
agent never opens a key or password file.

**Actors.** Owner: keys, accounts, wallet, signer start, TTY confirmations,
chain transactions, starting/stopping rented machines, anything on the AX42.
Agent: drives the Launchpad through the browser or MCP and writes evidence.

**Negative paths are cells too.** Every flow has at least one refusal cell
with its exact closed code and `next_step`, on both doors.

**One finding, one ticket, one PR.** A finding's fix lands with a test that
would have caught it (LA-F1's `test_installer_script_modes.py` is the
pattern), and the cell that found it reruns at the fix's revision.

**Spend.** Model cells under the plan's per-cell caps; compute cells under
OWNER-LAUNCHPAD-ACCEPTANCE-GRANT-01. Balance is read before the first
dispatch and reported as `within_cap`, never as a number.

**Security-adjacent changes** (anything touching signing, receivers, intakes,
listeners, tokens) go to the Carbon Validator for review and to the owner for
acceptance before they count as PASS.

---

## 5. Schedule

| Week | Deliverables | Gate |
|---|---|---|
| 1 | T-01 (journey + browser smoke in CI), T-05 (cell tooling + backfill of F01/F03/F07), T-10 LA-F11 fixed, §3 answered | `status` prints the matrix with three real cells; CI red on a broken journey |
| 2 | T-07 run on `carbon-fresh` (F05–F14 recorded), T-02 parity test, T-03 coverage report, T-04 stages 9–11 | First real submit→verdict cell exists; A6 traffic switch recorded |
| 3 | T-06 release check wired, T-08 tier-1 cells C1–C5, I1–I2, A1/A3/A4, T-04 stages 12–15 | §3.6 lines 1–5 evaluated by code; options labelled truthfully |
| 4+ | T-09 levels when VALIDATOR-25 unblocks; tier-2 compute; I3–I7 | §3.6 holds or every gap is a named BLOCKED cell |

If week 2 slips it is D3 (owner hands) or the tunnel/valV2 availability —
schedule, not engineering.

---

## 6. Definition of done

1. §3.6's seven lines evaluate true by `status.py`, or every false line
   names its BLOCKED cells and their owners.
2. `release_check.py` runs in the release rehearsal and refuses a release
   whose doors offer an untested option as tested.
3. Journey test, browser smoke, parity test and refusal coverage run in CI;
   the unreached-refusal count is published and non-increasing.
4. Graphite's testnet traffic runs through the Launchpad and every finding
   it raises has a ticket.

Passing all of this is **engineering evidence only**: implemented and
tested, empirically exercised on real infrastructure. It is not scientific,
security or production qualification, and it does not make the Launchpad
production-ready for mainnet; those remain the owner's separate acceptances.

---

## 7. Identities

- Plan: `docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md`; runbook:
  `docs/development/FRESH_MINER_JOURNEY.md`; programme record:
  `docs/development/CONTROL_CENTER_PROGRAMME.md` (26 Sept audit; stale on UI rows).
- Evidence: `docs/development/evidence/launchpad-acceptance-2026-10-07/FINDINGS.md`
  (LA-F1…F19), `docs/development/evidence/fresh-miner-2026-10-07/README.md`.
- Tickets: LAUNCHPAD-ACCEPT-01…05, LAUNCHPAD-LEVELS-01, LP-04, LP-05,
  MINER-SURVIVE-REBOOT-01, GRAPHITE-MINER-S*, C-MLP-01…05.
- Decisions: LAUNCHPAD-ACCEPT-02/03/04 (2026-10-07), LAUNCHPAD-FINDINGS-F4-F6,
  F8-F9, F15-F18, LAUNCHPAD-LEVELS-01-S1…S4, OWNER-LADDER-THROUGH-LAUNCHPAD-01,
  OWNER-LAUNCHPAD-ACCEPTANCE-GRANT-01, OWNER-DOOR-HARDENING-ACCEPT-01,
  LP04-MULTI-INTAKE-MIGRATION, PLT30-SHARED-GPU-PRACTICE-01,
  L4-LAUNCHPAD-STANDALONE-V3, PLT29 offline coverage (`docs/development/launchpad/offline_coverage/`).
- Code: `scripts/dev/miner_launchpad/` (`operations.py`, `capabilities.py`,
  `runner.py`, `controller.py`, `supervisor.py`, `browser_smoke.py`,
  `published_endpoints.json`), `carbon/miner_mcp/`, `scripts/install_miner.sh`.
- Tests: `tests/cpu/test_launchpad_*`, `tests/cpu/test_control_center_*`,
  `tests/cpu/control_center_dom.cjs`, `tests/service/test_launchpad_production_journey.py`,
  `tests/conformance/`.
