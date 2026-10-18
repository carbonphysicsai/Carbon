"""Compatibility import for the shared DEVELOPMENT bundle benchmark reducer.

Custody, saved-inference conversion and scoring reduction live in
carbon.scoring.bundle_benchmark_core.
"""

from carbon.scoring import bundle_benchmark_core as _core

ENTRY_SCHEMA = _core.ENTRY_SCHEMA
CUSTODY_SCHEMA = _core.CUSTODY_SCHEMA
MEASUREMENT_SCHEMA = _core.MEASUREMENT_SCHEMA
RESULT_SCHEMA = _core.RESULT_SCHEMA
BundleBenchmarkRefused = _core.BundleBenchmarkRefused
measurement_from_saved_inference = _core.measurement_from_saved_inference
benchmark_saved_entry = _core.benchmark_saved_entry


def __getattr__(name):
    return getattr(_core, name)
