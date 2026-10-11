import copy
import hashlib
import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import packet
from carbon.challenge_pipeline.onboarding.__main__ import main

ROOT = Path(__file__).resolve().parents[2]
REAL = {
    "motor": "docs/development/challenge_pipeline/round1/motor-precision-joint-v2.md",
    "battery-v3": "docs/development/challenge_pipeline/round1/battery-ambient-map-v3.md",
}


def brief(challenge="motor"):
    return {
        "schema": packet.SCHEMA,
        "challenge": challenge,
        "buyer": "mock design engineer",
        "decision": "pick a feasible action",
        "physics": "declared physical model",
        "solver": "proposed open solver",
    }


@pytest.mark.parametrize("challenge", REAL)
def test_real_packet_regeneration_records_gaps(challenge):
    actual = (ROOT / REAL[challenge]).read_text(encoding="utf-8")
    draft = packet.generate(brief(challenge), ROOT)
    rendered = packet.render(draft)
    assert rendered.count("\n## ") == 10
    assert all(r["status"] == "HUMAN_INPUT" for r in draft["fields"].values())
    report = packet.compare(draft, actual)
    assert len(report["actual_numbered_sections"]) == 10
    assert report["source_extracted_fields"] == 0
    assert report["human_input_fields"] and report["diff"]
    assert "NOT_SEMANTIC_EQUIVALENCE" in report["comparison"]


def test_sourced_extraction_is_pinned_not_an_approval():
    path = REAL["battery-v3"]
    raw = (ROOT / path).read_bytes()
    excerpt = "I calibrate an EV fleet's charging map."
    value = brief("battery-v3")
    value["fields"] = {
        "buyer": {
            "value": excerpt,
            "sources": [
                {
                    "path": path,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "excerpt": excerpt,
                }
            ],
        }
    }
    drafted = packet.generate(value, ROOT)
    assert drafted["fields"]["buyer"]["status"] == "SOURCE_EXTRACT"
    assert "not approval" in packet.render(drafted)
    bad = copy.deepcopy(value)
    bad["fields"]["buyer"]["value"] = "invented customer"
    with pytest.raises(packet.DraftError):
        packet.generate(bad, ROOT)
    value["fields"]["buyer"]["sources"][0]["sha256"] = "0" * 64
    with pytest.raises(packet.DraftError):
        packet.generate(value, ROOT)


@pytest.mark.parametrize(
    "path",
    ["../secret", "C:/secret", ".aws/config", "docs/development/hidden/bank.json"],
)
def test_no_host_or_hidden_source(path):
    with pytest.raises(packet.DraftError):
        packet.source_path(ROOT, path)


def test_closed_bounded_schema():
    value = brief()
    value["authorize_live"] = True
    with pytest.raises(packet.DraftError):
        packet.generate(value, ROOT)
    value = brief()
    value["buyer"] = "x" * 8001
    with pytest.raises(packet.DraftError):
        packet.generate(value, ROOT)


def test_cli_no_output_mutation_or_error_echo(tmp_path, capsys):
    inp = tmp_path / "brief.json"
    inp.write_text(json.dumps(brief()), encoding="utf-8")
    assert (
        main(["--root", str(ROOT), "packet", "--brief", str(inp), "--format", "json"])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["maturity"] == "DRAFT_ONLY"
    inp.write_text('{"secret": "DO_NOT_ECHO"}', encoding="utf-8")
    assert main(["packet", "--brief", str(inp)]) == 2
    assert "DO_NOT_ECHO" not in capsys.readouterr().err
