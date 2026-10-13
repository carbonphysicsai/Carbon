"""D1-D6: public study evidence, with scoped refusals and historical pins.

No solver, training, model call or confirmation reference is read or run.
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import importlib
import json
import math
import tempfile
from collections.abc import Mapping
from pathlib import Path

from .model import FAIL, NOT_BUILT, PASS, REVIEW_REQUIRED, Result, digest, file_digest
from .runtime_checks import Invalid, _committed, _git, _object

LEVELS = (2, 3, 4)


def _record(ctx, item):
    registered = ctx.data.get("studies_by_level", {})
    if type(registered) is not dict:
        raise Invalid("study_registration_malformed")
    entries = registered.get(item, {})
    if type(entries) is not dict:
        raise Invalid("study_registration_malformed")
    record = entries.get(str(ctx.level))
    if record is None:
        return None
    if (
        type(record) is not dict
        or record.get("challenge") != ctx.challenge
        or record.get("levels") != list(LEVELS)
        or ctx.level not in record["levels"]
        or type(record.get("basis")) is not str
        or not record["basis"].strip()
    ):
        raise Invalid("study_registration_scope_mismatch")
    return record


def _path(ctx, name):
    if type(name) is not str or not name or "\\" in name or ":" in name:
        raise Invalid("study_path_invalid")
    path = Path(name)
    target = ctx.repository / path
    if (
        path.is_absolute()
        or ".." in path.parts
        or target.is_symlink()
        or ctx.repository.resolve() not in target.resolve().parents
    ):
        raise Invalid("study_path_invalid")
    return target


def _bytes(ctx, name, *, ref="HEAD"):
    target = _path(ctx, name)
    body = _git(ctx, "show", ref + ":" + name)
    if ref == "HEAD" and target.read_bytes() != body:
        raise Invalid("study_evidence_differs_from_HEAD")
    return body, "sha256:" + hashlib.sha256(body).hexdigest()


def _json(ctx, name, *, ref="HEAD"):
    body, sha = _bytes(ctx, name, ref=ref)
    value = json.loads(body, object_pairs_hook=_object)
    if type(value) is not dict:
        raise Invalid("study_evidence_not_object")
    return value, sha


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _absent(item):
    return Result(
        NOT_BUILT,
        f"owner: Data Collection; no {item} study evidence recorded for this level",
    )


def _review(ctx, record, item, binding):
    path = record.get("review")
    if path is None:
        return Result(
            REVIEW_REQUIRED,
            f"owner: Test Lead; no {item} review of the exact evidence at this level",
        )
    from .runner import REVIEW_SCHEMA, review_problem

    review, sha = _committed(ctx, path)
    if (
        review.get("schema") != REVIEW_SCHEMA
        or review_problem(review, ctx.challenge, ctx.level, item)
        or review.get("reviewer") != "Test Lead"
        or review.get("binding") != binding
    ):
        raise Invalid("study_review_scope_or_digest_mismatch")
    return Result(review["decision"], f"committed Test Lead {item} review", (sha,))


def frozen_study(item, ctx):
    try:
        record = _record(ctx, "D1")
        if record is None:
            return _absent("D1")
        manifest, sha = _json(ctx, record["manifest"])
        contract, contract_sha = _json(ctx, record["contract"])
        if manifest.get("contract_digest") != digest(contract):
            raise Invalid("freeze_contract_digest_mismatch")
        candidates = manifest.get("candidates")
        if (
            type(candidates) is not list
            or not candidates
            or any(
                type(c) is not dict or not isinstance(c.get("id"), str)
                for c in candidates
            )
            or len({c["id"] for c in candidates}) != len(candidates)
        ):
            raise Invalid("freeze_comparator_not_finite_and_unique")
        groups = manifest.get("groups")
        if (
            type(groups) is not list
            or not groups
            or any(
                type(g) is not dict or not g.get("name") or not g.get("cases")
                for g in groups
            )
            or not {"REPRESENTATIVE", "BOUNDARY_STRESS"}.issubset(
                {g.get("role") for g in groups}
            )
        ):
            return Result(
                FAIL,
                "freeze does not label representative and boundary populations; a boundary control is not a population",
                (sha, contract_sha),
            )
        access_path = record.get("reference_access")
        if access_path is None:
            return Result(
                FAIL,
                "no recorded first-reference-access timestamp; commit time cannot replace it",
                (sha, contract_sha),
            )
        access, access_sha = _json(ctx, access_path)
        frozen, first = manifest.get("frozen_unix"), access.get("first_access_unix")
        if (
            access.get("challenge") != ctx.challenge
            or not _finite(frozen)
            or not _finite(first)
            or first <= frozen
        ):
            raise Invalid("freeze_does_not_precede_reference_access")
        _, reference_sha = _bytes(ctx, record["references"])
        if access.get("reference_digest") != reference_sha:
            raise Invalid("reference_access_digest_mismatch")
        return Result(
            PASS,
            "finite comparator, contract pin, populations and pre-access freeze verified",
            (sha, contract_sha, access_sha, reference_sha),
        )
    except (Invalid, OSError, ValueError, KeyError, TypeError) as error:
        return Result(FAIL, str(error))


def harness_adapter(item, ctx):
    try:
        record = _record(ctx, "D2")
        if record is None:
            return _absent("D2")
        from carbon.design_search import experiment, track_b

        module_name, separator, symbol = record["adapter"].partition(":")
        if not separator:
            raise Invalid("search_adapter_registration_invalid")
        module = importlib.import_module(module_name)
        adapter = getattr(module, symbol)()
        if (
            type(adapter) is not experiment.SearchAdapter
            or adapter.challenge != ctx.challenge
        ):
            raise Invalid("search_adapter_challenge_mismatch")
        from .checks import run_tests

        tested = run_tests(ctx, record["tests"], strict=True)
        if tested.status != PASS:
            return tested
        ladder = list(track_b.DEFAULT_LADDER)
        reviewed = _review(ctx, record, "D2", {"ladder_digest": digest(ladder)})
        return Result(
            reviewed.status,
            reviewed.detail,
            (
                file_digest(module.__file__),
                {"ladder_digest": digest(ladder)},
                *tested.evidence,
                *reviewed.evidence,
            ),
        )
    except (
        Invalid,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ImportError,
    ) as error:
        return Result(FAIL, str(error))


def counted_timing(item, ctx):
    try:
        record = _record(ctx, "D3")
        if record is None:
            return _absent("D3")
        locator = record.get("registry")
        if locator is None:
            return Result(
                NOT_BUILT,
                "owner: Data Collection; authoritative counted-plan code registry locator is not recorded; the earlier review alone cannot prove absence",
            )
        module_name, separator, symbol = locator.partition(":")
        if not separator:
            raise Invalid("counted_plan_registry_locator_invalid")
        module = importlib.import_module(module_name)
        registry = getattr(module, symbol)
        if not isinstance(registry, Mapping):
            raise Invalid("counted_plan_registry_not_mapping")
        plans = registry.get(ctx.challenge)
        if type(plans) not in (list, tuple):
            raise Invalid("counted_plan_registry_has_no_challenge_entry")
        evidence = (file_digest(module.__file__),)
        if not plans:
            declaration, sha = _json(ctx, record["not_applicable"])
            review, review_sha = _json(ctx, declaration["basis_review"])
            if (
                declaration.get("challenge") != ctx.challenge
                or declaration.get("levels") != list(LEVELS)
                or declaration.get("basis_review_digest") != review_sha
                or review.get("challenge") != ctx.challenge
                or review.get("item") != "D3"
                or review.get("reviewer") != "Test Lead"
                or review.get("decision") != PASS
                or review.get("level") != [0, 1]
                or "no counted plan" not in review.get("notes", "")
            ):
                raise Invalid("counted_plan_absence_declaration_mismatch")
            return Result(
                PASS,
                "not applicable: declared absence confirmed by the current code registry; a new plan reopens timing",
                (*evidence, sha, review_sha),
            )
        timing_path = record.get("timing")
        if timing_path is None:
            return Result(
                NOT_BUILT,
                "owner: Data Collection; counted plan registered without timing calibration",
                evidence,
            )
        timing, sha = _json(ctx, timing_path)
        p95 = timing.get("p95_seconds")
        if (
            timing.get("challenge") != ctx.challenge
            or not timing.get("host")
            or type(timing.get("n")) is not int
            or timing["n"] <= 0
            or not _finite(p95)
            or p95 <= 0
        ):
            raise Invalid("timing_calibration_malformed")
        for path in plans:
            plan, plan_sha = _json(ctx, path)
            timeout = plan.get("timeout_s")
            if (
                plan.get("challenge") != ctx.challenge
                or plan.get("host") != timing["host"]
                or not _finite(timeout)
                or timeout < 2 * p95
            ):
                raise Invalid("counted_plan_timeout_below_two_p95_or_wrong_host")
            evidence += (plan_sha,)
        return Result(
            PASS,
            "every registered counted plan has host-bound calibration and timeout >= 2*p95",
            (*evidence, sha),
        )
    except (
        Invalid,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ImportError,
    ) as error:
        return Result(FAIL, str(error))


def _references(ctx, record):
    body, archive_sha = _bytes(ctx, record["references"])
    plain = gzip.decompress(body) if record["references"].endswith(".gz") else body
    payload_sha = "sha256:" + hashlib.sha256(plain).hexdigest()
    checksum, checksum_sha = _bytes(ctx, record["checksum"])
    expected = checksum.decode().split()[0]
    if expected.removeprefix("sha256:") != payload_sha.removeprefix("sha256:"):
        raise Invalid("reference_payload_digest_mismatch")
    rows = [
        json.loads(line, object_pairs_hook=_object)
        for line in plain.decode().splitlines()
        if line.strip()
    ]
    if not rows or any(type(r) is not dict for r in rows):
        raise Invalid("reference_records_malformed")
    if any(
        r.get("fixture")
        or r.get("synthetic")
        or r.get("provenance") in ("SYNTHETIC", "ANALYTICAL_FIXTURE")
        for r in rows
    ):
        raise Invalid("fixture_reference_cannot_be_real_evidence")
    from .q1 import REAL_REFERENCE_KINDS

    if record.get("reference_provenance") not in REAL_REFERENCE_KINDS:
        raise Invalid("real_reference_provenance_unrecorded")
    return rows, plain, (archive_sha, payload_sha, checksum_sha)


def real_import(item, ctx):
    try:
        record = _record(ctx, "D4")
        if record is None:
            return _absent("D4")
        rows, plain, evidence = _references(ctx, record)
        manifest, manifest_sha = _json(ctx, record["manifest"])
        successful = [
            r
            for r in rows
            if r.get("status") == "OK"
            and r.get("outputs")
            and _finite(r.get("wall_s"))
            and r["wall_s"] > 0
        ]
        if not successful:
            raise Invalid("no_successful_real_output_with_wall_time")
        # The adapter is registered data; this implementation uses its existing
        # importer only, with no freeze, reconstruction, solver or scoring call.
        module_name, separator, symbol = record["importer"].partition(":")
        if not separator:
            raise Invalid("reference_importer_unregistered")
        factory = getattr(importlib.import_module(module_name), symbol)
        if not callable(factory):
            raise Invalid("reference_importer_not_supported")
        with tempfile.TemporaryDirectory(prefix="readiness-import-") as root:
            experiment = factory(Path(root), repository=ctx.repository)
            experiment.manifest_path.write_text(json.dumps(manifest))
            incoming = Path(root) / "incoming.jsonl"
            incoming.write_bytes(plain)
            imported = experiment.import_references(incoming)
            retained = experiment.reference_map()
        if imported.get("imported", 0) <= 0 or not any(
            r.get("case_id") in retained for r in successful
        ):
            raise Invalid("importer_retained_no_successful_real_record")
        return Result(
            PASS,
            "existing importer retained real solver output",
            (*evidence, manifest_sha, {"imported_records": imported["imported"]}),
        )
    except (Invalid, OSError, ValueError, KeyError, TypeError) as error:
        return Result(FAIL, str(error))


def reference_coverage(item, ctx):
    try:
        record = _record(ctx, "D5")
        if record is None:
            return _absent("D5")
        rows, _plain, evidence = _references(ctx, record)
        contract, contract_sha = _json(ctx, record["contract"])
        ev = importlib.import_module(record["contract_adapter"])
        decision = importlib.import_module(record["decision_adapter"])

        ev.validate(contract)
        candidates = ev.candidates(contract)
        references = {r["case_id"]: r for r in rows}
        if len(references) != len(rows):
            raise Invalid("reference_case_duplicate")
        scenarios = ev.scenarios(contract, split=record["split"])
        if not scenarios:
            raise Invalid("decision_set_empty")
        resolved = 0
        for scenario in scenarios:
            local = {
                (c["id"], i): references.get(ev.case_id(contract, scenario, c, i))
                for c in candidates
                for i in range(len(scenario["conditions"]))
            }
            verdicts = decision.assess_reference(contract, scenario, candidates, local)
            resolved += all(
                v["status"] in (decision.FEASIBLE, decision.INFEASIBLE)
                for v in verdicts.values()
            )
        report = {
            "challenge": ctx.challenge,
            "levels": list(LEVELS),
            "definition": "ALL_CANDIDATES_REFERENCE_DETERMINED",
            "resolved": resolved,
            "total": len(scenarios),
            "fraction": resolved / len(scenarios),
        }
        report_sha = digest(report)
        legacy, legacy_sha = _json(ctx, record["legacy_report"])
        policy_path = record["policy_record"]
        _, policy_sha = _bytes(ctx, policy_path)
        review_path = (
            "carbon/challenge_pipeline/readiness/" + ctx.challenge + "/reviews/D5.json"
        )
        if _path(ctx, review_path).is_file():
            from .runner import review_problem

            reviewed, review_sha = _json(ctx, review_path)
            if review_problem(reviewed, ctx.challenge, ctx.level, "D5") is None:
                if not any(
                    e.get("kind") == "decision"
                    and e.get("ref") == record["policy_decision"]
                    for e in reviewed["evidence"]
                ):
                    raise Invalid(
                        "reference_policy_review_does_not_name_registered_decision"
                    )
                evidence += (review_sha,)
        comparison = {
            "historical_panel_common_mask": legacy.get("mask"),
            "same_measure": False,
            "note": "panel common mask depends on member selections; no prior study is reinterpreted",
        }
        return Result(
            PASS,
            "reference-only coverage reported, not judged; per-level policy review remains separate",
            (
                *evidence,
                contract_sha,
                policy_sha,
                legacy_sha,
                report,
                {"coverage_report_digest": report_sha},
                comparison,
            ),
        )
    except (Invalid, OSError, ValueError, KeyError, TypeError) as error:
        return Result(FAIL, str(error))


def _import_closure(ctx, entry, ref):
    paths = set(
        _git(ctx, "ls-tree", "-r", "--name-only", ref, "--", "carbon", "scripts")
        .decode()
        .splitlines()
    )

    def files(name):
        base = name.replace(".", "/")
        result = {p for p in (base + ".py", base + "/__init__.py") if p in paths}
        parts = base.split("/")
        result.update(
            p
            for i in range(1, len(parts))
            if (p := "/".join(parts[:i]) + "/__init__.py") in paths
        )
        return result

    pending, visited = [entry], set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        if path not in paths:
            raise Invalid("analysis_entry_or_import_missing_at_freeze")
        visited.add(path)
        source, _sha = _bytes(ctx, path, ref=ref)
        package = path[:-3].split("/")
        package = package[:-1]
        for node in ast.walk(ast.parse(source)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
                for name in names:
                    if name.startswith(("carbon.", "scripts.")):
                        base = name.replace(".", "/")
                        if not {base + ".py", base + "/__init__.py"}.intersection(
                            paths
                        ):
                            raise Invalid("analysis_import_unavailable_at_freeze")
            elif isinstance(node, ast.ImportFrom):
                prefix = package[: len(package) - node.level + 1] if node.level else []
                base = ".".join([*prefix, *(node.module or "").split(".")]).strip(".")
                names = [
                    base,
                    *[base + "." + a.name for a in node.names if a.name != "*"],
                ]
            for name in names:
                if name.startswith(("carbon.", "scripts.")) or name in (
                    "carbon",
                    "scripts",
                ):
                    pending.extend(files(name) - visited)
    return visited


def analysis_pins(item, ctx):
    try:
        record = _record(ctx, "D6")
        if record is None:
            return _absent("D6")
        path = record.get("run_record")
        if path is None:
            return Result(
                NOT_BUILT,
                "owner: Data Collection; confirmation study has no recorded analysis pin",
            )
        pins, pins_sha = _json(ctx, path)
        if pins.get("schema") != record.get("pin_schema") or not record.get(
            "pin_schema"
        ):
            raise Invalid("analysis_pin_schema_mismatch")
        ref = record["freeze_commit"]
        if (
            type(ref) is not str
            or len(ref) != 40
            or any(c not in "0123456789abcdef" for c in ref)
        ):
            raise Invalid("freeze_commit_invalid")
        at_freeze, at_freeze_sha = _json(ctx, path, ref=ref)
        _git(ctx, "merge-base", "--is-ancestor", ref, "origin/main")
        if any(
            pins.get(key) != at_freeze.get(key)
            for key in (
                "schema",
                "study",
                "files",
                "trees",
                "freeze_manifest",
                "contract_digest",
            )
        ):
            raise Invalid("analysis_pin_changed_since_freeze")
        manifest_path = pins["freeze_manifest"]["path"]
        _, manifest_sha = _bytes(ctx, manifest_path, ref=ref)
        if pins["freeze_manifest"]["sha256"] != manifest_sha:
            raise Invalid("analysis_freeze_manifest_digest_mismatch")
        modules = _import_closure(ctx, record["analysis_entry"], ref)
        registered = pins.get("files")
        if type(registered) is not dict or not modules.issubset(registered):
            raise Invalid("analysis_import_missing_from_pin")
        for module in sorted(modules):
            _, sha = _bytes(ctx, module, ref=ref)
            if registered[module] != sha:
                raise Invalid("analysis_module_digest_drift_at_freeze")
        from .checks import run_tests

        tested = run_tests(ctx, record["tests"], strict=True)
        if tested.status != PASS:
            return tested
        return Result(
            PASS,
            "historical analysis import closure and every module pin verified",
            (
                pins_sha,
                at_freeze_sha,
                manifest_sha,
                {"freeze_commit": ref, "modules": len(modules)},
                *tested.evidence,
            ),
        )
    except (Invalid, OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        return Result(FAIL, str(error))
