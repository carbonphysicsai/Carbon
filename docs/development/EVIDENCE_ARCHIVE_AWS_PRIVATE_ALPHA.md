# C-EA1 AWS private-alpha deployment package

**Status:** unprovisioned DEVELOPMENT implementation package
**Decision:** `C-EA1-D3`
**Profile:** `carbon.alpha-evidence-archive.private.v1`
**Provider profile:** `carbon.alpha-evidence-archive.aws.private.v1`
**Authority ceiling:** package validation and isolated non-secret tests only;
no deployment, recovery acceptance, real acknowledgement, C-EA2, protected
execution, production, network, or LIVE authority

## Recommendation

Use AWS in `us-west-2` for the first private-alpha proposal, subject to the
account owner confirming host proximity, data residency, service availability,
and billing. The package maps Carbon's existing PostgreSQL/object/envelope-key
interfaces directly onto:

- RDS for PostgreSQL 17.11, `db.t4g.micro`, Multi-AZ with one synchronous
  standby, 20 GiB gp3, IAM database authentication and 35 days of point-in-time
  backups;
- S3 Standard with versioning, bucket-owner enforcement, public access blocked,
  customer-managed KMS encryption, and 90-day default compliance Object Lock;
- one customer-managed symmetric KMS key with rotation and context-constrained
  data-key operations;
- a gateway VPC endpoint for S3 and one-AZ interface endpoint for KMS; and
- AWS Backup daily RDS recovery points retained for 90 days.

AWS is selected over GCP Cloud SQL/Cloud Storage/CMEK and Azure Flexible
Server/Blob/Key Vault for this first implementation because the existing
catalogue is already PostgreSQL, S3's conditional create and Object Lock map to
the immutable-object contract, and KMS `GenerateDataKey` maps to Carbon's
existing client-side AES-256-GCM envelope. All three providers have suitable
managed primitives; this is an engineering choice, not a durability or security
qualification.

Primary mechanism references:

- [RDS PostgreSQL Multi-AZ](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html)
- [RDS PostgreSQL 17.11](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-versions.html)
- [S3 Object Lock and versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [KMS GenerateDataKey](https://docs.aws.amazon.com/kms/latest/APIReference/API_GenerateDataKey.html)
- [KMS encryption context](https://docs.aws.amazon.com/kms/latest/developerguide/encrypt_context.html)
- [AWS Backup restore testing](https://docs.aws.amazon.com/aws-backup/latest/devguide/restore-testing.html)

## Package and immutable identities

`deploy/evidence_archive/aws_private_alpha/` contains the CloudFormation
template, database-role migration, dependency/source-use manifest, versioned
deployment manifest, and priced estimate. Generate their exact content
identities without credentials or network access:

```bash
./scripts/dev/cea1_alpha_package.sh package-doctor
```

The command intentionally exits `1`: the package is valid but not deployed and
cannot acknowledge evidence. It reports digests only and never discovers or
prints credentials. The existing configuration-only doctor remains:

```bash
./scripts/dev/cea1_alpha_package.sh configuration-doctor \
  docs/development/evidence_archive_alpha_deployment.example.json
```

That command also remains non-ready by design.

The source-use manifest binds the exact updated `uv.lock` digest and the narrow
roles of `boto3==1.43.56`, its already-compatible `botocore==1.43.56`,
`s3transfer==0.19.2`, `psycopg[binary]==3.3.5`, and
`cryptography==50.0.1`. It preserves their recorded license facts and makes no
new protected-data, commercial-redistribution, or provider-account rights
claim. AWS managed services are configuration dependencies, not vendored code.

## Required external values

Before a plan can be authorized, the operator must supply through the normal
secret/configuration channel—not Git:

| Input | Required value |
|---|---|
| AWS account/project | exact 12-digit account and billing owner |
| region | approve `us-west-2` or prospectively version a different region |
| network | VPC, two private subnets in distinct AZs, route tables, and the exact supervisor security group |
| principals | operator, supervisor, audit, and recovery IAM role ARNs |
| custody | named key administrators and break-glass/recovery principals |
| deployment | stack name, tags, approved change set, budget alarm recipients |
| acceptance | scoped security acceptance reference and authorized recovery-rehearsal identity |

The CloudFormation template generates the RDS administrator secret inside AWS
Secrets Manager. Carbon runtime uses RDS IAM tokens; neither password nor token
belongs in the deployment manifest, CLI output, test evidence, or repository.
The numerical worker receives no AWS, database, KMS, or archive credentials.
The stack creates separate assumable supervisor, ciphertext-audit, and recovery
runtime roles from the supplied principal ARNs. Identity and VPC-endpoint
policies restrict them to the archive prefix, KMS key, and exact RDS database
roles. Catalogue and capacity-journal roles remain non-login PostgreSQL group
roles. No role grants object deletion, key administration, public access, or
worker access; only the named operator principal administers the KMS key.

## Deployment and rollback commands

These commands are a proposal. Do not run them until the owner authorizes the
named account, region, principals, estimated spend, and rehearsal. Use an
already-authenticated operator session; never paste credentials into arguments.

```bash
aws cloudformation validate-template \
  --region us-west-2 \
  --template-body file://deploy/evidence_archive/aws_private_alpha/template.json

aws cloudformation deploy \
  --region us-west-2 \
  --stack-name carbon-alpha-archive \
  --template-file deploy/evidence_archive/aws_private_alpha/template.json \
  --capabilities CAPABILITY_IAM \
  --no-execute-changeset \
  --parameter-overrides file://PRIVATE_OPERATOR_PARAMETER_FILE
```

Review the generated change set, resource shapes, policies, and current AWS
Pricing Calculator result before a separately authorized execution. After RDS
is available, use the generated administrator secret through the approved
operator secret channel to run the existing C-EA1 catalogue migration and the
new alpha-capacity migration, then run `database_roles.sql`. Do not place the
administrator secret in a command line, file, log, or evidence bundle. The
stack outputs the three assumable runtime role ARNs. Bind them respectively to
`carbon_archive_supervisor`, `carbon_archive_audit`, and
`carbon_archive_recovery` through RDS IAM; do not use the administrator for
normal runtime work.

Rollback before activation means reject/delete the unexecuted change set. After
resource creation, disable new archive admission first. CloudFormation deletion
retains the bucket, KMS key and backup vault and snapshots RDS; it does not erase
evidence. An authorized operator must reconcile those retained resources and
costs explicitly:

```bash
aws cloudformation delete-stack \
  --region us-west-2 \
  --stack-name carbon-alpha-archive
```

No runbook command performs bucket emptying, key deletion, global prune, or
automatic evidence deletion.

## Capacity and billing

`PostgresAlphaCapacityLedger` serializes reservations under PostgreSQL and
admits at most one pending evaluation. The 20 GiB logical quota includes both
pending and retained evidence. Transition to `RETAINED` frees the concurrency
slot but never frees logical bytes; only a future authorized retention/deletion
owner may add a removal transition. Failed unacknowledged work may release its
pending reservation while retaining its immutable reservation history.

The logical quota is not a provider billing cap. S3 object versions, RDS
allocated storage, snapshots/backups, logs, KMS/API calls, VPC endpoints and
data transfer are billed separately. A billing alert observes spend; it does
not enforce Carbon admission. The estimate assumes 30 GiB billed S3 storage
(20 GiB logical evidence times a 1.5 version factor), 10,000 PUT and 20,000 GET
requests, one KMS key, one KMS interface endpoint, and 20 GiB of excess RDS
backup contingency.

Current public AWS price-list quantities produce **$39.338/month**, rounded to
**$39.34/month**. Request authorization should use a **$55/month budget** for
unmodelled request, log, version and small-transfer variance. A single test-owned
restore rehearsal is budgeted at **$5 provider cost**, excluding operator time
and any missing VPC/VPN/supervisor-host cost. Exact SKUs, rates, arithmetic and
source URLs are in `cost_estimate.json`; the operator must refresh the estimate
in the target account immediately before authorization.

The recoverable journal for this proposal is the RDS transactional outbox,
archive events, and append-only alpha-capacity events restored with the
catalogue. The accepted SQLite stage journal remains a bounded
pre-acknowledgement spool only. No future real acknowledgement may depend on
that local file: exact S3 version receipts, wrapped KMS data keys, catalogue
rows, outbox state, and capacity history must already be committed and
recoverable. The current code cannot issue such an acknowledgement, so this
rule is not being asserted from package configuration alone.

## Recovery rehearsal

The first rehearsal is destructive only to test-owned restored resources. It
must not touch the source bucket, source RDS instance, production keys, or any
protected/customer data.

1. Freeze a test manifest containing catalogue snapshot/recovery point, exact S3
   object version IDs, KMS key ARN/version state, deployment manifest digest,
   expected entry/manifest/artifact digests, and start time.
2. Start an AWS Backup restore job into a new uniquely named RDS instance in the
   same private subnets. Never overwrite the source.
3. Recreate a fresh supervisor journal from retained catalogue/object state;
   acknowledged entries must not depend on released local spool bytes.
4. Retrieve the exact S3 object versions, recover their data keys through KMS,
   decrypt, and validate every catalogue, manifest and plaintext digest.
5. Confirm capacity ledger, outbox, availability and named-use state, and record
   elapsed restoration time against the 24-hour target.
6. Append a signed, private rehearsal report and security findings. Only the
   authorized acceptance owner may approve it.
7. Delete only the newly restored RDS test instance and its explicitly tagged
   test recovery artifacts after evidence capture.

Suggested non-destructive start/status commands:

```bash
aws backup start-restore-job --region us-west-2 \
  --recovery-point-arn RECOVERY_POINT_ARN \
  --iam-role-arn RECOVERY_ROLE_ARN \
  --resource-type RDS \
  --metadata file://TEST_OWNED_RESTORE_METADATA.json

aws backup describe-restore-job --region us-west-2 --restore-job-id JOB_ID
```

AWS states that restore time has no service SLA. Therefore the 24-hour Carbon
target remains unproved until an authorized rehearsal completes and Carbon
validates restored bytes and dependencies.

## Acknowledgement boundary

The activation contract records separate predicates for well-formed config,
provisioned service identity, authenticated authorization, recoverable object,
catalogue, journal and key dependencies, atomic capacity reservation, integrity,
current permitted use, recovery rehearsal, security acceptance, and deployment
authorization. Passing any subset cannot be promoted.

Even a complete predicate record currently returns
`ACKNOWLEDGEMENT_IMPLEMENTATION_REQUIRED`; it does not issue an
`ArchiveAcknowledgement`, remains false for real acknowledgement and C-EA2, and
cannot finalize or rerun science. C-EA2 stays blocked until an authorized,
provider-observed C-EA1 acknowledgement implementation and C-EA3-owned recovery
evidence exist.
