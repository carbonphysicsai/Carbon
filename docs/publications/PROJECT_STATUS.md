# Carbon project status

**Reviewed: 28 September 2026.** This guide summarizes the code and evidence on `main` at [63950e36](https://github.com/carbonphysicsai/Carbon/tree/63950e36fcf35b6996f9bbc92f793cfdbcd84304). It separates working development components, recorded experiments, and remaining launch work. Follow the linked records for subsequent changes.

Carbon has progressed from a Burgers testbed to a four-challenge launch plan, with battery fast charging and ageing as the first focus. The repository contains real numerical studies and research tooling alongside unfinished integration and qualification work. It does not establish a production reward network or customer-qualified models.

## Launch portfolio

The owner selected battery, AI-chip cold plates, electric motors, and silicon photonics in `OWNER-LAUNCH-PORTFOLIO-01` on 26 September 2026. The [decision record](../../.agent/DECISIONS.md#2026-09-26--owner-launch-portfolio-01-battery-is-a-launch-challenge) states that selection is not launch approval.

| Challenge | Intended prediction | Evidence to date | Next boundary |
|---|---|---|---|
| Battery fast charging and ageing | Voltage and temperature trajectories, plating margin, and capacity at selected cycles | PyBaMM reference study, JAX reconstruction, development exam and daemon, practice and MCP services | Complete research provisions, deployment/replay work, and challenge qualification |
| AI-chip cold plates | Thermal performance and pressure drop for a bounded channel family | OpenFOAM channel flow, heat-flux, and simplified conjugate heat-transfer verification | Define and test the actual cold-plate geometry, materials, and pilot |
| Electric motors | Torque-angle response, torque ripple, and selected magnetic quantities | Bounded feasibility assessment and proposed reference path | Reproduce a benchmark and establish reference adequacy |
| Silicon photonics | Optical coupling for a bounded coupler geometry | Reference diagnostics and calibration studies | Resolve phase convention and convergence before designing the exam |

Sources: [readiness records](../development/CHALLENGE_READINESS.md), [battery domain](../../carbon/battery/domain.py), [conjugate heat-transfer verification](../../scripts/dev/cold_plate/conjugate_verification/README.md), [motor feasibility](../development/MOTOR_FEASIBILITY.md), and [photonics repair](../development/PHOTONICS_PHASE_CONVENTION_REPAIR.md).

The registry distinguishes implemented entries from reserved challenge directions. An implemented entry still depends on the host's configured runtime and services. Burgers remains a development testbed; it is not the four-challenge launch portfolio.

## What the software supports

| Area | Available development work | Limit of the claim |
|---|---|---|
| Model reconstruction | Pinned JAX reconstruction, including FNO/DeepONet development paths and battery-specific recipes | Supported families and recipes vary by challenge; arbitrary model execution is not implied |
| Evaluation | Registered measurements, physical checks, retained results, and separate internal/public projections | Engineering tests do not establish scientific qualification of an exam |
| Battery services | Construction contract, reference/exam services, reconstruction daemon, and practice operations | Host deployment and a complete real miner journey have separate acceptance requirements |
| Miner Control Center | Local browser shell, challenge wizard, settings, campaign operations, and evidence views | Hosted service availability and end-to-end battery acceptance are not established by the interface |
| Miner MCP | Shared campaign operations and research tools; onboarding and exam information without a prepared campaign | Development submission does not mean official submission or reward eligibility |
| Research environments | Public material, construction vocabulary, training and practice support; Python/Julia research paths where configured | Battery's generator/reference kit remains an explicit gap in the research environment standard |
| Network integration | Chain adapter, identity/commitment/transport work, reward routing, and recorded localnet checks | Localnet results do not establish public mainnet readiness |
| Customer scoping | Goal-to-Challenge Workbench and intake/review components | A scoping or structural check does not qualify physics or prove a paid customer |

Read [MCP](../../carbon/miner_mcp/README.md), [Control Center implementation](../../scripts/dev/miner_launchpad/), [Control Center programme](../development/CONTROL_CENTER_PROGRAMME.md), [battery programme](../development/BATTERY_TESTNET_PROGRAMME_STATE.md), [research provisions](../../carbon/challenge_kit/standard.py), and [Workbench](../../Business/Carbon_Fit/workbench/README.md).

The Control Center programme matrix is a dated 26 September audit. Later code includes the new navigation and wizard; the matrix's older UI rows should not be treated as a description of today's markup. Neither source establishes a completed hosted battery campaign.

## Research evidence

### Battery exam design

The [24 September development study](../development/EXAM_DESIGN_CAMPAIGN_RESULT.md) reports 2,604 successful main-run reference jobs: 2,588 cases and 16 refinements. Its registered comparison rule distinguished the tested improvement from regression, regional regression, memorized-screening, and equal-quality controls on 200 fresh private verification cases.

That is evidence for the bounded study and controls. It does not establish production qualification or customer value. The same report records coverage gaps, reference uncertainty, and a correction: the original battery reconstructions used the pod's CPU backend, with GPU reconstruction reported separately.

### Engineering decision value

The [EV1 study](../development/BATTERY_ENGINEERING_VALUE_EV1.md) tested whether model scores select better charging protocols. It completed 384 reference solves and compared reconstructed models with labelled controls. The study found weak indicative alignment, and none of its verification scenarios had a feasible protocol within the tested design set.

The next work is to broaden that design set and test decision-aware robustness under a prospectively defined contract. Carbon cannot infer engineering fitness from the earlier exam-design success.

### Agent research

The [recorded browser campaign](../development/MINER_LAUNCHPAD_RESEARCH_BRIDGE.md#second-browser-campaign-real-final-result-one-practice-iteration) completed one real JAX practice trial and independent reconstruction. It returned `REJECTED_MANDATORY`; it did not demonstrate an accepted model improvement or sustained multi-iteration research.

The more recent battery [tiers 0 and 1](../development/BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIERS_0_1.md) measured design generation and research-interface friction. [Tier 2](../development/BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_2.md) stopped on an undisclosed one-call-per-turn restriction before a numerical experiment. Those findings guide tool repairs; they are not evidence that an autonomous agent has solved the battery challenge.

## Network and rewards

The [engineering board](../../.agent/WAVE.md) records completion of the bounded C0 network work and a successful standard-profile disposable-localnet run. Its historical development testnet publication has verified row readback, while burn amounts, epoch effects, miner payment, and settlement remain unproven.

The current reward direction is direct winner plus burn, with treasury optional. Battery Phase A permits only its approved all-burn development path. Mainnet operation, paying winners, and production qualification require their own evidence and authority.

The company's planned Alpha buyback and burn for useful research output is a separate commercial mechanism. See [Network and Alpha](../../Business/Network_and_Alpha_Value.md).

## Commercial position

Evidence Audit remains the first planned customer engagement. Sponsored Discovery is the first expansion based on competitive external research. Qualification, lifecycle support, enterprise software, and APIs follow as customers and delivery economics justify them.

The repository documents those offers and scoping tools. It does not establish signed paid customers, recurring revenue, validated prices, or product-market fit. [Business and market](../../Business/Investor_Positioning_and_Market.md) explains the thesis and the customer evidence required.

## Next milestones

1. Complete and observe the real battery research-to-evaluation journey, including recovery and resource cleanup.
2. Close the battery research environment gaps and resolve the recorded agent-interface findings.
3. Establish reference, scientific, security, operating, and economic readiness for each intended launch configuration.
4. Advance the remaining portfolio through their own reference and challenge studies.
5. Deliver a paid Evidence Audit, measure its cost and customer value, and test repeat demand.

These are development and business milestones, not release dates. The [launch path](../../launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.7.md), per-track records, and domain specifications control the detailed requirements.
