# Gate robustness under cross-device divergence: options for the owner and SCI

Recorded 2026-09-20 under programme #209, ticket C-CORE-19, work package item D5.

**Nothing here is implemented, and nothing here should be.** This is a protocol
and scientific decision for the owner and SCI. Engineering's job was to state the
problem precisely, lay out the options with their trade-offs, and stop. No
threshold was changed, no tolerance was chosen, and no gate behaviour was altered.

## 1. The problem, stated exactly

Pinned determinism gives same-device reproducibility. It does **not** make two
different GPU models agree, and no setting will - different streaming-
multiprocessor counts and memory hierarchies produce different floating-point
results from identical inputs. The same is true across CPU instruction-set
levels, measured earlier and independent of any device.

So residual divergence between validators is permanent. The question is what it
meets on the way to a verdict.

`carbon/scoring/engine.py`:

```python
passed = score_input.numeric_value(gate.input_key) < threshold
...
if any(decision.mandatory and not decision.passed for decision in gate_decisions):
    return InternalResult(ScoreStatus.MANDATORY_GATE_FAILED, ...)
```

The continuous legs absorb a small difference proportionally: a metric that moves
by ε moves the score by something like ε. **A mandatory gate does not.** It is a
step function with a strict comparison, and a failure rejects the whole
submission rather than deducting from it.

> Two validators whose metric lands either side of a threshold do not disagree
> slightly about a score. One scores the submission and the other rejects it.

That is the asymmetry. Divergence is noise in the legs and unfairness at a gate.

## 2. What is and is not measured

Measured: cross-instruction-set divergence on CPU - `6.105e-04` relative on
trained parameters, `1.264e-06` on model predictions, both at a two-step
workload, both floors. Cross-session GPU divergence unpinned, eliminated by
pinning on one device.

**Not measured**: divergence between two *different* GPU models, which is the
quantity these options are really about. It cannot be measured under a zero-spend
constraint with one device. Any option chosen below should be sized against a
real cross-device number, not against the CPU figures used here for scale.

Also not measurable today: how close real inputs sit to real thresholds. **No
production Score Pack exists** - only synthetic A5 fixtures - so the margin
question is open by default rather than answered.

## 3. Option A - mandate margins relative to measured divergence

Require every mandatory gate to carry a margin: typical inputs must sit at least
*k* times the measured cross-device divergence away from the threshold, with *k*
and the divergence both recorded.

*For.* Keeps gates per-validator and needs no protocol change. It is a discipline
on Score Pack authoring rather than new machinery.

*Against.* It needs a cross-device divergence number that does not exist yet, so
it cannot be applied today. It also constrains what a gate can express: a gate
whose scientific meaning genuinely sits near a threshold cannot be given a margin
without changing what it tests. And a margin makes the gate safe only for inputs
in the typical mass - a legitimate submission in the tail still straddles it.

## 4. Option B - decide gate admissibility once, not per validator

Evaluate mandatory gates from a single reference run, or from a consensus median
across validators, and have every validator apply that admissibility decision
rather than computing it independently.

*For.* Removes the flip entirely. Every validator reaches the same admissibility
answer because there is only one, and the continuous legs - which absorb
divergence gracefully - stay per-validator where they belong. It also needs no
divergence measurement to be correct.

*Against.* It is a real protocol change with its own failure modes. A reference
run is a trust concentration: whoever produces it decides admissibility, which is
exactly the centralisation independent reconstruction exists to avoid. A
consensus median needs enough validators, a tie-break rule, and a defence against
a minority steering the median. And it changes what a validator *is* for this one
decision, which is a scientific question about what independent verification
means, not an implementation detail.

## 5. Option C - make gates tolerant by construction

Express mandatory gates so that a near-threshold value is not decisive: a band
rather than a point, with values inside the band resolved by a registered
procedure rather than by a strict comparison.

*For.* Addresses the step function directly rather than working around it.

*Against.* It requires the registered procedure that does not exist, and it is
the option most easily mistaken for choosing a tolerance to make hardware pass.
It is only legitimate if the band is a scientific statement about the gate's
meaning - the range in which the gate genuinely does not discriminate - and not a
number picked to absorb hardware noise. If it cannot be justified without
reference to hardware, it is the wrong option.

## 6. Option D - accept it, and record it

Change nothing, and state in the protocol that near-threshold submissions may
receive different verdicts from different validators.

*For.* Honest, costs nothing, and does not pretend to a fairness property Carbon
does not have. It may be the right answer if margins turn out to be wide.

*Against.* It is only acceptable if the frequency is genuinely negligible, which
nobody can currently say, because no production Score Pack exists and no
cross-device divergence has been measured. Choosing it without those two numbers
is not a decision, it is a deferral.

## 7. What engineering recommends about the order

Not which option - that is not engineering's call. But the sequence is:

1. **Measure cross-device divergence** on the hardware validators will use. Every
   option above is sized by it, and Option A cannot be applied without it.
2. **Author a production Score Pack**, or at least a candidate, so margins can be
   computed against real thresholds and real inputs.
3. **Then choose.** With those two numbers, the options separate cleanly; without
   them, any choice is a guess.

Until both exist, the risk is real but unquantified, and saying so is more useful
than an implementation that encodes a guess.

## 8. What must not happen

No threshold should be adjusted to accommodate hardware. If a margin turns out
too narrow, that is a scientific decision about the gate, not a licence to move
the number until the hardware fits. The same rule that forbids choosing a
tolerance to make a device pass forbids moving a gate to the same end.
