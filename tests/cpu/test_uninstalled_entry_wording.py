"""The refusal of an uninstalled catalog entry states the measured install time, not the old 15 minutes."""

import pytest

from carbon.development_session import research_campaign


class _Practice:
    construction_mode = "direct"

    @staticmethod
    def backend_refusal(_strategy):
        return ["v2.motor.prior_krr"]


class _Executor:
    practice = _Practice()


class _Composition:
    executor = _Executor()


class _Prepared:
    composition = _Composition()


def test_uninstalled_entry_refusal_gives_the_measured_install_time():
    strategy = {"challenge": {"id": "electric-motor-magnetics", "version": "1.5"}}
    with pytest.raises(research_campaign.PracticeNotRun) as refused:
        research_campaign._refuse_uninstalled_entry(_Prepared(), strategy)
    text = str(refused.value) + " " + str(getattr(refused.value, "next_step", ""))
    assert "catalog_entry_not_installed" in text or "not installed" in text
    assert "about 20 to 40 minutes on 8 or more CPUs, about 2 hours on 4" in text
    assert "15 minutes" not in text
