# Industry Validation

External signals that corroborate Carbon’s verification thesis: **expensive engineering decisions need auditable truth; agentic generation multiplies the need for independent exams.**

Use as mechanism analogy and timing evidence — not identity claims (“X reinvented Carbon”).

## TL;DR

**What this is:** External industry and research signals that support Carbon’s thesis — not competitor claims and not “X reinvented Carbon.”

**Core thesis these sources reinforce:** expensive engineering decisions need auditable truth; agentic generation multiplies the need for **independent exams**.

**How to use this doc**
- Mechanism analogy and timing evidence for pitches and diligence
- Map each source to a specific Carbon design choice (gates, dual path, product bar)
- Do **not** overclaim identity with OpenAI, Ansys, NVIDIA, or M&A stories

**Strongest threads:** validation is the bottleneck once agents write code; hybrid sim + surrogate is the realistic pattern; capital is consolidating around multiphysics and Physical AI.

---

## OpenAI Field Report (July 2026)

**Source:** [*Scientific computing in the age of agentic AI: an exploratory field report*](https://cdn.openai.com/pdf/scientific-computing-in-the-age-of-agentic-ai-an-exploratory-field-report.pdf) — OpenAI + collaborators; eight real case studies of LLM coding agents on scientific software (primarily life sciences).

**Scope discipline:** Not a PDE paper, neural-operator paper, or physics-oracle paper. A field report on *coding agents* refactoring, optimizing, and rewriting scientific software.

### The paper in one sentence

Coding agents can accelerate maintenance, optimization, and rewrites of scientific software — but **validation and scientific correctness remain the bottleneck**, agents cannot reliably self-verify, and human effort concentrates on defining acceptance criteria and verification harnesses.

### What it supports in Carbon’s thesis

| Paper finding | What it supports in Carbon | Strength |
|---------------|----------------------------|----------|
| Validation / scientific correctness is the bottleneck once agents handle implementation | Verification is the scarce institutional function as agentic systems scale | **Strong** |
| Agents are strong at execution where correctness is well-defined; weak where it is not | Hard gates, Score Packs, and external references beat “agent said it passed” | **Strong** |
| Agents produce plausible but incorrect output; self-assessment is unreliable | Independent exam (validator-owned data + gates) rather than producer self-report | **Strong** |
| Human effort shifts to acceptance criteria and verification harnesses | Product battery + Validation Dossier + Score Pack as institutional harness | **Strong** |
| Domain is mostly life-sciences software, not industrial PDE surrogates | Analogy for agentic loops — not a direct PDE/NO result | **Medium (scope)** |

**How to cite in a pitch:** “Even when agents write the code, the scarce resource is verification. Carbon is built as that verification layer for physics surrogates.”

---

## Platform and capital signals (Physical AI / multiphysics)

Use as **timing and category** evidence:

- Major engineering-software and compute platforms are investing in Physics AI, surrogates, digital twins, and agentic engineering workflows.
- Large M&A and platform moves across design, simulation, and analysis show multiphysics and simulation-adjacent software remaining strategic.
- Core CAE and broader simulation software markets are multi-ten-billion-dollar categories — useful as context for *where physics models sit*, not as Carbon’s TAM claim.

**Discipline:** These signals support “the world is building Physical AI and needs trust.” They do **not** prove Carbon’s product is adopted.

---

## Hybrid simulation + surrogate (industry pattern)

Serious vendors describe **hybrid** workflows: screen with a fast model, promote candidates to high-fidelity solvers. That matches Carbon’s stance:

- High-fidelity solvers remain ground truth
- Learned maps compress exploration inside an envelope
- Verification defines where the map is allowed to be used

---

## What this appendix is not

- Not a competitor teardown
- Not a claim that any named company is building Carbon
- Not a substitute for Generator Validation dossiers or live Score Packs

---

*Keep this document short and current. Prefer primary sources and conservative paraphrases over marketing language.*
