# Battery — common packet worked example (DEVELOPMENT only)

This is an F1 **mapping example**, not a replacement for Battery's contract,
readiness record or exam. It uses public repository sources on main
`37ed2912cf4b5c590ceef8965a432652884bea9c`. It does not reopen EV5,
sealed journal sequence 14, the live exam, protected batches or the current
scoring rule. The older
[`BATTERY_STATUS_2026-10-02.md`](BATTERY_STATUS_2026-10-02.md) is dated
reconciliation evidence, not a live status oracle. `OPEN` below means no
approval is supplied by this packet. See the
[common template](COMMON_DESIGN_PACKET_V1.md) for field meanings and owners.

## 1. Engineering job

The [readiness record](../../../carbon/challenge_readiness/records/battery-fastcharge-ageing-development-v1.v3.json)
describes a battery-management/cell-engineer hypothesis: choose a two-stage
constant-current protocol while predicting voltage, temperature, plating
margin and capacity fade. Agreement is with the specified PyBaMM DFN cell,
not a real-cell or customer acceptance claim. The consequence of a wrong
choice is false acceptance of a physically inadmissible protocol, illustrated
by the boundary-optimist control in the dated Battery status record §2.
`OPEN` (science/product owners): deployment objective, real-cell acceptance
and any production loss model. The DEVELOPMENT exam cannot fill them.

## 2. Physical system

`carbon/battery/domain.py`, `contracts.py` and `reference.py` define the
two-stage currents and operating inputs, DFN/OKane2022 model, lumped thermal
response and 30-cycle task. The readiness record lists `c1` and `c2` as
design variables and ambient temperature and initial state of charge as
conditions. Its recorded outputs use a 30-second trajectory grid for the
first hour and capacity at cycles 1, 10, 20 and 30. This is a model-specific
cell task; it does not establish pack behavior or a real-cell ageing law.
`OPEN` (science owner): any new cell/material provenance, experimental
boundary/initial-state law or physical scope beyond that model.

## 3. Population P, Q and w

The v3 readiness record has a **proposed**, unapproved DEVELOPMENT sampling
statement over `INPUT_BOUNDS`; it is not a ratified production population.
The exact training, practice and protected exam draw contracts remain with
their registered owners (`carbon/battery/`, `carbon/seeding/` and current exam
policy), not this document. `OPEN` (science owner): independently approved
deployment `P`, proposal law `Q`, strata and evidence weighting `w`, with an
independent-observation unit. No reliability interval follows from reusing
cases across candidate arms.

## 4. Case contract

The registered Battery Challenge identity is
`battery-fastcharge-ageing-development-v1`; the reconstruction contract is
in `carbon/reconstruction/capability_registry.py`. The case authoring and
public/protected projection rules are in `carbon/authoring/cases.py`. Public
research inputs and miner-owned draws must not reveal official seeds, derived
IDs, protected labels or final-case composition. `OPEN` (science and
construction owners): any case-grammar expansion or new disclosure grant.

## 5. Reference policy

The v3 readiness record reports PyBaMM 26.8.0.0 DFN with OKane2022, a
hash-locked overlay and retained campaign records. The dated Battery status
record §1 gives the IDAKLU tolerances for that recorded study. These pins
belong to that study, not to another cell or new runtime. `FAILED_INFRA`
attempts remain distinct from scientific reference outcomes. `OPEN`
(science/security/compute owners): launch-grade reference qualification,
licensing/redistribution, any new solver profile, tolerances or spend.

## 6. Output and measurement contract

The v3 readiness record names voltage, temperature, plating margin and
capacity observations with units. `carbon/battery/exam.py` owns the
provisional DEVELOPMENT exam rules; the current registered rule and any
prospective variants must retain separate identities. A mandatory plating or
thermal failure cannot be erased by a favorable soft score. `OPEN` (science
owner): production gates, metric qualification and score weights. The
45/30/25 physics/robustness/accuracy split is a candidate for testing, not an
adopted Battery rule.

## 7. Construction contract

`carbon/reconstruction/capability_registry.py` and
`carbon/reconstruction/challenge_contracts.py` own the Battery vocabulary,
recipe and reconstruction permissions; the v3 readiness record calls the
contract Level 0. A public training path is not permission to access official
evaluation. `OPEN` (construction/security owners): any broader execution
freedom or LIVE isolation acceptance. No new permission is granted here.

## 8. Research kit

`carbon/challenge_kit/standard.py` declares Battery's public research,
documentation, own-seed generator/reference, practice, compute and agent
provisions and names gaps. Read that live registry before claiming a provision
complete. Miner-generated cases are distinct from official draws; whether a
generated case may enter construction is controlled by the construction
contract. `OPEN` (kit/construction owners): any remaining named provision gap
or data-rights grant. Protected exam and confirmation material remains
operator-side.

## 9. Evidence plan

The dated Battery status record §2 inventories EV1–EV4 and Problem C,
including adverse boundary-control findings; §6 separates starting evidence
from protocol-suite acceptance. The current pipeline
[`protocol.json`](../../../carbon/challenge_pipeline/protocol.json) remains
`DEFINING`, with Phase 1 steps 2–8 still `todo`. Admission, independent fresh
confirmation, a measured cost comparison and the training-budget study need
their own exact contracts and receipts. `OPEN` (science/process/compute
owners): final-case sampling, promotion rule, spending and qualified rubric.
No public practice result substitutes for sealed confirmation.

## 10. Readiness and claim record

The v3 Battery readiness record says `PROPOSED_DEVELOPMENT_DESIGN`, with
scientific, numerical-reference, customer and launch reviews not started at
that snapshot. Its `next_experiment` prose is stale relative to later EV2/EV4
work, so this example does not copy it as a current instruction. The
`carbon/challenge_pipeline/readiness/` files and current owner receipts are
the operational checks, not this example. `OPEN` (respective human owners):
scientific qualification, security acceptance, protocol lock, LIVE/launch and
customer claims. This packet earns none of them.
