# What "representative scale" means, fixed before the run

Written 2026-09-21, before any device time is spent. Owner-directed: define the
target against something real and write down the justification, so that
"representative" means a stated scale rather than "bigger". Same discipline as
the two-host plan fixing its candidate separation in advance.

---

## 1. The target

| Surface | Value | Why this value |
| --- | --- | --- |
| `width` | **32** | The width Carbon's own research campaign configures |
| `n_modes` | **16** | The registered catalog default, and the campaign's value |
| `steps` | **32** | The authorized envelope's per-invocation maximum |
| `backbone` | `fno` | The backbone the mode count applies to |

Baseline for comparison with every prior result: `width=8`, `n_modes=8`,
`steps=2`.

**Measured parameter counts**, from a real CPU reconstruction at each shape:

| Shape | Leaves | Parameters |
| --- | --- | --- |
| `width=8, n_modes=8` (all prior evidence) | 71 | **4,696** |
| `width=32, n_modes=16` (target) | 71 | **100,680** |

21.4x more parameters, and - the part that matters - **different tensor shapes**.

## 2. Where these numbers come from

Not judgement. The registered catalog `carbon.burgers-autoresearch-recipes.v1`
in `carbon/development_session/research_catalog.py`, whose own comment describes
its bounds as *"engineering admission bounds, not quality or scientific claims"*:

| Surface | Min | Max | **Catalog default** |
| --- | --- | --- | --- |
| `width` | 2 | 128 | **24** |
| `n_modes` | 2 | 64 | **16** |
| `depth` | 1 | 8 | **2** |
| `steps` | 2 | 1,000,000 | **512** |

And what Carbon actually configures when it runs research:

| Source | steps | width | depth | n_modes |
| --- | --- | --- | --- | --- |
| `research_campaign.py` | 512 | **32** | 3 | **16** |
| `research_service.py` | 512 | 24 | 2 | **16** |
| `reconstruction/profile.py` defaults | 2 | **8** | 1 | **8** |

The reconstruction defaults - the shape every determinism result Carbon holds was
measured on - sit **below the catalog minimum-useful region and far below every
configured recipe**. `width=8` is a third of the catalog default and a quarter of
the campaign's; `n_modes=8` is half the catalog default.

The target takes the campaign's `width=32` rather than the catalog default of 24
because it is the value Carbon actually configures for research, and because it
sits inside the width 32-64 band typical of real PDE surrogates.

## 3. Why shape, and not just step count

This is the reason the fixture was widened before spending device time rather
than after.

With `--xla_gpu_autotune_level=0` pinned - which the validator determinism policy
requires - **the kernel is fixed per shape**. A larger step count runs the *same*
kernel more times. A different width or mode count selects a **different fixed
kernel, whose determinism has never been measured**.

So a steps-only experiment would exercise one kernel path more often and say
almost nothing about the paths a real workload takes. It would also invite
exactly the overclaim that had to be retracted from the W3 and W5 packets, where
divergence was assumed to compound with step count and measurement showed it does
not.

There is a second reason. Width and modes change *reduction sizes*: the FNO's
spectral multiply and its channel mixing both accumulate over dimensions set by
these surfaces. Accumulation order within a reduction is where floating-point
divergence originates. Step count leaves those reductions the same size.

## 4. What this target is not

Stated plainly, so the result is not read as more than it is.

**It is not representative in training length.** The catalog default is 512
steps; the target is 32, because that is the authorized envelope's per-invocation
maximum. The run is therefore **16x short** on length while being close on shape.
That is the right trade under the envelope - shape selects kernels, length
repeats them - but it is a limit and not a completed question.

**`depth` is not widened.** It stays at the reconstruction default of 1, against
a catalog default of 2 and a campaign value of 3. Widening it was outside the
scope of this change, which the owner defined as width and modes. Depth adds
layers of the same shapes, so it is closer in character to step count than to
width; it should be widened before any claim that the full configured recipe has
been exercised.

**One device, one backbone, one workload.** The same scope limit every
same-device result carries.

**Nothing here is a scientific claim about model quality.** The catalog's own
comment says its bounds are engineering admission bounds. A 100,680-parameter
model is not asserted to be good, only to be the shape Carbon's registered
material describes.

## 5. What the run can and cannot conclude

**Can conclude:** whether the pinned determinism configuration still produces one
weight digest across fresh processes when the kernels change. That is the
assumption `VALIDATOR_GPU_DETERMINISM_POLICY.md` rests on and it has only been
tested at one shape.

**Cannot conclude:** anything about cross-device agreement, which remains
unmeasured and is the two-host study's question; anything about behaviour at 512
steps; or anything about a deeper model.

**If pinned determinism fails at this shape, that is the finding**, it outranks
the two-host study, and it should stop that study as premature rather than be
worked around.

## 6. Status

`SPECIFIED`. The fixture change that makes this expressible is implemented and
tested and is device-free. No device time has been spent against this target.
