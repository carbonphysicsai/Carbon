"""Motor registration for challenge-neutral campaign accounting."""

from carbon.design_search import campaign as _campaign

CampaignLedgerError = _campaign.CampaignLedgerError

CAMPAIGN_SCHEMA = "carbon.motor.reference-campaign.v1"
PLAN_SCHEMA = "carbon.motor.decision-reference-plan.v1"
SNAPSHOT_SCHEMA = "carbon.motor.reference-campaign-snapshot.v1"

SCHEMAS = _campaign.CampaignSchemas(
    plan=PLAN_SCHEMA,
    campaign=CAMPAIGN_SCHEMA,
    snapshot=SNAPSHOT_SCHEMA,
)


def _policy(plan):
    return _campaign.validate_plan(plan, SCHEMAS)


class CampaignLedger(_campaign.CampaignLedger):
    def __init__(self, path):
        super().__init__(path, schemas=SCHEMAS)
