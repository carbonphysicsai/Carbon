"""The self-trust inference program variant (SELF_TRUST DESIGN_v2, H3f; door-code 07:54:24Z).

A candidate that DECLARES self-trust (its recipe's output binds the version's trust interface) returns `W + k` columns from
its graph: the W physics columns and k trust columns. The graded inference container splits them at ONE place, so nothing
downstream of the container ever sees the wider tensor:

* the raw output must be `(n, W + k)`: any other shape, dtype kind or non-finite value is the SAME refusal text as today
  ("bundle inference output contract differs"), so `auto_retry`'s marker and every failure class are unchanged;
* the first W columns become `predictions.json` exactly as today (the existing contract check then runs on them, unchanged);
* the last k columns become `sigma.json`; the receipt names its digest (`sigma_digest`) and `trust_outputs`.

`trust_program(program)` derives the variant from a version's own inference program by anchored replacement (each anchor
must occur exactly once, else the derivation refuses), so it composes with whichever plain or compiled program that
version already runs. It is selected only for a trust candidate of a version whose Spec offers a trust interface
(`direct_graph_construction_worker.v2_infer_query`); every other program's text is untouched, so no other version's
graded-program digest moves. The container reads `control["trust_outputs"]` (k, set by `_infer_state`); with it absent the
variant behaves exactly as the plain program.
"""

from __future__ import annotations

_RESULT = "result = np.asarray(outputs[0])\n"
_RESULT_TRUST = """result = np.asarray(outputs[0])
trust_k = control.get("trust_outputs", 0)
sigma = None
if trust_k:
    expected = control["expected_output_shape"]
    if (result.ndim != len(expected)
            or list(result.shape[:-1]) != expected[:-1]
            or result.shape[-1] != expected[-1] + trust_k
            or result.dtype.kind not in "fiu" or not np.isfinite(result).all()):
        raise ValueError("bundle inference output contract differs")
    sigma = np.ascontiguousarray(result[..., expected[-1]:])
    result = np.ascontiguousarray(result[..., :expected[-1]])
"""

_WRITE = '(out / "predictions.json").write_bytes(body)\n'
_WRITE_TRUST = """(out / "predictions.json").write_bytes(body)
if sigma is not None:
    sigma_body = json.dumps(sigma.tolist(), allow_nan=False, separators=(",", ":")).encode()
    (out / "sigma.json").write_bytes(sigma_body)
"""

_DIGEST = """    "predictions_digest": digest(body),
}
"""
_DIGEST_TRUST = """    "predictions_digest": digest(body),
}
if sigma is not None:
    receipt["sigma_digest"] = digest(sigma_body)
    receipt["trust_outputs"] = trust_k
"""

ANCHORS = ((_RESULT, _RESULT_TRUST), (_WRITE, _WRITE_TRUST), (_DIGEST, _DIGEST_TRUST))


def trust_program(program: str) -> str:
    """The trust variant of one inference program text; refuses when an anchor is not present exactly once."""
    if type(program) is not str:
        raise RuntimeError("trust program: not a program text")
    if "trust_k" in program:
        raise RuntimeError("trust program: already a trust program")
    for old, _new in ANCHORS:
        if program.count(old) != 1:
            raise RuntimeError("trust program anchor moved")
    for old, new in ANCHORS:
        program = program.replace(old, new)
    return program
