# Customer Bounds Specialist — Plug-and-Play, Data Posture & GTM

**Carbon — requirements · constraints · envelope → bounded specialist SKU**

## TL;DR

**Customer provides:** requirements, constraints, operating envelope (not their secret simulation archive).  
**Carbon returns:** a specialist **set to those bounds**, plus artifact, evidence pack, and escalation notes — only after a product battery **parameterized by those bounds**.

**Default data posture:** *No customer proprietary trajectories in Carbon training.* Bounds in; procedural/eval machinery on Carbon’s side; sensitive data stays with the customer.

**Adapt path:** Customer may retrain/adapt **on their infra** under license. That **voids** the original PB cert until **re-qualification**. Two labels: `Certified` vs `Adapted (customer)`.

**Subnet vs sale:** If Landscape evidence is sufficient, fulfill **off-subnet**. Use sponsored challenges when evidence is thin or the customer wants network search. Emissions never sold.

**GTM:** Trial on non-critical regimes → bounds SKU → optional adapt kit → paid re-verify → sponsored/private only when needed.

---

## 1. Purpose

Define a repeatable commercial system:

1. Structured bounds intake (requirements / constraints / envelope).  
2. **Default execution without handling sensitive customer data.**  
3. Regime match (Landscape) → recipe → controlled retrain → bounds-parameterized product battery.  
4. On-subnet vs off-subnet fulfillment rules.  
5. **Customer-side adapt + re-qualification** (optimal product design).  
6. Go-to-market ladder that matches real buyer confidence, not hype.

Defers to [`Specialist_Bank.md`](./Specialist_Bank.md) for gauntlet definitions, dual egress, and anti-distillation doctrine.

---

## 2. Plug-and-play definition (normative)

| Term | Meaning |
|------|--------|
| **Plug-and-play** | Customer states bounds in a fixed schema; Carbon configures specialization + battery from that schema; delivery is a closed SKU with envelope-aligned evidence |
| **Not plug-and-play** | Skip retrain; skip product battery; claim system certification; accept free-text only; require proprietary datasets for the default SKU |

**Interface promise:** same intake schema across supported regime templates.  
**Physics promise:** only regimes with generators, gates, and battery templates.

---

## 3. Default data posture (normative)

### 3.1 Principle

> **Bounds in. Sensitive data stays with the customer.**  
> Standard specialization does **not** require training on customer proprietary meshes, flight logs, production trajectories, or golden solver decks.

| Carbon uses (default) | Customer keeps |
|------------------------|----------------|
| Stated requirements, constraints, envelope (numeric) | Proprietary CAD/CFD/FEA archives |
| Carbon procedural / licensed non-sensitive draws | Operational plant logs |
| Public or Carbon-owned regime templates | ITAR/export-controlled corpora |
| Product-battery seeds under Carbon policy | Anything they cannot put in a vendor cloud |

### 3.2 Why this is the default

- Primes and suppliers will **trial** a path that does not open a data-security program.  
- Carbon’s wedge is **verification and selection**, not “become the lakehouse for their sims.”  
- Bounds-parameterized INV/ADV already express the customer’s job without absorbing their archive.

### 3.3 Customer-side validation

After delivery, the customer **should** shadow-compare the specialist against their hi-fi on **their** data. That comparison is **their** process. Carbon does not need those runs to ship the default SKU.

### 3.4 When customer data *may* enter Carbon systems

Only under an explicit tier and written `data_policy`:

| Policy value | Meaning |
|--------------|--------|
| `no_customer_data` | **Default.** Train/eval without proprietary trajectories |
| `aggregate_only` | Optional anonymized/aggregate statistics; no raw trajectories retained as train set unless contract says so |
| `private_challenge` | Sponsored/private regime; data handling per contract (may include air-gap, no-retain, residency) |
| `customer_adapt_only` | Data never sent to Carbon; adapt kit runs on customer infra only |

**Forbidden as silent default:** “Upload your sims so we can fine-tune” without tier, DPA, and retention terms.

---

## 4. Customer intake schema (v1)

```text
CustomerBounds {
  customer_id / engagement_id
  regime_template_id          # e.g. contact_force_v1, thermal_panel_v1
  use_mode                    # design_sweep | control_loop | hybrid

  requirements[] {
    id, quantity, relation, value, unit, notes?
  }

  constraints[] {
    id, quantity, relation, value, unit, severity  # hard | soft
  }

  envelope {
    inputs[]  { name, min, max, unit, distribution_hint? }
    context[] { name, min, max, unit }
    exclusions[]?
  }

  latency_class?              # L1_interactive | L2_batch | L3_control_rate
  export_class?               # onnx | other_approved
  escalation_policy?          # outside envelope → stop | call_hifi | human

  data_policy                 # no_customer_data | aggregate_only | private_challenge | customer_adapt_only
  commercial_tier             # trial | catalog | bounds_sku | adapt_license | reverify | sponsored_* | private
  adapt_intent?               # none | customer_side | carbon_assisted
}
```

**Validation:** ≥1 numeric hard constraint or requirement; closed envelope on inference inputs; known `regime_template_id` or cold-start quote; free-text alone insufficient for battery parameterization.

---

## 5. Procedure (end-to-end)

```text
INTAKE → validate CustomerBounds
MAP bounds → PB-INV targets, ADV boxes, PB-ROLL/LAT depth, PB-ESC
REGIME MATCH (Landscape)
  sufficient evidence → OFF-SUBNET fulfillment (§6)
  thin evidence → SPONSORED CHALLENGE or cold-start quote
SYNTHESIZE recipe (effects, not champion weight dump)
CONTROLLED RETRAIN (fresh procedural draws; seed policy)
PRODUCT BATTERY (bounds-parameterized)
GROUNDING GATE → DELIVER closed SKU
OPTIONAL: Adapt license (§7) → customer-side retrain → RE-QUALIFY for Certified label
```

### 5.1 Bounds → battery mapping

| Customer field | Battery effect |
|----------------|----------------|
| Requirements / hard constraints | PB-INV targets and thresholds |
| Envelope | Stress/ADV domain |
| use_mode = control_loop | Stronger PB-ROLL + stricter PB-LAT |
| use_mode = design_sweep | Stronger PB-INV budget |
| escalation_policy | Mandatory PB-ESC |
| export_class | PB-ART format |

Lean subnet scoring is **not** rewritten by one customer’s bounds unless they fund a challenge that defines a regime.

---

## 6. On-subnet vs off-subnet fulfillment

Same grounding gate for full commercial SKUs. Difference is how evidence is obtained and paid for.

### 6.1 Off-subnet (intelligence already sufficient)

**When:** Landscape support density/stability meet policy; generators/gates/PB templates exist; bounds evaluable; legal accepts `data_policy`.

**What:** OpCo synthesize → retrain → full PB → ship. No new emissions challenge required.

**Why allowed:** Subnet’s job is to grow verified strategy intelligence. Once it exists, forcing every sale through live emissions is unnecessary. Buyers pay for **bounded, battery-passed artifacts**.

### 6.2 On-subnet sponsored challenge

**When:** Evidence thin; customer wants ongoing network search; novel regime; tier is challenge-sponsored.

**What:** Challenge brief + lean cards → Landscape update → graduate still needs PB (sponsor may add tests). Sponsor gets licensed graduate under contract.

### 6.3 Decision rule

```text
if landscape.sufficient(regime) and bounds.evaluable:
    prefer OFF_SUBNET_FULFILLMENT
elif customer.funds_challenge or evidence_thin:
    SPONSORED_CHALLENGE
else:
    COLD_START_QUOTE or DECLINE
```

---

## 7. Customer-side adapt & re-qualification (optimal product design)

### 7.1 Principle

> Selling “add your data and retrain” is smart **only if** adapt runs where the data already lives and **certification is explicit**.

Unconstrained retrain while still marketing the original PB pack is **not** allowed.

### 7.2 Product layers

| Layer | What customer gets | Cert status |
|-------|--------------------|-------------|
| **A. Certified specialist** | Artifact + recipe + PB pack + envelope | Valid **as shipped** |
| **B. Adapt kit (license)** | Train/adapter scripts or API, constraint hooks, local smoke gates | Runs on **customer infra**; Carbon need not hold data |
| **C. Re-qualification** | Re-run product battery after adapt (customer GPU or paid Carbon job) | **New** PB pack → may restore `Certified` |

### 7.3 Rules

1. Material retrain/fine-tune **voids** the previous PB cert for performance claims.  
2. SKU labels:  
   - `Certified` — current PB pass under stated bounds  
   - `Adapted (customer)` — lineage to a certified base; **no** Carbon performance claim until re-PB  
3. Prefer **constrained adapt** (frozen physics heads / small adapters, constraint losses on, local gate smoke) over free full retrain when templates allow.  
4. Envelope expansion requires new ADV/INV domain and a new battery — not a silent widen.  
5. Default adapt path is `customer_adapt_only` (data never sent to Carbon).

### 7.4 Carbon-assisted adapt (optional high tier)

Only under contract: data residency, retention, deletion, audit. Still requires re-PB for `Certified`. Not the default offer.

### 7.5 Why this is optimal

| Goal | How this design hits it |
|------|-------------------------|
| Customer confidence to try | No data-security program for default SKU |
| OEM need to specialize | Adapt kit on their side |
| Protect meaning of “Carbon specialist” | Cert resets until battery |
| Revenue | Re-verify and sponsored tiers stay valuable |
| Incentives | Purchase still does not buy emissions |

---

## 8. Deliverable package

| Asset | Role |
|-------|------|
| Deployable artifact | Runs in their tool / loop |
| Certified recipe | Provenance / adapt start |
| Model Card + PB report | Review evidence |
| Envelope + escalation | Printed validity domain |
| License + update channel | Terms; template drift handling |
| Adapt kit (if purchased) | Customer-side retrain under §7 |

**Allowed claim:** validated against customer-stated requirements, constraints, and envelope under Carbon’s product battery for regime template X.  
**Forbidden without separate program:** system/flight/safety certification; “replaces customer V&V”; unbounded operational authority.

---

## 9. Confidence & adoption ladder

Specialists earn a **trial**, not automatic standardization.

| Stage | Buyer action | Carbon offer |
|-------|--------------|--------------|
| **Try** | Non-critical regime, shadow vs hi-fi | Trial / catalog / small bounds SKU; `no_customer_data` |
| **Use** | Design sweep or advisory control inside envelope | Bounds SKU + evidence pack |
| **Adapt** | Specialize on internal data | Adapt license; label `Adapted (customer)` |
| **Depend** | Production-adjacent reliance | Re-verify → `Certified`; tighter SLA; optional private tier |

Sales must not skip the ladder. Field failures outside envelope are escalations, not “model betrayal,” if PB-ESC was honest.

---

## 10. Go-to-market strategy (optimal)

### 10.1 What we sell (SKU ladder)

| SKU | Contents | Data | Price posture (illustrative) |
|-----|----------|------|------------------------------|
| **Trial** | Limited envelope, full honesty on limits, short license | No customer train data | Low / design-partner |
| **Catalog specialist** | Regime template, generic bounds, PB pack | No customer train data | List |
| **Bounds specialist** | PB parameterized by their requirements/constraints/envelope | No customer train data (default) | Project |
| **Adapt license** | Kit + lineage to certified base | Customer infra only | Add-on subscription / seat |
| **Re-verify** | PB re-run after adapt or template drift | Optional; prefer customer-run harness | Per job or retainer |
| **Sponsored challenge** | Network search on regime family | Per tier (open → private) | Challenge fee + graduate license |
| **Private / air-gap** | Sealed pack, residency, no-retain | Contract-only | Program |

### 10.2 Who to sell first

| Priority | Buyer | Why |
|----------|-------|-----|
| 1 | Methods groups / digital-eng leads with authority to pilot | Care about evidence packs |
| 2 | Suppliers under requirements-driven design | Bounds language matches RFQs |
| 3 | Robotics / autonomy control teams (narrow plant maps) | Latency + envelope story |
| Later | Full program primes for fleet-wide dependency | After repeated Try→Use proof |

Avoid leading with “replace Ansys.” Lead with **faster search inside a declared envelope, with a battery the scoreboard does not require.**

### 10.3 Motion

1. **Land** — trial or catalog on a template Carbon already covers.  
2. **Prove** — customer shadow test on their data (their side).  
3. **Bound** — paid bounds SKU for a real requirements set.  
4. **Expand** — adapt license when they must fit internal distributions.  
5. **Lock** — re-verify retainer; sponsored challenges only for net-new regimes.  
6. **Protect** — never discount away PB; never let purchase touch emissions.

### 10.4 Messaging (external)

- Scoreboard ≠ product.  
- Input bounds, not your secret archive.  
- Specialist is valid inside the printed envelope.  
- Adapt on your side; certification is earned again, not inherited forever.  
- Off-subnet delivery when intelligence exists is a feature (speed), not a bypass of proof.

### 10.5 What not to do

- Sell unlimited certified retrain on customer data in Carbon cloud as the default.  
- Imply Phase-0 catalog SKUs are production autonomy stacks.  
- Use customer pilots as free subnet challenge design without a sponsored agreement.  
- Open dual egress (full SKU on miner paths).

### 10.6 Success metrics (commercial)

| Metric | Intent |
|--------|--------|
| Trial → paid bounds conversion | Offer clarity |
| % default SKUs with `no_customer_data` | Security-friendly motion |
| Adapt attach rate | OEM fit |
| Re-verify attach after adapt | Cert integrity + revenue |
| Off-subnet vs sponsored mix | Landscape maturity |
| Zero certified claims post-adapt without new PB | Trust |
| Zero emissions coupling to revenue | Incentive integrity |

---

## 11. Incentive and trust boundaries

| Rule | Statement |
|------|-----------|
| No pay-to-compete | Purchase / off-subnet work / adapt license does not buy emissions |
| No lean bypass | Commercial SKUs still require product battery |
| No full SKU on miner API | Dual egress unchanged |
| No teacher distillation | Effects + retrain + PB |
| No silent data ingest | Default `no_customer_data` |
| No inherited cert after adapt | Re-qualify or label `Adapted (customer)` |

---

## 12. Worked micro-example (gripper / contact)

**Intake:** Hold without drop; F ≤ F_max; payload and surface envelope; control-rate latency; `no_customer_data`.

**Match:** Contact template evidence sufficient → **off-subnet** bounds SKU.

**Build:** Effect-merged recipe; controlled retrain; PB with heavier/slicker ADV, control-rate LAT, ESC outside envelope.

**Deliver:** `Certified` force map + pack. Customer shadows on their cells.

**Later:** Adapt license on their logs → `Adapted (customer)` → paid re-verify → `Certified` again under same or updated bounds.

---

## 13. Thesis

Specialists are **bounds-conditioned, evidence-backed products**. The default path does not consume proprietary customer trajectories. Customers may adapt on their own infrastructure; Carbon’s name on performance holds only while a product battery says so.

The subnet accumulates verified intelligence. When that intelligence is dense enough, **commerce may run off-subnet** without apology. When it is not, **sponsored search** buys new evidence. Go-to-market follows buyer confidence: try without data drama, buy bounds with proof, adapt locally, re-qualify to depend.

---

*Canonical procedure for customer-bounds intake, default no-sensitive-data posture, customer-side adapt/re-qualify, on- vs off-subnet fulfillment, and GTM ladder. Gauntlet mechanics remain defined in Specialist_Bank.md.*
