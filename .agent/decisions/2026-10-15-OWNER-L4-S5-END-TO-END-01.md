## 2026-10-15 — OWNER-L4-S5-END-TO-END-01: L4 + S5, the construction contract served and tested end to end

**Authority.** The owner, 2026-10-15, in his own Claude Code session. He asked
for the three handoffs, then for the §3 answers, then said:

> Move them to decisions now

The answers were drafted in the session and adopted by that instruction; the
owner's words that led to each are quoted in its record. Every value below is
a DEVELOPMENT registration or a sequencing choice. No new grant figure, no
scientific threshold, no security acceptance, no LIVE, reward, mainnet or
production authority is created by any of the three records.

The owner's request for the answers, verbatim:

> Now I need the exact same thing with answers for the team finishing the L4 + S5 work needed to test the system end to end.


**From:** the owner (Ryan), 2026-10-15. **To:** Platform3 (construction
contract), Level 4 engineer, Carbon Validator, Graphite Testing Manager and
executor, Launchpad, Test Engineer, Test Lead, PR Head / Root.
**Basis:** `origin/main` at `bc465b1d` (#1368). DEVELOPMENT and testnet only.
**Standing authority this keeps:** OWNER-CONSTRUCTION-ANYTHING-01 (the
contract rebuilds anything in scope L0–L4; the level describes, never permits;
the rebuild is the only gate; entry on *tested*, removal when unprotectable),
OWNER-LEVEL4-GRAPH-ONLY-01, OWNER-L4-G5-COMPILE-ISOLATION-01 (dev/testnet
only; mainnet fail-closed), OWNER-L4-VALUES-01, OWNER-LEVEL4-TESTNET-RUNS-01,
OWNER-L4-STAGING-IMAGE-RELEASE-01 and its attached conditions,
OWNER-ANALYSIS-IMAGE-STANDING-ACCEPT-01 (six R8 probes), OWNER-DEV-LADDER-KIND-01,
OWNER-LADDER-THROUGH-LAUNCHPAD-01, OWNER-TESTNET-WEEKLY-BUDGET-01 (USD 150 /
rolling 7 days).

**The one-sentence goal.** One Level 4 graph, lowered by Graphite, goes
through the Launchpad to a real testnet validator that *serves* the combined
construction contract, is rebuilt by Carbon through G0–G7 in the isolated
lane, and returns a sealed DEVELOPMENT verdict — and the same submission
through the development door gives the same digest and record.

---

## 0. Where it actually stands

Almost everything is built. Nothing has run end to end. The gap is serving
(S5) plus three owner-conditioned steps that nobody can take without you.

**Built and merged (CPU/fixture tested)**

| Piece | State | Evidence |
|---|---|---|
| Level 4 gates G0–G7, Carbon-neutral; values approved (G0 bounds, G3 10 s / 512 MiB, G4 caps, G5 120 s) | MERGED | `carbon/level4/`, OWNER-L4-VALUES-01 |
| G5 compile isolation in the C-03 lane | ACCEPTED dev/testnet | OWNER-L4-G5-COMPILE-ISOLATION-01 |
| G5 8 GiB compile lane profile | MERGED | `carbon.c03.linux-x86_64-cpu.level4-g5-compile.v1` in `worker/model.py` |
| Staging contract: directory / envelope / workspace, one module both sides call | MERGED | `carbon/level4/staging.py`, `LEVEL4_STAGING_CONTRACT.md` |
| Launchpad Level 4 slot; envelope in signed parts to a target whose `tools` list parts | MERGED, fixture intake | LAUNCHPAD-LEVELS-01 S4 (#1060) |
| Graphite route R1: lower in its own sandbox → `graphite_level4_stage` → G0/G3/G4 → proposal carries the digest → pod-train | MERGED | #1098, `L4_STAGING_R1_CONTRACT.md` |
| Graph required at L4 (no graphless L4 winners) | MERGED | PLT-03 |
| graph-v3 default; graph-v4 `inert_fields` arm refuses width/depth | MERGED | PLT-18 |
| Composed L4 graph reconstruction with L1 loss, L2 spectral/pool, L3 numerics (S2) | MERGED | PLT-25 (`632a3172`) |
| Ladder + Launchpad wiring; combined `composition-v1` (`0865617e`) default for fresh launches; derived level reported, not required (S3) | MERGED | PLT-32 S3 (`b0c9c65`) |
| Promotion record schema + registered EMPTY set, fail-closed bar (S4) | MERGED | PLT-32 S4 (#1355) |
| Launchpad `construction_variant_digest` selector for standalone graph-v3 (`ad15d6a8`) | MERGED | L4-LAUNCHPAD-STANDALONE-V3 |
| Construction options page: "Available" only when a receiver-checked target serves it, else "Coming soon" with reason | MERGED | LP-04, PLT-28 |
| Dev-ladder admission (VALIDATOR-25 slice 1), `served_contracts` in intake facts, ladder config in deployment | MERGED | `deployment.ladder_for`, `intake.py:866` |
| Analysis-image release carrying the lowering tooling | ACCEPTED into testing | OWNER-L4-STAGING-IMAGE-RELEASE-01 |
| Attack oracles: seven graph oracles + three bounded software probes; six families still missing | PARTIAL | PKT-15 |
| Spend: stage C USD 71.80; constructor-6 USD 14.94; OPEN-SAFE L2–L4 pass USD 44.85 and L5 hunt USD 86.71 | APPROVED | the four grant records |

**Not done — the actual blockers, in dependency order**

1. **S5 has no go.** S4's own record ends "S5 needs go." Serving means: a
   real target lists `composition-v1` (and the L4 graph variants) in
   `served_contracts`, its required checks report healthy, a receiver is
   pinned, and the Launchpad's construction options flip from "Coming soon"
   to "Available" because of that fact. No deployment serves it today.
2. **The dev-ladder host state is unverified and L4 is closed on it.**
   OWNER-DEV-LADDER-KIND-01 opened `battery-dev-ladder` for L1–3 and
   explicitly refuses L4 (`ladder_level_4_not_open`). OWNER-LEVEL4-TESTNET-RUNS-01
   allows that refusal to be lifted via slice 4. VALIDATOR-25 **slice 3 — the
   owner's operator steps on valV2** (deployment file, service unit on a
   second loopback port, tunnel, minerC profile) — is not recorded as done,
   and what the running deployment serves is "host state, UNVERIFIED".
3. **The image conditions have not run.** The analysis image has not been
   rebuilt at current main; the R1 containment check has not passed on the
   new digest; the hostile-model lowering probe (memory / time / scratch
   flood) has not run. The release record's own "not verified" list is
   still entirely open: no live lowering in the real container, no graph
   trained on a real pod, G5 not exercised on this path.
4. **Graphite's L4 lane has never produced a graph.** Stage C lane G ran on
   2026-10-11 and was refused `REFUSED_UNREBUILDABLE` with the cause not in
   the extract; the brief fix (#1081), staging (#1098) and graph-required
   (PLT-03) all landed after. It has not been rerun.
5. **"Tested on Launchpad with every Launchpad capability"** (your words,
   OWNER-CONSTRUCTION-ANYTHING-01) has only an *offline* measurement: PLT-29's
   55 observations with every execution callback refusing. The live door
   and a served target are "host-side acceptance", unrun.
6. **Budget contention.** OPEN-SAFE's two grants reserve 88 % of the weekly
   USD 150; the ledger will refuse other launches past the cap. Sequencing
   the L4 end-to-end run against the L5 hunt is a scheduling decision, not
   an engineering one.

---

## 1. What "end to end" means here, exactly

The acceptance run is **one submission, two doors, one record**:

```
Graphite (R1)     lower spec → envelope → graphite_level4_stage → G0/G3/G4 → proposal(composition_graphs=digest)
      │
      ├─ door A: Launchpad L4 slot (minerC) → freeze → commit (TTY) → parts upload → battery-dev-ladder
      └─ door B: development door (dev_submit) → same envelope bytes
                                   │
                        served target lists composition-v1 + l4-graph-v3 in served_contracts
                                   │
                        rebuild in C-03 lane: staging.workspace → G5 (8 GiB lane, 120 s) → train → G6/G7
                                   │
                        sealed DEVELOPMENT verdict, device class CPU
```

Pass means: both doors yield the same submission digest and the same
rebuilt record; the verdict is sealed and labelled DEVELOPMENT/CPU; no hidden
score, seed or case appears on either door; the Launchpad's options page
showed the path "Available" *because* the target served it; and the refusal
cells fire typed: oversized at G0, hostile specimen at G3/G4, unstaged digest
(`level4_submission_not_staged`), unserved target
(`level4_envelope_transport_unavailable`), and width/depth under graph-v4
(`level4_field_inert`).

The same run, repeated with a **combined** recipe (graph + L1 expression +
L2 spectral + L3 numerics, the S2 "X3" case), is the construction-contract
acceptance under OWNER-CONSTRUCTION-ANYTHING-01. It is the second cell, not
a prerequisite for the first.

---

## 2. Critical path

| # | Stage | Owner | Deliverable | Done when |
|---|---|---|---|---|
| 1 | **Image** | Graphite Testing Manager + executor | Rebuild the analysis image at current main; run the six R8 hostile probes keyed to that digest; run R1 containment; run the three hostile-lowering sources (Test Engineer writes them) | `hostile_probe` record keyed to the new digest, all six PASS; R1 PASS; lowering probe PASS with typed refusals and no envelope from an unfinished run |
| 2 | **S5 go + ladder opens L4** | Owner (§3-D1, D2) → Carbon Validator | Decision records; `battery-dev-ladder` config lists `composition-v1`, `battery-l4-graph-v3` (default) and `-v4` (arm), levels 1–4, hotkeys minerC + Graphite's; `ladder_level_4_not_open` lifted per OWNER-LEVEL4-TESTNET-RUNS-01 | `deployment.ladder_for` accepts the file; intake facts show the entries in `served_contracts` and `tools` lists both L4 part tools |
| 3 | **VALIDATOR-25 slice 3, operator steps on valV2** | Owner (hands) with Carbon Validator | Deployment file, service unit on the second loopback port, tunnel, minerC Launchpad profile with pinned receiver | Launchpad Review passes on the loopback intake: network testnet / 567 / battery, receiver matches, `served_contracts` read; options page shows the L4 path "Available" |
| 4 | **Construction options truth** | Launchpad | Options page and MCP `options` both report Available/Coming soon from the served facts; health check failure names the check | A test against the stand-in daemon, then the real target; both doors agree |
| 5 | **Graphite L4 rerun** | Graphite executor under GRAPHITE-GRANT-L4-G-CONSTRUCTOR-6 (USD 14.94, one run, kimi-k3) | Lane G produces a graph through R1; the proposal's `composition_graphs` names a kept envelope; refusal (if any) carries its cause in the extract this time | A staged submission digest in the experiment root; cause-complete refused-capability rows otherwise |
| 6 | **The acceptance run** (§1) | Launchpad + Graphite executor + owner TTY | Door A and door B with the same envelope; all refusal cells | Acceptance cell `L4` written per the Launchpad plan §3.8, both doors, with digests; verdict sealed |
| 7 | **Combined-recipe run** | Platform3 + same actors | The S2 X3 composition through the same path | Cell `L4-COMBINED` written; derived level reported, not selected |
| 8 | **Live Launchpad coverage of the contract** | Launchpad | PLT-29's C0–X3 cases replayed through the live door against the served target; each row gets a live result replacing the offline prediction | `offline_coverage/MEASURED.json` gains a `live` column with cell links; no row left as prediction |
| 9 | **Attack pass at L4** | Graphite Attacker under stage C (USD 26.95) | L4 adapter + staging envelope handling; zero escapes; every finding dispositioned widen/fix in `LESSONS_REGISTER.md` | Stage C Attacker report filed; PKT-15's six missing families either probed or named as the next ticket |

Stages 1–3 are independent of each other and should run this week in
parallel. Stage 5 waits for 1. Stage 6 waits for 2, 3, 5.

---

## 3. Owner decisions — answered

**D1 — S5 serving: GO.** Serve `composition-v1` plus `battery-l4-graph-v3`
(default) and `battery-l4-graph-v4` (`inert_fields` arm) on `battery-dev-ladder`
on valV2, testnet 567 only, hotkeys minerC and Graphite's constructor
hotkey only. Weights refused; every result DEVELOPMENT-labelled; commitment
required. No public opening, no mainnet, no change to valV2's main
deployment. *Rider:* S5 is the first time the combined contract is served
anywhere; it is served on the ladder only, never on the main intake.

**D2 — Lift `ladder_level_4_not_open` on the dev ladder: YES**, per
OWNER-LEVEL4-TESTNET-RUNS-01, via VALIDATOR-25 slice 4, only after stage 1's
image conditions pass. L4 rebuilds compile under the accepted G5 profile in
the 8 GiB lane, deadline 120 s. Mainnet stays fail-closed.

**D3 — Image conditions: ENFORCED, IN ORDER.** Rebuild → six R8 probes → R1
containment → hostile-lowering probe → only then any Level 4 lowering,
Graphite's included. The standing rule (OWNER-ANALYSIS-IMAGE-STANDING-ACCEPT-01)
accepts the image when the six pass; the lowering probe is additionally
required at L4 and becomes gate item R8-L4 — *Test Lead: register the id
this week so it stops being a checklist line.*

**D4 — VALIDATOR-25 slice 3, owner operator steps: FIRST OWNER BLOCK THIS
WEEK**, same block as the Launchpad handoff's D3. Deployment file, service
unit, tunnel, minerC profile. The Carbon Validator prepares every file and
command the day before; the block applies them and records host state so
"UNVERIFIED here" stops being the honest description.

**D5 — The acceptance definition in §1: ADOPTED** as cell `L4` in the
Launchpad acceptance plan §3.8, and `L4-COMBINED` as a second cell. Both
doors, same bytes, same record, or it is not a pass.

**D6 — Graphite L4 rerun under constructor-6: YES, after D3**, one run,
kimi-k3, USD 14.94 ceiling. The cause of any refusal must reach the extract
(the 2026-10-11 refusal's cause did not; that is a logging defect to fix
before the rerun, not after).

**D7 — "Every Launchpad capability": DEFINED AS PLT-29's C0–X3 live.** The
offline coverage table is the test list; each row runs through the real door
against the served target and gets a live result. New capabilities Graphite
tests later are appended to the table before they are called tested.

**D8 — Entry bar "tested", operationally:** a capability is *tested* when it
has (a) a live rebuild to a sealed verdict on the dev ladder through the
Launchpad, and (b) an attack-oracle probe where an oracle family exists.
Capabilities without an oracle family are admitted and carried in the
refused-capability log's style as **UNPROTECTED** until PKT-15 covers them;
an attack that lands removes the item, per OWNER-CONSTRUCTION-ANYTHING-01.
No capability enters by prose.

**D9 — Budget sequencing: L4 END-TO-END BEFORE THE L5 HUNT.** Within the
weekly USD 150, reserve constructor-6 (14.94) and stage C Attacker (26.95)
this week; the OPEN-SAFE L5 hunt (86.71) starts the following week unless
the ledger shows headroom. The L2–L4 Constructor pass (44.85) runs after
stage 3 so it exercises a served ladder, not a fixture.

**D10 — Park:** Level 5 adoption, the promotion bar (stays `HUMAN_INPUT`,
set NULL), any mainnet G5 security review, per-level rules, a public
opening of L4. S4's empty set is correct and complete for now; Level 5 wins
enter the base only through a measured, versioned promotion later.

## 3B. Owner gates lifted, 2026-10-15

The owner, in his own session, verbatim:

> Include my authorization to lift the owner gates in the L4/S5 doc

This section is that authorization. Each gate below was reserved to the owner
by the record named beside it. It is lifted **for development and testnet
only**, on `battery-dev-ladder` and the development door, under the D3 image
conditions (rebuild → six R8 probes → R1 containment → hostile-lowering probe)
and the existing grants. Nothing here touches mainnet, LIVE, weights, rewards,
the main intake, or opening Level 4 to miners.

| Gate | Reserved by | Lifted as |
|---|---|---|
| **S5 serving go** | PLT-32 S4 record ("S5 needs go"); CONSTRUCTION_CONTRACT_PLAN_01 S5 | **GO.** Serve `composition-v1` plus `battery-l4-graph-v3` (default) and `-v4` (`inert_fields` arm) on `battery-dev-ladder`, testnet 567, hotkeys minerC and Graphite's constructor only. The Carbon Validator may configure and start it without a further owner prompt. |
| **`ladder_level_4_not_open`** | OWNER-DEV-LADDER-KIND-01 (L1–3 only); OWNER-LEVEL4-TESTNET-RUNS-01 ("may be lifted", VALIDATOR-25 slice 4) | **LIFTED** on the dev ladder once the D3 image conditions pass. Slice 4's Level 4 slot and parts upload are authorized to go live on that deployment. |
| **Isolation review of GRAPHITE-L4-STAGING-01 (route R1)** | GRAPHITE-L4-STAGING-01 DoD ("the isolation review recorded by the owner, or the tool left refused"); OWNER-L4-STAGING-IMAGE-RELEASE-01 (accepted into testing, analysis during testing) | **CONFIRMED for testing.** The acceptance covers lowering untrusted model source in the agent's own analysis container, the envelope transport, and the carry-through of staged documents into Carbon's rebuild workspace. It is an acceptance into testing, not an audit; the release record's "not verified" list is worked off by stage 1 and the acceptance run. |
| **Live Level 4 runs on testnet** | OWNER-LEVEL4-TESTNET-RUNS-01 | **REAFFIRMED.** Carbon builds and trains submitted graphs in the isolated rebuild worker (CarrierBackend), compiled under the accepted G5 profile in the 8 GiB lane. |
| **Stage C runs** | OWNER-GRAPHITE-STAGE-C-01 ("Running stage C is not authorized by this grant. Each run still needs…"); OWNER-L4-G-CONSTRUCTOR-6-GRANT-01 | **AUTHORIZED TO RUN**, within their ceilings: the Constructor rerun under constructor-6 (USD 14.94, one run, kimi-k3) and the two stage C Attacker runs (USD 26.95), in the order §3-D9 sets. No per-run owner prompt is needed; the ledger's weekly cap still governs. |
| **Attacker code on disposable testnet hosts** | GRAPHITE_OPEN_SAFE_01_PLAN §1 (L4 "waits for … the security sign-off for Attacker code on disposable hosts") | **ACCEPTED for dev/testnet disposable hosts only**, under AGENTS.md §13 as the owner's acceptance: the Attacker runs on hosts created for the run and destroyed after it, with the carrier containment and the standing analysis-image rule in force; it never runs on a Carbon host or the AX42. Not a production security claim. |
| **Operator steps on valV2** (VALIDATOR-25 slice 3) | Owner's hands | Not a gate; scheduled as §3-D4's owner block. The Carbon Validator prepares every file and command; the owner applies them. |

**Still closed, deliberately.**
- Opening Level 4 to miners: a locked, released contract the owners choose
  (OWNER-GRAPHITE-TEST-WAVE-03). Not lifted.
- Mainnet G5 security review (OWNER-L4-G5-COMPILE-ISOLATION-01): mainnet
  stays `mainnet_requires_security_review`. Not lifted.
- The promotion bar (PLT-32 S4): stays `HUMAN_INPUT`, NULL. Level 5 wins
  enter the base only through a measured, versioned promotion.
- Any new grant figure: none is created here (OWNER-POD-LAUNCH-DELEGATION-01).
- Weights, rewards, the main intake and the main deployment: unchanged.

---

## 4. Execution guidance

- **Nothing executes a participant's bytes on a Carbon host.** Lowering runs
  in the agent's own analysis container; Carbon reads one exported file
  through the miner door, parses it strictly as data, and keeps it by digest.
  G5 compiles Carbon's own program from a Carbon-checked graph. Any change
  to that boundary is security-sensitive and goes to the Carbon Validator and
  the owner before it counts.
- **Fail closed, name the blocker.** Every rebuild stop is Carbon's
  environment (`BLOCKED`, e.g. `level4_submission_documents_not_staged`) or
  the candidate's (typed `GraphRefused`), never ambiguous. A refusal whose
  cause is missing from the extract is a defect.
- **Same module both sides.** Launchpad and validator call
  `carbon/level4/staging.py`; if the contract page and the module disagree,
  the module is right and the page is fixed.
- **Evidence.** Cells per the Launchpad plan §2 (no keys, addresses,
  balances, profile contents, hidden material). Image acceptance records
  keyed to the image digest. Refusals and wishes to
  `REFUSED_CAPABILITY_LOG.md` with a class (BRIEF_GAP / ENVELOPE_TOO_TIGHT /
  CORRECT_BLOCK). Findings to `LESSONS_REGISTER.md` as widen or fix.
- **Validation** through `./scripts/dev/canonical.sh`; exact-head CI is the
  acceptance source. Focused baselines: `test_level4_staging.py`,
  `test_graphite_level4_{stage,carry,session}.py`, `test_level4_tooling_in_image.py`,
  `test_battery_level4_rebuild.py`, `test_battery_composed_training.py`,
  `test_composition_launchpad.py`, `test_construction_promotions.py`,
  `test_launchpad_construction_levels.py`, both import-closure invariants.
- **Spend** only under a named grant and the weekly cap; the ledger's
  `weekly_budget_reached` is a schedule signal, not something to work around.

---

## 5. Schedule

| Week | Stages | Gate |
|---|---|---|
| 1 | 1 (image + probes), 2 (S5 + L4 open, records), 3 (owner block on valV2), 4 (options truth) | New image accepted; ladder serves composition-v1 + L4; Launchpad shows the path Available |
| 2 | 5 (Graphite L4 rerun), 6 (acceptance run, both doors), 7 (combined recipe) | Cells `L4` and `L4-COMBINED` written with sealed verdicts |
| 3 | 8 (live coverage C0–X3), 9 (stage C Attacker at L4) | MEASURED.json has a live column; zero escapes or every finding dispositioned |
| 4 | OPEN-SAFE L2–L4 Constructor pass on the served ladder; L5 hunt | Budget permitting |

If week 1 slips it is stage 3 — owner hands on valV2 — or the image
rebuild; neither is an engineering unknown.

---

## 6. Definition of done

1. A Level 4 graph lowered by Graphite has a sealed DEVELOPMENT verdict from
   `battery-dev-ladder`, submitted through the Launchpad and through the
   development door, same digest, same record.
2. The combined S2 composition has the same.
3. Every PLT-29 coverage row has a live result through the real door.
4. The analysis image in use passed the six R8 probes, R1 and the hostile
   lowering probe, keyed to its digest.
5. Stage C's Attacker pass at L4 is filed with zero escapes or every finding
   dispositioned.
6. The Launchpad's construction options show "Available" only for what a
   receiver-checked target serves, on both doors.

Passing is engineering evidence: implemented, tested, exercised on testnet.
It is not scientific, security or production qualification; it does not open
Level 4 to miners (a locked, released contract the owners choose) and does
not touch mainnet.

---

## 7. Identities

Decisions: OWNER-CONSTRUCTION-ANYTHING-01, OWNER-LEVEL4-GRAPH-ONLY-01,
OWNER-L4-G5-COMPILE-ISOLATION-01, OWNER-L4-VALUES-01, OWNER-LEVEL4-TESTNET-RUNS-01,
OWNER-L4-STAGING-IMAGE-RELEASE-01, OWNER-ANALYSIS-IMAGE-STANDING-ACCEPT-01,
OWNER-DEV-LADDER-KIND-01, OWNER-LADDER-THROUGH-LAUNCHPAD-01,
OWNER-GRAPHITE-STAGE-C-01, OWNER-L4-G-CONSTRUCTOR-6-GRANT-01,
OWNER-GRAPHITE-OPEN-SAFE-01-GRANTS, PLT25-D1/D2, PLT32-S3-WIRING,
PLT32-S4-EMPTY-PROMOTIONS, PLT18-PROSPECTIVE-INERT-FIELDS-01, L4-LAUNCHPAD-STANDALONE-V3,
LAUNCHPAD-LEVELS-01-S2-S3 / S4, PKT15-BOUNDED-ORACLES-01.
Tickets: UNIFIED-CONSTRUCTION-01-PHASE1, PLT-25-CONSTRUCTION-CONTRACT-S2,
PLT-32-CONSTRUCTION-S3 / S4, VALIDATOR-25, LAUNCHPAD-LEVELS-01,
GRAPHITE-L4-STAGING-01, L4-LAUNCHPAD-STANDALONE-V3-01, PLT-03, PLT-18, PLT-24,
PLT-28, PKT-15, LEVEL4-G5-LANE-MEMORY-01.
Docs: `docs/development/graphite/level4/` (`LEVEL4_STAGING_CONTRACT.md`,
`L4_STAGING_R1_CONTRACT.md`, `L4_STAGING_IMAGE_RELEASE_SUMMARY.md`,
`REFUSED_CAPABILITY_LOG.md`, `STARTER.md`), `GRAPHITE_OPEN_SAFE_01_PLAN.md`,
`GRAPHITE_LADDER_WAVE_PLAN.md`, `UNIFIED_CONSTRUCTION_SHADOW.md`,
`docs/development/launchpad/offline_coverage/MEASURED.json`.
Code: `carbon/level4/`, `carbon/battery/{level4_worker,level4_parts,composed_*}.py`,
`carbon/reconstruction/{composition_registry,development_composition,construction_promotions}.py`,
`carbon/development_ladder/`, `carbon/battery/deployment.py` (`ladder_for`),
`carbon/agent_campaign/graphite/{experiment,miner_path,phase3}.py`,
`scripts/dev/miner_launchpad/{construction_options,levels,operations}.py`.
Registered digests: `composition-v1` `0865617e…`; `battery-l4-graph-v3`
`ad15d6a8…`; G5 profile `carbon.c03.linux-x86_64-cpu.level4-g5-compile.v1`.
