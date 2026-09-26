"""Provider-neutral compute provisioning for miner research campaigns.

DEVELOPMENT infrastructure only: it provisions, observes, accounts for and
tears down compute that a miner's campaign pays for. It carries no scientific,
scoring, qualification or settlement authority.
"""

from .accounting import AccountingSummary, collect_charges, committed_usd, summarize
from .admission import (
    AdmissionDecision,
    GpuFact,
    HostFacts,
    WorkloadDemand,
    admit_concurrency,
    observe_local_host,
)
from .capability import capability_summary
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
    "AccountingSummary",
    "AdmissionDecision",
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
    "GpuFact",
    "HostFacts",
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
    "WorkloadDemand",
    "admit_concurrency",
    "capability_summary",
    "collect_charges",
    "committed_usd",
    "observe_local_host",
    "reconcile",
    "summarize",
]
