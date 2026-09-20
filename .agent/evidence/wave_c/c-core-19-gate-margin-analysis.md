# Gate margin analysis (W5)

Recorded 2026-09-20 under programme #209, ticket C-CORE-19.
Analysis only. **No threshold was changed**, and none should be changed on the
strength of this document. It is scoring-side, involves no GPU, and its purpose
is to decide whether numeric variation between hosts can flip a submission's
outcome.

## 1. The mechanism, confirmed in code

`carbon/scoring/pack.py` requires at least one mandatory hard gate. Evaluation in
`carbon/scoring/engine.py`:

```python
passed = score_input.numeric_value(gate.input_key) < threshold
...
if any(decision.mandatory and not decision.passed for decision in gate_decisions):
    return InternalResult(ScoreStatus.MANDATORY_GATE_FAILED, ...)
```

Three properties matter:

1. **Strict less-than against a bare threshold.** A value exactly at the
   threshold fails.
2. **A mandatory gate failure rejects the whole submission** — `MANDATORY_GATE_FAILED`,
   not a deduction.
3. **A gate is a step function.** The continuous legs absorb a small numeric
   difference proportionally; a gate does not. It flips.

So the risk is specific and asymmetric: a difference far too small to matter
anywhere else can change a submission from scored to rejected, if it happens to
straddle a threshold.

## 2. The margin question cannot be answered today

The task is to ask, for each mandatory gate in the registered Score Packs, how
close a typical input sits to its threshold in units of the noise from W3.

**There is no production Score Pack in this repository.** The only packs present
are three synthetic A5 fixtures under `tests/fixtures/score_packs/`, and all
three carry the same synthetic gates:

| Gate | Operator | Threshold | Mandatory |
| --- | --- | --- | --- |
| `synthetic_error_gate` | `less_than` | `1.0` | yes |
| `synthetic_finite_gate` | `boolean_true` | — | yes |
| `synthetic_optional_diagnostic` | `less_than` | `2.0` | no |

These are fixtures. Their thresholds were chosen to exercise the engine, and
their inputs are fixture values. Computing a margin from them would produce a
number with no relationship to any real submission, and quoting it as a margin
would be worse than reporting nothing.

> **Reported rather than invented: the margin is not computable today, because
> the thing it would be computed against does not yet exist.**

## 3. What can be said, and is

The risk is not hypothetical even though the margin is not yet measurable,
because the noise is measured and the mechanism is confirmed.

From W3, between CPU instruction-set levels, on identical R0 identities. A gate
acts on a metric computed from model **output**, not on parameters, so both were
measured and the output figure is the one that governs:

| Level | Differing | Max absolute | Max relative |
| --- | --- | --- | --- |
| Trained parameters | 2660 / 4696 (56.6%) | `2.086e-07` | `6.105e-04` |
| **Model predictions** | 11 / 64 | **`1.746e-10`** | **`1.264e-06`** |

The output divergence is roughly five hundred times smaller than the parameter
divergence. That is expected at this training length — after two steps the
predictions are still dominated by the shared initialisation — and it is the
reason the parameter figure must not be used as the margin yardstick. Quoting
`6.1e-4` as the metric noise would overstate the risk by about that factor.

Both figures are measured after **two training steps**, the shortest run the
fixture permits, so both are **floors**. Parameter divergence compounds with step
count and output divergence follows it; the envelope allows 32 steps, sixteen
times longer, and that measurement is not available (see W3 §4).

The usable rule, stated against the quantity that matters:

> **A mandatory threshold is unsafe if typical inputs sit within roughly `1e-6`
> relative of it — and that is a lower bound from the shortest possible run, not
> a safe margin.**

What this does *not* license is the conclusion that the risk is negligible. A
floor measured at two steps says little about a real training run, and the
mechanism — a step function acting on a host-dependent quantity — is unchanged by
the magnitude.

Two validators on hosts with different CPU feature levels would then disagree not
by a fraction of a score, but on whether the submission is admissible at all.

The boolean gate deserves separate mention. `synthetic_finite_gate` fails on a
non-finite input. Divergence at the magnitude measured will not by itself turn a
finite value into a NaN, but a computation already near an overflow or a
divide-by-zero could resolve differently on two hosts. That is a narrower risk
than the threshold case and is noted rather than quantified.

## 4. What should happen when a production pack is authored

Not a change to anything today — a check to apply then:

1. **For each mandatory gate, measure the distribution of typical inputs against
   its threshold.** Not the best case; the mass of real submissions.
2. **Compare that distance to the cross-host divergence of that specific
   metric** — measured on the metric itself, not on parameters, and at the step
   count real submissions use. The two differ by orders of magnitude.
3. **If any threshold sits within the divergence of typical inputs, that is a
   design problem** and belongs in front of the owner before any validator runs
   on any backend — not only on GPU. The measured divergence is a CPU
   phenomenon.

A gate whose margin is wide relative to the noise closes this risk. A gate whose
margin is narrow does not become safe by being left alone.

## 5. Scope

Read-only inspection of `carbon/scoring/pack.py`, `carbon/scoring/engine.py` and
the three fixture packs, plus the W3 measurements. No Score Pack was modified, no
threshold was changed, no scoring run was executed, and nothing here qualifies or
accepts anything.

## 6. For the owner

1. **A production Score Pack does not exist yet**, so the margin question is
   open by default rather than answered. When one is authored, §4 is the check.
2. **The risk is not GPU-specific.** It is created by cross-host numeric
   divergence, which W3 measured on CPU. A GPU would add to it, not create it.
3. **No threshold should be adjusted to accommodate hardware.** If a margin turns
   out to be too narrow, the answer is a scientific decision about the gate, not
   a tolerance chosen to make hosts agree.
