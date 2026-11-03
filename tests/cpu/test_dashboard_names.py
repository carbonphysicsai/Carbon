"""Challenge display names: a deploy-time map, never a list in the page.

`data/names.json` (written by `build --names`, or served by the Worker from the
CHALLENGE_NAMES var) maps a Challenge id to a plain label. The page shows the name and
falls back to the id in title case (tests/cpu/dashboard_check.cjs). Here: the build
writes only plain labels, the CLI refuses a bad one, and the Worker serves the var,
else the build's file, else 404, and ignores a var that holds anything but plain labels.
"""

from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from carbon.dashboard import __main__ as cli
from carbon.dashboard import build, feed
from tests.cpu import test_dashboard_worker as base

NAMES = {"electric-motor-magnetics": "Motor", "f02": "Burst Thermal"}


def test_the_build_writes_the_names_file(tmp_path):
    build.write_names(tmp_path, NAMES)
    written = json.loads((tmp_path / "data" / "names.json").read_text(encoding="utf-8"))
    assert written == {"schema": build.NAMES_SCHEMA, "names": NAMES}


@pytest.mark.parametrize(
    "names",
    [
        {},
        [],
        {"f02": ""},
        {"f02": "<b>Burst</b>"},
        {"f02": "x" * 41},
        {"f02": 7},
        {"": "Burst Thermal"},
        {"f02": " Burst"},
    ],
)
def test_the_build_refuses_a_name_that_is_not_a_plain_label(tmp_path, names):
    with pytest.raises(ValueError):
        build.write_names(tmp_path, names)
    assert not (tmp_path / "data" / "names.json").exists()


def test_the_command_writes_names_and_refuses_a_bad_one(tmp_path, capsys):
    good = tmp_path / "names.json"
    good.write_text(json.dumps(NAMES), encoding="utf-8")
    out = tmp_path / "site"
    assert (
        cli.main(
            [
                "build",
                "--fixtures",
                "--no-showcase",
                "--out",
                str(out),
                "--names",
                str(good),
            ]
        )
        == 0
    )
    assert (
        json.loads((out / "data" / "names.json").read_text(encoding="utf-8"))["names"]
        == NAMES
    )
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"f02": "<script>"}), encoding="utf-8")
    assert (
        cli.main(
            [
                "build",
                "--fixtures",
                "--no-showcase",
                "--out",
                str(tmp_path / "s2"),
                "--names",
                str(bad),
            ]
        )
        == 1
    )
    assert "names refused" in capsys.readouterr().err


def _serve(tmp_path, env_names, built_names):
    tmp_path.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    trust = feed.Trust(keys=frozenset({base._public(key)}))
    site = tmp_path / "site"
    build.build(site, [base._production(base._fixture(), key)], trust)
    if built_names:
        build.write_names(site, built_names)
    env = {
        "FEED_URLS": "https://validator.example/carbon/v1/feed/a",
        "FEED_KEYS": base._public(key),
    }
    if env_names is not None:
        env["CHALLENGE_NAMES"] = env_names
    answers = base._worker(tmp_path, str(site), env, {}, ["/data/names.json"])
    return answers[0]


def test_the_worker_serves_the_var_first(tmp_path):
    answer = _serve(tmp_path, json.dumps(NAMES), {"f02": "From the build"})
    assert answer["status"] == 200
    assert json.loads(answer["body"])["names"] == NAMES


def test_the_worker_falls_back_to_the_builds_file_then_to_nothing(tmp_path):
    answer = _serve(tmp_path / "a", None, {"f02": "From the build"})
    assert answer["status"] == 200
    assert json.loads(answer["body"])["names"] == {"f02": "From the build"}
    assert _serve(tmp_path / "b", None, None)["status"] == 404


@pytest.mark.parametrize("var", ["not json", "[]", json.dumps({"f02": "<b>"}), "{}"])
def test_the_worker_ignores_a_var_that_is_not_plain_labels(tmp_path, var):
    assert _serve(tmp_path, var, None)["status"] == 404
