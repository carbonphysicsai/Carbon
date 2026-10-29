"""The exam-total standard error of a pool-graded version (Validator ruling, 2026-10-29; exam-refresh audit gap 2).

`physical_dual_pack.bootstrap_total_se` resamples the bank's cases and refuses pool versions. A pool version's
independent unit is the TARGET (a fresh draw brings new targets with their pools and A_gen points), so its SE is a
cluster bootstrap over targets of the final pool total (`pool_exam.target_bootstrap_se`). This module sits beside
`physical_dual_pack` rather than inside it: that file is part of every producer digest, and an SE is operator
evidence, not part of any grade. Nothing here reaches a miner surface; the only output is the operator's
`exam-total-se.json` sidecar (`exam_rotation`).
"""

from __future__ import annotations

from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import pool_exam


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
    """The target-cluster SE of one retained model's pool exam total, or a typed refusal.

    The model is measured once more with the per-target decomposition captured (the optimiser's queries are reads
    of the model's table, so this is cheap); then targets are resampled within each set. ``report`` (a dict)
    receives ``n_targets``, one count per set. Typed refusals: ``gated`` (a gate failed, so no total) and
    ``too_few_targets`` (fewer than four in a set)."""
    from carbon.development_session import single_call_timing

    ctx = physical._inputs(
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
    try:
        call_s, outputs_match = single_call_timing.read_side_file(
            originals.get("single_call_raw")
        )
    except single_call_timing.SingleCallRefused as exc:
        raise refused("single_call_evidence_unavailable") from exc

    def rows_of(flat):
        return [list(flat[i * width : (i + 1) * width]) for i in range(n)]

    capture = {}
    try:
        adapter.measure(
            bank_rows=physical.bank_rows(bank, interface_names),
            outputs=rows_of(ctx["values"]),
            repeats=[rows_of(r) for r in ctx["repeats"]],
            definition=ctx["definition"],
            limits=roles["important_limit_definition"],
            objective=roles["design_objective"],
            train_raw=ctx["train_raw"],
            names=interface_names,
            speed_call_seconds=call_s,
            speed_outputs_match=outputs_match,
            capture=capture,
        )
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
