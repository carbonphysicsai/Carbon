# Ticket GRAPHITE-L4-STAGING-01 - a Graphite Constructor can lower and stage a Level 4 submission

**Status:** todo (proposed by the Test Engineer 2026-10-11; the Test Lead schedules it after battery)
**Owner of the isolation review:** HUMAN_INPUT (the owner and the security owner)
**Depends on:** the Level 4 gates G0-G7 (`carbon.level4`), OWNER-L4-G5-COMPILE-ISOLATION-01, the staging contract (`docs/development/graphite/level4/LEVEL4_STAGING_CONTRACT.md`)

## Why

Stage C's Level 4 Constructor runs (lane G) built no graph. Two causes:
- **The brief.** The brief's `level_domain` listed only Level 0's names, because battery's Level 4 planner document declares no capability. The level_additions brief fix corrects this for every level.
- **No staging path.** A Level 4 strategy's `parameters.composition_graphs` holds only a submission digest (`carbon.battery.level4.reconstruct`). The graph documents travel as a staged directory or envelope (`carbon.level4.staging`). Only the Launchpad miner path stages them (`construction_level.check_freeze` with `level4_directory`). A Graphite phase-3 Constructor has no tool that lowers a model or stages documents, and its experiment and pod path carry none. So every Level 4 proposal from Graphite is refused or stays plain.

Graphite's internal Level 4 and Level 5 hunting needs this path. Until it exists, Level 4 tests run through the Launchpad's Level 4 slot (route A, the Test Lead, 2026-10-11).

## Scope

1. **A research tool** (development levels only, refused at Level 0-3). It takes a graph spec, or a JAX or PyTorch model source in the session workspace, lowers it with `carbon.level4.tooling` inside the session's sandbox, and returns the submission digest plus G0's verdict. No miner code runs on Carbon's side: the tool runs the miner tooling in the sandbox, as the Launchpad path does on the miner's machine.
2. **Carry the staged envelope** with the proposal through `experiment` and the pod path into the rebuild workspace (`level4-manifest.json`, `level4-doc-*.json`), so G3-G7 judge it exactly as for a Launchpad submission.
3. **Tests:**
   - the tool's refusals (level, size bounds, unstaged digest);
   - the same envelope bytes from both paths giving the same digest and record;
   - a Graphite dry run at Level 4 that proposes a graph.

## Not in scope

- Any change to G0-G7, the allowlist, the caps or the variant.
- Any frozen or LIVE rule.
- Level 5.

## Isolation review (owner-reserved)

The tool runs miner-side tooling inside Graphite's sandbox and moves miner-written bytes into Carbon's rebuild workspace. **Before any live use, the owner and the security owner decide** whether the sandbox's isolation covers lowering untrusted model source, and whether the envelope transport inherits G0's bounds (`intake.BOUNDS`, still HUMAN_INPUT). Until then the tool stays refused outside dry runs.

## Definition of Done

- [ ] The tool, the carry-through and the tests above, at DEVELOPMENT maturity.
- [ ] The isolation review recorded by the owner, or the tool left refused.
