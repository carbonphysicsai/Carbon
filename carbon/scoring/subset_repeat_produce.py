"""The dual producer of a subset-repeat version (`subset_repeat_evidence.SUBSET_REPEAT_VERSIONS`: Motor 1.8).

`physical_dual_pack.produce` reads the full repeat pair (`private_evaluation_source.read_inference_repeats`) and binds
the pack's pinned producer by exact equality; both live in shared producer files whose bytes every other live pack pins.
So a subset version is produced HERE, never by editing them: the door routes a subset version's grade to
`produce_registered_dual_measurement` (and its exam SE to `bootstrap_total_se`). Everything else is the shared code,
called unchanged: the same role reads, bindings, authenticated graded outputs, pool query measurement, the adapter's
`measure`, the shared receipt builder and its pack checks.

What differs, exactly (CV-Motor-B's rulings; Validator-2B R-1..R-3):

- **The producer binding** (R-1): the pinned digest must equal the producer recomputed here, or the version's ONE
  successor row must map exactly that pinned digest to exactly this producer (`producer_successor.binds`). The shared
  receipt builder checks the pack under the pinned digest it was sealed with; the receipt then records the ACTUAL
  producer digest in its evidence and measurement basis (R-3). Nothing older is rescored.
- **The repeat** (Q1 = B; owner "66 per stratum"): the repeat-evidence slot of the graded originals (``inference_pair_raw`` /
  ``inference_pair_sha256``, the slot the full pair rides in for every other version) carries the subset repeat's side
  file: ALL the sealed cells plus ``k`` keyed rows inside each registered stratum, re-run in one fresh process, read by
  `subset_repeat_evidence.read` into one fresh answer per repeated row and None on every row that is not
  repeat-checked. Its own schema tells it from a pair: neither reader accepts the other's document. Missing or broken
  evidence is typed unavailable (``dual_repeat_evidence_unavailable``), never a candidate verdict.
- **The gate** (`measure_subset`, Q2): the DECISIVE rule is that every repeated row's fresh answer equals the graded
  answer bit for bit over the whole row (`subset_repeat_evidence.rows_agree`); a differing value, a malformed or a
  non-finite fresh answer fails it. One failure makes the grade unscored exactly as a pair mismatch on a graded cell
  does today: ``native_motor_valid`` and ``complete_fixed_coverage`` FAIL, A is None and D is 0. Motor's existing
  torque-slice ``paired_repeat`` gate runs as it always did, inside the adapter's measure, on each repeated sealed
  cell's fresh answer.
- **What the repeat may touch** (R-2): fresh answers reach only gates. The shared sealed measure takes two full twin
  rows (as `pool_plugin` and the baseline packs pass ``[outputs, outputs]``), so a row that is not repeat-checked (or
  whose fresh answer is not one finite row of the right width) is given its own graded answer as its twin: its
  ``paired_repeat`` then reads PASS internally. That verdict is never exported (the aggregate counts only FAIL) and has
  no score effect: `exam.score_case` reads the twin only inside its gates, and the pool rows' twins are never read.

This module is a producer file of Motor 1.8 only (`motor18_dual_pack.FILES`).
"""

from __future__ import annotations

import io
import json
import math

from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import producer_successor
from carbon.scoring import subset_repeat_evidence as subset_evidence

#: The mandatory gates a failed subset repeat fails, as a pair mismatch on a graded cell fails them today.
REPEAT_GATES = ("native_motor_valid", "complete_fixed_coverage")
#: The graded procedure the subset repeat repeats (the pack's public ``paired_repeat_procedure``).
PROCEDURE = "per_case"


def _source():
    from carbon.scoring import private_evaluation_source

    return private_evaluation_source


def repeat_holds(outputs, twins):
    """The subset gate's decisive rule over the whole graded bank: every repeated row (``twins[i]`` not None) equals its
    graded answer bit for bit over the whole row. Rows that are not repeat-checked are not judged here.
    """
    return all(
        subset_evidence.rows_agree(output, twin)
        for output, twin in zip(outputs, twins, strict=True)
        if twin is not None
    )


def _twin_row(output, twin):
    """The twin row the adapter's measure is given: the fresh answer when it is one finite row of the graded width,
    else the graded answer itself (the exact check has already failed such a row)."""
    if (
        twin is not None
        and len(twin) == len(output)
        and all(type(v) is float and math.isfinite(v) for v in twin)
    ):
        return list(twin)
    return list(output)


def measure_subset(adapter, *, outputs, twins, capture=None, **arguments):
    """The adapter's measure of one grade under the subset repeat (see the module docstring)."""
    if (
        type(outputs) is not list
        or type(twins) is not list
        or len(twins) != len(outputs)
    ):
        raise adapter.Refused("motor_prediction_roster")
    repeat = [
        _twin_row(output, twin) for output, twin in zip(outputs, twins, strict=True)
    ]
    measured = adapter.measure(
        outputs=outputs,
        repeats=[repeat, repeat],
        **({} if capture is None else {"capture": capture}),
        **arguments,
    )
    return gated(adapter, measured, repeat_holds(outputs, twins), capture=capture)


def gated(adapter, measured, holds, *, capture=None):
    """``measured`` unchanged when the repeat holds; else the grade unscored exactly as a pair mismatch on a graded cell
    leaves it: ``native_motor_valid`` and ``complete_fixed_coverage`` FAIL, A None, D 0.
    """
    if holds:
        return measured
    gates = dict(measured.get("gates") or {})
    if not set(REPEAT_GATES) <= set(gates):
        raise adapter.Refused("subset_repeat_gates_unregistered")
    if capture is not None:
        capture["se_basis"] = {"gated": True}
    return {
        **measured,
        "A": None,
        "D": 0.0,
        "gates": {**gates, **dict.fromkeys(REPEAT_GATES, False)},
    }


def _inputs(
    adapter,
    *,
    selected,
    public_root,
    private_root,
    entry,
    job,
    registration,
    references,
    originals,
    source_raw,
    bank,
    interface_names,
):
    """`physical_dual_pack._inputs` for a subset version: the same checks, with the successor-aware producer binding
    and the keyed subset repeat in place of the pair."""
    import numpy as np

    from carbon.development_session.bundle_construction_worker import _tensors

    source_module = _source()
    refused = source_module.PrivateEvaluationSourceRefused
    require = source_module._producer_require
    require(
        subset_evidence.is_subset_version(adapter.CHALLENGE, adapter.VERSION)
        and getattr(adapter, "POOL_GRADED", False),
        "subset_repeat_version_unregistered",
    )
    roles = {}
    for audience, names, root in (
        (
            "public",
            ("accuracy_definition", "important_limit_definition", "design_objective"),
            public_root,
        ),
        ("private", ("score_pack",), private_root),
    ):
        for name in names:
            try:
                roles[name] = selected.read_json_role(
                    root, audience, name, max_bytes=1024 * 1024
                )
            except ValueError as exc:
                raise refused("dual_native_role_unavailable:" + name) from exc
    try:
        train_raw = selected.read_role(
            public_root, "public", "train", max_bytes=16 * 1024**2
        )
        case_bank = selected.read_role(
            private_root, "private", "case_bank", max_bytes=16 * 1024**2
        )
    except ValueError as exc:
        raise refused("dual_native_role_unavailable:train_or_case_bank") from exc
    definition = roles["accuracy_definition"]
    # The pool's truths ride in the carried batch, never in the public accuracy definition.
    if type(bank.get("pool")) is not dict:
        raise refused("dual_native_pool_material_missing")
    definition = {**definition, "pool": bank["pool"]}
    identity = physical.producer_digest(adapter)
    pinned = definition.get("producer_digest")
    try:
        adapter.validate_definition(definition)
    except adapter.Refused as exc:
        raise refused("dual_native_definition_method") from exc
    require(
        producer_successor.binds(adapter.CHALLENGE, adapter.VERSION, pinned, identity)
        and definition.get("train_digest")
        == entry.get("train_digest")
        == physical.sha(train_raw)
        and definition.get("bank_digest") == physical.bank_digest(bank),
        "dual_native_producer_or_train_binding",
    )
    require(
        case_bank == _tensors(inputs=np.array(bank["inputs"]))
        and physical.sha(case_bank)
        == entry.get("roles", {}).get("inputs", {}).get("sha256"),
        "dual_native_source_mapping",
    )
    source = source_module._parse_pack_source(source_raw)
    require(
        type(source.get("cases")) is list
        and len(source["cases"]) == 1
        and type(references) is list
        and len(references) == 1
        and len(registration.get("cases", [])) == 1,
        "dual_native_complete_batch_required",
    )
    require(
        source["evaluation_pack_digest"] == selected.manifest_digest
        and source["registration_digest"] == registration.get("registration_digest")
        and source["cases"][0]["query_sha256"] == physical.sha(case_bank)
        and source["cases"][0]["reference_row_sha256"]
        == physical.sha(physical.canonical(references[0]))
        and source["cases"][0]["reference_status"] == references[0].get("status"),
        "dual_native_source_original_binding",
    )
    for field in ("challenge", "challenge_version", "interface_digest", "train_digest"):
        require(
            source.get(field) == entry.get(field) == job.get(field),
            "dual_native_identity",
        )
    if references[0].get("status") != "RESOLVED":
        raise refused(
            "dual_native_reference_infra"
            if references[0].get("status") == "FAILED_INFRA"
            else "dual_native_reference_unresolved"
        )
    require(
        references[0].get("outputs") == physical.flat_references(bank),
        "dual_native_reference_flat_binding",
    )
    receipt, worker, values, inference = source_module._authenticated_graph_outputs(
        entry, registration, originals
    )
    platform = definition.get("leg_minimum_platform")
    if (
        type(platform) is not dict
        or platform.get("inference_image_id") != worker.get("inference_image_id")
        or platform.get("device_class")
        != registration.get("timing_profile", {}).get("model_device")
    ):
        raise refused("leg_minimum_platform_mismatch")
    n, width = len(bank["case_ids"]), len(bank["references"][0])
    measurement = physical._pool_query_measurement(
        selected, public_root, registration, originals, bank, refused
    )
    require(
        len(values) == n * width and measurement["output_shape"] == [n, width],
        "dual_native_tensor_shape",
    )
    # The repeat repeats the graded per-case procedure itself (the pack's public paired_repeat_procedure).
    require(
        definition.get("paired_repeat_procedure") == PROCEDURE
        and receipt.get("schema") == "carbon.development.bundle-inference.v1",
        "dual_repeat_procedure",
    )
    if not {"inference_pair_raw", "inference_pair_sha256"} <= set(originals):
        raise refused("dual_repeat_evidence_unavailable")
    try:
        with np.load(io.BytesIO(case_bank), allow_pickle=False) as loaded:
            graded_inputs = loaded["inputs"]
        twins = subset_evidence.read(
            originals["inference_pair_raw"],
            registered_sha256=originals["inference_pair_sha256"],
            challenge=adapter.CHALLENGE,
            version=adapter.VERSION,
            evaluation_pack_digest=selected.manifest_digest,
            cohorts=list(bank["cohorts"]),
            graded_inputs=graded_inputs,
            output_shape=measurement["output_shape"],
            recipe_digest=receipt["recipe_digest"],
            state_digest=receipt["state_digest"],
            inference_image_id=worker["inference_image_id"],
            graded_operation=worker.get("inference_operation"),
        )
    except subset_evidence.SubsetRepeatRefused as exc:
        raise refused("dual_repeat_evidence_unavailable:" + exc.code) from exc
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise refused("dual_repeat_evidence_unavailable") from exc
    return {
        "refused": refused,
        "require": require,
        "roles": roles,
        "definition": definition,
        "train_raw": train_raw,
        "source": source,
        "values": values,
        "twins": twins,
        "inference": inference,
        "n": n,
        "width": width,
        "identity": identity,
        "pinned": pinned,
    }


def _single_call(originals, refused):
    from carbon.development_session import single_call_timing

    try:
        return single_call_timing.read_side_file(originals.get("single_call_raw"))
    except single_call_timing.SingleCallRefused as exc:
        raise refused("single_call_evidence_unavailable") from exc


def produce(adapter, **kwargs):
    """`physical_dual_pack.produce` for a subset version (pool-graded: no batched timed query), or a typed refusal:
    ``(measured model, benchmark, producer digest, pinned producer digest)``. The graded originals are read under the
    ceiling sized from this bank (`pair_read_bound`), as `physical_dual_pack.produce` reads them for this version.
    """
    from carbon.scoring import pair_read_bound

    shape = pair_read_bound._bank_shape(kwargs.get("bank"))
    if shape is None:
        with pair_read_bound.held():
            return _produce(adapter, **kwargs)
    with pair_read_bound.raised(pair_read_bound.pair_bytes(*shape)):
        return _produce(adapter, **kwargs)


def _produce(
    adapter,
    *,
    selected,
    public_root,
    private_root,
    entry,
    job,
    registration,
    references,
    originals,
    source_raw,
    bank,
    interface_names,
    timing_step,
):
    del timing_step  # a pool-graded version has no batched timed query to agree with
    from carbon.scoring import bundle_benchmark_core as bundle

    ctx = _inputs(
        adapter,
        selected=selected,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        job=job,
        registration=registration,
        references=references,
        originals=originals,
        source_raw=source_raw,
        bank=bank,
        interface_names=interface_names,
    )
    refused, require = ctx["refused"], ctx["require"]
    roles, definition, source = ctx["roles"], ctx["definition"], ctx["source"]
    n, width = ctx["n"], ctx["width"]
    if originals.get("timed_query") is not None:
        raise refused("dual_native_pool_has_no_timed_query")
    call_s, outputs_match = _single_call(originals, refused)
    pack = roles["score_pack"]
    gates = list(pack.get("hard_gates", []))
    values = ctx["values"]
    outputs = [list(values[i * width : (i + 1) * width]) for i in range(n)]
    try:
        measured = measure_subset(
            adapter,
            outputs=outputs,
            twins=list(ctx["twins"]),
            bank_rows=physical.bank_rows(bank, interface_names),
            definition=definition,
            limits=roles["important_limit_definition"],
            objective=roles["design_objective"],
            train_raw=ctx["train_raw"],
            names=interface_names,
            speed_call_seconds=call_s,
            speed_outputs_match=outputs_match,
        )
    except adapter.Refused as exc:
        raise refused("dual_native_" + exc.code) from exc
    require(
        gates == registration["mandatory_gates"] == list(measured["gates"]),
        "dual_native_gate_contract",
    )

    def leg(value):
        if value is None:
            return {"status": "CANDIDATE_INVALID", "value": None, "unit": "1"}
        return {"status": "RESOLVED", "value": value, "unit": "1"}

    benchmark = {
        "schema": "carbon.scoring.dual-benchmark-input.v1",
        "scope": pack["scope"],
        "challenge": adapter.CHALLENGE,
        "physics_contract_digest": pack["physics_contract_digest"],
        "measurement_contract_digest": pack["measurement_contract_digest"],
        "population_role": source["cases"][0]["role"],
        "common_mask_digest": physical.sha(physical.canonical(source["cases"])),
        "models": [
            {
                "artifact_digest": entry["entry_id"],
                "gates": {
                    k: ("PASS" if measured["gates"][k] else "FAIL") for k in gates
                },
                "measurements": {
                    physical.METRICS["A"]: leg(measured["A"]),
                    physical.METRICS["D"]: leg(measured["D"]),
                },
                "decision_outcome": measured["decision_outcome"],
            }
        ],
    }
    model = bundle.measurement_from_saved_inference(
        entry,
        registration,
        ctx["inference"],
        gates={k: measured["gates"][k] for k in gates},
        single_call_raw=originals["single_call_raw"],
    )
    return model, benchmark, ctx["identity"], ctx["pinned"]


def _resolve(selected_pack, private_root, entry, copy_hotkey):
    """The subset version's sealed adapter and bank, exactly as `private_evaluation_source.produce_dual_benchmark_input`
    resolves a physical version's."""
    from carbon.scoring import sealed_batch_source

    source_module = _source()
    challenge = entry.get("challenge") if type(entry) is dict else None
    version = entry.get("challenge_version") if type(entry) is dict else None
    if not subset_evidence.is_subset_version(challenge, version):
        raise source_module.PrivateEvaluationSourceRefused(
            "subset_repeat_version_unregistered"
        )
    adapter = source_module._physical_adapter(challenge, version)
    if adapter is None:
        raise source_module.PrivateEvaluationSourceRefused(
            "dual_measurement_producer_unavailable"
        )
    try:
        sealed = sealed_batch_source.resolve(
            challenge=adapter.CHALLENGE,
            version=version,
            selected_pack=selected_pack,
            private_root=private_root,
            development_adapter=adapter,
            copy_hotkey=copy_hotkey,
        )
        if sealed is None:
            raise source_module.PrivateEvaluationSourceRefused(
                "subset_repeat_needs_the_sealed_bank"
            )
        bank, adapter = sealed
        names = physical.input_names(adapter)
    except sealed_batch_source.SealedBankRefused as exc:
        raise source_module.PrivateEvaluationSourceRefused(exc.code) from exc
    except (ImportError, ValueError) as exc:
        if isinstance(exc, source_module.PrivateEvaluationSourceRefused):
            raise
        raise source_module.PrivateEvaluationSourceRefused(
            "dual_native_role_unavailable:development_bank"
        ) from exc
    return adapter, bank, names


def produce_dual_benchmark_input(
    *,
    selected_pack,
    public_root,
    private_root,
    entry,
    trusted_job,
    registration,
    references,
    graph_originals,
    evaluation_source_receipt_raw,
    timing_step,
    copy_hotkey=None,
    single_call_raw=None,
):
    """`private_evaluation_source.produce_dual_benchmark_input` for a subset version: ``(measured model, benchmark,
    actual producer digest)`` (operator tools re-measure a subset grade through this, never the shared path).
    """
    model, benchmark, identity, _pinned = _produce_input(
        selected_pack=selected_pack,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        trusted_job=trusted_job,
        registration=registration,
        references=references,
        graph_originals=graph_originals,
        evaluation_source_receipt_raw=evaluation_source_receipt_raw,
        timing_step=timing_step,
        copy_hotkey=copy_hotkey,
        single_call_raw=single_call_raw,
    )
    return model, benchmark, identity


def _produce_input(
    *,
    selected_pack,
    public_root,
    private_root,
    entry,
    trusted_job,
    registration,
    references,
    graph_originals,
    evaluation_source_receipt_raw,
    timing_step,
    copy_hotkey,
    single_call_raw,
):
    adapter, bank, names = _resolve(selected_pack, private_root, entry, copy_hotkey)
    return produce(
        adapter,
        selected=selected_pack,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        job=trusted_job,
        registration=registration,
        references=references,
        originals=(
            graph_originals
            if single_call_raw is None
            else {**graph_originals, "single_call_raw": single_call_raw}
        ),
        source_raw=evaluation_source_receipt_raw,
        bank=bank,
        interface_names=names,
        timing_step=timing_step,
    )


def produce_registered_dual_measurement(
    *,
    selected_pack,
    public_root,
    private_root,
    entry,
    trusted_job,
    registration,
    references,
    graph_originals,
    evaluation_source_receipt_raw,
    timing_step,
    copy_hotkey=None,
    single_call_raw=None,
):
    """`private_evaluation_source.produce_registered_dual_measurement` for a subset version: the shared receipt builder
    checks the pack under its pinned producer; the receipt then carries the actual producer digest (R-3).
    """
    source_module = _source()
    measured_model, benchmark, identity, pinned = _produce_input(
        selected_pack=selected_pack,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        trusted_job=trusted_job,
        registration=registration,
        references=references,
        graph_originals=graph_originals,
        evaluation_source_receipt_raw=evaluation_source_receipt_raw,
        timing_step=timing_step,
        copy_hotkey=copy_hotkey,
        single_call_raw=single_call_raw,
    )
    prepared = source_module.build_dual_measurement_receipt(
        selected_pack=selected_pack,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        measured_model=measured_model,
        graph_originals=graph_originals,
        evaluation_source_receipt_raw=evaluation_source_receipt_raw,
        benchmark=benchmark,
        producer_digest=pinned,
    )
    if identity == pinned:
        return prepared
    body = json.loads(prepared.raw)
    if (
        body.get("producer_digest") != pinned
        or body.get("measurement_contract", {}).get("producer_digest") != pinned
    ):
        raise source_module.PrivateEvaluationSourceRefused("dual_producer_pin")
    body["producer_digest"] = identity
    body["measurement_contract"] = {
        **body["measurement_contract"],
        "producer_digest": identity,
    }
    raw = source_module._canonical(body)
    if len(raw) > source_module._MAX_RECEIPT_BYTES:
        raise source_module.PrivateEvaluationSourceRefused("dual_receipt_too_large")
    return source_module.PreparedPrivateDualMeasurement(
        raw,
        source_module._sha(raw),
        prepared.evaluation_pack_digest,
        prepared.measured_model,
    )


def bootstrap_total_se(
    adapter,
    *,
    selected,
    public_root,
    private_root,
    entry,
    job,
    registration,
    references,
    originals,
    source_raw,
    bank,
    interface_names,
    exam_key,
    resamples=200,
    report=None,
):
    """`pool_exam_se.bootstrap_total_se` for a subset version: the same target-cluster SE, the grade measured through
    `measure_subset`."""
    from carbon.scoring import pool_exam

    ctx = _inputs(
        adapter,
        selected=selected,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        job=job,
        registration=registration,
        references=references,
        originals=originals,
        source_raw=source_raw,
        bank=bank,
        interface_names=interface_names,
    )
    refused, roles, n, width = ctx["refused"], ctx["roles"], ctx["n"], ctx["width"]
    call_s, outputs_match = _single_call(originals, refused)
    values = ctx["values"]
    capture = {}
    try:
        measure_subset(
            adapter,
            outputs=[list(values[i * width : (i + 1) * width]) for i in range(n)],
            twins=list(ctx["twins"]),
            bank_rows=physical.bank_rows(bank, interface_names),
            definition=ctx["definition"],
            limits=roles["important_limit_definition"],
            objective=roles["design_objective"],
            train_raw=ctx["train_raw"],
            names=interface_names,
            speed_call_seconds=call_s,
            speed_outputs_match=outputs_match,
            capture=capture,
        )
        if report is not None and "accuracy" in capture:
            report["accuracy"] = capture["accuracy"]
        spread, sizes = pool_exam.target_bootstrap_se(
            capture.get("se_basis"), exam_key, resamples=resamples
        )
    except (adapter.Refused, pool_exam.ExamRefused) as exc:
        raise refused(
            getattr(exc, "code", None) or "bootstrap_pool_unmeasurable"
        ) from exc
    if report is not None:
        report["n_targets"] = sizes
    return spread


__all__ = [
    "PROCEDURE",
    "REPEAT_GATES",
    "bootstrap_total_se",
    "gated",
    "measure_subset",
    "produce",
    "produce_dual_benchmark_input",
    "produce_registered_dual_measurement",
    "repeat_holds",
]
