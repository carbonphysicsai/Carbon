"""A40 acceptance harness: selection rule, budget, fake-pod lifecycle, comparison.

No pod is created and nothing is spent: RunPod is the in-memory `FakeRunPod`
(the operator layer's own transport fake) and each pod's bootstrap endpoints
are served by `Fleet`. The numerical tests need the science stacks and skip
without them.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal

import pytest
from operator_fake_runpod import MOCK_KEY, Clock, FakeRunPod, key_file

from scripts.dev.exam_design.runpod import a40_acceptance as a40
from scripts.dev.exam_design.runpod import a40_pod_phase as phase

RELEASED_ACCELERATOR = a40.ACCELERATOR_IMAGE
RELEASED_TORCH = a40.TORCH_IMAGE


# ----------------------------------------------------------------- images, rate, budget
@pytest.mark.parametrize(
    "image",
    [
        "ghcr.io/carbonphysicsai/carbon-accelerator-worker:latest",
        "ghcr.io/carbonphysicsai/carbon-accelerator-worker",
        "ghcr.io/carbonphysicsai/carbon-accelerator-worker@sha256:" + "0" * 64,
        "ghcr.io/other/worker@sha256:" + "c34d579e" + "0" * 56,
        "ghcr.io/carbonphysicsai/carbon-torch-gpu-worker@sha256:abc",
        "",
        None,
    ],
)
def test_only_released_digest_pinned_images_are_accepted(image):
    with pytest.raises(a40.Refused):
        a40.check_image(image)


def test_released_images_are_the_briefs_digests():
    assert a40.check_image(RELEASED_ACCELERATOR).endswith(
        "c34d579e37eeffee944b8b4b876289963a6b283ea825b91a404167d92d0124b4"
    )
    assert a40.check_image(RELEASED_TORCH).endswith(
        "28856fd628d46818741e028837f064fe1a6f9f19653091adca92a36ff5726fc1"
    )
    assert a40.IMAGES == {"jax": RELEASED_ACCELERATOR, "pytorch": RELEASED_TORCH}


def test_rate_ceiling_derives_from_the_committed_grant():
    from pathlib import Path

    grant = Path(a40.REPOSITORY, a40.GRANT_RECORD).read_text()
    amended = re.findall(
        r"^\d{4}-\d{2}-\d{2}, owner: ceiling ([0-9.]+)/h, cap USD ([0-9.]+)$",
        grant,
        flags=re.MULTILINE,
    )
    assert amended[-1] == ("0.65", "8")
    assert a40.RATE_CEILING_USD_PER_HR == Decimal(amended[-1][0])
    assert a40.DEFAULT_CAP_USD == Decimal(amended[-1][1])
    assert a40.RATE_CEILING_USD_PER_HR == a40.grant_rate()
    # The original table's terms stay in the record, unchanged.
    assert "0.492739726" in grant and "4.25" in grant


def test_the_pod_phase_leaves_the_process_environment_untouched(tmp_path, monkeypatch):
    import os

    from carbon.agent_campaign.graphite import pod_phase

    device = {"index": 0, "uuid": "GPU-1", "name": "NVIDIA A40", "driver_version": "1"}
    monkeypatch.setattr(phase, "read_identity", lambda: (device, None))
    monkeypatch.setattr(pod_phase, "probe_environment", lambda code=None: {"ok": False})
    before = dict(os.environ)
    phase.run(pod_config(), tmp_path)
    assert dict(os.environ) == before


def test_rate_is_the_grants_rate():
    assert a40.hourly_rate() == Decimal("0.65")


def test_budget_gate_is_the_test_leads_inequality():
    hours = 1.0
    gate = a40.budget_gate(3600)
    expected = (4 + 2) * Decimal(hours) * Decimal("0.65") + Decimal("0.25")
    assert Decimal(gate["worst_case_usd"]) == expected.quantize(Decimal("0.0001"))
    # The grant's own 2.0 h deadline cannot fit six pods under USD 8.00.
    with pytest.raises(a40.Refused, match="exceeds the cap"):
        a40.budget_gate(2 * 3600)
    # A smoke pod's reservation counts against the same cap.
    with pytest.raises(a40.Refused):
        a40.budget_gate(3600, Decimal("4.25"), smoke_reserved=Decimal("0.5"))
    assert a40.budget_gate(3600, Decimal("4.25"))["cap_usd"] == "4.25"


def test_deadline_is_measured_times_one_and_a_half():
    smoke = {"startup_seconds": 100.0, "rebuild_wall_seconds": 20.0}
    assert a40.pod_deadline_seconds(smoke, 8) == int((100 + 8 * 20) * 1.5)


# ----------------------------------------------------------------- selection rule
def row(ident, n, jax=True, torch=True):
    return {
        "id": ident,
        "family": "mlp",
        "n_params": n,
        "compiles": {"jax": jax, "pytorch": torch},
    }


def ordered(rows):
    return sorted(rows, key=lambda r: (r["n_params"], r["id"]))


def roles(pool):
    return {role: r["id"] for role, r in a40.choose(ordered(pool))}


def test_smallest_lower_median_largest_with_ties_by_smallest_id():
    pool = [row("a", 1), row("b", 1), row("c", 2), row("d", 3), row("e", 3)]
    # n = 5: position floor(6/2) = 3 ascending is "c"; the largest tie is "d".
    assert roles(pool) == {"smallest": "a", "lower_median": "c", "largest": "d"}
    # Even n: position floor((4+1)/2) = 2, the lower median.
    assert roles([row("a", 1), row("b", 2), row("c", 3), row("d", 4)]) == {
        "smallest": "a",
        "lower_median": "b",
        "largest": "d",
    }


def test_a_member_that_cannot_compile_on_both_backends_is_skipped_in_direction():
    pool = [row("a", 1, torch=False), row("b", 1), row("c", 2, jax=False)]
    pool += [row("d", 3), row("e", 3, torch=False), row("f", 4)]
    # Skips a (smallest, upward) and c (median, upward to d); the largest is f.
    assert roles(pool) == {"smallest": "b", "lower_median": "d", "largest": "f"}
    # The largest direction runs down: the top two are ineligible.
    pool = [row("a", 1), row("b", 2), row("c", 3), row("d", 4, torch=False)]
    assert roles(pool)["largest"] == "c"


def test_no_eligible_member_is_a_refusal():
    with pytest.raises(a40.Refused):
        a40.choose(ordered([row("a", 1, jax=False)]))
    with pytest.raises(a40.Refused):
        a40.choose([])


def test_record_must_exist_and_match_its_sha256(tmp_path):
    path = tmp_path / "record.json"
    with pytest.raises(a40.Refused, match="no run record"):
        a40.load_record(path)
    record = {"schema": a40.RECORD_SCHEMA, "picks": [], "repeats": 2}
    digest = a40.write_record(record, path)
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert a40.load_record(path) == record
    path.write_bytes(path.read_bytes().replace(b'"repeats": 2', b'"repeats": 3'))
    with pytest.raises(a40.Refused, match="stored sha256"):
        a40.load_record(path)


def test_run_refuses_without_a_matching_record(tmp_path, capsys):
    code = a40.main(
        [
            "run",
            "--record",
            str(tmp_path / "missing.json"),
            "--smoke-record",
            str(tmp_path / "s.json"),
            "--work-dir",
            str(tmp_path / "w"),
            "--dry-run",
        ]
    )
    assert code == 2
    assert "no run record" in capsys.readouterr().err


# ----------------------------------------------------------------- a fake pod account
class Behaviour:
    def __init__(self, *, driver="580.159.03", uuid=None, probe_fails=False, salt="x"):
        self.driver, self.uuid = driver, uuid
        self.probe_fails, self.salt = probe_fails, salt
        self.polls = 0
        self.go = False


class Fleet:
    """Serves each pod's bootstrap endpoints, by creation order. No network."""

    def __init__(self, fake, behaviours, *, finish_after=3, crash_after=None):
        self.fake, self.behaviours = fake, behaviours
        self.finish_after, self.crash_after = finish_after, crash_after
        self.total_polls = 0
        self.go_calls = []
        self.identity_served = {}

    def behaviour(self, pod_id):
        index = int(pod_id[-4:]) - 1
        while len(self.behaviours) <= index:
            self.behaviours.append(Behaviour())
        return self.behaviours[index]

    def files(self, pod_id, behaviour, config):
        uuid = behaviour.uuid or f"GPU-{pod_id}"
        files = {
            "probe.json": {"ok": not behaviour.probe_fails},
            "identity.json": {
                "index": 0,
                "uuid": uuid,
                "name": "NVIDIA A40",
                "driver_version": behaviour.driver,
            },
        }
        if behaviour.probe_fails:
            files["failure.json"] = {
                "stage": "environment",
                "error": "no_usable_device",
            }
            return files
        rows = [
            {
                "recipe_id": recipe["id"],
                "repeat": repeat,
                "params_sha256": hashlib.sha256(
                    f"w:{config['backend']}:{recipe['id']}:{behaviour.salt}".encode()
                ).hexdigest(),
                "predictions_sha256": hashlib.sha256(
                    f"p:{config['backend']}:{recipe['id']}:{behaviour.salt}".encode()
                ).hexdigest(),
                "wall_seconds": 30.0,
                "seconds": 28.0,
            }
            for recipe in config["recipes"]
            for repeat in range(config["repeats"])
        ]
        files["results.json"] = {"complete": True, "rows": rows}
        return files

    def post(self, url, token, timeout):
        """The barrier release: only valid once two live pods of the backend
        have both served their identity (and probe)."""
        found = re.fullmatch(r"https://(\w+)-8000\.proxy\.runpod\.net/go", url)
        assert found, url
        pod_id = found.group(1)
        pod = self.fake.pods[pod_id]
        assert token == pod["env"]["PROBE_TOKEN"]
        backend = json.loads(pod["env"]["PHASE_CONFIG"])["backend"]
        seen = {
            p
            for p, b in self.identity_served.items()
            if b == backend and p in self.fake.pods
        }
        assert len(seen) >= 2, "released before both identities were recorded"
        self.behaviour(pod_id).go = True
        self.go_calls.append(pod_id)
        return 200, b""

    def __call__(self, url, token, timeout):
        found = re.fullmatch(r"https://(\w+)-8000\.proxy\.runpod\.net(/.*)", url)
        assert found, url
        pod_id, path = found.groups()
        pod = self.fake.pods.get(pod_id)
        if pod is None:
            return 0, b""
        assert token == pod["env"]["PROBE_TOKEN"]
        behaviour = self.behaviour(pod_id)
        behaviour.polls += 1
        self.total_polls += 1
        if self.crash_after is not None and self.total_polls > self.crash_after:
            raise RuntimeError("operator process died")
        config = json.loads(pod["env"]["PHASE_CONFIG"])
        stage = (
            "fetching_code"
            if behaviour.polls < 2
            else (
                "running_phase"
                if behaviour.polls < self.finish_after
                else ("phase_failed" if behaviour.probe_fails else "done")
            )
        )
        if stage == "done" and config.get("barrier") and not behaviour.go:
            stage = "running_phase"  # waiting at the barrier, nothing rebuilt
        files = {}
        if stage != "fetching_code":
            files = self.files(pod_id, behaviour, config)
        if stage in ("running_phase",):
            files.pop("results.json", None)
        blobs = {name: json.dumps(value).encode() for name, value in files.items()}
        if path == "/status":
            return 200, json.dumps({"stage": stage}).encode()
        if path == "/files":
            listing = [
                {"path": n, "size": len(b), "sha256": hashlib.sha256(b).hexdigest()}
                for n, b in sorted(blobs.items())
            ]
            return 200, json.dumps(listing).encode()
        if path.startswith("/file/") and path[6:] in blobs:
            if path == "/file/identity.json":
                self.identity_served[pod_id] = config["backend"]
            return 200, blobs[path[6:]]
        return 404, b""


RECORD = {
    "schema": a40.RECORD_SCHEMA,
    "repeats": 2,
    "seed": 0,
    "fno": {"id": "fno_defaults"},
    "picks": [
        {"role": "smallest", "id": "r1", "strategy": {}},
        {"role": "largest", "id": "r2", "strategy": {}},
    ],
    "recipes_by_backend": {
        "jax": [{"id": "r1", "strategy": {}}, {"id": "r2", "strategy": {}}],
        "pytorch": [
            {"id": "r1", "strategy": {}},
            {"id": "r2", "strategy": {}},
            {"id": "fno_defaults", "strategy": {}},
        ],
    },
}
SMOKE = {
    "schema": a40.SMOKE_SCHEMA,
    "outcome": "COMPLETE",
    "startup_seconds": 120.0,
    "rebuild_wall_seconds": 30.0,
    "booked_usd": "0.02",
}

SMOKES = {"jax": SMOKE, "pytorch": SMOKE}


@pytest.fixture
def world(tmp_path):
    clock = Clock()
    fake = FakeRunPod(rate=0.40)
    fake.fail_creates = 0
    bodies = []

    def transport(method, url, *, body, headers, timeout):
        if method == "POST" and url.endswith("/v1/pods") and fake.fail_creates:
            fake.fail_creates -= 1
            return 500, b'{"error": "There are no instances currently available"}'
        if method == "POST" and url.endswith("/v1/pods"):
            bodies.append(json.loads(body))
        reply = fake(method, url, body=body, headers=headers, timeout=timeout)
        if method == "POST" and url.endswith("/v1/pods") and fake.pods:
            newest = max(fake.pods)
            fake.pods[newest].setdefault(
                "machine", {"dataCenterId": f"DC-{len(bodies)}"}
            )
        return reply

    def make(behaviours, retry_window_seconds=None, **fleet_options):
        fleet = Fleet(fake, behaviours, **fleet_options)
        runner_options = (
            {}
            if retry_window_seconds is None
            else {"retry_window_seconds": retry_window_seconds}
        )
        runner = a40.PodRunner(
            work_dir=tmp_path / "work",
            key_file=key_file(tmp_path),
            code_ref="a" * 40,
            manifest={"carbon/x.py": "0" * 64},
            clock=clock,
            sleep=clock.advance,
            transport=transport,
            http=fleet,
            post=fleet.post,
            balance_floor=lambda: 1.0,
            poll_seconds=15.0,
            run_id="t1",
            **runner_options,
        )
        fake.fleet = fleet
        return runner, fleet

    yield make, fake, bodies
    # nothing may outlive a test, whatever it did
    assert fake.pods == {}


def run(world, behaviours, **options):
    make, fake, bodies = world
    runner, _fleet = make(behaviours, **options)
    try:
        summary, results = a40.run_acceptance(runner, RECORD, SMOKES)
    finally:
        runner.close()
    return summary, results, fake, bodies


def labels(results, backend):
    return {p.label: p for p in results[backend] if p.outcome == "COMPLETE"}


def test_clean_run_four_pods_each_terminated_and_verified(world):
    summary, _results, fake, bodies = run(world, [])
    assert fake.creates() == 4 and len(bodies) == 4
    assert summary["replacements_used"] == 0
    assert all(p["terminated_verified"] is True for p in summary["pods"])
    assert summary["reconciliation"]["clean"]
    assert summary["reconciliation"]["carbon_tagged_pods_left"] == 0
    assert fake.pods == {}
    # Released digests only, the A40 SECURE shape, the python-only bootstrap.
    images = [b["imageName"] for b in bodies]
    assert images == [RELEASED_ACCELERATOR] * 2 + [RELEASED_TORCH] * 2
    for body in bodies:
        assert body["cloudType"] == "SECURE" and body["gpuCount"] == 1
        assert body["gpuTypeIds"] == ["NVIDIA A40"]
        assert body["allowedCudaVersions"] == ["13.0"]
        assert body["dockerEntrypoint"][:3] == [a40.PYTHON, "-I", "-c"]
        env = body["env"]
        assert env["PHASE"] == "a40_acceptance"
        assert env["PHASE_MODULE"] == a40.PHASE_MODULE
        assert env["CODE_REF"] == "a" * 40
        assert MOCK_KEY not in json.dumps(body)
        assert not {k for k in env if "KEY" in k or "SECRET" in k}
    assert MOCK_KEY not in json.dumps(summary)


def test_each_pod_is_booked_at_its_full_reservation_with_its_backends_deadline(world):
    summary, _results, _fake, _bodies = run(world, [])
    for backend, rebuilds in (("jax", 4), ("pytorch", 6)):
        deadline = a40.pod_deadline_seconds(SMOKE, rebuilds)
        assert summary["budget"][backend]["deadline_seconds"] == deadline
        booked = {p["booked_usd"] for p in summary["pods"] if p["backend"] == backend}
        assert booked == {str(a40.reservation_usd(deadline))}


def test_the_cap_gate_applies_per_backend():
    slow_torch = {**SMOKE, "rebuild_wall_seconds": 3000.0}
    with pytest.raises(a40.Refused, match="exceeds the cap"):
        a40.plan(RECORD, {"jax": SMOKE, "pytorch": slow_torch})
    plan = a40.plan(RECORD, SMOKES)
    assert plan["jax"]["pods"] == 4 and plan["jax"]["replacements"] == 2


def test_comparison_of_a_clean_run(world):
    _summary, results, *_ = run(world, [])
    flat = a40.pod_results([p for pods in results.values() for p in pods])
    document = a40.compare(flat)
    cells = {(c["backend"], c["recipe_id"]): c for c in document["cells"]}
    assert set(cells) == {
        ("jax", "r1"),
        ("jax", "r2"),
        ("pytorch", "r1"),
        ("pytorch", "r2"),
        ("pytorch", "fno_defaults"),
    }
    for cell in cells.values():
        assert cell["within_host_equal"] is True
        assert cell["across_hosts"]["outcome"] == "AGREE"
        assert cell["driver_builds"] == ["580.159.03"]
        assert len(cell["device_ids"]) == 2
    assert document["jax_fno"].startswith("not applicable")


def test_failed_probe_is_failed_infra_and_gets_one_replacement(world):
    summary, results, fake, _bodies = run(world, [Behaviour(probe_fails=True)])
    assert fake.creates() == 5 and summary["replacements_used"] == 1
    outcomes = [(p["backend"], p["label"], p["outcome"]) for p in summary["pods"]]
    assert ("jax", "A", "FAILED_INFRA") in outcomes
    assert sorted(labels(results, "jax")) == ["A", "B"]
    replacement = next(p for p in summary["pods"] if p["replaces"])
    assert replacement["reason"] is None and replacement["outcome"] == "COMPLETE"
    failed = next(p for p in summary["pods"] if p["outcome"] == "FAILED_INFRA")
    assert failed["reason"] == "gpu probe" or failed["terminated_verified"] is True


def test_a_failed_probe_stops_everything_else_on_that_pod(world):
    _summary, results, *_ = run(world, [Behaviour(probe_fails=True)])
    failed = next(p for p in results["jax"] if p.outcome == "FAILED_INFRA")
    assert "results.json" not in failed.files
    assert "failure.json" in failed.files


def test_driver_mismatch_replaces_the_second_host_once(world):
    behaviours = [Behaviour(), Behaviour(driver="580.159.04")]
    summary, results, fake, _bodies = run(world, behaviours)
    assert fake.creates() == 5
    assert summary["driver_problems"] and "driver builds differ" in " ".join(
        summary["driver_problems"][0]["problems"]
    )
    assert any(p["outcome"] == "REPLACED_DRIVER_MISMATCH" for p in summary["pods"])
    flat = a40.pod_results([p for pods in results.values() for p in pods])
    jax_cells = [c for c in a40.compare(flat)["cells"] if c["backend"] == "jax"]
    assert {c["across_hosts"]["outcome"] for c in jax_cells} == {"AGREE"}


def test_persistent_driver_mismatch_releases_no_rebuild_and_is_recorded(world):
    odd = lambda: Behaviour(driver="580.159.04")
    summary, results, fake, _bodies = run(world, [Behaviour(), odd(), odd(), odd()])
    assert fake.creates() == 6  # 4 pods + the 2 replacements the grant allows
    assert summary["replacements_used"] == 2
    jax = [p for p in summary["pods"] if p["backend"] == "jax"]
    assert {"REFUSED_DRIVER_MISMATCH", "REPLACED_DRIVER_MISMATCH"} <= {
        p["outcome"] for p in jax
    }
    assert not [p for p in results["jax"] if p.outcome == "COMPLETE"]
    # The barrier was never released for a jax pod: no rebuild ever started.
    jax_ids = {p["pod_id"] for p in jax}
    assert not jax_ids & set(fake.fleet.go_calls)
    assert summary["driver_problems"][-1]["builds"] == ["580.159.03", "580.159.04"]


def test_the_barrier_is_released_only_after_both_identities_match(world):
    behaviours = [Behaviour(), Behaviour(driver="580.159.04")]
    summary, _results, fake, _bodies = run(world, behaviours)
    mismatched = next(
        p for p in summary["pods"] if p["outcome"] == "REPLACED_DRIVER_MISMATCH"
    )
    assert mismatched["pod_id"] not in fake.fleet.go_calls
    assert len(fake.fleet.go_calls) == 4  # two matching pods per backend


def test_a_pod_never_outlives_a_crashed_operator(world):
    make, fake, _bodies = world
    runner, _fleet = make([], crash_after=3)
    with pytest.raises(RuntimeError, match="operator process died"):
        a40.run_acceptance(runner, RECORD, SMOKES)
    runner.close()
    assert fake.pods == {}  # the fixture asserts it again


def test_a_pod_that_never_finishes_times_out_and_is_terminated(world):
    summary, _results, fake, _bodies = run(world, [], finish_after=10**9)
    assert {p["outcome"] for p in summary["pods"]} == {"TIMEOUT"}
    assert all(p["terminated_verified"] is True for p in summary["pods"])
    assert fake.pods == {}


def test_launch_refuses_below_the_balance_floor(world):
    make, fake, _bodies = world
    runner, _fleet = make([])
    runner.balance_floor = lambda: 10**6
    with pytest.raises(a40.Refused, match="balance"):
        a40.run_acceptance(runner, RECORD, SMOKES)
    runner.close()
    assert fake.creates() == 0


def test_launch_refuses_an_offer_above_the_rate_ceiling(world):
    make, fake, _bodies = world
    fake.rate = 0.70
    runner, _fleet = make([])
    with pytest.raises(a40.NoA40):  # above the ceiling is never created
        a40.run_acceptance(runner, RECORD, SMOKES)
    runner.close()
    assert fake.creates() == 0


def test_run_refuses_when_the_worst_case_exceeds_the_cap(world):
    make, fake, _bodies = world
    runner, _fleet = make([])
    slow = {**SMOKE, "rebuild_wall_seconds": 3000.0}
    with pytest.raises(a40.Refused, match="exceeds the cap"):
        a40.run_acceptance(runner, RECORD, {"jax": slow, "pytorch": slow})
    runner.close()
    assert fake.creates() == 0


def test_smoke_records_measured_seconds_on_one_pod(world, tmp_path):
    make, fake, _bodies = world
    runner, _fleet = make([])
    out = tmp_path / "smoke.json"
    record = {
        **RECORD,
        "picks": [{"role": "largest", "id": "r2", "strategy": {}}],
    }
    measured = a40.smoke(runner, record, backend="jax", out=out)
    runner.close()
    assert fake.creates() == 1 and fake.pods == {}
    assert measured["outcome"] == "COMPLETE"
    assert measured["rebuild_wall_seconds"] == 30.0
    assert measured["startup_seconds"] >= 0
    assert a40.load_smoke(out)["recipe_id"] == "r2"
    assert measured["pod"]["terminated_verified"] is True


def test_pytorch_smoke_is_one_fno_rebuild(world, tmp_path):
    make, fake, _bodies = world
    runner, _fleet = make([])
    measured = a40.smoke(runner, RECORD, backend="pytorch", out=tmp_path / "s.json")
    runner.close()
    assert measured["recipe_id"] == "fno_defaults" and fake.creates() == 1
    assert measured["backend"] == "pytorch" and measured["outcome"] == "COMPLETE"


def test_dry_run_creates_nothing(tmp_path, monkeypatch, capsys):
    record_path = tmp_path / "record.json"
    a40.write_record(RECORD, record_path)
    smoke_path = tmp_path / "smoke.json"
    smoke_path.write_text(json.dumps(SMOKE))
    torch_path = tmp_path / "smoke-pytorch.json"
    torch_path.write_text(json.dumps(SMOKE))

    def forbidden(*_a, **_k):
        raise AssertionError("a dry run must not build a pod runner")

    monkeypatch.setattr(a40, "PodRunner", forbidden)
    monkeypatch.setattr(a40, "build_manifest", lambda ref, repository=None: {"a": "b"})
    code = a40.main(
        [
            "run",
            "--record",
            str(record_path),
            "--smoke-record",
            str(smoke_path),
            "--smoke-record-pytorch",
            str(torch_path),
            "--work-dir",
            str(tmp_path / "w"),
            "--code-ref",
            "a" * 40,
            "--dry-run",
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["pods_created"] == 0 and printed["images"] == a40.IMAGES
    for backend in a40.BACKENDS:
        assert printed["plan"][backend]["worst_case_usd"]
        assert printed["plan"][backend]["deadline_seconds"] > 0


# ----------------------------------------------------------------- comparison
def host(label, uuid, driver, backend="jax", salt="s", repeats=("s", "s"), rid="r"):
    return {
        "backend": backend,
        "label": label,
        "identity": {"uuid": uuid, "driver_version": driver, "name": "NVIDIA A40"},
        "rows": [
            {
                "recipe_id": rid,
                "repeat": i,
                "params_sha256": hashlib.sha256(f"{salt}{r}".encode()).hexdigest(),
                "predictions_sha256": hashlib.sha256(
                    f"p{salt}{r}".encode()
                ).hexdigest(),
            }
            for i, r in enumerate(repeats)
        ],
    }


def cell(document):
    return document["cells"][0]


def test_within_host_difference_is_reported_and_blocks_across_hosts():
    document = a40.compare(
        [host("A", "u1", "1", repeats=("a", "b")), host("B", "u2", "1")]
    )
    assert cell(document)["within_host_equal"] is False
    assert cell(document)["across_hosts"]["outcome"] == "NO_SINGLE_DIGEST_WITHIN_A_HOST"


def test_across_hosts_disagreement_is_recorded_without_a_tolerance():
    document = a40.compare([host("A", "u1", "1"), host("B", "u2", "1", salt="z")])
    assert cell(document)["within_host_equal"] is True
    assert cell(document)["across_hosts"]["outcome"] == "DISAGREE"


def test_one_unit_is_refused():
    document = a40.compare([host("A", "u1", "1")])
    assert cell(document)["across_hosts"]["outcome"] == "REFUSED_ONE_UNIT"


def test_driver_mismatch_is_refused_unless_a_deviation_names_exactly_the_builds():
    from scripts.dev.gpu_determinism_study import compare_units

    pair = [host("A", "u1", "580.1"), host("B", "u2", "580.2")]
    document = a40.compare(pair)
    assert cell(document)["across_hosts"]["outcome"] == "REFUSED_DRIVER_MISMATCH"
    assert cell(document)["driver_builds"] == ["580.1", "580.2"]
    assert cell(document)["preflight_problems"]

    def deviation(builds):
        return compare_units.DriverDeviation.read(
            {
                "schema": compare_units.DEVIATION_SCHEMA,
                "builds": builds,
                "recorded_in": "run record",
                "reason": "operator decision",
            }
        )

    wrong = a40.compare(pair, deviation=deviation(["580.1", "580.9"]))
    assert cell(wrong)["across_hosts"]["outcome"] == "REFUSED_DRIVER_MISMATCH"
    right = a40.compare(pair, deviation=deviation(["580.1", "580.2"]))
    assert cell(right)["across_hosts"]["outcome"] == "AGREE"
    assert cell(right)["across_hosts"]["deviation"]["builds"] == ["580.1", "580.2"]


def test_cpu_versus_gpu_is_labelled_a_record_only():
    gpu = [host("A", "u1", "1"), host("B", "u2", "1")]
    cpu_rows = host("cpu", "none", "none", salt="cpu")["rows"]
    cpu = {"jax": {"recipes": ["r"], "rows": cpu_rows}}
    document = a40.compare(gpu, cpu=cpu)
    [record] = document["cpu_vs_gpu"]
    assert record["label"] == (
        "harness-to-harness only; not comparable to capability-report state_sha256"
    )
    assert record["digests_equal"] is False


# ----------------------------------------------------------------- the pod phase
def test_pinned_environment_matches_worker_environment():
    pytest.importorskip("numpy")
    import accelerator_host

    from carbon.reconstruction.accelerators import (
        GPU_PROFILE,
        AcceleratorRole,
        worker_environment,
    )

    record = accelerator_host.for_profile(
        __import__("pathlib").Path(__import__("tempfile").mkdtemp()), GPU_PROFILE
    )
    mine = phase.pinned_environment(
        "jax", device={"uuid": record.device_uuid, "name": record.device_kind}
    )
    theirs = worker_environment(
        GPU_PROFILE, AcceleratorRole.VALIDATOR_RECONSTRUCTION, host_device=record
    )
    assert all(theirs[key] == value for key, value in mine.items())
    for key in (
        "JAX_PLATFORMS",
        "XLA_FLAGS",
        "NVIDIA_TF32_OVERRIDE",
        "CUBLAS_WORKSPACE_CONFIG",
        "JAX_DEFAULT_MATMUL_PRECISION",
        "JAX_ENABLE_X64",
        "XLA_PYTHON_CLIENT_PREALLOCATE",
        "XLA_PYTHON_CLIENT_ALLOCATOR",
        "CARBON_ACCELERATOR_DEVICE_KIND",
        "CUDA_VISIBLE_DEVICES",
    ):
        assert key in mine
    assert mine["XLA_FLAGS"].count("--xla_gpu_") == 3


def test_cpu_environment_has_no_device_variables():
    env = phase.pinned_environment("jax", device=None)
    assert env["JAX_PLATFORMS"] == "cpu"
    assert not {
        "CUDA_VISIBLE_DEVICES",
        "XLA_FLAGS",
        "CARBON_ACCELERATOR_DEVICE_KIND",
    } & set(env)


def pod_config(backend="jax"):
    return {
        "backend": backend,
        "recipes": [{"id": "r1", "strategy": {"x": 1}}],
        "repeats": 2,
        "seed": 0,
    }


def test_phase_refuses_an_unreadable_device_and_runs_no_rebuild(tmp_path, monkeypatch):
    monkeypatch.setattr(
        phase, "read_identity", lambda: (None, "device uuid is unreadable")
    )
    monkeypatch.setattr(
        phase, "run_recipes", lambda *a, **k: pytest.fail("a rebuild ran")
    )
    assert phase.run(pod_config(), tmp_path) == phase.EXIT_ENVIRONMENT
    failure = json.loads((tmp_path / "failure.json").read_text())
    assert failure["stage"] == "environment"
    assert not (tmp_path / "results.json").exists()


def test_phase_stops_on_a_failed_probe_before_any_rebuild(tmp_path, monkeypatch):
    from carbon.agent_campaign.graphite import pod_phase

    device = {
        "index": 0,
        "uuid": "GPU-1",
        "name": "NVIDIA A40",
        "driver_version": "580.1",
    }
    monkeypatch.setattr(phase, "read_identity", lambda: (device, None))
    monkeypatch.setattr(
        pod_phase,
        "probe_environment",
        lambda code=None: {
            "schema": pod_phase.PROBE_SCHEMA,
            "ok": False,
            "error_type": "X",
        },
    )
    monkeypatch.setattr(
        phase, "run_recipes", lambda *a, **k: pytest.fail("a rebuild ran")
    )
    monkeypatch.setenv("JAX_PLATFORMS", "unchanged-by-the-test")
    assert phase.run(pod_config(), tmp_path) == phase.EXIT_ENVIRONMENT
    assert json.loads((tmp_path / phase.IDENTITY_FILE).read_text())["uuid"] == "GPU-1"
    assert json.loads((tmp_path / phase.PROBE_FILE).read_text())["ok"] is False
    assert not (tmp_path / "results.json").exists()


def _ready_phase(monkeypatch, order):
    from carbon.agent_campaign.graphite import pod_phase

    device = {
        "index": 0,
        "uuid": "GPU-1",
        "name": "NVIDIA A40",
        "driver_version": "580.1",
    }
    monkeypatch.setattr(phase, "read_identity", lambda: (device, None))
    monkeypatch.setattr(pod_phase, "probe_environment", lambda code=None: {"ok": True})
    monkeypatch.setattr(
        phase, "run_recipes", lambda *a, **k: order.append("rebuild") or []
    )


def test_phase_waits_at_the_barrier_and_runs_no_rebuild_unreleased(
    tmp_path, monkeypatch
):
    order = []
    _ready_phase(monkeypatch, order)
    monkeypatch.setattr(
        phase, "wait_for_go", lambda *a, **k: order.append("wait") or False
    )
    config = {**pod_config(), "barrier": True, "go_timeout_seconds": 1}
    assert phase.run(config, tmp_path) == phase.EXIT_BARRIER
    assert order == ["wait"]
    assert json.loads((tmp_path / "failure.json").read_text())["stage"] == "barrier"
    assert (tmp_path / phase.IDENTITY_FILE).exists()


def test_phase_rebuilds_only_after_the_release(tmp_path, monkeypatch):
    order = []
    _ready_phase(monkeypatch, order)
    monkeypatch.setattr(
        phase, "wait_for_go", lambda *a, **k: order.append("wait") or True
    )
    config = {**pod_config(), "barrier": True, "go_timeout_seconds": 1}
    phase.run(config, tmp_path)
    assert order == ["wait", "rebuild"]


def test_phase_uses_the_torch_probe_for_the_pytorch_image(tmp_path, monkeypatch):
    from carbon.agent_campaign.graphite import pod_phase

    seen = []
    device = {
        "index": 0,
        "uuid": "GPU-1",
        "name": "NVIDIA A40",
        "driver_version": "580.1",
    }
    monkeypatch.setattr(phase, "read_identity", lambda: (device, None))
    monkeypatch.setattr(
        pod_phase,
        "probe_environment",
        lambda code=None: seen.append(code) or {"ok": False, "error_type": "X"},
    )
    phase.run(pod_config("pytorch"), tmp_path)
    phase.run(pod_config("jax"), tmp_path)
    assert seen == [phase.TORCH_PROBE, None]


def test_phase_hashes_weights_and_predictions_per_fresh_interpreter(
    tmp_path, monkeypatch
):
    calls = []

    def child(strategy, seed, root, env, python=None, timeout=0):
        calls.append(env)
        return {
            "params_sha256": "a" * 64,
            "predictions_sha256": "b" * 64,
            "seconds": 1.0,
        }

    monkeypatch.setattr(phase, "run_repeat", child)
    rows = phase.run_recipes(
        pod_config(), tmp_path, {"JAX_PLATFORMS": "cuda"}, out=tmp_path
    )
    assert [r["repeat"] for r in rows] == [0, 1] and len(calls) == 2
    document = phase.results_document(
        pod_config(), rows, device=None, environment_pins=["JAX_PLATFORMS"]
    )
    assert document["complete"] is True
    assert json.loads((tmp_path / "progress.json").read_text()) == {
        "done": 2,
        "total": 2,
    }


def test_a_failed_repeat_makes_the_results_incomplete():
    rows = [{"recipe_id": "r1", "repeat": 0, "error": "exit 1"}]
    assert (
        phase.results_document(pod_config(), rows, device=None, environment_pins=[])[
            "complete"
        ]
        is False
    )


def test_ship_list_excludes_protected_code_and_still_refuses_protected_data(
    monkeypatch,
):
    from carbon.agent_campaign.graphite import pods

    tracked = [
        "carbon/a.py",
        "carbon/private/x.py",
        "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json",
        "carbon/challenge_validator/confirmation_sets/registry.json",
    ]
    monkeypatch.setattr(pods, "tracked", lambda ref, prefixes, repository=None: tracked)
    paths = a40.ship_paths("a" * 40)
    assert "carbon/a.py" in paths
    assert not [p for p in paths if a40.is_protected(p) or "/private/" in p]
    assert set(a40.DATA_PATHS) <= set(paths) and set(a40.SHIPPED_FILES) <= set(paths)
    monkeypatch.setattr(a40, "DATA_PATHS", ("docs/secret/train.jsonl.gz",))
    with pytest.raises(a40.Refused, match="forbidden data path"):
        a40.ship_paths("a" * 40)


def test_the_real_tree_ships_without_a_refusal():
    import subprocess

    ref = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=a40.REPOSITORY,
    ).stdout.strip()
    paths = a40.ship_paths(ref)
    assert not [p for p in paths if a40.is_protected(p)]
    assert "carbon/battery/compile.py" in paths


def test_a_rebuild_needs_none_of_the_excluded_files(tmp_path):
    """Copy the shipped files only, and rebuild one tiny recipe from them."""
    pytest.importorskip("jax")
    import shutil
    import subprocess

    ref = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=a40.REPOSITORY,
    ).stdout.strip()
    for path in a40.ship_paths(ref):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a40.REPOSITORY / path, target)
    strategy = a40._strategy("mlp", {"steps": 32, "width": 8, "depth": 1})
    record = phase.run_repeat(
        strategy, 0, tmp_path, phase.pinned_environment("jax", device=None)
    )
    assert "error" not in record, record


# ----------------------------------------------------------------- numerics (science stacks)
def test_data_paths_and_pins_are_the_challenges():
    pytest.importorskip("numpy")
    from pathlib import Path

    from carbon.battery import challenge

    root = Path(__file__).resolve().parents[2]
    assert a40.DATA_PATHS == (challenge.TRAIN_V1_PATH, challenge.OCV_TABLE_PATH)
    challenge.PublicMaterial.load(root)  # both files exist and match their pins


def test_the_fno_recipe_uses_the_contracts_defaults():
    pytest.importorskip("numpy")
    strategy = a40.fno_strategy()
    assert strategy["parameters"] == {"backend": "pytorch"}
    recipe = a40.compiled(strategy)
    assert recipe is not None and recipe.family == "fno"
    assert recipe.settings["backend"] == "pytorch"
    # Every other value is the registered default: no field was chosen here.
    assert set(recipe.supplied) == {"backend"}


def test_one_rebuild_hashes_weights_and_predictions_in_a_fresh_interpreter(tmp_path):
    pytest.importorskip("jax")
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    strategy = a40._strategy("mlp", {"steps": 32, "width": 8, "depth": 1})
    env = phase.pinned_environment("jax", device=None)
    first = phase.run_repeat(strategy, 0, root, env)
    second = phase.run_repeat(strategy, 0, root, env)
    assert "error" not in first, first
    for key in ("params_sha256", "predictions_sha256"):
        assert re.fullmatch(r"[0-9a-f]{64}", first[key])
        assert first[key] == second[key]
    assert first["backend"] == "jax"


# ----------------------------------------------------------------- launch diagnostics
def _runner_and_clock(world):
    make, fake, _bodies = world
    runner, _fleet = make([])
    return runner, fake


def test_ports_are_exactly_the_bootstrap_port(world):
    _summary, _results, _fake, bodies = run(world, [])
    assert {tuple(b["ports"]) for b in bodies} == {("8000/http",)}
    assert not any("GO_TOKEN" in b["env"] for b in bodies)


def test_provider_text_redacts_key_shapes_and_is_bounded():
    from scripts.dev.exam_design.runpod.operator_compute.runpod import provider_text

    body = {
        "error": f"no instances; key {MOCK_KEY} Bearer abcdef0123 "
        + "A1b2C3d4" * 6
        + " x" * 300
    }
    text = provider_text(body)
    assert len(text) <= 200
    assert MOCK_KEY not in text and "abcdef0123" not in text
    assert "A1b2C3d4" * 3 not in text
    assert "[redacted]" in text and "no instances" in text
    assert provider_text(None) == "no JSON body"


def test_create_failure_carries_status_and_redacted_body(world):
    from scripts.dev.exam_design.runpod.operator_compute import ComputeError

    runner, fake = _runner_and_clock(world)
    fake.fail_next_create_with = 400
    with pytest.raises(a40.LaunchFailed) as caught:
        runner.launch("jax", "A", {"recipes": [], "repeats": 1, "seed": 0}, 600)
    runner.close()
    assert caught.value.status == 400 and "mock refusal" in caught.value.message
    assert MOCK_KEY not in str(caught.value)
    assert ComputeError  # the typed error is what the adapter raised


def test_definitive_failure_stops_at_once_and_the_intent_is_rejected(world):
    runner, fake = _runner_and_clock(world)
    fake.fail_next_create_with = 400
    with pytest.raises(a40.LaunchFailed):
        runner.launch("jax", "A", {"recipes": [], "repeats": 1, "seed": 0}, 600)
    assert len(runner.launch_attempts) == 1
    assert runner.launch_attempts[0]["capacity"] is False
    state = runner.store.intent("a40-acceptance", "a40-t1-jax-a-1").state
    runner.close()
    assert str(state) == "rejected"


def test_a_failed_secure_attempt_falls_back_to_community_in_the_same_round(
    world, capsys
):
    runner, fake = _runner_and_clock(world)
    fake.fail_creates = 1
    start = runner.clock()
    pod = runner.launch("jax", "A", {"recipes": [], "repeats": 1, "seed": 0}, 600)
    assert pod.cloud == "COMMUNITY" and runner.clock() == start  # no wait
    [attempt] = runner.launch_attempts
    assert attempt["cloud"] == "SECURE" and attempt["status"] == 500
    assert attempt["capacity"] is True
    assert "no instances" in attempt["message"]
    err = capsys.readouterr().err
    assert "cloud=SECURE" in err and "status=500" in err and "no instances" in err
    assert MOCK_KEY not in err
    assert pod.summary()["cloud"] == "COMMUNITY"
    runner.terminate(pod)
    runner.close()


def test_a_whole_round_failing_waits_ten_minutes_then_secure_is_tried_again(world):
    runner, fake = _runner_and_clock(world)
    fake.fail_creates = 2  # SECURE and COMMUNITY of round one
    start = runner.clock()
    pod = runner.launch("jax", "A", {"recipes": [], "repeats": 1, "seed": 0}, 600)
    assert pod.cloud == "SECURE"
    assert runner.clock() - start == a40.RETRY_SECONDS
    assert [a_["cloud"] for a_ in runner.launch_attempts] == ["SECURE", "COMMUNITY"]
    runner.terminate(pod)
    runner.close()


def test_no_capacity_in_the_window_is_the_named_result_after_every_round(world):
    runner, fake = _runner_and_clock(world)
    fake.fail_creates = 10**6
    start = runner.clock()
    with pytest.raises(a40.NoA40) as caught:
        runner.launch("jax", "A", {"recipes": [], "repeats": 1, "seed": 0}, 600)
    runner.close()
    assert caught.value.result == "NO_A40_AFTER_60_MIN"
    assert runner.clock() - start == 3600
    # rounds at 0, 10, ..., 60 minutes, SECURE then COMMUNITY in each
    assert len(runner.launch_attempts) == 14
    assert {a_["cloud"] for a_ in runner.launch_attempts} == {"SECURE", "COMMUNITY"}
    assert fake.pods == {}


def test_the_retry_window_is_configurable(world):
    make, fake, _bodies = world
    runner, _fleet = make([], retry_window_seconds=1200)
    fake.fail_creates = 10**6
    with pytest.raises(a40.NoA40) as caught:
        runner.launch("jax", "A", {"recipes": [], "repeats": 1, "seed": 0}, 600)
    runner.close()
    assert caught.value.result == "NO_A40_AFTER_20_MIN"


def test_the_cli_exits_with_the_named_result_when_no_a40_comes(
    monkeypatch, capsys, tmp_path
):
    record = tmp_path / "r.json"
    a40.write_record(RECORD, record)
    smoke_path = tmp_path / "s.json"
    smoke_path.write_text(json.dumps(SMOKE))
    seen = {}

    def runner_that_never_gets_one(args, record):
        seen["window"] = args.retry_window_minutes
        raise a40.NoA40(args.retry_window_minutes * 60)

    monkeypatch.setattr(a40, "_runner", runner_that_never_gets_one)
    code = a40.main(
        ["smoke", "--record", str(record), "--smoke-record", str(smoke_path),
         "--work-dir", str(tmp_path / "w"), "--retry-window-minutes", "30"]
    )  # fmt: skip
    assert code == 3 and seen["window"] == 30
    assert json.loads(capsys.readouterr().out) == {"result": "NO_A40_AFTER_30_MIN"}


def test_a_definitive_refusal_does_not_try_the_other_cloud(world):
    runner, fake = _runner_and_clock(world)
    fake.fail_next_create_with = 400
    with pytest.raises(a40.LaunchFailed):
        runner.launch("jax", "A", {"recipes": [], "repeats": 1, "seed": 0}, 600)
    runner.close()
    assert [a_["cloud"] for a_ in runner.launch_attempts] == ["SECURE"]
    assert fake.creates() == 1


def test_cuda_versions_are_derived_from_both_image_locks(world):
    assert a40.supported_cuda_versions() == ("13.0",)
    _summary, _results, _fake, bodies = run(world, [])
    assert {tuple(b["allowedCudaVersions"]) for b in bodies} == {("13.0",)}


def test_the_decision_record_names_its_allowances_and_changes_no_figure():
    text = (a40.REPOSITORY / a40.GRANT_RECORD).read_text()
    lines = [line.strip() for line in text.splitlines()]
    assert "Community allowed per owner direction 2026-10-08" in lines
    assert "Vast.ai A40 allowed, owner-rented, per owner direction 2026-10-08" in lines
    assert "0.492739726" in text and "4.25" in text


def test_the_bootstrap_accepts_post_go_only_with_the_token(tmp_path, monkeypatch):
    import http.server
    import importlib.util
    import threading
    import urllib.error
    import urllib.request

    marker = tmp_path / "go"
    monkeypatch.setenv("PROBE_TOKEN", "tok-123")
    monkeypatch.setenv("GO_FILE", str(marker))
    spec = importlib.util.spec_from_file_location(
        "a40_bootstrap_under_test",
        a40.REPOSITORY / "scripts/dev/exam_design/runpod/bootstrap.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = http.server.HTTPServer(("127.0.0.1", 0), module.H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def post(path, token):
        request = urllib.request.Request(
            base + path, data=b"", method="POST", headers={"X-Probe-Token": token}
        )
        try:
            return urllib.request.urlopen(request, timeout=10).status
        except urllib.error.HTTPError as refused:
            return refused.code

    try:
        assert post("/go", "wrong") == 404 and not marker.exists()
        assert post("/other", "tok-123") == 404 and not marker.exists()
        assert post("/go", "tok-123") == 200 and marker.exists()
    finally:
        server.shutdown()


def test_the_phase_barrier_sees_the_marker_or_times_out(tmp_path):
    marker = tmp_path / "go"
    assert phase.wait_for_go(0.2, path=marker) is False
    marker.write_text("go")
    assert phase.wait_for_go(5, path=marker) is True


def test_each_pods_datacenter_and_driver_build_are_recorded(world):
    summary, results, _fake, _bodies = run(world, [])
    assert all(p["datacenter"].startswith("DC-") for p in summary["pods"])
    assert {p["driver_version"] for p in summary["pods"]} == {"580.159.03"}
    flat = a40.pod_results([p for pods in results.values() for p in pods])
    cell = a40.compare(flat)["cells"][0]
    assert len(cell["datacenters"]) == 2 and cell["driver_builds"] == ["580.159.03"]


# ----------------------------------------------------------------- --skip-fno
def test_skip_fno_drops_the_leg_from_recipes_rebuilds_and_deadline():
    full = a40.phase_config("pytorch", RECORD)["recipes"]
    skipped = a40.phase_config("pytorch", RECORD, skip_fno=True)["recipes"]
    assert [r["id"] for r in full] == ["r1", "r2", "fno_defaults"]
    assert [r["id"] for r in skipped] == ["r1", "r2"]
    assert a40.phase_config("jax", RECORD, skip_fno=True)["recipes"] == (
        a40.phase_config("jax", RECORD)["recipes"]
    )
    plan = a40.plan(RECORD, SMOKES)
    short = a40.plan(RECORD, SMOKES, skip_fno=True)
    assert plan["pytorch"]["rebuilds_per_pod"] == 6
    assert short["pytorch"]["rebuilds_per_pod"] == 4
    assert short["pytorch"]["deadline_seconds"] < plan["pytorch"]["deadline_seconds"]
    assert short["jax"] == plan["jax"]


def test_pytorch_smoke_with_skip_fno_rebuilds_the_largest_pick(world, tmp_path):
    make, _fake, _bodies = world
    runner, _fleet = make([])
    measured = a40.smoke(
        runner, RECORD, backend="pytorch", out=tmp_path / "s.json", skip_fno=True
    )
    runner.close()
    assert measured["recipe_id"] == "r2" and measured["outcome"] == "COMPLETE"


def test_a_skipped_fno_run_records_the_skip_and_never_launches_the_fno(world):
    make, fake, bodies = world
    runner, _fleet = make([])
    try:
        summary, results = a40.run_acceptance(runner, RECORD, SMOKES, skip_fno=True)
    finally:
        runner.close()
    configs = [json.loads(dict(b["env"])["PHASE_CONFIG"]) for b in bodies]
    assert all("fno_defaults" not in [r["id"] for r in c["recipes"]] for c in configs)
    assert summary["skipped"]["fno"]["skipped"] is True
    assert "v3" in summary["skipped"]["fno"]["reason"]
    flat = a40.pod_results([p for pods in results.values() for p in pods])
    document = a40.compare(flat, skipped=a40.SKIPPED_FNO)
    assert document["skipped"] == a40.SKIPPED_FNO
    assert "fno_defaults" not in {c["recipe_id"] for c in document["cells"]}
    assert fake.pods == {}


def test_the_run_record_is_not_changed_by_skip_fno(tmp_path, capsys, monkeypatch):
    record_path = tmp_path / "record.json"
    digest = a40.write_record(RECORD, record_path)
    for name in ("s.json", "t.json"):
        (tmp_path / name).write_text(json.dumps(SMOKE))
    monkeypatch.setattr(a40, "build_manifest", lambda ref, repository=None: {"a": "b"})
    code = a40.main(
        [
            "run", "--record", str(record_path), "--smoke-record", str(tmp_path / "s.json"),
            "--smoke-record-pytorch", str(tmp_path / "t.json"),
            "--work-dir", str(tmp_path / "w"), "--code-ref", "a" * 40,
            "--dry-run", "--skip-fno",
        ]
    )  # fmt: skip
    printed = json.loads(capsys.readouterr().out)
    assert code == 0 and printed["plan"]["pytorch"]["rebuilds_per_pod"] == 4
    assert digest == a40.hashlib.sha256(record_path.read_bytes()).hexdigest()
    assert a40.load_record(record_path) == RECORD
