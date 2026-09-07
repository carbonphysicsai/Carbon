"""Private, offline-only lossy PriorPack v2 to frozen v1 projection.

This adapter deliberately lives outside ``carbon.research`` so the v2 runtime
does not acquire a dependency on the frozen v1 service.  It defines no
provider, route, publication authority, or activation path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum

from carbon.mcp.model import (
    PriorDirective,
    PriorDirectiveKind,
    PriorRef,
    PublishedPrior,
)
from carbon.registry import validate_version
from carbon.research.model import (
    CounterevidenceNoneFound,
    PriorAction,
    PriorGuidanceKind,
    PriorPack,
)
from carbon.research.prior_store import prior_pack_ref
from carbon.research.refs import PriorPackRef

_PROJECTION_DOMAIN = b"carbon.prior-projection.v2-to-v1\x00"
_V1_KIND = {
    PriorGuidanceKind.STEER: PriorDirectiveKind.STRUCTURAL_STEER,
    PriorGuidanceKind.AVOID: PriorDirectiveKind.AVOID,
    PriorGuidanceKind.EXPLORE: PriorDirectiveKind.EXPLORE,
    PriorGuidanceKind.INSUFFICIENT_EVIDENCE: PriorDirectiveKind.NOT_INCLUDED,
}


def _private_bytes(value: object) -> bytes:
    def primitive(item: object) -> object:
        if item is None or type(item) in (str, int, float, bool):
            return item
        if isinstance(item, Enum):
            return item.value
        if type(item) is tuple:
            return [primitive(child) for child in item]
        if is_dataclass(item):
            return {
                field.name: primitive(getattr(item, field.name))
                for field in fields(item)
            }
        raise TypeError("unsupported private projection value")

    return json.dumps(
        primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


@dataclass(frozen=True, slots=True)
class PriorProjectionReceipt:
    source_prior_pack_ref: PriorPackRef
    mapping_version: str
    omitted_item_ids: tuple[str, ...]
    output_hash: str

    def __post_init__(self) -> None:
        validate_version(self.mapping_version)
        if self.omitted_item_ids != tuple(sorted(self.omitted_item_ids)):
            raise ValueError("projection omissions must be sorted")
        if not self.output_hash.startswith("sha256:") or len(self.output_hash) != 71:
            raise ValueError("projection output hash must be tagged SHA-256")


@dataclass(frozen=True, slots=True)
class PrivatePriorProjection:
    published_prior: PublishedPrior
    receipt: PriorProjectionReceipt


def project_v2_to_v1_private(
    pack: PriorPack, *, mapping_version: str = "1.0"
) -> PrivatePriorProjection:
    """Project only representable items; return private bytes-bound evidence."""

    validate_version(mapping_version)
    source_ref = prior_pack_ref(pack)
    directives: list[PriorDirective] = []
    omitted: list[str] = []
    for item in pack.items:
        if (
            item.intervention.action
            not in {PriorAction.ENABLE, PriorAction.DISABLE, PriorAction.COMPARE}
            or len(item.expected_outcomes) != 1
            or type(item.counterevidence_and_applicability) is CounterevidenceNoneFound
        ):
            omitted.append(item.item_id)
            continue
        anchor = (
            item.intervention.baseline_ref
            or item.intervention.from_ref
            or item.intervention.to_ref
            or "not_applicable"
        )
        directives.append(
            PriorDirective(
                _V1_KIND[item.kind],
                item.intervention.surface_id,
                (
                    item.intervention.action.value.lower(),
                    anchor,
                    item.expected_outcomes[0].direction.value.lower(),
                ),
            )
        )
    projected = PublishedPrior(
        "1.0",
        PriorRef(
            pack.challenge_key,
            pack.prior_id,
            pack.prior_version,
            source_ref.content_hash,
        ),
        tuple(directives),
    )
    payload = _private_bytes(projected)
    receipt = PriorProjectionReceipt(
        source_ref,
        mapping_version,
        tuple(sorted(omitted)),
        "sha256:" + hashlib.sha256(_PROJECTION_DOMAIN + payload).hexdigest(),
    )
    return PrivatePriorProjection(projected, receipt)


__all__ = (
    "PriorProjectionReceipt",
    "PrivatePriorProjection",
    "project_v2_to_v1_private",
)
