# Dated mechanisms and failure evidence

All sourced constants below are **fixed low = base = high**, not uncertainty
intervals. Historical different values are versions, not an uncertainty range.
Implementation inspection establishes the published algorithm, not that every
validator deployed it. Operator reports remain operator reports. Source pins
and verification gaps are in [SOURCES](SOURCES.md).

| Contest | Margin and comparison | Accumulation, seeds and copying | Carbon lesson |
|---|---|---|---|
| SN30 Endure, current primary docs | Realized financial outcomes score forecasts and feed miner EMAs; no model-crown epsilon found | Commit/reveal, deterministic recorded outcomes and multiple horizon resolution; no sourced paired model final | Include as a requested negative finding. Do not borrow a nonexistent model-takeover rule |
| SN97 Distil, code at 8875153 (2026-05-20) | `is_dethrone` uses `challenger.final >= king.final*(1+margin)`; default 0.05 relative; requires enough axes on both sides and a worst-axis floor | Operator's April report describes king re-evaluation on shared procedural items and one evaluation per non-king commitment. May code selects among persisted composites; a paired statistical CI is not required by the crown function | A refreshed king alone does not prove every persisted challenger is a shared-fresh comparison; match evidence identities explicitly |
| SN120 Affine, historical dd0d03d (2026-09-27) | Historical per-duel paired mean must exceed `max(k_sigma*SE, delta)`; per-byte era delta 0.002, k_sigma 2; later normalized era delta 0.2 teacher-SD units | Reveal-block-hash/hotkey selects shared stratified turns; disjoint near-miss/confirmation slices existed in dated forks; confirmation was removed in wvk21. Sequential look code exists but its planned activation must be distinguished from the pinned effective rule | Shared data and a noise-aware bar are useful; absolute floors, selected-positive pooling and sequential peeking still need explicit error control |
| SN91 Cascade, code at 0fba3c0 (2026-10-10) | Paired bootstrap lower bound clears margin; fresh margin 0.01 to floor 0.005 over 8 held rounds in pinned config; increment normalization is block-activated | Shared initialization/training settings; private shared eval windows; source clusters; cohort max-T correction. Config determines consecutive-win requirement, not a generic claim that every round requires multiple wins | Strong analogue for clustered inference and multiple challengers. A decaying practical margin eases entry, but cannot replace statistical control |
| SN112 Minotaur, docs last-update label 26.05.22 | Exact delivered output on the same fork/order set; net breadth wins minus regressions must be at least 1; ties inside 0.1%; no catastrophic >1% loss or dropped order | Fully matched output ties may use metered gas or structural code metrics; no statistical CI described on the cited page | Deterministic tolerances and secondary resource objectives can resolve meaningful ties, if registered as part of the Challenge rather than invented at takeover |
| Stockfish Fishtest, official docs | Sequential probability ratio testing with declared null/alternative and type-I/type-II errors; short and long time-control stages | Opposite-color game pairs and pentanomial statistics account for within-pair dependence; FAQ warns about repeated lucky tries | A genuine accumulating-evidence test has a stopping contract; repeat-until-significant is not one |

Sources: [Endure validator overview](https://docs.endure.network/build/validators/overview),
[SN97 crown code](https://github.com/unarbos/distil/blob/88751532bea283d812df98c0b8e304465344eed0/distil/eval/composite.py#L479),
[SN97 April round contract](https://github.com/unarbos/distil/blob/88751532bea283d812df98c0b8e304465344eed0/reports/2026-04-29-v30.2-rollup.md#L85),
[historical SN120 duel execution](https://github.com/AffineFoundation/affine/blob/dd0d03d8ffae2ed944e1d3c22d2a8af03b80414c/affine/evalsrv/dueling.py),
[Cascade config](https://github.com/TensorLink-AI/cascade/blob/0fba3c0dcfd38aa6f9901ba4a9ec3f4ec20d843e/chain.toml#L682),
[Minotaur rules](https://docs.minotaursubnet.com/miner/overview/#championchallenger-model),
[Fishtest methodology](https://official-stockfish.github.io/docs/fishtest-wiki/Creating-my-first-test.html).

## What the failures actually establish

**Noise crowns, SN97.** The May variance-reduction report says the operator saw
copy-like challengers cross the earlier 0.03 margin through noise. It raised the
margin to 0.05 and increased evaluation counts. Its approximate false-positive
figures are modeled, not a counted independent live error-rate study. The report
says <8%; the README says <6%. Do not treat either as a measured guarantee or
resolve the discrepancy by choosing the more attractive number. A bootstrap
gate and multi-round confirmation were explicitly deferred.
[Operator report](https://github.com/unarbos/distil/blob/88751532bea283d812df98c0b8e304465344eed0/reports/2026-05-10-variance-reduction.md#L82).

**Incomparable records, SN97.** The crown code documents spurious dethrones
during the May cutover when a sparse/legacy king was treated as an open seat.
The repair requires enough current axes on both sides. This is a source-backed
implementation incident, not an independently reconstructed chain payout event.
[Code and failure explanation](https://github.com/unarbos/distil/blob/88751532bea283d812df98c0b8e304465344eed0/distil/eval/composite.py#L485).

**Copier win, historical SN120.** The operator's history reports a re-upload of
the same tensors with different shard boundaries passed file-level hashes and
crowned under the window-best rule's pooled-positive test. The crown was revoked.
This supports canonical tensor/artifact identity and selection-adjusted
confirmation. It does not prove a universal error probability for all copies.
[Dated incident](https://github.com/AffineFoundation/affine/blob/dd0d03d8ffae2ed944e1d3c22d2a8af03b80414c/affine/website/llms.txt#L517).

**Too hard to displace, historical SN120.** A required second slice was removed;
the history records one challenger blocked only by confirmation and a subsequent
retroactive crown. This is evidence of the operational power/latency trade-off,
not proof the blocked candidate was truly better. Carbon should retain original
verdicts and make policy changes prospective.
[Dated reversal](https://github.com/AffineFoundation/affine/blob/dd0d03d8ffae2ed944e1d3c22d2a8af03b80414c/affine/website/llms.txt#L448).

**Anti-copy false positives, Cascade.** Its config records a confirmed false
positive in approximate source-similarity filtering and restricts rejection to
exact identity classes. Functional probe-output equivalence is an explicit
configurable seam. Similarity can flag review, but is not proof of theft or lack
of value. [Pinned dedup policy](https://github.com/TensorLink-AI/cascade/blob/0fba3c0dcfd38aa6f9901ba4a9ec3f4ec20d843e/chain.toml#L510).

**Dependence, Fishtest.** A maintainer's public issue measured dependence within
game pairs and motivated pentanomial variance. The lesson is the sampling unit,
not importing chess effect sizes into physics.
[Maintainer analysis](https://github.com/official-stockfish/fishtest/issues/348).

No independently audited public frequency of stagnant kings, lucky crowns or
copier payouts across these subnets was found. Long tenure alone does not prove
stagnation: the challenger may lack value, power, eligibility or budget. No such
frequency is invented here. No SN30 model-crown failure was verified.

## Version and seed cautions

SN120's [current guide](https://affine.io/llms.txt) now describes a different
contribution/training protocol. Its older KOTH pages are historical evidence,
not current instructions. SN97's May code allows recent-kings payout, whereas
its README still describes winner-take-all; promotion and payout are distinct.
[SN97 current emission builder](https://github.com/unarbos/distil/blob/88751532bea283d812df98c0b8e304465344eed0/distil/eval/king.py).

A public future block hash can make the next selected subset unavailable before
commitment under the protocol's assumptions. It does **not** make a public corpus
secret or prove resistance to identity grinding, timing, chain influence or
memorization. Carbon's hidden seeds, protected material, delayed publication and
allowlisted evidence must remain its own registered custody policy. Do not
import another subnet's public seed/verdict disclosure.
