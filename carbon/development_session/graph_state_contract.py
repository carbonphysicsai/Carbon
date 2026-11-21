"""Closed graph serialization identities, shared without numerical imports.

The codecs own numeric validation. Recognizing a serialization schema grants
no source authenticity, execution, scientific admission or qualification.
"""

GRAPH_SOURCE_STATE_SCHEMA = "carbon.development.graph-source-state.v1"
GRAPH_ENSEMBLE_STATE_SCHEMA = "carbon.development.graph-ensemble-state.v1"
#: A self-trust version's ensemble state (SELF_TRUST H3d-2a, `physical_graph_state_v3`): graph W + k wide, decoder and combine W.
GRAPH_ENSEMBLE_TRUST_STATE_SCHEMA = "carbon.development.graph-ensemble-trust-state.v1"
GRAPH_SOURCE_STATE_SCHEMAS = (
    GRAPH_SOURCE_STATE_SCHEMA,
    GRAPH_ENSEMBLE_STATE_SCHEMA,
    GRAPH_ENSEMBLE_TRUST_STATE_SCHEMA,
)
