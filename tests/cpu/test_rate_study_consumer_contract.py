"""VALIDATOR-30 consumer contract (docs/development/graphite/VALIDATOR_30_CONSUMER_CONTRACT.md).

Acceptance tests for the module the rate study calls,
`carbon.challenge_validator.rate_study`. Each is `xfail` until VALIDATOR-30 lands:
`raises` is limited to the errors a missing module or surface produces, so once the
module exists a real contract violation is a real failure, not an expected one.
Fixture mode only: no bank, pool, host or spend.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
MISSING = (ImportError, AttributeError, ModuleNotFoundError)
not_built = pytest.mark.xfail(
    reason="VALIDATOR-30 (rate-study harness) is not built yet",
    raises=MISSING,
    strict=False,
)

REFUSALS = (
    "config_unreadable",
    "config_schema_mismatch",
    "rule_unknown",
    "rule_not_study_variant",
    "rule_window_blocks_mismatch",
    "library_digest_mismatch",
    "study_bank_not_sealed",
    "study_bank_wrong_size",
    "study_bank_not_sacrificial",
    "topup_not_off",
    "fresh_bank_missing",
    "fresh_bank_drawable_by_a_window",
    "clock_not_simulated",
    "production_root_refused",
    "revealed_on_non_sacrificial_bank",
    "freeze_manifest_required",
    "freeze_manifest_mismatch",
    "replicate_already_complete",
    "run_dir_not_fresh",
    "fixture_with_real_root",
)


def _analyze():
    spec = importlib.util.spec_from_file_location(
        "analyze", REPOSITORY / "scripts/dev/rate_study/analyze.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module():
    return importlib.import_module("carbon.challenge_validator.rate_study")


def _config(tmp_path, **over):
    config = {
        "schema": "carbon.rate-study.config.v1",
        "fixture": True,
        "roots": {
            name: str(tmp_path / name)
            for name in ("producer", "battery", "bank", "fresh", "runs")
        },
        "rules": {"1": "v2-bank-rate-1", "2": "v2-bank-rate-2", "4": "v2-bank-rate-4"},
        "library": {"path": "library-v2.json", "digest": None},
        "order_seed": "SUBMISSION-RATE-STUDY-01/arm-H/library-v2",
        "windows": 2,
        "clock": {"mode": "simulated", "start_block": 1_000_000},
        "hotkey": "study-hotkey-1",
        "bank": {
            "name": "study",
            "cases": 3000,
            "sacrificial": True,
            "top_up": "off",
            "tranche_roots": [],
        },
        "fresh": {"name": "fresh", "windows": 12, "cases_per_window": 98, "roots": {}},
        "records_dir": str(tmp_path / "records"),
    }
    config.update(over)
    path = tmp_path / "rate-study.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _records(tmp_path, arm="H", rate=1, replicate=1):
    path = tmp_path / "records" / arm / str(rate) / f"{replicate}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_the_refusal_list_is_closed_and_unique():
    assert len(set(REFUSALS)) == len(REFUSALS) == 20


@not_built
def test_the_module_exposes_the_contract_surface():
    module = _module()
    for name in ("main", "run", "fresh", "check"):
        assert callable(getattr(module, name))


@pytest.mark.xfail(
    reason="VALIDATOR-30 (rate-study harness) is not built yet",
    raises=MISSING + (KeyError,),
    strict=False,
)
def test_the_three_rule_variants_are_v2_bank_plus_window_blocks_and_study():
    from carbon.battery import exam

    base = exam.RULES["v2-bank"]
    digests = set()
    for rate, blocks in ((1, 360), (2, 180), (4, 90)):
        rule = exam.RULES[f"v2-bank-rate-{rate}"]
        assert rule["per_hotkey"]["window_blocks"] == blocks
        assert rule["study"] == "SUBMISSION-RATE-STUDY-01"
        rest = {k: v for k, v in rule.items() if k not in ("per_hotkey", "study")}
        assert rest == {k: v for k, v in base.items() if k != "per_hotkey"}
        digests.add(json.dumps(rule, sort_keys=True))
    assert len(digests) == 3


@not_built
def test_run_writes_records_in_exactly_the_analysis_schema(tmp_path):
    module, analyze = _module(), _analyze()
    config = _config(tmp_path)
    code = module.main(
        [
            "run",
            "--config",
            str(config),
            "--arm",
            "H",
            "--rate",
            "1",
            "--replicate",
            "1",
        ]
    )
    assert code == 0
    records = _records(tmp_path)
    assert records and all(set(r) == set(analyze.FIELDS) for r in records)
    for record in records:
        analyze.check_record(record)
        assert record["provenance"] == "FIXTURE"
    assert [r["t"] for r in records] == list(range(1, len(records) + 1))
    assert len(records) == 3 * 1 * 2  # 3m per window x 2 windows at m = 1


@not_built
def test_a_resume_appends_only_the_missing_submissions(tmp_path):
    module = _module()
    config = _config(tmp_path)
    argv = [
        "run",
        "--config",
        str(config),
        "--arm",
        "H",
        "--rate",
        "2",
        "--replicate",
        "1",
    ]
    assert module.main(argv) == 0
    first = _records(tmp_path, rate=2)
    assert module.main(argv) in (0, 2)  # complete: nothing duplicated
    assert _records(tmp_path, rate=2) == first


@not_built
def test_a_repeated_outcome_is_its_own_line_and_never_scored(tmp_path):
    # 14 windows at m = 4 is 168 submissions against library-v2's >= 144 distinct
    # recipes, so the fixture route must answer the surplus with REPEATED lines.
    module, analyze = _module(), _analyze()
    library = json.loads(
        (
            REPOSITORY
            / "docs/development/evidence/submission-rate-study-01/library-v2.json"
        ).read_text(encoding="utf-8")
    )
    distinct = (
        len(library["entries"]) if "entries" in library else len(library["recipes"])
    )
    config = _config(tmp_path, windows=14)
    module.main(
        [
            "run",
            "--config",
            str(config),
            "--arm",
            "H",
            "--rate",
            "4",
            "--replicate",
            "1",
        ]
    )
    records = _records(tmp_path, rate=4)
    repeated = [r for r in records if r["state"] == "REPEATED"]
    assert len(repeated) == max(0, 168 - distinct)
    assert all(r["d_index"] is None and r["s_fresh"] is None for r in repeated)
    assert analyze.excluded_counts(records)["REPEATED"] == len(repeated)


@not_built
@pytest.mark.parametrize(
    "over, code",
    [
        (
            {
                "bank": {
                    "name": "study",
                    "cases": 3000,
                    "sacrificial": True,
                    "top_up": "on",
                    "tranche_roots": [],
                }
            },
            "topup_not_off",
        ),
        (
            {
                "bank": {
                    "name": "study",
                    "cases": 2000,
                    "sacrificial": True,
                    "top_up": "off",
                    "tranche_roots": [],
                }
            },
            "study_bank_wrong_size",
        ),
        (
            {
                "bank": {
                    "name": "study",
                    "cases": 3000,
                    "sacrificial": False,
                    "top_up": "off",
                    "tranche_roots": [],
                }
            },
            "study_bank_not_sacrificial",
        ),
        ({"clock": {"mode": "chain", "start_block": 1}}, "clock_not_simulated"),
        (
            {"rules": {"1": "v2-bank", "2": "v2-bank-rate-2", "4": "v2-bank-rate-4"}},
            "rule_not_study_variant",
        ),
    ],
)
def test_check_refuses_with_a_typed_code(tmp_path, capsys, over, code):
    module = _module()
    config = _config(tmp_path, **over)
    assert module.main(["check", "--config", str(config)]) == 2
    assert f"refused: {code}" in capsys.readouterr().out
    assert code in REFUSALS


@not_built
def test_revealed_is_refused_on_a_non_sacrificial_bank(tmp_path, capsys):
    module = _module()
    bank = {
        "name": "study",
        "cases": 3000,
        "sacrificial": False,
        "top_up": "off",
        "tranche_roots": [],
    }
    config = _config(tmp_path, bank=bank)
    code = module.main(
        [
            "run",
            "--config",
            str(config),
            "--arm",
            "S-revealed",
            "--rate",
            "1",
            "--replicate",
            "1",
            "--prober",
            "x:y",
        ]
    )
    out = capsys.readouterr().out
    assert code == 2 and "refused:" in out
    assert not (tmp_path / "records").exists()


@not_built
def test_a_fixture_never_runs_on_a_real_root(tmp_path, capsys):
    module = _module()
    roots = {
        k: f"/var/lib/carbon-producer/rate-study/{k}"
        for k in ("producer", "battery", "bank", "fresh", "runs")
    }
    config = _config(tmp_path, roots=roots)
    assert module.main(["check", "--config", str(config)]) == 2
    assert "refused: fixture_with_real_root" in capsys.readouterr().out


@not_built
def test_the_fresh_scorer_is_non_consuming_and_prints_nothing_hidden(tmp_path, capsys):
    module = _module()
    config = _config(tmp_path)
    argv = [
        "fresh",
        "--config",
        str(config),
        "--submission",
        "s1",
        "--set",
        "fresh-w01",
    ]
    assert module.main(argv) == 0
    first = capsys.readouterr().out.strip()
    assert module.main(argv) == 0  # a repeat returns the stored result
    assert capsys.readouterr().out.strip() == first
    assert set(json.loads(first)) == {"state", "s_fresh"}
    assert (
        module.main(
            [
                "fresh",
                "--config",
                str(config),
                "--submission",
                "s2",
                "--set",
                "fresh-w01",
            ]
        )
        == 0
    )  # another model, the same set: scores normally


@not_built
def test_nothing_hidden_reaches_stdout_or_the_records(tmp_path, capsys):
    module = _module()
    config = _config(tmp_path)
    module.main(
        [
            "run",
            "--config",
            str(config),
            "--arm",
            "H",
            "--rate",
            "1",
            "--replicate",
            "1",
        ]
    )
    text = capsys.readouterr().out + (tmp_path / "records/H/1/1.jsonl").read_text(
        encoding="utf-8"
    )
    for token in ("case_id", "fingerprint", "prediction", "seed", "private_root"):
        assert token not in text
