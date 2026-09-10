from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_c01_queue_has_no_chain_scoring_or_publication_dependency() -> None:
    text = (ROOT / "carbon/execution/store.py").read_text()
    forbidden = (
        "carbon.chain",
        "carbon.scoring",
        "carbon.rewards",
        "carbon.leaderboard",
        "CardStore",
        "set_weights",
        "eligible_for_emission",
    )
    assert all(value not in text for value in forbidden)


def test_c01_result_is_explicitly_not_archive_acknowledged() -> None:
    text = (ROOT / "carbon/execution/model.py").read_text()
    assert "C_EA2_ACKNOWLEDGEMENT_REQUIRED" in text
    assert "archive_acknowledgement_ref: None" in text
    assert "archive_acknowledged is not False" in text
