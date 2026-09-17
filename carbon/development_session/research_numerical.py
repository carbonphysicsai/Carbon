"""Metered invocation of the existing C-05 v3 derived-measurement owner."""

from __future__ import annotations

import json
from pathlib import Path

from .data import write_once
from .profile import canonical, digest
from .research_carrier import _run

PROGRAM = """
import importlib.util,json,sys
from pathlib import Path
root=Path('/input')
for name in ('carbon.measurement_runtime.development','carbon.measurement_runtime.development_controls','carbon.development_comparison.numerical_worker'):
    spec=importlib.util.spec_from_file_location(name,root/(name+'.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
from carbon.development_comparison.numerical_worker import execute
result=execute(json.loads((root/'bundle.json').read_bytes()))
Path('/scratch/output/derived-measurements.json').write_text(json.dumps(result,allow_nan=False,separators=(',',':')))
"""


class CampaignDerivedMeasurements:
    def __init__(self, *, ledger, owner):
        self.ledger, self.owner = ledger, owner

    def run(self, root, bundle, image):
        if not root.resolve().is_relative_to(self.ledger.root.resolve()):
            raise ValueError("comparison outside campaign accounting")
        if bundle.get("kind") != "remeasure" or len(bundle.get("sources", [])) != 2:
            raise ValueError("complete paired derived measurement bundle required")
        cases = {
            row["request"]["case_digest"] for rows in bundle["sources"] for row in rows
        }
        if len(cases) != 24 or any(len(rows) != 72 for rows in bundle["sources"]):
            raise ValueError("complete shared 24-case three-replica bundle required")
        modules = (
            "carbon.measurement_runtime.development",
            "carbon.measurement_runtime.development_controls",
            "carbon.development_comparison.numerical_worker",
        )
        repo = Path(__file__).resolve().parents[2]
        files = {
            name + ".py": (repo / (name.replace(".", "/") + ".py")).read_bytes()
            for name in modules
        }
        files["bundle.json"] = canonical(bundle)
        identity = (
            "final-derived-"
            + digest(canonical([str(root), digest(files["bundle.json"])]))[7:]
        )
        worker = _run(
            self.ledger,
            owner=self.owner,
            identity=identity,
            source=PROGRAM,
            files=files,
            image=image,
            seconds=600,
            provenance="EVALUATOR_C05_V3_DERIVED_MEASUREMENT",
            phase="final",
            extra_resources={
                "reference_invocations": 2 * len(cases),
                "reference_trajectories": 2 * len(cases),
            },
        )
        snapshot = self.ledger.root / worker["operation"] / "snapshot"
        body = (snapshot / "derived-measurements.json").read_bytes()
        if digest(body) != worker["files"]["derived-measurements.json"]:
            raise ValueError("derived measurement output changed")
        output = json.loads(body)
        if set(output["reference_checks"]) != cases:
            raise ValueError("incomplete reference refinement checks")
        operation = root / "derived-measurements"
        (operation / "input").mkdir(parents=True, exist_ok=True, mode=0o700)
        write_once(operation / "input/bundle.json", files["bundle.json"])
        write_once(operation / "output.json", body)
        write_once(
            operation / "resources.json",
            canonical(
                {
                    "output_digest": digest(body),
                    "campaign_operation": identity,
                    "reference_solver_invocations": 2 * len(cases),
                    "worker": worker,
                    "qualification": False,
                }
            ),
        )
        return output
