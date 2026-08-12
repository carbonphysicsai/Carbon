<img width="1412" height="62" alt="image" src="https://github.com/user-attachments/assets/1d63753c-a391-44d9-a4b8-ee667545bcae" />

# Carbon

**A Bittensor subnet for verifying physics-based AI models**

Carbon pays miners to find better ways to train fast physics models. It only pays when those methods survive an independent exam the miner does not control.

---

## The Problem

High-fidelity simulation is accurate but too slow for large design spaces and real-time control.  
Pure machine-learning surrogates are fast but often break conservation laws, fail outside their training data, or look good on a leaderboard and fail when you actually try to use them.

Engineering teams will not bet expensive decisions on a model just because someone claimed a low test loss. They need evidence the model still behaves under stress, and a clear path from research competition to something they can actually deploy. Physics breakdowns are expensive and not optional. A chief engineer needs something auditable and reconstructible to defend a model in a design review.

---

## What Carbon Does

Carbon runs a competition to find training methods for neural operators (models that learn entire families of physical simulations, not single cases). We build off open tooling (NVIDIA PhysicsNeMo, SciML/Julia Labs, and others). Once trained and verified, the models are cheap and fast for design exploration, real-time control systems, agentic solving, and any use case that needs trustworthy next-state prediction.

1. **Miners** submit a training strategy (and optional model artifacts).  
2. **Validators** retrain and evaluate on data the miner never saw, with hard physics checks. Fail a check → score zero.  
3. **Emissions** follow that independent score — not self-reported metrics.  
4. As the network matures, verified results can feed better starting points for the next round of search and, separately, stronger commercial models that pass harder product tests.

Traditional neural operators are dominated by accuracy-driven objectives. They may solve overfitting, but the objective still drives them toward accuracy and learning data, which is why they struggle with real physics in deployment. Carbon changes the optimization target: physics gates, fidelity, and model robustness are weighted more than pure training loss accuracy in the final score. We are driving miners at training strategies that survive a different objective, and learning from them. That is the valuable work Carbon is paying for and that the validators are pressure-testing. It is plausible that the Pareto front of methods under hard physics + stress differs from those under pure accuracy. Bittensor miners are the right tool for finding it.

The training data and evaluation criteria are generated in real time, seed-triggered, impossible for the miners to know ahead of time, challenge-specific, fully auditable, and verified against real physics and real simulation tools. Every training run generates a Model Card that captures how it was trained, how accurate it was, and how it scored on the real physics testing. That data is used to return value to miners, improve the evaluation, improve challenge design, and develop industry-deployable models.

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

The scarce layer is not another fast model. It is credible verification as agentic and automated training scales. Physics is well defined and perfectly suited for the Bittensor evaluation and compounding intelligence loop; this is math. Validation can be independent of the incentivized producer, and agentic search can scale discovery without a single lab owning both the training and the answer key. Bittensor is the value creation engine for Carbon. The open source and auditable training and evaluation mechanism is exactly what an engineer needs to defend the deployment of these physics models in high-risk environments.

---

## How a Round Works (simple)

1. A challenge defines a physics regime and what “good” means (accuracy under stress, physical consistency).  
2. A miner submits a strategy — how to train (architecture choices, losses, schedules, etc.).  
3. Validators regenerate evaluation data, train under the submitted strategy where required, and run physics gates + held-out and stress tests.  
4. A public, challenge-specific scoring rule turns results into a score. Critical failures zero the submission.  
5. Scores drive on-chain weights / emissions.

Details of formulas, configs, and phase roadmap live in the technical docs — not required to understand the subnet.

---

## Agent Friendly MCP Miner Solving Loop

Competing on training strategy only works if people can try ideas quickly. Carbon is built so miners (or their agents) can run a tight loop before a full submission:

1. Read the latest public insight from the challenge leader — a noisy, delayed summary of what worked (not the full winning recipe or weights). Enough to steer search; not enough to copy the exam or clone the winner.  
2. Estimate how a candidate strategy might score, using that insight plus cheap proxies (short runs, surrogates of the last verified outcome, or local light trains).  
3. Optionally run a light local train gated by the same kinds of checks the validator cares about — different data than the real exam, so the network stays honest.  
4. Submit only when the loop looks promising. Full validator scoring is still the only path to emissions. You can submit with no local training; paid or heavy local train is optional, not required.

Mining is deliberately agentic auto-research. The agent-friendly front end (MCP) receives noisy feedback from the current challenge winner’s strategy and provides estimated scoring impacts of local changes, allowing AI solving at scale. This lowers the barrier to entry, raises the quality of submissions, and leverages network effects on the discovery end.

That loop is meant for humans and agents: show up, pull the current leader signal, propose variants, estimate, refine, submit. Low friction on purpose so search scales, without turning the leaderboard into a copy-paste contest or leaking the real evaluation data.

Validators always grade the same way: hidden data, hard physics checks, public scoring rules. Miner-side estimation never replaces the exam.

---

## Market and Product

"Expensive engineering decisions need auditable, reconstructible truth; fake benchmarks don’t move a chief engineer."

**Who pays**  
Teams that already run simulation and are hitting cost or latency walls: design exploration, real-time or hardware-in-the-loop response, uncertainty screening, and hybrid setups where a fast model sits next to a classical solver. The buyer is not “crypto.” It is a chief engineer or SciML lead who will not accept a fake benchmark. Challenges will progress from simple PDEs to more complex physics regimes targeted at valuable engineering fields and use cases (Aerospace, Auto, Robotics, Propulsion, UAV/Drones). The subnet is designed from day one so competition produces evidence that can later support the development of valuable commercial specialists.

**What we sell**  
The product is envelope qualified models and evidence:

| Offering | What the customer gets |
|----------|-------------------------|
| **Standard specialist** | A model trained for a public regime, with evaluation history and license terms |
| **Sponsored open challenge** | They fund a physics regime; the network competes; results stay broadly usable |
| **Sponsored licensed challenge** | Same competition, tighter IP and distribution terms |
| **Private challenge** | Highest control and cost — only when trust and process exist |

Price and privacy go up together. Early revenue is expected from sponsored challenges and licensed specialists, not from charging miners to play. Carbon will enable industry players to sponsor their own challenge targeted at their specific physics envelope. Custom surrogate development and verification without having to expose proprietary data is a valuable service for major engineering players.

The subnet team builds a knowledge graph of the Model Cards and uses them to retrain, retest, and harden specialist models built for industry deployment. That process is purposely more rigorous than the mining evaluation. We want the mine → validate → feedback loop to stay fast, but we build real thorough due diligence into the models we are selling.

**How we aim development**  
Build order follows what a skeptical buyer would ask:

1. Make the exam real — one challenge, honest scoring, reproducible cards. No product claims before this.  
2. Prove the loop — miners can compete; validators can run; scores mean something under stress.  
3. Only then productize — harder qualification for anything sold; clear separation from competition rank.  
4. Grow regimes that match demand — fluids, structures, and multiphysics paths that map to CAE and digital-twin budgets, including sponsored regimes when partners show up.  
5. Stay compatible with the tools people already use — export paths into common ML and simulation stacks; do not try to replace Ansys or the GPU vendor.

We do not prioritize dashboards, multi-challenge sprawl, or “AI agent theater” ahead of a trustworthy first exam. Market fit is earned by models someone can defend in a design review, not by subnet narrative alone.

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

GPU vendors and CAE platforms own engines and tools. Carbon owns decentralized discovery of training methods plus independent verification — with a clear line between competition results and anything offered as a product.

---

## Current status

**Phase 0:** foundations and offline proof-of-concept — strategy → seeded data → train → physics checks → score → evaluation card (`poc/`). We have a full protocol specification, scoring and data design, trustless procedural eval generation, **generator creation + Validation Dossier path**, product path, phased roadmap, and go-to-market structure in the public repo. Phase 0 (academic PDE foundation) is the launch target; we are building that now along with an offline Proof of Concept.

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
| [appendices/Generator_Creation.md](./appendices/Generator_Creation.md) | How we build generators per phase (backends, partners, fallbacks) |
| [appendices/Generator_Validation.md](./appendices/Generator_Validation.md) | Validation Dossier before a challenge goes LIVE |
| [docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md](./docs/TRUSTLESS_VERIFICATION_AND_DATA_GENERATION.md) | Seeding philosophy, trustless eval design |
| [appendices/Data_Management.md](./appendices/Data_Management.md) | Seeds, train ≠ eval |
| [appendices/Runtime_Julia_Truth_Oracle.md](./appendices/Runtime_Julia_Truth_Oracle.md) | SciML reference / adjoint oracle |
| [appendices/Landscape_Agent.md](./appendices/Landscape_Agent.md) | Knowledge / routing architecture |
| [appendices/Specialist_Bank.md](./appendices/Specialist_Bank.md) | Product qualification path |
| [appendices/Use_Cases_by_Phase.md](./appendices/Use_Cases_by_Phase.md) | Use cases by maturity |
| [appendices/POC_Burgers_FNO.md](./appendices/POC_Burgers_FNO.md) | First PoC build guide |
| [appendices/Compute_Optimization.md](./appendices/Compute_Optimization.md) | Compute strategy |
| [appendices/JAX_Optimization.md](./appendices/JAX_Optimization.md) | Validator JAX efficiency |
| [appendices/Implementation.md](./appendices/Implementation.md) | Gates, toolkit, SciML |
| [appendices/Operations.md](./appendices/Operations.md) | Deploy / ops |

---

*Carbon: independent exams for physics-model training strategies — cheap to compete, hard to fake, and strict about what gets called a product.*
