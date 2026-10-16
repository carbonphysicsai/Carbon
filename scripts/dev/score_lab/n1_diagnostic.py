"""Run the existing N1 DEVELOPMENT diagnostic on an explicitly pinned public bundle.

No fitting, acquisition, optimizer replay, private-role loader or new score rule.
Root supplies compatible producer evidence inputs and original commitments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath

from carbon.design_search import tasks
from carbon.development_comparison import carbon_arm
from scripts.dev.score_lab import owner_v3_n1 as diagnostic
from scripts.dev.score_lab import owner_v3_panel_export as producer

SCHEMA = "carbon.scorelab.n1-diagnostic-run.v1"
GUARDED_SCHEMA = "carbon.scorelab.n1-diagnostic-run.guard419.v1"
SCOPES = ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")


class Refused(ValueError):
    """Stable developer refusal code; never echo source values or paths."""


def _require(condition, code):
    if not condition:
        raise Refused(code)


def _hex(value):
    _require(type(value) is str, "INVALID_SHA256")
    value = value.removeprefix("sha256:")
    _require(re.fullmatch(r"[0-9a-f]{64}", value) is not None, "INVALID_SHA256")
    return value


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise Refused("INVALID_JSON") from exc


def _object(value, code):
    _require(type(value) is dict, code)
    return value


def _relative(root, name):
    _require(type(name) is str and bool(name), "INVALID_INPUT_PATH")
    parts = PurePosixPath(name)
    _require(
        not parts.is_absolute()
        and "\\" not in name
        and ":" not in name
        and parts.as_posix() == name
        and all(p not in (".", "..") for p in parts.parts),
        "INVALID_INPUT_PATH",
    )
    path = root
    for part in parts.parts:
        path = path / part
        try:
            info = path.lstat()
        except OSError as exc:
            raise Refused("INPUT_UNAVAILABLE") from exc
        _require(
            not stat.S_ISLNK(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400,
            "LINKED_INPUT_REFUSED",
        )
    _require(
        path.is_file() and path.resolve().is_relative_to(root), "INVALID_INPUT_PATH"
    )
    return path


class _Files:
    """Lazy allow-listed file reader; no glob, discovery or payload-selected code."""

    def __init__(self, root, specs):
        self.root, self.specs = root, specs

    def __getitem__(self, key):
        return _relative(self.root, self.specs[key]["path"]).read_bytes()


def _draws(value, population, *, context=None):
    _require(type(value) is list and bool(value), "DRAW_ROSTER_REQUIRED")
    ids = set()
    for draw in value:
        _require(
            type(draw) is dict
            and draw.get("population") == population
            and draw.get("role") in ("LEG", "VALUE")
            and type(draw.get("outer_weight")) in (int, float)
            and draw["outer_weight"] == 1,
            "DRAW_ROLE_OR_POPULATION_DIFFERS",
        )
        task = _object(draw.get("task"), "QUESTION_OBJECT_REQUIRED")
        if context is not None:
            from scripts.dev.score_lab import owner_v3

            owner_v3._validate(task, context=context)
        qid = task.get("task_digest")
        _require(type(qid) is str and qid not in ids, "QUESTION_IDENTITY_DIFFERS")
        ids.add(qid)
    _require({d["role"] for d in value} == {"LEG", "VALUE"}, "BOTH_ROLES_REQUIRED")
    return value


def _panels(draw, physical):
    return [
        {
            "index_value": index["index_value"],
            "values": {
                (candidate, condition["id"]): physical[key]
                for candidate in index["task"]["candidates"]
                for condition in index["task"]["conditions"]
                if (key := (index["index_value"], candidate, condition["id"]))
                in physical
            },
        }
        for index in draw["task"]["indices"]
    ]


def _member(spec, load, draws, view_digest, scope):
    prediction = _object(_json(load(spec["predictions"])), "PREDICTION_OBJECT_REQUIRED")
    fit = _object(_json(load(spec["fit_receipt"])), "FIT_OBJECT_REQUIRED")
    receipt = _object(
        _json(load(spec["commitment_receipt"])), "RECEIPT_OBJECT_REQUIRED"
    )
    train = _object(fit.get("train"), "FIT_TRAIN_OBJECT_REQUIRED")
    code = _object(fit.get("code"), "FIT_CODE_OBJECT_REQUIRED")
    actual_source = _object(code.get("actual_source"), "FIT_SOURCE_OBJECT_REQUIRED")
    raw = load(spec["commitments"])
    _require(
        prediction.get("schema") == carbon_arm.PREDICTIONS
        and fit.get("schema") == carbon_arm.RECEIPT
        and prediction.get("model_id") == fit.get("model_id") == spec["id"]
        and prediction.get("scope") == fit.get("scope") == receipt.get("scope") == scope
        and prediction.get("export_digest") == fit.get("export_digest") == view_digest
        and prediction.get("source_receipt_digest")
        == "sha256:" + _sha(carbon_arm.canonical(fit))
        and fit.get("kit") == spec["kit"]
        and train.get("sha256") == "sha256:" + _hex(spec["train_sha256"])
        and train.get("fixture") is (scope == "SYNTHETIC_FIXTURE")
        and actual_source.get("commit") == spec["fit_source"],
        "PREDICTION_FIT_CONTEXT_DIFFERS",
    )
    _require(
        receipt.get("model_id") == spec["id"]
        and receipt.get("references_joined") is False
        and receipt.get("sealed_holdout_read") is False
        and _hex(receipt.get("commitments_sha256")) == _sha(raw),
        "ORIGINAL_COMMITMENT_RECEIPT_REQUIRED",
    )
    prediction_sha = _sha(load(spec["predictions"]))
    linked = [
        receipt[k]
        for k in ("model_predictions_sha256", "predictions_sha256")
        if k in receipt
    ]
    _require(
        bool(linked) and all(_hex(v) == prediction_sha for v in linked),
        "COMMITMENT_PREDICTION_DIFFERS",
    )
    physical = {}
    _require(type(prediction.get("rows")) is list, "PREDICTION_ROWS_REQUIRED")
    for row in prediction["rows"]:
        _require(
            type(row) is dict
            and set(row) == {"band", "candidate", "condition", "values"},
            "PREDICTION_ROW_SHAPE",
        )
        key = (row["band"], row["candidate"], row["condition"])
        _require(key not in physical, "DUPLICATE_PREDICTION_ROW")
        physical[key] = row["values"]
    expected = {
        (index["index_value"], candidate, condition["id"])
        for draw in draws
        for index in draw["task"]["indices"]
        for candidate in index["task"]["candidates"]
        for condition in index["task"]["conditions"]
    }
    _require(not set(physical) - expected, "FOREIGN_PREDICTION_ROW")
    commitments = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        row = _object(_json(line), "COMMITMENT_ROW_OBJECT_REQUIRED")
        i = row.get("population_index")
        _require(
            type(i) is int and 0 <= i < len(draws) and i not in commitments,
            "COMMITMENT_ROSTER_DIFFERS",
        )
        draw = draws[i]
        commitment = _object(row.get("commitment"), "COMMITMENT_OBJECT_REQUIRED")
        _require(
            all(
                row.get(k) == draw[k]
                for k in ("population", "role", "outer_weight", "bank_cluster")
            )
            and commitment.get("task_digest") == draw["task"]["task_digest"]
            and commitment.get("model_id") == spec["id"],
            "COMMITMENT_CONTEXT_DIFFERS",
        )
        commitments[i] = commitment
    _require(set(commitments) == set(range(len(draws))), "COMMITMENT_ROSTER_DIFFERS")
    return physical, commitments


def _guarded_cohort(members, pretruth, load, draws, view_digest, scope):
    """Join independently pinned new construction/fit/choice bytes before truth.

    Root custody establishes pretruth chronology. Hashes authenticate these
    bytes; this consumer does not recreate nominal TRAIN admission from JSON.
    """
    pinned = {row["id"]: row for row in pretruth["members"]}
    _require(
        set(pinned) == {member["id"] for member in members}, "PRETRUTH_ROSTER_DIFFERS"
    )
    result = {}
    for spec in members:
        expected = pinned[spec["id"]]
        _require(
            all(
                spec[key] == expected[key]
                for key in ("id", "recipe", "seed", "kit", "fit_source")
            )
            and _hex(spec["train_sha256"]) == expected["train_sha256"],
            "PRETRUTH_MEMBER_DIFFERS",
        )
        for file_key, hash_key in (
            ("fit_receipt", "fit_receipt_sha256"),
            ("predictions", "predictions_sha256"),
            ("commitments", "commitments_sha256"),
            ("commitment_receipt", "commitment_receipt_sha256"),
        ):
            _require(
                _sha(load(spec[file_key])) == expected[hash_key],
                "PRETRUTH_MEMBER_BYTES_DIFFER",
            )
        receipt = _object(
            _json(load(spec["construction_receipt"])), "CONSTRUCTION_RECEIPT_REQUIRED"
        )
        _require(
            receipt.get("schema")
            == "carbon.scorelab.guarded419.role-separated-train128.v1"
            and receipt.get("scope") == scope
            and receipt.get("receipt_digest") == expected["construction_receipt_digest"]
            and tasks.digest(
                {k: v for k, v in receipt.items() if k != "receipt_digest"}
            )
            == expected["construction_receipt_digest"]
            and receipt.get("construction_jsonl_digest")
            == "sha256:" + _hex(spec["train_sha256"])
            and receipt.get("construction_offered") == 105
            and receipt.get("validation_offered") == 23
            and type(receipt.get("construction_accepted")) is int
            and 2 <= receipt["construction_accepted"] <= 105
            and receipt.get("validation_rows_used_for_fitting") == 0
            and receipt.get("historical_labels_or_models_reused") == 0
            and receipt.get("numerical_evaluation_reference") is False
            and receipt.get("qualification") is False
            and spec["kit"]
            == "carbon.battery-v3.guard419.stage128.kit.v1:"
            + str(receipt.get("binding_digest")),
            "CONSTRUCTION_CONTEXT_DIFFERS",
        )
        fit = _object(_json(load(spec["fit_receipt"])), "FIT_OBJECT_REQUIRED")
        recipe = _object(fit.get("recipe"), "FIT_RECIPE_REQUIRED")
        code = _object(fit.get("code"), "FIT_CODE_OBJECT_REQUIRED")
        train = _object(fit.get("train"), "FIT_TRAIN_OBJECT_REQUIRED")
        _require(
            type(spec["seed"]) is int
            and recipe.get("seed") == spec["seed"]
            and code.get("recipe_id") == spec["recipe"]
            and train.get("records") == receipt["construction_accepted"]
            and train.get("excluded_non_finite")
            == 105 - receipt["construction_accepted"],
            "FIT_CONSTRUCTION_OR_RECIPE_DIFFERS",
        )
        result[spec["id"]] = _member(spec, load, draws, view_digest, scope)
    return result


def evaluate(manifest, artifacts):
    """Pure reduction of pinned bytes; calls the existing scientific APIs only."""
    _require(
        type(manifest) is dict
        and set(manifest)
        == {
            "schema",
            "scope",
            "job",
            "population",
            "registration_sha256",
            "files",
            "draws",
            "banks",
            "members",
            "gamers",
            "bootstrap",
            "seed",
        }
        and manifest["schema"] in (SCHEMA, GUARDED_SCHEMA)
        and manifest["scope"] in SCOPES
        and manifest["population"] in ("P", "Q")
        and not (
            manifest["scope"] == "PUBLIC_DEVELOPMENT" and manifest["population"] != "P"
        ),
        "DEVELOPMENT_CONTEXT_REQUIRED",
    )
    scope, population = manifest["scope"], manifest["population"]
    registered = diagnostic.registration(
        expected_sha256=manifest["registration_sha256"]
    )
    context = diagnostic._selected_context(manifest["registration_sha256"])
    _require(
        manifest["schema"] == (SCHEMA if context is None else GUARDED_SCHEMA),
        "RUN_SCHEMA_CONTEXT_DIFFERS",
    )
    _require(manifest["job"] == registered["job"], "DEVELOPMENT_CONTEXT_REQUIRED")
    _require(
        type(manifest["files"]) is dict and bool(manifest["files"]),
        "FILE_INVENTORY_REQUIRED",
    )
    for spec in manifest["files"].values():
        _require(
            type(spec) is dict and set(spec) == {"path", "sha256"}, "FILE_SPEC_DIFFERS"
        )
        _hex(spec["sha256"])
    used, cache = set(), {}

    def load(key):
        _require(type(key) is str and key in manifest["files"], "UNDECLARED_INPUT")
        if key not in cache:
            try:
                raw = artifacts[key]
            except (KeyError, OSError) as exc:
                raise Refused("INPUT_UNAVAILABLE") from exc
            _require(
                type(raw) is bytes
                and _sha(raw) == _hex(manifest["files"][key]["sha256"]),
                "INPUT_SHA256_DIFFERS",
            )
            cache[key] = raw
        used.add(key)
        return cache[key]

    draws = _draws(_json(load(manifest["draws"])), population, context=context)
    members = manifest["members"]
    _require(type(members) is list and bool(members), "FIXED_COHORT_REQUIRED")
    ids = set()
    for member in members:
        _require(
            type(member) is dict
            and set(member)
            == {
                "id",
                "recipe",
                "predictions",
                "fit_receipt",
                "commitments",
                "commitment_receipt",
                "train_sha256",
                "fit_source",
                "kit",
            }
            | ({"seed", "construction_receipt"} if context is not None else set()),
            "MEMBER_SPEC_DIFFERS",
        )
        _require(
            type(member["id"]) is str
            and member["id"]
            and member["id"] not in ids
            and type(member["recipe"]) is str
            and member["recipe"],
            "FIXED_COHORT_REQUIRED",
        )
        ids.add(member["id"])
    _require(
        type(manifest["bootstrap"]) is int
        and manifest["bootstrap"] > 0
        and type(manifest["seed"]) is int
        and manifest["seed"] >= 0,
        "EXPLICIT_UNCERTAINTY_REQUIRED",
    )
    _require(
        type(manifest["gamers"]) is list
        and len(set(manifest["gamers"])) == len(manifest["gamers"])
        and set(manifest["gamers"]) <= ids,
        "GAMER_ROSTER_DIFFERS",
    )
    banks = manifest["banks"]
    _require(type(banks) is list and len(banks) == len(draws), "COMPLETE_BANK_REQUIRED")
    active_producer = producer
    producer_kwargs = {}
    if context is not None:
        from scripts.dev.score_lab import guarded419_context

        active_producer = guarded419_context.producer(context)
        producer_kwargs["context"] = context
    bank_fields = {
        "population_index",
        "plan",
        "source_pins",
        "manifest",
        "raw_chunks",
        "binding",
    }
    if context is not None:
        bank_fields |= {"calibration_delivery", "pretruth", "pretruth_sha256"}
    for bank in banks:
        _require(type(bank) is dict and set(bank) == bank_fields, "BANK_SPEC_DIFFERS")
    guarded_members, guarded_view_digest, pretruth_sha = None, None, None
    if context is not None:
        first = banks[0]
        plan = _object(_json(load(first["plan"])), "PLAN_OBJECT_REQUIRED")
        plan_digest = _object(first["binding"], "PRODUCER_BINDING_REQUIRED")[
            "plan_digest"
        ]
        view = active_producer.population_view(
            plan, expected_plan_digest=plan_digest, scope=scope, context=context
        )
        guarded_view_digest = view["export_digest"]
        pretruth_sha = _hex(first["pretruth_sha256"])
        pretruth = active_producer.pretruth_receipt(
            load(first["pretruth"]),
            pretruth_sha,
            plan=plan,
            expected_plan_digest=plan_digest,
            scope=scope,
            context=context,
        )
        _require(
            pretruth["draws_digest"] == tasks.digest(draws), "PRETRUTH_DRAWS_DIFFER"
        )
        guarded_members = _guarded_cohort(
            members, pretruth, load, draws, guarded_view_digest, scope
        )
    rows, bindings, seen = [], {}, set()
    for bank in banks:
        _require(
            type(bank) is dict and set(bank) == bank_fields,
            "BANK_SPEC_DIFFERS",
        )
        i = bank["population_index"]
        _require(
            type(i) is int and 0 <= i < len(draws) and i not in seen,
            "COMPLETE_BANK_REQUIRED",
        )
        seen.add(i)
        binding = bank["binding"]
        _require(
            type(binding) is dict
            and set(binding)
            == {"plan_digest", "source_pins_digest", "manifest_digest"},
            "PRODUCER_BINDING_REQUIRED",
        )
        delivery = _object(_json(load(bank["manifest"])), "DELIVERY_OBJECT_REQUIRED")
        _require(
            delivery.get("scope") == scope
            and delivery.get("role") == "HELDOUT_REFERENCE",
            "PUBLIC_REFERENCE_ROLE_REQUIRED",
        )
        extra = dict(producer_kwargs)
        source_pins = _object(
            _json(load(bank["source_pins"])), "SOURCE_PINS_OBJECT_REQUIRED"
        )
        if context is not None:
            _require(
                _hex(bank["pretruth_sha256"]) == pretruth_sha
                and _sha(load(bank["pretruth"])) == pretruth_sha,
                "PRETRUTH_BANK_DIFFERS",
            )
            calibration = active_producer.calibration_from_files(
                bank["calibration_delivery"],
                load=load,
                scope=scope,
                context=context,
            )
            _require(
                tasks.digest(source_pins) == binding["source_pins_digest"],
                "PRODUCER_SOURCE_PINS_DIFFER",
            )
            active_producer.validate_calibration(
                calibration, delivery, source_pins, context=context
            )
            extra.update(
                calibration_evidence=calibration,
                pretruth=load(bank["pretruth"]),
                expected_pretruth_sha256=pretruth_sha,
            )
        evidence = active_producer.build(
            draws[i]["task"],
            plan=_object(_json(load(bank["plan"])), "PLAN_OBJECT_REQUIRED"),
            expected_plan_digest=binding["plan_digest"],
            source_pins=source_pins,
            expected_source_pins_digest=binding["source_pins_digest"],
            manifest=delivery,
            expected_manifest_digest=binding["manifest_digest"],
            raw_chunks={
                key: load(file_id)
                for key, file_id in _object(
                    bank["raw_chunks"], "RAW_CHUNKS_OBJECT_REQUIRED"
                ).items()
            },
            **extra,
        )
        active_producer.validate_for(
            evidence,
            draws[i]["task"],
            evidence.references,
            evidence.enclosures,
            scope=scope,
            **producer_kwargs,
        )
        rows.append({"draw": draws[i], "evidence": evidence})
        bindings[draws[i]["task"]["task_digest"]] = binding
    # Preserve original draw order for the saved commitments and input view.
    by_id = {r["draw"]["task"]["task_digest"]: r for r in rows}
    rows = [by_id[d["task"]["task_digest"]] for d in draws]
    view = {
        "schema": active_producer.CANDIDATE_VIEW,
        "scope": scope,
        "family": "battery-v3",
        "questions": [r["evidence"].prediction_view["questions"][0] for r in rows],
    }
    view_digest = tasks.digest(view)
    if context is not None:
        _require(view_digest == guarded_view_digest, "PRETRUTH_CANDIDATE_VIEW_DIFFERS")
    legs, values = {}, {}
    for member in members:
        physical, commitments = (
            _member(member, load, draws, view_digest, scope)
            if context is None
            else guarded_members[member["id"]]
        )
        leg_rows = [r for r in rows if r["draw"]["role"] == "LEG"]
        value_rows = [r for r in rows if r["draw"]["role"] == "VALUE"]

        def bound(part):
            return {
                r["draw"]["task"]["task_digest"]: bindings[
                    r["draw"]["task"]["task_digest"]
                ]
                for r in part
            }

        kwargs = {
            "expected_registration_digest": manifest["registration_sha256"],
            "scope": scope,
            "population": population,
        }
        legs[member["id"]] = diagnostic.score_leg(
            leg_rows,
            {
                r["draw"]["task"]["task_digest"]: _panels(r["draw"], physical)
                for r in leg_rows
            },
            producer_bindings=bound(leg_rows),
            **kwargs,
        )
        values[member["id"]] = diagnostic.judge_values(
            value_rows,
            {
                d["task"]["task_digest"]: commitments[i]
                for i, d in enumerate(draws)
                if d["role"] == "VALUE"
            },
            producer_bindings=bound(value_rows),
            **kwargs,
        )
    _require(used == set(manifest["files"]), "UNUSED_INPUT_FILE")
    report = diagnostic.alignment(
        legs,
        values,
        recipe_of={m["id"]: m["recipe"] for m in members},
        gamers=manifest["gamers"],
        bootstrap=manifest["bootstrap"],
        seed=manifest["seed"],
    )
    result = {
        "cohort": {
            "schema": manifest["schema"],
            "scope": scope,
            "job": manifest["job"],
            "population": population,
            "manifest_digest": tasks.digest(manifest),
            "members": members,
            "input_files": manifest["files"],
            "bootstrap": manifest["bootstrap"],
            "seed": manifest["seed"],
            "qualification": False,
        },
        "members": {"legs": legs, "values": values},
        "alignment": report,
    }
    if context is not None:
        result["cohort"]["diagnostic_context"] = guarded419_context.metadata(context)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument(
        "--manifest", required=True, help="relative to the public input root"
    )
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.input_root.resolve(strict=True)
        _require(
            not args.input_root.is_symlink() and root.is_dir(), "INVALID_INPUT_ROOT"
        )
        raw = _relative(root, args.manifest).read_bytes()
        _require(_sha(raw) == _hex(args.manifest_sha256), "RUN_MANIFEST_SHA256_DIFFERS")
        manifest = _object(_json(raw), "RUN_MANIFEST_OBJECT_REQUIRED")
        _require(not args.output_dir.exists(), "OUTPUT_ALREADY_EXISTS")
        results = evaluate(manifest, _Files(root, manifest.get("files", {})))
        outputs = {
            name
            + ".json": (
                json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
            ).encode()
            for name, value in results.items()
        }
        args.output_dir.mkdir(parents=True, exist_ok=False)
        for name, data in outputs.items():
            with (args.output_dir / name).open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        complete = {
            "status": "COMPLETED_DEVELOPMENT_DIAGNOSTIC",
            "input_manifest_sha256": _sha(raw),
            "files": {name: _sha(data) for name, data in outputs.items()},
            "qualification": False,
        }
        with (args.output_dir / "complete.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as handle:
            json.dump(complete, handle, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        print(json.dumps(complete, sort_keys=True))
        return 0
    except (
        Refused,
        tasks.TaskError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    ) as exc:
        code = (
            str(exc)
            if isinstance(exc, Refused)
            else (
                "REFERENCE_CONTRACT_REFUSED"
                if isinstance(exc, tasks.TaskError)
                else (
                    "INPUT_OR_OUTPUT_UNAVAILABLE"
                    if isinstance(exc, OSError)
                    else "MALFORMED_INPUT"
                )
            )
        )
        print(
            json.dumps(
                {
                    "status": "REFUSED",
                    "code": code,
                    "candidate_penalty": False,
                    "qualification": False,
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
