# GOAL-WORKBENCH-09 private deployment proposal

Status: `PREPARED_NOT_PROVISIONED_NOT_AUTHORIZED_FOR_CUSTOMER_COLLECTION`

Recommended bounded target: reuse the existing Cloudflare account and website
stack, but mount the team receiver behind named-user Cloudflare Access. Use one
private Worker and one approved durable persistence binding. Keep the public
Ask Carbon and homepage routes unchanged.

The implementation contract is already testable locally:

- reviewed package v1 input, 120 KB maximum;
- exact idempotency key plus raw/canonical content identities;
- persist inquiry and transactional outbox before receipt;
- optimistic `If-Match` revision updates;
- receiver/reviewer/data-steward/notification-operator roles;
- authenticated read/update/export/delete;
- no files, geometry, executable content or URL fetching;
- failed notification retains the inquiry and pending event;
- public Submit remains disabled.

Owner inputs still required before provisioning or live collection:

| Decision | Recommended choice | Blocks |
|---|---|---|
| Private target/store | existing Cloudflare account; Access + one D1/DO binding | deployment |
| Staff identities | named principals mapped to least-privilege roles | customer-record access |
| Notification | one staff destination and authorized sender | staff alert only; not durable receipt |
| Retention/deletion | explicit period plus data-steward procedure | live intake |
| Notice/permissions | reviewed inquiry notice; optional learning separate | public collection |
| Incident/rollback | named operator; disable Worker route and preserve store | production operation |
| Incremental cost | review actual Cloudflare storage/request estimate | paid provisioning |

No secret belongs in source, an issue, a client export or chat. A shared staging
password is not the proposed customer-record control.
