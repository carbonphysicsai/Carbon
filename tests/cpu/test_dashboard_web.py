"""DASHBOARD-02 S2: the static web app's budget and browser policy.

The pages' rendering in each board.v2 phase is checked in Node
(`test_dashboard_feed.test_view_models_in_node`, tests/cpu/dashboard_check.cjs).
Here: the asset budget, the strict CSP, and that no page source can carry an
inline script, inline style or HTML parsing.
"""

from __future__ import annotations

import re
from pathlib import Path

from carbon.dashboard import build, fixtures

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "carbon" / "dashboard" / "web"
WORKER = ROOT / "carbon" / "dashboard" / "worker" / "index.mjs"
#: ENGINEERING BUDGET (DASHBOARD-02 plan, S2): the app without its fonts.
BUDGET_BYTES = 120 * 1024
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'none'"
)


def _web_files():
    return sorted(p for p in WEB.rglob("*") if p.is_file())


def test_assets_stay_under_the_budget():
    """Everything the page loads except the brand fonts: HTML, CSS, JS and the
    wordmark."""
    sizes = {p.name: p.stat().st_size for p in _web_files()}
    for relative, (published, _digest) in build.BRAND_ASSETS.items():
        if not published.startswith("fonts/"):
            sizes[published] = (ROOT / relative).stat().st_size
    total = sum(sizes.values())
    assert total <= BUDGET_BYTES, (total, sizes)


def test_the_web_app_is_plain_files():
    assert {p.suffix for p in _web_files()} <= {".html", ".js", ".css"}


def test_index_carries_the_strict_csp():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    metas = re.findall(
        r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', html
    )
    assert metas == [CSP]


def test_the_worker_sends_the_same_csp_and_frame_ancestors():
    worker = WORKER.read_text(encoding="utf-8")
    assert f'"Content-Security-Policy": "{CSP}; frame-ancestors \'none\'"' in worker


def test_index_has_no_inline_script_style_or_handler():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    for tag in re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.DOTALL):
        assert tag.strip() == "", "inline script"
    for attributes in re.findall(r"<script\b([^>]*)>", html):
        assert re.search(r'\bsrc="[a-z]+\.js"', attributes), attributes
    assert "<style" not in html
    assert not re.search(r"\sstyle=", html)
    assert not re.search(r"\son[a-z]+=", html)


def test_scripts_never_parse_html_or_set_inline_style():
    forbidden = re.compile(
        r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|"
        r"new Function|\.style\.|setAttribute\(\s*[\"']style|cssText"
    )
    for path in _web_files():
        if path.suffix == ".js":
            assert not forbidden.search(path.read_text(encoding="utf-8")), path.name


def test_the_page_says_eligible_never_qualified():
    text = (WEB / "dashboard.js").read_text(encoding="utf-8")
    assert '"Eligible for the championship"' in text
    for path in _web_files():
        assert "qualified" not in path.read_text(encoding="utf-8").lower(), path.name


def test_files_are_utf8_with_lf_endings():
    for path in _web_files():
        body = path.read_bytes()
        body.decode("utf-8")
        assert b"\r\n" not in body, path.name


def test_no_per_field_null_text_in_the_pages():
    """A null field is hidden: its reason stays in the board.v2 JSON. The pages
    carry one section line and one rules line instead (Test Lead review)."""
    for path in _web_files():
        text = path.read_text(encoding="utf-8").lower()
        for phrase in ("not yet published", "to be announced", "timing unavailable"):
            assert phrase not in text, (path.name, phrase)
    script = (WEB / "dashboard.js").read_text(encoding="utf-8")
    assert script.count('"More coming as the Validator publishes it"') == 1
    assert script.count('"Rules unavailable"') == 1


def test_the_index_says_whether_a_network_snapshot_exists(tmp_path):
    site = tmp_path / "site"
    assert (
        build.build(site, fixtures.documents(), fixtures.fixture_trust())["network"]
        is False
    )
    (site / "data" / "network.json").write_text("{}", encoding="utf-8")
    assert (
        build.build(site, fixtures.documents(), fixtures.fixture_trust())["network"]
        is True
    )
    # The Worker serves no snapshot yet (S3), so its index says so.
    assert "network: false" in WORKER.read_text(encoding="utf-8")
    script = (WEB / "dashboard.js").read_text(encoding="utf-8")
    assert 'index.network === true ? await optional("data/network.json")' in script
