"""A closed candidate build refusal: Carbon's lowering or freeze refused the graph.

The build program writes ``refusal.json`` when Carbon's own lowering raises one
of the two closed refusal types after the miner's code produced its model. The
file is written where miner code runs, so the parent treats it as untrusted: a
fixed schema, a bounded size, a code from the registry below (anything else
becomes ``unspecified``) and a bounded identifier for the location (anything
else becomes ``None``). A missing or malformed file is never a refusal; the
failure then keeps its infrastructure meaning.
"""

from __future__ import annotations

import json
import re

SCHEMA = "carbon.development.bundle-build-refusal.v1"
MAX_BYTES = 1024
UNSPECIFIED = "unspecified"
#: Refusal codes Carbon's lowering and freeze raise for a candidate's graph.
CODES = frozenset(
    {
        "aten_arguments_not_supported",
        "aten_input_kind_not_supported",
        "aten_node_kind_not_supported",
        "aten_op_not_allowlisted",
        "aten_op_not_lowered",
        "aten_result_metadata_not_supported",
        "aten_scatter_index_not_static",
        "aten_scatter_index_out_of_bounds",
        "aten_scatter_registered_resource_bound",
        "aten_scatter_shape_or_dtype_not_supported",
        "aten_tuple_index_not_supported",
        "bundle_graph_caps_refused",
        "bundle_graph_invalid",
        "bundle_graph_oversized",
        "bundle_state_oversized",
        "bundle_state_parameter_count_invalid",
        "bundle_state_parameter_invalid",
        "bundle_state_source_invalid",
        "cap_exceeded",
        "constant_bytes_mismatch",
        "constant_dtype_not_allowed",
        "constant_malformed",
        "constant_not_base64",
        "dtype_not_allowed",
        "dynamic_shape",
        "graph_call_cycle",
        "input_names_mismatch",
        "integer_constant_out_of_range",
        "named_function_arity",
        "named_function_not_allowlisted",
        "named_function_refused",
        "op_not_allowed_in_role",
        "op_not_allowlisted",
        "op_not_supported_v0",
        "op_refused",
        "open_constants",
        "oversized_document",
        "parameter_kind_mismatch",
        "parameter_kind_unknown",
        "parameter_not_default",
        "parameters_not_allowlisted",
        "prng_impl_not_allowed",
        "result_count_mismatch",
        "role_mismatch",
        "role_unknown",
        "shape_malformed",
        "value_id_invalid",
        "value_undefined",
    }
)
_LOCATION = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]{0,63}", re.ASCII)


class CandidateBuildRefused(Exception):
    """The candidate's build was refused by Carbon's closed lowering rules."""

    def __init__(self, code: str, at: str | None):
        super().__init__(code if at is None else f"{code} at {at}")
        self.code, self.at = code, at


def parse(raw: bytes) -> tuple[str, str | None] | None:
    """The sanitised (code, at) of a valid refusal file, or None when not one."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    if type(value) is not dict or set(value) != {"schema", "code", "at"}:
        return None
    if value["schema"] != SCHEMA:
        return None
    code, at = value["code"], value["at"]
    if type(code) is not str or code not in CODES:
        code = UNSPECIFIED
    if type(at) is not str or _LOCATION.fullmatch(at) is None:
        at = None
    return code, at
