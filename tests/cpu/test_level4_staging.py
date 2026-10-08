"""The Level 4 staging contract: `carbon.level4.staging` (development only).

Claims tested:

1. The three forms carry the same bytes: a lowered directory (the CLI's
   layout), the JSON envelope and a worker's workspace round-trip exactly,
   and the submission digest is the manifest's.
2. Every name is checked against its bytes: a tampered document, a manifest
   that is not the declared submission, a malformed name, non-canonical
   base64 and an unexpected directory entry are typed refusals.
3. A worker's staged submission that does not match its record is
   `StagingCorrupt` (FAILED_INFRA), never the candidate's refusal.
4. The bundle a staging round-trip returns passes G0's verify unchanged.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, staging, submission
from carbon.level4.tooling import through_bprime

MAX_BYTES = 1 << 24
INTERFACE = "sha256:" + "1" * 64


@pytest.fixture(scope="module")
def bundle():
    import jax
    import jax.numpy as jnp

    allowlist = allowlist_module.load()

    def forward(p, x):
        return jnp.tanh(x @ p[0])

    def init(key):
        return [jax.random.normal(key, (3, 2))]

    _, fwd, _ = through_bprime(
        forward,
        ([jnp.ones((3, 2))], jnp.ones((4, 3))),
        role="forward",
        allowlist=allowlist,
        input_names=["params/0", "inputs/x"],
        max_bytes=MAX_BYTES,
    )
    _, ini, _ = through_bprime(
        init,
        (jax.random.PRNGKey(0),),
        role="init",
        allowlist=allowlist,
        input_names=["carbon/key"],
        max_bytes=MAX_BYTES,
    )
    manifest, files = submission.build(
        challenge="example",
        interface=INTERFACE,
        allowlist=allowlist,
        forward=fwd,
        init=ini,
    )
    return allowlist, submission.canonical(manifest), files


def test_the_three_forms_carry_the_same_bytes(bundle, tmp_path):
    allowlist, raw_manifest, files = bundle
    digest = staging.check(raw_manifest, files)
    assert digest == submission.name(raw_manifest)
    staging.write_directory(tmp_path, raw_manifest, files)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [staging.MANIFEST] + [n.split(":", 1)[1] + ".json" for n in files]
    )
    assert staging.read_directory(tmp_path) == (digest, raw_manifest, files)
    envelope = staging.envelope(raw_manifest, files)
    assert envelope["submission"] == digest
    assert staging.from_envelope(envelope) == (digest, raw_manifest, files)
    staged = staging.workspace(raw_manifest, files)
    assert all("/" not in name and ":" not in name for name in staged)
    assert staging.from_workspace(staged, digest) == (raw_manifest, files)
    manifest, parsed = submission.verify(
        raw_manifest,
        files,
        allowlist=allowlist,
        challenge="example",
        interface=INTERFACE,
        max_bytes=MAX_BYTES,
    )
    assert set(parsed) == {"forward", "init"} and manifest["level"] == 4


def _refused(code, call, *args):
    with pytest.raises(graph.GraphRefused) as refused:
        call(*args)
    assert refused.value.code == code


def test_every_name_is_checked_against_its_bytes(bundle, tmp_path):
    _, raw_manifest, files = bundle
    name = next(iter(files))
    tampered = {**files, name: files[name] + b" "}
    _refused("document_digest_mismatch", staging.check, raw_manifest, tampered)
    _refused("staging_name", staging.check, raw_manifest, {"forward": files[name]})
    envelope = staging.envelope(raw_manifest, files)
    _refused(
        "staging_submission_mismatch",
        staging.from_envelope,
        {**envelope, "submission": "sha256:" + "0" * 64},
    )
    _refused("staging_schema", staging.from_envelope, {**envelope, "schema": "x"})
    _refused("staging_malformed", staging.from_envelope, {**envelope, "extra": 1})
    padded = {**envelope, "manifest": envelope["manifest"] + "\n"}
    _refused("staging_base64", staging.from_envelope, padded)
    staging.write_directory(tmp_path, raw_manifest, files)
    (tmp_path / "notes.txt").write_text("x")
    _refused("staging_unexpected_entry", staging.read_directory, tmp_path)
    (tmp_path / "notes.txt").unlink()
    (tmp_path / staging.MANIFEST).unlink()
    _refused("staging_manifest_missing", staging.read_directory, tmp_path)


def test_a_corrupt_workspace_is_carbons(bundle):
    _, raw_manifest, files = bundle
    digest = staging.check(raw_manifest, files)
    staged = staging.workspace(raw_manifest, files)
    name = next(n for n in staged if n.startswith(staging.WORKSPACE_PREFIX))
    for broken in (
        {**staged, name: staged[name] + b" "},
        {k: v for k, v in staged.items() if k != staging.WORKSPACE_MANIFEST},
    ):
        with pytest.raises(staging.StagingCorrupt) as corrupt:
            staging.from_workspace(broken, digest)
        assert corrupt.value.kind == "FAILED_INFRA"
    with pytest.raises(staging.StagingCorrupt):
        staging.from_workspace(staged, "sha256:" + "0" * 64)
