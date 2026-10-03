# C-MLP-05: the miner's research surface, in Carbon's brand

Owner authority: the owner, in chat on 2026-10-02, after sending a mockup:

> we were supposed to be working to a branded version of this. Whatever you as
> an agent think is an optimal work surface for you and the miner

Recorded as `OWNER-MINER-RESEARCH-SURFACE-01` in `.agent/DECISIONS.md`, with
the executor's decisions RSURF-D1 to RSURF-D10.

**Primary Development Hub map_ref:** `SYSTEM/AGENT-EXECUTION`,
`HUB_UPDATE_REQUIRED`.

**Status:** implemented on `agent/miner-research-surface` (engineering
evidence only). It is built on the C-MLP-03 easy-mode Control Center and
shares its files. The setup wizard and `environment_setup.py` stay
C-MLP-03's.

## What the surface is

The screen a miner and their agent work from once setup is done:
- **Shell.** A left rail. On a narrow screen it collapses behind a menu
  button. A light and a dark theme come from the same brand tokens: the
  system setting is followed, and a toggle overrides it.
- **Launchpad.** The configured setup in agent-first order: Challenge, Agent,
  Inference (only with Carbon's own agent), Compute, Limits, Review. Each card
  links to the setup or launch step that changes it. Launch is the existing
  launch operation and its gates.
- **Active campaign.**
  - A header with the campaign's real state, halt and resume.
  - Tiles from data that exists.
  - The real lifecycle as a stage tracker (RSURF-D9).
  - Tabs: Live, Experiments, Agent reasoning, Contract, Artifacts,
    Submission, Logs, Settings.
- **Charts.** One SVG renderer draws by output kind (RSURF-D8). Battery
  draws its aggregate practice components, current against previous with
  deltas, and the trend across practice runs. Where allowed (RSURF-D2), it
  also draws predicted-vs-reference curves for public practice cases.
- **Contract.** What the miner may change for this Challenge:
  - rebuildable models;
  - controls with their ranges and defaults;
  - every capability's status and blocker;
  - exam gates, never-disclosed material, the feedback mode and limits;
  - the contract digest and the exam version.
  It also has an empty construction-level slot (RSURF-D10).
- **Agent parity.**
  - `carbon_campaign_view` and its browser route return one document
    (RSURF-D1).
  - `carbon_note` lets any MCP client write to the journal (RSURF-D5).
  - Attach now brings the research prompts and skill (RSURF-D6).
- **Demo fixture.** `scripts/dev/miner_launchpad/research_demo.py` serves one
  synthetic battery campaign, labelled as a fixture (RSURF-D7).
- **Toolbox (owner's second request, RSURF-D11).** The Tools tab and a
  Toolbox on each Challenge card, from one document read from the
  Challenge's records. It covers:
  - the JAX and PyTorch runtimes, with their pinned versions;
  - Julia (research only), with its blocker and whether `run_julia` runs
    here;
  - the workspace and workflow tools, with their exact MCP names;
  - rebuildable families and their backends;
  - what the validator rebuilds with.

  It is also `carbon_toolbox`, and each practice run shows its framework and
  image.
- **Conversation (RSURF-D12).** The miner writes to their own agent from the
  page. Any MCP agent reads with `carbon_messages` and replies with
  `carbon_note` (`note_kind=reply`). A message cannot change anything frozen
  at launch.

## Owner input

Both questions were answered on 2026-10-03
(OWNER-MINER-RESEARCH-SURFACE-02), and both are built:

- **RSURF-D3, yes, as a new trainer version.** Battery trainer v2 records up
  to 64 points of the trainer's own TRAIN loss, in practice only. The
  validator's reconstruction never records it and computes exactly what it
  did. The implementation identity changes prospectively, and running
  deployments carry over under OWNER-BATTERY-CARRYOVER-01. The Learning curve
  chart draws the recorded history.
- **RSURF-D13, yes, recorded.** This amends C-MLP-02-D6 prospectively.
  - A campaign launched under the frozen miner-guidance rule has Carbon's
    agent read new messages at each step boundary, at most 4 per step.
  - Each step's messages are recorded with their digests, chained from the
    epoch plan, and replayed exactly.
  - The agent replies through the same reply note.
  - Earlier campaigns read none.

## Owner answers, 2026-10-03 (OWNER-MINER-RESEARCH-SURFACE-03)

- **Carry messages across epochs (RSURF-D14).** A new epoch's first step
  carries forward the last 3 messages Carbon's agent read, each with up to 2
  of its own replies. They are recorded and chained like new messages.
- **Use the tooling from the page (RSURF-D15 to D18).**
  - The Tools tab opens a tool session under the campaign's ownership lock,
    and its panels are the agent's own research tools.
  - A run's stdout, files and images come through `run_output`.
  - The demo shows the toolbox working and runs nothing.

## Boundaries

- DEVELOPMENT and testnet 567. Practice evidence is not qualification. No
  leaderboard, rank or official score.
- No private evaluation data, seed, private-pool material or per-case
  evaluation error reaches the view.
- Spend shown is the miner's own ledger. Carbon caps and bills nothing.
- Fixture data cannot reach a campaign, a ledger or LIVE.
