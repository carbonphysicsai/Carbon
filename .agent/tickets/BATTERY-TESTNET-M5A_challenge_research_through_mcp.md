# BATTERY-TESTNET-M5A — Challenge-scoped research through Carbon's shared MCP interface

**Programme:** battery testnet hardening track (parent #341)
**Status:** `in_progress`, pending delivery in its PR
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`
**Authority:** OWNER-BATTERY-TESTNET-01, the owner's 2026-09-25 direction to
close the gap between the shared MCP interface and each Challenge's research
environment, and OWNER-DX-03. Launch Challenges: Battery, Chip cooling,
Electric motors and Photonics. Power magnetics and airfoils are deferred.
**Depends on:** BATTERY-TESTNET-M1 (per-Challenge contracts),
BATTERY-TESTNET-M2 (exam, seeds, shadow pool).

## Outcome

An agent works through MCP only, with no Challenge-specific launcher,
repository access or manual step:
1. it discovers the Challenges and selects battery by exact id and version;
2. it reads battery's permitted data, models, reference method and limits;
3. it researches under the shared twelve operations;
4. it submits a reconstructable recipe;
5. Carbon evaluates the recipe under battery's own contract.

## Scope

- `carbon/challenge_registry/`: the adapter registry.
  - Resolution is by exact (id, version, profile), with typed refusals and no
    default or fallback.
  - Descriptions are derived from executable registrations and separate
    *implemented* from *usable on this host*.
  - Chip cooling, electric motors and photonics are RESERVED with their
    tracking issues (#342, #344, #345).
  - Power magnetics (#343) and airfoils (#346) are DEFERRED.
- Open-tier MCP discovery: `carbon_challenges_v1__list`,
  `carbon_challenges_v1__describe` and `carbon://challenges/v1/catalog`.
- One B-07 composition for every Challenge:
  - `research_service.compose_research_service(ChallengeParts)`;
  - Burgers keeps `make_research_service`, byte-identical;
  - the research SDK sends its composition's own Challenge key.
- Battery adapter (`carbon/battery/research.py`, `practice.py`):
  - authored practice population, sampling plan and measurement contract;
  - public objective, TRAIN v1, PRACTICE and OCV material;
  - practice in the isolated carrier from the exact Carbon recipe bytes,
    scored by Carbon with the exam's gates;
  - scaffold and examples.
- Campaign binding:
  - `launch` takes `challenge` and `challenge_version`, recorded in the frozen
    manifest;
  - `prepare`, attach, freeze and submit route by it;
  - a battery gateway authenticates battery requests only.
- Evaluation (`carbon/battery/evaluation.py`):
  - an operator-configured deployment over committed private batches and truth
    references;
  - allow-listed feedback;
  - typed `REFUSED` and `FAILED_INFRA` outcomes, neither of them a score.

## Definition of Done

- [x] Unknown, reserved, deferred, wrong-version and unusable-profile
      selections are typed errors, and no request falls back to Burgers.
- [x] A battery request needs no Burgers field, and a Burgers request never
      reaches battery code. The gateway test covers both directions.
- [x] Burgers composition digests are unchanged: ChallengeInfo, the
      InteractionManifest, the policy and the scaffold (snapshot compared).
- [x] End-to-end MCP test on the real signed gateway, adapter, durable tasks
      and ledger:
  - discover, validate, compile and estimate, charging nothing;
  - public material, including PRACTICE;
  - check_design;
  - practice of a JAX MLP and a KNN;
  - cancel;
  - a freeze refused without practice;
  - submit refused while evaluation is unconfigured, without consuming the
    epoch;
  - submit scored on committed private pools;
  - no private case, input or seed in the feedback.
- [x] Discovery tests: the catalog, typed refusals, derived descriptions,
      host usability, the open-tier tools, and discovery writing nothing.

## Known limits

**Superseded by M3 (BATTERY-TESTNET-M3):** the reconstruction-path,
pool-state and autonomous-agent limits below are closed there. Evaluation
now goes through the validator daemon, `evaluation.py` is removed, and
Carbon's agent can research battery (M3-D11, M3-D12). The text below is kept
as M5A delivered it.

- **Reconstruction path.** The submission rebuild runs in the evaluation
  process (`DIRECT_TRUSTED_PROCESS`), not in the validator's isolated
  reconstruction worker. Every result says `validator_path: false`. Moving it
  into the C-03 worker is the validator daemon's work (M3).
- **Pool state.** The screening pool's rotation count lives for the life of the
  process. Retirements persist in the journal. Durable pool state is M3.
- **Test runner.** In tests, practice runs through a subprocess stand-in for
  the Docker carrier, and its feedback says `SUBPROCESS_TEST_ONLY_NOT_ISOLATED`.
  The carrier itself is exercised by the existing Burgers carrier tests; no
  battery practice has yet run in the real image on a host.
- **No autonomous agent.** Battery campaigns are miner-driven (`agent: none`).
  Carbon's autonomous agent is written for Burgers and is refused by name.
- **Launchpad.** The shared operations table gives both doors the Challenge
  fields. The browser's starter recipe and labels remain Burgers-only.
- **Reserved Challenges.** Chip cooling, motors and photonics have names,
  tracking issues and the refusal path, and nothing else. Their slugs are
  working names until each registers a contract.
- **Runtime lanes.** Julia, the GPU diagnostic lane and authored scientific
  tasks are not composed for battery. A battery launch declaring them is
  refused.
