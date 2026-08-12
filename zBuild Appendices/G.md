# Appendix G: Operational Runbook

**Purpose:** This document specifies the complete operational procedures, incident response runbooks, maintenance procedures, backup/disaster recovery, security incident response, and communication protocols for the Hydrogen subnet operations team. This is the operational handbook for running the subnet in production.

---

# Appendix G: Operational Runbook v2.1

---

## G.1 Service Level Objectives (SLOs)

```yaml
# slo.yaml

slo_definitions:
  api_availability:
    target: 99.9%
    measurement_window: 30d
    error_budget: 43.2 minutes/month
    
  api_latency_p99:
    targets:
      GET /challenges: 200ms
      GET /baseline: 100ms
      GET /priors: 300ms
      POST /submit: 500ms
    measurement_window: 5m
    
  challenge_completion_rate:
    target: 99%
    measurement_window: 30d
    definition: "Challenges that complete scoring and distribute rewards"
    
  validator_uptime:
    target: 99.5%
    measurement_window: 30d
    per_validator: true
    
  scoring_consensus_rate:
    target: 99%
    measurement_window: 30d
    definition: "Challenges where ≥3 validators reach median consensus"
    
  specialist_promotion_rate:
    target: 80%
    measurement_window: 30d
    definition: "Specialists passing gauntlet / total distilled"
    
  landscape_baseline_improvement:
    target: ">0.02 log-improvement/challenge avg over 30 challenges"
    measurement_window: rolling 30 challenges

error_budget_policies:
  api_availability:
    at_25%_budget: "Alert on-call, investigate"
    at_50%_budget: "Page on-call, halt non-critical deployments"
    at_75%_budget: "Freeze all non-hotfix deployments"
    at_100%_budget: "Incident declared, all hands"
    
  validator_uptime:
    below_99%: "Alert validator operator"
    below_95%: "Reduce validator weight, alert owner"
    below_90%: "Slash validator, remove from active set"
```

---

## G.2 Incident Response Procedures

### G.2.1 Incident Classification

```yaml
severity_levels:
  SEV-1 (Critical):
    definition: "Subnet non-functional, rewards not distributing, chain halted"
    examples:
      - Chain halted / not producing blocks
      - Rewards not distributing for >2 challenges
      - >50% validators offline
      - Consensus failure on >3 consecutive challenges
    response_time: 15 minutes
    escalation: Page on-call + owner + core team
    communication: Status page + Discord announcement within 30 min
    
  SEV-2 (High):
    definition: "Major functionality degraded, rewards delayed"
    examples:
      - API unavailable >15 min
      - >30% validators offline
      - Scoring consensus failing on 2+ challenges
      - Indexer stuck >100 blocks
    response_time: 30 minutes
    escalation: Page on-call
    communication: Status page update within 1 hour
    
  SEV-3 (Medium):
    definition: "Minor degradation, workaround exists"
    examples:
      - API latency >2x SLO
      - Single validator offline
      - Indexer lag >50 blocks
      - Dashboard showing stale data
    response_time: 2 hours
    escalation: Assign to team member
    communication: Internal note, status page if user-facing
    
  SEV-4 (Low):
    definition: "Minor issue, no user impact"
    examples:
      - Dashboard typo
      - Non-critical metric missing
      - Documentation outdated
    response_time: Next business day
    escalation: Create ticket
    communication: Internal only
```

---

### G.2.2 Incident Response Runbooks

#### RUNBOOK-001: Chain Halted / Not Producing Blocks

```markdown
# RUNBOOK-001: Chain Halted / Not Producing Blocks

## Symptoms
- No new blocks for >5 minutes
- Subtensor RPC returns "block not found" for recent heights
- Validators unable to submit scores

## Diagnosis Steps
1. Check subtensor process status: `systemctl status subtensor` or `docker ps`
2. Check subtensor logs: `docker logs hydrogen-subtensor --tail 100`
3. Check peer count: `curl -s http://localhost:9933 | jq '.peers'`
4. Check disk space: `df -h /data`
4. Check memory: `free -h`

## Common Causes & Fixes

### Database Corruption
```bash
# Stop subtensor
docker stop hydrogen-subtensor

# Backup database
cp -r /data/subtensor /data/subtensor.backup.$(date +%s)

# Rebuild database
docker run --rm -v hydrogen_subtensor_data:/data \
  paritytech/substrate:latest \
  substrate purge-chain --chain local -y

# Restart
docker start hydrogen-subtensor
```

### Out of Memory
```bash
# Check memory
free -h
docker stats hydrogen-subtensor

# Increase swap
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Add to /etc/fstab for persistence
echo "/swapfile none swap sw 0 0" >> /etc/fstab
```

### Peer Connection Issues
```bash
# Check firewall
ufw status
# Ensure 30333/tcp open

# Add bootnodes
docker restart hydrogen-subtensor
# Add --bootnodes flag to command
```

### Disk Full
```bash
# Check disk
df -h

# Clean old logs
journalctl --vacuum-time=7d
docker system prune -a --volumes -f

# Prune old blocks (if safe)
# Only if chain is not halted
```

### Post-Recovery Verification
1. Verify block production: `curl -s http://localhost:9933 | jq '.blockNumber'`
2. Check peer count > 5
2. Verify API responding: `curl http://localhost:8000/health`
3. Verify indexer syncing: Check indexer logs
4. Monitor for 30 minutes before closing

## Escalation
- If not resolved in 30 min → SEV-1 escalation to core team
- If database corruption → Consider chain rollback (last resort)
```

---

#### RUNBOOK-002: Validator Offline / Scoring Failure

```markdown
# RUNBOOK-002: Validator Offline / Scoring Failure

## Symptoms
- Validator not submitting scores
- Scoring consensus failing (insufficient validators)
- Challenge stuck in "SCORING" status

## Diagnosis
1. Check validator container: `docker ps | grep validator`
2. Check validator logs: `docker logs hydrogen-validator-pino --tail 200`
3. Check GPU: `nvidia-smi`
3. Check disk: `df -h /workspace/output`
3. Check API connectivity: `curl http://api:8000/health`

## Common Issues & Fixes

### OOM During Training
```bash
# Check memory
docker stats hydrogen-validator-pino

# Reduce batch size in strategy JSON
# "batch_size": 8 (was 16)

# Enable gradient checkpointing
# Add to strategy: "gradient_checkpointing": true

# Restart validator
docker restart hydrogen-validator-pino
```

### GPU Not Available
```bash
# Check GPU
nvidia-smi

# Check Docker GPU access
docker run --rm --gpus all nvidia/cuda:12.4-base nvidia-smi

# Fix: Restart Docker daemon
systemctl restart docker

# Or: Add --gpus all to docker run
```

### OOM on Stress Test
```bash
# Reduce stress test batch size
# Modify validator code: stress_batch_size = 4

# Or: Increase swap
fallocate -l 8G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
```

### Container Crashed
```bash
# Check exit code
docker inspect hydrogen-validator-pino --format '{{.State.ExitCode}}'

# Check logs
docker logs hydrogen-validator-pino --tail 100

# Restart
docker restart hydrogen-validator-pino
```

### Stuck in Scoring
```bash
# Check challenge status
curl http://api:8000/api/v1/challenges/{challenge_id}

# If stuck in SCORING > 4 hours:
# 1. Check validator logs
# 2. Restart stuck validators
# 3. If <3 validators, challenge may need manual intervention

# Manual score submission (emergency):
# Owner submits scores via extrinsic
```

### Post-Fix Verification
1. Validator submitting scores: Check `docker logs -f`
2. Challenge moves to COMPLETED
2. Rewards distributed
2. Monitor for 2 challenges

## Escalation
- If >2 validators down → SEV-2
- If scoring stuck >4 hours → SEV-1
```

---

#### RUNBOOK-003: API Outage / High Latency

```markdown
# RUNBOOK-003: API Outage / High Latency

## Symptoms
- API health check failing
- Dashboard showing errors
- Miners unable to submit/fetch baselines
- GraphQL queries timing out

## Diagnosis
1. Check API container: `docker ps | grep api`
2. Check API logs: `docker logs hydrogen-api --tail 100`
2. Check database: `docker exec hydrogen-postgres pg_isready`
2. Check Redis: `redis-cli ping`
2. Check subtensor connection: `curl http://subtensor:9933/health`

## Common Issues & Fixes

### Database Connection Pool Exhausted
```bash
# Check connections
docker exec hydrogen-postgres psql -U hydrogen -c "SELECT count(*) FROM pg_stat_activity;"

# Increase pool size
# In api config: POOL_SIZE=50

# Kill idle connections
docker exec hydrogen-postgres psql -U hydrogen -c "
  SELECT pg_terminate_backend(pid) 
  FROM pg_stat_activity 
  WHERE state = 'idle' AND state_change < now() - interval '5 minutes';
"
```

### Redis Memory Full
```bash
# Check memory
redis-cli INFO memory

# Flush cache (careful!)
redis-cli FLUSHDB

# Increase maxmemory
# In redis.conf: maxmemory 512mb
```

### Subtensor Connection Lost
```bash
# Check subtensor
curl http://subtensor:9933/health

# Restart API (will reconnect)
docker restart hydrogen-api

# Check firewall
ufw status
```

### High Latency - Slow Queries
```bash
# Check slow queries
docker exec hydrogen-postgres psql -U hydrogen -c "
  SELECT query, mean_time, calls 
  FROM pg_stat_statements 
  ORDER BY mean_time DESC 
  LIMIT 10;
"

# Add missing indexes
# Check EXPLAIN ANALYZE for slow queries
```

### Subtensor Reorg Handling
```bash
# Check indexer logs
docker logs hydrogen-indexer --tail 50

# If reorg detected:
# 1. Indexer should handle automatically
# 2. If stuck: restart indexer
docker restart hydrogen-indexer
```

### Post-Fix Verification
1. API health: `curl http://localhost:8000/health`
2. GraphQL: `curl -X POST http://localhost:4000 -d '{"query":"{health}"}'`
2. Dashboard loads correctly
2. Miner CLI works: `hydrogen-miner challenges`
```

---

#### RUNBOOK-004: Physics Gate Bug / False Positive

```markdown
# RUNBOOK-004: Physics Gate Bug / False Positive

## Symptoms
- Valid submissions scoring 0 (hard failure)
- Physics gates failing on known-good solutions
- Miners reporting false failures

## Diagnosis
1. Check validator logs for gate failures
2. Run determinism test: `./scripts/determinism_test.sh`
3. Check recent code changes to physics gates
3. Run physics regression tests: `pytest tests/integration/physics_regression.py`

## Common Issues & Fixes

### Threshold Too Strict
```python
# Check thresholds in SPEC vs implementation
# Mass conservation: 1e-3 might be too strict for 3D
# Adjust in validator/physics_gates.py

# Example fix:
# MASS_CONSERVATION_THRESHOLD = 1e-3  # 2D
# MASS_CONSERVATION_THRESHOLD_3D = 5e-3  # 3D
```

### Numerical Precision Issue
```python
# Use double precision for physics gates
# In physics_gates.py:
u_double = u.double()
divergence = torch.div(u_double, ...)
```

### Wrong Formula Implementation
```python
# Verify formulas against SPEC
# Energy dissipation: dE/dt should be ≤ 0
# Check sign convention

# Rollout stability: E(t=100) vs E(t=0)
# Should use relative difference: |E_T - E_0| / E_0
```

### UQ Calibration Bug
```python
# Check calibration calculation
# coverage = mean(y_true ∈ [y_pred - 1.645*std, y_pred + 1.645*std])
# For 90% PI: z = 1.645
# For 95% PI: z = 1.96
# For 99% PI: z = 2.576
```

### Rollout Stability Calculation
```python
# Should track energy over time
# energy_drift = abs(energy[-1] - energy[0]) / energy[0]
# Must use relative, not absolute
```

### 3D-Specific Gates
```python
# Energy spectrum: fit power law to log-log plot
# Q-criterion: Q = 0.5*(||Ω||² - ||S||²)
# Wall shear: τ_w = μ * (∂u/∂y)|wall
# Nu distribution: Nu = h*L/k
# Added mass: A_ij = -ρ ∫ n_i φ_j dS
```

### Emergency Rollback
```bash
# Rollback validator image
docker pull hydrogen/validator:pino-v24.08
docker tag hydrogen/validator:pino-v24.08 hydrogen/validator:pino-v24.09
docker restart hydrogen-validator-pino

# Or: Deploy previous known-good commit
git checkout <previous-good-commit>
./scripts/build_validator_images.sh
docker compose up -d validator-dev
```

### Post-Fix Verification
1. Run determinism test
2. Run physics regression suite
3. Submit known-good strategy → verify passes
3. Monitor 3 challenges
```

---

#### RUNBOOK-005: Indexer Stuck / Out of Sync

```markdown
# RUNBOOK-005: Indexer Stuck / Out of Sync

## Symptoms
- Indexer block height << chain tip
- Dashboard showing stale data
- Missing recent challenges/submissions

## Diagnosis
1. Check indexer logs: `docker logs hydrogen-indexer --tail 100`
2. Check current block: `curl -s http://localhost:9933 | jq '.blockNumber'`
2. Check indexer height: `curl http://indexer:8080/health`
2. Check database size: `docker exec postgres psql -U hydrogen -c "SELECT pg_size_pretty(pg_database_size('hydrogen_indexer'));`

## Common Issues & Fixes

### Stuck at Specific Block
```bash
# Check for error at specific block
docker logs hydrogen-indexer | grep -A 10 -B 5 "ERROR"

# Common: Event decoding failure
# Fix: Update indexer event decoding logic
# Then: restart indexer
docker restart hydrogen-indexer
```

### Database Lock / Deadlock
```bash
# Check locks
docker exec hydrogen-postgres psql -U hydrogen -c "
  SELECT pid, state, query_start, query 
  FROM pg_stat_activity 
  WHERE state != 'idle';
"

# Kill blocking queries
docker exec hydrogen-postgres psql -U hydrogen -c "
  SELECT pg_terminate_backend(pid) 
  FROM pg_stat_activity 
  WHERE state = 'idle in transaction' 
  AND state_change < now() - interval '1 minute';
"
```

### Chain Reorg Handling
```bash
# Check for reorg
docker logs hydrogen-indexer | grep -i reorg

# If stuck on reorg:
# 1. Reset indexer to block before reorg
# 2. Restart indexer
docker exec hydrogen-indexer python -c "
from indexer.sync import reset_to_block
reset_to_block(SAFE_BLOCK_NUMBER)
"
docker restart hydrogen-indexer
```

### Database Corruption
```bash
# Check corruption
docker exec hydrogen-postgres pg_dump -U hydrogen hydrogen_indexer > /dev/null

# If corrupt: restore from backup
# 1. Stop indexer
docker stop hydrogen-indexer
# 2. Restore DB
pg_restore -U hydrogen -d hydrogen_indexer /backups/latest.dump
# 3. Restart indexer
docker start hydrogen-indexer
```

### Slow Sync
```bash
# Check sync speed
# Should Beatspeed
# Normal: ~100 blocks/sec

# Check batch size
# Increase: BATCH_SIZE=200

# Check network latency to subtensor
ping subtensor

# Increase RPC timeout
# RPC_TIMEOUT=30
```

### Post-Fix Verification
1. Indexer catches up to chain tip
2. Dashboard shows current data
2. No gaps in challenge/submission data
2. GraphQL queries return current data
```

---

## G.3 Routine Maintenance Procedures

### G.3.1 Daily Operations

```markdown
# DAILY-OPS-001: Daily Operations Checklist

## Morning (09:00 UTC)
- [ ] Check subnet health: `curl http://api:8000/health`
- [ ] Check active challenges: `hydrogen-miner challenges`
- [ ] Verify active validators: `docker ps | grep validator`
- [ ] Check emission distribution: `hydrogen-miner rewards --days 1`
- [ ] Review overnight alerts (PagerDuty/Slack)
- [ ] Check emission budget utilization

## Midday (14:00 UTC)
- [ ] Verify challenge deadlines met
- [ ] Check scoring completion rate
- [ ] Review validator performance metrics
- [ ] Check emission budget utilization

## Evening (22:00 UTC)
- [ ] Verify all challenges scored
- [ ] Check reward distribution
- [ ] Review Landscape Agent baseline updates
- [ ] Check specialist distillation (if scheduled)
- [ ] Verify backup completion

## Alerts to Monitor
- API latency > 2x SLO
- Validator count < 5
- Challenge scoring rate < 90%
- Emission budget utilization > 90%
- Database disk > 80%
- Validator GPU memory > 90%
```

---

### G.3.2 Weekly Operations

```markdown
# WEEKLY-OPS-001: Weekly Operations

## Monday
- [ ] Review weekly metrics report
- [ ] Check specialist promotion pipeline
- [ ] Review data royalty distributions
- [ ] Update baseline configs if needed

## Tuesday
- [ ] Run determinism test on all validator images
- [ ] Run physics regression tests
- [ ] Review specialist promotion queue

## Wednesday
- [ ] Database maintenance: VACUUM ANALYZE
- [ ] Check disk space, clean old logs
- [ ] Review validator performance metrics

## Thursday
- [ ] Security scan: dependency audit
- [ ] Review slashing events (if any)
- [ ] Check treasury balance

## Friday
- [ ] Weekly metrics report generation
- [ ] Plan next week's challenges
- [ ] Review miner feedback / support tickets
- [ ] Plan next week's operational priorities

## Weekend (On-call)
- [ ] Monitor for SEV-1/2 alerts
- [ ] Emergency response if needed
```

---

### G.3.3 Monthly Operations

```markdown
# MONTHLY-OPS-001: Monthly Operations

## 1st of Month
- [ ] Generate monthly metrics report
- [ ] Review emission economics
- [ ] Plan next month's challenges
- [ ] Review specialist bank health

## Mid-Month
- [ ] Security audit: dependencies, containers
- [ ] Performance benchmark run
- [ ] Review validator hardware health

## End of Month
- [ ] Treasury report
- [ ] Emission economics analysis
- [ ] Plan next month's operational priorities
- [ ] Update runbooks based on incidents
```

---

## G.4 Backup & Disaster Recovery

### G.4.1 Backup Strategy

```yaml
# backup_strategy.yaml

backup_schedule:
  postgres:
    frequency: "daily at 02:00 UTC"
    retention: "30 days daily, 12 months monthly, 7 years yearly"
    method: "pg_dump --format=custom --compress=9"
    storage: "MinIO (s3://hydrogen-backups/postgres/)"
    verification: "pg_restore --list on 10% of backups monthly"
    
  redis:
    frequency: "daily at 03:00 UTC"
    retention: "7 days"
    method: "BGSAVE + copy RDB"
    storage: "MinIO (s3://hydrogen-backups/redis/)"
    
  minio:
    frequency: "continuous (versioning enabled)"
    retention: "90 days"
    lifecycle: "Transition to cold storage after 30 days"
    
  chain_data:
    frequency: "daily at 04:00 UTC"
    retention: "90 days"
    method: "Snapshot /data/subtensor"
    storage: "MinIO (s3://hydrogen-backups/chain/)"

  validator_images:
    frequency: "on each release"
    retention: "all release tags"
    storage: "GHCR + mirrored to ECR"
    
  configs_secrets:
    frequency: "on change"
    retention: "indefinite"
    storage: "1Password / Vault"
    encryption: "age / GPG"

recovery_time_objectives:
  postgres: 4 hours
  redis: 30 minutes
  chain_data: 8 hours
  validator_images: 1 hour
  full_subnet: 12 hours

recovery_point_objectives:
  postgres: 24 hours
  redis: 24 hours
  chain_data: 24 hours
```

---

### G.4.2 Disaster Recovery Procedures

#### DR-001: Complete Subnet Recovery

```markdown
# DR-001: Complete Subnet Recovery from Backup

## Scenario
- Complete infrastructure loss (cloud account compromised, region down)
- All services down, need full rebuild

## Recovery Time Objective: 12 hours
## Recovery Point Objective: 24 hours

## Prerequisites
- Access to backup storage (MinIO)
- Access to secret management (1Password/Vault)
- Clean infrastructure (new cloud account)

## Procedure

### Phase 1: Infrastructure (Hours 0-2)
1. Provision new infrastructure (Terraform)
   - VPC, subnets, security groups
   - EKS cluster / EC2 instances
   - RDS PostgreSQL, ElastiCache Redis
   - S3/MinIO for backups
   
2. Restore secrets from Vault/1Password
   - Subtensor keys
   - API keys
   - Database passwords
   - TLS certificates

### Phase 2: Data Layer (Hours 2-6)
2. Restore PostgreSQL
   ```bash
   # Latest daily backup
   pg_restore -U hydrogen -d hydrogen_indexer \
     s3://hydrogen-backups/postgres/latest.dump
   ```
   
3. Restore Redis
   ```bash
   # Copy RDB to new Redis
   aws s3 cp s3://hydrogen-backups/redis/dump.rdb /data/dump.rdb
   redis-cli SHUTDOWN NOSAVE
   # Restart Redis
   ```

4. Restore MinIO (versioning enabled, so latest)
   ```bash
   # MinIO versioning handles this automatically
   mc mirror s3/hydrogen-backups/minio/ minio/hydrogen/
   ```

### Phase 3: Blockchain (Hours 4-8)
5. Restore Subtensor
   ```bash
   # Restore chain data
   tar -xzf s3://hydrogen-backups/chain/latest.tar.gz -C /data/subtensor
   
   # Start subtensor
   docker run -d --name subtensor \
     -v /data/subtensor:/data \
     -p 9944:9944 -p 9933:9933 \
     opentensor/subtensor:latest \
     --chain=local --dev
   ```

6. Wait for sync (if not --dev)
   ```bash
   # Wait for block sync
   while true; do
     CURRENT=$(curl -s http://localhost:9933 | jq '.blockNumber')
     TARGET=$(curl -s http://backup-subtensor:9933 | jq '.blockNumber')
     if [ "$CURRENT" -ge "$((TARGET - 10))" ]; then break; fi
     sleep 60
   done
   ```

### Phase 4: Application Layer (Hours 6-10)
6. Deploy API, Indexer, Dashboard
   ```bash
   docker compose -f docker-compose.prod.yml up -d api indexer dashboard
   ```

7. Deploy Validators
   ```bash
   docker compose -f docker-compose.prod.yml up -d validator-pino validator-fno ...
   ```

### Phase 5: Verification (Hours 10-12)
8. Run smoke tests
   ```bash
   ./scripts/smoke_test.sh
   ```

9. Verify emission distribution
   ```bash
   ./scripts/verify_emissions.sh
   ```

10. Open to miners
    ```bash
    # Update DNS
    # Announce recovery
    ```

### Post-Recovery
- Monitor for 24 hours
- Run full regression test suite
- Notify community
- Post-incident review within 48 hours
```

---

## G.5 Security Incident Response

```markdown
# SEC-INC-001: Security Incident Response

## Classification
| Type | Examples | Response |
|------|----------|----------|
| Container Escape | Validator container breakout | Isolate node, forensic image |
| Chain Attack | Double spend, reorg >10 blocks | Halt subnet, forensic |
| API Abuse | DDoS, injection, auth bypass | WAF rules, rate limit |
| Data Exfiltration | Well data, specialist models leaked | Revoke keys, rotate |
| Key Compromise | Owner/hotkey compromised | Rotate keys, multisig |

## Response Phases

### 1. Detection (0-15 min)
- Alert triggered (monitoring, user report, audit log)
- Classify severity (SEV-1 to SEV-4)
- Assign incident commander

### 2. Containment (15 min - 2 hours)
- Isolate affected systems
- Preserve forensic evidence
- Revoke compromised credentials
- Apply mitigations (WAF, firewall, revoke keys)

### 3. Eradication (2-24 hours)
- Root cause analysis
- Remove threat actor access
- Patch vulnerabilities
- Rotate all potentially compromised credentials

### 4. Recovery (24-72 hours)
- Restore from clean backups
- Verify system integrity
- Gradual service restoration
- Enhanced monitoring

### 5. Post-Incident (1-2 weeks)
- Root cause analysis (RCA)
- Update runbooks
- Implement preventive measures
- Legal/regulatory notification if required
- Community communication

## Communication Templates

### Internal Alert
```
🚨 SEV-{1-4}: {Title}
**Impact**: {User-facing impact}
**Status**: {Investigating/Mitigating/Resolved}
**Commander**: @{handle}
**Channel**: #incident-{id}
```

### Public Status Page
```
**Incident**: {Title}
**Status**: {Investigating/Identified/Monitoring/Resolved}
**Impact**: {Description}
**Next Update**: {Time}
```

### Post-Mortem Template
```
# Incident {ID}: {Title}

## Summary
{1-2 paragraph summary}

## Timeline
- {Timestamp}: {Event}
- {Timestamp}: {Event}

## Root Cause
{Technical root cause}

## Impact
- Users affected: {Number}
- Duration: {Time}
- Data loss: {Yes/No}

## Action Items
- [ ] {Action} - Owner: @{handle} - Due: {Date}
- [ ] {Action} - Owner: @{handle} - Due: {Date}

## Lessons Learned
{What we learned}
```
```

---

## G.6 Communication Protocols

```markdown
# COMM-001: Communication Protocols

## Internal Channels

### #hydrogen-ops (Operations)
- Daily ops updates
- Maintenance windows
- Routine alerts

### #hydrogen-incidents (Incidents)
- SEV-1/2/3 coordination
- Real-time incident updates
- Post-incident reviews

### #hydrogen-alerts (Alerts)
- Automated alerts (Prometheus, PagerDuty)
- No discussion, alerts only

### #hydrogen-dev (Development)
- Deployments
- Code reviews
- Feature flags

### #hydrogen-validators (Validator Operations)
- Validator-specific alerts
- Version upgrades
- Hardware issues

## External Communication

### Status Page (status.hydrogen.subnet)
- Updated within 15 min of SEV-1/2
- Updated hourly during active incidents
- Post-mortem within 48 hours

### Discord (#announcements)
- Major upgrades
- Phase transitions
- Community-relevant incidents

### Twitter/X (@HydrogenSubnet)
- Major milestones
- Phase launches
- Major incident resolutions

### Miner/Validator Discord
- Challenge updates
- Reward distributions
- Upcoming changes

## Communication SLAs

| Severity | Internal Ack | Public Status | Next Update |
|----------|--------------|---------------|-------------|
| SEV-1 | 5 min | 15 min | 30 min |
| SEV-2 | 15 min | 30 min | 1 hour |
| SEV-3 | 1 hour | If user-facing | 4 hours |
| SEV-4 | Next business day | N/A | Next business day |
```

---

## G.7 On-Call Rotation

```yaml
# oncall.yaml

schedule:
  rotation: "weekly"
  handoff: "Monday 09:00 UTC"
  timezone: "UTC"

roles:
  primary:
    responsibilities:
      - First response to SEV-1/2
      - Execute runbooks
      - Coordinate with team
    escalation: 15 min → secondary
    
  secondary:
    responsibilities:
      - Backup for primary
      - Handle SEV-3/4
      - Support primary
    escalation: 30 min → team lead
    
  team_lead:
    responsibilities:
      - SEV-1 decision authority
      - External communication approval
      - Post-incident review owner
    escalation: N/A

rotation_schedule:
  - week_1: {primary: "alice", secondary: "bob", lead: "carol"}
  - week_2: {primary: "dave", secondary: "eve", lead: "frank"}
  - week_3: {primary: "grace", secondary: "heidi", lead: "ivan"}
  - week_4: {primary: "judy", secondary: "mallory", lead: "trent"}

handoff_checklist:
  - [ ] Active incidents status
  - [ ] Upcoming maintenance
  - [ ] Pending deployments
  - [ ] Known issues / watchlist
  - [ ] On-call phone / pager test
  - [ ] Access verification (AWS, K8s, Vault, Discord)

compensation:
  primary: "$500/week + $200/incident (SEV-1/2)"
  secondary: "$250/week + $100/incident (SEV-1/2)"
  lead: "$300/week"
```

---

## G.8 Vendor & Dependency Management

```markdown
# VENDOR-001: Critical Dependencies

## Core Dependencies
| Dependency | Version Pinning | Update Policy | Alternative |
|------------|-----------------|---------------|-------------|
| PhysicsNeMo | Pinned (0.4.0) | Quarterly, after validation | Custom impl |
| NeuralOperator | Pinned (0.3.0) | Quarterly, after validation | Custom impl |
| PyTorch | Pinned (2.3.0) | Semi-annual, after validation | N/A |
| CUDA | Pinned (12.4) | Annual | N/A |
| Substrate | Pinned (monthly) | Monthly, after testing | N/A |
| PostgreSQL | 16.x | Minor: auto, Major: quarterly | CockroachDB |
| Redis | 7.x | Minor: auto | Valkey |
| Docker | Latest stable | Monthly | Podman |

## Update Procedures

### Monthly (Automated via Dependabot)
- [ ] Security patches (OS, base images)
- [ ] Minor dependency updates (non-breaking)
- [ ] Run full test suite

### Quarterly (Manual)
- [ ] PhysicsNeMo / NeuralOperator major version
- [ ] PyTorch minor version
- [ ] Substrate runtime upgrade
- [ ] Full regression test suite

### Annually (Planned)
- [ ] CUDA version upgrade
- [ ] PostgreSQL major version
- [ ] OS base image upgrade
- [ ] Security audit

## Vendor Risk Assessment

| Vendor | Risk | Mitigation |
|--------|------|------------|
| NVIDIA (PhysicsNeMo) | Single source, license change | Fork capability, abstraction layer |
| Opentensor (Substrate) | Ecosystem dependency | Fork readiness, community sync |
| Cloud Provider | Region outage | Multi-region, multi-cloud ready |
| MinIO / S3 | Data loss | Cross-region replication |
```

---

*End of Appendix G: Operational Runbook v2.1*
