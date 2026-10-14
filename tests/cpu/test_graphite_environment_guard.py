"""PLT-33: distinguish a small-job pass from the declared L4 size budget."""

import json

import pytest

from scripts.dev.exam_design.runpod import environment_guard as guard
from scripts.dev.exam_design.runpod import pod_control, pod_env


@pytest.mark.parametrize(
    ("offset", "status"),
    [(-1, "PASS"), (0, "FAIL"), (guard.CI_RESERVE_CHARS + 1, "FAIL")],
)
def test_ci_guard_retains_the_cap_and_strict_reserve(offset, status):
    size = pod_env.ENV_LIMIT_CHARS - guard.CI_RESERVE_CHARS + offset
    result = guard.measurement({"A": "x" * (size - 1)})
    assert result["total_chars"] == size
    assert result["status"] == status
    assert result["limit_chars"] == pod_env.ENV_LIMIT_CHARS
    assert result["reserve_chars"] == 8_000
    assert result["headroom_chars"] == pod_env.ENV_LIMIT_CHARS - size


def test_l4_payload_consumes_real_environment_budget_and_names_its_cause():
    phase_size = pod_env.ENV_LIMIT_CHARS - guard.CI_RESERVE_CHARS - 30_000
    small = {"CODE_REF": "a" * 40, "PHASE_CONFIG": "x" * phase_size}
    assert guard.measurement(small)["status"] == "PASS"
    large = {**small, "PHASE_CONFIG": small["PHASE_CONFIG"] + "x" * 60_000}
    result = guard.measurement(large)
    assert result["status"] == "FAIL"
    assert result["largest_variable"] == "PHASE_CONFIG"
    assert f"{result['total_chars']} characters" in guard.failure_detail(result)
    assert "reserve 8000" in guard.failure_detail(result)
    assert "largest variable PHASE_CONFIG" in guard.failure_detail(result)


def test_measurement_does_not_disclose_environment_values():
    secret = "TEST_ONLY_NEVER_PRINT_THIS_VALUE"
    result = guard.measurement({"PROBE_TOKEN": secret, "PHASE_CONFIG": "fixture"})
    output = json.dumps(result) + guard.failure_detail(result)
    assert secret not in output
    assert "fixture" not in output
    assert "PHASE_CONFIG" not in result
    assert result["total_chars"] == len("PROBE_TOKENPHASE_CONFIG" + secret + "fixture")


def test_uploaded_manifest_anchors_are_counted_without_disclosing_their_values():
    env = pod_control.manifest_upload_env({"fixture.py": "0" * 64})
    result = guard.measurement(env)
    assert (
        result["manifest_env_chars"] == result["total_chars"] == pod_env.env_chars(env)
    )
    assert result["manifest_env_chars"] > 0
    assert result["manifest_carrier_chars"] == 0
    assert result["manifest_compressed_bytes"] is None
    assert env["CODE_MANIFEST_SHA256"] not in json.dumps(result)
    assert env["CODE_MANIFEST_TRANSPORT"] not in json.dumps(result)


def test_comparison_counts_real_source_changes_without_emitting_paths_or_digests():
    before = {"sensitive-name.py": "a" * 64, "removed.py": "b" * 64}
    after = {"sensitive-name.py": "c" * 64, "added.py": "d" * 64}
    base = {
        "schema": "carbon.graphite.environment-ci.v2",
        "measurement_recipe": "fixture-frozen-recipe",
        "factory_source_sha256": "f" * 64,
        "host_system": "fixture",
        "ca_roots_present": 1,
        "ca_roots_configured": 1,
        "source_ref": "1" * 40,
        "shipped_files": 2,
        "manifest_json_bytes": 100,
        "profiles": [
            {
                "profile": "small",
                "backend": "jax",
                "total_chars": 50,
                "manifest_carrier_chars": 20,
                "manifest_env_chars": 30,
                "phase_config_chars": 10,
                "limit_chars": pod_env.ENV_LIMIT_CHARS,
                "reserve_chars": guard.CI_RESERVE_CHARS,
                "ci_limit_chars": pod_env.ENV_LIMIT_CHARS - guard.CI_RESERVE_CHARS,
            }
        ],
    }
    head = {
        **base,
        "source_ref": "2" * 40,
        "manifest_json_bytes": 120,
        "profiles": [
            {
                "profile": "small",
                "backend": "jax",
                "total_chars": 60,
                "manifest_carrier_chars": 30,
                "manifest_env_chars": 40,
                "phase_config_chars": 10,
                "limit_chars": pod_env.ENV_LIMIT_CHARS,
                "reserve_chars": guard.CI_RESERVE_CHARS,
                "ci_limit_chars": pod_env.ENV_LIMIT_CHARS - guard.CI_RESERVE_CHARS,
            }
        ],
    }
    result = guard.compare(base, head, before, after)
    assert (
        result["added_files"],
        result["removed_files"],
        result["changed_files"],
    ) == (1, 1, 1)
    assert result["manifest_json_byte_delta"] == 20
    assert result["added_python_files"] == 1
    assert result["added_nonpython_files"] == 0
    assert result["profile_char_deltas"][0]["total_char_delta"] == 10
    assert "sensitive-name" not in json.dumps(result)
    assert "a" * 64 not in json.dumps(result)
    with pytest.raises(ValueError, match="comparison_recipe_differs"):
        guard.compare(base, {**head, "factory_source_sha256": "0" * 64}, before, after)
    head["profiles"][0]["phase_config_chars"] += 1
    with pytest.raises(ValueError, match="comparison_job_differs"):
        guard.compare(base, head, before, after)
    head["profiles"][0]["phase_config_chars"] -= 1
    head["profiles"][0]["limit_chars"] += 1
    with pytest.raises(ValueError, match="comparison_job_differs"):
        guard.compare(base, head, before, after)


def test_cli_fails_on_any_profile_or_incomplete_environment(monkeypatch, capsys):
    result = {"complete_environment": True, "profiles": [{"status": "FAIL"}]}
    monkeypatch.setattr(guard, "profiles", lambda ref: (result, {}))
    assert guard.main([]) == 1
    assert json.loads(capsys.readouterr().out)["current"] == result
    result["profiles"][0]["status"] = "PASS"
    result["complete_environment"] = False
    assert guard.main([]) == 1
    capsys.readouterr()
    result["complete_environment"] = True
    assert guard.main([]) == 0


@pytest.fixture(scope="module")
def current_measurement():
    return guard.profiles()


def test_current_ship_fits_the_declared_l4_transport_budget(current_measurement):
    """Real source manifest, real CA roots, real environment factory; no pod."""
    result, _manifest = current_measurement
    assert result["schema"] == "carbon.graphite.environment-ci.v2"
    assert result["complete_environment"], result
    assert len(result["profiles"]) == 4
    for row in result["profiles"]:
        assert row["status"] == "PASS", guard.failure_detail(row)


def test_current_recipe_history_comparison_is_like_for_like(current_measurement):
    """No historical deployed-environment claim: only frozen-recipe growth."""
    current, current_manifest = current_measurement
    prior, prior_manifest = guard.profiles(guard.HISTORY_REF)
    result = guard.compare(prior, current, prior_manifest, current_manifest)
    assert result["shipped_file_delta"] == len(current_manifest) - len(prior_manifest)
    assert (
        result["added_files"] - result["removed_files"] == result["shipped_file_delta"]
    )
    for old, new, delta in zip(
        prior["profiles"],
        current["profiles"],
        result["profile_char_deltas"],
        strict=True,
    ):
        assert old["phase_config_chars"] == new["phase_config_chars"]
        assert delta["total_char_delta"] == delta["manifest_env_char_delta"]
