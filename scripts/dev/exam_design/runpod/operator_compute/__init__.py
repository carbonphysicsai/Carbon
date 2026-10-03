"""RunPod pods on Carbon's own operator account, for Graphite phase 3.

OWNER-MINER-COMPUTE-LINK-ONLY-01 removed this layer from `carbon.compute`:
Carbon never creates, stops, bills or reads rented compute with a miner's
provider key. Its LINKONLY-D1 leaves operator scripts on the operator's own
RunPod account (this directory) unchanged, and the owner chose on 2026-10-03
that Graphite phase 3 keeps one RunPod pod per proposal on Carbon's account
under the phase-3 grant (GRAPHITE-D32). So the layer lives here, operator-side,
with the same semantics it had: a durable intent before every create, an
ownership tag that resolves a lost create response without resending it, a
rate ceiling and deadline bound, verified termination, and the provider's own
charge when it reports one.

Nothing on the miner path imports this package; `carbon.agent_campaign.graphite`
reaches it only from the phase-3 operator runner, as it reaches `pod_control`.
DEVELOPMENT infrastructure only: no scientific, scoring, qualification or
settlement authority.
"""

from .credentials import (
    CredentialProvider,
    CredentialStatus,
    CredentialUnavailable,
    FileCredentialProvider,
    Secret,
)
from .errors import ComputeError, Execution
from .model import (
    CarbonOwnedResource,
    IntentState,
    Offer,
    PodSpec,
    ProvisionRequest,
    ResourceState,
    UserManagedHost,
)
from .provider import BalanceObservation, ComputeProvider
from .reconcile import ReconcileReport, reconcile
from .runpod import RunPodAdapter, UrllibTransport
from .service import ComputeService
from .store import ComputeStore

__all__ = [
    "BalanceObservation",
    "CarbonOwnedResource",
    "ComputeError",
    "ComputeProvider",
    "ComputeService",
    "ComputeStore",
    "CredentialProvider",
    "CredentialStatus",
    "CredentialUnavailable",
    "Execution",
    "FileCredentialProvider",
    "IntentState",
    "Offer",
    "PodSpec",
    "ProvisionRequest",
    "ReconcileReport",
    "ResourceState",
    "RunPodAdapter",
    "Secret",
    "UrllibTransport",
    "UserManagedHost",
    "reconcile",
]
