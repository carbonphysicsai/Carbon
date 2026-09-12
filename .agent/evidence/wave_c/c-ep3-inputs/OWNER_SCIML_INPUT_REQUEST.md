# C-EP3 consolidated owner / Physics-SciML input request

Please supply one permission-cleared immutable package for the intended JAX
reconstruction implementation so Carbon can decide whether existing ticket
C-02 is ready to select. This request does not select or authorize C-02.

Essential now:

- repository or archive locator, immutable commit/digest, source owner and
  permitted Carbon research/integration use;
- reproducible dependency/build identity;
- actual training and inference symbols and signatures, without renaming them;
- input/output shapes, units, layouts, dtypes, supported dimensions and batch
  behavior;
- parameter/state and checkpoint format;
- RNG ownership, data-loader behavior and reproducibility contract;
- JIT/compilation, warm-up, batching, sharding and required CPU/GPU/accelerator
  environment;
- failure/cancellation semantics and safe observation points for construction,
  training-data work, training/reconstruction and inference.

Already known, so it need not be rediscovered:

- The supplied public workbench's TRAIN arrays are `initial_field float64
  [36,512]`, `viscosity [36]`, `requested_times [36,193]`, and `solution
  [36,193,512]`; those public labels do not define the intended JAX interface.
- PR #40 at `5bde3d8f5983d7136682c7b8eb2f17d57a59e5fe` is explicitly a
  non-authoritative research candidate. It demonstrates 22 shared-weight fp32
  forward-pass parity cases for `FNO.__call__(x)`, with shape
  `(batch, channels, nx) -> (batch, out_channels, nx)`. It does not establish
  initialization, gradients, optimizer/training trajectory, packaging,
  reconstruction runtime, checkpoints, RNG ownership or the intended C-02
  source.
- Carbon owns the adapter. Upstream function renaming is not requested.

Later optimization details may follow after the essential interface is fixed.
Representative miner demand, common-comparison rules, protected-reference
qualification and Variant-B overhead are separate missing inputs and should not
be invented inside this source handoff.
