"""Packaged App resource identity; no browser, SDK or worker runtime required."""

import base64
import hashlib
import json
import re
from pathlib import Path

from carbon.miner_mcp.mcp_apps import packaged_app


def test_fixed_app_matches_exact_build_and_workbench_sources():
    root = Path(__file__).resolve().parents[2]
    asset = root / "carbon/miner_mcp/apps_ui"
    manifest = json.loads((asset / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["sources"].items():
        source = (root / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        assert hashlib.sha256(source.encode()).hexdigest() == digest, name
    html = packaged_app()
    assert "connect-src 'none'" in html
    assert "frame-src 'none'" in html
    assert "form-action 'none'" in html
    assert "NOT_QUALIFIED" in html
    assert 'src="http' not in html
    assert "onsubmit=" not in html
    assert manifest["sdk"] == "@modelcontextprotocol/ext-apps@2.0.0"
    licenses = (
        (asset / "THIRD_PARTY_LICENSES.txt")
        .read_text(encoding="utf-8")
        .replace("\r\n", "\n")
    )
    assert (
        hashlib.sha256(licenses.encode()).hexdigest() == manifest["licenses"]["sha256"]
    )
    for package in (
        "@modelcontextprotocol/ext-apps@2.0.0",
        "@modelcontextprotocol/client@2.0.0",
        "zod@4.6.5",
    ):
        assert package in licenses
    attributes = (root / ".gitattributes").read_text(encoding="utf-8")
    assert "carbon/miner_mcp/apps_ui/workbench.html text eol=lf" in attributes
    for tag, content in re.findall(
        r"<(script|style)(?: [^>]*)?>(.*?)</\1>", html, re.DOTALL
    ):
        digest = base64.b64encode(hashlib.sha256(content.encode()).digest()).decode()
        assert "'sha256-" + digest + "'" in html, tag
