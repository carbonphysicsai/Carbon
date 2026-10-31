"""Every miner HTTP call to a door names itself; none goes out with urllib's default agent.

Cloudflare refuses Python's default urllib agent with 403 (as `carbon/dashboard/__main__.py` FETCH_HEADERS says), so a
miner reading `/info` or posting a signed request through `https://<name>-door.carbonphysics.ai` must send the one agent
string in `carbon.miner_agent`. No network is contacted: `urllib.request.urlopen` is replaced and records what it was
given (a bare URL string would go out with the default agent).
"""

import json

import pytest

from carbon import __version__
from carbon.battery import dev_submit, intake_client
from carbon.development_session import direct_submission
from carbon.miner_agent import MINER_HEADERS, MINER_USER_AGENT
from scripts.dev.miner_launchpad import king

DOOR = "https://motor-door.carbonphysics.ai"


class Answer:
    status = 200

    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def read(self, *_):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture
def sent(monkeypatch):
    seen = []

    def fake(target, *args, **kwargs):
        seen.append(target)
        return Answer(
            {
                "schema": direct_submission.PUBLIC_SCHEMA,
                "ok": True,
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake)
    return seen


def agent_of(target):
    assert not isinstance(
        target, str
    ), "a bare URL goes out with urllib's default agent"
    return target.get_header("User-agent")


def test_the_agent_names_the_miner_and_the_version():
    assert MINER_USER_AGENT.startswith(f"carbon-miner/{__version__} ")
    assert "Python-urllib" not in MINER_USER_AGENT
    assert MINER_HEADERS == {"User-Agent": MINER_USER_AGENT}


def test_direct_read_intake_sends_the_agent(sent):
    direct_submission.read_intake(DOOR)
    assert agent_of(sent[0]) == MINER_USER_AGENT


def test_direct_post_sends_the_agent(sent):
    direct_submission.post(DOOR, b"{}", {"X-Signed": "1"})
    assert agent_of(sent[0]) == MINER_USER_AGENT
    assert sent[0].get_header("X-signed") == "1"
    assert sent[0].get_header("Content-type") == "application/json"


def test_battery_intake_client_sends_the_agent(monkeypatch):
    seen = []

    def fake(target, *args, **kwargs):
        seen.append(target)
        return Answer({"schema": intake_client.PUBLIC_SCHEMA})

    monkeypatch.setattr("urllib.request.urlopen", fake)
    intake_client.read_intake(DOOR)
    intake_client.post(DOOR, b"{}", {})
    assert [agent_of(target) for target in seen] == [MINER_USER_AGENT] * 2


def test_battery_dev_submit_sends_the_agent(sent):
    dev_submit._post(DOOR, b"{}")
    assert agent_of(sent[0]) == MINER_USER_AGENT


def test_king_read_default_sends_the_agent(sent):
    king.read(DOOR, "electric-motor-magnetics")
    assert agent_of(sent[0]) == MINER_USER_AGENT
