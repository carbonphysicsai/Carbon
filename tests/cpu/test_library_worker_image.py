"""At-use identity checks for the distinct offline library worker child."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session.library_bundles import (
    LibraryBundleRef,
    ProvisionedLibraryEnvironment,
)
from carbon.development_session.research_image import (
    LibraryWorkerImage,
    verify_library_worker_image,
)
from carbon.reconstruction.worker.model import WorkerImageIdentity


def _sha(char):
    return "sha256:" + char * 64


def _fixture():
    parent = WorkerImageIdentity(
        _sha("a"),
        _sha("a"),
        _sha("b"),
        _sha("c"),
        _sha("d"),
        _sha("e"),
        _sha("f"),
        _sha("0"),
    )
    ref = LibraryBundleRef(
        "carbon.library-bundle-ref.v1",
        _sha("1"),
        "python",
        "jax-cuda13-py311",
        _sha("2"),
    )
    provisioned = ProvisionedLibraryEnvironment(
        ref,
        parent.image_id,
        Path("/private/checked-context"),
        _sha("3"),
        _sha("4"),
    )
    image = LibraryWorkerImage(provisioned, parent, ref.to_dict())
    entrypoint = [
        "/opt/carbon-worker/bin/python",
        "-I",
        "-m",
        "carbon.reconstruction.worker.entrypoint",
    ]
    parent_meta = {
        "Id": parent.image_id,
        "Config": {"Entrypoint": entrypoint},
        "RootFS": {"Layers": [_sha("5"), _sha("6")]},
    }
    child_meta = {
        "Id": image.image_id,
        "Os": "linux",
        "Architecture": "amd64",
        "Config": {
            "User": "65532:65532",
            "Entrypoint": entrypoint,
            "Labels": {
                "org.opencontainers.image.carbon.development.library-bundle": ref.bundle_digest,
                "org.opencontainers.image.carbon.development.parent": parent.image_id,
            },
        },
        "RootFS": {"Layers": [_sha("5"), _sha("6"), _sha("7")]},
    }
    return image, parent_meta, child_meta


class _Inspect:
    def __init__(self, image, parent, child):
        self.image, self.parent, self.child = image, parent, child

    def json(self, args):
        assert args[:2] == ["image", "inspect"]
        return self.child if args[2] == self.image.image_id else self.parent


def test_provisioned_child_uses_distinct_parent_and_bundle_bindings(monkeypatch):
    from carbon.development_session import research_image

    image, parent, child = _fixture()
    monkeypatch.setattr(
        research_image, "doctor", lambda **kwargs: SimpleNamespace(eligible=True)
    )
    assert verify_library_worker_image(image, _Inspect(image, parent, child)) is image
    for changed in (
        {"Id": _sha("8")},
        {"Config": {**child["Config"], "Entrypoint": ["/bin/sh"]}},
        {"Config": {**child["Config"], "Labels": {}}},
        {"RootFS": {"Layers": [_sha("8")]}},
    ):
        with pytest.raises(ValueError, match="child binding differs"):
            verify_library_worker_image(
                image, _Inspect(image, parent, {**child, **changed})
            )
    with pytest.raises(ValueError, match="identity differs"):
        verify_library_worker_image(
            LibraryWorkerImage(
                image.provisioned,
                image.parent,
                {**image.bundle_ref, "bundle_digest": _sha("9")},
            ),
            _Inspect(image, parent, child),
        )


def test_parent_doctor_refusal_blocks_child_before_inspection(monkeypatch):
    from carbon.development_session import research_image

    image, parent, child = _fixture()
    monkeypatch.setattr(
        research_image, "doctor", lambda **kwargs: SimpleNamespace(eligible=False)
    )
    with pytest.raises(ValueError, match="parent ineligible"):
        verify_library_worker_image(image, _Inspect(image, parent, child))


def test_library_build_keeps_the_bounded_carbon_worker_profile():
    from carbon.development_session.research_carrier import (
        LIBRARY_BUILD_PROVENANCE,
        _worker_profile,
    )

    assert LIBRARY_BUILD_PROVENANCE != "MINER_SELF_REPORTED"
    assert _worker_profile(None, LIBRARY_BUILD_PROVENANCE) == _worker_profile(None)
