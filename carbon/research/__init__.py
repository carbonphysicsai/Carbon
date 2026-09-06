"""Shared nominal core and bounded discovery for ``carbon_research_v2``."""

from .canonical import (
    MAX_CALL_REPLY_BYTES,
    MAX_DEPTH,
    MAX_RESOURCE_BYTES,
    MAX_TEXT_BYTES,
    MAX_TUPLE_ITEMS,
    CanonicalWireError,
    canonical_bytes,
    canonical_digest,
    load_canonical,
    verify_resource_ref,
)
from .discovery import (
    DiscoveryResourceVersion,
    InMemoryDiscoveryProvider,
    LocalDiscoveryAdapter,
)
from .errors import (
    DiscoveryProviderUnavailable,
    ErrorDetail,
    ResearchServiceError,
    ResearchServiceErrorCode,
    RetryDisposition,
    public_error,
)
from .model import *
from .model import __all__ as _model_exports
from .providers import *
from .providers import __all__ as _provider_exports
from .refs import *
from .refs import __all__ as _ref_exports

__all__ = (  # noqa: PLE0604 - composed from the three explicit string registries
    *_model_exports,
    *_provider_exports,
    *_ref_exports,
    "CanonicalWireError",
    "DiscoveryProviderUnavailable",
    "DiscoveryResourceVersion",
    "ErrorDetail",
    "InMemoryDiscoveryProvider",
    "LocalDiscoveryAdapter",
    "MAX_CALL_REPLY_BYTES",
    "MAX_DEPTH",
    "MAX_RESOURCE_BYTES",
    "MAX_TEXT_BYTES",
    "MAX_TUPLE_ITEMS",
    "ResearchServiceError",
    "ResearchServiceErrorCode",
    "RetryDisposition",
    "canonical_bytes",
    "canonical_digest",
    "load_canonical",
    "public_error",
    "verify_resource_ref",
)
