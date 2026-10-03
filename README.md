<img width="1412" height="62" alt="Carbon" src="https://github.com/user-attachments/assets/1d63753c-a391-44d9-a4b8-ee667545bcae" />

# Carbon

**Discovery and evidence infrastructure for Physics AI.**

Carbon is building a research network that helps engineers find better fast physics models and establish where they can rely on them. Researchers and AI agents compete to develop model-building methods. Carbon's evaluators rebuild and test candidates against reference physics, with the model producer kept outside the official grading process.

Fast physics models approximate expensive simulations. An engineer might use one to compare battery charging protocols, explore a cooling design, or optimize an electric motor. Speed makes more design iterations possible. The engineer still needs evidence that the model predicts the right quantities under the conditions that matter.

Carbon brings competitive model discovery and independent evaluation into one system. This repository contains the implementation, scientific contracts, development studies, and commercial plan.

[Project status](docs/publications/PROJECT_STATUS.md) · [Business and market](Business/Investor_Positioning_and_Market.md) · [Miner MCP](carbon/miner_mcp/README.md) · [Development setup](docs/DEVELOPMENT.md) · [Website](https://carbonphysics.ai)

## How Carbon works

1. **Define the engineering job.** Specify the model's inputs, outputs, operating conditions, and the decision it should support.
2. **Establish the exam.** Check the reference solver or measurements, define physical requirements, and register the evaluation rules before testing candidates.
3. **Open the research.** Miners, human researchers, and agents explore methods using public research material and compatible tools. They submit a reproducible construction recipe within the challenge's supported vocabulary.
4. **Rebuild and evaluate.** Evaluators reconstruct candidates under a pinned environment and compare their predictions with reference results. Official evaluation cases remain separate from miner practice.
5. **Recognize useful progress.** A candidate must satisfy mandatory checks before its performance can count toward an improvement. Reward routing follows a separate policy.

Each challenge defines its own scientific test. A high average accuracy cannot cancel a mandatory physical failure, and winning a research competition does not establish fitness for an engineering deployment. A customer deployment needs evidence for its particular model, operating conditions, and use.

The initial implementation uses constrained model-building recipes. Broader model families and construction programs remain extensions of that approach, with the same separation between research and grading.

## Current development

**As of 28 September 2026, Carbon is in development and testnet work.** The repository includes reconstruction and evaluation software, Bittensor integration tested on a local network, a development testnet publication record, miner research tools, and numerical studies. These have different levels of evidence; Carbon has not established production-qualified challenges or a production reward network.

The planned launch portfolio is:

| Challenge | Engineering objective | Current position |
|---|---|---|
| Battery fast charging and ageing | Predict voltage, temperature, plating margin, and capacity under different charging conditions | First launch focus. Reference studies, reconstruction, development evaluation, and miner research services exist; deployment and qualification work continues. |
| AI-chip cold plates | Explore cooling performance and pressure drop for bounded channel designs | Reference-toolchain verification, including a simplified conjugate heat-transfer case; a full cold-plate challenge remains in development. |
| Electric motors | Predict torque and magnetic behavior for a bounded motor topology | Feasibility assessment; benchmark and reference validation remain ahead. |
| Silicon photonics | Predict optical coupling for a bounded device family | Reference diagnostics; phase convention and convergence require further work. |

Burgers' equation remains a development testbed for the reconstruction and evaluation pipeline. It is not the current commercial launch portfolio.

The [project status and evidence guide](docs/publications/PROJECT_STATUS.md) links each statement to the relevant code or study, including limitations and the next milestones.

## Research tools

Carbon provides two interfaces to the same research operations:

- **Miner Control Center / Launchpad:** a local browser interface for challenge selection, campaign controls, research settings, and permitted evidence.
- **Miner MCP:** a Model Context Protocol interface for external agents and clients, including onboarding reads, campaign operations, and research tools.

Researchers can use public material, run supported experiments, inspect results, and submit a frozen candidate through the development path. Available models and compute depend on the challenge and configured host. The complete hosted battery journey is still an integration milestone; a visible UI or an installed adapter does not establish that journey.

See the [MCP guide](carbon/miner_mcp/README.md), [Control Center programme](docs/development/CONTROL_CENTER_PROGRAMME.md), and [research environment standard](docs/development/RESEARCH_ENVIRONMENT_STANDARD.md). The standard records available provisions and remaining gaps, including the battery generator/reference kit.

## Commercial model

The first planned customer engagement is a **Carbon Evidence Audit**. An engineering team brings an existing fast model and a proposed use. Carbon scopes an independent evaluation to identify supported behavior, failure regions, and the evidence still needed before wider use.

**Sponsored Discovery** extends that work to finding a better model-building method. A customer brings a defined problem; Carbon organizes research and independent evaluation. Customers pay for the agreed research and evidence program, with outcomes that can include a useful candidate, a narrower operating range, or a finding that the current approach is inadequate.

The expansion path is qualification, model lifecycle support, and recurring evidence software for teams managing multiple models. Reusable solver integrations, evaluation workflows, and permitted experiment records could reduce the cost of each subsequent engagement. Paid demand, repeatability, and delivery economics still need commercial evidence.

Carbon can work with model developers, CAE vendors, and engineering software platforms. Customers keep their existing simulation and design tools; Carbon aims to supply the research and evidence they need to use fast models within those workflows.

[Products and revenue](Business/Product_and_Revenue_Architecture.md) · [Go-to-market](Business/Go_To_Market.md) · [Business plan](Business/Business_Plan.md)

## Why Bittensor

Bittensor provides a network for researcher participation and incentives. Carbon defines the physics task, evaluation rules, and evidence required for a candidate to count as an improvement. Chain consensus does not determine physical truth.

The network thesis is that independent researchers and agents can explore more useful approaches than Carbon could develop with one internal team. Carbon must test that thesis against the cost, speed, and quality of credible alternatives.

The current reward direction is **direct winner plus burn**, with a treasury optional. The separately recorded development testnet publications are non-paying demonstrations. They do not establish miner payouts or production settlement.

The company's commercial plan is to use the subnet as a research team and pay for useful output through Alpha buyback and burn. This remains a planned commercial mechanism, with implementation and review outstanding. Company revenue, network rewards, and Alpha ownership are distinct.

## Explore the repository

| Start here | Read for |
|---|---|
| [Project status](docs/publications/PROJECT_STATUS.md) | Implemented capabilities, research evidence, open work, and launch milestones |
| [Business overview](Business/README.md) | Customers, products, company economics, and market position |
| [Protocol specification](SPEC.md) | Architecture and links to the domain specifications |
| [Challenge readiness](docs/development/CHALLENGE_READINESS.md) | Per-challenge reference, cost, and review records |
| [Development Hub](docs/development/carbon_hub/orientation/START_HERE.md) | Implementation map and engineering workstreams |
| [Publications](docs/publications/README.md) | Current reading guide and historical paper records |
| [Constitution](CONSTITUTION.md) | Scientific, business, and implementation responsibilities |

## Development Hub

Use the [GitHub reading guide](docs/development/carbon_hub/orientation/START_HERE.md) to explore the implementation map. The [HTML Hub](docs/development/carbon_hub/index.html) opens as a local file after cloning; GitHub's file view does not host it. The Hub was retired on 2026-10-03 (OWNER-WORKFLOW-SPEED-01): it is frozen history, not maintained, and no merge requirement.

## Development

```bash
git clone https://github.com/carbonphysicsai/Carbon.git
cd Carbon
# Use the committed Carbon Dev Container / canonical Ubuntu environment.
./scripts/dev/bootstrap.sh
./scripts/dev/doctor.sh
./scripts/dev/ci.sh
```

Follow [Development setup](docs/DEVELOPMENT.md) and the [environment guide](docs/development/ENVIRONMENT.md). Optional science and network dependencies have separate setup requirements. Contributors should read [AGENTS.md](AGENTS.md) before changing code or specifications.

For commercial enquiries and project updates, visit [carbonphysics.ai](https://carbonphysics.ai). Keep confidential customer data out of public issues.
