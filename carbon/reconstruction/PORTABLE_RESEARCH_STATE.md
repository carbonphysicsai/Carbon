# Public research state transport

`portable_state.py` preserves logical JAX lab state for a new admitted research
operation. It wraps the existing non-pickle checkpoint and keeps parameter and
optimizer/EMA leaves, RNG/progress, physical units/scaling, recipe, data, source
and numerical environment identities. Its separate binding records source device
placement and the originating principal/operation. It contains no executable,
compiled cache or device handle.

The current implementation accepts fully addressable single-device state only.
The destination keeps source/library and precision identities exact while
allowing an explicit backend/machine change. Such a continuation must use a new
operation. Actual CPU transport and continued training have been exercised;
GPU/TPU transport and cross-backend numerical calibration remain open. The
ordinary `load_checkpoint` continues to reject a different environment.

## Use through existing research services

Obtain an admitted public research workspace using the existing CLI, Launchpad
or standard MCP service described in `carbon/miner_mcp/README.md`. Its principal,
grant, image, resource limits and final-work reserve remain controlling. The
helper does not create or extend any of these.

Stage the public `portable_state.py` source as an explicitly named workspace file
such as `portable_helper.py`, alongside the permitted own/public data. The
existing `run_python` action can use `runpy.run_path('portable_helper.py')` inside
its isolated worker. This keeps the helper in the same hashed input provenance
as other research source, without changing the installed analysis image.

After training, save within the worker's bounded output directory:

```python
from pathlib import Path
import runpy

helper = runpy.run_path("portable_helper.py")
bundle_digest = helper["save_research_state"](
    trainer,
    Path("/scratch/output/state"),
    principal=research_principal,
    operation_id=current_operation_id,
)
Path("/scratch/output/state-digest.txt").write_text(bundle_digest)
```

Retain the exact digest and all three bundle files (`binding.json`,
`checkpoint/manifest.json`, `checkpoint/state.npz`) through the existing output
and workspace APIs. For a later operation, explicitly stage those bytes and the
helper, reconstruct the directory in private scratch, then restore:

```python
receipt = helper["load_research_continuation"](
    trainer,
    Path("state"),
    principal=research_principal,
    operation_id=new_operation_id,
    expected_digest=retained_bundle_digest,
)
trainer.fit()
```

The target trainer must be constructed from the same recipe, training data,
normalization and runtime RNG binding. The returned receipt records source and
target placement, the new operation and starting progress. Save it with outputs.
Pass the existing admitted identities; a string or matching digest is not an
authentication mechanism. The controller still authorizes every operation and
accounts for compilation, execution, storage and cleanup. A replay uses the same
existing operation and returns its retained result without another dispatch.

These outputs remain `MINER_SELF_REPORTED_NO_EVALUATION_AUTHORITY`. They cannot
replace fresh validator reconstruction, authorize training-support reuse, change
physics gates or establish comparable backend scores. Cross-backend fixed-state
agreement and retraining differences require separate measured experiments.

## Verification

In the pinned numerical environment:

```sh
python -m pytest tests/science/test_portable_state.py -q
CARBON_C03_IMAGE_MANIFEST=/absolute/path/to/worker-image.json \
  python -m pytest tests/service/test_portable_research_state.py -q -s
```

The actual service test uses synthetic engineering admission and the existing
isolated research carrier. It runs two CPU workers, checks an unchanged fresh CPU
control, verifies accounting/replay and confirms exact container cleanup. It does
not make model calls, allocate accelerators or exercise a production grant.
