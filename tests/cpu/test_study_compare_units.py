"""The driver check the acceptance calls hard, enforced across pods.

Stage A refused differing drivers across devices in one chassis. Nothing compared
drivers across pods, and stage B's two hosts differed (`580.159.03` against
`580.159.04`) without anything stopping the comparison. The specimen here is that
real pair, transcribed from the published stage B result: every refusal below is
shown refusing it, and every acceptance is shown on the same data, so a green
result cannot come from a check that is incapable of firing.
"""

import json
from pathlib import Path

import pytest

from scripts.dev.gpu_determinism_study import compare_units
from scripts.dev.gpu_determinism_study.compare_units import (
    DriverDeviation,
    RecordError,
    UnitSession,
    compare,
    preflight,
)

REPO = Path(__file__).resolve().parents[2]
DEVIATION_FILE = REPO / "docs/development/GPU_DETERMINISM_STAGE_B_DRIVER_DEVIATION.json"

# From docs/development/GPU_DETERMINISM_STAGE_B_RESULT.md.
HOST_1 = ("GPU-6fb9f860-a693-1f05-8510-09300c93d617", "580.159.03")
HOST_2 = ("GPU-b55ef9f3-5fd2-d26b-3a56-95b9b65260d7", "580.159.04")
DIGEST = "83e523384fd44db6207583cede3294bd3f2f8b690802b11f661ade1eb825f10a"
PINNED = (
    "--xla_gpu_deterministic_ops=true --xla_gpu_exclude_nondeterministic_ops=true "
    "--xla_gpu_autotune_level=0"
)


def record(
    label: str,
    unit: tuple[str, str | None],
    digest: str = DIGEST,
    *,
    pinned: bool = True,
) -> dict:
    uuid, driver = unit
    return {
        "label": label,
        "numerics": {"xla_flags": PINNED if pinned else None},
        "device_identity": {
            "index": 0,
            "uuid": uuid,
            "name": "NVIDIA A40",
            "driver_version": driver,
        },
        "runs": [
            {"index": i, "status": "COMPLETE", "weights_sha256": digest}
            for i in range(3)
        ],
        "successful_runs": 3,
        "distinct_weight_digests": 1,
        "bit_identical": True,
    }


def stage_b() -> list[UnitSession]:
    return [
        UnitSession.read(record(f"b-h{h}-s{s}", unit))
        for h, unit in ((1, HOST_1), (2, HOST_2))
        for s in range(3)
    ]


def published_deviation() -> DriverDeviation:
    return DriverDeviation.read(json.loads(DEVIATION_FILE.read_text()))


def test_the_published_stage_b_pair_is_refused_without_a_deviation() -> None:
    result = compare(stage_b())
    assert result["outcome"] == "REFUSED_DRIVER_MISMATCH"
    assert result["driver_builds"] == ["580.159.03", "580.159.04"]
    # Refused, not disagreed: no digest verdict is reported at all.
    assert "weight_digests" not in result


def test_the_published_deviation_admits_stage_b_and_is_carried_into_the_result() -> (
    None
):
    result = compare(stage_b(), published_deviation())
    assert result["outcome"] == "AGREE"
    assert result["weight_digests"] == [DIGEST]
    assert result["pinned"] is True
    assert result["deviation"]["builds"] == ["580.159.03", "580.159.04"]
    assert "Amendment 9" in result["deviation"]["recorded_in"]


def test_a_deviation_excuses_only_the_builds_it_names() -> None:
    other = (HOST_2[0], "580.126.09")
    sessions = [
        UnitSession.read(record("h1", HOST_1)),
        UnitSession.read(record("h2", other)),
    ]
    result = compare(sessions, published_deviation())
    assert result["outcome"] == "REFUSED_DRIVER_MISMATCH"
    assert "580.126.09" in result["reason"]


def test_matched_builds_compare_without_a_deviation() -> None:
    matched = (HOST_2[0], HOST_1[1])
    sessions = [
        UnitSession.read(record("h1", HOST_1)),
        UnitSession.read(record("h2", matched)),
    ]
    result = compare(sessions)
    assert result["outcome"] == "AGREE"
    assert result["deviation"] is None


def test_a_deviation_given_to_a_matched_comparison_is_refused() -> None:
    matched = (HOST_2[0], HOST_1[1])
    sessions = [
        UnitSession.read(record("h1", HOST_1)),
        UnitSession.read(record("h2", matched)),
    ]
    assert (
        compare(sessions, published_deviation())["outcome"]
        == "REFUSED_UNUSED_DEVIATION"
    )


def test_the_comparator_can_disagree() -> None:
    """Positive control: AGREE above is not the only verdict it can reach."""
    matched = (HOST_2[0], HOST_1[1])
    sessions = [
        UnitSession.read(record("h1", HOST_1)),
        UnitSession.read(record("h2", matched, "f" * 64)),
    ]
    result = compare(sessions)
    assert result["outcome"] == "DISAGREE"
    assert len(result["weight_digests"]) == 2


def test_pinned_and_unpinned_sessions_are_not_compared_together() -> None:
    matched = (HOST_2[0], HOST_1[1])
    sessions = [
        UnitSession.read(record("h1", HOST_1)),
        UnitSession.read(record("h2", matched, pinned=False)),
    ]
    assert compare(sessions)["outcome"] == "REFUSED_MIXED_CONDITION"


def test_one_unit_is_not_a_comparison() -> None:
    sessions = [UnitSession.read(record(f"s{s}", HOST_1)) for s in range(3)]
    assert compare(sessions)["outcome"] == "REFUSED_ONE_UNIT"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r.pop("device_identity"), "no device_identity"),
        (
            lambda r: r["device_identity"].update(driver_version=None),
            "driver build was not recorded",
        ),
        (lambda r: r["device_identity"].update(uuid=None), "absent is not a name"),
        (lambda r: r.update(bit_identical=False), "no single digest"),
        (lambda r: r.update(status="REFUSED_UNPINNED"), "refused to run"),
    ],
)
def test_a_record_that_cannot_show_its_driver_or_digest_is_refused(
    mutate, message
) -> None:
    specimen = record("h1", HOST_1)
    UnitSession.read(specimen)  # the unmutated record is accepted
    mutate(specimen)
    with pytest.raises(RecordError, match=message):
        UnitSession.read(specimen)


def test_a_session_cannot_be_built_around_the_reader() -> None:
    """A perfectly valid session, built directly, is still refused."""
    with pytest.raises(TypeError, match="UnitSession.read"):
        UnitSession("h1", HOST_1[0], HOST_1[1], DIGEST, True)
    with pytest.raises(TypeError, match="DriverDeviation.read"):
        DriverDeviation(frozenset({"a", "b"}), "here", "because")


def test_a_deviation_must_name_two_builds_and_its_reason() -> None:
    document = json.loads(DEVIATION_FILE.read_text())
    DriverDeviation.read(document)
    with pytest.raises(RecordError, match="two distinct builds"):
        DriverDeviation.read({**document, "builds": ["580.159.03"]})
    with pytest.raises(RecordError, match="reason"):
        DriverDeviation.read({**document, "reason": " "})


def identity(unit: tuple[str, str | None]) -> dict:
    return {
        "index": 0,
        "uuid": unit[0],
        "name": "NVIDIA A40",
        "driver_version": unit[1],
    }


def test_preflight_would_have_stopped_stage_b_before_any_device_time() -> None:
    problems = preflight([identity(HOST_1), identity(HOST_2)])
    assert any("driver builds differ" in p for p in problems)
    assert preflight([identity(HOST_1), identity((HOST_2[0], HOST_1[1]))]) == []


def test_preflight_refuses_an_unreadable_build() -> None:
    problems = preflight([identity(HOST_1), identity((HOST_2[0], None))])
    assert any("no readable driver build" in p for p in problems)


def test_command_line_refuses_and_admits(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    paths = []
    for h, unit in ((1, HOST_1), (2, HOST_2)):
        path = tmp_path / f"h{h}.json"
        path.write_text(json.dumps(record(f"h{h}", unit)))
        paths.append(str(path))
    assert compare_units.main(["compare_units.py", *paths]) == 2
    assert '"REFUSED_DRIVER_MISMATCH"' in capsys.readouterr().out
    assert (
        compare_units.main(
            ["compare_units.py", *paths, "--deviation", str(DEVIATION_FILE)]
        )
        == 0
    )
    assert '"AGREE"' in capsys.readouterr().out
