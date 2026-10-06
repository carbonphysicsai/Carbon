"""A passing stand-in for the carrier containment check, for gate tests that
are about something else (GRAPHITE-CARRIER-CONTAINMENT-01).

SYNTHETIC: it runs no container and proves nothing; its report says so. The
check itself is tested in `test_carrier_containment.py`, and the gates fail
closed without it (`test_carrier_containment.py` covers both).
"""

from __future__ import annotations

from carbon.development_session import containment_check

DIGEST = "sha256:" + "0" * 64


def passing_report(*, root, manifest=None, **_):
    return {
        "schema": containment_check.SCHEMA,
        "status": "PASS",
        "code": None,
        "synthetic_test_double": True,
        "image_id": DIGEST,
        "create_arguments_digest": DIGEST,
        "probes": [
            {"probe": name, "status": "PASS", "observed": None, "rule": "double"}
            for name in containment_check.PROBES
        ],
        "claims": {"security_acceptance": False},
    }


def install(monkeypatch):
    """Both gates import the check at call time, so this reaches both."""
    monkeypatch.setattr(containment_check, "containment_check", passing_report)
