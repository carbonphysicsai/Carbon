# VALIDATOR-03 — Challenge-neutral sealed confirmation sets

**Status:** slice 1 implemented in bounded DEVELOPMENT scope, awaiting review.
**Authority:**
- the Test Lead's request, 2026-10-05: generalise EV5's confirmation-set
  pattern into tooling, so each Challenge's final Track B evidence has a
  sealed, independent set;
- OWNER-GRAPHITE-TEST-WAVE-01 §7 (item 6): battery's
  `graphite-confirmation-v1`;
- OWNER-GRAPHITE-TEST-WAVE-05 §4 (#593): the sizes, laws and strata of the
  three sets. Its cooling stratum was set by the Test Lead under that
  delegation on 2026-10-05.

**Executor:** the Carbon Validator session. Branch
`claude/validator-confirmation-sets`, from main `56187e74f`.

## Outcome

An operator can seal one fresh, independent confirmation set per Challenge on
the operator host and bind a study to it.
- The sizes, laws and strata come from recorded decisions.
- No case may repeat a published, private-pool or earlier sealed case.
- Only the public commitment is ever printed.

Sealing itself is an operator action that waits for the owner. This PR is
the tooling. Scores stay DEVELOPMENT; nothing here is a weight or a reward.

## Working decisions (delegated engineering scope)

- **VAL3-D1 — sets are registered documents, never code.**
  - Each role is one document in
    `carbon/challenge_validator/confirmation_sets/`, pinned by digest in its
    `registry.json`, following the `attribution_policies` pattern.
  - Size, law and strata are scientific values. An unset one is `null`,
    listed under `authority.human_input`, and refuses every seal.
  - A document with values must name a decision.
  - Every registered role must be reserved in
    `interface.RESERVED_SEED_ROLES`, so no pool path can prepare it.
  - `motor-graphite-confirmation-v1` is reserved here.
- **VAL3-D2 — the registered sets.**

  | Role | Challenge | Size | Law | Stratum (at least 1/3) | Required priors |
  |---|---|---|---|---|---|
  | `ev5-confirmation` | battery | 120 + 4 | published box, uniform | none | prior only; never sealed by this tool |
  | `graphite-confirmation-v1` | battery | 120 + 4 | as EV5 | none | EV5's set |
  | `cooling-graphite-confirmation-v1` | chip-cold-plate | 60 + 2 | DEVELOPMENT population | `heat_load_w >= 1200` and `inlet_c >= 40.0` | `cold-plate-pools-v1-private` |
  | `motor-graphite-confirmation-v1` | electric-motor-magnetics | 60 + 2 | DEVELOPMENT population | `current_density_a_mm2 >= 10.0` (the motor exam's `J_IMPORTANT`) | `motor-pools-v1-private` |

- **VAL3-D3 — how a stratum is drawn.** The quota is `ceil(cases × fraction)`
  (20 of 60). It is drawn from the population restricted to the stratum by
  rejection, and the remaining cases from the whole population. The Test
  Lead accepted this method. Strata are reported separately.
- **VAL3-D4 — custody.**
  - **Battery** seals into its validator deployment's seed journal through
    `seeds.make_batch` and `daemon.seal_batch`, under the writer lock, as EV5
    did. The validator is never started or recovered. A battery set with
    strata is refused, since `make_batch` draws one law.
  - **Cooling and motor** each use an owner-only custody directory created
    once outside the repository (`init`):
    - a 32-byte root;
    - an append-only journal of public commitments;
    - a writer lock.
  - **Draws (cooling and motor):** HMAC-keyed from the root and role, with
    opaque case ids, hidden duplicates and a root-derived order. These are
    the battery pattern, rebuilt neutrally.
- **VAL3-D5 — the overlap check.** Before committing, the seal refuses any
  fresh case equal to a prior case. The key rounds inputs to 4 decimals for
  battery (its draw precision) and 6 for cooling and motor. The priors are:
  - every published case in the Challenge's evidence directories (TRAIN,
    PRACTICE, pilot, decision-study and timing records), or battery's
    `daemon.published_inputs`;
  - each registered private pool, supplied by the operator as an owner-only
    plan file outside the repository; its digest is printed, its cases never;
  - every pooled batch, for battery;
  - every batch already sealed in the same custody.
    - Each is regenerated from the root and must reproduce its committed
      fingerprint. A role that can't be regenerated, or a mismatch, refuses
      the seal.
    - This is how a battery set is compared with EV5's cases without them
      ever being stored or printed. It runs only on the operator host, under
      the deployment's lock, as OWNER-GRAPHITE-TEST-WAVE-01 §7 requires.
    - A required prior role absent from the custody refuses the seal. Battery
      therefore needs EV5's deployment.
  - Fresh draws that collide with each other are refused too.
- **VAL3-D6 — case-insensitive roles everywhere.** Lookups, the reuse check
  and prior matching all compare `interface.canonical_role`. A different
  batch under a role in any spelling refuses the seal
  (`confirmation_role_reused`). A rerun recalls the same commitment.
- **VAL3-D7 — public output only.** The seal prints exactly these fields:
  - challenge, role and counts;
  - the set digest;
  - `newly_committed`;
  - the commitment (fingerprint, journal sequence);
  - how many prior keys each overlap source held;
  - private-prior file digests.

  Refusals are typed codes naming no case, input or root. Roots and batches
  redact their `repr` and refuse pickling.
- **VAL3-D8 — the pinning manifest** binds:
  - the set document and registry digests;
  - the public skeleton;
  - the digests of the code that draws and seals the set;
  - the commitment;
  - the remaining blockers (`human_input:*`, `not_sealable`, `not_sealed`).
- **VAL3-D9 — EV5's own code is unchanged.** `carbon/battery/value/ev5.py`
  still compares its role exactly. EV5 is frozen (OWNER-EV5-FREEZE-01), so
  this tool registers its set only as a prior.

## Amendment, 2026-10-05: "no strata" is stated explicitly

At the Test Lead's request, from the Graphite readiness gate's check D7
(#625): an empty `strata` list could not be told apart from a missing value.

- **VAL3-D10.** A set drawn from one law with no strata now records
  `strata: "NONE_UNIFORM_LAW"`. The registry refuses an empty list for every
  role (`strata_empty_state_NONE_UNIFORM_LAW`). `null` still means the
  owner's value is unset, and a list still means registered strata. The
  skeleton shows the explicit value.
- **The two battery documents changed:** `ev5-confirmation` and
  `graphite-confirmation-v1`. Each now cites its decision for having no
  strata: OWNER-EV5-FREEZE-01 with the L0 study sheet, and
  OWNER-GRAPHITE-TEST-WAVE-05 §4. The registry re-pins their digests.
- **Nothing sealed changes.** No set has been sealed under these documents,
  and EV5's seal was made by `ev5.seal_confirmation`, not by this registry.

## Slices

1. **This PR:**
   - `carbon/challenge_validator/confirmation.py`: registry, batch, custody,
     overlap, seal, manifest and CLI;
   - `confirmation_sources.py`: battery, cold plate, motor;
   - `confirmation_sets/`: four documents and the registry;
   - the motor role reserved in `interface.py`;
   - `tests/cpu/test_challenge_validator_confirmation.py`.
2. **Next:** the operator-host solve-and-predict path. No such path exists
   even for EV5. It covers:
   - recall a sealed set and write its reference plan in each Challenge's
     runner format (battery `TruthService` jobs; cooling and motor
     `run_batch` plans), owner-only;
   - ingest the solved references against the set;
   - rebuild a frozen strategy and predict on the set;
   - score with the Challenge's exam rule, reporting each stratum
     separately.

   Codex owns each Challenge's scoring pieces (OWNER-GRAPHITE-TEST-WAVE-06
   §5), so slice 2 calls them through a hook and never reimplements them.

## Operator use

```
python -m carbon.challenge_validator.confirmation list
python -m carbon.challenge_validator.confirmation init --challenge chip-cold-plate --custody DIR
python -m carbon.challenge_validator.confirmation seal --role cooling-graphite-confirmation-v1 \
    --custody DIR --prior cold-plate-pools-v1-private=PRIVATE_PLAN.json
python -m carbon.challenge_validator.confirmation seal --role graphite-confirmation-v1 \
    --config DEPLOYMENT.json
python -m carbon.challenge_validator.confirmation manifest --role ROLE \
    [--fingerprint F --sequence N]
```

## Validation

- `tests/cpu/test_challenge_validator_confirmation.py` (19 tests). They cover:
  - the registry's recorded values and invariants: altered, malformed and
    unreserved documents, and unset values that refuse every seal;
  - a motor and a cooling set sealed in a temporary custody:
    - 60 fresh and admitted cases inside the box;
    - at least 20 inside the stratum;
    - hidden duplicates;
  - idempotent reruns in any spelling, and a second batch under the role
    refused;
  - overlap refusals against published and private cases;
  - required, unregistered, group-readable and malformed private priors;
  - earlier sets regenerated: required, unregenerable and mismatched cases;
  - custody guards: inside the repository, existing, owner-only, and an
    uncommitted root;
  - the CLI's output and the journal holding no case id, input or root;
  - battery sealed after EV5 in a synthetic deployment: EV5 required, EV5
    regenerated, the pool untouched, the validator never started, and reuse
    and EV5 mismatch refused;
  - the manifest.
- **Native:** the confirmation, contract, battery, hardening, cooling and
  scoring validator suites, the EV5 suite and the lessons log: 251 passed.
- `scripts/check_quality.py --base origin/main`: passed.
- **Canonical:** recorded in the PR.

## Invariants exercised

- **1 and 2:** no confirmation case, input, seed or root on any public
  surface, pod or pool.
- **3 and 10:** pinned identities and digests; a set changes only by a new
  registered version.
- **9:** every unset scientific value fails closed.
- **The confirmation custody rules** of OWNER-EV5-Q3-01 and
  OWNER-GRAPHITE-TEST-WAVE-01 §7.

## Maturity

SPECIFIED, IMPLEMENTED, TESTED (DEVELOPMENT tooling). No set is sealed, and
nothing is SCIENTIFICALLY_QUALIFIED or SECURITY_QUALIFIED. The custody's
owner-only checks are engineering guards, not a security audit (AGENTS.md
§13).

## Human input required

- **Sealing:** each seal is an operator action on the operator or validator
  host, ordered by the owner.
- **Battery:** sealing `graphite-confirmation-v1` needs EV5's deployment
  (journal sequence 14). Only the owner names its path.
- **Merge order:** #593 (OWNER-GRAPHITE-TEST-WAVE-05) records the values
  registered here. It should merge first.
