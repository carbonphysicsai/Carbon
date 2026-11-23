"""The published Carbon submission terms v0 (owner G-LEAD-50 + addendum): one file, one pinned sha256, served as is."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from carbon.dashboard import build
from carbon.development_session import submission_terms as terms

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = "docs/terms/carbon-submission-terms-v0.md"
SHA = "946244f64b9c8580010595822ad997eb22e7184dd4074dfca808868c30232faa"


def _text():
    return (ROOT / RELATIVE).read_bytes()


def test_the_file_is_the_pinned_bytes():
    assert hashlib.sha256(_text()).hexdigest() == SHA
    assert build.TERMS[RELATIVE] == ("terms/carbon-submission-terms-v0.md", SHA)
    assert len(_text()) <= terms.MAX_TEXT_BYTES


def test_the_file_is_plain_lf_ascii_with_one_trailing_newline():
    text = _text()
    assert all(byte < 128 for byte in text)
    assert b"\r" not in text and text.endswith(b".\n") and not text.endswith(b"\n\n")


def test_it_holds_sections_1_to_8_and_no_placeholder_contact_or_drafting_note():
    text = _text().decode("ascii")
    assert text.startswith("**Carbon submission terms, version v0**\n\n")
    assert re.findall(r"^\*\*(\d+)\. ", text, re.MULTILINE) == [str(n) for n in range(1, 9)]
    for absent in ("HUMAN_INPUT", "[", "Contact", "counsel", "> "):
        assert absent not in text


def test_the_name_and_path_follow_the_versioned_terms_route():
    version = Path(RELATIVE).stem
    assert terms.VERSION.fullmatch(version)
    assert terms.PATH_PREFIX + version == "/carbon/v1/terms/carbon-submission-terms-v0"


def test_the_dashboard_build_publishes_it_byte_for_byte(tmp_path):
    build._copy_terms(tmp_path)
    assert (tmp_path / "terms" / "carbon-submission-terms-v0.md").read_bytes() == _text()


def test_the_sha_pin_survives_checkout_line_endings():
    assert "docs/terms/*.md -text" in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
