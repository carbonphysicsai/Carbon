# CHALLENGE-AI-COOLING-08 — Interface-v1 validator adapter

**Status:** active engineering implementation

**Authority:** `VALIDATOR-01_challenge_neutral_validator.md` Interface v1,
OWNER-GRAPHITE-TEST-WAVE-01 section 3, OWNER-CHALLENGE-FOUNDATION-01,
OWNER-CHALLENGE-DESIGN-01 and OWNER-LAUNCH-PORTFOLIO-02.

**Predecessor:** `CHALLENGE-AI-COOLING-06_launchpad_level0.md`. The separate
Graphite public-practice scoring adapter is PR #584 and is not a dependency of
this validator adapter.

**Tracking:** one branch and one PR. PR Lead may take over after the author
pushes the reviewable head.

## Outcome

Implement `ChallengeAdapter` Interface v1 for `chip-cold-plate` so the neutral
validator can:

1. dispatch by the registered Cooling construction-contract digest;
2. compile and deterministically reconstruct the registered Level-0
   Gaussian kernel-ridge recipe;
3. prepare, ingest and open the exact digest-pinned public PRACTICE batch;
4. synchronously score a reconstruction with the existing cold-plate exam
   gates, TRAIN scales and aggregate;
5. persist owner, outcome and operator-only per-case score records in an
   owner-only DEVELOPMENT store; and
6. return only an allow-listed miner outcome with no private cases,
   qualification or reward.

The adapter is public adaptive DEVELOPMENT evaluation. It is not the fresh
Graphite confirmation set and does not create a private or official exam.

## Scope

KEEP the registered Cooling Level-0 contract, compiler, deterministic rebuild,
pinned 400-case TRAIN material, pinned 100-case PRACTICE material, existing
exam gates, TRAIN-normalized three-component score and aggregate. WRAP them
behind Interface v1.

The adapter's only preparable batch kind is the exact public PRACTICE batch.
Reference ingestion accepts only records byte-for-data equivalent to the
digest-pinned public material. The operator must explicitly prepare, ingest
and open that batch before a submission can score.

Out of scope:

- generating or importing a fresh/private confirmation set;
- counted decision-study CFD or its 48-case evidence;
- PB-ADV/Mode X or constructed Track-B controls;
- changing any scientific gate, scale, aggregate, population or recipe;
- service deployment, security qualification, customer acceptance, LIVE,
  weights, rewards or chain action;
- EV5, journal sequence 14 or Battery's live contract.

## Working decisions

- **COOL-VAL-D1 — public practice only.** The first Cooling validator pool is
  exactly the pinned public PRACTICE batch. Its evidence label is
  `DEVELOPMENT_PUBLIC_ADAPTIVE`; it cannot support confirmation or reliability
  claims.
- **COOL-VAL-D2 — exact reference custody.** Ingestion accepts a record only
  when it equals the corresponding record in the pinned PRACTICE artifact.
  No caller-supplied plausible output becomes reference truth.
- **COOL-VAL-D3 — no sampling decision.** Batch preparation exposes the fixed
  public set and performs no random draw. Fresh confirmation sampling remains
  `HUMAN_INPUT` outside this ticket.
- **COOL-VAL-D4 — synchronous bounded evaluation.** Level 0 contains no
  participant code. The adapter compiles, rebuilds and predicts in process;
  malformed constructions are `INVALID_CONSTRUCTION`, while unexpected
  adapter faults remain validator-typed infrastructure failures.
- **COOL-VAL-D5 — durable minimal disclosure.** The miner outcome contains
  only score eligibility and descriptive counts. Cases, predictions, gates,
  identities and reconstruction details remain operator-only.
- **COOL-VAL-D6 — confirmation role reserved, set absent.** The Cooling
  Graphite confirmation role is reserved by record, but this ticket creates,
  prepares, ingests or seals no confirmation batch.

## Acceptance

- [ ] The adapter registers against the exact Cooling contract/version and
      publishes pinned contract, rule and implementation identities.
- [ ] The neutral validator evaluates a valid Cooling submission only after
      the public batch is complete and open.
- [ ] Invalid Cooling recipes are recorded as `INVALID_CONSTRUCTION` and no
      cross-Challenge fallback exists.
- [ ] Reference ingestion refuses altered inputs, outputs, checks, image or
      other record fields.
- [ ] The miner outcome is allow-listed and contains no case id, prediction,
      reference, private path or confirmation identity.
- [ ] The operator score record reproduces the existing exam rows and
      aggregate under the pinned rule.
- [ ] The store is owner-only, survives adapter restart and keeps owner reads
      separate from operator records.
- [ ] The Cooling confirmation role is reserved without creating a set.
- [ ] Battery adapter and neutral Interface-v1 behavior remain covered.
- [ ] Focused tests, applicable subsystem checks, lint and canonical
      acceptance pass at the delivered head.

## Maturity ceiling

At most SPECIFIED, IMPLEMENTED and TESTED for public adaptive DEVELOPMENT
evaluation. Not scientifically or security qualified. No population
reliability, customer, production or LIVE claim.

## Hub impact

None. The Development Hub is retired by the current delivery protocol.

## Human input required

None for this bounded public-practice adapter. Fresh confirmation population,
attack budget, private reference execution, service deployment and any spend
remain separately human-owned and fail closed.
