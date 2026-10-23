"""F08 1.4 / F02 2.3 catalog settings schemas (Graphite Test, 2026-10-22):
their packets' float32 builds are pinned by sha256, so `pipeline add` finds a
schema for them instead of refusing catalog_library_not_pinned."""

from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from carbon.backbone_catalog import settings

ROOT = Path(__file__).resolve().parents[2]
#: Operator inputs (untracked): the checkout's own, or the main checkout's
#: when this runs in a worktree under it.
PACKETS = next(
    (
        base / "codex-queue/inputs/physical_catalog_14"
        for base in (ROOT, *ROOT.parents[:2])
        if (base / "codex-queue/inputs/physical_catalog_14").is_dir()
    ),
    ROOT / "codex-queue/inputs/physical_catalog_14",
)


def test_each_schema_is_registered_with_the_levers_vocabulary():
    for schema in (settings.F08_LEVERS, settings.F02_LEVERS):
        assert settings.SCHEMAS[schema.schema_id] is schema
        assert schema.configuration == settings.LEVERS.configuration
        assert schema.train_use == settings.LEVERS.train_use
        assert settings.PRECISIONS[schema.schema_id] == ("bfloat16", "float16")
        assert settings.schema_for_build(schema.build_sha256) == schema.schema_id
    builds = [s.build_sha256 for s in settings.SCHEMAS.values()]
    assert len(builds) == len(set(builds))


@pytest.mark.skipif(not PACKETS.is_dir(), reason="packets are operator inputs")
@pytest.mark.parametrize(
    "packet, schema",
    [
        ("t_f08_neuralop_fno_baseline", settings.F08_LEVERS),
        ("t_f08_transolver_baseline", settings.F08_LEVERS),
        ("t_f02_physicsnemo_fullyconnected_baseline", settings.F02_LEVERS),
    ],
)
def test_the_packet_builds_are_the_pinned_bytes(packet, schema):
    raw = (PACKETS / packet / "source.tar.gz").read_bytes()
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        member = next(
            m
            for m in archive.getmembers()
            if m.name.endswith("carbon_candidate/build.py")
        )
        build = archive.extractfile(member).read()
    assert "sha256:" + hashlib.sha256(build).hexdigest() == schema.build_sha256


def test_the_float32_coverage_schema_pins_the_f08_f02_port_builds():
    schema = settings.COVERAGE_F32
    assert settings.SCHEMAS[schema.schema_id] is schema
    assert schema.configuration == settings.COVERAGE.configuration
    assert schema.train_use == settings.COVERAGE.train_use
    assert settings.schema_for_build(schema.build_sha256) == schema.schema_id
    assert schema.build_sha256 != settings.COVERAGE.build_sha256
