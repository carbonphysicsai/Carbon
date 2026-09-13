# CPES reference-reuse gauntlet continuation protocol

**Protocol:** `carbon.cpes-reference-reuse-gauntlet.protocol.v2`  
**Frozen configuration:**
`.agent/preregistrations/EXAM-PROTECT-01_reference_reuse_gauntlet_v2.json`  
**Issue:** [EXAM-PROTECT-01 #142](https://github.com/carbonphysicsai/Carbon/issues/142)  
**Pinned research baseline:** `d94a22bb3c09089e01402db9e7ebf6eb3c662966`

This study is a detached falsification exercise. It neither selects nor changes
any Wave C ticket, and it cannot write shared membership, reference answers,
scores, rewards, disclosure state, or launch authority into Carbon runtime
owners.

## Decision and hypotheses

The decision is whether fresh common packs for compatible jobs already
committed at dispatch merit a later, separately authorized Engineering
proposal. The null is to retain Variant A. Variant B must show conditional
recurring reference savings without weakening the fixed security floor.
Variant C must show a decision-relevant incremental advantage over B to justify
deliberate waiting. The repeated hidden-bank arm is a vulnerable control, not a
candidate policy.

The protocol tests these alternatives:

1. immutable pre-exposure membership, exact cache identity, pack closure and
   restricted feedback reject the modeled reuse attacks;
2. shared packs reduce reference work only when compatible jobs coexist and
   the saved reference cost exceeds incremental group work;
3. shared closure delays fast members and can correlate reference failure;
4. exact repeated feedback over a finite bank permits adaptive extraction;
5. absent demand, qualified reference cost, lineage, custody and integrity
   evidence keeps any deployment recommendation conditional.

## Evidence and observation boundaries

The original v0.2 bundle supplies historical model semantics and attack IDs.
Its unchanged harness is rerun separately before this continuation. New
results identify whether they came from the in-memory model, a disposable
SQLite research prototype, an existing tested repository interface, or a
counterfactual replay. These layers are never collapsed.

The persistent prototype records only synthetic digests and transition events.
It exercises atomic membership, exact cache binding, closure, stale writes,
restart and forged authority. It is under `scripts/dev`, uses a disposable
database, and is not imported by production packages. A passing prototype is
not evidence for an unimplemented production Variant B.

The operating replay uses one serial validator resource, fixed arrivals and a
finite horizon. Each declared overhead scenario recomputes dispatch and group
membership. A zero-overhead result is a scenario, never a universal bound.
Variant C observes arrivals only as simulated time advances and uses the frozen
wait; it does not select a group using outcomes or future service times.

## Information-reuse experiment

Candidates are frozen before fresh-pack realization in A/B/C. The attack API
exposes only the configured summary. The vulnerable D arm returns an exact
score against a fixed synthetic bank. One baseline plus one single-bit flip per
case reconstructs the bank; accuracy is then measured on the reused bank and
an independently generated held-out bank. Cases are whole bits, not adjacent
coordinates. The result demonstrates exploitability of that interface only.

The original publication proxy remains historical. Its 72.5% exact overlap is
a deliberately finite example and is not rerolled into an expected Carbon
overlap rate.

## External-result boundaries

[Dwork et al.](https://papers.nips.cc/paper_files/paper/2015/file/bad5f33780c42f2588878a9d07405083-Paper.pdf)
show that adaptive holdout reuse needs a particular information-limiting
algorithm and assumptions; ordinary repeated access can overfit. The
[Ladder paper](https://arxiv.org/abs/1502.04585) studies a narrower adaptive
leaderboard guarantee, not Carbon physical-reference qualification. The
[drand protocol](https://docs.drand.love/docs/specification/) describes public,
verifiable beacon output; public verifiability is not active-case secrecy.
[drand timelock documentation](https://docs.drand.love/docs/timelock-encryption/)
describes time-based release and its threshold assumptions, not proof that a
Carbon pack's answer-dependent work is closed.

These are external scientific/technical results. Carbon's reuse design remains
a hypothesis, this harness is a proposed Carbon experiment, and no qualified
Carbon evidence is created.

## Stop and acceptance rules

Run the frozen grid once with seed `20260914`. Retain failed, cancelled,
unresolved and underfilled work. Do not tune parameters after seeing whether B
looks favorable. Stop any affected claim on an invariant failure, inconsistent
reference requirements, future-information use, missing unit, accounting
imbalance or non-deterministic replay. The five original blockers AT-09,
AT-16, AT-19, AT-22 and AT-30 remain blocked unless their owning evidence—not
this model—changes.
