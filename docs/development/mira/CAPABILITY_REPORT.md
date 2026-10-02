# Autoscience Mira: integration capability report

**Status (2026-10-01):** integration mode **repository/artifact handoff,
planned**; Autoscience's own site now confirms PR-based delivery, hosted or
on-prem, but nothing account-level is verified. Live Mira execution is **BLOCKED** until Autoscience
supplies verified answers to the questions below and the owner completes the
spending grant. The provider-independent controller, the fake provider and the
Mira adapter (which refuses every call) are built; see `README.md`.

Mira is **Autoscience Mira, https://www.autoscience.ai/mira** (owner answer
2026-10-01). No other product named Mira is meant, and no vendor package was
installed.

## How this report was made, and its limits

- **Update 2026-10-01 (owner opened network access):** the lead fetched
  `www.autoscience.ai` (`/`, `/mira`, `/get-started`, `/carl`) with `curl` and
  read the text in the site's page scripts (`/components/HeroMorph.js`,
  `ConceptB.js`, `Outcomes.js`, `Pages.js`). Those **primary public** statements
  are in the next section. `/pricing`, `/docs`, `/security`, `/terms`, `/privacy`
  and `/about` return 404.
- Earlier rows came from web search results (secondary sources), gathered
  while the site was blocked.
- No form was submitted, no account was created, no one was contacted and no
  API was called.
- **PUBLIC_PRIMARY** means "stated on Autoscience's own site". It is marketing
  copy, not vendor documentation and not account-specific evidence, so no §3
  question below is marked VERIFIED on its strength alone.

## What Autoscience's own site states (primary, public)

| Item | Status | Source (quoted) |
|---|---|---|
| Hosted deployment on Autoscience's GPUs, delivering PRs | PUBLIC_PRIMARY | "In the cloud. Your model, your data, and our GPUs. Start receiving PRs the same week." (`/mira`, `ConceptB.js`) |
| On-premises deployment | PUBLIC_PRIMARY | "On your infra. Full on-prem deployment. Your data never leaves your network. Same agents, same results." (`ConceptB.js`) |
| Workflow: papers → experiments on the customer's model → verification on the customer's eval → PRs | PUBLIC_PRIMARY | "Sees every paper." "Experiments on your model. Mira spins up isolated training runs, tracks loss curves, compares against your baseline." "Verifies on your eval." "Ships improvements as PRs." (`HeroMorph.js`) |
| The customer's verifier, not the agent, decides | PUBLIC_PRIMARY | "No agent decides what 'better' means. Your eval set, your metrics, your significance threshold — deterministic pass/fail." "agent proposes, verifier decides" (`HeroMorph.js`, `ConceptB.js`) |
| What a PR carries | PUBLIC_PRIMARY | "Nothing merges until it beats your baseline on your verifier. Each PR ships with the run logs, ablations, and a writeup your team can audit." (`HeroMorph.js`) |
| Access route | PUBLIC_PRIMARY | `/get-started` form: name, email, company, role, interest, message; posts to `/api/qualify`, then offers a Calendly booking (`Pages.js`) |
| No public pricing, documentation, security or terms pages | PUBLIC_PRIMARY (absence) | those paths return 404 |

**Fit with Carbon.** "Agent proposes, verifier decides" is the same authority
split as Carbon's invariant 7.9 and 7.10: Mira may propose constructions and
attacks, while Carbon's evaluator and reference decide. The PR-with-logs
delivery matches the planned repository/artifact handoff mode.

## What the public material states (secondary sources)

| Item | Status | Source |
|---|---|---|
| Mira is an ML research agent by Autoscience Institute (San Mateo) | PUBLIC_SECONDARY | search result titled "Mira - Machine Learning Research Agent" (autoscience.ai/mira); R&D World |
| It reads new research papers (the summary says 1,200+ a week), matches techniques to a customer's repositories and implements improvements in the customer's production ML models | PUBLIC_SECONDARY | search summaries of autoscience.ai/mira |
| It is described as deployed into customer codebases and shipping improvements as code changes | PUBLIC_SECONDARY | lead's vendor research, 2026-10-01 |
| A sister agent, Carl, generates hypotheses and writes papers | PUBLIC_SECONDARY | search summaries |
| Autoscience raised a USD 14M seed round led by General Catalyst (March 2026) | PUBLIC_SECONDARY | R&D World, TAMradar, Dealroom |
| Access is early access, by contacting the Autoscience team (Get Started form, https://www.autoscience.ai/get-started) | PUBLIC_SECONDARY | lead's vendor research |
| Pricing, documentation, API, SDK, CLI and MCP details are not public | PUBLIC_SECONDARY (absence) | lead's vendor research |

## The handoff §3 questions

No row is VERIFIED. Four are PARTIAL from Autoscience's own public site (2026-10-01); the rest are **UNVERIFIED**. "Carbon's need" is what the controller requires
before `MiraProvider` may be replaced by a live adapter.

| Question | Status | Carbon's need |
|---|---|---|
| How do we launch Mira? (hosted, local, customer cloud) | PARTIAL (public primary: hosted on Autoscience GPUs, or on-prem; launch mechanics unverified) | A documented deployment we can point at a Carbon-owned disposable workspace |
| How do we supply tasks? (API/SDK/CLI schema or repository workflow) | PARTIAL (public primary: works on the customer's repository and eval, delivers PRs; task submission and idempotency unverified) | A documented task submission with an idempotency key, or a repository workflow we drive |
| Can Mira use Carbon tools? (MCP or another mechanism) | UNVERIFIED | MCP stdio client support, or a documented tool mechanism; only campaign-scoped access would be offered |
| Where do experiments execute? (workers, network, dependencies, compute) | PARTIAL (public primary: "isolated training runs" on Autoscience GPUs or on-prem; worker ownership, egress and whether Carbon's runner can replace its compute unverified) | Worker ownership, egress, and whether Mira's own compute can be replaced by Carbon's runner |
| Can we export its work? (source, recipes, artifacts, logs, dependency versions, usage) | PARTIAL (public primary: each PR ships with run logs, ablations and a writeup; dependency versions and usage export unverified) | Full export of each run, including logs and dependency versions |
| How do we stop it? (cancellation, outstanding jobs, recovery) | UNVERIFIED | Cancel by run id, confirmation that every worker stopped, recovery after disconnect |
| Can we limit spending? (billing units, concurrency, quotas, caps, billing delay) | UNVERIFIED | A per-run worst case and usage reporting; the controller enforces caps itself |
| Can we separate campaigns? (session memory, workspaces, retention, access) | UNVERIFIED | No memory shared across the three research roles; deletion on request |
| Can we reproduce its configuration? (agent/model/version identifiers, updates) | UNVERIFIED | A version identifier per run and notice of updates |
| Can we conduct this red-team work? (testing scope on Carbon-owned disposable infrastructure) | UNVERIFIED | Written permission for adversarial construction research against Carbon's own systems |
| Can customers receive its output? (rights to use, distribute, rebuild, modify) | UNVERIFIED | Rights for Carbon and its customers to use, redistribute, rebuild and modify generated artifacts |

## Integration mode

| Mode | Status |
|---|---|
| Direct MCP | Not chosen: MCP support is unverified |
| Documented tool adapter | Not chosen: no documented tool mechanism |
| **Repository/artifact handoff** | **Working mode (planned; the PR-based delivery is now stated on Autoscience's own site, but the account-level workflow is still unverified).** Mira proposes code or recipes in an allowlisted research checkout; a Carbon runner imports and executes them; human interventions are recorded |
| Unavailable | The adapter's behaviour today: `MiraProvider.capabilities()` reports the planned mode with `verified=False`, so the controller refuses to dispatch, and every operation raises `ProviderUnavailable` |

No endpoint has been invented. OpenAI-compatible inference access, if offered,
would not be treated as the Mira research agent.

## Ready-to-send inquiry (for the owner to send)

> **Subject:** Early-access inquiry: Mira for internal model-construction research at Carbon
>
> Hello Autoscience team,
>
> Carbon (carbonphysics.ai) builds and evaluates fast physical surrogate
> models. We would like to evaluate Mira for three internal development jobs on
> Carbon-owned infrastructure: (1) developing model-construction recipes within
> a declared permission profile, (2) adversarial research that tries to break
> our construction, evaluation and disclosure boundaries, and (3) reviewing and
> improving a fixed design-optimization search. Our own controller supervises
> every run, enforces spending limits and keeps evaluation material outside the
> agent's workspace.
>
> Before we start, could you tell us, ideally with documentation:
>
> 1. **Launch:** is Mira hosted, local or deployable in a customer cloud?
> 2. **Tasks:** how are tasks supplied (API, SDK, CLI, or a documented
>    repository workflow), and is there an idempotency key or equivalent?
> 3. **Tools:** can Mira act as an MCP client (stdio), or use another
>    documented tool mechanism?
> 4. **Execution:** where do Mira's experiments run, who owns the workers, what
>    network and dependency access do they have, and can we supply our own
>    compute?
> 5. **Export:** can we export each run's source code, recipes, artifacts,
>    logs, dependency versions and usage?
> 6. **Stopping:** how is a run cancelled, how do we confirm every worker has
>    stopped, and how are outstanding jobs recovered after a disconnect?
> 7. **Spending:** what are the billing units, concurrency limits, quotas and
>    hard caps, and how long is the billing delay?
> 8. **Separation:** can we run separate campaigns with no shared session
>    memory or workspace, and what are your retention and access controls?
> 9. **Reproducibility:** which agent, model and version identifiers are
>    available per run, and how are updates announced?
> 10. **Red-team scope:** may Mira be used for adversarial testing of our own
>     systems on disposable infrastructure we own?
> 11. **Rights:** may we and our customers use, redistribute, rebuild and
>     modify the artifacts Mira generates?
>
> We would also welcome pricing for a small pilot: three short sessions for
> an end-to-end smoke test, then about three adversarial and one construction
> session.
>
> Thank you,
> Carbon
