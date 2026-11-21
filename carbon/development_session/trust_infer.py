"""The self-trust inference program variant (SELF_TRUST DESIGN_v2, H3f; door-code 07:54:24Z and 08:10:59Z).

A candidate that DECLARES self-trust (its recipe's output binds the version's trust interface) returns `W + k` columns from
its graph: the W physics columns and k trust columns. The graded inference container splits them at ONE place, so nothing
downstream of the container ever sees the wider tensor:

* the raw output must be `(n, W + k)`: any other shape, dtype kind or non-finite value is the SAME refusal text as today
  ("bundle inference output contract differs"), so `auto_retry`'s marker and every failure class are unchanged;
* the first W columns become `predictions.json` exactly as today (the existing contract check then runs on them, unchanged);
* the last k columns become `sigma.json` (the trust columns as the graph returned them: the reader decides what they mean);
  the receipt names its digest (`sigma_digest`) and `trust_outputs`.

Two program families offer it, each derived from a version's OWN program by anchored replacement (every anchor must occur
exactly once, else the derivation refuses):

* the plain bundle/graph program (`bundle_construction_worker.INFER_PROGRAM`): the split follows the raw result;
* the graph route v2 ENSEMBLE program (`direct_graph_construction_worker.PHYSICAL_V2_INFER_PROGRAM` and its compiled form): every
  member's output is W + k wide. The members' PHYSICS columns (the first W) are combined by the registered weights exactly as
  today; the k trust columns come from the ONE trust member (member 0, combine weight 1: a weighted mean of sigma is not a sigma
  of the weighted mean, door-code 04:34:35Z); the split happens BEFORE the decoder, which therefore touches the W physics
  columns only (the trust columns are not standardised targets).

It is selected only for a trust candidate of a version whose Spec offers a trust interface
(`direct_graph_construction_worker.v2_trust_infer_query`); every other program's text is untouched, so no other version's
graded-program digest moves. The container reads `control["trust_outputs"]` (k, set by `_infer_state`).
"""

from __future__ import annotations

# -- the part common to both families: write sigma.json and name it in the receipt ----------------------------------------
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

# -- the split of a raw (n, W + k) result: shared text, placed by each family --------------------------------------------------
_SPLIT = """trust_k = control.get("trust_outputs", 0)
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

# -- family 1: the plain program -----------------------------------------------------------------------------------------------
_RESULT = "result = np.asarray(outputs[0])\n"
_RESULT_TRUST = _RESULT + _SPLIT

PLAIN_ANCHORS = (
    (_RESULT, _RESULT_TRUST),
    (_WRITE, _WRITE_TRUST),
    (_DIGEST, _DIGEST_TRUST),
)

# -- family 2: the graph route v2 ensemble program (it already decodes the result: `* decoder_sd + decoder_mu`) -----------------
_V2_PARAMETERS = "parameters = list(members[0])\n"
_V2_PARAMETERS_TRUST = (
    _V2_PARAMETERS + "width = int(np.asarray(decoder_mu).shape[-1])\n"
)

_V2_TOTAL = "    total = None\n"
_V2_TOTAL_TRUST = "    total = None\n    trust = None\n"

_V2_COMBINE = """        term = produced[0] * jnp.asarray(weights)
        total = term if total is None else total + term
    return [total]
"""
_V2_COMBINE_TRUST = """        term = produced[0][..., :width] * jnp.asarray(weights)
        total = term if total is None else total + term
        if trust is None:
            trust = produced[0][..., width:]
    return [jnp.concatenate([total, trust], axis=-1)]
"""

_V2_RESULT = "result = np.asarray(outputs[0]) * decoder_sd + decoder_mu\n"
_V2_RESULT_TRUST = (
    "result = np.asarray(outputs[0])\n"
    + _SPLIT
    + "result = result * decoder_sd + decoder_mu\n"
)

# the trust candidate's state is the trust ensemble state (graph W + k, decoder and combine W): its loader replaces v2's
_V2_LOAD = "from carbon.development_session.physical_graph_state_v2 import load\n"
_V2_LOAD_TRUST = "from carbon.development_session.physical_graph_state_v3 import load\n"

V2_ANCHORS = (
    (_V2_LOAD, _V2_LOAD_TRUST),
    (_V2_PARAMETERS, _V2_PARAMETERS_TRUST),
    (_V2_TOTAL, _V2_TOTAL_TRUST),
    (_V2_COMBINE, _V2_COMBINE_TRUST),
    (_V2_RESULT, _V2_RESULT_TRUST),
    (_WRITE, _WRITE_TRUST),
    (_DIGEST, _DIGEST_TRUST),
)

#: Kept for callers that name the original plain set.
ANCHORS = PLAIN_ANCHORS


def anchors_for(program: str):
    """The anchor set of the family this program belongs to: the v2 ensemble program (it decodes its result) or the plain
    one; a program that is neither, or is already a trust program, is refused."""
    if type(program) is not str:
        raise RuntimeError("trust program: not a program text")
    if "trust_k" in program:
        raise RuntimeError("trust program: already a trust program")
    if program.count(_V2_RESULT) == 1:
        return V2_ANCHORS
    if program.count(_RESULT) == 1:
        return PLAIN_ANCHORS
    raise RuntimeError("trust program anchor moved")


def trust_program(program: str) -> str:
    """The trust variant of one inference program text; refuses when an anchor is not present exactly once."""
    anchors = anchors_for(program)
    for old, _new in anchors:
        if program.count(old) != 1:
            raise RuntimeError("trust program anchor moved")
    for old, new in anchors:
        program = program.replace(old, new)
    return program
