"""The pool-graded published block (Validator spec
POOL_GRADER_AND_PROOF_SUITE_SPEC_20261024): it is data-only, Challenge-neutral,
carries only what the spec fixes (every owner constant is "not yet
registered"), reveals nothing the exam-safety ruling withholds, and leaves every
version served today unchanged."""

import json
from pathlib import Path

import pytest

from carbon.challenge_registry import published_exam as pe

#: Same words the publish ruling withholds (test_published_exam.WITHHELD), plus
#: the pool grader's own private material.
WITHHELD = (
    "seeds",
    "seed_root",
    "derived seed",
    "draw_id",
    "hidden_case",
    "private_metadata",
    "fingerprint",
    "pack_set",
    "manifest",
    "custody",
    "lattice",
    "mesh",
    "refit",
    "yield",
    "start point",
    "starting point",
)
ROOT = Path(__file__).resolve().parents[2]
SERVED = pe.served()
SOME = ("f08-ribbed-bracket", "1.5")
NEW = ("f08-ribbed-bracket", "9.9")  # synthetic: a version the registry does not serve


def _walk(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)
    elif isinstance(value, str):
        yield value


def _numbers(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _numbers(v)
    elif isinstance(value, list):
        for v in value:
            yield from _numbers(v)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield value


@pytest.fixture
def pool_version(monkeypatch):
    """Register a synthetic version as pool-graded, using a served version's facts."""
    own = dict(pe._BY_VERSION[SOME])
    own["score"] = pe.pool_score("accuracy of the model's outputs on the exam's cases")
    monkeypatch.setitem(pe._BY_VERSION, NEW, own)
    monkeypatch.setattr(pe, "_POOL_VERSIONS", frozenset({NEW}))
    return pe.for_version(*NEW)


def test_no_version_served_today_is_pool_graded():
    assert pe._POOL_VERSIONS == frozenset()
    for key in SERVED:
        block = pe.for_version(*key)
        assert block["schema"] == pe.SCHEMA
        assert "design_search" not in block
        assert block["practice_vs_exam"] == pe._PRACTICE


def test_a_pool_version_serves_the_v2_schema_and_the_design_search(pool_version):
    assert pool_version["schema"] == pe.SCHEMA_POOL
    assert pool_version["design_search"] is pe._DESIGN_SEARCH
    assert pool_version["practice_vs_exam"] == pe._PRACTICE_POOL


def test_every_pool_section_is_on_the_allow_list(pool_version):
    assert set(pool_version) <= pe.ALLOWED_FIELDS


def test_the_pool_block_reveals_nothing_the_ruling_withholds(pool_version):
    words = " ".join(_walk(pool_version)).lower()
    for word in WITHHELD:
        assert word not in words, word


def test_the_pool_block_survives_json_and_is_small(pool_version):
    assert len(json.dumps(pool_version, sort_keys=True)) < 16000


def test_owner_constants_are_not_yet_registered_and_the_registered_ones_are_exact(
    pool_version,
):
    search = pool_version["design_search"]
    assert search["search"]["query_budget"] == pe.NOT_REGISTERED
    assert search["per_target_score"]["honesty_scale"] == pe.NOT_REGISTERED
    assert search["targets_and_pools"] == (
        "6 targets per set, 2 sets; 100 solved designs per target"
    )
    rule = pool_version["score"]["rule"]
    assert pe.NOT_REGISTERED in rule["A"]
    assert rule["D"] == (
        "D = min(mean of the per-target scores of a set, C); see design_search"
    )
    assert pe.NOT_REGISTERED not in rule["D"]


def test_the_design_search_publishes_no_number_the_spec_does_not_fix(pool_version):
    # The only number is the infeasible target's 0; budgets, scales and counts
    # are owner-set (or withheld) and appear as the words "not yet registered".
    assert list(_numbers(pool_version["design_search"])) == [0]


def test_the_pool_score_keeps_the_formula_and_drops_the_old_design_legs():
    score = pe.pool_score("accuracy")
    assert score["formula"] == "TOTAL = 0.5 * A + 0.5 * D"
    assert score["weights"] == {"A": 0.5, "D": 0.5}
    ids = [leg["id"] for leg in score["legs"]]
    assert ids == [
        "A_acc",
        "A_robust",
        "A_law",
        "A_response",
        "A_gen",
        "D_opt",
        "C",
    ]
    assert not {"V_pair", "V_feas", "V_var"} & set(ids)


def test_the_practice_text_says_practice_never_touches_the_exam_s_hidden_questions():
    assert "public bank" in pe._PRACTICE_POOL
    assert "never touches the exam's hidden targets" in pe._PRACTICE_POOL
    assert "not an exam total" in pe._PRACTICE_POOL


def test_the_grader_is_not_imported_by_the_published_data_module():
    # Data only: the miner door carries no exam code.
    source = Path(pe.__file__).read_text(encoding="utf-8")
    assert "import carbon.scoring" not in source
    assert "from carbon.scoring" not in source


# --- "How you're tested" (owner, 2026-10-25) ---------------------------------

MINING = ROOT / "docs" / "MINING.md"
HIDDEN_IN_HOW = (
    "seed",
    "start point",
    "starting point",
    "pool",
    "cma-es seed",
    "extended region",
    "25 %",
)


def _how_section():
    text = MINING.read_text(encoding="utf-8")
    start = text.index("## How you're tested")
    return text[start : text.index("\n## ", start + 5)]


def test_a_pool_version_serves_the_how_you_are_tested_lines(pool_version):
    lines = pool_version["how_you_are_tested"]
    assert [line["id"] for line in lines] == [
        "score",
        "inverse_design",
        "optimizer",
        "variants",
        "out_of_range",
        "gates",
        "speed",
        "minimums",
        "practice",
    ]
    assert all(set(line) == {"id", "title", "text"} for line in lines)


def test_no_version_served_today_carries_them():
    for key in SERVED:
        assert "how_you_are_tested" not in pe.for_version(*key)


def test_nothing_hidden_is_on_the_how_you_are_tested_lines():
    for challenge_id in pe._SPEED_CEILING_SECONDS:
        text = " ".join(
            line["title"] + " " + line["text"]
            for line in pe.how_you_are_tested(challenge_id)
        ).lower()
        for word in HIDDEN_IN_HOW:
            assert word not in text, (challenge_id, word)


def test_mining_md_says_exactly_what_the_block_says():
    section = _how_section()
    for _id, _title, text in pe.HOW_TESTED_LINES:
        assert text in section, _id
    for challenge_id, ceiling in pe._SPEED_CEILING_SECONDS.items():
        assert f"{ceiling} s" in section, challenge_id
        speed = next(
            line
            for line in pe.how_you_are_tested(challenge_id)
            if line["id"] == "speed"
        )
        assert speed["text"].startswith(pe.SPEED_LINE)
        assert f"{ceiling} s per design" in speed["text"]


def test_the_ceilings_are_the_solver_time_over_500():
    solver_seconds = {
        "f02": 190,
        "f08-ribbed-bracket": 1040,
        "chip-cold-plate": 1420,
        "electric-motor-magnetics": 1650,
    }
    for challenge_id, seconds in solver_seconds.items():
        assert pe._SPEED_CEILING_SECONDS[challenge_id] == round(seconds / 500, 2)


def test_the_launchpad_page_shows_the_lines_from_the_challenge_s_own_block():
    source = (ROOT / "scripts" / "dev" / "miner_launchpad" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "published_exam?.how_you_are_tested" in source
    assert "How you're tested" in source
