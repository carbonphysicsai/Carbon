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

- **RSURF-D3.** May the battery worker record a bounded, TRAIN-only loss
  history? It would change the trusted worker program and its implementation
  identity. Until the owner decides, the learning-curve slot says why it is
  empty.
- **RSURF-D13.** May Carbon's own autonomous agent read the miner's messages
  as user-role input at step boundaries? That would amend C-MLP-02-D6, which
  freezes its task at launch and keeps the browser from authoring its
  prompts. Until the owner decides, it does not read them, and the page says
  so.

## Boundaries

- DEVELOPMENT and testnet 567. Practice evidence is not qualification. No
  leaderboard, rank or official score.
- No private evaluation data, seed, private-pool material or per-case
  evaluation error reaches the view.
- Spend shown is the miner's own ledger. Carbon caps and bills nothing.
- Fixture data cannot reach a campaign, a ledger or LIVE.
