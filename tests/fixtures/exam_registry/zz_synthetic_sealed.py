"""The synthetic family's sealed kit and sealed grader (X1): the least a family no code names must serve to be dispatched.

Imported as ``carbon.zz_synthetic_sealed`` only by the conformance and family tests. It grades nothing: no science, no sealed
material, no value of any exam. Its producer files are its own, so its digest moves when this file does.
"""

from __future__ import annotations

import json

CHALLENGE = "zz-synthetic"
VERSION = "0.1"
POOL_VERSIONS = {VERSION: ("zz-pool-sealed-v1", "zz-sealed-pool-set")}
VERSIONS = dict(POOL_VERSIONS)
EVALUATION_VERSION, CASE_ID = POOL_VERSIONS[VERSION]
POOL_GRADED = True
#: Relative to ``carbon/scoring``, as `physical_dual_pack.producer_digest` reads a producer's files.
FILES = ("../../tests/fixtures/exam_registry/zz_synthetic_sealed.py",)


def sealed_bank(document, records, *, version, pool=None):
    return {
        "population": "zz",
        "version": version,
        "document": document,
        "records": list(records),
        "pool": pool,
    }


def private_roles(bank):
    return {"case_bank": json.dumps(bank, sort_keys=True).encode("utf-8")}


def adapter_for_bank(bank, version):
    """This module itself for its own population; any other has no grader (``ValueError``)."""
    import sys

    if type(bank) is not dict or bank.get("population") != "zz":
        raise ValueError("zz_bank_population")
    return sys.modules[__name__]
