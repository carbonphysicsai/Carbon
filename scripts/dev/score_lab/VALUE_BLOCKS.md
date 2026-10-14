# Synthetic value-block uncertainty (OPT-15c section E)

The existing `core.analyze` Python API accepts an optional `value_blocks` spec.
Without it, every existing path remains unchanged. This is fixture-tested lab
plumbing, not a completed block study or a production reference policy.

```python
from scripts.dev.score_lab.core import analyze

spec = {
    "schema": "carbon.dev.score-lab-value-blocks.v1",
    "label": "ASSUMPTION: illustrative independent synthetic draw blocks",
    "groups": {
        "a": ["V-0", "V-1"],
        "b": ["V-2", "V-3"],
        "c": ["V-4", "V-5"],
    },
    "missing_policy": "REQUIRE_COMPLETE",
}
result = analyze(panel, rule, value_blocks=spec, bootstrap=200, seed=42)
```

The names above are synthetic examples. The partition must cover every value
question exactly once, with 3-30 equal-size blocks as in the experiment plan.
No grouping, production draw unit or independence is inferred from IDs.
Unequal sizes refuse: they require an explicit weighting/statistical contract
outside this slice. There is no new CLI flag, coefficient or adopted threshold.

Each member's value losses are averaged within each complete block. Equal
original block sizes preserve the uniform-question point mean. The unchanged
`score_proof.bootstrap` then crosses recipe resampling with complete BLOCK
resampling, not independent resampling of correlated cases within each block.
Its intervals remain conditional on fixed scoring cases and the supplied
synthetic block-independence assumption; the code does not prove independence
or adequacy of three blocks. No population P/proposal Q/weighting w is registered.

`REQUIRE_COMPLETE` leaves the entire measurement unscored if any block is
incomplete. `EXCLUDE_COMPLETE_BLOCKS` excludes every incomplete block for all
members and controls. Otherwise resolved questions in such a block are also
excluded and counted. The estimand is conditional on complete blocks; missing
data are not imputed and no candidate penalty is introduced. Fewer than three
complete blocks leaves the measurement unscored without invoking the scorer.

`value_questions` and `value_questions_offered` retain ORIGINAL question units.
`value_resampling_units` reports the complete-block count used by the bootstrap.
`value_block_measurement` binds spec/input/analysis/mask digests and separately
reports offered and available/scored questions and blocks, unresolved questions,
incomplete blocks and resolved questions excluded with those blocks.

The scorer receives the same score references, predictions, metadata and gates;
block accounting is outside its callback. Inputs are copied. Optional absent
oracle data retains the existing best-member regret interpretation. Public
panels refuse this option. No real/hidden/holdout data, model, reference solver,
paid campaign, registered scoring-rule change or qualification is involved.
