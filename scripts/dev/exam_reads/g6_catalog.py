# ruff: noqa: BLE001 - a failed build is a NOT_RUN result for G6, never a learner verdict
"""G6 for a CATALOG default model: the version's own catalog practice route builds the default on one nested TRAIN subset and
predicts the G6 QUERY. CUSTODY scratch: it builds and predicts only; it grades nothing, opens no pack and writes no store.

Why a wrapper: a catalog default is built only by the bundle worker on the FULL public TRAIN bytes (five digest checks), so it
cannot take a subset file (Validator 3 Nov 18:46: "a worker-side subset path"). Design: reports/
G6_CATALOG_SUBSET_PATH_DESIGN_TE2_20261104.md, option (B): no change under carbon/.

- The version's catalog practice (`practice_v2_curves.practice_for`, the route `recal_build_entry` drives) assembles the ledger,
  the owner identity, the worker image or verified GPU overlay, the challenge binding, the full TRAIN bytes, the example, the
  allowlist and the limits exactly as a miner's practice does. Only its `reconstruct_and_infer_public` call is replaced, by a
  capture that calls the REAL `reconstruct_and_infer_public` with the same arguments except: ``inputs`` = the G6 QUERY,
  ``expected_output_shape`` = (QUERY rows, the practice's output shape), ``seed`` = 0, no timed query, and ``runner`` =
  `subset_runner` around the real `research_carrier._run`.
- `subset_runner` changes ONLY the build child (``source == BUILD_PROGRAM``): it stages one more file, ``g6-subset.json``
  (the subset's TRAIN row indices, ascending, and their sha256), and inserts `SUBSET_BLOCK` once, right after the line that
  decodes the digest-checked TRAIN (`ANCHOR`). The block checks the indices and keeps those rows. Everything after it, the
  entrypoint, Carbon's lowering, the freeze, the allowlist and the receipt, is the official program byte for byte. The
  inference child (no TRAIN) runs unchanged.
- With a runner given, `reconstruct_and_infer_public` labels its result TEST_ONLY_LOCAL_RUNNER and skips the control digests;
  the G6 record says what really ran (``execution``): the real carrier, the patched program's sha, the block's sha.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_DEV = _HERE.parent
for _path in (_HERE, _DEV):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import g6_subsets as subsets

_need = subsets._need
OFFICIAL_SEED = 0
SUBSET_FILE = "g6-subset.json"
SUBSET_SCHEMA = "carbon.exam-reads.g6-subset-rows.v1"
#: The BUILD_PROGRAM line after which TRAIN is decoded and digest-checked; the subset is cut right after it.
ANCHOR = 'train_inputs, train_targets = train_tensors(train_raw, control["binding"])\n'
SUBSET_BLOCK = (
    "# G6 (custody scratch, scripts/dev/exam_reads/g6_catalog.py): keep only the nested subset's TRAIN rows.\n"
    f'_g6 = json.loads((work / "{SUBSET_FILE}").read_bytes())\n'
    '_g6_idx = np.asarray(_g6.get("indices"), dtype=np.int64)\n'
    'if (_g6.get("schema") != "' + SUBSET_SCHEMA + '"\n'
    '        or _g6.get("indices_sha256") != hashlib.sha256(_g6_idx.astype("<i8").tobytes()).hexdigest()\n'
    '        or _g6_idx.ndim != 1 or len(_g6_idx) < 2 or _g6.get("k") != len(_g6_idx)\n'
    '        or _g6.get("n_train") != len(train_inputs)\n'
    "        or int(_g6_idx[0]) < 0 or int(_g6_idx[-1]) >= len(train_inputs)\n"
    "        or not bool(np.all(np.diff(_g6_idx) > 0))):\n"
    '    raise ValueError("g6 subset rows differ")\n'
    "train_inputs, train_targets = train_inputs[_g6_idx], train_targets[_g6_idx]\n"
)
ROUTES = ("motor", "cooling", "f08", "f02")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _recipe_for(route, catalog_id):
    """The version's catalog recipe for ``catalog_id`` (`practice_v2_curves.recipe_for`: the registry's own builder)."""
    import practice_v2_curves as curves

    return curves.recipe_for(route, catalog_id)


class G6Done(BaseException):
    """Leaves the practice after the G6 build + query inference (a BaseException: no practice handler swallows it)."""

    def __init__(self, record):
        super().__init__("g6 build captured")
        self.record = record


def patched_build_program(program):
    """``program`` with `SUBSET_BLOCK` inserted once after `ANCHOR`; refuses unless the anchor occurs exactly once."""
    _need(
        type(program) is str and program.count(ANCHOR) == 1, "g6_build_program_anchor"
    )
    return program.replace(ANCHOR, ANCHOR + SUBSET_BLOCK)


def subset_document(indices, n_train):
    """The ``g6-subset.json`` bytes: the subset's TRAIN row indices (ascending, distinct, in range), k and their sha256."""
    import numpy as np

    idx = np.asarray(indices, dtype=np.int64)
    _need(
        idx.ndim == 1
        and len(idx) >= 2
        and int(idx[0]) >= 0
        and int(idx[-1]) < n_train
        and bool(np.all(np.diff(idx) > 0)),
        "g6_subset_indices",
    )
    doc = {
        "schema": SUBSET_SCHEMA,
        "indices": [int(i) for i in idx],
        "indices_sha256": _sha(idx.astype("<i8").tobytes()),
        "k": len(idx),
        "n_train": int(n_train),
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()


def subset_runner(subset_bytes, build_program, run, calls):
    """A carrier runner: the build child (``source is build_program``) gets the subset file and the patched program; every
    other child (inference) passes through unchanged. ``calls`` collects what each call ran.
    """
    patched = patched_build_program(build_program)

    def runner(ledger, **kw):
        if kw.get("source") == build_program:
            files = dict(kw["files"])
            _need(SUBSET_FILE not in files, "g6_subset_file_name_taken")
            files[SUBSET_FILE] = subset_bytes
            kw = {**kw, "source": patched, "files": files}
            calls.append(
                {
                    "child": "build",
                    "program_sha256": _sha(patched.encode()),
                    "official_program_sha256": _sha(build_program.encode()),
                }
            )
        else:
            calls.append(
                {"child": "other", "program_sha256": _sha(kw["source"].encode())}
            )
        return run(ledger, **kw)

    return runner


def make_capture(
    *, original, query, subset_bytes, record_into, run, official_check=None
):
    """The replacement for `reconstruct_and_infer_public` (see the module docstring)."""

    def capture(ledger, **kw):
        import numpy as np

        from carbon.development_session import bundle_construction_worker as worker

        recipe = kw["recipe"]
        if official_check is not None:
            official_check(recipe.to_dict())
        practice_inputs = np.asarray(kw["inputs"])
        _need(
            query.shape[1:] == practice_inputs.shape[1:],
            "g6_query_width_differs_from_interface",
        )
        rows = np.ascontiguousarray(query, dtype=practice_inputs.dtype)
        calls = []
        result = original(
            ledger,
            **{
                **kw,
                "inputs": rows,
                "expected_output_shape": (
                    len(rows),
                    *tuple(kw["expected_output_shape"])[1:],
                ),
                "seed": OFFICIAL_SEED,
                "measure_query": False,
                "timing_optional": False,
                "runner": subset_runner(subset_bytes, worker.BUILD_PROGRAM, run, calls),
            },
        )
        _need(
            [c["child"] for c in calls][:1] == ["build"]
            and sum(c["child"] == "build" for c in calls) == 1,
            "g6_build_child_not_run_once",
        )
        record_into.update(
            {
                "recipe": recipe,
                "train": kw["train"],
                "challenge_binding": kw["challenge_binding"],
                "accelerator": kw.get("accelerator"),
                "result": result,
                "calls": calls,
            }
        )
        raise G6Done(record_into)

    return capture


def checked_subset(train_raw, binding, manifest, fraction, subset_raw):
    """``(indices, k)`` for ``fraction``: TRAIN decoded by the bundle codec (digest-checked against the binding), the subset's
    indices re-derived from the manifest, and the subset file's rows equal to TRAIN's rows at those indices.
    """
    from carbon.development_session.construction_tensor_codec import train_tensors

    inputs, targets = train_tensors(train_raw, binding)
    _order, indices = subsets.subset_indices(
        manifest, fraction, len(inputs), arrays={"inputs": inputs, "targets": targets}
    )
    _names, sub, _n = subsets.load_train(subset_raw)
    _need(
        set(sub) == {"inputs", "targets"}
        and sub["inputs"].dtype == inputs.dtype
        and sub["targets"].dtype == targets.dtype
        and sub["inputs"].tobytes() == inputs[indices].tobytes()
        and sub["targets"].tobytes() == targets[indices].tobytes(),
        "g6_subset_rows_differ_from_train",
    )
    return indices, len(inputs)


def default_rows(
    route,
    catalog_id,
    practice_args,
    manifest,
    fraction,
    subset_raw,
    query,
    *,
    version=None,
    factory=None,
    run=None,
    official=True,
):
    """``(rows, record)`` for the catalog default at ``fraction``, or ``(None, NOT_RUN record)``.

    ``factory`` (a practice factory) and ``run`` (the carrier) are the real ones unless a test passes stand-ins.
    """
    import numpy as np
    import practice_v2_curves as curves
    from recal_build_entry import OfficialMismatch, verify_official

    from carbon.development_session import bundle_construction_worker as worker
    from carbon.development_session.construction_recipe import RecipeRefused

    _need(route in ROUTES, "g6_catalog_route")
    # The version is the caller's, always: practice_v2_curves' defaults are older versions (self-review finding 4).
    _need(type(version) is str and bool(version), "g6_catalog_version_required")
    targets = curves.TARGETS
    curves.TARGETS = {**targets, route: (targets[route][0], version)}
    try:
        return _default_rows(
            route,
            catalog_id,
            practice_args,
            manifest,
            fraction,
            subset_raw,
            query,
            curves=curves,
            factory=factory,
            run=run,
            official=official,
            np=np,
            worker=worker,
            RecipeRefused=RecipeRefused,
            OfficialMismatch=OfficialMismatch,
            verify_official=verify_official,
        )
    finally:
        curves.TARGETS = targets


def _default_rows(
    route,
    catalog_id,
    practice_args,
    manifest,
    fraction,
    subset_raw,
    query,
    *,
    curves,
    factory,
    run,
    official,
    np,
    worker,
    RecipeRefused,
    OfficialMismatch,
    verify_official,
):
    factory = factory or curves.practice_for
    if run is None:
        from carbon.development_session.research_carrier import _run as run
    practice = factory(route, practice_args)
    if getattr(practice_args, "gpu_image", None):
        from carbon.reconstruction.worker.docker_runtime import load_image_identity

        practice.gpu_image = load_image_identity(Path(practice_args.gpu_image))
    catalog_recipe = _recipe_for(route, catalog_id)
    official_check = None
    declared = ()
    if official:
        from carbon.backbone_catalog.served import expand_official
        from carbon.development_session.gpu_practice import gpu_runtimes

        declared = gpu_runtimes(getattr(practice, "gpu_image", None))

        def official_check(expanded):
            if declared:  # a GPU build: it must be the bundle official grading rebuilds
                verify_official(expanded, catalog_recipe, declared, expand_official)

    # The subset document needs TRAIN's row count, read from the practice's own TRAIN inside the capture.
    record = {}
    original = worker.reconstruct_and_infer_public

    def capture(ledger, **kw):
        binding = worker._checked_binding(kw["recipe"], kw["challenge_binding"])
        _need(
            _sha(kw["train"]) == manifest["train_sha256"],
            "g6_train_differs_from_the_practice_train",
        )
        indices, n = checked_subset(
            kw["train"], binding, manifest, fraction, subset_raw
        )
        record["indices_sha256"] = _sha(np.asarray(indices, dtype="<i8").tobytes())
        record["train_cases"] = len(indices)
        inner = make_capture(
            original=original,
            query=query,
            subset_bytes=subset_document(indices, n),
            record_into=record,
            run=run,
            official_check=official_check,
        )
        return inner(ledger, **kw)

    identity = (
        f"g6-{route}-{hashlib.sha256(catalog_id.encode()).hexdigest()[:12]}"
        f"-f{subsets.frac_label(fraction).replace('.', '')}"
    )
    worker.reconstruct_and_infer_public = capture
    try:
        practice(identity, catalog_recipe)
    except G6Done:
        pass
    except (subsets.SubsetsRefused, OfficialMismatch):
        # the tool's own refusal, or a GPU build that is not the official bundle: never a NOT_RUN learner row
        raise
    except RecipeRefused as error:
        return None, {
            "status": "NOT_RUN",
            "code": getattr(error, "code", "recipe_refused"),
        }
    except Exception as error:
        code = getattr(error, "code", None)
        return None, {
            "status": "NOT_RUN",
            "code": "g6_catalog_build_failed:"
            + type(error).__name__
            + (f":{code}" if type(code) is str and code else ""),
        }
    finally:
        worker.reconstruct_and_infer_public = original
    if "result" not in record:
        return None, {
            "status": "NOT_RUN",
            "code": "g6_practice_did_not_reach_the_build",
        }
    result = record["result"]
    predictions = np.asarray(result.inference.predictions, dtype=np.float64)
    predictions = predictions.reshape(len(query), -1)
    build_calls = [c for c in record["calls"] if c["child"] == "build"]
    return predictions, {
        "status": "FITTED",
        "path": "catalog practice route, real reconstruct_and_infer_public, build child patched by g6_catalog",
        "route": route,
        "catalog_id": catalog_id,
        "recipe_digest": result.build.recipe_digest,
        "state_digest": result.build.state_digest,
        "train_input": "the practice's full public TRAIN, cut in the build child to the subset rows (TRAIN order)",
        "train_cases": record["train_cases"],
        "indices_sha256": record["indices_sha256"],
        "accelerator": record["accelerator"],
        # True only for a GPU-twin build checked against expand_official; a CPU curve is recorded as such (Validator 15:51 (2))
        "official_bundle_verified": bool(official and declared),
        "execution": {
            "carrier": (
                "research_carrier._run" if run.__name__ == "_run" else run.__name__
            ),
            "label_from_worker": result.execution_boundary,
            "build_program_sha256": build_calls[0]["program_sha256"],
            "official_build_program_sha256": build_calls[0]["official_program_sha256"],
            "subset_block_sha256": _sha(SUBSET_BLOCK.encode()),
        },
        "build_receipt": result.build.receipt,
        # the receipt's train_digest is the FULL TRAIN the child decoded before the cut; never read it as the trained rows
        "receipt_train_digest_is_pre_cut": True,
    }
