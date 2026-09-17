"""Fixed evaluator-owned numerical diagnostics; input carries no credentials."""

from __future__ import annotations

import numpy as np

from carbon.development_session.profile import digest
from carbon.measurement_runtime.development import measure
from carbon.measurement_runtime.development_controls import controls
from carbon.measurement_runtime.model import FrozenFieldArtifact
from carbon.measurement_runtime.protocol import decode_measurement_request
from carbon.reference_runtime.model import _cole_hopf, decode_reference_request


def execute(bundle):
    if bundle["kind"] == "controls":
        return controls(bundle["stage"])
    if bundle["kind"] not in ("remeasure", "reference-resolution"):
        raise ValueError("unsupported numerical operation")
    sources = []
    reference_checks = {}
    for rows in bundle["sources"]:
        output = []
        for row in rows:
            q = decode_measurement_request(row["request"])
            u = np.asarray(row["candidate"], dtype="<f8")
            v = np.asarray(row["reference"], dtype="<f8")
            if (
                FrozenFieldArtifact(
                    q.candidate_binding_digest,
                    q.shape,
                    u.tobytes(),
                    "CANDIDATE_PREDICTION",
                ).artifact_digest
                != q.candidate_artifact_digest
                or FrozenFieldArtifact(
                    q.reference_request_digest,
                    q.shape,
                    v.tobytes(),
                    "REFERENCE_PRIMARY",
                ).artifact_digest
                != q.reference_artifact_digest
            ):
                raise ValueError("altered signed field artifact")
            if q.case_digest not in reference_checks:
                rq = decode_reference_request(row["reference_request"])
                if rq.request_digest != q.reference_request_digest:
                    raise ValueError("reference request association changed")
                refined, _ = _cole_hopf(rq, internal_grid_points=2048)
                finest, _ = _cole_hopf(rq, internal_grid_points=4096)
                scale = float(
                    np.sqrt(
                        np.mean(
                            (np.asarray(q.initial_values) - np.mean(q.initial_values))
                            ** 2
                        )
                    )
                )
                e0 = q.domain_length * scale * scale / 2

                def energy(w, length=q.domain_length):
                    return (
                        length * np.mean((w - w.mean(axis=1)[:, None]) ** 2, axis=1) / 2
                    )

                reference_checks[q.case_digest] = {
                    "reference_request_digest": rq.request_digest,
                    "method": "C04_COLE_HOPF_QUADRATURE_1024_2048_4096_SHARED_METHOD",
                    "field_indicator": float(
                        max(np.max(abs(v - refined)), np.max(abs(refined - finest)))
                        / scale
                    ),
                    "energy_indicator": float(
                        max(
                            np.max(abs(energy(v) - energy(refined))),
                            np.max(abs(energy(refined) - energy(finest))),
                        )
                        / e0
                    ),
                    "refined_payload_digest": digest(refined.astype("<f8").tobytes()),
                    "finest_payload_digest": digest(finest.astype("<f8").tobytes()),
                    "qualified_bound": False,
                }
            if bundle["kind"] == "reference-resolution":
                continue
            m = measure(
                u,
                v,
                times=q.requested_times,
                length=q.domain_length,
                viscosity=q.viscosity,
                initial=q.initial_values,
                amplitude=q.amplitude,
                characteristic_time=q.characteristic_time,
            )
            output.append(
                {
                    "role": row["role"],
                    "case": q.case_digest,
                    "replica": int(q.candidate_replica_id.rsplit("-", 1)[1]),
                    "measurement": m,
                }
            )
        sources.append(output)
    return {
        "schema": "carbon.cw1.derived-measurement-bundle.v1",
        "sources": sources,
        "reference_checks": reference_checks,
    }
