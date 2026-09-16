"""Bounded target-free prediction using the accepted C-03 carrier and controls."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import numpy as np

from carbon.reconstruction.model import PredictionReceipt
from carbon.reconstruction.repeats import development_request_digest
from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    create_arguments,
    doctor,
    inspect_effective_controls,
    observe_effective_resources,
    remove_exact_container,
    spawn_watchdog,
)
from carbon.reconstruction.worker.protocol import validated_receipt_payload

from .data import write_once
from .profile import canonical, digest

# Fixed trusted code, never populated from a strategy or model response. The
# version-pinned C-03 receipt decoder is reused only inside this owner wrapper.
PREDICT_CODE = """
import json
from pathlib import Path
from dataclasses import asdict
import numpy as np
from carbon.reconstruction.worker.protocol import _receipt_from_validated_payload
from carbon.reconstruction.service import predict
root=Path('/input')
receipt=_receipt_from_validated_payload(json.loads((root/'receipt.json').read_bytes()),artifact_path=root/'artifact')
query={key:np.asarray(value,dtype=np.float64) for key,value in json.loads((root/'query.json').read_bytes()).items()}
values,proof=predict(receipt,**query)
print(json.dumps({'prediction':values.tolist(),'receipt':asdict(proof)},allow_nan=False,separators=(',',':')))
"""


def isolated_predict(receipt, query, *, root: Path, image, worker, replay_only=False):
    request_digest = development_request_digest(query)
    launch = digest(
        canonical(
            {
                "artifact": receipt.artifact_digest,
                "request": request_digest,
                "image": image.image_id,
                "code": PREDICT_CODE,
                "policy": worker.digest,
            }
        )
    )
    name = "carbon-session-predict-" + launch[7:31]
    stage = root / "input"
    if replay_only:
        intent = json.loads((root / "intent.json").read_bytes())
        if intent["launch"] != launch or intent["container"] != name:
            raise ValueError("retained prediction launch mismatch")
        if (stage / "receipt.json").read_bytes() != canonical(
            validated_receipt_payload(receipt)
        ):
            raise ValueError("retained prediction receipt mismatch")
        if (stage / "query.json").read_bytes() != canonical(
            {key: value.tolist() for key, value in query.items()}
        ):
            raise ValueError("retained prediction query mismatch")
        active = DockerCLI().run(
            ["ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.ID}}"],
            timeout=20,
        )
        if active.stdout.strip():
            raise ValueError(
                "retained prediction carrier still exists; reconcile first"
            )
        controls = json.loads((root / "controls-and-resources.json").read_bytes())
        if digest(canonical(controls["controls"])) != controls["controls_digest"]:
            raise ValueError("retained prediction controls changed")
        return _validated_prediction(root / "prediction.json", receipt, request_digest)
    if root.exists():
        raise ValueError("prediction already started; reconcile existing carrier")
    root.mkdir(parents=True, mode=0o700)
    stage.mkdir(mode=0o755)
    # The operator uses umask 077. Only this read-only export must be
    # traversable by the non-root carrier; the enclosing root stays private.
    stage.chmod(0o755)
    members = list(receipt.artifact_path.rglob("*"))
    files = [item for item in members if item.is_file()]
    if (
        any(item.is_symlink() for item in members)
        or len(files) > 1024
        or sum(item.stat().st_size for item in files) > 128 * 1024**2
    ):
        raise ValueError("prediction artifact export exceeds bound")
    shutil.copytree(receipt.artifact_path, stage / "artifact")
    for path in (stage / "artifact", *(stage / "artifact").rglob("*")):
        path.chmod(0o755 if path.is_dir() else 0o444)
    write_once(stage / "receipt.json", canonical(validated_receipt_payload(receipt)))
    write_once(
        stage / "query.json",
        canonical({key: value.tolist() for key, value in query.items()}),
    )
    (stage / "receipt.json").chmod(0o444)
    (stage / "query.json").chmod(0o444)
    cli = DockerCLI()
    checked = doctor(image_id=image.image_id, image_identity=image, cli=cli)
    if not checked.eligible:
        raise ValueError("prediction host ineligible")
    started = time.time()
    write_once(
        root / "intent.json",
        canonical(
            {
                "launch": launch,
                "container": name,
                "started": started,
                "deadline": started + 600,
                "request_digest": request_digest,
            }
        ),
    )
    created = False
    try:
        cli.run(
            create_arguments(
                container_name=name,
                image_id=image.image_id,
                input_directory=stage,
                cpuset=checked.cpuset,
                launch_digest=launch,
                worker_profile=worker,
            ),
            timeout=30,
        )
        created = True
        spawn_watchdog(
            container_name=name, launch_digest=launch, deadline_unix=started + 600
        )
        cli.run(["start", name], timeout=20)
        controls_digest, controls = inspect_effective_controls(
            cli=cli,
            container_name=name,
            image_id=image.image_id,
            input_directory=stage,
            cpuset=checked.cpuset,
            launch_digest=launch,
            worker_profile=worker,
        )
        output = root / "prediction.json"
        cli.stream_to_file(
            ["exec", name, "/opt/carbon-worker/bin/python", "-I", "-c", PREDICT_CODE],
            output,
            maximum=2 * 1024**2,
            timeout=max(1, 600 - (time.time() - started)),
        )
        resources = observe_effective_resources(cli=cli, container_name=name)
        write_once(
            root / "controls-and-resources.json",
            canonical(
                {
                    "controls_digest": controls_digest,
                    "controls": controls,
                    "resources": resources,
                    "wall_seconds": time.time() - started,
                }
            ),
        )
        return _validated_prediction(output, receipt, request_digest)
    finally:
        if created:
            remove_exact_container(cli=cli, container_name=name, launch_digest=launch)


def _validated_prediction(output, receipt, request_digest):
    if output.is_symlink() or output.stat().st_size > 2 * 1024**2:
        raise ValueError("prediction output exceeds bound")
    result = json.loads(output.read_bytes())
    proof = PredictionReceipt(**result["receipt"])
    prediction = np.asarray(result["prediction"], dtype=np.float32)
    if (
        proof.artifact_digest != receipt.artifact_digest
        or proof.request_digest != request_digest
    ):
        raise ValueError("prediction association mismatch")
    if (
        prediction.shape != (proof.cases, proof.times, proof.points)
        or not np.isfinite(prediction).all()
    ):
        raise ValueError("prediction shape or values invalid")
    # Same named-array framing used by C-02's prediction receipt owner.
    import hashlib

    framed = hashlib.sha256()
    metadata = canonical(
        {
            "name": "prediction",
            "dtype": prediction.dtype.str,
            "shape": list(prediction.shape),
        }
    )
    payload = prediction.tobytes(order="C")
    framed.update(len(metadata).to_bytes(8, "big"))
    framed.update(metadata)
    framed.update(len(payload).to_bytes(8, "big"))
    framed.update(payload)
    # The exact framing is checked independently in the focused test; an
    # altered output never reaches measurement or a signed session dossier.
    if "sha256:" + framed.hexdigest() != proof.output_digest:
        raise ValueError("prediction output digest mismatch")
    return prediction, proof
