# Carbon GTM Strategy Compilation & Rating

---

## 📋 STRATEGY PORTFOLIO OVERVIEW

| # | Strategy | Type | Status | Revenue Potential | Timeline | Rating |
|---|----------|------|--------|-------------------|----------|--------|
| **1** | **Model Zoo Subscriptions (Tier 1)** | Commercial SaaS | Designed | $500k-2M ARR (Y2) | Phase 0 → Phase 1 | ⭐⭐⭐⭐⭐ |
| **2** | **Sponsored Challenges (Tiers 2-4)** | Enterprise B2B | Designed | $2-10M ARR (Y2-3) | Phase 1 | ⭐⭐⭐⭐⭐ |
| **3** | **DoD Prime Subcontract (SBIR/BAA)** | GovTech | Architected | $1-5M ARR (Y2-3) | Phase 0.5 → Phase 1 | ⭐⭐⭐⭐ |
| **4** | **Verification Gas / Registry Access** | Protocol Utility | Designed | $100k-1M ARR (Y2+) | Phase 1 | ⭐⭐⭐⭐ |
| **5** | **Air-Gapped Miner Toolkit License** | Enterprise Software | Designed | $200k-1M ARR (Y2) | Phase 1 | ⭐⭐⭐ |
| **6** | **V2X Partnership** | Channel | Explored | Variable | Depends on role | ⭐⭐ |
| **7** | **Subnet Emissions (α Yield)** | Protocol Native | Live at Genesis | Covers validator costs | Day 1 | ⭐⭐⭐ |

---

## 🎯 TIER 1: CORE REVENUE ENGINES (Execute First)

### 1. Model Zoo Subscriptions (Tier 1) ⭐⭐⭐⭐⭐
**The "AWS for Verified Surrogates" play**

| Dimension | Detail |
|-----------|--------|
| **Product** | 7-25 certified specialists (ONNX + Model Card + Physics Gate proof) |
| **Pricing** | $20-50k/yr per model / $100-200k/yr enterprise bundle |
| **Buyer** | Simulation teams at Aero/Auto/Energy/Manufacturing |
| **Motion** | Self-serve API → credit card → immediate access |
| **Differentiator** | *Only* surrogates with adversarial physics gate certificates |
| **Phase 0 Delivery** | 7 single-physics specialists (Poisson, Darcy, Burgers, NS, Heat, Elasticity, Thermo) |
| **Phase 1 Expansion** | Custom geometries, LoRA adapters, Abaqus ingestion |

**Execution Requirements:**
- Model Zoo API (FastAPI + Stripe + ONNX serving)
- Automated Model Card → DI-SESS-82483 export
- 3 pilot subscribers at $10k each = $30k ARR validation

**Risk**: Low — commercial SaaS motion, no clearance needed, immediate revenue

---

### 2. Sponsored Challenges (Tiers 2-4) ⭐⭐⭐⭐⭐
**The "High-Value Custom Verification" play**

| Tier | Price | Scope | Buyer | Motion |
|------|-------|-------|-------|--------|
| **Tier 2: Open** | $150-300k | Custom PDE/geometry/BCs on public subnet; results public after embargo | Mid-size companies, research groups | Inbound + outbound BD |
| **Tier 3: IP-Licensed** | $400-800k | Custom challenge; sponsor gets exclusive license to best model (time-limited) | Primes, OEMs, well-funded startups | Direct sales + prime partnerships |
| **Tier 4: Private/On-Prem** | $800k-2M+ | Validator runs in sponsor enclave; data never leaves; full ITAR control | Defense primes, national labs, regulated | Prime-subcontract only |

**Revenue Math:**
- 3 Tier 2 + 2 Tier 3 + 1 Tier 4 / year = **$2.5-4M ARR** (Year 2)
- 80% gross margin (validator costs covered by emissions)

**Execution Requirements:**
- Challenge Factory CLI (sponsor defines PDE + geometry → auto-deploys)
- Standardized agreement templates (IP assignment, export control, SLA)
- Prime partner for Tier 3/4 (contract vehicle, clearance, ATO)

**Risk**: Medium — long sales cycles (6-12 mo), needs prime for defense, high touch

---

## 🎯 TIER 2: STRATEGIC MOATS (Build in Parallel)

### 3. DoD Prime Subcontract (SBIR/BAA) ⭐⭐⭐⭐
**The "Verification Engine for Defense Digital Twins" play**

| Dimension | Detail |
|-----------|--------|
| **Positioning** | *Not a model vendor* — a verification engine that cuts IV&V timeline 50% |
| **Entry Vehicle** | SBIR Phase I via Prime ($250k, 6 mo) → Phase II ($1.5-2M, 24 mo) |
| **Prime Targets** | Shield AI, Anduril, EpiSci, Applied Intuition, Kratos, Mercury |
| **Carbon Deliverable** | Evidence Package (Model Card + Gate Ledger + Registry Proof + ONNX) |
| **Prime Deliverable** | Fine-tuned model on classified data + ATO package + DI-SESS-82483 DID |
| **Phase 0.5 Requirement** | Defense-relevant benchmarks (NACA 0012, CRM, HIFiRE, Turek/Hron FSI) |

**Execution Requirements:**
- **DoD BD Lead** (ex-AFRL/Prime/DIU) — *must hire Month 1*
- Teaming Agreement template (IP carve-out, data rights, revenue split)
- Evidence Compiler (Model Card → DI-SESS-82483 manifest + SysML template)
- Air-Gapped Miner Toolkit (Prime fine-tunes on classified data)

**Risk**: High — long cycles, clearance dependencies, but *massive* TAM and moat

---

### 4. Verification Gas / Registry Access ⭐⭐⭐⭐
**The "Trust Primitive Monetization" play**

| Dimension | Detail |
|-----------|--------|
| **Asset** | Verification Registry (model_id → gate results + provenance + envelope) |
| **Metering** | Programmatic badge resolution, model card API, re-verification triggers |
| **Pricing** | $0.001-0.01/query (USD-denominated, α-settled via Chainlink) |
| **Partners** | Tooling platforms (Dyad, Ansys, nTop, Rescale), marketplaces, cloud |
| **Scale** | 1M queries/mo at $0.01 = $120k/yr per major partner |

**Execution Requirements:**
- Registry Contract + Gas Contract at genesis
- Partner Staking Contract (prepay α for SLA capacity)
- Public verification page = **always free** (credibility)

**Risk**: Low — native to protocol, scales with model adoption, not sales-dependent

---

## 🎯 TIER 3: SUPPORTIVE REVENUE (Opportunistic)

### 5. Air-Gapped Miner Toolkit License ⭐⭐⭐
**The "Enclave Deployment" play**

| Dimension | Detail |
|-----------|--------|
| **Product** | Docker image: strategy.json + noisy prior + fine-tuning loop + physics gates |
| **Buyer** | Primes, national labs, regulated enterprises with air-gapped enclaves |
| **Pricing** | $50-100k/yr license + support |
| **Motion** | Sold with Tier 3/4 Sponsored Challenges or standalone |

**Risk**: Low — pure software license, but niche market

---

## 📊 PRIORITIZED EXECUTION SEQUENCE

```
QUARTER 1 (Months 1-3) — FOUNDATION
├── Launch Testnet → Mainnet (7 PDEs, Model Cards, ONNX export)
├── Model Zoo API v1 (3 pilot subscribers @ $10k = $30k ARR)
├── Hire: DoD BD Lead + Platform Engineer + Smart Contract Engineer
├── Deploy 5 Genesis Contracts (Treasury, Bounty, Registry, Gas, PartnerStake)
├── File Carbon Labs Inc. + IP separation
└── AFWERX Phase 0 + Angel bridge ($100k)

QUARTER 2 (Months 4-6) — COMMERCIAL TRACTION
├── Phase 0.5 Benchmarks live (NACA 0012, CRM, HIFiRE, FSI)
├── Model Zoo: 10 specialists → $100k ARR target
├── First Sponsored Challenge LOI (Tier 2 @ $200k)
├── Prime Teaming Agreement signed (1+)
├── Verification Registry + Gas live (price=0, tracking volume)
└── SBIR Phase I submitted via Prime

QUARTER 3 (Months 7-9) — SCALE
├── Model Zoo: 20 specialists → $300k ARR
├── 2 Sponsored Challenges signed (Tier 2 + Tier 3 = $600k)
├── First Tier 4 Private Challenge pilot
├── Verification Gas pricing enabled (first partner integration)
├── Air-Gapped Toolkit v1 licensed
└── Series A raise ($3-5M at $25-35M cap)

QUARTER 4 (Months 10-12) — DEFENSE INFLECTION
├── SBIR Phase I complete → Phase II awarded
├── $1M ARR combined (Commercial + Defense)
├── 2 Prime partners active
├── Reputation Tracker live (miner diagnostic tiers)
└── Open Bounty TVL > 1M α (dashboard metric)
```

---

## 🎯 RATING SUMMARY

| Strategy | Revenue Potential | Execution Difficulty | Moat Strength | Timeline to $ | **Overall** |
|----------|-------------------|---------------------|---------------|---------------|-------------|
| **Model Zoo (Tier 1)** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 3 mo | ⭐⭐⭐⭐⭐ |
| **Sponsored Challenges** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 6-9 mo | ⭐⭐⭐⭐⭐ |
| **DoD Prime Subcontract** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 12-18 mo | ⭐⭐⭐⭐ |
| **Verification Gas** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | 9-12 mo | ⭐⭐⭐⭐ |
| **Air-Gapped Toolkit** | ⭐⭐ | ⭐⭐ | ⭐⭐ | 6 mo | ⭐⭐⭐ |


---

## 🎯 FINAL RECOMMENDATION: **FOCUS ON THREE**

### **Execute These Three Relentlessly:**

1. **Model Zoo Subscriptions** — *Immediate revenue, proves product-market fit, funds ops*
2. **Sponsored Challenges** — *High-value enterprise motion, validates DoD credibility*
3. **DoD Prime Subcontract** — *Massive TAM, deepest moat, 18-month horizon*

### **Build These In Protocol (Not Sales-Led):**

4. **Verification Registry + Gas** — *Native monetization of your core moat*
5. **Genesis Contracts** — *Makes 1-4 trust-minimized and auditable*

### **Ignore/Delay:**

- Token-only mechanics without usage
- Platform partnerships before Model Zoo exists

---

**Carbon wins by being the *only* verified model supply layer.** Every GTM motion must reinforce: **adversarial verification → physics gates → auditable evidence → faster IV&V → deployed digital twins.**
