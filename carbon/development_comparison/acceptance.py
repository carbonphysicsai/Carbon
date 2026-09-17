"""Trusted DEVELOPMENT admission, derived reports and lifecycle readback.

The registration is controller-owned, outside the miner. It grants no provider,
training or transaction budget. C-06 signatures bind the new derived evidence;
original signed sources and their old dispositions are never rewritten.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from carbon.audit.derivation import (
    DevelopmentDerivation,
    sign_derivation,
    verify_derivation,
)
from carbon.audit.signing import DevelopmentVerificationKey
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest
from carbon.development_session.service import development_signer
from carbon.development_testnet.execution import load_source_handoff
from carbon.measurement_runtime.model import FrozenFieldArtifact
from carbon.scoring.development import RULE, compare, rule_digest

from .numerical import run_numerical
from .sources import read_json, resolve_source


@dataclass(frozen=True)
class DevelopmentAcceptanceRef:
    root: Path
    registration_digest: str
    report_digest: str


def _seal(root, name, payload, receipts, kind):
    signer = development_signer(root)
    proof = DevelopmentDerivation(
        rule_digest(),
        tuple(receipts),
        digest(canonical(payload)),
        time.time_ns() // 1000,
        signer.verification_key.key_id,
        signer.verification_key.public_key_digest,
        kind,
    )
    body = {
        "payload": payload,
        "derivation": proof.document(),
        "signature": sign_derivation(signer, proof).hex(),
    }
    write_once(root / name, canonical(body))
    return body


def _verify(body, key):
    d = body["derivation"]
    proof = DevelopmentDerivation(
        d["rule_digest"],
        tuple(d["input_receipts"]),
        d["artifact_digest"],
        d["issued_at_micros"],
        d["key_id"],
        d["public_key_digest"],
        d["kind"],
    )
    if (
        d != proof.document()
        or proof.rule_digest != rule_digest()
        or digest(canonical(body["payload"])) != proof.artifact_digest
    ):
        raise ValueError("altered derivation")
    verify_derivation(
        proof, bytes.fromhex(body["signature"]), key, now_micros=time.time_ns() // 1000
    )
    return body["payload"]


def register(root, *, template_source, quarantine_journal, reference_root, sessions):
    """Freeze before construction. Sessions map absolute roots to C-08 trust pins.

    The trusted operator prepares session services/keys first, then registers
    their exact existing trust configuration. No wallet/model call is made.
    """
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    template = resolve_source(
        template_source,
        retention_root=template_source.parent,
        quarantine_journal=quarantine_journal,
        reference_root=reference_root,
    )
    if not sessions or any(not Path(p).is_absolute() for p in sessions):
        raise ValueError("exact private session roots required")
    signer = development_signer(root)
    key = signer.verification_key
    payload = {
        "schema": "carbon.cw1.development-rule-registration.v1",
        "rule": RULE,
        "rule_digest": rule_digest(),
        "created_at_micros": time.time_ns() // 1000,
        "shared_bindings": template.bindings,
        "case_manifest": template.manifest,
        "quarantine_journal": str(quarantine_journal),
        "reference_root": str(reference_root),
        "sessions": sessions,
        "verification_key": {
            "key_id": key.key_id,
            "public_key": key.public_key.hex(),
            "valid_from_micros": key.valid_from_micros,
            "valid_until_micros": key.valid_until_micros,
        },
    }
    body = _seal(root, "scoring-registration.json", payload, (), "RULE_REGISTRATION")
    return digest(canonical(body))


def register_fresh_research(
    root, *, prepared_roots, quarantine_journal, reference_root, sessions
):
    """Prospective v2 registration from exact prepared inputs, before outcomes.

    No historical source is promoted to fit a new cohort. Full source bindings
    must agree downstream in addition to these independently frozen input pins.
    """
    from carbon.development_session.research_profile import (
        document as research_document,
    )

    if len(prepared_roots) != 2 or set(map(str, prepared_roots)) != set(sessions):
        raise ValueError("exact control/challenger trust roots required")
    profiles = [read_json(p / "profile.json") for p in prepared_roots]
    manifests = [read_json(p / "case-manifest.json") for p in prepared_roots]
    if any(p != research_document() for p in profiles) or manifests[0] != manifests[1]:
        raise ValueError("matched prospective research profile/cohort required")
    if any((p / "evaluations").exists() for p in prepared_roots):
        raise ValueError("register before either construction starts")
    freezes = [read_json(p / "final-construction-freeze.json") for p in prepared_roots]
    if any(f["profile_digest"] != digest(canonical(profiles[0])) for f in freezes):
        raise ValueError("construction profile freeze differs")
    for prepared, freeze, manifest in zip(
        prepared_roots, freezes, manifests, strict=True
    ):
        if (
            set(freeze)
            != {
                "schema",
                "epoch",
                "strategy_digest",
                "profile_digest",
                "cohort_digest",
                "randomness_digests",
            }
            or freeze["schema"] != "carbon.autoresearch.final-construction.v1"
        ):
            raise ValueError("exact prospective construction freeze required")
        cases = [
            read_json(prepared / (row["name"] + "-case.json"))
            for row in manifest["cases"]
        ]
        if (
            len(cases) != 24
            or freeze["epoch"] != manifest["epoch"]
            or freeze["cohort_digest"] != digest(canonical(cases))
        ):
            raise ValueError("frozen final role/cohort association differs")
        if any(
            digest(canonical(case)) != row["case_digest"]
            for case, row in zip(cases, manifest["cases"], strict=True)
        ):
            raise ValueError("prepared case association changed")
        if (
            len(freeze["randomness_digests"]) != 3
            or len(set(freeze["randomness_digests"])) != 3
        ):
            raise ValueError("three distinct frozen construction replicas required")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    signer = development_signer(root)
    key = signer.verification_key
    manifest = manifests[0]
    active_digest = digest(canonical(profiles[0]))
    payload = {
        "schema": "carbon.cw1.development-rule-registration.v2",
        "rule": RULE,
        "rule_digest": rule_digest(),
        "research_profile": profiles[0],
        "created_at_micros": time.time_ns() // 1000,
        "shared_bindings": {
            "resource_policy_digest": active_digest,
            "scoring_policy_digest": active_digest,
            "training_data_commitment": manifest["training_archive_digest"],
            "worker_image_digest": manifest["worker_image"],
            "case_manifest_digest": digest(canonical(manifest)),
        },
        "case_manifest": manifest,
        "source_roles": {
            "baseline": str(prepared_roots[0]),
            "challenger": str(prepared_roots[1]),
        },
        "construction_freezes": dict(
            zip(map(str, prepared_roots), freezes, strict=True)
        ),
        "quarantine_journal": str(quarantine_journal),
        "reference_root": str(reference_root),
        "sessions": sessions,
        "verification_key": {
            "key_id": key.key_id,
            "public_key": key.public_key.hex(),
            "valid_from_micros": key.valid_from_micros,
            "valid_until_micros": key.valid_until_micros,
        },
    }
    body = _seal(root, "scoring-registration.json", payload, (), "RULE_REGISTRATION")
    return digest(canonical(body))


def registration(root, expected):
    if (root / "derivation-revoked.json").exists():
        raise ValueError("derived evidence signing authority revoked")
    body = read_json(root / "scoring-registration.json")
    if digest(canonical(body)) != expected:
        raise ValueError("registration pin mismatch")
    k = dict(body["payload"]["verification_key"])
    k["public_key"] = bytes.fromhex(k["public_key"])
    key = DevelopmentVerificationKey(**k)
    value = _verify(body, key)
    if value.get("schema") not in {
        "carbon.cw1.development-rule-registration.v1",
        "carbon.cw1.development-rule-registration.v2",
    }:
        raise ValueError("unsupported rule registration version")
    if value.get("schema") == "carbon.cw1.development-rule-registration.v2":
        from carbon.development_session.research_profile import (
            document as research_document,
        )

        if value.get("research_profile") != research_document():
            raise ValueError("registered research scope changed")
    if value["rule"] != RULE:
        raise ValueError("rule changed after registration")
    return value, key


def _resolve(path, reg):
    root = path.parent
    if str(root) not in reg["sessions"]:
        raise ValueError("unregistered source session")
    source = resolve_source(
        path,
        retention_root=root,
        quarantine_journal=Path(reg["quarantine_journal"]),
        reference_root=Path(reg["reference_root"]),
        trusted=reg["sessions"][str(root)],
        research_profile=reg["schema"] == "carbon.cw1.development-rule-registration.v2",
    )
    if (
        any(source.bindings.get(k) != v for k, v in reg["shared_bindings"].items())
        or (
            reg["schema"] == "carbon.cw1.development-rule-registration.v1"
            and source.bindings != reg["shared_bindings"]
        )
        or source.manifest != reg["case_manifest"]
    ):
        raise ValueError("incompatible challenge/cohort/resource/measurement versions")
    if reg["schema"] == "carbon.cw1.development-rule-registration.v2":
        freeze = read_json(root / "final-construction-freeze.json")
        if freeze != reg["construction_freezes"][str(root)] or freeze[
            "strategy_digest"
        ] != digest(canonical(source.strategy)):
            raise ValueError("recipe changed after prospective comparison freeze")
    handoff = load_source_handoff(
        path, retention_root=root, export_root=root / "exports"
    )
    return source, handoff.evidence.account.started_at_micros


def _bundle(source, path):
    root = path.parent
    submission = source.identity["binding"]["submission_id"]
    predictions = {}
    for k in range(3):
        doc = read_json(
            root / "evaluations" / submission / f"prediction-{k}" / "prediction.json"
        )
        array = np.asarray(doc["prediction"], dtype=np.float32).astype("<f8")
        if array.shape != (24, 13, 64) or not np.isfinite(array).all():
            raise ValueError("incomplete candidate prediction")
        predictions[k] = array
    result = []
    bycase = {x["case_digest"]: x["name"] for x in source.manifest["cases"]}
    for role, pairs in source.cohorts:
        for q, _ in pairs:
            replica = int(q.candidate_replica_id.rsplit("-", 1)[1])
            matches = []
            for candidate in predictions[replica]:
                if (
                    FrozenFieldArtifact(
                        q.candidate_binding_digest,
                        q.shape,
                        candidate.tobytes(),
                        "CANDIDATE_PREDICTION",
                    ).artifact_digest
                    == q.candidate_artifact_digest
                ):
                    matches.append(candidate)
            if len(matches) != 1:
                raise ValueError(
                    "candidate artifact absent, altered or ambiguously associated"
                )
            reference = read_json(
                root / (bycase[q.case_digest] + "-reference-result.json")
            )
            payload = Path(reference["solution_path"]).read_bytes()
            if (
                digest(payload) != reference["payload_digest"]
                or FrozenFieldArtifact(
                    q.reference_request_digest, q.shape, payload, "REFERENCE_PRIMARY"
                ).artifact_digest
                != q.reference_artifact_digest
            ):
                raise ValueError("reference artifact changed")
            result.append(
                {
                    "role": role,
                    "request": q.document(),
                    "candidate": matches[0].tolist(),
                    "reference": np.frombuffer(payload, dtype="<f8")
                    .reshape(q.shape)
                    .tolist(),
                    "reference_request": read_json(
                        root / (bycase[q.case_digest] + "-reference-request.json")
                    ),
                }
            )
    return result


def create_report(
    root,
    registration_digest,
    baseline_path,
    challenger_path,
    *,
    image,
    reference_indicators=None,
    resume_completed=False,
    research_runner=None,
):
    reg, _ = registration(root, registration_digest)
    if image.image_id != reg["shared_bindings"]["worker_image_digest"]:
        raise ValueError("diagnostic image differs from registered source environment")
    if reg["schema"].endswith(".v2") and (
        str(baseline_path.parent) != reg["source_roles"]["baseline"]
        or str(challenger_path.parent) != reg["source_roles"]["challenger"]
    ):
        raise ValueError("comparison direction differs from prospective role freeze")
    b, bt = _resolve(baseline_path, reg)
    c, ct = _resolve(challenger_path, reg)
    if reg["schema"].endswith(".v2") and b.bindings != c.bindings:
        raise ValueError("complete source measurement/resource bindings differ")
    if b.identity["receipt_digest"] == c.identity["receipt_digest"]:
        raise ValueError("source replay is not a challenger")
    bundle = {
        "kind": "remeasure",
        "sources": [_bundle(b, baseline_path), _bundle(c, challenger_path)],
    }
    if resume_completed:
        operation = root / "derived-measurements"
        output = read_json(operation / "output.json", 16 * 1024**2)
        resource = read_json(operation / "resources.json")
        if digest((operation / "output.json").read_bytes()) != resource[
            "output_digest"
        ] or canonical(
            read_json(operation / "input/bundle.json", 16 * 1024**2)
        ) != canonical(
            bundle
        ):
            raise ValueError("retained diagnostic association changed")
        if "reference_checks" not in output:
            correction = root / "reference-resolution-recovery"
            result = read_json(correction / "output.json", 16 * 1024**2)
            if (
                digest((correction / "output.json").read_bytes())
                != read_json(correction / "resources.json")["output_digest"]
            ):
                raise ValueError("reference recovery output changed")
            expected = {
                "kind": "reference-resolution",
                "sources": [bundle["sources"][0][:12] + bundle["sources"][0][36:48]],
            }
            if canonical(
                read_json(correction / "input/bundle.json", 16 * 1024**2)
            ) != canonical(expected):
                raise ValueError("reference recovery input changed")
            output["reference_checks"] = result["reference_checks"]
    else:
        if reg["schema"] == "carbon.cw1.development-rule-registration.v2":
            from carbon.development_session.research_numerical import (
                CampaignDerivedMeasurements,
            )

            if type(research_runner) is not CampaignDerivedMeasurements:
                raise ValueError("metered research numerical owner required")
            output = research_runner.run(root, bundle, image)
        else:
            if research_runner is not None:
                raise ValueError("legacy numerical scope cannot use research override")
            output = run_numerical(root, "derived-measurements", bundle, image)
    prospective = reg["created_at_micros"] < min(bt, ct)
    if reference_indicators is not None:
        raise ValueError("caller-supplied reference uncertainty is not admissible")
    indicators = {
        "field": max(x["field_indicator"] for x in output["reference_checks"].values()),
        "energy": max(
            x["energy_indicator"] for x in output["reference_checks"].values()
        ),
        "basis": "SHARED_METHOD_SPATIAL_REFINEMENT_NOT_QUALIFIED_BOUND",
    }
    decision = asdict(
        compare(
            tuple(output["sources"][0]),
            tuple(output["sources"][1]),
            prospective=prospective,
            reference_field_indicator=indicators["field"],
            reference_energy_indicator=indicators["energy"],
        )
    )
    payload = {
        "schema": (
            "carbon.cw1.development-acceptance-report.v2"
            if reg["schema"].endswith(".v2")
            else "carbon.cw1.development-acceptance-report.v1"
        ),
        "registration_digest": registration_digest,
        "rule_digest": rule_digest(),
        "baseline_source": str(baseline_path),
        "challenger_source": str(challenger_path),
        "baseline": b.identity,
        "challenger": c.identity,
        "baseline_strategy": b.strategy,
        "challenger_strategy": c.strategy,
        "construction_started_micros": [bt, ct],
        "prospective": prospective,
        "measurements": output,
        "decision": decision,
        "reference_indicators": indicators,
        "provenance": "AUTHENTIC_RETAINED_MODEL_PREDICTIONS_DERIVED_REMEASUREMENT",
        "limitations": [
            (
                "FRESH_FINAL_DRAWS_SHARED_GENERATOR_NOT_QUALIFIED"
                if reg["schema"].endswith(".v2")
                else "SEEN_DEVELOPMENT_COHORT"
            ),
            "THREE_REPLICAS_NO_POPULATION_CI",
            "REFERENCE_UNQUALIFIED",
        ],
        "paying": False,
        "network_eligible": False,
        "official_eligible": False,
    }
    body = _seal(
        root,
        "development-acceptance.json",
        payload,
        (b.identity["receipt_digest"], c.identity["receipt_digest"]),
        "DERIVED_COMPARISON",
    )
    return DevelopmentAcceptanceRef(root, registration_digest, digest(canonical(body)))


def resolve_acceptance(ref):
    if type(ref) is not DevelopmentAcceptanceRef:
        raise ValueError("nominal development acceptance reference required")
    reg, key = registration(ref.root, ref.registration_digest)
    body = read_json(ref.root / "development-acceptance.json", 16 * 1024**2)
    if digest(canonical(body)) != ref.report_digest:
        raise ValueError("altered comparison report")
    payload = _verify(body, key)
    if payload["registration_digest"] != ref.registration_digest:
        raise ValueError("cross-registration report")
    resolved_sources = []
    for label in ("baseline", "challenger"):
        if (
            reg["schema"].endswith(".v2")
            and str(Path(payload[label + "_source"]).parent)
            != reg["source_roles"][label]
        ):
            raise ValueError("comparison direction changed")
        source, started = _resolve(Path(payload[label + "_source"]), reg)
        resolved_sources.append(source)
        if any(
            canonical(source.identity[k]) != canonical(payload[label][k])
            for k in ("receipt_digest", "source_digest", "binding")
        ):
            raise ValueError("source association changed")
        if (
            started
            != payload["construction_started_micros"][0 if label == "baseline" else 1]
        ):
            raise ValueError("construction time changed")
        _bundle(
            source, Path(payload[label + "_source"])
        )  # Recheck exact retained artifact identities, not a numerical rerun.
    if (
        reg["schema"].endswith(".v2")
        and resolved_sources[0].bindings != resolved_sources[1].bindings
    ):
        raise ValueError("source compatibility changed")
    if body["derivation"]["input_receipts"] != [
        payload[k]["receipt_digest"] for k in ("baseline", "challenger")
    ]:
        raise ValueError("derived signature input association differs")
    prospective = reg["created_at_micros"] < min(payload["construction_started_micros"])
    indicators = payload["reference_indicators"]
    computed = asdict(
        compare(
            tuple(payload["measurements"]["sources"][0]),
            tuple(payload["measurements"]["sources"][1]),
            prospective=prospective,
            reference_field_indicator=indicators["field"],
            reference_energy_indicator=indicators["energy"],
        )
    )
    if payload["prospective"] is not prospective or canonical(computed) != canonical(
        payload["decision"]
    ):
        raise ValueError("decision differs from exact evidence and rule")
    return payload
