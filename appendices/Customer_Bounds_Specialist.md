# Customer Bounds Specialist — Plug-and-Play Procedure

**Carbon — requirements · constraints · envelope → bounded specialist SKU**

**Version:** 1.0  
**Status:** Product & ops procedure  
**Related:** [`Specialist_Bank.md`](./Specialist_Bank.md), [`Landscape_Agent.md`](./Landscape_Agent.md), [`Use_Cases_by_Phase.md`](./Use_Cases_by_Phase.md), `SPEC.md`

---

## TL;DR

**Customer provides:** requirements, constraints, operating envelope (and optional latency/export class).  
**Carbon returns:** a specialist model **set to those bounds**, plus artifact, evidence pack, and escalation notes — only after a product battery **parameterized by those bounds**.

**Subnet is not required for every sale.** If Landscape already holds enough verified intelligence for the regime, OpCo may run specialization **off-subnet** (controlled retrain + full product battery) and sell the SKU. The subnet remains the engine that *grows* regime intelligence; commercial delivery is allowed wherever evidence is sufficient and the grounding gate passes.

**Not claimed:** one form fill → flight certification.  
**Claimed:** standardized bounds intake → bounded specialist with job-shaped proof.

---

## 1. Purpose

Define a **repeatable commercial procedure** so specialists are plug-and-play at the *contract* layer:

1. Structured customer intake (requirements / constraints / envelope).  
2. Regime match against Landscape evidence (or explicit cold-start path).  
3. Recipe synthesis + controlled retrain.  
4. Product battery **configured from customer bounds**.  
5. Grounding gate → license → deliverable.  
6. Clear rules for **on-subnet sponsored challenges** vs **off-subnet fulfillment** when intelligence already exists.

This procedure sits **on top of** [`Specialist_Bank.md`](./Specialist_Bank.md). It does not replace lean exams, dual egress, or anti-distillation doctrine.

---

## 2. Plug-and-play definition (normative)

| Term | Meaning |
|------|--------|
| **Plug-and-play** | Customer states bounds in a fixed schema; Carbon configures specialization + battery from that schema; delivery is a closed SKU with envelope-aligned evidence |
| **Not plug-and-play** | Skip retrain; skip product battery; claim system-level certification; accept free-text requirements with no machine-checkable constraints |

**Interface promise:** same intake schema across regimes that Carbon supports.  
**Physics promise:** only regimes with generators, gates, and battery templates.

---

## 3. Customer intake schema (v1)

Minimal structured fields. Extend per regime template; do not require a full MBSE model to start.

```text
CustomerBounds {
  customer_id / engagement_id
  regime_template_id          # e.g. contact_force_v1, thermal_panel_v1
  use_mode                    # design_sweep | control_loop | hybrid

  requirements[] {
    id, quantity, relation, value, unit, notes?
    # e.g. peak_force <= 40 N; cycle_time <= 2 ms
  }

  constraints[] {
    id, quantity, relation, value, unit, severity  # hard | soft
  }

  envelope {
    inputs[]  { name, min, max, unit, distribution_hint? }
    context[] { name, min, max, unit }   # ambient, surface_class, …
    exclusions[]?                       # explicit out-of-scope
  }

  latency_class?              # L1_interactive | L2_batch | L3_control_rate
  export_class?               # onnx | other_approved
  escalation_policy?          # text or structured: outside envelope → stop | call_hifi | human

  data_policy                 # no_customer_data | aggregate_only | private_challenge
  commercial_tier             # catalog | sponsored_open | sponsored_licensed | private
}
```

**Validation rules**

- At least one hard constraint or requirement with numeric bound.  
- Envelope must be a closed box on all model inputs used at inference.  
- `regime_template_id` must exist in Carbon’s template registry (or engagement is R&D/cold-start priced).  
- Free-text alone is insufficient for battery parameterization.

---

## 4. Procedure (end-to-end)

```text
INTAKE
  Validate CustomerBounds schema
  Map requirements/constraints → PB-INV targets + ADV boxes
  Map envelope → stress/ADV domain + PB-ESC notes
  Map use_mode + latency_class → PB-LAT / PB-ROLL depth
        │
        ▼
REGIME MATCH
  Query Landscape opportunity for regime_template (+ neighbors)
  IF evidence sufficient → OFF-SUBNET or BANK path (§5)
  IF evidence thin → SPONSORED CHALLENGE or cold-start premium (§5)
        │
        ▼
SYNTHESIZE RECIPE
  Effect-based merge from verified cards (not single-winner weights)
  Inject customer objectives into training recipe where representable
  Controlled retrain on fresh procedural draws (seed policy per Specialist_Bank)
        │
        ▼
PRODUCT BATTERY (bounds-parameterized)
  PB-PHYS, PB-ROLL, PB-INV(customer targets), PB-ADV(envelope box),
  PB-LAT, PB-ART, PB-ESC(envelope + escalation_policy)
        │
        ▼
GROUNDING GATE
  All mandatory PB pass + lineage + seed policy
  Fail → repair / re-queue / no ship
        │
        ▼
DELIVER
  Closed SKU: artifact + recipe + Model Card + PB report + license
  Envelope printed on card is the commercial validity domain
```

### 4.1 How bounds parameterize the battery

| Customer field | Battery effect |
|----------------|----------------|
| Requirements / hard constraints | PB-INV target set and pass thresholds |
| Envelope box | Domain for stress draws and PB-ADV search |
| use_mode = control_loop | Stronger PB-ROLL + stricter PB-LAT |
| use_mode = design_sweep | Stronger PB-INV query budget; LAT may be L1/L2 |
| escalation_policy | PB-ESC text mandatory; ties to observed ADV/INV holes |
| export_class | PB-ART format |

Lean subnet scoring is **unchanged** by a single customer’s bounds. Customer bounds affect **promotion / commercial** exams only (unless the customer funds a sponsored challenge that defines a public or semi-public regime).

### 4.2 Recipe synthesis (reminder)

Per [`Specialist_Bank.md`](./Specialist_Bank.md):

- Merge **stable effects** from cards (backbone family, loss enables, curriculum tags).  
- **Do not** dump champion weights as the product.  
- Add customer-shaped objectives only when they are expressible in train/eval (e.g. constraint penalties, INV targets).  
- Retrain under control; then prove with PB on **new** seeds.

---

## 5. On-subnet vs off-subnet commercial paths

Both paths must hit the **same grounding gate** for a full commercial SKU. They differ in *how evidence is obtained and paid for*.

### 5.1 Off-subnet fulfillment (intelligence already sufficient)

**When allowed**

- Landscape support density and stability for `regime_template_id` meet internal policy thresholds.  
- Required generators, gates, and PB templates exist.  
- Customer bounds lie inside (or are a contraction of) a domain Carbon can evaluate.  
- Legal/commercial review accepts data_policy and license tier.

**What runs**

- OpCo / Specialist Bank pipeline only: synthesize → retrain → **full product battery** → ship.  
- **No requirement** to open a new subnet challenge or spend emissions on this engagement.  
- Optional: thin public catalog entry (“regime specialized”) without leaking recipe/weights.

**Why this is allowed**

The subnet’s job is to **produce verified strategy intelligence at scale**. Once that intelligence exists, forcing every commercial delivery back through emissions is unnecessary theater. Buyers pay for **bounded, battery-passed artifacts**, not for a live challenge ID.

**Why this is not a side-door cheat**

- Still no teacher-checkpoint laundering.  
- Still mandatory PB configured by **their** bounds.  
- Still dual egress: miners do not receive the closed SKU.  
- Emissions remain lean-exam-only; purchase never buys rank.

### 5.2 On-subnet sponsored challenge (intelligence thin or customer wants network search)

**When used**

- Sparse Landscape evidence for the regime.  
- Customer wants ongoing competition against their regime family.  
- Bounds are novel enough that public or licensed challenge definitions add data Carbon does not yet have.  
- Pricing tier is challenge-sponsored (open / licensed / private per GTM).

**What runs**

- Challenge brief encodes regime + optional public constraints (private details stay off public brief as tier requires).  
- Lean exams accumulate cards → Landscape updates.  
- Graduation still requires product battery (sponsor may **add** PB tests in the brief).  
- Sponsor receives licensed graduate under contract; network receives search signal.

### 5.3 Decision rule (ops)

```text
if landscape.opportunity_sufficient(regime) and bounds.in_evaluable_domain:
    prefer OFF_SUBNET_FULFILLMENT
elif customer.funds_sponsored_challenge or evidence_thin:
    SPONSORED_CHALLENGE_PATH
else:
    COLD_START_QUOTE (time + cost premium) or DECLINE
```

**Principle:** Subnet when you need **new verified search**. Off-subnet when you already have **enough verified intelligence** to specialize honestly.

---

## 6. Deliverable package (commercial)

| Asset | Role |
|-------|------|
| Deployable artifact (ONNX-class) | Runs in customer tool / loop |
| Exact certified recipe | Provenance / fine-tune start under license |
| Model Card + PB report | Review evidence |
| Envelope + escalation | Validity domain printed as product boundary |
| License + update channel | Commercial terms; re-verify when templates move |

**Qualification language (allowed)**  
“Specialist validated against customer-stated requirements, constraints, and envelope under Carbon’s product battery for regime template X.”

**Qualification language (forbidden without separate program)**  
System certification, flight/safety cert, “replaces customer V&V,” unbounded operational authority.

---

## 7. Incentive and trust boundaries

| Rule | Statement |
|------|-----------|
| No pay-to-compete | Buying a specialist or funding off-subnet work does not buy emissions |
| No lean bypass | Off-subnet SKUs still require product battery; they do not redefine subnet scores |
| No full SKU on miner API | Dual egress unchanged |
| No teacher distillation | Recipe from effects + retrain + PB |
| Customer data | Default: no training on proprietary trajectories unless tier and data_policy explicitly allow; prefer bounds-parameterized procedural/eval design |

---

## 8. Worked micro-example (gripper / contact)

**Intake**  
- Requirement: hold part without drop under payload band.  
- Constraint: force ≤ F_max (no crush).  
- Envelope: payload [m0, m1], surface classes {dry, slightly_slick}, speed ≤ v_max.  
- use_mode: control_loop; latency_class: L3_control_rate.

**Match**  
Contact-force template has sufficient Landscape cards → **off-subnet fulfillment** allowed.

**Recipe**  
Merge contact-stress-surviving loss/curriculum effects; drop lab-pose-only winners; train with constraint-aware objective.

**Battery**  
PB-INV/ADV inside envelope (heavier / slicker cases); PB-ROLL horizon for control; PB-LAT at control rate; PB-ESC outside envelope → reduce force / stop.

**Deliver**  
Force map specialist + envelope card + evidence pack for production grip assistance — not a leaderboard rank.

---

## 9. Success metrics

| Metric | Intent |
|--------|--------|
| Time intake → grounded SKU (off-subnet path) | Commercial throughput |
| % engagements served off-subnet vs sponsored | Intelligence maturity |
| PB pass rate on bounds-parameterized batteries | Procedure quality |
| Envelope-related field escalations / returns | Honesty of bounds |
| Zero SKUs without PB report | Grounding gate integrity |
| Zero emissions coupling to purchase | Incentive integrity |

---

## 10. Thesis

Specialists are **bounds-conditioned products**. The customer plugs in requirements, constraints, and envelope; Carbon specializes from verified Landscape intelligence, proves the model under a battery **defined by those bounds**, and ships a closed artifact with a printed validity domain.

When the subnet has already done its job — dense, stable evidence for a regime — **business may proceed off-subnet** without apology. When evidence is thin, **sponsored challenges** buy new verified search. In both cases the commercial object is the same: a model set to the customer’s bounds, not a trophy from the public scoreboard.

---

*Canonical procedure for customer-bounds intake, bounds-parameterized product battery, and on- vs off-subnet commercial fulfillment. Implements plug-and-play at the contract layer; defers to Specialist_Bank for gauntlet definitions and dual egress.*
