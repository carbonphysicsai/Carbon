# Graphite admission testing: reconciliation (handoff §2)

**Ticket:** GRAPHITE-ADMISSION-01. **Handoff:**
`docs/development/graphite/ADMISSION_TESTING_HANDOFF.md`. Refreshed 2026-10-02
at `origin/main` `0a207a43f`. This branch also merges `origin/agent/challenge-pipeline`
(PR 498, roadmap rev 2.2, head `6ce38845b`) for the ladder, level-proposal
and lessons modules.

## 1. Commits

| Item | Commit | State |
| --- | --- | --- |
| #458 Challenge admission | `aea352d38` (its core, merged as #473) | On main. `Design_Specs/Challenge_Admission.md`, `carbon/challenge_readiness/admission.py`. The readiness-record gate held from #458 is not on main |
| #464 hidden-batch sealing | `f1429b60a` | On main. Rule v2, `exam.MINER_DISCLOSURE` |
| #468 expansion records | `aadaf2331` | On main. `carbon/reconstruction/expansion_record.py`; battery records `0000`, `0001` |
| #470 divergence detection | `dc61a6e83` | On main. `carbon/battery/value/divergence.py` |
| #475 MIRA-ADMISSION-01 stages 1-2 | `f65461f02` | On main. Controller, grant, boundaries, Level-0 study sheet, `search_commitment`, EV4 protected conditions |
| GRAPHITE-01 plan, phases 1-2 | `65732f597` (#478), `899ce6f1c` (#480), `fae375621` (#494) | On main. Provider, roles, ladder, toolbox, literature layer, method cards |
| PR 504, Graphite phase 3 | `origin/claude/graphite-phase3` `1b64013c6` | Open. Real miner path, proposal runner, pods, delivery bundle and clean rebuild |
| Step 4 rebuild (CHALLENGE-PROTOCOL-04) | `origin/agent/challenge-protocol-04` `658f5cffd` | In progress on top of #504. Stage profile, Attacker v1, step 4 grant. Its rebuild branch `agent/challenge-protocol-04b` is not pushed |
| PR 498, roadmap rev 2.2 | `origin/agent/challenge-pipeline` `6ce38845b` | Open; merged into this branch. `ladder.py`, `proposals.py`, `lessons.py` |

## 2. What exists and what is missing, by handoff section

| § | Exists | Missing | Where it is addressed |
| --- | --- | --- | --- |
| 3 Integration contract | `GraphiteProvider` behind the #475 controller, grants, session records with role, model, grant and campaign | The real miner path (PR 504); the stage profile (step 4); the construction level in each session record | PR 504, step 4; level proposals record their level (slice P) |
| 5 Controller | Intent before dispatch, reservations, reconciliation, limits, findings stop expansion | Nothing these slices need | |
| 6 Boundaries | Role workspaces, allowlisted checkout, canaries | Allowlists name battery files per role, with no Challenge dimension | Follow-up; not changed while step 4 binds the manifests |
| 7 Study sheet | Battery Level-0 sheet, ten pins, inventory | Takes no Challenge; the ladder map is battery's but lives in shared code | Slice A |
| 8 Ladder | Admission §3 levels, `ladder.py`, `proposals.py`, expansion records | Level proposals for any Challenge; a Level-1 surface; Carbon's reconstruction for it; the matched, ablation and interaction harness | Slices P and B |
| 9 Eight checks | Registered specimens and controls (battery text) | Coverage report; Attacker v1 runs | Step 4 |
| 10 Related protections | #464, #468, #470 and #458 suites | Reproducing and triaging the retained battery divergence findings before a new expansion | Step 4, before any climb |
| 11-12 Optimizer researcher | `search_commitment` (commitment before reference access, EV4 refused, comparison harness) | A Challenge-neutral request and result; a Graphite method proposal; a freeze manifest; priced K and grid choices | Slice C |
| 13 Customer rebuild | PR 504's delivery bundle and clean rebuild | A second operator, fresh-seed repeats, continued training under a new identity | Slice D, after PR 504 merges |
| 15 Stages | Reconciliation (this file) | Smoke (#504), Level 0 campaign (step 4), Level 1, optimizer pilot, confirmation | Engineering parts in slices B and C; the live stages need owner grants |

## 3. Affected tests

Run for every slice, on the canonical workflow:

- admission `tests/cpu/test_challenge_admission.py`; readiness
  `tests/cpu/test_challenge_readiness.py`;
- engineering value `tests/cpu/test_battery_engineering_value*.py`,
  `tests/cpu/test_engineering_value_audit.py`; divergence
  `tests/cpu/test_admission_divergence.py`;
- expansion records `tests/cpu/test_construction_expansion_record.py`;
  capability registry `tests/cpu/test_construction_capability_registry.py`;
  battery construction contract `tests/cpu/test_battery_construction_contract.py`;
- MCP connection `tests/cpu/test_mcp_agent_connection.py`,
  `tests/service/test_mcp_external_client.py`; protected material
  `tests/cpu/test_protected_material_isolation.py`; rule v2
  `tests/cpu/test_battery_rule_v2.py`; intake `tests/cpu/test_battery_intake.py`;
  B02b boundary `tests/invariants/test_b02b_construction_boundaries.py`;
- agent campaign `tests/cpu/test_agent_campaign_*.py`,
  `tests/cpu/test_design_search_commitment.py`; Graphite
  `tests/cpu/test_graphite_*.py`; pipeline `tests/cpu/test_challenge_pipeline.py`.

## 4. Battery literals in shared code that block a second Challenge

| Where | Literal | Disposition |
| --- | --- | --- |
| `carbon/agent_campaign/study.py` | the Challenge token; `_LADDER`, which also lacks the `hybrid` and `prediction` dimensions; battery pin sources (`daemon`, `exam.RULES["v2"]`, `exam.MINER_DISCLOSURE[2]`, feedback fields, `reference.py`, `truth.py`, the EV2 decision contract); specimen and sheet text naming rule v2 and EV2 | Slice A moves all of it to battery's adapter |
| `carbon/agent_campaign/boundaries.py` | allowlists of battery files per role; `ev4` in the denylist | Follow-up: a per-Challenge allowlist. Not changed here, because the step 4 work binds the manifests |
| `carbon/agent_campaign/graphite/literature_fetch.py`, `method_cards.py` | three battery queries in the registered query set; battery wording in the Reader prompt, pinned by digest | Follow-up: a per-Challenge query set and prompt are a new registered version |
| `carbon/battery/value/search_commitment.py` | `c1`, `c2`, `t_amb_c`, `soc0`, the design grid, the three quantities, the battery constraint ids, `ev4_protected_conditions` | Slice C adds a Challenge-neutral layer; this file becomes the battery adapter's engine, unchanged |
| `carbon/reconstruction/challenge_contracts.py` | the `if`/`elif` compiler dispatch by Challenge | Follow-up: a compiler registry when a second contract is registered |
| `carbon/reconstruction/capability_registry.py` | the closed `CONTRACTS` tuple; Burgers as every function's default | The registry is each Challenge's record, so its battery data is in the right place. A new Challenge adds its contract here |
| `carbon/battery/value/divergence.py` | `DECIDING_RULE = "control-exam-v1"` as the default; the only emitter of `carbon.admission-conditions.v1` lives under `carbon/battery` | Follow-up: the condition logic is generic and can move to a shared module |
