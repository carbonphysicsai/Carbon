# Burgers v1 — JAX/Flax FNO Neuraloperator Parity Port

**Status:** DRAFT — design note, pending review. Not yet implemented.
**Purpose:** map the official PyTorch `neuraloperator` FNO architecture to a
JAX/Flax Linen port module-for-module, specify how that port and a new
periodic Cole–Hopf reference plug into the Burgers v1 exam flow described in
`docs/context/Carbon_Independent_Exam_Burgers_v1.md`, and record what is
deliberately deferred from that document's full uncertainty-quantification
apparatus.
**Related:** `docs/context/Carbon_Independent_Exam_Burgers_v1.md`,
`Design_Specs/POC_Burgers_FNO.md`, `Design_Specs/Scoring.md`,
`Design_Specs/Scoring_Formulas.md`, `docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md`,
`docs/context/MASTER_OPEN_DESIGN_QUESTIONS.md` (MQ-001, MQ-004, MQ-005),
upstream `github.com/neuraloperator/neuraloperator`.

---

## TL;DR

**Goal:** a JAX/Flax Linen FNO whose module boundaries mirror
`neuralop.models.FNO` (lifting → `FNOBlocks` → projection, with `SpectralConv`
and `ChannelMLP` as named submodules), proven numerically equivalent to the
PyTorch original via shared-weight forward-pass diffs, plus a new periodic
Cole–Hopf reference solver and doc-exact gates/scoring — wired into a new,
clearly-labeled **pre-LIVE** Burgers v1 exam harness.

**What this note is not:** a change to the ratified A5 `carbon/scoring/`
engine or the ratified A2 `carbon/schema/strategy.py` contract. Both are under
versioned-change governance (`Design_Specs/Scoring.md` §11,
`CONSTITUTION.md` §5–6) and out of scope here. This work produces new,
separately-labeled code that computes the exam doc's formulas directly, for
dossier-building and mechanism-proving — not a new LIVE Score Pack.

**Existing code found along the way that this note does *not* fix:** a
fixed-vs-ranged viscosity conflict with ratified MQ-001, a broken kwarg
mismatch in `carbon/backbones/neural_operator.py`, and three formula
divergences between the exam doc/`Scoring.md` and the PoC's live
`poc/eval/score.py`. All flagged in §6, none touched by this branch.

---

## 1. Scope

**In scope:**
- `SpectralConv1D → ChannelMLP1D → FNOBlocks1D → FNO` Flax Linen port,
  specialized to 1D real-valued data, dense (non-factorized) weights, no
  domain padding, no resolution scaling, no complex-valued data path.
- Cross-framework parity tests at each layer (shared weights, diffed
  outputs, stated fp32 tolerance).
- A periodic Cole–Hopf reference solver for fixed ν, numerically stable at
  small ν (§9 of the exam doc).
- A fixed-ν (5×10⁻³), zero-mean bounded-Fourier IC generator for this new
  flow (doc §6).
- The four mandatory gates from doc §14 (finite, energy non-increase, mean
  conservation, maximum-principle consistency).
- Soft scoring exactly as specified in doc §15–18 (quadratic-barrier
  physics, tail-logistic robustness over physics-derived stress strata,
  reference-relative-L2 accuracy, weighted-geometric combination).
- A small integration test from seed → score on a fixed, eyeballable case
  set.

**Out of scope (see §7 for the full deferral list):** the §11 uncertainty
campaign, the §13 adversarial reference-bias campaign, the §21 Validation
Dossier, tensor-factorized/complex-valued/domain-padded FNO variants, any
change to `carbon/scoring/`, `carbon/schema/strategy.py`, or
`poc/eval/{gates,score}.py`.

---

## 2. Where this lives

New code, not a rewrite of existing PoC modules:

```text
poc/models/fno_neuralop/          # JAX/Flax FNO port (neuraloperator-parity)
    __init__.py
    embeddings.py                  # GridEmbedding1D
    channel_mlp.py                 # ChannelMLP1D
    spectral_conv.py               # SpectralConv1D
    fno_block.py                   # FNOBlocks1D
    fno.py                          # FNO (top-level Linen Module)

poc/challenges/burgers_v1/        # new doc-exact exam harness (pre-LIVE)
    __init__.py
    generator.py                    # fixed-nu, zero-mean bounded-Fourier IC (doc §6)
    reference_cole_hopf.py          # periodic Cole-Hopf reference (doc §9)
    stress.py                       # k_rms / U_rms / Re_eff / steepening-index strata (doc §17)
    gates.py                        # 4 mandatory gates (doc §14)
    scoring.py                      # doc-exact soft scoring (doc §15-18)
    run_exam.py                     # seed -> {candidate, cole-hopf} -> gates -> score

tests/cpu/test_fno_neuralop_parity.py   # cross-framework parity (skips if torch/neuralop absent)
tests/cpu/test_cole_hopf_burgers.py      # heat-equation exactness, periodicity, rescaling invariance
tests/cpu/test_burgers_v1_gates.py
tests/cpu/test_burgers_v1_scoring.py
poc/tests/test_burgers_v1_integration.py # small seeded end-to-end integration test
```

**Why a new tree instead of extending `poc/models/fno1d_jax.py` or
`poc/eval/{gates,score}.py` in place:** those existing modules back the
current PoC lean-loop harness (`poc/train/loop.py`,
`poc/validator/run_once.py`) and its own test suite (`poc/tests/`), which
was built to "prove the mechanism" with deliberately simple placeholder
formulas (§6 below), not to be doc-exact. Silently rewriting their formulas
would be a breaking behavioral change to a harness with its own tests and
its own stated purpose, and is a separate decision from porting an FNO
architecture. §6.4 flags this as an open reconciliation question rather than
deciding it here.

**Dependencies:** parity tests need both the JAX stack (`poc` extra) and the
real PyTorch `neuraloperator` package (`neuraloperator` extra). Neither
extra alone is enough; install `pip install -e ".[poc,neuraloperator]"` for
local parity testing. Propose adding `flax>=0.9` to the `poc` extra (only
`jax`/`numpy`/`pyyaml` currently listed). Parity tests should
`pytest.importorskip` both stacks so default CI (whichever extras are
installed) stays green, and should be registered in `poc/tests/conftest.py`'s
existing `(file, test_name)` allowlist pattern under `backend_jax`; a new
`backend_torch` marker (registered in `pyproject.toml`) is proposed for the
PyTorch-side requirement, following the same classification-not-autouse
convention already used for `backend_jax`.

---

## 3. Module mapping

| PyTorch (`neuralop`, current `main` @ `00b7d86`) | Flax Linen port | Notes |
|---|---|---|
| `neuralop.models.fno.FNO` | `poc.models.fno_neuralop.fno.FNO` | Same constructor shape where JAX idioms allow: `n_modes`, `in_channels`, `out_channels`, `hidden_channels`, `n_layers`, `lifting_channel_ratio=2`, `projection_channel_ratio=2`, `positional_embedding="grid"`, `non_linearity=gelu`, `fno_skip="linear"`, `channel_mlp_skip="soft-gating"`. Fixed at `None`/defaults for v1: `norm`, `complex_data`, `resolution_scaling_factor`, `domain_padding`, `factorization`, `separable`, `preactivation`. |
| `neuralop.layers.spectral_convolution.SpectralConv` | `poc.models.fno_neuralop.spectral_conv.SpectralConv1D` | Dense (non-factorized), real-valued, order-1 case only. See §4 for the exact algorithm and the three non-obvious parity details verified empirically. |
| `neuralop.layers.fno_block.FNOBlocks` | `poc.models.fno_neuralop.fno_block.FNOBlocks1D` | Composes `SpectralConv1D` + unbiased linear skip (`fno_skip="linear"` → `Flattened1dConv`, i.e. an unbiased 1×1 conv) + soft-gating skip (per-channel learned scalar, no bias) + `ChannelMLP1D` + `gelu`. Postactivation ordering only (`preactivation=False`, matching the PyTorch default). |
| `neuralop.layers.channel_mlp.ChannelMLP` | `poc.models.fno_neuralop.channel_mlp.ChannelMLP1D` | Conv1d-kernel-1 stack ≡ per-position `Dense` applied over the channel axis. `n_layers=2` for both lifting and projection, matching `FNO`'s own use of `ChannelMLP` for lifting/projection. |
| `neuralop.layers.embeddings.GridEmbeddingND` (1D case) | `poc.models.fno_neuralop.embeddings.GridEmbedding1D` | Appends one coordinate channel `x_i = i / nx` (left-endpoint, periodic-consistent — matches our `[0, L)` domain convention already used in `poc/generators/burgers1d.py`). |
| `neuralop.layers.skip_connections.{Flattened1dConv, SoftGating}` | inlined into `FNOBlocks1D` | Not ported as standalone modules; both are trivial (`Dense` without bias; learned per-channel scale without bias) and only used inside the block. |
| `neuralop.layers.legacy_spectral_convolution.SpectralConv1d` | — (not ported) | Considered and rejected as the port target — see §4.1 for why targeting the *current* module is both correct and no harder, once the mode-selection semantics are understood. |
| Tensor factorization (`tensorly`/`tltorch`: CP/Tucker/TT), `complex_data=True`, `domain_padding`, `resolution_scaling_factor`, `norm∈{ada_in,group_norm,instance_norm}`, `fno_block_precision∈{half,mixed}`, `conv_bias_kernel>1` (very recent upstream addition) | — (not ported, v1) | None of these are needed for a plain dense 1D Burgers FNO and none are in the ratified `carbon/schema/strategy.py` backbone-config surface today. Extend later only if a strategy knob is ratified that needs one. |

### 3.1 Why target the current module, not `legacy_spectral_convolution.py`

The user brief flagged this as an open question. Verdict: target the
**current** `SpectralConv`/`FNO`, for two reasons. First, it's what the brief
asked for and what `carbon/backbones/neural_operator.py` already intends to
wrap (see §6.2 — that wrapper is currently broken, but its intent is clearly
the current API). Second, and less obviously: for the 1D real-valued case,
the current module's mode-truncation *behavior* reduces to exactly the same
"keep the first K low-frequency `rfft` coefficients" semantics as the legacy
module — verified empirically (§4.1) — so there is no simplicity cost to
targeting the current module, only a documentation-reading cost, which this
note pays once so the implementation doesn't have to re-derive it.

---

## 4. `SpectralConv1D` — the exact algorithm, verified empirically

For `in_channels=C_in`, `out_channels=C_out`, real 1D input `x` of shape
`(B, C_in, nx)`, requested `n_modes=M`, `factorization=None`,
`separable=False`, `complex_data=False`, `resolution_scaling_factor=None`,
`fno_block_precision="full"`:

```text
1. m = M // 2 + 1                         # "redundancy" halving — see §4.2
2. X = rfft(x, axis=-1, norm="forward")   # (B, C_in, nx//2+1) complex
3. W = W_real + i * W_imag                # learned, shape (C_in, C_out, m)
4. Y[..., :m] = einsum('bik,iok->bok', X[..., :m], W)   # low modes only
   Y[..., m:] = 0
5. Y[..., 0].imag = 0                     # Hermitian-symmetry enforcement — see §4.3
   if nx % 2 == 0: Y[..., -1].imag = 0
6. y = irfft(Y, n=nx, axis=-1, norm="forward")
7. y = y + bias[None, :, None]            # bias shape (C_out,), enabled by default
```

### 4.1 Mode selection is genuinely low-pass in 1D — verified, not assumed

A first read of `spectral_convolution.py`'s `forward()` is misleading: the
per-dimension slice into `x`'s spectrum is built from a "centered" formula
(`center = all_modes // 2; slice(center - neg, center + pos)`) that, taken in
isolation, would select a *mid-spectrum* band whenever `n_modes` genuinely
truncates (e.g. `nx=128`, requested modes `16` → kept `m=9` → naive trace
gives `slice(28, 37)`, not `slice(0, 9)`). This does **not** match the
well-known "FNO keeps low frequencies" description, so it was verified
rather than assumed.

Two checks were run before trusting either reading:

1. **Hand-derivation was corrected by re-reading the source.** Lines
   514–517 of `spectral_convolution.py` explicitly override the last
   dimension's slice back to `slice(0, kept_modes)` whenever
   `weight.shape[-1] < fft_size[-1]` (i.e. whenever truncation is real). The
   "centered" formula a few lines above is for the fftshift-based path used
   by *interior* dimensions in ND cases with `order > 1`; the last
   (never-shifted, one-sided real) dimension always gets this override. In
   1D, the only dimension *is* the last dimension, so the override always
   fires and the centered formula's output is fully discarded.
2. **Empirically confirmed against installed PyTorch.** A CPU venv with
   `torch`, `tensorly`, `tltorch` was built specifically for this
   verification (not part of the repo). An impulse-response test — feeding
   pure `cos(2πkx/nx)` for every `k` through a real `SpectralConv(1, 1, 16,
   separable=True)` on `nx=128` and measuring output energy per `k` —
   showed non-negligible response only for `k = 0..8` (9 modes, matching
   `m = 16 // 2 + 1`), zero elsewhere. Low-pass, confirmed, not assumed.

### 4.2 Mode-count semantics: requested `n_modes` ≠ retained coefficients

The constructor applies `n_modes[-1] = n_modes[-1] // 2 + 1` to the
user-requested value for the last (real) dimension — documented in the
class docstring as accounting for `rfft`'s conjugate-symmetry redundancy.
Requesting `n_modes=16` retains **9** complex low-frequency coefficients,
not 16. `poc/models/fno1d_jax.py`'s existing `_spectral_conv` uses
`m = min(modes, x_ft.shape[1])` — i.e. `modes` is taken literally. Any
strategy-schema `backbone_config.modes` field intended to mean the same
thing across both implementations needs this halving applied consistently;
the port's `SpectralConv1D` applies it exactly as upstream does.

### 4.3 `enforce_hermitian_symmetry`: verified to be a no-op here, ported anyway

The current module's default `enforce_hermitian_symmetry=True` explicitly
zeroes the imaginary part of the DC bin (and the Nyquist bin, if `nx` is
even) before calling `irfft` — a robustness fix for cuFFT/GPU edge cases per
its own docstring, added after PyPI's `neuraloperator==2.0.0` (the version
actually satisfying Carbon's own `neuraloperator>=2.0,<3` pin — 2.0.0 is the
only 2.x release; there is no `enforce_hermitian_symmetry` in the installed
2.0.0 source at all). Rather than assume this is safe to skip or unsafe to
add, it was checked directly: for a worst-case random complex spectrum with
large nonzero imaginary parts at both the DC and Nyquist bins, `irfft` with
and without the explicit zeroing produced a max absolute difference of
exactly `0.0` on CPU (`torch.fft.irfft`, `norm="forward"`). The port
implements the explicit zeroing anyway (step 5 above) since it's free,
matches current upstream exactly, and costs nothing if JAX's CPU/GPU `irfft`
turns out to have the same GPU-only edge case upstream describes.

### 4.4 `fft_norm`

Current module defaults to `fft_norm="forward"` (normalize on the forward
FFT only); the legacy module defaults to `"backward"`. The port uses
`norm="forward"` for both `jnp.fft.rfft`/`jnp.fft.irfft` to match current
upstream.

---

## 5. `FNOBlocks1D` — residual wiring (non-obvious, verified by reading `forward_with_postactivation`)

For block input `x` (shape `(B, C, nx)`, `C = hidden_channels` for all
interior blocks):

```text
x_skip_fno    = LinearSkip(x)            # unbiased 1x1 conv/Dense, from block input
x_skip_gate   = SoftGate(x)               # per-channel learned scalar, no bias, from block input
x_spec        = SpectralConv1D(x)
x             = x_spec + x_skip_fno
if not last_layer: x = gelu(x)
x             = ChannelMLP1D(x) + x_skip_gate   # note: x_skip_gate is from the ORIGINAL block input,
                                                  # bypassing both the spectral conv and the channel MLP
if not last_layer: x = gelu(x)
return x
```

Both skips are computed from the same pre-spectral-conv `x`, at the top of
the block, before `x` is reassigned — `x_skip_gate` re-enters *after* the
channel-MLP step, so it is a long residual bypassing two sublayers, not two
short sequential ones. Activation fires after both sums, but never after the
final `FNOBlocks1D` layer in the stack (checked against `FNO.forward`'s loop
which never applies a trailing activation after the last block either — the
`if index < (self.n_layers - 1)` guard is internal to `FNOBlocks`, and `FNO`
itself has no activation between the block stack and `projection`).

`ChannelMLP1D` inside each block: `hidden_channels = round(C *
channel_mlp_expansion)` with `channel_mlp_expansion=0.5` default.

Lifting: `ChannelMLP1D(in_channels + 1 → hidden_channels)` (the `+1` is the
grid positional-embedding channel), `hidden_channels_of_mlp =
lifting_channel_ratio(2) * hidden_channels`, `n_layers=2`. Projection:
`ChannelMLP1D(hidden_channels → out_channels)`,
`hidden_channels_of_mlp = projection_channel_ratio(2) * hidden_channels`,
`n_layers=2`.

---

## 6. Findings on existing code (flagged, not fixed by this branch)

### 6.1 ν must be fixed at 5×10⁻³ for v1 — current PoC config uses ranges

Both the exam doc and ratified `MASTER_OPEN_DESIGN_QUESTIONS.md` (MQ-001)
are explicit: *"Do not vary viscosity until ν is an explicit candidate
input."* `poc/configs/challenge_burgers1d.yaml` samples ν from ranges per
role (`train: [0.001, 0.01]`, `stress: [0.0005, 0.005]`), and
`poc/generators/burgers1d.py` draws `nu = rng.uniform(nu_lo, nu_hi)` per
sample. This is a live conflict between ratified direction and current PoC
code (`IMPLEMENTATION_LAG` per the Constitution's own taxonomy in §12).
**Not fixed here** — the new `poc/challenges/burgers_v1/generator.py` uses
fixed `ν = 5×10⁻³` per the doc, and the existing `poc/configs/*` /
`poc/generators/burgers1d.py` are left untouched.

### 6.2 `carbon/backbones/neural_operator.py` calls the wrong kwargs

`NeuralOperatorFNO._get_fno` constructs `FNO(in_channels=..., out_channels=...,
modes=modes, width=width, **kwargs)`. Neither `modes` nor `width` exist in
`neuralop.models.fno.FNO.__init__` — confirmed against both current upstream
`main` and the actually-pinned installable `neuraloperator==2.0.0` on PyPI
(both use `n_modes`/`hidden_channels`; the `<3` pin resolves to exactly
`2.0.0`, the only 2.x release). Constructing `backbone: "fno"` through this
wrapper today would raise a `TypeError`. Pre-existing, unrelated to this
port, not touched here — flagged since it's directly adjacent (same upstream
package) and someone will hit it the moment a strategy actually specifies
`backbone: "fno"` end-to-end.

### 6.3 Two schema modules — `carbon/schema/strategy.py` is current

`carbon/schema/strategy.py` (top-level `schema_version`/`challenge_id`/
`backbone`/`parameters` only; backbones `{deeponet, fno, physicsnemo_fno,
uno}`) is the ratified A2 wire contract. `carbon/common/strategy_schema.py`
(top-level `backbone`/`loss`/`training`/`budget`; includes `fno1d`/`fno2d`)
is legacy pre-reconciliation PoC-only code — `Design_Specs/Strategy_Schema.md`
itself says so. No `backbone_config.modes`-style knob exists in the ratified
schema today; if one is added later for this FNO, it belongs under
`parameters` in the `carbon/schema/strategy.py` shape, not the legacy one.

### 6.4 The PoC's live scoring path diverges from the exam doc in three ways

Read `poc/eval/gates.py`, `poc/eval/score.py`, and `carbon/common/scoring.py`
in full. Concretely, versus `Scoring.md` §6 / exam doc §15–18:

| | Exam doc / `Scoring.md` | PoC live (`poc/eval/score.py` → `carbon/common/scoring.py`) |
|---|---|---|
| Physics margin | quadratic barrier `1 - (e/τ)²` | linear clip `clip(1 - e/τ, 0, 1)` |
| Robustness | tail-logistic sigmoid per category, weighted sum | `β·mean(r_c) + (1-β)·min(r_c)` |
| Top-level combine | weighted **geometric** mean (log-space) | weighted **arithmetic** sum |
| Gates | finite, energy non-increase, mean conservation, max-principle | finite, conservation, residual_ceiling, accuracy_ceiling, loss_signal (missing energy non-increase and max-principle; two extra PoC-only safety gates) |
| Reference | Cole–Hopf | IMEX pseudo-spectral forward solve (`burgers_reference_solve`) |

`Scoring_Formulas.md` itself already names the arithmetic combination and
linear-clip-as-default as superseded historical rules — so the PoC harness
was already known to be pre-reconciliation in this respect. This branch
does **not** rewrite `poc/eval/{gates,score}.py`: they back the existing PoC
lean-loop's own tests and its own "prove the mechanism" purpose (see §2).
Instead, `poc/challenges/burgers_v1/{gates,scoring}.py` implement the doc's
exact formulas as new, separately-labeled code. Whether/when to reconcile
the two is left as an open question (§7.2) — it's a bigger, cross-cutting
decision than an FNO port.

---

## 7. Deferred from the exam doc, and what this code enables later

Per your instruction, explicitly not silently skipped:

| Doc section | What's deferred | Why | What this branch still provides |
|---|---|---|---|
| §11.A Reference uncertainty | δ_ref campaign vs. an independent witness | Requires a methodologically independent (non-pseudo-spectral) solver, which doesn't exist yet, plus a multi-case measurement campaign | Cole–Hopf implementation built to doc §9's stability requirements (log-domain/rescaling), so a future finite-volume/finite-difference witness has something real to compare against |
| §11.B Measurement floors | Numerical floor characterization per measurement | Needs the §11.A witness data first | Gates/scoring code structured so floors can be substituted in as pack-bound thresholds later, not hardcoded |
| §11.C Reconstruction variability | Multi-seed retraining variance study | No training loop wired to this new harness yet (out of scope: this note covers architecture + reference + gates + scoring, not the JAX training loop) | — |
| §11.D Finite-exam variability | Repeated fresh-exam score/rank variance | Requires a running exam loop at scale | Deterministic, seeded `run_exam.py` entry point this can later be driven repeatedly against |
| §11.E Minimum resolvable improvement | Derivation from A–D above | Depends on all of the above existing first | — |
| §13 Adversarial reference-bias test | Two controlled candidate families (bias-imitator vs. reference-tracker) | Requires trained candidates and a qualified witness; neither exists yet | Cole–Hopf reference is the qualified target such a test would check against |
| §21 Validation Dossier | The full signed evidence package | Is the terminal deliverable of everything above | This branch is a prerequisite artifact, not a substitute |

None of these are silently dropped from the codebase's ambitions — they're
sequenced after a working, numerically-verified FNO port and reference
solver exist to measure against.

---

## 8. Open questions for review

1. **§6.1** — should the ratified-vs-PoC ν conflict be raised as its own
   ticket/decision now, independent of this branch?
2. **§6.2** — is fixing `carbon/backbones/neural_operator.py`'s kwarg bug
   in scope for a follow-up commit on this branch, or a separate PR (it's
   unrelated to the JAX port but touches the same upstream package)?
3. **§6.4** — long-term, should `poc/eval/{gates,score}.py` be migrated to
   the doc-exact formulas (matching `Scoring.md`), or are the two
   deliberately meant to stay separate (PoC mechanism-proving vs. exam
   dossier-qualification)?
4. **Stress taxonomy** — `poc/generators/stress_categories.py`'s existing
   six categories (`extended_envelope`, `shock_perturbation`, etc.) are
   engineering-chosen, not derived from the doc's `k_rms`/`U_rms`/`Re_eff`/
   steepening-index descriptors (doc §17). `poc/challenges/burgers_v1/stress.py`
   defines new doc-derived categories rather than reusing the existing six.
   Confirm this is the right call rather than trying to map the existing
   categories onto the doc's descriptors after the fact.
5. **Placement** — confirm `poc/models/fno_neuralop/` and
   `poc/challenges/burgers_v1/` are the right locations, versus e.g. a
   top-level `carbon/operators/` if this is meant to graduate beyond PoC
   status sooner than the rest of the harness.

---

## 9. Implementation order (bottom-up, test-at-each-layer)

1. `SpectralConv1D` + parity test (shared weights vs. PyTorch `SpectralConv`,
   dense/real/order-1 config).
2. `ChannelMLP1D` + parity test.
3. `GridEmbedding1D` + parity test (trivial, but keeps the chain complete).
4. `FNOBlocks1D` + parity test (single block, then `n_layers>1`).
5. `FNO` + parity test (full model, weight-transfer harness documented in
   the test file: exact PyTorch-state-dict → Flax-params mapping).
6. Cole–Hopf reference solver + self-consistency tests (recovers `u0` at
   `t=0`, periodicity, mean conservation, invariance to harmless φ
   rescaling, convergence under refinement).
7. Fixed-ν generator (doc §6) + the four gates (doc §14).
8. Doc-derived stress strata (doc §17) + soft scoring (doc §15–18).
9. `run_exam.py` integration test: seed → score, on a small fixed,
   eyeballable case set (per your step 5).

---

*This note records what was verified and how, not just what was assumed —
in particular §4's mode-selection and Hermitian-symmetry claims were checked
against running PyTorch code, not inferred from reading alone, given how
consequential a mistake there would be for the numerical-parity goal.*
