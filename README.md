<img width="1412" height="62" alt="image" src="https://github.com/user-attachments/assets/1d63753c-a391-44d9-a4b8-ee667545bcae" /># Carbon

**A Bittensor subnet for verifying physics-based AI models**

Carbon pays miners to propose better ways to train fast physics models — and pays only when those methods survive an independent exam the miner does not control.

---

## The Problem

High-fidelity simulation is accurate but too slow for large design spaces and real-time control.  
Pure machine-learning surrogates are fast but often break conservation laws, fail outside their training data, or look good on a leaderboard and fail in use.

Engineering teams will not bet expensive decisions on a model because someone claimed a low test loss. They need **evidence the model still behaves under stress** — and a path from research competition to something they can actually deploy.

---

## What Carbon does

Carbon runs a **competition to find training methods** for neural operators (models that learn entire families of physical simulations, not single cases).

1. **Miners** submit a training strategy (and optional model artifacts).  
2. **Validators** retrain and evaluate on data the miner never saw, with **hard physics checks**. Fail a check → score zero.  
3. **Emissions** follow that independent score — not self-reported metrics.  
4. As the network matures, verified results can feed **better starting points for the next round of search** and, separately, **stronger commercial models** that pass harder product tests.

Discovery stays cheap. Anything sold as a product has to clear a higher bar than “won a leaderboard row.”

---

## Why This Design

| Usual failure | Carbon’s answer |
|---------------|-----------------|
| Miner grades their own homework | Validators run the exam on hidden, freshly generated data |
| Good average error, bad physics | Hard gates on conservation and residuals — fail closed |
| Overfit to a fixed public benchmark | Train, eval, and stress data are separated; stress is procedural |
| Leaderboard model treated as shippable product | Competition score ≠ commercial qualification |
| No memory across rounds | Over time, verified outcomes can inform search without giving away the exam |

The scarce layer is not “another fast model.” It is **credible verification** as agentic and automated training scales.

---

## How a round works (simple)

1. A **challenge** defines a physics regime and what “good” means (accuracy under stress, physical consistency).  
2. A miner submits a **strategy** — how to train (architecture choices, losses, schedules, etc.).  
3. Validators **regenerate evaluation data**, train under the submitted strategy where required, and run **physics gates + held-out and stress tests**.  
4. A public, challenge-specific **scoring rule** turns results into a score. Critical failures zero the submission.  
5. Scores drive **on-chain weights / emissions**.

Details of formulas, configs, and phase roadmap live in the technical docs — not required to understand the subnet.

---

## How miners iterate without burning a full train every time

Competing on training strategy only works if people can **try ideas quickly**. Carbon is built so miners (or their agents) can run a tight loop **before** a full submission:

1. **Read the latest public insight from the challenge leader** — a **noisy, delayed summary** of what worked (not the full winning recipe or weights). Enough to steer search; not enough to copy the exam or clone the winner.  
2. **Estimate** how a candidate strategy might score, using that insight plus cheap proxies (short runs, surrogates of the last verified outcome, or local light trains).  
3. **Optionally run a light local train** gated by the same *kinds* of checks the validator cares about — different data than the real exam, so the network stays honest.  
4. **Submit only when the loop looks promising.** Full validator scoring is still the only path to emissions. You can submit with **no** local training; paid or heavy local train is optional, not required.

That loop is meant for **humans and agents**: show up, pull the current leader signal, propose variants, estimate, refine, submit. Low friction on purpose — so search scales — without turning the leaderboard into a copy-paste contest or leaking the real evaluation data.

Validators always grade the same way: hidden data, hard physics checks, public scoring rules. Miner-side estimation never replaces the exam.

---

## Market and Product

"Expensive engineering decisions need auditable, reconstructible truth; fake benchmarks don’t move a chief engineer."

**Who pays**  
Teams that already run simulation and are hitting cost or latency walls: design exploration, real-time or hardware-in-the-loop response, uncertainty screening, and hybrid setups where a fast model sits next to a classical solver. The buyer is not “crypto.” It is a chief engineer or SciML lead who will not accept a fake benchmark.

**What we sell**  
The product is **envelope qualified models and evidence**:

| Offering | What the customer gets |
|----------|-------------------------|
| **Standard specialist** | A model trained for a public regime, with evaluation history and license terms |
| **Sponsored open challenge** | They fund a physics regime; the network competes; results stay broadly usable |
| **Sponsored licensed challenge** | Same competition, tighter IP and distribution terms |
| **Private challenge** | Highest control and cost — only when trust and process exist |

Price and privacy go up together. Early revenue is expected from **sponsored challenges and licensed specialists**, not from charging miners to play.

**How we aim development**  
Build order follows what a skeptical buyer would ask:

1. **Make the exam real** — one challenge, honest scoring, reproducible cards. No product claims before this.  
2. **Prove the loop** — miners can compete; validators can run; scores mean something under stress.  
3. **Only then productize** — harder qualification for anything sold; clear separation from competition rank.  
4. **Grow regimes that match demand** — fluids, structures, and multiphysics paths that map to CAE and digital-twin budgets, including sponsored regimes when partners show up.  
5. **Stay compatible with the tools people already use** — export paths into common ML and simulation stacks; do not try to replace Ansys or the GPU vendor.

We do **not** prioritize dashboards, multi-challenge sprawl, or “AI agent theater” ahead of a trustworthy first exam. Market fit is earned by **models someone can defend in a design review**, not by subnet narrative alone.

---

## What the network learns over time

- **Search signal** — which training ideas actually survive stress  
- **Qualified models** — for design exploration, real-time response, uncertainty, or hybrid solver loops  
- **Sponsored regimes** — organizations fund challenges and receive models under agreed terms  

Early phases focus on getting the exam right. Product layers expand only after that foundation holds.

---

## Who this is for

| Audience | Why care |
|----------|----------|
| **Miners / agents** | Compete on strategy quality; iterate with leader insights and cheap estimates before full submit |
| **Validators** | Run a defined evaluation pipeline; secure the integrity of scores |
| **Engineering / SciML teams** | Models with reconstructible evaluation history, not only a chart |
| **Sponsors** | Fund a physics regime; get specialists under open, licensed, or private terms |

---

## Stack position (one sentence)

GPU vendors and CAE platforms own engines and tools. Carbon owns **decentralized discovery of training methods plus independent verification** — with a clear line between competition results and anything offered as a product.

---

## Current status

**Phase 0:** foundations and offline proof-of-concept — strategy → seeded data → train → physics checks → score → evaluation card (`poc/`).

```bash
git clone https://github.com/jbequ5/Carbon--Decentralized-Physics-AI.git
cd Carbon--Decentralized-Physics-AI
pip install -e .
./poc/scripts/smoke.sh
```

---

## Technical documentation

| Document | Contents |
|----------|----------|
| [SPEC.md](./SPEC.md) | Full protocol |
| [appendices/Scoring.md](./appendices/Scoring.md) | Scoring rules |
| [appendices/Launch_Bar.md](./appendices/Launch_Bar.md) | Readiness checklist before public priors |
| [appendices/Landscape_Agent.md](./appendices/Landscape_Agent.md) | Knowledge / routing architecture |
| [appendices/Specialist_Bank.md](./appendices/Specialist_Bank.md) | Product qualification path |
| [appendices/Use_Cases_by_Phase.md](./appendices/Use_Cases_by_Phase.md) | Use cases by maturity |
| [appendices/POC_Burgers_FNO.md](./appendices/POC_Burgers_FNO.md) | First PoC build guide |
| [docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md](./docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md) | Data and verification design |
| [appendices/Compute_Optimization.md](./appendices/Compute_Optimization.md) | Compute strategy |
| [appendices/Data_Management.md](./appendices/Data_Management.md) | Seeds, train ≠ eval |
| [appendices/JAX_Optimization.md](./appendices/JAX_Optimization.md) | Validator JAX efficiency |
| [appendices/Implementation.md](./appendices/Implementation.md) | Gates, toolkit, SciML |
| [appendices/Operations.md](./appendices/Operations.md) | Deploy / ops |

---

*Carbon: independent exams for physics-model training strategies — cheap to compete, hard to fake, and strict about what gets called a product.*
