"""Private S3 test-only status provider; never imported by runtime code."""

import pytest

from carbon.development_ladder import required_checks as checks
from carbon.development_session import construction_level as cl
from carbon.development_session.unified_construction import UnifiedContract
from carbon.reconstruction import development_level_cli as cli
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE as BATTERY


def fixture_source(status="PASS"):
    document = checks._expected(BATTERY).document
    for row in document["types"]:
        for check in row["checks"]:
            check["status"] = status
    return UnifiedContract(document)


@pytest.fixture
def accepted_fixture_checks(monkeypatch):
    # Private in-process provider substitution only. Real child/default source
    # remains UNAVAILABLE; this exercises mechanics after an explicit fixture.
    monkeypatch.setattr(checks, "_source", lambda challenge: fixture_source())

    def run(request):
        result = cli.answer(request)
        if not result.get("ok"):
            raise cl.LevelRefused(result["code"], result.get("issues", ()))
        return result

    monkeypatch.setattr(cl, "RUN", run)
