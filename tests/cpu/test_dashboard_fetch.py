"""`python -m carbon.dashboard fetch` names itself (DASHBOARD-02).

Cloudflare in front of feeds.carbonphysics.ai answered Python's default urllib
agent with 403 on the first live deploy, so the fetch sends an explicit
`carbon-dashboard/1` User-Agent. No network: urlopen is replaced.
"""

from __future__ import annotations

import io
import json

from carbon.dashboard import __main__ as cli


class _Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_sends_a_named_user_agent(tmp_path, monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["agent"] = request.get_header("User-agent")
        seen["accept"] = request.get_header("Accept")
        seen["url"] = request.full_url
        return _Answer(json.dumps({"schema": "x"}).encode())

    monkeypatch.setattr(cli.urllib.request, "urlopen", fake_urlopen)
    out = tmp_path / "feed.json"
    url = "https://feeds.example/valv2/feed.json"
    assert cli.main(["fetch", "--url", url, "--out", str(out)]) == 0
    assert seen["url"] == url
    assert seen["agent"] == cli.FETCH_HEADERS["User-Agent"]
    assert seen["agent"].startswith("carbon-dashboard/")
    assert seen["accept"] == "application/json"
    assert json.loads(out.read_text(encoding="utf-8")) == {"schema": "x"}
