# Appendix D: Dashboard & Indexer Specification

**Purpose:** This document specifies the complete Dashboard & Indexer architecture for the Hydrogen subnet, including the GraphQL API schema, REST API endpoints, database schema, real-time subscriptions, indexer architecture, and webhook endpoints. This is the data layer that powers the Hydrogen dashboard, provides query access to subnet state, and enables real-time monitoring of challenges, submissions, specialists, and network health.

---

# Appendix D: Dashboard & Indexer Specification v2.1

---

## D.1 GraphQL Schema

```graphql
# schema.graphql

scalar DateTime
scalar JSON
scalar BigInt

type Query {
  # Challenge queries
  challenge(id: ID!): Challenge
  challenges(filter: ChallengeFilter, pagination: Pagination): ChallengeConnection!
  activeChallenges: [Challenge!]!
  
  # Submission queries
  submission(id: ID!): Submission
  submissions(filter: SubmissionFilter, pagination: Pagination): SubmissionConnection!
  minerSubmissions(minerHotkey: String!, pagination: Pagination): SubmissionConnection!
  
  # Miner queries
  miner(hotkey: String!): Miner
  miners(filter: MinerFilter, pagination: Pagination): MinerConnection!
  leaderboard(phase: Int, limit: Int): [MinerRank!]!
  
  # Specialist queries
  specialist(id: ID!): Specialist
  specialists(filter: SpecialistFilter, pagination: Pagination): SpecialistConnection!
  specialistBank(problemId: Int): [Specialist!]!
  
  # Landscape queries
  causalGraph(problemId: Int, depth: Int): CausalGraph
  priors(challengeId: ID!): [Prior!]!
  baseline(challengeId: ID!): Baseline
  
  # Network stats
  networkStats: NetworkStats!
  emissionInfo: EmissionInfo!
}

type Mutation {
  # Miner mutations (called via API, signed by hotkey)
  submitStrategy(input: SubmitStrategyInput!): SubmissionResult!
  submitSpecialistPipeline(input: SubmitSpecialistPipelineInput!): SubmissionResult!
  submitCustomData(input: SubmitCustomDataInput!): CustomDataResult!
  
  # Validator mutations (called by validator hotkeys)
  submitScore(input: SubmitScoreInput!): ScoreResult!
  
  # Owner mutations (owner only)
  proposeBaseline(input: ProposeBaselineInput!): BaselineResult!
  promoteSpecialist(input: PromoteSpecialistInput!): SpecialistResult!
}

type Subscription {
  # Real-time updates
  challengeUpdates: ChallengeUpdate!
  submissionUpdates(minerHotkey: String): SubmissionUpdate!
  scoreUpdates(challengeId: ID!): ScoreUpdate!
  leaderboardUpdates: LeaderboardUpdate!
  specialistUpdates: SpecialistUpdate!
}

# ============================================================
# Core Types
# ============================================================

type Challenge {
  id: ID!
  problemId: Int!
  problemName: String!
  dimension: String!
  physicsClass: String!
  phase: Int!
  status: ChallengeStatus!
  resolution: String!
  emissionBudget: BigInt!
  submissionDeadline: DateTime!
  scoringDeadline: DateTime!
  baselineConfig: JSON!
  stressFloors: StressFloors!
  wellMapping: [String!]!
  createdAt: DateTime!
  updatedAt: DateTime!
  trainSamples: Int!
  holdoutSamples: Int!
  stressSamples: Int!
}

enum ChallengeStatus {
  ACTIVE
  SCORING
  COMPLETED
  ARCHIVED
}

type StressFloors {
  massConservation: Float!
  energyDissipation: Float!
  boundarySatisfaction: Float!
  rolloutSteps: Int!
  uqTarget: Float!
}

type Submission {
  id: ID!
  challenge: Challenge!
  miner: Miner!
  type: SubmissionType!
  strategyJson: JSON
  specialistPipeline: JSON
  customDataId: ID
  status: SubmissionStatus!
  submittedAt: DateTime!
  revealedAt: DateTime
  score: Float
  improvement: Float
  noveltyBonus: Float
  emissionReward: BigInt
  rank: Int
  physicsGates: PhysicsGateResults!
  stressDetails: StressDetails!
  causalInsights: [CausalInsight!]!
  validatorConsensus: ConsensusInfo!
  createdAt: DateTime!
  updatedAt: DateTime!
}

enum SubmissionType {
  STRATEGY
  SPECIALIST_PIPELINE
}

enum SubmissionStatus {
  COMMITTED
  REVEALED
  VALIDATING
  SCORED
  REWARDED
  REJECTED
}

type PhysicsGateResults {
  massConservation: GateResult!
  energyDissipation: GateResult!
  boundarySatisfaction: GateResult!
  rolloutStability: GateResult!
  uqCalibration: GateResult!
}

type GateResult {
  passed: Boolean!
  value: Float!
  threshold: Float!
  unit: String
}

type StressDetails {
  proceduralPassed: Int!
  proceduralFailed: Int!
  wellSlicesPassed: Int!
  wellSlicesFailed: Int!
  worstCaseDegradation: Float!
  gateResults: [GateResult!]!
}

type Miner {
  hotkey: String!
  coldkey: String
  uid: Int
  stake: BigInt
  totalRewards: BigInt!
  totalSubmissions: Int!
  successfulSubmissions: Int!
  winRate: Float!
  avgScore: Float!
  avgNoveltyBonus: Float!
  firstSubmissionAt: DateTime
  lastSubmissionAt: DateTime
  isActive: Boolean!
  registeredAt: DateTime!
}

type MinerRank {
  hotkey: String!
  rank: Int!
  score: Float!
  totalRewards: BigInt!
  challengesWon: Int!
  challengesParticipated: Int!
  avgNoveltyBonus: Float!
}

type Specialist {
  id: ID!
  problemId: Int!
  problemName: String!
  version: Int!
  onnxModelHash: String!
  validityDomain: ValidityDomain!
  stressTestResults: StressTestResults!
  metrics7d: Metrics7D!
  license: LicenseType!
  provenance: [String!]!
  createdAt: DateTime!
  updatedAt: DateTime!
  downloadUrl: String!
  downloadCount: Int!
  revenueGenerated: BigInt!
}

type ValidityDomain {
  parameters: JSON!
  constraints: [String!]!
  knownFailures: [String!]!
  recommendedUseCases: [String!]!
}

type StressTestResults {
  massConservation: Boolean!
  energyDissipation: Boolean!
  boundarySatisfaction: Boolean!
  rolloutStability: Boolean!
  uqCalibration: Boolean!
  spectralFidelity: Boolean
  couplingConsistency: Boolean
  addedMassTensor: Boolean
  nuDistribution: Boolean
}

type Metrics7D {
  fidelity: Float!
  accuracy: Float!
  efficiency: Float!
  robustness: Float!
  generalization: Float!
  interpretability: Float!
  usability: Float!
}

enum LicenseType {
  AGPL_3_0
  COMMERCIAL
  DUAL
}

type Prior {
  parameter: String!
  recommendedRange: JSON!
  causalEffect: String!
  confidence: Float!
  supportingFragments: Int!
  condition: String
  lastUpdated: DateTime!
}

type Baseline {
  challengeId: ID!
  problemId: Int!
  config: JSON!
  version: Int!
  lastUpdated: DateTime!
  proposedBy: String!
  approvedAt: DateTime!
}

type CausalGraph {
  nodes: [CausalNode!]!
  edges: [CausalEdge!]!
}

type CausalNode {
  id: ID!
  parameter: String!
  value: Float!
  ate: Float!
  confidence: Float!
  fragmentCount: Int!
}

type CausalEdge {
  from: ID!
  to: ID!
  interactionEffect: Float!
  confidence: Float!
}

type NetworkStats {
  totalMiners: Int!
  activeMiners24h: Int!
  activeValidators: Int!
  activeChallenges: Int!
  totalSubmissions24h: Int!
  avgScore24h: Float!
  totalEmissions24h: BigInt!
  specialistCount: Int!
  compositionWinRate: Float!
}

type EmissionInfo {
  totalEmission: BigInt!
  challengeBudget: BigInt!
  activeChallenges: Int!
  minerShare: Float!
  validatorShare: Float!
  ownerShare: Float!
  noveltyBonusPool: BigInt!
}

# ============================================================
# Input Types
# ============================================================

input ChallengeFilter {
  problemId: Int
  phase: Int
  status: ChallengeStatus
  dimension: String
}

input SubmissionFilter {
  challengeId: ID
  minerHotkey: String
  type: SubmissionType
  status: SubmissionStatus
  dateFrom: DateTime
  dateTo: DateTime
  minScore: Float
  maxScore: Float
}

input MinerFilter {
  isActive: Boolean
  minStake: BigInt
  minRewards: BigInt
}

input SpecialistFilter {
  problemId: Int
  license: LicenseType
  minFidelity: Float
}

input Pagination {
  first: Int
  after: String
  last: Int
  before: String
}

input SubmitStrategyInput {
  challengeId: ID!
  strategyJson: JSON!
  nonce: String!
  signature: String!
}

input SubmitSpecialistPipelineInput {
  challengeId: ID!
  pipelineJson: JSON!
  nonce: String!
  signature: String!
}

input SubmitCustomDataInput {
  challengeId: ID!
  dataUri: String!
  checksum: String!
  usage: String!
  weight: Float!
  encryption: EncryptionInput
}

input SubmitScoreInput {
  challengeId: ID!
  scores: [ValidatorScoreInput!]!
  signature: String!
}

input ValidatorScoreInput {
  minerHotkey: String!
  score: Float!
  improvement: Float!
  stressPassed: Boolean!
  uqCalibrated: Boolean!
  physicsGates: JSON!
  stressDetails: JSON!
}

input ProposeBaselineInput {
  problemId: Int!
  baselineJson: JSON!
  signature: String!
}

input PromoteSpecialistInput {
  specialistId: ID!
  gauntletResultHash: String!
  onnxModelHash: String!
  validityDomain: JSON!
  signature: String!
}

input SubmitCustomDataInput {
  challengeId: ID!
  dataUri: String!
  checksum: String!
  usage: String!
  weight: Float!
  encryption: EncryptionInput
}

input EncryptionInput {
  algorithm: String!
  keyId: String!
}

# ============================================================
# Connection Types (Relay-style pagination)
# ============================================================

type ChallengeConnection {
  edges: [ChallengeEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type ChallengeEdge {
  node: Challenge!
  cursor: String!
}

type SubmissionConnection {
  edges: [SubmissionEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type SubmissionEdge {
  node: Submission!
  cursor: String!
}

type MinerConnection {
  edges: [MinerEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type MinerEdge {
  node: Miner!
  cursor: String!
}

type SpecialistConnection {
  edges: [SpecialistEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type SpecialistEdge {
  node: Specialist!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}

# ============================================================
# Subscription Payloads
# ============================================================

type ChallengeUpdate {
  event: ChallengeEventType!
  challenge: Challenge!
  timestamp: DateTime!
}

enum ChallengeEventType {
  CREATED
  STATUS_CHANGED
  BASELINE_UPDATED
  COMPLETED
}

type SubmissionUpdate {
  event: SubmissionEventType!
  submission: Submission!
  timestamp: DateTime!
}

enum SubmissionEventType {
  SUBMITTED
  REVEALED
  SCORED
  REWARDED
  REJECTED
}

type ScoreUpdate {
  challengeId: ID!
  minerHotkey: String!
  score: Float!
  rank: Int!
  timestamp: DateTime!
}

type LeaderboardUpdate {
  phase: Int!
  rankings: [MinerRank!]!
  timestamp: DateTime!
}

type SpecialistUpdate {
  event: SpecialistEventType!
  specialist: Specialist!
  timestamp: DateTime!
}

enum SpecialistEventType {
  CREATED
  UPDATED
  PROMOTED
  DEPRECATED
}
```

---

## D.2 REST API Endpoints (Complementary to GraphQL)

```yaml
# REST endpoints for simple queries and webhooks

GET  /api/v1/challenges                    # List challenges with filters
GET  /api/v1/challenges/{id}               # Challenge details
GET  /api/v1/challenges/{id}/baseline      # Current baseline JSON
GET  /api/v1/challenges/{id}/priors        # Landscape priors (DML effects)
GET  /api/v1/challenges/{id}/submissions   # Submissions for challenge
GET  /api/v1/challenges/{id}/leaderboard   # Challenge leaderboard

GET  /api/v1/miners/{hotkey}               # Miner profile
GET  /api/v1/miners/{hotkey}/submissions   # Miner's submissions
GET  /api/v1/miners/{hotkey}/rewards       # Miner's rewards history

GET  /api/v1/specialists                   # List specialists
GET  /api/v1/specialists/{id}              # Specialist details
GET  /api/v1/specialists/{id}/download     # Download ONNX model

GET  /api/v1/landscape/priors/{challengeId} # Causal priors for challenge
GET  /api/v1/landscape/baseline/{challengeId} # Current baseline
GET  /api/v1/landscape/graph/{problemId}   # Causal graph for problem

GET  /api/v1/network/stats                 # Network statistics
GET  /api/v1/network/emissions             # Emission info

POST /api/v1/submit                        # Submit strategy/pipeline
POST /api/v1/webhooks/validator-score      # Validator webhook for scores

GET  /api/v1/health                        # Health check
GET  /api/v1/version                       # Version info
```

---

## D.3 Indexer Architecture

```yaml
# indexer.yaml

indexer:
  name: "hydrogen-indexer"
  version: "1.0.0"
  
  blockchain:
    network: "finney"
    ws_endpoint: "wss://entrypoint-finney.opentensor.ai:443"
    netuid: 107
    start_block: 1000000  # Subnet registration block
  
  database:
    type: "postgresql"
    host: "${DB_HOST}"
    port: 5432
    database: "hydrogen_indexer"
    user: "${DB_USER}"
    password: "${DB_PASSWORD}"
    pool_size: 20
    max_overflow: 10
  
  redis:
    host: "${REDIS_HOST}"
    port: 6379
    db: 0
    password: "${REDIS_PASSWORD}"
  
  sync:
    batch_size: 100
    block_interval: 12  # seconds
    confirmation_depth: 3
    retry_attempts: 5
    retry_delay: 5
  
  processing:
    workers: 4
    batch_size: 50
    queue_size: 10000
    dead_letter_queue: "hydrogen_dlq"
  
  graphql:
    host: "0.0.0.0"
    port: 4000
    playground: true
    introspection: true
    complexity_limit: 1000
    depth_limit: 10
  
  rest_api:
    host: "0.0.0.0"
    port: 8000
    cors_origins:
      - "https://dashboard.hydrogen.subnet"
      - "https://app.hydrogen.subnet"
    rate_limit:
      requests_per_minute: 120
      burst: 20
  
  websocket:
    host: "0.0.0.0"
    port: 4001
    ping_interval: 30
    ping_timeout: 10
  
  monitoring:
    prometheus_port: 9090
    health_check_port: 8080
    log_level: "INFO"
    log_format: "json"
```

---

## D.4 Database Schema (PostgreSQL)

```sql
-- schema.sql

-- Core tables
CREATE TABLE challenges (
    id VARCHAR(64) PRIMARY KEY,
    problem_id INTEGER NOT NULL,
    problem_name VARCHAR(100) NOT NULL,
    dimension VARCHAR(20) NOT NULL,
    physics_class VARCHAR(100) NOT NULL,
    phase INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    resolution VARCHAR(50),
    emission_budget NUMERIC(78, 0) NOT NULL,
    submission_deadline TIMESTAMPTZ NOT NULL,
    scoring_deadline TIMESTAMPTZ NOT NULL,
    baseline_config JSONB NOT NULL,
    stress_floors JSONB NOT NULL,
    well_mapping JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    train_samples INTEGER,
    holdout_samples INTEGER,
    stress_samples INTEGER
);

CREATE INDEX idx_challenges_status ON challenges(status);
CREATE INDEX idx_challenges_problem_phase ON challenges(problem_id, phase);

CREATE TABLE submissions (
    id VARCHAR(64) PRIMARY KEY,
    challenge_id VARCHAR(64) REFERENCES challenges(id),
    miner_hotkey VARCHAR(128) NOT NULL,
    type VARCHAR(20) NOT NULL,
    strategy_json JSONB,
    specialist_pipeline JSONB,
    custom_data_id VARCHAR(64),
    status VARCHAR(20) NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL,
    revealed_at TIMESTAMPTZ,
    score NUMERIC(10, 6),
    improvement NUMERIC(10, 6),
    novelty_bonus NUMERIC(10, 6),
    emission_reward NUMERIC(78, 0),
    rank INTEGER,
    physics_gates JSONB,
    stress_details JSONB,
    causal_insights JSONB,
    validator_consensus JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_submissions_challenge ON submissions(challenge_id);
CREATE INDEX idx_submissions_miner ON submissions(miner_hotkey);
CREATE INDEX idx_submissions_status ON submissions(status);
CREATE INDEX idx_submissions_score ON submissions(score DESC);

CREATE TABLE miners (
    hotkey VARCHAR(128) PRIMARY KEY,
    coldkey VARCHAR(128),
    uid INTEGER,
    stake NUMERIC(78, 0),
    total_rewards NUMERIC(78, 0) DEFAULT 0,
    total_submissions INTEGER DEFAULT 0,
    successful_submissions INTEGER DEFAULT 0,
    win_rate NUMERIC(5, 4) DEFAULT 0,
    avg_score NUMERIC(10, 6) DEFAULT 0,
    avg_novelty_bonus NUMERIC(10, 6) DEFAULT 0,
    first_submission_at TIMESTAMPTZ,
    last_submission_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    registered_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE specialists (
    id VARCHAR(64) PRIMARY KEY,
    problem_id INTEGER NOT NULL,
    problem_name VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL,
    onnx_model_hash VARCHAR(64) NOT NULL,
    validity_domain JSONB NOT NULL,
    stress_test_results JSONB NOT NULL,
    metrics_7d JSONB,
    license VARCHAR(20) NOT NULL,
    provenance JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    download_url VARCHAR(512),
    download_count INTEGER DEFAULT 0,
    revenue_generated NUMERIC(78, 0) DEFAULT 0
);

CREATE INDEX idx_specialists_problem ON specialists(problem_id);
CREATE INDEX idx_specialists_version ON specialists(version);

CREATE TABLE strategy_fragments (
    id VARCHAR(64) PRIMARY KEY,
    miner_uid INTEGER NOT NULL,
    challenge_id VARCHAR(64) REFERENCES challenges(id),
    problem_id INTEGER NOT NULL,
    config_json JSONB NOT NULL,
    improvement NUMERIC(10, 6) NOT NULL,
    stress_passed BOOLEAN NOT NULL,
    uq_metrics JSONB,
    score NUMERIC(10, 6),
    timestamp TIMESTAMPTZ NOT NULL,
    causal_parents TEXT[],
    param_values JSONB
);

CREATE INDEX idx_fragments_problem ON strategy_fragments(problem_id);
CREATE INDEX idx_fragments_challenge ON strategy_fragments(challenge_id);
CREATE INDEX idx_fragments_improvement ON strategy_fragments(improvement DESC);

CREATE TABLE baselines (
    problem_id INTEGER PRIMARY KEY,
    config JSONB NOT NULL,
    version INTEGER NOT NULL,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    proposed_by VARCHAR(128),
    approved_at TIMESTAMPTZ
);

CREATE TABLE causal_edges (
    id BIGSERIAL PRIMARY KEY,
    from_fragment VARCHAR(64) NOT NULL,
    to_fragment VARCHAR(64) NOT NULL,
    interaction_effect NUMERIC(10, 6),
    confidence NUMERIC(5, 4),
    problem_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_causal_edges_problem ON causal_edges(problem_id);

-- Views for common queries
CREATE VIEW miner_stats AS
SELECT 
    m.hotkey,
    m.total_rewards,
    m.total_submissions,
    m.successful_submissions,
    CASE WHEN m.total_submissions > 0 
        THEN m.successful_submissions::numeric / m.total_submissions 
        ELSE 0 END as win_rate,
    m.avg_score,
    m.avg_novelty_bonus,
    MAX(s.submitted_at) as last_submission_at
FROM miners m
LEFT JOIN submissions s ON m.hotkey = s.miner_hotkey
GROUP BY m.hotkey, m.total_rewards, m.total_submissions, m.successful_submissions, m.avg_score, m.avg_novelty_bonus;

CREATE VIEW challenge_stats AS
SELECT 
    c.id,
    c.problem_id,
    c.status,
    COUNT(s.id) as total_submissions,
    COUNT(DISTINCT s.miner_hotkey) as unique_miners,
    MAX(s.score) as best_score,
    AVG(s.score) as avg_score,
    MAX(s.improvement) as best_improvement
FROM challenges c
LEFT JOIN submissions s ON c.id = s.challenge_id
GROUP BY c.id, c.problem_id, c.status;
```

---

## D.5 Real-time Subscriptions (GraphQL over WebSocket)

```typescript
// subscriptions.ts - Client-side subscription handlers

// Challenge updates
subscription ChallengeUpdates {
  challengeUpdates {
    event
    challenge {
      id
      status
      submissionDeadline
      emissionBudget
    }
    timestamp
  }
}

// Miner's submission updates
subscription MySubmissions($hotkey: String!) {
  submissionUpdates(minerHotkey: $hotkey) {
    event
    submission {
      id
      challenge { id problemName }
      status
      score
      rank
      emissionReward
    }
    timestamp
  }
}

// Live leaderboard
subscription Leaderboard($phase: Int!) {
  leaderboardUpdates(phase: $phase) {
    phase
    rankings {
      hotkey
      rank
      score
      totalRewards
    }
    timestamp
  }
}

// Challenge scoring updates
subscription ChallengeScores($challengeId: ID!) {
  scoreUpdates(challengeId: $challengeId) {
    challengeId
    minerHotkey
    score
    rank
    timestamp
  }
}

// Specialist bank updates
subscription SpecialistUpdates {
  specialistUpdates {
    event
    specialist {
      id
      problemName
      version
      validityDomain
      metrics7d {
        fidelity
        accuracy
      }
    }
    timestamp
  }
}
```

---

## D.6 Webhook Endpoints

```yaml
# Webhook endpoints for external integrations

POST /webhooks/validator-score
  # Called by validator after scoring
  # Payload: { challengeId, minerHotkey, score, improvement, stressPassed, uqCalibrated, physicsGates, stressDetails }
  # Response: { accepted: true, scoreId: "..." }

POST /webhooks/rewards-distributed
  # Called after rewards distributed
  # Payload: { challengeId, rewards: [{ minerHotkey, amount, rank }] }

POST /webhooks/specialist-promoted
  # Called when specialist promoted
  # Payload: { specialistId, problemId, version, validityDomain, onnxHash }

POST /webhooks/baseline-updated
  # Called when baseline updated
  # Payload: { problemId, version, baselineHash, proposedBy }
```

---

*End of Appendix D: Dashboard & Indexer Specification v2.1*
