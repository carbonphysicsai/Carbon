"""The issuance job (E4): signs each permitted hotkey's copy on the custody host, writes
create-only owner-only packages, and prints counts and digests only."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest
from test_copy_delivery import FORMATS, WINDOW, _canonical_pack

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import copy_delivery as delivery
from carbon.challenge_validator import copy_issuance as issuance
from carbon.challenge_validator import copy_route
from carbon.challenge_validator import sealed_pack_import as spi

# Well-formed (base58, 48 chars) stand-ins for two permitted hotkeys.
ONE = "5" + "F" * 47
TWO = "5" + "G" * 47


def _owner_file(path, body):
    path.write_bytes(body)
    path.chmod(0o600)
    return str(path)


@pytest.fixture
def job(tmp_path):
    challenge, version, manifest, files, carried = _canonical_pack("motor-grid")
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / spi.MANIFEST_NAME).write_bytes(manifest)
    for name, body in files.items():
        (pack / name).parent.mkdir(parents=True, exist_ok=True)
        (pack / name).write_bytes(body)
    key = ak.ProducerKey.create(str(tmp_path / "producer.key"))
    config = {
        "schema": issuance.CONFIG_SCHEMA,
        "producer_key": str(tmp_path / "producer.key"),
        "master_key": _owner_file(tmp_path / "master.key", os.urandom(32)),
        "challenge_id": challenge,
        "challenge_version": version,
        "pack": str(pack),
        "batch": _owner_file(
            tmp_path / "batch.json",
            json.dumps(dict(carried, schema=carried["schema"])).encode(),
        ),
        "copies": str(tmp_path / "copies"),
        "window": WINDOW,
        "hotkeys": _owner_file(
            tmp_path / "hotkeys.json", json.dumps([ONE, TWO]).encode()
        ),
    }
    return {"config": config, "key": key, "manifest": manifest, "tmp": tmp_path}


def test_it_writes_each_hotkeys_own_verified_copy_and_prints_no_secret(job, capsys):
    summary = issuance.issue(job["config"])
    canonical = delivery._sha(job["manifest"])
    assert summary == {
        "canonical_digest": canonical,
        "written": 2,
        "held": 0,
        "hotkeys": 2,
        "challenge": job["config"]["challenge_id"],
        "challenge_version": job["config"]["challenge_version"],
    }
    copies = job["tmp"] / "copies"
    names = {}
    for hotkey in (ONE, TWO):
        (path,) = (copies / hotkey).glob("*.json")
        assert path.name == canonical.removeprefix("sha256:") + ".json"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        package = json.loads(path.read_bytes())
        commitment, _payload, copy = copy_route.verify_package(
            package, job["key"].public_key
        )
        assert commitment["fingerprint"] == canonical
        assert copy["validator_hotkey"] == hotkey
        names[hotkey] = package
    # Each hotkey's copy imports as its own and canonicalises to the same pack.
    digests = set()
    for n, (hotkey, package) in enumerate(names.items()):
        store = spi.SealedPackStore(job["tmp"] / f"v{n}")
        digests.add(
            delivery.import_copy(store, package, job["key"].public_key, hotkey=hotkey)
        )
    assert digests == {canonical}
    # The CLI prints counts and digests only: never key material.
    path = job["tmp"] / "job.json"
    path.write_text(json.dumps(job["config"]))
    path.chmod(0o600)
    assert issuance.main(["issue", "--config", str(path)]) == 0
    out = capsys.readouterr().out
    assert job["config"]["master_key"] not in out and "key" not in json.loads(out)
    master = (job["tmp"] / "master.key").read_bytes()
    assert master.hex() not in out and master not in out.encode()


def test_a_second_run_keeps_every_existing_copy(job):
    issuance.issue(job["config"])
    before = {p: p.read_bytes() for p in (job["tmp"] / "copies").rglob("*.json")}
    again = issuance.issue(job["config"])
    assert (again["written"], again["held"]) == (0, 2)
    assert before == {
        p: p.read_bytes() for p in (job["tmp"] / "copies").rglob("*.json")
    }


def test_a_new_permit_holder_gets_a_copy_without_touching_the_others(job):
    issuance.issue(job["config"])
    three = "5" + "H" * 47
    summary = issuance.issue(job["config"], hotkeys=[ONE, TWO, three])
    assert (summary["written"], summary["held"]) == (1, 2)
    assert list((job["tmp"] / "copies" / three).glob("*.json"))


@pytest.mark.parametrize("bad", [[], [ONE, ONE], ["not a hotkey"], "5abc", [ONE, 7]])
def test_malformed_hotkey_lists_are_refused(job, bad):
    with pytest.raises(ak.AnswerKeyRefused, match="copy_issuance_hotkeys"):
        issuance.issue(job["config"], hotkeys=bad)
    assert not (job["tmp"] / "copies").exists() or not list(
        (job["tmp"] / "copies").rglob("*.json")
    )


def test_a_short_or_group_readable_master_key_is_refused(job):
    config = dict(job["config"])
    config["master_key"] = _owner_file(job["tmp"] / "short.key", b"short")
    with pytest.raises(ak.AnswerKeyRefused, match="copy_master_key_invalid"):
        issuance.issue(config)
    open_key = job["tmp"] / "open.key"
    open_key.write_bytes(os.urandom(32))
    open_key.chmod(0o640)
    config["master_key"] = str(open_key)
    with pytest.raises(ak.AnswerKeyRefused, match="owner_only"):
        issuance.issue(config)


def test_a_malformed_job_config_is_refused(job):
    with pytest.raises(ak.AnswerKeyRefused, match="copy_issuance_config_malformed"):
        issuance.issue({"schema": "x"})
    _ = FORMATS


def test_the_pack_set_is_signed_published_once_and_imports_on_a_validator(job):
    from carbon.challenge_validator import sealed_exam_common as common

    challenge = job["config"]["challenge_id"]
    version = job["config"]["challenge_version"]
    # Two real canonical batches: the job's pack, and a second whose exam
    # content (its case bank role) differs.
    other = json.loads(job["manifest"])
    other["private"]["case_bank"]["sha256"] = "sha256:" + "ab" * 32
    other_bytes = json.dumps(other, sort_keys=True).encode()
    first_dir = job["tmp"] / "pack-one"
    second_dir = job["tmp"] / "pack-two"
    for directory, body in ((first_dir, job["manifest"]), (second_dir, other_bytes)):
        directory.mkdir()
        (directory / spi.MANIFEST_NAME).write_bytes(body)
    batches = [delivery._sha(job["manifest"]), delivery._sha(other_bytes)]
    contents = [
        spi.manifest_content(job["manifest"]),
        spi.manifest_content(other_bytes),
    ]
    config = {
        "schema": issuance.SET_CONFIG_SCHEMA,
        "producer_key": job["config"]["producer_key"],
        "challenge_id": challenge,
        "challenge_version": version,
        "batches": batches,
        "packs": {batches[0]: str(first_dir), batches[1]: str(second_dir)},
        "window": WINDOW,
        "inbox": str(job["tmp"] / "inbox"),
    }
    first = issuance.publish_set(config)
    assert first["batches"] == 2 and first["written"] is True
    assert first["set_key"] == common.pack_set_key(
        common.pack_set_document(challenge, version, contents)
    )
    # The same contents give the same key; one changed case bank gives another.
    again = issuance.publish_set({**config, "inbox": str(job["tmp"] / "inbox-2")})
    assert again["set_key"] == first["set_key"]
    changed = json.loads(other_bytes)
    changed["private"]["case_bank"]["sha256"] = "sha256:" + "cd" * 32
    changed_bytes = json.dumps(changed, sort_keys=True).encode()
    third_dir = job["tmp"] / "pack-three"
    third_dir.mkdir()
    (third_dir / spi.MANIFEST_NAME).write_bytes(changed_bytes)
    moved = {
        **config,
        "inbox": str(job["tmp"] / "inbox-3"),
        "batches": [batches[0], delivery._sha(changed_bytes)],
        "packs": {
            batches[0]: str(first_dir),
            delivery._sha(changed_bytes): str(third_dir),
        },
    }
    assert issuance.publish_set(moved)["set_key"] != first["set_key"]
    # A batch with no pack in custody is refused typed.
    missing = {
        **config,
        "packs": {**config["packs"], batches[1]: str(job["tmp"] / "none")},
    }
    with pytest.raises(ak.AnswerKeyRefused, match="copy_issuance_pack_missing"):
        issuance.publish_set(missing)
    # A pack whose manifest is not the one the batch names is refused.
    wrong = {
        **config,
        "packs": {batches[0]: str(second_dir), batches[1]: str(first_dir)},
    }
    with pytest.raises(ak.AnswerKeyRefused, match="copy_issuance_pack_digest_mismatch"):
        issuance.publish_set(wrong)
    assert issuance.publish_set(config)["written"] is False
    (path,) = (job["tmp"] / "inbox" / challenge).glob("set-*.json")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    # A validator verifies and imports it like any signed package.
    value = json.loads(path.read_bytes())
    commitment, payload = ak.verify(value, job["key"].public_key)
    store = spi.SealedPackStore(job["tmp"] / "v")
    assert store.import_pack_set(commitment, payload) == first["set_key"]
    assert store.holds_set(commitment)
    with pytest.raises(ak.AnswerKeyRefused, match="copy_issuance_config_malformed"):
        issuance.publish_set({"schema": "x"})


def test_a_pool_batch_also_gets_each_hotkeys_k_speed_beside_its_copy(
    job, monkeypatch, capsys
):
    """GPU_REBUILD_RULINGS end: the grading host gets K_speed = HMAC(copy key, domain || set id), never the copy key."""
    from carbon.development_session import single_call_timing

    set_id = "sha256:" + "5" * 64
    carried = json.loads((job["tmp"] / "batch.json").read_bytes())
    carried["document"]["pool"] = {"set_digest": set_id}
    (job["tmp"] / "batch.json").write_text(json.dumps(carried))
    monkeypatch.setattr(delivery, "issue_copy", lambda *a, **k: {"stub": k["hotkey"]})
    monkeypatch.setattr(copy_route, "verify_package", lambda *a, **k: None)
    summary = issuance.issue(job["config"])
    assert summary["speed_keys"] == 2 and summary["written"] == 2
    canonical = delivery._sha(job["manifest"]).removeprefix("sha256:")
    master = (job["tmp"] / "master.key").read_bytes()
    keys = {}
    for hotkey in (ONE, TWO):
        path = job["tmp"] / "copies" / hotkey / (canonical + ".speed-key")
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        keys[hotkey] = path.read_bytes()
        assert keys[hotkey] == single_call_timing.speed_key(
            delivery.validator_key(master, hotkey), set_id
        )
        # never the copy key itself
        assert keys[hotkey] != delivery.validator_key(master, hotkey)
    assert keys[ONE] != keys[TWO]
    # create-only: a second run keeps them and writes none
    before = dict(keys)
    again = issuance.issue(job["config"])
    assert again["speed_keys"] == 0 and again["held"] == 2
    assert keys == before
    # the summary and the CLI never carry a key
    out = json.dumps(summary)
    assert all(k.hex() not in out for k in keys.values())


def test_a_batch_without_a_pool_gets_no_speed_key(job):
    summary = issuance.issue(job["config"])
    assert "speed_keys" not in summary
    assert not list((job["tmp"] / "copies").rglob("*.speed-key"))


# --- scripts/dev/sealed_exam/import_copy.py: a delivered copy into a validator's pack store ---------


def _tool():
    path = (
        Path(__file__).resolve().parents[2] / "scripts/dev/sealed_exam/import_copy.py"
    )
    spec = importlib.util.spec_from_file_location("import_copy_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_file(job, hotkey):
    canonical = delivery._sha(job["manifest"]).removeprefix("sha256:")
    return job["tmp"] / "copies" / hotkey / (canonical + ".json")


def test_a_hotkeys_copy_imports_to_the_canonical_digest_and_repeats_are_harmless(
    job, tmp_path, capsys
):
    issuance.issue(job["config"])
    tool = _tool()
    store = tmp_path / "store"
    digest = tool.import_one(store, _copy_file(job, ONE), ONE, job["key"].public_key)
    assert digest == delivery._sha(job["manifest"])
    assert os.stat(store).st_mode & 0o077 == 0
    before = sorted(p.name for p in store.iterdir())
    assert (
        tool.import_one(store, _copy_file(job, ONE), ONE, job["key"].public_key)
        == digest
    )
    assert sorted(p.name for p in store.iterdir()) == before
    # the command prints the digest only
    argv = [
        "--store",
        str(tmp_path / "store2"),
        "--copy",
        str(_copy_file(job, TWO)),
        "--hotkey",
        TWO,
        "--producer-public-key",
        job["key"].public_key,
    ]
    assert tool.main(argv) == 0
    out = capsys.readouterr().out
    assert json.loads(out) == {"canonical_digest": digest}


def test_another_hotkeys_copy_or_a_wrong_producer_key_is_refused_and_stores_nothing(
    job, tmp_path, capsys
):
    issuance.issue(job["config"])
    tool = _tool()
    store = tmp_path / "store"
    argv = [
        "--store",
        str(store),
        "--copy",
        str(_copy_file(job, TWO)),
        "--hotkey",
        ONE,  # TWO's copy presented as ONE's
        "--producer-public-key",
        job["key"].public_key,
    ]
    assert tool.main(argv) == 2
    assert "refused" in json.loads(capsys.readouterr().err)
    wrong_key = "00" * 32
    argv[argv.index(ONE)] = TWO
    argv[-1] = wrong_key
    assert tool.main(argv) == 2
    assert not store.exists() or not [
        p for p in store.iterdir() if not p.name.startswith(".")
    ]


def test_a_copy_file_that_is_not_json_is_refused(job, tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    argv = [
        "--store",
        str(tmp_path / "s"),
        "--copy",
        str(bad),
        "--hotkey",
        ONE,
        "--producer-public-key",
        job["key"].public_key,
    ]
    assert _tool().main(argv) == 2
    assert "refused" in json.loads(capsys.readouterr().err)


# --- scripts/dev/sealed_exam/diagnose_copy.py: which role of a refused copy differs, and how -----------


def _diagnose_tool():
    path = (
        Path(__file__).resolve().parents[2] / "scripts/dev/sealed_exam/diagnose_copy.py"
    )
    spec = importlib.util.spec_from_file_location("diagnose_copy_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_good_copy_reports_every_role_matching_and_the_host_facts(job, capsys):
    issuance.issue(job["config"])
    tool = _diagnose_tool()
    copy = _copy_file(job, ONE)
    report = tool.diagnose(copy, ONE, job["key"].public_key)
    assert report["all_roles_match"] and report["copy_hotkey_matches"]
    assert set(report["roles"]) == {"case_bank", "reference_rows", "solver_evidence"}
    assert all(
        r["match"] and r["pack_sha256"] == r["recomputed_sha256"]
        for r in report["roles"].values()
    )
    assert {"python", "numpy", "platform", "machine", "cpu_count"} <= set(
        report["host"]
    )
    argv = [
        "--copy",
        str(copy),
        "--hotkey",
        ONE,
        "--producer-public-key",
        job["key"].public_key,
    ]
    assert tool.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["all_roles_match"] is True


def test_a_differing_role_is_named_with_where_and_how_much_never_a_value(
    job, monkeypatch, capsys
):
    import io

    import numpy as np

    from carbon.challenge_validator import copy_delivery as cdl

    issuance.issue(job["config"])
    tool = _diagnose_tool()
    real = cdl.expected_roles

    def drifted(challenge, version, kit, bank):
        roles = dict(real(challenge, version, kit, bank))
        rows = json.loads(roles["reference_rows"])
        rows[0]["marker_field"] = 12.5
        roles["reference_rows"] = json.dumps(
            rows, sort_keys=True, separators=(",", ":")
        ).encode()
        roles["solver_evidence"] = roles["solver_evidence"] + b" "
        return roles

    monkeypatch.setattr(cdl, "expected_roles", drifted)
    copy = _copy_file(job, ONE)
    report = tool.diagnose(copy, ONE, job["key"].public_key)
    assert not report["all_roles_match"]
    assert report["roles"]["case_bank"]["match"] is True
    ref = report["roles"]["reference_rows"]
    assert ref["match"] is False and ref["difference"]["kind"] == "keys"
    assert "marker_field" in ref["difference"]["only_recomputed"]
    assert ref["difference"]["path"] == "$[0]"
    assert report["roles"]["solver_evidence"]["first_differing_byte"] > 0
    argv = [
        "--copy",
        str(copy),
        "--hotkey",
        ONE,
        "--producer-public-key",
        job["key"].public_key,
    ]
    assert tool.main(argv) == 3
    assert "12.5" not in capsys.readouterr().out
    # numeric drift of an array and of a float is named by size, not content
    left = np.array([[1.0, 2.0]])

    def npz(array):
        buffer = io.BytesIO()
        np.savez(buffer, inputs=array)
        return buffer.getvalue()

    detail = tool._array_difference(npz(left), npz(left + 1e-9))
    assert detail["kind"] == "elements" and detail["different"] == 2
    assert detail["max_relative_difference"] < 1e-8
    assert tool._json_difference({"a": [1.0]}, {"a": [1.0 + 1e-15]})["kind"] == "float"
