# Cooling 1.8 default model: E1

E1 is the model Carbon ships as the Cooling 1.8 (`chip-cold-plate` 1.8) default. It is one submission on the graph route.

## What it is

E1 starts from the public textbook model of a microchannel cold plate (`spec/prior.py`). It adds a learned correction on top
of that model, plus a separate small learned head for the pressure output. Three copies are trained with different seeds, and
their predictions are averaged.

- The textbook part takes nothing from TRAIN. Its scales are fixed physics scales.
- Only the learned parts are fitted, on TRAIN, by Carbon's graph trainer, from a keyed start.
- Before launch, E1 cleared the Cooling 1.8 physics gate on a fresh set of in-range cases on every one of 3 seeds, for both
  graded outputs.
- How it was chosen: a fresh gate set was drawn after two failed reads on an earlier set. E1 was then picked by
  cross-validation on TRAIN only, among 3 new and 9 earlier candidates. Cross-validation is slightly optimistic, so the one
  read on the fresh gate set is the unbiased check.

## Files

| Path | What |
|---|---|
| `spec/d6v_spec_head.py` | The graph spec you lower. It loads `spec/d6_spec.py`, which loads `spec/prior.py`. |
| `config_E_ensemble3.json` | The training configuration: 6000 steps, batch 366, 3 members averaged, output weights. |
| `submission/` | The spec already lowered: `manifest.json` and its two documents. |

The submission digest is `sha256:7fa5a63f692e7a780a31d4d31d71294530354abcfbf9ae56dd33f1f85cbc0e59`.

## Lower it yourself (optional)

`submission/` is the output of this command. Run it to check that you get the same digest.

```bash
python -m carbon.level4.tooling lower kits/cooling-default-1.8-e1/spec/d6v_spec_head.py OUT_DIR \
    --challenge chip-cold-plate --challenge-version 1.8 \
    --interface sha256:849275fb67c5766452d2bbc1f6da691c553630a89026f5bd1048a70b97d2c12a --batch 366
```

It needs JAX (the `science-jax` extra). It prints the submission digest, which must equal the one above.

## Submit it

Submit `submission/` with `config_E_ensemble3.json` as its configuration, to Cooling 1.8 on the graph route. Follow your
usual submit steps in the Control Center (see `docs/MINING.md`).

This folder holds no hidden or exam data. `tests/cpu/test_cooling_default_18_e1.py` checks these points:
- every file here is pinned;
- the spec lowers to this submission;
- Carbon's own Cooling 1.8 graph intake admits it.
