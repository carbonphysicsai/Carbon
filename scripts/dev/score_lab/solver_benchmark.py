"""Compatibility import for the shared DEVELOPMENT benchmark evidence reducer.

Validation and reduction live in carbon.scoring.benchmark_evidence. Existing
workbench imports retain their names and historical result semantics.
"""

from carbon.scoring import benchmark_evidence as _core

SCHEMA = _core.SCHEMA
SCHEMA_V3 = _core.SCHEMA_V3
RESULT_SCHEMA = _core.RESULT_SCHEMA
ROLES = _core.ROLES
ENGINEERING_REFERENCE = _core.ENGINEERING_REFERENCE
BenchmarkRefused = _core.BenchmarkRefused
physics_contract_identity = _core.physics_contract_identity
register = _core.register
compare = _core.compare


def __getattr__(name):
    return getattr(_core, name)
