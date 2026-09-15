# C-EA1 AWS private-alpha deployment and recovery package

**Status:** unprovisioned DEVELOPMENT implementation package
**Decision:** `C-EA1-D4`
**Alpha policy:** `carbon.alpha-evidence-archive.private.v1`
**Provider profile:** `carbon.alpha-evidence-archive.aws.private.v2`
**Superseded unprovisioned profile:** `carbon.alpha-evidence-archive.aws.private.v1`
**Authority ceiling:** offline validation, account-bound change-set preparation,
and an authorized test-owned recovery rehearsal. This repository state creates
no resource, charge, real acknowledgement, protected admission, C-EA2
eligibility, security acceptance, public-network action, or LIVE claim.

## Correctness review disposition

The focused review confirmed six grouped package defects. `ArchiveKey` lacked both
CloudFormation retention attributes; IAM omitted supervisor version reads,
conditioned bucket metadata on an inapplicable prefix, and put `DescribeKey`
behind an encryption-context condition; S3 SSE-KMS and Carbon envelope
cryptography shared a key despite incompatible contexts; the private network
omitted STS, Secrets Manager and Backup API paths; and the runbook claimed stack
deletion despite RDS deletion protection. The 90-day bucket default also did
not implement retention from each exact version's last eligible use or open
obligations.

The review disproved broader interpretations of those concerns. The adapter
already passed `VersionId` on version-specific reads, RDS already used IAM auth
and verified TLS, the bucket and backup vault already had retain policies, and
the template already had a backup service role and Multi-AZ private RDS. No
evidence shows a deployed archive, lost historical evidence, or a historical
acknowledgement: v1 was never provisioned and could not issue a real
acknowledgement.

V2 repairs the confirmed defects without changing the accepted alpha policy:

- both the AWS service-storage key and Carbon envelope key have
  `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain`;
- S3, RDS, the managed master secret and AWS Backup use `StorageKey`; only
  Carbon data-key generation/recovery uses `ArchiveKey` with exact Carbon
  profile/tenant/entry context;
- the audit role can remove S3's storage-encryption layer through S3 only, but
  has no envelope-key permission and therefore receives Carbon ciphertext;
- exact-version reads, retention, and legal-hold calls have matching role and
  endpoint permissions; bucket metadata and `DescribeKey` are separate from
  conditions that do not apply to them;
- restore initiation, restore-service execution, and restored-database access
  are separate roles. `iam:PassRole` is limited to the exact restore service
  role and `backup.amazonaws.com`; the restored RDS resource ID must be added
  prospectively before its recovery login can connect; and
- gateway S3 plus interface KMS, regional STS, Secrets Manager, AWS Backup and
  CloudWatch Logs endpoints provide the declared private runtime API paths.
  Their security group admits only the four supplied execution-location
  security groups.

Only allow-listed, sanitized operational diagnostics may enter the 90-day log
group. Candidate values, object names, manifests, signatures, key contexts and
plaintext are forbidden there. Logs are not an acknowledgement dependency and
cannot substitute for the immutable catalogue/object/journal watermark.

The bound [operation-to-role matrix](../../deploy/evidence_archive/aws_private_alpha/operation_role_matrix.json)
lists each executable call, caller, resource, permission, encryption context,
network path, and expected denial. Its policy tests are structural; only an
authorized deployment can observe account SCPs, permission boundaries, endpoint
availability, service-linked behavior, and actual IAM evaluation.

## Resource recommendation and feasibility

Use AWS `us-west-2`, subject to the account owner confirming locality, account
policy, and actual orderability. PostgreSQL 17.11 is an RDS-supported release,
but exact engine/class/Multi-AZ availability must still be queried in the target
account. The v1 `db.t4g.micro` proposal has 1 GiB memory. AWS documents an
additional 300–1000 MiB requirement for reliable IAM database authentication,
so v2 proposes `db.t4g.medium` (4 GiB) rather than claim unsupported headroom.
One active evaluation remains the Carbon limit; the operator must observe
`FreeableMemory`, connections and PostgreSQL processes during rehearsal. The
template alarms at 1 GiB free memory and 5 GiB free storage; alarms are signals,
not admission rules or spending caps.

The package creates Multi-AZ PostgreSQL 17.11, 20 GiB gp3, 35-day PITR, daily
AWS Backup recovery points retained 90 days, 20 GiB logical Carbon capacity,
versioned S3 Standard with COMPLIANCE Object Lock, and the two retained KMS
keys. Multi-AZ failover addresses an availability event; it is not a backup
restore or a demonstration that all acknowledgement dependencies survived a
lost supervisor host.

Official mechanism references:

- [RDS IAM authentication memory](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html)
- [RDS PostgreSQL releases](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/doc-history.html)
- [RDS DB instance resource identity](https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_DBInstance.html)
- [S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [S3 Bucket Key encryption context](https://docs.aws.amazon.com/AmazonS3/latest/userguide/specifying-kms-encryption.html)
- [KMS encryption context](https://docs.aws.amazon.com/kms/latest/developerguide/encrypt_context.html)
- [AWS Backup service roles](https://docs.aws.amazon.com/aws-backup/latest/devguide/iam-service-roles.html)
- [AWS Backup private endpoint](https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-network.html)
- [AWS PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/)

## Package identities and offline checks

`deploy/evidence_archive/aws_private_alpha/` contains the CloudFormation
template, PostgreSQL roles, source-use record, cost model, role matrix, closed
deployment-input schema/example, and manifest binding them. Run:

```bash
./scripts/dev/cea1_alpha_package.sh package-doctor
./scripts/dev/cea1_alpha_package.sh configuration-doctor \
  docs/development/evidence_archive_alpha_deployment.example.json
```

Both intentionally remain non-ready: the first exits `1` after validating an
unprovisioned package; the second names absent external references without
contacting AWS. The existing alpha policy digest remains
`sha256:e7f9b86943d482ad5c0e92c386a6edf3cdc493049f912c88f7e5a25d5eb6f49c`.
Package-component digests are in `deployment_manifest.json` and must be
recomputed after any change. V1's component digests remain historical and are
not valid approval for v2.

## Account-bound inputs

Copy `deployment_inputs.example.json` outside the repository and replace its
obvious fixture values through the operator's normal configuration channel.
Never put credentials, session tokens, database passwords, private keys, or
secret values in that document. The genuinely missing facts are:

- AWS account/billing owner, approved `us-west-2`, stack name, tenant, and tags;
- VPC, two private subnets in distinct AZs, their route tables, and distinct
  operator/supervisor/audit/recovery security groups;
- the four exact IAM principals and the four private execution locations;
- named KMS administration, break-glass and recovery owners;
- deployment, recovery-rehearsal and corrected spending decisions; and
- later, the observed recovery report and scoped security acceptance.

With an already authorized read-only AWS session, the shortest discovery calls
are:

```bash
aws sts get-caller-identity --query Account --output text
aws ec2 describe-vpcs --region us-west-2 --query 'Vpcs[].VpcId' --output text
aws ec2 describe-subnets --region us-west-2 \
  --filters Name=vpc-id,Values=VPC_ID \
  --query 'Subnets[].[SubnetId,AvailabilityZone,MapPublicIpOnLaunch]' --output table
aws ec2 describe-route-tables --region us-west-2 \
  --filters Name=vpc-id,Values=VPC_ID --query 'RouteTables[].RouteTableId' --output text
aws ec2 describe-security-groups --region us-west-2 \
  --filters Name=vpc-id,Values=VPC_ID --query 'SecurityGroups[].[GroupId,GroupName]' --output table
aws rds describe-orderable-db-instance-options --region us-west-2 \
  --engine postgres --engine-version 17.11 --db-instance-class db.t4g.medium \
  --query 'OrderableDBInstanceOptions[?MultiAZCapable==`true`].[DBInstanceClass,AvailabilityZones[].Name]' --output json
```

These return identifiers, not secrets. If no authorized account context exists,
leave the fields explicit. Do not infer the website host or another project.

## Deployment sequence

These commands are preparation only. Do not execute a change set until the
named account owner authorizes v2, the corrected monthly request, and a
test-owned rehearsal.

1. Validate the local package and replace the fixture deployment inputs.
2. Confirm the caller/account, region, subnet AZs, private DNS, route tables,
   principal boundaries, current service quotas, and the RDS orderability query.
3. Validate the template and create, but do not execute, a change set:

```bash
aws cloudformation validate-template --region us-west-2 \
  --template-body file://deploy/evidence_archive/aws_private_alpha/template.json

aws cloudformation deploy --region us-west-2 \
  --stack-name ACCOUNT_BOUND_STACK_NAME \
  --template-file deploy/evidence_archive/aws_private_alpha/template.json \
  --capabilities CAPABILITY_IAM --no-execute-changeset \
  --parameter-overrides file://ACCOUNT_BOUND_PARAMETER_FILE
```

4. Review resource replacement behavior, endpoint hours, key-retention
   attributes, IAM simulation results, and the current Pricing Calculator
   output. Execute only under separate provisioning authorization, and execute
   the reviewed change set with rollback disabled. CloudFormation retention
   attributes cover stack deletion and replacement, but do not protect a newly
   created resource that CloudFormation removes during an initial failed-create
   rollback. Disabling automatic rollback keeps successfully created keys and
   stores available for inspected, explicit reconciliation.

   ```bash
   aws cloudformation execute-change-set --region us-west-2 \
     --stack-name ACCOUNT_BOUND_STACK_NAME \
     --change-set-name REVIEWED_CHANGE_SET_NAME --disable-rollback
   ```
5. After provisioning, obtain the RDS-managed administrator secret through the
   approved operator channel and run the existing C-EA1 migrations plus
   `database_roles.sql` from the operator security group. Never log or persist
   the administrator secret in Carbon evidence.
6. Bind stack outputs and provider observations into a new deployment identity.
   Run the isolated provider integration and policy-denial checks. This is
   provisional deployment evidence, not an acknowledgement.

The numerical worker never receives AWS, RDS, KMS, signing, or archive
credentials. Runtime clients assume only their named roles through regional STS
and use private DNS. Secrets Manager is for authorized migration/recovery
administration, not ordinary supervisor or worker access.

The package supplies the steady-state private data-plane paths above. The
operator's CloudFormation, IAM, EC2, RDS and pricing control-plane path is an
explicit external account input: use an already approved management station or
existing private management endpoints. The package neither creates nor assumes
NAT/public egress for it, and the cost table excludes any new management-plane
connectivity.

## Retention, rollback, and continuing cost

For every retained S3 `VersionId`, the supervisor advances COMPLIANCE retention
to at least 90 days after the recorded last eligible use. While a receipt,
review, or dispute obligation remains open, it turns on the exact version's
Object Lock legal hold. On obligation closure it first verifies the last-use
retention deadline and only then removes the hold. COMPLIANCE retention cannot
be shortened. Failed calls leave the entry unavailable for acknowledgement and
must be reconciled; a bucket creation-time default is not sufficient evidence.

Before provisioning, rollback means delete the unexecuted change set. Initial
creation uses `--disable-rollback`; a failed create is inspected and reconciled
rather than automatically deleting a key or store. After creation, disable new
admission and reconcile every obligation before any destructive request.
`Catalogue.DeletionProtection=true` means a direct stack delete is expected to
fail rather than remove RDS. A separately approved change set must first turn
deletion protection off; the stack's `DeletionPolicy` then creates a final RDS
snapshot. Stack deletion retains the Object-Locked bucket, both KMS keys, and
backup vault. Retained recovery points can also prevent vault deletion. Deleting
the stack does not erase evidence, end retention, or stop all charges, and
aliases/endpoints/roles removed with the stack must be recreated or recorded
before recovery.

The following commands are deliberately not authorized by this document; they
show the reviewed order:

```bash
# 1. reviewed update: Catalogue.DeletionProtection false (only after obligations permit)
# 2. then, and only then:
aws cloudformation delete-stack --region us-west-2 --stack-name ACCOUNT_BOUND_STACK_NAME
aws cloudformation wait stack-delete-complete --region us-west-2 --stack-name ACCOUNT_BOUND_STACK_NAME
# 3. inventory retained bucket versions, both key ARNs, RDS snapshot and recovery points
```

No package command empties a bucket, schedules a key deletion, deletes a
recovery point, prunes global resources, or treats continuing cost as cleanup.

## Recoverable acknowledgement watermark

Immediately before any future eligible acknowledgement, freeze a watermark
over the latest committed acknowledgement set. It includes the exact catalogue
recovery point and commit sequence, journal and outbox state, alpha-capacity
sequence, acknowledgement/manifest/signature references, every required S3 key
and `VersionId`, ciphertext/plaintext digests, wrapped envelope-key digest,
envelope-key ARN and encryption-context digest, plus the deployment-manifest
digest. The recovery observation must meet or exceed all sequences and contain
the entire exact object-version and key set. An older internally consistent
subset fails.

`carbon.evidence_archive.alpha_recovery` provides closed, bounded watermark and
observation parsers and reports explicit missing/mismatched dependencies. Run
it after an authorized test-owned restore:

```bash
./scripts/dev/cea1_alpha_package.sh recovery-doctor \
  PRIVATE_FROZEN_WATERMARK.json PRIVATE_RECOVERY_OBSERVATION.json
```

A zero exit means only that the supplied observation matches the frozen
watermark. Its report remains false for real acknowledgement and C-EA2. Raw
manifests, signatures, object names, candidate values, and key context belong in
the private evidence channel, not public logs or Hub output.

## Recovery rehearsal sequence and fault claims

The first destructive rehearsal is confined to explicitly tagged test-owned
restored resources and requires separate authorization.

1. Freeze the watermark and an idempotency token before starting restore.
2. Select a tagged recovery point from the retained vault. The recovery-control
   role calls `StartRestoreJob` and passes only `BackupRestoreServiceRole`.
3. Restore to a new unique RDS identifier in the private subnets. Never replace
   the source catalogue.
4. After AWS returns the restored `DbiResourceId`, prepare and execute a reviewed
   stack update setting only `RestoredCatalogueResourceId`. This adds the exact
   `rds-db:connect` ARN for `carbon_archive_recovery`; a wildcard restored DB
   permission is not present.
5. From the recovery security group, connect over verified TLS/IAM, verify the
   schema/commit/journal/outbox/capacity watermark, fetch each exact S3 version,
   recover each Carbon envelope key, decrypt, and verify every digest.
6. Run `recovery-doctor`, retain actual elapsed time and provider events, and
   record failures. A pass is provisional C-EA1/C-EA3 prerequisite evidence;
   the 24-hour target is not qualified until its owner accepts the rehearsal.
7. Remove the temporary connection policy by resetting
   `RestoredCatalogueResourceId` to empty. Only after evidence capture and a
   separate destructive-test authorization, delete the specifically tagged
   restored DB. Never touch the source DB, bucket versions, keys, or vault.

Suggested non-destructive start/status calls:

```bash
aws backup start-restore-job --region us-west-2 \
  --recovery-point-arn EXACT_TAGGED_RECOVERY_POINT_ARN \
  --iam-role-arn EXACT_BACKUP_RESTORE_SERVICE_ROLE_ARN \
  --resource-type RDS --idempotency-token FROZEN_TEST_TOKEN \
  --metadata file://TEST_OWNED_RESTORE_METADATA.json
aws backup describe-restore-job --region us-west-2 --restore-job-id EXACT_JOB_ID
```

Fault-claim boundaries are explicit:

| Test | What it demonstrates | What it does not demonstrate |
|---|---|---|
| RDS Multi-AZ failover | managed standby availability for the catalogue | backup restore, lost-host recovery, object/key recovery |
| Carbon process restart | durable replay against still-available services | provider or host loss |
| AWS Backup restore plus watermark verification | recovery of the frozen acknowledged dependency set after the declared supervisor-host-loss setup | correlated account/region/provider loss, independent security, protected admission |

## Cost and authorization delta

Rates were refreshed from AWS public price lists on 2026-09-15. Detailed SKUs,
quantities, URLs and arithmetic are in `cost_estimate.json`.

| View | Monthly estimate | Meaning |
|---|---:|---|
| Incremental archive | $140.628 | RDS medium Multi-AZ, storage, S3/version factor, two keys, five one-AZ interface endpoints, backup contingency, secret and alarms; existing VPC/execution host |
| Complete | $155.022 | incremental view plus one on-demand Linux `t4g.small` supervisor-equivalent, 20 GiB gp3 and 1 GiB/month log assumptions |
| Corrected authorization request | $175.00 | proposed ceiling for the complete design; not authorized |
| Retained after rollback | $6.49 | illustrative monthly S3 versions, both keys and 40 GiB combined recovery-point/snapshot storage; actual lifecycle can be higher |

The prior **$55/month** and **$5/rehearsal** remain historical proposals, not
authorization. The current calculated eight-hour restore estimate is **$1.15**;
the requested rehearsal allowance remains **$5** for provider variance. The
monthly request increases because v2 replaces the memory-inadequate micro,
adds a second custody key, and supplies the previously omitted STS, Secrets
Manager, Backup and CloudWatch Logs private endpoints. A budget notification observes spend and
cannot enforce the 20 GiB Carbon logical quota. Object versions, backups,
endpoint hours, requests, logs, transfer and retained resources are billed
outside that quota.

## Acknowledgement and C-EA2 boundary

The existing `ArchiveAcknowledgement` and `EvidenceArchive` remain permanently
closed to the synthetic profile. `alpha_activation` remains a non-issuing
predicate assessment. A provider-backed issuer is not dependency-ready in this
unprovisioned ticket state because there is no provider service identity,
account authorization, observed full-watermark recovery, scoped security
acceptance, or authorized production/testnet signer custody. Adding fixture
references would only create a false real-acknowledgement path.

The non-circular ordered path is:

```text
account/spend/rehearsal authorization
-> test-owned provisioning and provider policy tests
-> frozen-watermark recovery rehearsal
-> retained C-EA3-owned recovery evidence and scoped security assessment
-> separately selected C-EA1 real-issuer implementation/activation at that exact deployment
-> eligible real C-EA1 acknowledgement
-> C-EA2 selection
```

C-EA2 may be selected only after the exact provider profile has an authorized
issuer and an acknowledgement whose object, catalogue, journal, key, capacity,
integrity, current-use, recovery, security and deployment predicates all point
to observed, accepted evidence. A signature, upload, database commit, green CI,
or provisional rehearsal comparison is insufficient.
