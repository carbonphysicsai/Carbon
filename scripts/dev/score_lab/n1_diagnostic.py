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


def _draws(value, population):
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
        task = draw.get("task", {})
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
    prediction = _json(load(spec["predictions"]))
    fit = _json(load(spec["fit_receipt"]))
    receipt = _json(load(spec["commitment_receipt"]))
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
        and fit.get("train", {}).get("sha256") == "sha256:" + _hex(spec["train_sha256"])
        and fit.get("train", {}).get("fixture") is (scope == "SYNTHETIC_FIXTURE")
        and fit.get("code", {}).get("actual_source", {}).get("commit")
        == spec["fit_source"],
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
        row = _json(line)
        i = row.get("population_index")
        _require(
            type(i) is int and 0 <= i < len(draws) and i not in commitments,
            "COMMITMENT_ROSTER_DIFFERS",
        )
        draw = draws[i]
        _require(
            all(
                row.get(k) == draw[k]
                for k in ("population", "role", "outer_weight", "bank_cluster")
            )
            and row.get("commitment", {}).get("task_digest")
            == draw["task"]["task_digest"]
            and row["commitment"].get("model_id") == spec["id"],
            "COMMITMENT_CONTEXT_DIFFERS",
        )
        commitments[i] = row["commitment"]
    _require(set(commitments) == set(range(len(draws))), "COMMITMENT_ROSTER_DIFFERS")
    return physical, commitments


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
        and manifest["schema"] == SCHEMA
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

    draws = _draws(_json(load(manifest["draws"])), population)
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
            },
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
    rows, bindings, seen = [], {}, set()
    for bank in banks:
        _require(
            type(bank) is dict
            and set(bank)
            == {
                "population_index",
                "plan",
                "source_pins",
                "manifest",
                "raw_chunks",
                "binding",
            },
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
        delivery = _json(load(bank["manifest"]))
        _require(
            delivery.get("scope") == scope
            and delivery.get("role") == "HELDOUT_REFERENCE",
            "PUBLIC_REFERENCE_ROLE_REQUIRED",
        )
        evidence = producer.build(
            draws[i]["task"],
            plan=_json(load(bank["plan"])),
            expected_plan_digest=binding["plan_digest"],
            source_pins=_json(load(bank["source_pins"])),
            expected_source_pins_digest=binding["source_pins_digest"],
            manifest=delivery,
            expected_manifest_digest=binding["manifest_digest"],
            raw_chunks={
                key: load(file_id) for key, file_id in bank["raw_chunks"].items()
            },
        )
        producer.validate_for(
            evidence,
            draws[i]["task"],
            evidence.references,
            evidence.enclosures,
            scope=scope,
        )
        rows.append({"draw": draws[i], "evidence": evidence})
        bindings[draws[i]["task"]["task_digest"]] = binding
    # Preserve original draw order for the saved commitments and input view.
    by_id = {r["draw"]["task"]["task_digest"]: r for r in rows}
    rows = [by_id[d["task"]["task_digest"]] for d in draws]
    view = {
        "schema": producer.CANDIDATE_VIEW,
        "scope": scope,
        "family": "battery-v3",
        "questions": [r["evidence"].prediction_view["questions"][0] for r in rows],
    }
    view_digest = tasks.digest(view)
    legs, values = {}, {}
    for member in members:
        physical, commitments = _member(member, load, draws, view_digest, scope)
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
    return {
        "cohort": {
            "schema": SCHEMA,
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
        manifest = _json(raw)
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
    except (Refused, tasks.TaskError, OSError, ValueError, TypeError, KeyError) as exc:
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
