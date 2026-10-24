"""Every served launch version must pass the executor's resource-policy check.

`reconstruct_and_infer_public` first calls `verify_direct_resource_policy` with
the worker resources the allowlist implies. When the large-model profile is on
(`LARGE_MODEL_PROFILE_APPLIED`), a v7-allowlist version whose kit still
publishes the older `reconstruction_resource_policy` is refused with
`construction_resource_policy_unserved` before any build, and the direct task
ends UNRESOLVED (shown as FAILED_INFRA). This pins the pairing for each served
version so the mismatch cannot reach a proof run again.
"""

from __future__ import annotations

import pytest

from carbon.challenge_kit import physical_material
from carbon.development_session import bundle_construction_worker as worker
from carbon.reconstruction.worker.model import worker_resources_version

SERVED = [
    ("chip-cold-plate", "1.3"),
    ("chip-cold-plate", "1.4"),
    ("electric-motor-magnetics", "1.4"),
    ("f08-ribbed-bracket", "1.5"),
    ("f02", "2.4"),
]
BINDING_KEYS = (
    "train_digest",
    "interface_digest",
    "construction_limits_digest",
)


@pytest.mark.parametrize(("challenge_id", "version"), SERVED)
def test_the_kits_published_policy_is_the_one_the_executor_demands(
    challenge_id, version
):
    material = physical_material.bundle_material(challenge_id, version)
    kit = material["construction_kit"]
    binding = {
        "challenge_id": kit["id"],
        "challenge_version": kit["version"],
        **{key: kit[key] for key in BINDING_KEYS},
    }
    allowlist = worker._trusted_allowlist(material["allowlist_bytes"])
    worker.verify_direct_resource_policy(
        binding,
        material["construction_limits_document"],
        worker_resources_version(allowlist.version),
    )
