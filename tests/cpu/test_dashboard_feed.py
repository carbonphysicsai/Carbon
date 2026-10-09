"""DASHBOARD-01 D1: the dashboard's own disclosure checks on the score feed.

Every refusal in DASHBOARD_PLAN.md §2 has a case here. A refused document is
never drawn in part, and an accepted board carries only allow-listed fields.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from carbon.dashboard import build, feed, fixtures

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "carbon" / "dashboard"
CHECK = ROOT / "tests" / "cpu" / "dashboard_check.cjs"
HOTKEY = "5" + "F" * 47  # an SS58-shaped synthetic hotkey


def _public(key):
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        .hex()
    )


def _fixture():
    return fixtures.board_document("fixture-challenge-alpha", "gpu:FIXTURE-GPU", seed=1)


def _refused(document, code, trust=None):
    with pytest.raises(feed.FeedRefused) as caught:
        feed.project(document, trust or fixtures.fixture_trust())
    assert caught.value.code == code


def _production(document):
    """The fixture document, re-labelled and re-keyed as a production feed."""
    key = Ed25519PrivateKey.generate()
    text = json.dumps(document).replace("fixture-miner-0", "5" + "G" * 44 + "A")
    body = json.loads(text)
    body["labels"] = [label for label in body["labels"] if label != "FIXTURE"]
    return fixtures.sign(body, key), feed.Trust(keys=frozenset({_public(key)}))


def test_fixture_key_is_the_pinned_constant():
    assert fixtures.fixture_public_key() == feed.FIXTURE_PUBLIC_KEY


def test_fixture_feeds_project_with_labels_and_one_class():
    for document in fixtures.documents():
        board = feed.project(document, fixtures.fixture_trust())
        assert board["labels"][0] == "DEVELOPMENT"
        assert "FIXTURE" in board["labels"] and board["fixture"] is True
        assert board["device_class"] in ("cpu", "gpu:FIXTURE-GPU")
        assert board["standing"][0]["rank"] == 1
        assert board["incumbent"]["hotkey"] in board["miners"]


def test_signed_bytes_match_the_validator_feed_key():
    """The validator signs DOMAIN + canonical JSON (score_feed.FeedKey.sign)."""
    document = fixtures.sign(_fixture())
    body = {k: v for k, v in document.items() if k != "signature"}
    expected = (
        b"carbon.validator.score-feed.v1\x00"
        + json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )
    assert feed.canonical_bytes(document) == expected


def test_production_feed_signed_by_a_pinned_key_is_accepted():
    document, trust = _production(fixtures.sign(_fixture()))
    board = feed.project(document, trust)
    assert board["fixture"] is False and "FIXTURE" not in board["labels"]


def test_unknown_schema_is_refused():
    _refused(
        fixtures.sign({**_fixture(), "schema": "carbon.validator.score-feed.v2"}),
        "schema_unsupported",
    )


def test_missing_signature_is_refused():
    _refused(_fixture(), "signature_missing")


def test_document_altered_after_signing_is_refused():
    document = fixtures.sign(_fixture())
    document["leaderboard"]["standing"][0]["rank"] = 2
    _refused(document, "signature_invalid")


def test_key_named_in_the_document_is_not_trusted():
    """A feed signed by its own in-document key, not a pinned one, is refused."""
    stranger = Ed25519PrivateKey.generate()
    body = {**_fixture(), "validator": {"hotkey": "x", "feed_key": _public(stranger)}}
    _refused(fixtures.sign(body, stranger), "signature_invalid")


def test_fixture_key_is_never_a_production_key():
    with pytest.raises(ValueError):
        feed.Trust(keys=frozenset({feed.FIXTURE_PUBLIC_KEY}))
    with pytest.raises(ValueError):
        feed.Trust(
            keys=frozenset({_public(Ed25519PrivateKey.generate())}), fixture=True
        )


def test_fixture_labelled_feed_is_refused_by_a_production_trust():
    document, trust = _production(fixtures.sign(_fixture()))
    document = {**document, "labels": [*document["labels"], "FIXTURE"]}
    key = Ed25519PrivateKey.generate()
    trust = feed.Trust(keys=frozenset({_public(key)}))
    _refused(fixtures.sign(document, key), "labels_invalid", trust)


def test_fixture_hotkeys_are_refused_in_production():
    key = Ed25519PrivateKey.generate()
    body = {**_fixture(), "labels": ["DEVELOPMENT", "TESTNET"]}
    trust = feed.Trust(keys=frozenset({_public(key)}))
    _refused(fixtures.sign(body, key), "hotkey_invalid", trust)


@pytest.mark.parametrize("where", ["top", "values"])
def test_live_values_are_refused(where):
    body = _fixture()
    if where == "top":
        body["live"] = {"submissions": []}
    else:
        body["values"]["live"] = {"precision": 0.001}
    _refused(fixtures.sign(body), "live_not_authorized")


def test_labels_without_development_are_refused():
    _refused(
        fixtures.sign({**_fixture(), "labels": ["TESTNET", "FIXTURE"]}),
        "labels_invalid",
    )


def test_unregistered_values_are_refused():
    body = _fixture()
    body["values"]["released"] = {"display_threshold": None}
    _refused(fixtures.sign(body), "feed_values_unregistered")
    body["values"]["released"] = {"precision": 0.003, "display_threshold": None}
    _refused(fixtures.sign(body), "feed_values_unregistered")


@pytest.mark.parametrize(
    "path",
    [
        ("submissions", 0, "sections", "accuracy"),
        ("leaderboard", "standing", 0, "best", "accuracy"),
        ("leaderboard", "incumbent", "sections", "near_limit"),
    ],
)
def test_unrounded_values_are_refused(path):
    body = _fixture()
    target = body
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = 0.41612
    _refused(fixtures.sign(body), "unrounded_value")


def test_a_submission_on_an_unreleased_window_is_refused():
    body = _fixture()
    body["submissions"][0]["windows"] = ["sha256:" + "0" * 64]
    _refused(fixtures.sign(body), "unreleased_window")


def test_case_detail_for_an_unreleased_window_is_refused():
    body = _fixture()
    row = next(s for s in body["submissions"] if "detail" not in s)
    row["detail"] = {"sha256:" + "1" * 64: {"cases": [{"case_id": "c", "error": 0.1}]}}
    _refused(fixtures.sign(body), "detail_not_released")


def test_mixed_device_classes_are_refused():
    body = _fixture()
    del body["device_class"]
    body["submissions"][0]["device_class"] = "cpu"
    _refused(fixtures.sign(body), "device_class_mixed")


def test_device_class_comes_from_submissions_when_the_feed_has_none():
    body = _fixture()
    del body["device_class"]
    board = feed.project(fixtures.sign(body), fixtures.fixture_trust())
    assert board["device_class"] == "gpu:FIXTURE-GPU"


def test_unknown_fields_are_dropped_not_shown():
    body = _fixture()
    body["operator_note"] = "private"
    body["submissions"][0]["endpoint"] = "203.0.113.7:8091"
    body["submissions"][0]["sections"]["raw_accuracy"] = 0.416123
    case_row = next(s for s in body["submissions"] if "detail" in s)
    first = next(iter(case_row["detail"].values()))["cases"][0]
    first["seed"] = 1234
    board = feed.project(fixtures.sign(body), fixtures.fixture_trust())
    text = json.dumps(board)
    for leaked in (
        "operator_note",
        "203.0.113.7",
        "raw_accuracy",
        "0.416123",
        '"seed"',
    ):
        assert leaked not in text


def test_markup_in_text_is_refused():
    body = _fixture()
    body["submissions"][0]["submission_id"] = "<img src=x>"
    _refused(fixtures.sign(body), "submissions_invalid")


def _site(tmp_path, documents):
    return build.build(tmp_path / "site", documents, fixtures.fixture_trust())


def test_build_writes_boards_and_index(tmp_path):
    index = _site(tmp_path, fixtures.documents())
    assert index["fixture"] is True
    assert [b["state"] for b in index["boards"]] == ["ACCEPTED"] * 3
    for entry in index["boards"]:
        assert (
            tmp_path / "site" / "data" / "boards" / f"{entry['slug']}.json"
        ).is_file()
    assert (tmp_path / "site" / "index.html").is_file()


def test_a_refused_feed_keeps_the_last_accepted_board(tmp_path):
    good = fixtures.sign(_fixture())
    _site(tmp_path, [good])
    bad = copy.deepcopy(good)
    bad["leaderboard"]["standing"][0]["rank"] = 9  # signature no longer holds
    index = _site(tmp_path, [bad])
    (entry,) = index["boards"]
    assert entry["state"] == "REFUSED" and entry["code"] == "signature_invalid"
    stored = json.loads(
        (tmp_path / "site" / "data" / "boards" / f"{entry['slug']}.json").read_text()
    )
    assert stored["version"] == good["version"]
    assert stored["standing"][0]["rank"] == 1


def test_a_refused_feed_with_no_previous_board_draws_nothing(tmp_path):
    index = _site(tmp_path, [_fixture()])
    (entry,) = index["boards"]
    assert entry == {"slug": None, "state": "REFUSED", "code": "signature_missing"}
    assert not (tmp_path / "site" / "data" / "boards").exists()


def test_brand_assets_match_the_website_baseline_manifest():
    manifest = json.loads(
        (ROOT / "website/ask-carbon/production-baseline.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    pinned = {}

    def walk(value):
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and "sha256" in value:
                pinned[value["path"]] = value["sha256"]
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(manifest)
    for relative, (published, digest) in build.BRAND_ASSETS.items():
        assert pinned["assets/" + Path(published).name] == digest
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest


CLAIM_WORDS = re.compile(
    r"\b(qualified|validated|certified|production[- ]ready|matches reality|accurate)\b",
    re.IGNORECASE,
)


def test_page_text_makes_no_qualification_claims():
    for path in sorted((PACKAGE / "web").glob("*")):
        text = path.read_text(encoding="utf-8")
        text = text.replace("carry no qualification", "")
        assert not CLAIM_WORDS.search(text), path.name


def test_page_loads_nothing_from_the_internet():
    for path in sorted((PACKAGE / "web").glob("*")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"https?://(?!www\.w3\.org/2000/svg)", text), path.name


def test_dashboard_imports_no_validator_state_or_private_material():
    """The feed reader imports nothing outside carbon.dashboard. The showcase
    adds only the public decision contract and the design_search optimizer;
    neither reads validator state, bank draws, seeds or private material."""
    showcase_allowed = {
        "carbon.battery.value",
        "carbon.design_search",
    }
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [
                    (
                        node.module + "." + alias.name
                        if node.module in showcase_allowed
                        else node.module
                    )
                    for alias in node.names
                ]
            for name in names:
                if not name.startswith("carbon") or name.startswith("carbon.dashboard"):
                    continue
                assert path.name == "showcase.py", (path.name, name)
                assert name in {
                    "carbon.battery.value.contract",
                    "carbon.battery.value.decision",
                    "carbon.design_search.controls",
                    "carbon.design_search.tasks",
                }, name


def test_view_models_in_node(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed here")
    _site(tmp_path, fixtures.documents())
    boards = sorted((tmp_path / "site" / "data" / "boards").glob("*.json"))
    result = subprocess.run(
        [node, str(CHECK), *map(str, boards)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["boards"] == len(boards)


def test_section_meta_comes_from_the_feed_sections():
    board = feed.project(fixtures.sign(_fixture()), fixtures.fixture_trust())
    assert board["section_meta"]["accuracy"]["sense"] == "lower_is_better"
    assert board["section_meta"]["design_q"]["sense"] == "higher_is_better"
    assert board["section_meta"]["gates"]["sense"] is None


@pytest.mark.parametrize(
    ("section", "sense"),
    [("accuracy", None), ("accuracy", "up"), ("gates", "lower_is_better")],
)
def test_section_meta_with_a_bad_sense_is_refused(section, sense):
    body = _fixture()
    body["sections"] = copy.deepcopy(body["sections"])
    body["sections"][section]["sense"] = sense
    _refused(fixtures.sign(body), "section_meta_invalid")
