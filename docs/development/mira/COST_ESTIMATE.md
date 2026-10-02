# Mira integration: cost estimate for the paid stages

**Owner update (2026-10-01):** "spending is approved, I will add $ if needed."
Paid Mira execution is authorized in principle. The controller still enforces
an explicit **per-campaign ceiling** and a **grant ceiling**; both are
owner-supplied configuration with no default, and the controller refuses to
register a campaign or exist at all without them (`grant.py`,
`controller.register_campaign`). The numbers below are recommendations with
their basis, not settings.

## Basis

| Input | Value | Source |
|---|---|---|
| GPU pod rate | USD 0.49 per hour (A40, RunPod) | EV4 spending ledger, `docs/development/evidence/ev4-2026-10-01/accounting/ledger.jsonl` (branch `claude/ev4-optimizer`) |
| Reference solve | about 74 s per 30-cycle solve, 7 workers per A40 pod | EV4 pre-registration §8, from the exam-design campaign |
| Earlier solve figure | about 65 s per solve on 4 local CPU workers | `BATTERY_ENGINEERING_VALUE_EV1.md`; a planning input only (handoff §15: re-benchmark before pricing) |
| Construction envelope | 2 CPU, 4 GiB, 600 s deadline per reconstruction | `capability_registry._WORKER_ENVELOPE` |
| Level-0 attack workload | 3 adversarial sessions × up to 20 executed attempts | handoff §15; a workload estimate, not coverage |
| Mira price | **UNVERIFIED**: pricing is not public | `CAPABILITY_REPORT.md` |

## Carbon-side compute by stage (measurable)

| Stage | Work | Worst case | Cost at USD 0.49/h |
|---|---|---|---|
| 3. Mira smoke test | 1 valid submission reconstructed and screened, 1 expected rejection (no compute), 1 cancellation, recovery, export | about 1 pod-hour | about USD 0.50 |
| 4. Level-0 campaign | 60 attempts × at most 600 s reconstruction; 5 retained constructions × 3 rebuilds (fresh worker, fresh seeds, second operator); diagnostic specimens | about 10 + 2.5 + 1 pod-hours | about USD 7 |
| 6. Optimizer pilot | Re-benchmark the solve; per method (fixed grid and one proposed search) at most 8 PB-INV + 50 PB-ADV verification solves on EV2's published development conditions | 116 solves ≈ 0.4 pod-hours, plus benchmark | about USD 0.50 |
| Confirmation (stage 7) | Fresh evaluator-held cases and withheld attacks | budget is **HUMAN_INPUT** (study sheet) | not estimated |

Model queries for the optimizer are seconds (1,023 designs × conditions), so the
pilot's cost is the verification solves.

## Vendor cost (unknown)

`total = Σ sessions × Autoscience's per-session (or per-unit) price + Carbon compute`.
Planned sessions: 3 for the smoke test, then 3 adversarial and 1 construction
session at Level 0, then 1 optimizer-review session. The per-session price is
**UNVERIFIED** until Autoscience quotes it.

## Recommended starting ceilings

| Setting | Recommendation | Basis |
|---|---|---|
| Smoke-test campaign ceiling | **USD 50** | About USD 0.50 Carbon compute plus an exposure limit for three early-access sessions of unknown price. It is a stop, not a forecast; raise it once Autoscience quotes. |
| Level-0 campaign ceilings | Carbon compute USD 25 per campaign; the vendor part set from the quote | About USD 7 projected compute with roughly 3× headroom, following EV4's pattern (USD 15 cap against about USD 3.5 projected) |
| `cleanup_allowance` | USD 1 | Two pod-hours to stop and confirm stray workers |
| `worst_case_run_cost` | The vendor's quoted maximum per session plus USD 1 Carbon compute | The controller reserves this before every launch |
| `max_concurrency` | 1 for the smoke test, 3 for Level 0 | One supervised run at first; three adversarial sessions later |

The grant also needs a provider account, expiry, permitted runs, runtime and
submission limits (`python -m carbon.agent_campaign grant-template`).
