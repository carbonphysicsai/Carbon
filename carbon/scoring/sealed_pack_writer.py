"""The sealed graders' receiver-pack writer (Motor's `write_sealed_pack`, generalised for F02 and F08).

A sealed batch's complete receiver pack under a new, empty ``root`` (the pack, public and private root; the manifest
the receiver seals is ``root / MANIFEST_NAME``): the Challenge's public roles, the sealed batch's private roles (from
its kit's ``private_roles``, Data Collection's bank) and the grader's accuracy_definition, reference_rows,
solver_evidence, score_pack and source_registration. It mirrors `physical.write_development_pack`: ``calibration``
writes the minimum-free calibration pack for ``inference_image_id``; ``baseline_binding_raw`` with
``calibration_pack_root`` writes the per-image pack from the baseline's graded run on this batch. Without either the
pack carries no leg minimums (none were measured on this batch).

A new module: no development pack file changes, so no development producer digest moves. This file is part of each
using grader's ``FILES``. DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from carbon.scoring import physical_dual_pack as physical


def write(
    chosen,
    kit,
    root,
    bank,
    *,
    challenge,
    version,
    is_sealed_bank,
    refusal,
    pack_suffix,
    inference_image_id=None,
    device_class=None,
    calibration=False,
    baseline_binding_raw=None,
    calibration_pack_root=None,
):
    """Write the sealed pack for ``bank`` and return the draft manifest's path.

    ``chosen`` is the sealed adapter for exactly ``version``; ``kit`` the Challenge's sealed pack module;
    ``refusal`` the grader's typed refusal, raised when ``bank`` is not its sealed grid.
    """
    from carbon.challenge_kit import physical_pack

    if chosen is None:
        raise ValueError(f"no sealed {challenge} adapter for this Challenge version")
    if not is_sealed_bank(bank):
        raise refusal
    physics = physical_pack.physics_contract(challenge, version)
    if type(physics) is not dict or set(physics) != {"version", "definition"}:
        raise ValueError(
            "pack physics role is not in its {version, definition} envelope"
        )
    generated = chosen.physics_contract()
    if generated is not None and generated != physics:
        raise ValueError("pack physics role differs from the generated contract")
    root = Path(root)
    manifest_path = physical_pack.write_public_pack(
        root, challenge, version, exposed_development_bank=False
    )
    public = physical_pack.public_roles(challenge, version)
    draft = json.loads(manifest_path.read_bytes())
    (root / "private").mkdir(mode=0o700, exist_ok=True)
    for role, body in kit.private_roles(bank).items():
        name = f"private/{role}.{'npz' if role == 'case_bank' else 'json'}"
        (root / name).write_bytes(body)
        draft["private"][role] = {"path": name}
    draft["pack_version"] = draft["pack_version"] + pack_suffix
    inputs = {
        "bank": bank,
        "physics": physics,
        "interface_raw": public["interface"],
        "train_raw": public["train"],
        "limits_raw": public["important_limit_definition"],
        "objective_raw": public["design_objective"],
    }
    if calibration and baseline_binding_raw is not None:
        raise ValueError("a calibration pack takes no baseline binding")
    minimums = "calibration" if calibration else None
    if baseline_binding_raw is not None:
        if calibration_pack_root is None:
            raise ValueError("a baseline binding needs its calibration pack")
        platform, calibration_documents = physical._calibration_platform(
            chosen, calibration_pack_root, baseline_binding_raw, inputs
        )
        if (
            inference_image_id is not None
            and inference_image_id != platform["inference_image_id"]
        ) or (device_class is not None and device_class != platform["device_class"]):
            raise ValueError("inference platform differs from the baseline run's")
        minimums = physical.baseline_minimums(
            chosen, baseline_binding_raw, calibration_documents=calibration_documents
        )
    else:
        platform = physical.leg_minimum_platform(
            inference_image_id, device_class or physical.DEVICE_CLASS
        )
    documents = physical.pack_documents(
        chosen, minimums=minimums, platform=platform, **inputs
    )
    for role, body in documents.items():
        scope = "public" if role == "accuracy_definition" else "private"
        name = f"{scope}/{role}.json"
        (root / name).write_bytes(body)
        draft[scope][role] = {"path": name}
    manifest_path.write_bytes(physical.canonical(draft))
    return manifest_path


__all__ = ["write"]
