"""Pinned public completed-menu producer. No model/solver/provider execution.

Run only under Root's actual TEST lease. The preflight route reads reference
support only; replay commits real model quantities before any truth reader.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

from carbon.battery import calibration, exam
from carbon.battery.value import contract as ct
from carbon.battery.value import decision, panel

from . import candidates, completed_menu, public_v2_reference
from .core import LabRefused

ROOT = Path(__file__).resolve().parents[3]
REGISTRATION = (
    ROOT / "Business/research/score-lab-campaign-01/completed-menu-research-v2"
)
PROTOCOL = "NEW_COVERED_COMPLETED_MENU_RESEARCH_V2_PROTOCOL.json"
BINDINGS = "NEW_COVERED_COMPLETED_MENU_RESEARCH_V2_SOURCE_BINDINGS.json"
PROTOCOL_SHA = "ebe45085d2dd5a7f89ff9bf243ff00551e69a972959b8d24e46659ef2c9427bb"
BINDINGS_SHA = "c6249c49f12360f10322aec6246b2991591e1e725bb33b7521772e02d8b1e532"
READERS_SHA = "4d0c046ec6be2cef6f82f21711ddf45d6f8cb18270d2f0f4ee0af0ff3cc44f58"


def pinned(path, expected):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise LabRefused("completed_menu_input_digest")
    return raw


def contained(root, relative):
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root.resolve(strict=True)):
        raise LabRefused("completed_menu_input_root")
    return path


def write_new(path, document):
    raw = (json.dumps(document, sort_keys=True, allow_nan=False) + "\n").encode()
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def frozen_readers():
    path = REGISTRATION / "frozen-public-readers.py.txt"
    raw = pinned(path, READERS_SHA)
    loader = candidates._PinnedSourceLoader("completed_menu_frozen_readers", path, raw)
    spec = importlib.util.spec_from_file_location(loader.name, path, loader=loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    # Deliberately expose only the already-reviewed allow-listed readers.
    # The incompatible old main/385/122 experiment is not an entrypoint here.
    return SimpleNamespace(
        predictions=module.predictions,
        reference_rows=module.reference_rows,
        v2_rows=module.v2_rows,
    )


def native_menus(protocol, contract):
    """Join exact native case IDs; a prefix or row number is not an identity."""
    scenarios = {s["id"]: s for s in ct.scenarios(contract, "development")}
    native_candidates = {c["id"]: c for c in ct.candidates(contract)}
    action_of, question_candidates = {}, {}
    for q in protocol["questions"]:
        if q["native_context_id"] not in scenarios:
            raise LabRefused("completed_menu_native_public_D_role")
        scenario = scenarios[q["native_context_id"]]
        expected = {
            ct.case_id(contract, scenario, c, 0): c["id"]
            for c in native_candidates.values()
        }
        if len(scenario["conditions"]) != 1 or not set(q["case_ids"]) <= set(expected):
            raise LabRefused("completed_menu_exact_native_case_join")
        action_of.update({cid: expected[cid] for cid in q["case_ids"]})
        question_candidates[q["question_id"]] = [
            native_candidates[expected[cid]] for cid in q["case_ids"]
        ]
    completed_menu.manifest(protocol, action_of)
    return scenarios, action_of, question_candidates


def cohort_partition(inventory, cohorts):
    records = {r["public_member_id"]: r for r in inventory["records"]}
    if len(records) != 137 or len(inventory["records"]) != 137:
        raise LabRefused("completed_menu_raw_cohort")
    primary, other = cohorts["primary_ev4_cpu_100"], cohorts["other_raw_37"]
    if (
        len(primary) != 100
        or len(other) != 37
        or set(primary) & set(other)
        or set(primary + other) != set(records)
    ):
        raise LabRefused("completed_menu_cohort_partition")
    groups = {m: r["dependence_group_RESEARCH_V1"] for m, r in records.items()}
    if any(type(g) is not str or not g for g in groups.values()):
        raise LabRefused("completed_menu_group_identity")
    return records, groups


def completed_library_labels(labels, wanted):
    for cid in wanted:
        row = labels.get(cid)
        if row is not None and (
            row.get("case_id") != cid
            or row.get("source") != "ev4"
            or row.get("rule") != "m160-d3-r1"
        ):
            raise LabRefused("completed_menu_completed_library_source_rule")


def bound_module_origins(root, selected, modules=None):
    """On-disk pins alone do not identify preloaded helper module objects."""
    modules = sys.modules if modules is None else modules
    origins = {}
    for relative in selected:
        if not relative.endswith(".py"):
            continue
        name = relative[:-3].replace("/", ".")
        module = modules.get(name)
        origin = getattr(module, "__file__", None)
        if origin is None or Path(origin).resolve() != (root / relative).resolve():
            raise LabRefused("completed_menu_loaded_module_origin:" + name)
        origins[name] = str(Path(origin).resolve())
    used = [
        calibration,
        exam,
        ct,
        decision,
        panel,
        public_v2_reference,
        candidates,
        completed_menu.bank,
        completed_menu.owner_dev_v1,
        completed_menu.public_v2_replay,
        completed_menu.score_proof,
    ]
    if any(modules.get(module.__name__) is not module for module in used):
        raise LabRefused("completed_menu_loaded_module_object")
    return origins


class PublicInputs:
    """Exact public registration and artifacts; no caller-supplied rule code."""

    def __init__(self, packet, public):
        self.packet, self.public = Path(packet).resolve(), Path(public).resolve()
        self.protocol = json.loads(pinned(REGISTRATION / PROTOCOL, PROTOCOL_SHA))
        self.bindings = json.loads(pinned(REGISTRATION / BINDINGS, BINDINGS_SHA))
        for relative, digest in self.bindings["selected_source_files_sha256"].items():
            pinned(contained(ROOT, relative), digest)
        origins = bound_module_origins(
            ROOT, self.bindings["selected_source_files_sha256"]
        )
        local = self.protocol["binding_closure"]["packet_files_sha256"]
        for name, digest in local.items():
            pinned(contained(self.packet, name), digest)
        self.inventory = json.loads(
            pinned(self.packet / "MODEL_INVENTORY.json", local["MODEL_INVENTORY.json"])
        )
        self.cohorts = json.loads(
            pinned(
                self.packet / "ANALYSIS_COHORTS_RESEARCH_V1.json",
                local["ANALYSIS_COHORTS_RESEARCH_V1.json"],
            )
        )["cohorts"]
        self.contract = json.loads(
            pinned(
                ROOT / self.protocol["binding_closure"]["native_contract"]["path"],
                self.protocol["binding_closure"]["native_contract"]["sha256"],
            )
        )
        self.readers = frozen_readers()
        self.scenarios, self.action_of, self.question_candidates = native_menus(
            self.protocol, self.contract
        )
        self.records, self.groups = cohort_partition(self.inventory, self.cohorts)
        self.rules, self.rule_digest = candidates.load()
        self.identity = {
            "protocol_sha256": PROTOCOL_SHA,
            "source_bindings_sha256": BINDINGS_SHA,
            "consumer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "mapping_sha256": hashlib.sha256(
                Path(completed_menu.__file__).read_bytes()
            ).hexdigest(),
            "candidate_sha256": self.rule_digest,
            "lexical_reader_sha256": READERS_SHA,
            "loaded_selected_module_origins": origins,
        }

    def models(self):
        raw_models, quantities, invalid = {}, {}, {}
        wanted = set(self.action_of)
        for member, record in self.records.items():
            relative = (
                Path(record["manifest_folder"])
                / PureWindowsPath(record["public_source_file"]).name
            )
            source = contained(self.public, relative)
            raw = self.readers.predictions(
                source, record["compressed_sha256"], wanted, member
            )
            if set(raw) != wanted:
                invalid[member] = "PREDICTION_ARTIFACT_CASE_COVERAGE_UNKNOWN"
                continue
            if any(not exam._finite_shape(p, calibration.SHAPES) for p in raw.values()):
                invalid[member] = "INVALID_OR_NONFINITE_PREDICTIONS"
                continue
            quantities[member] = {
                cid: decision.measure(self.contract, p) for cid, p in raw.items()
            }
            raw_models[member] = raw
        self.raw_models = raw_models
        self.quantities = quantities
        return {
            "schema": "carbon.scorelab.completed-menu.prediction-commitment.v2",
            "scope": "PUBLIC_DEVELOPMENT_DIAGNOSTIC_ONLY",
            "identity": self.identity,
            "case_ids": sorted(wanted),
            "real_members": sorted(self.records),
            "quantities": quantities,
            "invalid_or_unavailable_members": invalid,
            "constructed_controls_included": False,
            "references_opened": False,
            "chronology": "producer ordering, not independent remote timestamp attestation",
        }

    def truth(self):
        wanted = set(self.action_of)
        refs = self.readers.reference_rows(
            contained(self.public, "ev4-decision-references.jsonl"), wanted
        )
        labels = self.readers.v2_rows(
            ROOT / self.protocol["source_binding"]["sealed_v2_path"], wanted
        )
        completed_library_labels(labels, wanted)
        assessed, coverage = {}, {}
        for cid in wanted:
            assessed[cid] = public_v2_reference.assess_condition(
                self.contract, cid, refs.get(cid), labels
            )
            if refs.get(cid, {}).get("status") == "OK":
                margin = decision.measure(self.contract, refs[cid]["outputs"])[
                    "plating_margin_v"
                ]
                coverage[cid] = {
                    "m20_mv": None if margin is None else margin * 1000,
                    "sealed_v2": labels.get(cid),
                }
        questions, receipt = completed_menu.reference_questions(
            self.protocol, self.action_of, assessed, coverage
        )
        self.refs = refs
        return questions, receipt

    def _predictions(self, quantities):
        result = {}
        for q in self.protocol["questions"]:
            qid = q["question_id"]
            result[qid] = decision.assess_predicted(
                self.contract,
                self.scenarios[q["native_context_id"]],
                self.question_candidates[qid],
                {(self.action_of[cid], 0): quantities[cid] for cid in q["case_ids"]},
            )
        return result

    def analyze(self, questions, receipt):
        _, scales = calibration.frozen_calibration(ROOT)
        raw = dict(self.raw_models)
        quantities = dict(self.quantities)
        controls = []
        for kind in panel.CONTROLS:
            member = "control-" + kind
            if member in self.records:
                raise LabRefused("completed_menu_control_raw_identity_collision")
            controls.append(member)
            raw[member] = panel.control_predictions(kind, self.refs)
            quantities[member] = {
                cid: decision.measure(self.contract, p)
                for cid, p in raw[member].items()
            }
        predictions = {m: self._predictions(q) for m, q in quantities.items()}
        errors = {}
        for m, outputs in raw.items():
            case_errors = {
                cid: exam.case_error(
                    exam.case_components(outputs[cid], self.refs[cid], scales)
                )
                for q in self.protocol["questions"]
                if questions[q["question_id"]]["class"] == "SCORED"
                for cid in q["case_ids"]
            }
            errors[m] = completed_menu.question_errors(case_errors, self.protocol)
        rule_ids = self.protocol["analysis_knobs"]["predeclared_active_diagnostics"]
        rules = {rid: self.rules[rid]["rule"] for rid in rule_ids}
        cohorts = {"all_raw_137": list(self.records), **self.cohorts}
        reports = {}
        for name, members in cohorts.items():
            matched = [m for m in members if m in self.raw_models]
            reports[name] = {
                "declared_members": len(members),
                "missing_members": sorted(set(members) - set(matched)),
                "orientations": {
                    side: completed_menu.orientation(
                        self.protocol,
                        questions,
                        predictions,
                        errors,
                        self.groups,
                        members,
                        controls,
                        rules,
                        leg_fold=side,
                    )
                    for side in ("A", "B")
                },
            }
        return {
            "first_line": self.protocol["first_line"],
            "scope": "PUBLIC_CONDITIONAL_DIAGNOSTIC",
            "identity": self.identity,
            "reference_admission": receipt,
            "menus_and_anchors": self.protocol["questions"],
            "P": self.protocol["P"],
            "Q": self.protocol["Q"],
            "w": self.protocol["w"],
            "cohorts": reports,
            "controls": controls,
            "control_basis": "original public references; a truth control is not a fine-reference oracle",
            "full_rule_adoption": "UNAVAILABLE_NO_REGISTERED_PER_CASE_FORMS_OR_GUARD_RECEIPTS",
            "independent_families_claimed": False,
            "new_solver_runs": 0,
            "new_inference": 0,
            "qualification": False,
        }


def replay(inputs, out):
    """The actual producer sequence; fixtures instrument these same calls."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    commitment = inputs.models()
    digest = write_new(out / "prediction-commitment.json", commitment)
    # No truth callback may move before the completed/closed write above.
    questions, receipt = inputs.truth()
    write_new(out / "reference-admission.json", receipt)
    result = inputs.analyze(questions, receipt)
    result["prediction_commitment_sha256"] = digest
    write_new(out / "readout.json", result)
    return result


def preflight(inputs, out):
    """Reference-only route: no predictions, scores, candidate selection or tau."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    _, receipt = inputs.truth()
    result = {
        "first_line": receipt.get("first_line"),
        "scope": "REFERENCE_PREFLIGHT_ONLY_NOT_MODEL_EVIDENCE",
        "identity": inputs.identity,
        "reference_admission": receipt,
        "prediction_coverage_checked": False,
        "qualification": False,
    }
    write_new(out / "reference-preflight.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "replay"))
    parser.add_argument("--packet-root", type=Path, required=True)
    parser.add_argument("--public-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise LabRefused(
            "completed_menu_Root_TEST_requires_isolated_no_site_no_bytecode"
        )
    inputs = PublicInputs(args.packet_root, args.public_dir)
    result = (preflight if args.mode == "preflight" else replay)(inputs, args.out)
    print(result["first_line"])
    print(
        json.dumps(
            {"scope": result["scope"], "qualification": False, "out": str(args.out)}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
