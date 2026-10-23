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
#: A Carbon capability gap does not count against the miner; the candidate's own construct does.
GAP = "CARBON_CAPABILITY_GAP"
REFUSED = "CANDIDATE_BUILD_REFUSED"
#: Refusal codes Carbon's lowering and freeze raise for a candidate's graph, each with its class
#: (OWNER-BUILD-REFUSAL-SPLIT-01). A new code joins with its class stated; moving a code between
#: classes is a recorded change. Anything not listed is treated as a gap.
CODES = {
    "aten_arguments_not_supported": GAP,
    "aten_input_kind_not_supported": GAP,
    "aten_node_kind_not_supported": GAP,
    "aten_op_not_allowlisted": GAP,
    "aten_op_not_lowered": GAP,
    "aten_result_metadata_not_supported": GAP,
    "aten_index_lowering_expansion_bound": GAP,
    "aten_index_not_static": GAP,
    "aten_index_shape_or_dtype_not_supported": GAP,
    "aten_scatter_index_not_static": GAP,
    "aten_scatter_lowering_expansion_bound": GAP,
    "aten_scatter_shape_or_dtype_not_supported": GAP,
    "aten_tuple_index_not_supported": GAP,
    "constant_dtype_not_allowed": GAP,
    "dtype_not_allowed": GAP,
    "dynamic_shape": GAP,
    "named_function_not_allowlisted": GAP,
    "op_not_allowlisted": GAP,
    "op_not_supported_v0": GAP,
    # F08/F02 graph adapters (Validator, 2026-10-20): a registered training surface the
    # adapter does not serve is Carbon's gap; every other adapter refusal is the candidate's.
    "f02_graph_surface_unserved": GAP,
    "f08_graph_surface_unserved": GAP,
    "allowlist_version_mismatch": REFUSED,
    "aten_index_out_of_bounds": REFUSED,
    "aten_index_registered_resource_bound": REFUSED,
    "aten_scatter_index_out_of_bounds": REFUSED,
    "aten_scatter_registered_resource_bound": REFUSED,
    "bundle_graph_caps_refused": REFUSED,
    "bundle_graph_invalid": REFUSED,
    "bundle_graph_oversized": REFUSED,
    "bundle_state_oversized": REFUSED,
    "bundle_state_parameter_count_invalid": REFUSED,
    "bundle_state_parameter_invalid": REFUSED,
    "bundle_state_source_invalid": REFUSED,
    "cap_exceeded": REFUSED,
    "constant_bytes_mismatch": REFUSED,
    "constant_malformed": REFUSED,
    "constant_not_base64": REFUSED,
    "decoded_graph_state_decoder_invalid": REFUSED,
    "decoded_graph_state_output_invalid": REFUSED,
    "f02_graph_batch_exceeds_train": REFUSED,
    "f02_graph_challenge_version_unregistered": REFUSED,
    "f02_graph_input_invalid": REFUSED,
    "f02_graph_loss_unsupported": REFUSED,
    "f02_graph_nonfinite_state": REFUSED,
    "f02_graph_output_unsupported": REFUSED,
    "f02_graph_procedure_invalid": REFUSED,
    "f02_graph_seed_invalid": REFUSED,
    "f02_graph_train_empty": REFUSED,
    "f02_graph_train_invalid": REFUSED,
    "f02_graph_training_field_invalid": REFUSED,
    "f02_graph_training_value_invalid": REFUSED,
    "f02_graph_untrained": REFUSED,
    "f08_graph_batch_exceeds_train": REFUSED,
    "f08_graph_challenge_version_unregistered": REFUSED,
    "f08_graph_input_invalid": REFUSED,
    "f08_graph_loss_unsupported": REFUSED,
    "f08_graph_nonfinite_state": REFUSED,
    "f08_graph_output_unsupported": REFUSED,
    "f08_graph_procedure_invalid": REFUSED,
    "f08_graph_seed_invalid": REFUSED,
    "f08_graph_train_empty": REFUSED,
    "f08_graph_train_invalid": REFUSED,
    "f08_graph_training_field_invalid": REFUSED,
    "f08_graph_training_value_invalid": REFUSED,
    "f08_graph_untrained": REFUSED,
    "graph_call_cycle": REFUSED,
    "key_dtype_outside_init": REFUSED,
    "input_names_mismatch": REFUSED,
    # A graph whose declared batch differs from its own registered batch_size is the
    # candidate's construct (Validator, 2026-10-21), not a gap Carbon left open.
    "interface_batch": REFUSED,
    "integer_constant_out_of_range": REFUSED,
    "named_function_arity": REFUSED,
    "named_function_refused": REFUSED,
    "op_not_allowed_in_role": REFUSED,
    "op_refused": REFUSED,
    "open_constants": REFUSED,
    "oversized_document": REFUSED,
    "parameter_kind_mismatch": REFUSED,
    "parameter_kind_unknown": REFUSED,
    "parameter_not_default": REFUSED,
    "parameters_not_allowlisted": REFUSED,
    "prng_impl_not_allowed": REFUSED,
    # An op Carbon's own allowlist admits but its interpreter cannot bind.
    "primitive_unsupported": GAP,
    "result_count_mismatch": REFUSED,
    "role_mismatch": REFUSED,
    "role_unknown": REFUSED,
    "shape_malformed": REFUSED,
    "value_id_invalid": REFUSED,
    "value_undefined": REFUSED,
}
_LOCATION = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]{0,63}", re.ASCII)


def outcome(code: str) -> str:
    """The class of a refusal code; unspecified and unregistered codes are gaps, since
    ambiguity is resolved in the miner's favour."""
    return CODES.get(code, GAP)


class CandidateBuildRefused(Exception):
    """The build was refused by Carbon's closed lowering rules (a gap or the candidate's own)."""

    def __init__(self, code: str, at: str | None):
        super().__init__(code if at is None else f"{code} at {at}")
        self.code, self.at = code, at
        self.outcome = outcome(code)


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
