"""The Launchpad's analysis image in the worker-image release (IMAGE-RELEASE-01).

The Test Lead (2026-10-06): the readiness gate's prelive carrier containment
check needs the miner analysis image (`analysis_image_manifest`) on every host,
so it ships in `worker-images-v1` with the workers - built by its own builder
(`carbon.development_session.research_image`, as `install_miner.sh` builds it)
on the released C-03 worker, pushed by digest, its manifest attached. A host
pulls it like any released image. What is held, with a fake docker CLI:
- the release record carries the analysis manifest and its `d4` identity
  labels, never the C-03 set;
- a pulled manifest is the containment check's own: `containment_check`
  loads it and `research_image.verify_image` accepts the pulled image;
- a label or digest mismatch, or a worker manifest offered as the analysis
  image, is refused.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_worker_image_release import (
    ENTRYPOINT,
    refused,
    run,
    tools,  # noqa: F401 - fixture
    write,
)

from carbon.development_session import containment_check, research_image
from carbon.development_session.profile import canonical, digest

C03 = "sha256:" + "1" * 64
IMAGE = "sha256:" + "a" * 64
REPO = "ghcr.io/carbonphysicsai/carbon-miner-analysis"
REFERENCE = f"{REPO}@{IMAGE}"
LABEL = "org.opencontainers.image.carbon."


def manifest():
    """The manifest `research_image.build_analysis_image` writes."""
    runtime = digest(canonical(research_image.runtime_document(C03)))
    return {
        "schema": research_image.SCHEMA,
        "image_id": IMAGE,
        "parent_image": C03,
        "runtime_digest": runtime,
    }


def labels(value=None, **changes):
    value = value or manifest()
    return {
        LABEL + "d4.runtime": value["runtime_digest"],
        LABEL + "d4.parent": value["parent_image"],
        # Inherited from the C-03 parent; not part of the analysis identity.
        LABEL + "c03.scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
        **changes,
    }


def inspected(image_labels=None, **changes):
    return {
        "Id": IMAGE,
        "RepoDigests": [REFERENCE],
        "Os": "linux",
        "Architecture": "amd64",
        "Config": {
            "User": "65532:65532",
            "Entrypoint": ENTRYPOINT,
            "Labels": labels() if image_labels is None else image_labels,
        },
        "RootFS": {"Layers": ["sha256:" + c * 64 for c in "567"]},
        **changes,
    }


def record():
    value = manifest()
    return {
        "schema": "carbon.worker-image-release.v1",
        "kind": "analysis",
        "release_tag": "worker-images-v1",
        "source_commit": "f" * 40,
        "repository": REPO,
        "registry_digest": IMAGE,
        "reference": REFERENCE,
        "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
        "security_acceptance": "HUMAN_INPUT",
        "image_store": "containerd",
        "labels": {
            LABEL + "d4.runtime": value["runtime_digest"],
            LABEL + "d4.parent": value["parent_image"],
        },
        "manifest": value,
    }


def pull(tools, tmp_path, rec, **kwargs):  # noqa: F811
    out = tmp_path / "analysis-image.json"
    completed, calls = run(
        tools,
        "pull",
        "--record",
        str(write(tmp_path / "r.json", rec)),
        "--out",
        str(out),
        CARBON_FAKE_REF=REFERENCE,
        CARBON_FAKE_ID=IMAGE,
        **kwargs,
    )
    return completed, calls, out


class FakeCLI:
    """What `research_image.verify_image` inspects: the pulled image and its
    C-03 parent, the parent's layers a prefix of the image's."""

    def json(self, arguments):
        if arguments[:2] == ["image", "inspect"] and arguments[2] == IMAGE:
            return inspected()
        if arguments[:2] == ["image", "inspect"] and arguments[2] == C03:
            return {"RootFS": {"Layers": ["sha256:" + c * 64 for c in "56"]}}
        raise AssertionError(arguments)


def test_a_pulled_analysis_manifest_satisfies_the_containment_check(
    tmp_path, tools  # noqa: F811
):
    completed, calls, out = pull(tools, tmp_path, record(), inspect=inspected())
    assert completed.returncode == 0, completed.stderr
    assert calls == [
        f"pull {REFERENCE}",
        f"image inspect --format {{{{json .}}}} {REFERENCE}",
    ]
    # Byte for byte what the builder writes, and the containment check's own.
    assert json.loads(out.read_text()) == manifest()
    image, reason = containment_check.load_image(out)
    assert reason is None
    assert research_image.verify_image(image, FakeCLI()) == image


@pytest.mark.parametrize("label", ["d4.runtime", "d4.parent"])
def test_a_changed_identity_label_is_refused(tmp_path, tools, label):  # noqa: F811
    changed = labels(**{LABEL + label: "sha256:" + "9" * 64})
    completed, _, out = pull(tools, tmp_path, record(), inspect=inspected(changed))
    assert refused(completed) == "label_mismatch"
    assert not out.exists()


def test_another_image_under_the_reference_is_refused(tmp_path, tools):  # noqa: F811
    completed, _, out = pull(
        tools, tmp_path, record(), inspect=inspected(Id="sha256:" + "b" * 64)
    )
    assert refused(completed) == "image_id_mismatch"
    assert not out.exists()


def test_a_worker_manifest_is_never_the_analysis_image(tmp_path, tools):  # noqa: F811
    value = record()
    value["manifest"] = {
        "schema": "carbon.c03.worker-image.v1",
        "image_id": IMAGE,
        "parent_image": C03,
        "runtime_digest": manifest()["runtime_digest"],
    }
    completed, calls, _ = pull(tools, tmp_path, value)
    assert refused(completed) == "manifest_invalid"
    assert calls == []
    del value["manifest"]
    completed, calls, _ = pull(tools, tmp_path, value)
    assert refused(completed) == "record_invalid"


def test_the_release_records_the_analysis_identity(tmp_path, tools):  # noqa: F811
    path = write(tmp_path / "analysis-worker-image.json", manifest())
    out = tmp_path / "analysis-worker-image.release.json"
    completed, _ = run(
        tools,
        "record",
        "--kind",
        "analysis",
        "--manifest",
        str(path),
        "--repository",
        REPO,
        "--tag",
        "worker-images-v1",
        "--commit",
        "f" * 40,
        "--out",
        str(out),
        CARBON_FAKE_REF=REFERENCE,
        CARBON_FAKE_ID=IMAGE,
        CARBON_FAKE_INSPECT=json.dumps(inspected()),
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(out.read_text()) == record()
