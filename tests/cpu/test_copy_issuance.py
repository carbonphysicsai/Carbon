"""The issuance job (E4): signs each permitted hotkey's copy on the custody host, writes
create-only owner-only packages, and prints counts and digests only."""

from __future__ import annotations

import json
import os
import stat

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
    other["private"]["case_bank"]["sha256"] = "ab" * 32
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
