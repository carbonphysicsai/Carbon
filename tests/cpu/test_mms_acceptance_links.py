"""Document identity tests only; no solver, protected material or qualification."""

import copy
import json

import pytest

from carbon.trust_map.acceptance import (
    DIRECTORY,
    LINKS,
    ROOT,
    AcceptanceRefused,
    byte_digest,
    digest,
    load_acceptance,
    validate_acceptance,
)


def registered(family):
    link = json.loads((ROOT / DIRECTORY / LINKS[family]).read_bytes())
    paths = [
        link["decision"]["path"],
        link["criteria_path"],
        *[item["path"] for item in link["evidence"]],
    ]
    return link, {path: (ROOT / path).read_bytes() for path in paths}


@pytest.mark.parametrize("family", LINKS)
def test_all_three_links_bind_existing_owner_decision_and_exact_criteria(family):
    link, files = registered(family)
    result = load_acceptance(family, link["image_digest"], link["criteria_digest"])
    assert result["decision"]["decision_id"] == link["decision"]["id"]
    assert result["decision"]["sha256"] == link["decision"]["sha256"]
    assert result["scope"] == "DEVELOPMENT_CODE_VERIFICATION"
    assert result["criteria_digest"] == digest(json.loads(files[link["criteria_path"]]))
    assert result["conditions"] == ({"t_end": 0.375} if family == "f02" else {})
    if family == "battery-v3":
        verdict = json.loads(files[link["evidence"][0]["path"]])
        assert verdict["state"] == "HUMAN_INPUT"
        assert verdict["accepted_development_pass"] is False


@pytest.mark.parametrize("field", ["image_digest", "criteria_digest"])
def test_repin_or_different_criteria_needs_new_acceptance(field):
    link, _ = registered("battery-v3")
    arguments = {key: link[key] for key in ("image_digest", "criteria_digest")}
    arguments[field] = "sha256:" + "a" * 64
    with pytest.raises(AcceptanceRefused, match="mismatch"):
        load_acceptance("battery-v3", **arguments)


def test_missing_link_is_unavailable(tmp_path):
    link, _ = registered("battery-v3")
    with pytest.raises(AcceptanceRefused, match="unavailable"):
        load_acceptance(
            "battery-v3", link["image_digest"], link["criteria_digest"], root=tmp_path
        )


@pytest.mark.parametrize("part", ["image", "criteria", "format"])
def test_relinking_a_record_cannot_reinterpret_older_mms_headers(part):
    link, files = registered("battery-v3")
    if part == "image":
        link["image_digest"] = "sha256:" + "a" * 64
    elif part == "criteria":
        criteria = json.loads(files[link["criteria_path"]])
        criteria["t"] = 0.5
        files[link["criteria_path"]] = json.dumps(criteria).encode()
        link["criteria_digest"] = digest(criteria)
    else:
        path = link["evidence"][0]["path"]
        result = json.loads(files[path])
        result["schema"] = "carbon.code-verification.fields.v1"
        files[path] = json.dumps(result).encode()
        link["evidence"][0]["sha256"] = byte_digest(files[path])
    with pytest.raises(
        AcceptanceRefused, match="evidence_(.*mismatch|result_required)"
    ):
        validate_acceptance(
            link,
            family="battery-v3",
            image_digest=link["image_digest"],
            criteria_digest=link["criteria_digest"],
            files=files,
        )


def test_link_symlink_is_refused_before_any_unregistered_file_read(tmp_path):
    link, _ = registered("battery-v3")
    directory = tmp_path / DIRECTORY
    directory.mkdir(parents=True)
    # Dangling synthetic target: refusal must precede opening even the link.
    (directory / LINKS["battery-v3"]).symlink_to(tmp_path / "unregistered.json")
    with pytest.raises(AcceptanceRefused, match="regular_file_required"):
        load_acceptance(
            "battery-v3", link["image_digest"], link["criteria_digest"], root=tmp_path
        )


@pytest.mark.parametrize("part", ["decision", "criteria", "result"])
def test_changed_evidence_or_decision_bytes_cannot_establish_acceptance(part):
    link, files = registered("battery-v3")
    path = {
        "decision": link["decision"]["path"],
        "criteria": link["criteria_path"],
        "result": link["evidence"][0]["path"],
    }[part]
    files[path] += b"\n"
    if part == "criteria":
        # Whitespace is irrelevant to the historical canonical criteria digest.
        document = json.loads(files[path])
        document["t"] = 0.5
        files[path] = json.dumps(document).encode()
    with pytest.raises(AcceptanceRefused, match="mismatch"):
        validate_acceptance(
            link,
            family="battery-v3",
            image_digest=link["image_digest"],
            criteria_digest=link["criteria_digest"],
            files=files,
        )


@pytest.mark.parametrize("mutation", ["missing", "wrong", "criteria"])
def test_elmer_end_time_condition_is_enforced(mutation):
    link, files = registered("f02")
    link = copy.deepcopy(link)
    if mutation == "missing":
        link["conditions"] = {}
    elif mutation == "wrong":
        link["conditions"]["t_end"] = 0.5
    else:
        criteria = json.loads(files[link["criteria_path"]])
        criteria["t_end"] = 0.5
        files[link["criteria_path"]] = json.dumps(criteria).encode()
        link["criteria_digest"] = digest(criteria)
    with pytest.raises(AcceptanceRefused, match="condition"):
        validate_acceptance(
            link,
            family="f02",
            image_digest=link["image_digest"],
            criteria_digest=link["criteria_digest"],
            files=files,
        )


@pytest.mark.parametrize(
    "challenge", ["battery-fastcharge-ageing-development-v1", "motor", "f02"]
)
def test_deliverable_reads_registered_links_and_retains_original_verdicts(challenge):
    from scripts.dev.customer_deliverable.generate import Source, git_blob, load_policy
    from scripts.dev.customer_deliverable.package_sections import build_package_sections

    config = load_policy()["challenges"][challenge]
    sources = {}
    for spec in config["package_sources"]:
        if spec["id"] not in {"P1", "P2", "P5", "P6", "P7"}:
            continue
        data = (ROOT / spec["path"]).read_bytes()
        sources[spec["id"]] = Source(
            spec["id"], spec["path"], "a" * 40, git_blob(data), data.decode()
        )
    package = build_package_sections(challenge, config["package_family"], sources)
    rows = {
        row["field"]: row for row in package["sections"]["solver_verification"]["rows"]
    }
    assert rows["owner_acceptance_link"]["value"] == (
        "CONDITIONAL, t_end 0.375 (MMS test-design scope)"
        if challenge == "f02"
        else "RECORDED_OWNER_DECISION"
    )
    assert package["qualification_claim"] is False
    if challenge == "battery-fastcharge-ageing-development-v1":
        assert rows["machine_verdict"]["value"] == "HUMAN_INPUT"
        assert rows["machine_acceptance"]["value"] is False
    if challenge == "f02":
        assert (
            rows["supplement.owner_acceptance_link"]["value"]
            == rows["owner_acceptance_link"]["value"]
        )
        assert rows["acceptance_conditions"]["value"] == {"t_end": 0.375}
        assert rows["time_orders.1.max"]["value"] > 2.3  # adverse t_end=0.5 retained
        assert rows["supplement.time_orders.2.max"]["value"] < 2.3
