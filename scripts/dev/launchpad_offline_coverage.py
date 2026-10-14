"""PLT-29: measure bounded construction and local toolbox calls without execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from carbon import research
from carbon.agent_campaign.attack.adapters import battery_level1
from carbon.battery import pools
from carbon.battery.challenge import CHALLENGE
from carbon.battery.research import make_battery_research_service
from carbon.development_session.research_ledger import CampaignLedger
from carbon.reconstruction import development_composition as dc

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = "docs/development/launchpad/offline_coverage"
OPERATIONS = (
    "dry_validate",
    "compile_strategy",
    "inspect_resources",
    "forecast_resources",
)
SOURCE_PATHS = (
    "carbon/reconstruction/development_composition.py",
    "carbon/reconstruction/development_compositions/battery-construction-v1.json",
    "carbon/reconstruction/development_compositions/registry.json",
    "carbon/reconstruction/development_variants.py",
    "carbon/reconstruction/development_variant_policies/registry.json",
    "carbon/battery/research.py",
    "carbon/battery/compile.py",
    "carbon/battery/contracts.py",
    "carbon/development_session/research_service.py",
    "carbon/development_session/research_resources.py",
    "carbon/development_session/construction_level.py",
    "carbon/research/service.py",
    "carbon/research/model.py",
    "scripts/dev/launchpad_offline_coverage.py",
)


def no_execution(*args, **kwargs):
    raise RuntimeError("offline coverage never dispatches execution")


def strategies():
    """One bounded public fixture per change; two same-level combinations."""
    (pool,) = pools.registered()
    parts = {
        "loss": {battery_level1.FIELD: battery_level1.VALID["valid_robust_l2"]},
        "spectral": {"muon_spectral": True},
        "pool": {
            "pool_selection": {
                "pool_version": pool,
                "strata": {"train": 1.0},
                "box": {"t_amb_c": [10.0, 35.0]},
                "cases": 120,
            }
        },
        "numerics": {"quasi_newton_family": "bfgs"},
        "search": {"line_search": "backtracking"},
        # This is a refusal control, not a verified staged graph.
        "graph": {"composition_graphs": "sha256:" + "0" * 64},
    }
    cases = {
        "C0": (),
        "C1": ("loss",),
        "C2a": ("spectral",),
        "C2b": ("pool",),
        "C3a": ("numerics",),
        "C3b": ("numerics", "search"),
        "C4": ("graph",),
        "X1_pool": ("spectral", "pool"),
        "X1_search": ("numerics", "search"),
        "X2": ("loss", "spectral"),
        "X3": ("loss", "spectral", "pool", "numerics", "search", "graph"),
    }
    made = {}
    for name, names in cases.items():
        parameters = {
            "width": 16,
            "depth": 1,
            "steps": 48,
            "polish_steps": 6,
            "optimizer_family": "muon",
        }
        for item in names:
            parameters.update(parts[item])
        made[name] = {
            "schema_version": "1.0",
            "challenge_id": CHALLENGE.challenge_id,
            "backbone": "mlp",
            "parameters": parameters,
        }
    return made


def command(case, operation):
    return f"python -m scripts.dev.launchpad_offline_coverage --case {case} --operation {operation}"


def summarize(reply):
    """Report protocol evidence, without interpreting empty forecasts as passes."""
    result = reply.result
    value = {"reply_status": reply.status.value, "result_type": type(result).__name__}
    if reply.status is research.ReplyStatus.ERROR:
        value["status"] = "ERROR"
        value["code"] = result.code.value
        return value
    if type(result) is research.DryValidationResult:
        value["status"] = "ACCEPTED" if result.valid else "REFUSED"
    elif type(result) is research.CompileStrategyResult:
        value["status"] = "ACCEPTED" if result.accepted else "REFUSED"
    else:
        value["status"] = "RETURNED"
        value["line_item_count"] = len(result.line_items)
        value["limitations"] = list(result.limitations)
        if type(result) is research.ResourceForecast:
            value["wall_seconds_band"] = list(result.total_wall_seconds_band)
    if hasattr(result, "issues"):
        value["issues"] = [
            {"code": issue.code, "path": list(issue.path)} for issue in result.issues
        ]
    return value


def measure(case, operation):
    strategy = strategies()[case]
    if operation == "construction":
        with tempfile.TemporaryDirectory(
            prefix="carbon-offline-strategy-"
        ) as directory:
            path = Path(directory) / "strategy.json"
            path.write_text(json.dumps(strategy), encoding="utf-8", newline="\n")
            done = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "carbon.reconstruction.development_composition",
                    str(path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if done.returncode not in {0, 2}:
                raise RuntimeError(
                    "construction CLI did not return a typed compile answer"
                )
            answer = json.loads(done.stdout)
            expected = 0 if answer["status"] == "ACCEPTED" else 2
            if done.returncode != expected:
                raise RuntimeError("construction CLI exit/status disagree")
            return {
                **answer,
                "cli_exit_code": done.returncode,
                "execution": "STATIC_COMPILE_ONLY",
            }
    with tempfile.TemporaryDirectory(prefix="carbon-offline-coverage-") as directory:
        root = Path(directory)
        ledger = CampaignLedger(root / "ledger")
        service = make_battery_research_service(
            root=root / "tasks",
            ledger=ledger,
            owner="offline-coverage-fixture",
            image=SimpleNamespace(),
            practice=no_execution,
            material=no_execution,
        )
        try:
            requests = {
                "dry_validate": research.DryValidateRequest(CHALLENGE, strategy),
                "compile_strategy": research.CompileStrategyRequest(
                    CHALLENGE, strategy, service.contracts.assembly.training_support_ref
                ),
                "inspect_resources": research.InspectResourcesRequest(
                    CHALLENGE, strategy, service.inspection.policy_ref
                ),
                "forecast_resources": research.ForecastResourcesRequest(
                    CHALLENGE, strategy, service.inspection.policy_ref, 600
                ),
            }
            reply = service.service.call(
                research.ServiceCall(
                    research.RESEARCH_NAMESPACE, operation, requests[operation]
                )
            )
            result = summarize(reply)
            used = ledger.status(owner="offline-coverage-fixture")["used"]
            if any(used.values()):
                raise RuntimeError("offline coverage consumed execution allowance")
            return {
                **result,
                "execution": "LOCAL_SERVICE_CALL_ONLY",
                "execution_allowance_used": used,
            }
        finally:
            service.tasks.close()


def report():
    cases = strategies()
    rows = []
    for case in cases:
        for operation in ("construction", *OPERATIONS):
            rows.append(
                {
                    "case": case,
                    "operation": operation,
                    "ran": True,
                    "command": command(case, operation),
                    "observation": measure(case, operation),
                    "scope": (
                        "UNVERIFIED_GRAPH_METADATA_ONLY"
                        if case in {"C4", "X3"}
                        else "REPRESENTATIVE_OFFLINE_FIXTURE"
                    ),
                }
            )
    composition = dc.load(CHALLENGE.challenge_id)
    return {
        "schema": "carbon.launchpad.offline-coverage.v1",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_files": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in SOURCE_PATHS
        },
        "construction": {"version": composition.version, "digest": composition.digest},
        "strategies": cases,
        "measurements": rows,
        "basis": {
            "declared_strategy_cases": len(cases),
            "actual_calls": len(rows),
            "training_runs": 0,
            "host_runs": 0,
        },
        "unrun_matrix": [
            {
                "change": change,
                "capability": f"B{capability}",
                "ran": False,
                "outcome": "HOST_BOUND",
                "reason": "real Launchpad/host path excluded; local service calls are not door acceptance",
            }
            for change in (
                "C0",
                "C1",
                "C2a",
                "C2b",
                "C3a",
                "C3b",
                "C4",
                "X1",
                "X2",
                "X3",
            )
            for capability in range(1, 26)
            if capability != 11
        ],
        "b18": {
            "live_serving": "HOST_BOUND_UNVERIFIED",
            "observed_local_service": "base compiler",
            "variant_door": "requires target served_contracts exact digest",
            "distinction": "compiled construction capability does not establish deployed intake serving",
        },
        "maturity": "DEVELOPMENT_STATIC_ENGINEERING_EVIDENCE_ONLY",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=tuple(strategies()))
    parser.add_argument("--operation", choices=("construction", *OPERATIONS))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if bool(args.case) != bool(args.operation):
        parser.error("--case and --operation are supplied together")
    value = measure(args.case, args.operation) if args.case else report()
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
