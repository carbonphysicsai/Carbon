"""The pool pack builder's class-map producer (Validator 11-01 16:55 / 17:15): a NEW version that registers a coverage
plan (`coverage_plan_sha256` + `coverage_plan_sums_sha256`) builds only with its class-map document and the SHA256SUMS
that lists it, both checked against the registration and carried in the sealed material; a version that registers none
builds exactly as before. Synthetic fixtures only: the constants file is a temporary one, the class names are fixture
names and nothing here is a production value or a registered digest.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_pack import MOTOR, POOL_VERSION, batch, material  # noqa: F401

from carbon.scoring import pool_grader, pool_version
from carbon.scoring import sealed_batch_source as source

KEY = f"{MOTOR} {POOL_VERSION}"


def _builder():
    path = REPOSITORY / "scripts/dev/sealed_exam/pool_pack.py"
    spec = importlib.util.spec_from_file_location("pool_pack_class_map", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _map(targets=None):
    document = {
        "schema": pool_grader.COVERAGE_PLAN_SCHEMA,
        "classes": ["fixture-class-a", "fixture-class-b"],
        "targets": (
            {"A1": "fixture-class-a", "A2": "fixture-class-b"}
            if targets is None
            else targets
        ),
    }
    return pool_grader.coverage_plan_bytes(document)


def _sums(*shas):
    return "".join(f"{sha} *file-{i}.json\n" for i, sha in enumerate(shas)).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _constants(tmp_path, optimizer=None):
    entry = {} if optimizer is None else {"optimizer": optimizer}
    path = tmp_path / "pool_constants.json"
    path.write_text(
        json.dumps({"schema": pool_version.SCHEMA, "versions": {KEY: entry}}),
        encoding="utf-8",
    )
    return path


def _registered(tmp_path, map_raw, sums_raw):
    return _constants(
        tmp_path,
        {
            "coverage_plan_sha256": _sha(map_raw),
            "coverage_plan_sums_sha256": _sha(sums_raw),
        },
    )


def _attach(constants, map_raw, sums_raw, pool=None):
    return _builder().attach_coverage_plan(
        material() if pool is None else pool,
        challenge=MOTOR,
        version=POOL_VERSION,
        coverage_map_raw=map_raw,
        coverage_sums_raw=sums_raw,
        constants=constants,
    )


def _refused(code, call):
    with pytest.raises(SystemExit) as caught:
        call()
    assert str(caught.value).startswith(f"refused: {code}:"), caught.value


def _plain(batch, tmp_path):  # noqa: F811
    document, records = batch
    plain = tmp_path / "plain"
    plain.mkdir(exist_ok=True)
    (plain / source.SEALED_BATCH_FILE).write_bytes(
        source.batch_bytes(document, records)
    )
    return plain


def _files(root):
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# --- a version that registers no coverage plan -------------------------------------------------------


def test_a_version_registering_no_plan_builds_exactly_as_before(
    batch, tmp_path, monkeypatch  # noqa: F811
):
    builder = _builder()
    plain = _plain(batch, tmp_path)
    arguments = {
        "challenge": MOTOR,
        "version": POOL_VERSION,
        "batch_dir": plain,
        "inference_image_id": "sha256:" + "1" * 64,
        "material": material(),
    }
    # the registered constants file (no Motor 1.5 coverage plan) through the new path
    new = builder.build(out_dir=tmp_path / "new", **arguments)
    # the path before the producer: the material goes into the pack untouched
    monkeypatch.setattr(builder, "attach_coverage_plan", lambda m, **_: m)
    old = builder.build(out_dir=tmp_path / "old", **arguments)
    assert new == old
    assert "coverage_plan_sha256" not in new
    assert _files(tmp_path / "new") == _files(tmp_path / "old")
    carried = source.read_batch(tmp_path / "new" / "pack")
    assert carried is not None and carried[0]["pool"] == material()


def test_a_registration_without_the_keys_or_without_an_entry_is_no_plan(tmp_path):
    assert _attach(_constants(tmp_path), None, None) == material()
    other = tmp_path / "other.json"
    other.write_text(
        json.dumps({"schema": pool_version.SCHEMA, "versions": {}}), encoding="utf-8"
    )
    assert _attach(other, None, None) == material()
    assert (
        _builder().registered_coverage_plan(
            MOTOR, POOL_VERSION, constants=pool_version.CONSTANTS
        )
        is None
    )


def test_inputs_for_a_version_that_registers_no_plan_are_refused(tmp_path):
    map_raw = _map()
    sums_raw = _sums(_sha(map_raw))
    for given in ((map_raw, sums_raw), (map_raw, None), (None, sums_raw)):
        _refused(
            "coverage_plan_not_registered",
            lambda given=given: _attach(_constants(tmp_path), *given),
        )


# --- a version that registers one ----------------------------------------------------------------------


def test_the_registered_map_and_sums_ride_in_the_sealed_material_and_the_record(
    batch, tmp_path  # noqa: F811
):
    map_raw = _map()
    sums_raw = _sums("0" * 64, _sha(map_raw))
    constants = _registered(tmp_path, map_raw, sums_raw)
    record = _builder().build(
        challenge=MOTOR,
        version=POOL_VERSION,
        batch_dir=_plain(batch, tmp_path),
        out_dir=tmp_path / "out",
        inference_image_id="sha256:" + "1" * 64,
        material=material(),
        coverage_map_raw=map_raw,
        coverage_sums_raw=sums_raw,
        constants=constants,
    )
    assert record["coverage_plan_sha256"] == _sha(map_raw)
    assert record["coverage_plan_sums_sha256"] == _sha(sums_raw)
    assert json.loads((tmp_path / "out" / "record.json").read_text()) == record
    carried = source.read_batch(tmp_path / "out" / "pack")
    assert carried is not None
    pool = carried[0]["pool"]
    pool_version.check_material(pool)
    assert pool[pool_version.COVERAGE_PLAN] == json.loads(map_raw)
    assert pool[pool_version.COVERAGE_PLAN_SUMS] == sums_raw.decode()
    # what the grader re-derives from the sealed material is exactly the registration
    plan = pool_grader.coverage_plan(pool[pool_version.COVERAGE_PLAN])
    assert plan.sha256 == _sha(map_raw)
    assert _sha(pool[pool_version.COVERAGE_PLAN_SUMS].encode()) == _sha(sums_raw)
    assert pool_grader.sums_list(pool[pool_version.COVERAGE_PLAN_SUMS], plan.sha256)
    # the record names digests and counts only: no target id or class name
    text = json.dumps(record)
    assert "fixture-class" not in text and '"A1"' not in text


def test_a_registered_version_refuses_a_build_without_its_inputs(
    batch, tmp_path  # noqa: F811
):
    map_raw = _map()
    sums_raw = _sums(_sha(map_raw))
    constants = _registered(tmp_path, map_raw, sums_raw)
    for given in ((None, None), (map_raw, None), (None, sums_raw)):
        _refused(
            "coverage_plan_inputs_missing",
            lambda given=given: _attach(constants, *given),
        )
    # the build itself refuses before writing a pack
    _refused(
        "coverage_plan_inputs_missing",
        lambda: _builder().build(
            challenge=MOTOR,
            version=POOL_VERSION,
            batch_dir=_plain(batch, tmp_path),
            out_dir=tmp_path / "out",
            inference_image_id="sha256:" + "1" * 64,
            material=material(),
            constants=constants,
        ),
    )
    assert not (tmp_path / "out").exists()


def test_a_digest_that_is_not_the_registered_one_is_refused(tmp_path):
    map_raw = _map()
    sums_raw = _sums(_sha(map_raw))
    constants = _registered(tmp_path, map_raw, sums_raw)
    other_map = _map({"A1": "fixture-class-b", "A2": "fixture-class-a"})
    _refused(
        "coverage_plan_sha256_mismatch", lambda: _attach(constants, other_map, sums_raw)
    )
    _refused(
        "coverage_plan_sums_sha256_mismatch",
        lambda: _attach(constants, map_raw, sums_raw + b"\n"),
    )


def test_a_map_not_listed_in_its_sums_is_refused(tmp_path):
    map_raw = _map()
    sums_raw = _sums("0" * 64)
    _refused(
        "coverage_plan_not_listed_in_its_sums",
        lambda: _attach(_registered(tmp_path, map_raw, sums_raw), map_raw, sums_raw),
    )


def test_a_map_file_that_is_not_its_canonical_bytes_is_refused(tmp_path):
    loose = json.dumps(json.loads(_map()), indent=1).encode()
    sums_raw = _sums(_sha(loose), _sha(_map()))
    _refused(
        "coverage_plan_not_canonical",
        lambda: _attach(_registered(tmp_path, loose, sums_raw), loose, sums_raw),
    )


@pytest.mark.parametrize(
    "map_raw, sums_raw",
    [
        (b"not json", None),
        (json.dumps({"schema": "other", "classes": [], "targets": {}}).encode(), None),
        (None, b"not a sums line\n"),
        (None, b"\xff\xfe"),
    ],
)
def test_a_malformed_map_or_sums_is_refused(tmp_path, map_raw, sums_raw):
    map_raw = _map() if map_raw is None else map_raw
    sums_raw = _sums(_sha(map_raw)) if sums_raw is None else sums_raw
    _refused(
        "coverage_plan_malformed",
        lambda: _attach(_registered(tmp_path, map_raw, sums_raw), map_raw, sums_raw),
    )


def test_a_target_missing_from_the_map_or_a_set_missing_a_class_is_refused(tmp_path):
    # A2 is not classed
    short = pool_grader.coverage_plan_bytes(
        {
            "schema": pool_grader.COVERAGE_PLAN_SCHEMA,
            "classes": ["fixture-class-a"],
            "targets": {"A1": "fixture-class-a"},
        }
    )
    sums_raw = _sums(_sha(short))
    _refused(
        "target_not_in_the_coverage_plan",
        lambda: _attach(_registered(tmp_path, short, sums_raw), short, sums_raw),
    )
    # the second set (B1 alone) holds only one of the two classes
    both = _map(
        {"A1": "fixture-class-a", "A2": "fixture-class-b", "B1": "fixture-class-a"}
    )
    sums_raw = _sums(_sha(both))
    _refused(
        "set_missing_a_registered_class",
        lambda: _attach(
            _registered(tmp_path, both, sums_raw),
            both,
            sums_raw,
            pool=material(extra_target=True),
        ),
    )


@pytest.mark.parametrize(
    "optimizer, code",
    [
        ({"coverage_plan_sha256": "a" * 64}, "coverage_plan_needs_its_map_and_sums"),
        (
            {"coverage_plan_sums_sha256": "a" * 64},
            "coverage_plan_needs_its_map_and_sums",
        ),
        (
            {"coverage_plan_sha256": None, "coverage_plan_sums_sha256": "a" * 64},
            "coverage_plan_digest_not_registered",
        ),
        (
            {
                "coverage_plan_sha256": pool_version.HUMAN_INPUT,
                "coverage_plan_sums_sha256": pool_version.HUMAN_INPUT,
            },
            "coverage_plan_digest_not_registered",
        ),
        (
            {"coverage_plan_sha256": "A" * 64, "coverage_plan_sums_sha256": "a" * 64},
            "coverage_plan_digest_not_registered",
        ),
    ],
)
def test_an_incomplete_or_unpicked_registration_refuses(tmp_path, optimizer, code):
    with pytest.raises(SystemExit) as caught:
        _attach(_constants(tmp_path, optimizer), None, None)
    assert str(caught.value).startswith(f"refused: {code}"), caught.value


def test_an_unreadable_constants_file_refuses(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "other", "versions": {}}), encoding="utf-8")
    _refused("pool_constants_unreadable", lambda: _attach(bad, None, None))
    _refused(
        "pool_constants_unreadable", lambda: _attach(tmp_path / "absent", None, None)
    )


def test_a_material_already_carrying_a_plan_is_refused(tmp_path):
    map_raw = _map()
    sums_raw = _sums(_sha(map_raw))
    carrying = {
        **material(),
        pool_version.COVERAGE_PLAN: json.loads(map_raw),
        pool_version.COVERAGE_PLAN_SUMS: sums_raw.decode(),
    }
    for constants in (_constants(tmp_path), _registered(tmp_path, map_raw, sums_raw)):
        _refused(
            "coverage_plan_already_in_the_material",
            lambda constants=constants: _attach(
                constants, map_raw, sums_raw, pool=carrying
            ),
        )


def test_the_cli_reads_both_files_as_bytes(tmp_path, monkeypatch):
    builder = _builder()
    seen = {}

    def capture(**kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(builder, "build", capture)
    map_path, sums_path = tmp_path / "map.json", tmp_path / "SHA256SUMS"
    map_path.write_bytes(_map())
    # CRLF kept: the registered digest names the file's own bytes
    sums_path.write_bytes(b"a" * 64 + b" *x\r\n")
    common = [
        "build",
        "--challenge",
        MOTOR,
        "--version",
        POOL_VERSION,
        "--batch-dir",
        "b",
        "--set-dir",
        "s",
        "--out-dir",
        "o",
        "--inference-image-id",
        "sha256:" + "1" * 64,
    ]
    assert (
        builder.main(
            common
            + ["--coverage-map", str(map_path), "--coverage-sums", str(sums_path)]
        )
        == 0
    )
    assert seen["coverage_map_raw"] == _map()
    assert seen["coverage_sums_raw"] == b"a" * 64 + b" *x\r\n"
    seen.clear()
    assert builder.main(common) == 0
    assert seen["coverage_map_raw"] is None and seen["coverage_sums_raw"] is None
