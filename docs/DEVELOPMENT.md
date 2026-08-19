# Carbon development and test lanes

Carbon's supported A1 development lane is Ubuntu-compatible Python 3.11 and
CPU-only. It establishes packaging, collection, unit-test, and quality-gate
infrastructure. It is not evidence that any scientific backend, challenge,
score, validator, Bittensor path, or production deployment is qualified.

## Supported CPU development install

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
```

The default suite discovers `tests/cpu/`. It imports `carbon`, exercises every
A0 role package, verifies installed distribution metadata, repeats imports from
an isolated process outside the repository, and proves that blocking optional
scientific packages does not break the core package.

## Dependency boundaries

The default `carbon` distribution has no runtime dependency. This is deliberate:
the package root and the fourteen A0 role boundaries are behavior-free, and the
current scientific, chain, Landscape, and prototype modules are not promoted to
the supported core merely because they remain in the source tree.

| Extra | Purpose | A1 status |
|---|---|---|
| `dev` | Pinned pytest, Ruff, and Black used by the supported CPU lane | Supported for A1 development/CI |
| `chain`, `validator`, `miner` | Bittensor integration dependencies | Optional aliases for base Bittensor; no chain/network behavior is exercised or qualified by A1 |
| `neuraloperator` | PyTorch and the community NeuralOperator dependency | Optional legacy-adapter boundary; installed-backend API compatibility and science remain deferred |
| `physicsnemo` | PyTorch and NVIDIA's `nvidia-physicsnemo` distribution | Optional Python 3.11+ backend boundary; not scientifically qualified |
| `poc` | NumPy, PyYAML, and JAX for the historical Burgers PoC | Optional, slow, and outside default CI |

Install only the boundary being developed, for example:

```bash
python -m pip install -e ".[dev,physicsnemo]"
```

The optional backend wrappers import their libraries only when used and are
registered even when their extras are absent. If an extra is absent, direct or
registry-based construction fails with an error naming the required extra.
Import defects inside an installed backend are re-raised and are not disguised
as a missing package. A1 verifies that dependency/failure boundary only; it does
not claim that the retained legacy NeuralOperator model arguments are compatible
with current upstream APIs. PhysicsNeMo's upstream package itself requires
Python 3.11 or newer.

Dependencies used only by unsupported historical Landscape, symbolic, data,
or validator modules are not advertised as supported extras. Those modules
remain audit inputs for later scoped tickets.

## Pytest classifications

The following markers are registered:

- `invariant`: reserved for the A12 constitutional invariant suite;
- `legacy`: retained tests for retired namespaces or superseded prototype
  behavior;
- `poc`: historical, scientifically unqualified PoC regression tests;
- `poc_integration`: slow generator/training/end-to-end PoC tests;
- `backend_jax`: tests that require JAX;
- `gold`: opt-in long-budget PoC tests requiring `POC_GOLD=1`.

The five inherited root tests are retained under `tests/legacy/`. They target
retired `neurons` APIs or superseded scoring/schema/seeding behavior and are not
current-spec CPU acceptance tests. Several do not collect or pass even after
their heavyweight dependencies are installed; A1 does not invent compatibility
aliases or scientific semantics to make them green.

The PoC remains a separate diagnostic lane:

```bash
python -m pip install -e ".[dev,poc]"
POC_FAST=1 python -m pytest poc/tests -q
POC_FAST=1 bash poc/scripts/smoke.sh
```

Use `bash` explicitly because the tracked smoke script is not executable. The
current PoC failure baseline is recorded in `.agent/DECISIONS.md`; it is not a
blocking A1 gate and no PoC result is production or scientific qualification.

## Quality ratchet

The full inherited Ruff and Black inventory is committed at
`.ci/quality-baseline.json`, anchored to the A1 starting SHA. The blocking gate:

1. runs pinned Ruff and Black over every tracked Python file, without honoring
   repository-wide excludes;
2. rejects any diagnostic not present in the inherited fingerprint inventory;
3. permits inherited findings to be removed;
4. runs strict Ruff and Black on every Python file added or touched since the
   selected base commit;
5. emits the complete current machine-readable inventory for the Actions
   artifact.

Ruff runs with `--isolated`. Black is given the empty `/dev/null` configuration
explicitly, and the gate checks Black's summary against the complete enumerated
file list. Repository configuration therefore cannot silently exclude debt from
the inventory.

Run it locally with a suitable comparison base:

```bash
python scripts/check_quality.py \
  --baseline .ci/quality-baseline.json \
  --base origin/main \
  --report /tmp/carbon-quality-current.json
```

The raw audits remain useful diagnostics and are intentionally still red while
the inherited debt exists:

```bash
ruff check .
black --check .
```

Do not regenerate the baseline from a feature head to absorb new findings.
Changing the baseline requires deliberate review of the complete fingerprint
delta and its source SHA.
