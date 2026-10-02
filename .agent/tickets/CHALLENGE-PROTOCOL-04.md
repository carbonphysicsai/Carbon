# CHALLENGE-PROTOCOL-04 — Phase 1 step 4: battery through Test/iterate with Graphite (Graphite phases 3 and 4)

**Status:** in progress (slice 1).
**Primary Hub map_ref:** `SYSTEM/DEVELOPMENT-SEQUENCING`, `HUB_UPDATE_REQUIRED`.
**Affects:** `SYSTEM/AGENT-EXECUTION`.
**Authority:**
- OWNER-CHALLENGE-ROADMAP-01 and -02;
- OWNER-CHALLENGE-STEP4-01;
- OWNER-GRAPHITE-01 and -02;
- OWNER-CHALLENGE-ADMISSION-01;
- OWNER-DX-03.

**Spec:** `Design_Specs/Challenge_Roadmap.md` §01 step 4, §02 and §03; the
protocol draft; `docs/development/GRAPHITE_TESTING_AGENT_PLAN.md` §5 and §7.

## Outcome

The roadmap's step 4 is "Run battery through Test/iterate with Graphite.
Attack, fix, re-score; tune construction and scoring until results stop
improving or the iteration budget runs out." Its output is an iteration log.
It is Graphite's phase 3 and phase 4, built in this lane (ROADMAP-02 item 4):
- **Phase 3, Constructor at Level 0.** Live sessions propose battery recipes
  through the real miner path, inside the recorded construction contract.
  Carbon checks each proposal against the contract record, rebuilds it on the
  owner's host, scores it on development material with the deciding rule,
  and rebuilds it cleanly from its package.
- **Phase 4, Attacker.** Live sessions probe suite v1's eight vectors through
  the miner path and, under OWNER-CHALLENGE-STEP4-01, run code in the
  sandbox. Carbon re-verifies every claimed fail-open outside the agent
  before anything is a finding. A coverage report merges the attacker's
  results with the suite's checks, bound to the suite digest.

**Budget.** The `GRAPHITE-GRANT-STEP4` grant: USD 5.00 of Engy, 6 runs at a
USD 0.77 worst case each. The plan is 3 Constructor and 3 Attacker sessions,
about USD 0.73 expected. Derivation: `docs/development/graphite/grants/README.md`.

## Slices

1. **Records, grant and stage.**
   - The grant and its derivation, the decisions and this ticket.
   - The stage profile (`carbon/agent_campaign/graphite/stage.py`). Its
     digest is the campaign's profile in the controller.
   - The provider refuses a role outside its stage's row of Graphite's
     permission ledger, a task with another profile, a changed ledger, and a
     resumed session whose stage changed.
2. **Provider repairs for live sessions.** Planning found these defects:
   - an async run inside the miner path's event loop;
   - per-role call caps;
   - tool identities namespaced by run;
   - the research-trial cap enforced in the toolbox;
   - the parallel-call rule recorded;
   - results trimmed for the model, with the full result kept by digest;
   - over-refusal tested against real battery results.
3. **Miner-path adapter.** Graphite drives the owner's battery campaign the
   way a miner's client does. Practice runs in the local carrier. Graphite
   never submits to the validator.
4. **Carbon-side scoring.** After `SELECT`, Carbon runs:
   - the contract-record check;
   - compile and rebuild;
   - the development score under the deciding rule;
   - a case-by-case comparison with the incumbent, report only;
   - the package, and a clean rebuild.

   An out-of-record candidate is refused, recorded as a finding, and never
   scored.
5. **The phase 3 runner**, with dry run, the iteration log and one store per
   grant. Then the live block of 3 Constructor sessions.
6. **Attacker v1:**
   - brief builder;
   - sandboxed execution;
   - vector classifier;
   - re-verification outside the agent;
   - findings into the controller;
   - specimen harness;
   - coverage report.
7. **The live block of 3 Attacker sessions.** Then the coverage report and
   iteration log are committed and step 4 closes.

## Working decisions (slice 1)

- **PROTO4-D1. The stage enters through the campaign profile.** A stage
  profile binds the stage, the permission ledger's bytes and battery's
  permission inventory (`study.permission_inventory`). Its digest is the
  campaign's registered profile, so the controller's `profile_not_in_force`
  check needs no change. The provider, which alone knows the Graphite role,
  checks the role against the stage's row.
- **PROTO4-D2. Step 4 runs at `test_iterate`.**
  - Battery's pipeline record is at `protocol` (Phase 1). The ledger's stages
    are the roadmap's stages.
  - Step 4 is the roadmap's Test/iterate stage applied to battery.
  - The ledger is a DRAFT for the process owner to approve at lock.
- **PROTO4-D3. Without a stage profile, a provider behaves as before.**
  - Phase 2's literature runner keeps working unchanged.
  - Phase 3 and 4 runners will refuse to start without one.

## Human-reserved, fail closed until set

- **Science owner.** These are reported, not decided, until set:
  - the development scoring set;
  - the incumbent member;
  - any comparison margin;
  - the reconstruction tolerance.
- **Process owner.** The permission ledger and the stage mapping, both DRAFT
  until lock.
- **Credential.** The Engy key is supplied by the owner's environment. It is
  never in chat, the repository or logs.

## Maturity ceiling

DEVELOPMENT, internal, never mainnet. Nothing here is scientific or security
qualification. Allowing attacker code in the sandbox is the owner's
development decision, not security acceptance.
