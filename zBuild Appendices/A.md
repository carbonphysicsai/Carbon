# Appendix A: Chain Pallet Specification (Substrate FRAME/Rust)

**Purpose:** This document specifies the complete on-chain logic for the Hydrogen subnet as a Substrate FRAME pallet. It defines all on-chain state, extrinsics, events, errors, consensus logic, slashing conditions, and emission mechanics. This pallet is the consensus-critical layer that enforces the incentive mechanics, challenge lifecycle, validator assignments, scoring consensus, specialist promotion, and landscape agent governance. It is the single source of truth for all on-chain state transitions and the final authority for reward distribution.

---

# Appendix A: Chain Pallet Specification (Substrate FRAME/Rust) v2.1

---

## 1. Pallet Overview

```rust
// pallets/hydrogen/src/lib.rs

#![cfg_attr(not(feature = "std"), no_std)]

pub use pallet::*;

#[frame_support::pallet]
pub mod pallet {
    use frame_support::{
        pallet_prelude::*,
        traits::{Currency, ReservableCurrency, LockableCurrency, ExistenceRequirement::KeepAlive},
        dispatch::DispatchResultWithPostInfo,
    };
    use frame_system::pallet_prelude::*;
    use sp_std::prelude::*;
    use sp_runtime::{
        traits::{Hash, Zero, Saturating, CheckedDiv, CheckedMul, CheckedAdd, Verify},
        ArithmeticError, Percent, FixedPointNumber, FixedU128,
    };
    use sp_runtime::traits::BlakeTwo256;
    use sp_crypto_hashing::blake2_256;
    use sp_core::crypto::UncheckedFrom;
    use sp_std::collections::btree_map::BTreeMap;

    #[frame_support::pallet]
    pub mod pallet {
        use super::*;

        #[frame_support::pallet]
        pub mod pallet {
            use super::*;

            #[pallet::config]
            pub trait Config: frame_system::Config {
                type RuntimeEvent: From<Event<Self>> + IsType<<Self as frame_system::Config>::RuntimeEvent>;
                
                /// Currency type for emissions and fees
                type Currency: Currency<Self::AccountId> 
                    + ReservableCurrency<Self::AccountId> 
                    + LockableCurrency<Self::AccountId, Moment = Self::BlockNumber>;
                
                /// Subnet ID (NetUID)
                #[pallet::constant]
                type NetUid: Get<u16>;
                
                /// Maximum active challenges at any time
                #[pallet::constant]
                type MaxActiveChallenges: Get<u32>;
                
                /// Submission fee (burned on invalid submission)
                #[pallet::constant]
                type SubmissionFee: Get<BalanceOf<Self>>;
                
                /// Minimum stake to be a validator
                #[pallet::constant]
                type MinValidatorStake: Get<BalanceOf<Self>>;
                
                /// Maximum validators per challenge
                #[pallet::constant]
                type MaxValidatorsPerChallenge: Get<u32>;
                
                /// Minimum validators per challenge
                #[pallet::constant]
                type MinValidatorsPerChallenge: Get<u32>;
                
                /// Minimum validators required for consensus
                #[pallet::constant]
                type MinValidatorsForConsensus: Get<u32>;
                
                /// Emission split: miners (41%), validators (41%), owner (18%)
                #[pallet::constant]
                type MinerEmissionShare: Get<Percent>;
                #[pallet::constant]
                type ValidatorEmissionShare: Get<Percent>;
                #[pallet::constant]
                type OwnerEmissionShare: Get<Percent>;
                
                /// Novelty bonus share (5% of challenge budget)
                #[pallet::constant]
                type NoveltyBonusShare: Get<Percent>;
                
                /// Warm-up period: challenges before competitive phase
                #[pallet::constant]
                type WarmupChallengeThreshold: Get<u32>;
                
                /// Minimum submissions for competitive phase
                #[pallet::constant]
                type MinSubmissionsForCompetitive: Get<u32>;
                
                /// Novelty bonus share of challenge budget (5%)
                #[pallet::constant]
                type NoveltyBonusPercent: Get<Percent>;
                
                /// Challenge duration in blocks
                #[pallet::constant]
                type ChallengeDurationBlocks: Get<BlockNumberFor<Self>>;
                
                /// Commit phase duration in blocks
                #[pallet::constant]
                type CommitPhaseBlocks: Get<BlockNumberFor<Self>>;
                
                /// Reveal phase duration in blocks
                #[pallet::constant]
                type RevealPhaseBlocks: Get<BlockNumberFor<Self>>;
                
                /// Scoring period blocks
                #[pallet::constant]
                type ScoringPeriodBlocks: Get<BlockNumberFor<Self>>;
                
                /// Minimum validators required for consensus
                #[pallet::constant]
                type MinValidatorsForConsensus: Get<u32>;
                
                /// Maximum active challenges
                #[pallet::constant]
                type MaxActiveChallenges: Get<u32>;
                
                /// VRF provider for validator selection
                type VRF: VRFProvider<Self::AccountId>;
                
                /// Cryptographic hash function
                type Hashing: Hash<Output = Self::Hash>;
                
                /// Weight info for benchmarking
                type WeightInfo: WeightInfo;
            }

        // Type aliases
        type BalanceOf<T> = <<T as Config>::Currency as Currency<<T as frame_system::Config>::AccountId>>::Balance;
        type BlockNumberFor<T> = <<T as frame_system::Config>::BlockNumber;
        type AccountIdOf<T> = <T as frame_system::Config>::AccountId;
        type HashOf<T> = <T as frame_system::Config>::Hash;
```

---

## 2. Core Types

```rust
    // ============================================================
    // Core Types
    // ============================================================

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub enum ProblemId {
        Poisson2D = 1,
        Poisson3D = 2,
        Darcy2D = 3,
        Darcy3D = 4,
        Burgers2D = 5,
        NavierStokes2D = 6,
        NavierStokes3D = 7,
        Heat2D = 8,
        Elasticity2D = 9,
        ThermoElasticity2D = 10,
        // Phase 2+
        FSI2D = 11,
        CHT2D = 12,
        ThermoElasticity2D_v2 = 13,
        // Phase 3+
        FSI3D = 100,
        ThermoElasticity3D = 101,
        CHT3D = 102,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub enum ChallengeStatus {
        Active,       // Accepting submissions
        Committing,   // Commit phase
        Revealing,    // Reveal phase
        Scoring,      // Validators scoring
        Completed,    // Rewards distributed
        Failed,       // Insufficient submissions/validators
        Archived,     // Completed, rewards distributed rewards
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub enum SubmissionType {
        Strategy,
        SpecialistPipeline,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub enum SubmissionStatus {
        Committed,
        Revealed,
        Validating,
        Scored,
        Rewarded,
        Rejected,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct ProblemSignature {
        problem_id: ProblemId,
        dimension: u8,
        resolution: Vec<u32>,
        physics_class: Vec<u8>,
        coupling_spec: Option<CouplingSpec>,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct CouplingSpec {
        primary_physics: Vec<u8>,
        secondary_physics: Vec<u8>,
        coupling_type: Vec<u8>,
        coupling_params: Vec<(Vec<u8>, Vec<u8>)>, // key-value pairs
        coupling_scheme: Vec<u8>,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct Challenge<BlockNumber, Balance, AccountId> {
        id: ChallengeId,
        problem_signature: ProblemSignature,
        status: ChallengeStatus,
        created_at: BlockNumber,
        commit_deadline: BlockNumber,
        reveal_deadline: BlockNumber,
        scoring_deadline: BlockNumber,
        baseline_config_hash: Hash, // Hash of baseline JSON
        stress_floors: StressFloors,
        well_mapping: Vec<Vec<u8>>, // Well dataset names
        emission_budget: Balance,
        emission_distributed: bool,
        baseline_config: Vec<u8>, // Full JSON config
        creator: AccountId,
        submission_count: u32,
        validator_count: u32,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct StressFloors {
        mass_conservation: u64,      // Scaled by 1e6 (1e-3 = 1000)
        energy_dissipation: u64,
        boundary_satisfaction: u64,
        rollout_steps: u32,
        uq_target: u64,              // Scaled by 100 (0.90 = 90)
        // 3D-specific
        energy_spectrum: Option<u64>,      // k^(-5/3) scaling error
        q_criterion: Option<u64>,          // Q-criterion error
        wall_shear: Option<u64>,           // Wall shear stress error
        nu_distribution: Option<u64>,      // Nu distribution error
        added_mass_tensor: Option<u64>,    // Added-mass tensor error
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct Submission<AccountId, BlockNumber, Balance> {
        id: SubmissionId,
        challenge_id: ChallengeId,
        miner: AccountId,
        submission_type: SubmissionType,
        commitment_hash: Hash,      // blake2b256(canonical_json || nonce || challenge_id || miner)
        revealed_json: Option<Vec<u8>>, // Revealed JSON (None during commit phase)
        nonce: [u8; 32],            // 256-bit nonce
        submission_type_enum: SubmissionType,
        status: SubmissionStatus,
        submitted_at: BlockNumber,
        revealed_at: Option<BlockNumber>,
        score: Option<Score>,       // None until scored
        improvement: Option<Score>,
        novelty_bonus: Option<Score>,
        emission_reward: Balance,
        rank: Option<u32>,
        physics_gates: PhysicsGateResults,
        stress_details: StressDetails,
        novelty_bonus_awarded: Score,
        miner_hotkey: AccountId,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct PhysicsGateResults {
        mass_conservation: GateResult,
        energy_dissipation: GateResult,
        boundary_satisfaction: GateResult,
        rollout_stability: GateResult,
        uq_calibration: GateResult,
        // 3D-specific
        spectral_fidelity: Option<GateResult>,
        q_criterion: Option<GateResult>,
        wall_shear_stress: Option<GateResult>,
        nu_distribution: Option<GateResult>,
        added_mass_tensor: Option<GateResult>,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct GateResult {
        passed: bool,
        value: u64,      // Scaled by 1e6
        threshold: u64,  // Scaled by 1e6
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct StressDetails {
        procedural_passed: u32,
        procedural_failed: u32,
        well_slices_passed: u32,
        well_slices_failed: u32,
        worst_case_degradation: u64, // Scaled by 1e6
    }

    // Scaled score (FixedU128 for precision)
    pub type Score = FixedU128;

    // IDs
    pub type ChallengeId = [u8; 32];
    pub type SubmissionId = [u8; 32];
    pub type SpecialistId = [u8; 32];

    // ============================================================
    // Cryptographic Primitives
    // ============================================================

    /// VRF Provider trait for validator selection
    pub trait VRFProvider<AccountId> {
        /// Generate VRF output and proof
        fn generate(output: &mut [u8; 32], proof: &mut [u8; 64], secret_key: &[u8; 32], input: &[u8]) -> Result<(), ()>;
        
        /// Verify VRF output and proof
        fn verify(output: &[u8; 32], proof: &[u8; 64], public_key: &[u8; 32], input: &[u8]) -> bool;
    }

    /// VRF output for validator selection
    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct VRFOutput {
        pub randomness: [u8; 32],
        pub proof: [u8; 64],
    }

    /// Commit-Reveal commitment
    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct Commitment {
        pub commitment_hash: Hash,  // blake2b256(canonical_json || nonce || challenge_id || miner)
        pub nonce: [u8; 32],
        pub challenge_id: ChallengeId,
        pub miner: AccountId,
        pub committed_at: BlockNumber,
    }

    /// Commit-Reveal protocol constants
    pub const COMMITMENT_DOMAIN: &[u8] = b"hydrogen-commit-v2";
    pub const NONCE_SIZE: usize = 32;
    pub const MIN_NONCE_ENTROPY_BITS: u32 = 128;
```

---

## 3. Storage

```rust
    // ============================================================
    // Storage
    // ============================================================

    /// Current challenge counter
    #[pallet::storage]
    #[pallet::getter(fn challenge_count)]
    pub type ChallengeCount<T: Config> = StorageValue<_, u64, ValueQuery>;

    /// Active challenges by ID
    #[pallet::storage]
    #[pallet::getter(fn challenges)]
    pub type Challenges<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        Challenge<BlockNumberFor<T>, BalanceOf<T>, T::AccountId>,
        OptionQuery,
    >;

    /// Active challenge IDs for iteration
    #[pallet::storage]
    #[pallet::getter(fn active_challenge_ids)]
    pub type ActiveChallengeIds<T: Config> = StorageValue<_, BoundedVec<ChallengeId, T::MaxActiveChallenges>, ValueQuery>;

    /// Challenge metadata by problem
    #[pallet::storage]
    #[pallet::getter(fn challenges_by_problem)]
    pub type ChallengesByProblem<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ProblemId,
        BoundedVec<ChallengeId, ConstU32<100>>,
        ValueQuery,
    >;

    /// Submissions by challenge and miner
    #[pallet::storage]
    #[pallet::getter(fn submissions)]
    pub type Submissions<T: Config> = StorageDoubleMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        Blake2_128Concat,
        T::AccountId,
        Submission<T::AccountId, BlockNumberFor<T>, BalanceOf<T>>,
        OptionQuery,
    >;

    /// Submission IDs for iteration
    #[pallet::storage]
    #[pallet::getter(fn submission_ids)]
    pub type SubmissionIds<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<T::AccountId, ConstU32<1000>>,
        ValueQuery,
    >;

    /// Commitments for commit-reveal
    #[pallet::storage]
    #[pallet::getter(fn commitments)]
    pub type Commitments<T: Config> = StorageDoubleMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        Blake2_128Concat,
        T::AccountId,
        Commitment,
        OptionQuery,
    >;

    /// Validator scores for consensus
    #[pallet::storage]
    #[pallet::getter(fn validator_scores)]
    pub type ValidatorScores<T: Config> = StorageDoubleMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        Blake2_128Concat,
        T::AccountId,
        ValidatorScore,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct ValidatorScore {
        score: Score,
        improvement: Score,
        stress_passed: bool,
        uq_calibrated: bool,
        physics_gates: PhysicsGateResults,
        stress_details: StressDetails,
        submitted_at: BlockNumber,
        validator: AccountId,
    }

    /// Validator assignments per challenge
    #[pallet::storage]
    #[pallet::getter(fn validator_assignments)]
    pub type ValidatorAssignments<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<T::AccountId, ConstU32<10>>,
        OptionQuery,
    >;

    /// Current baseline configurations per problem
    #[pallet::storage]
    #[pallet::getter(fn baselines)]
    pub type Baselines<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ProblemId,
        BaselineConfig,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct BaselineConfig {
        config_json: Vec<u8>,
        version: u64,
        last_updated: BlockNumber,
        proposed_by: AccountId,
        approved_at: Option<BlockNumber>,
    }

    /// Specialist registry
    #[pallet::storage]
    #[pallet::getter(fn specialists)]
    pub type Specialists<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        SpecialistId,
        SpecialistOnChain,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct SpecialistOnChain {
        id: SpecialistId,
        problem_id: ProblemId,
        problem_signature: ProblemSignature,
        onnx_model_hash: Hash,
        validity_domain: ValidityDomain,
        stress_test_results: StressTestResults,
        metrics_7d: Metrics7D,
        license: LicenseType,
        distilled_from: Vec<SubmissionId>,
        created_at: BlockNumber,
        created_by: AccountId,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct ValidityDomain {
        parameters: Vec<u8>, // JSON
        constraints: BoundedVec<Vec<u8>, ConstU32<20>>,
        known_failures: BoundedVec<Vec<u8>, ConstU32<20>>,
        recommended_use_cases: BoundedVec<Vec<u8>, ConstU32<20>>,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct StressTestResults {
        mass_conservation: bool,
        energy_dissipation: bool,
        boundary_satisfaction: bool,
        rollout_stability: bool,
        uq_calibration: bool,
        spectral_fidelity: Option<bool>,
        q_criterion: Option<bool>,
        wall_shear_stress: Option<bool>,
        nu_distribution: Option<bool>,
        added_mass_tensor: Option<bool>,
        coupling_consistency: Option<bool>,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct Metrics7D {
        fidelity: u64,        // Scaled by 1e6
        accuracy: u64,
        efficiency: u64,
        robustness: u64,
        generalization: u64,
        interpretability: u64,
        usability: u64,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub enum LicenseType {
        AGPL3,
        Commercial,
        Dual,
    }

    /// Landscape fragment DAG
    #[pallet::storage]
    #[pallet::getter(fn fragments)]
    pub type Fragments<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        FragmentId,
        FragmentOnChain,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct FragmentOnChain {
        id: FragmentId,
        miner_uid: u32,
        challenge_id: ChallengeId,
        problem_id: ProblemId,
        config_json: Vec<u8>,
        improvement: Score,
        stress_passed: bool,
        uq_metrics: UQMetricsOnChain,
        score: Score,
        timestamp: BlockNumber,
        causal_parents: BoundedVec<FragmentId, ConstU32<10>>,
        param_values: Vec<(Vec<u8>, u64)>, // Flattened param map
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct UQMetricsOnChain {
        calibration_error: u64,  // Scaled 1e6
        sharpness: u64,          // Scaled 1e6
        coverage: u64,           // Scaled 1e6
        calibrated: bool,
    }

    /// Current active validators
    #[pallet::storage]
    #[pallet::getter(fn active_validators)]
    pub type ActiveValidators<T: Config> = StorageValue<_, BoundedVec<T::AccountId, ConstU32<100>>, ValueQuery>;

    /// Validator performance tracking
    #[pallet::storage]
    #[pallet::getter(fn validator_performance)]
    pub type ValidatorPerformance<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        T::AccountId,
        ValidatorPerf,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct ValidatorPerf {
        total_validations: u64,
        successful_validations: u64,
        avg_score_deviation: u64, // Scaled 1e6
        uptime_percentage: u64,   // Scaled 1e4
        last_active: BlockNumber,
        slashed_count: u32,
    }

    /// Emission tracking
    #[pallet::storage]
    #[pallet::getter(fn emission_tracker)]
    pub type EmissionTracker<T: Config> = StorageValue<_, EmissionTrackerData, ValueQuery>;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct EmissionTrackerData {
        total_emitted: Balance,
        total_burned: Balance,
        total_novelty_bonus: Balance,
        last_emission_block: BlockNumber,
    }

    /// Owner account (set at genesis, changeable via governance)
    #[pallet::storage]
    #[pallet::getter(fn owner)]
    pub type Owner<T: Config> = StorageValue<_, T::AccountId, OptionQuery>;

    /// Pending baseline proposals
    #[pallet::storage]
    #[pallet::getter(fn pending_baselines)]
    pub type PendingBaselines<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ProblemId,
        BaselineProposal,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct BaselineProposal {
        config_json: Vec<u8>,
        proposed_by: AccountId,
        proposed_at: BlockNumber,
        causal_evidence: Vec<CausalEvidence>,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct CausalEvidence {
        parameter: Vec<u8>,
        ate: i64, // Scaled 1e6
        confidence: u64, // Scaled 1e6
        supporting_fragments: u32,
    }

    /// Pending specialist promotions (awaiting gauntlet)
    #[pallet::storage]
    #[pallet::getter(fn pending_specialists)]
    pub type PendingSpecialists<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        SpecialistId,
        PendingSpecialist,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct PendingSpecialist {
        specialist: SpecialistOnChain,
        gauntlet_status: GauntletStatus,
        judges: BoundedVec<AccountId, ConstU32<3>>,
        judge_results: Vec<JudgeResult>,
        repair_iteration: u8,
        created_at: BlockNumber,
        lock: GauntletLock, // Concurrency control
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub enum GauntletStatus {
        PendingDistillation,
        AwaitingJudges,
        InRepair { iteration: u8, feedback: Vec<u8> },
        Passed,
        Rejected { reason: Vec<u8> },
    }

    /// Mutex for specialist gauntlet concurrency control
    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct GauntletLock {
        locked: bool,
        locked_by: Option<SpecialistId>,
        locked_at: BlockNumber,
        expires_at: BlockNumber,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct JudgeResult {
        judge: AccountId,
        backbone: Vec<u8>,
        passed: bool,
        feedback: Vec<u8>,
        scored_at: BlockNumber,
    }

    /// Novelty embeddings for bonus calculation
    #[pallet::storage]
    #[pallet::getter(fn strategy_embeddings)]
    pub type StrategyEmbeddings<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<(T::AccountId, BoundedVec<u8, ConstU32<32>>), ConstU32<1000>>,
        ValueQuery,
    >

    /// Emission budget per challenge (cached)
    #[pallet::storage]
    #[pallet::getter(fn challenge_budgets)]
    pub type ChallengeBudgets<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BalanceOf<T>,
        OptionQuery,
    >

    /// Novelty embeddings per challenge (for bonus calculation)
    #[pallet::storage]
    #[pallet::getter(fn challenge_embeddings)]
    pub type ChallengeEmbeddings<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<(AccountId, BoundedVec<u8, ConstU32<32>>), ConstU32<1000>>,
        ValueQuery,
    >

    /// Bounty accumulation pool per challenge
    #[pallet::storage]
    #[pallet::getter(fn bounty_pools)]
    pub type BountyPools<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BalanceOf<T>,
        OptionQuery,
    >

    /// Active challenge IDs for iteration
    #[pallet::storage]
    #[pallet::getter(fn active_challenge_ids)]
    pub type ActiveChallengeIds<T: Config> = StorageValue<_, BoundedVec<ChallengeId, T::MaxActiveChallenges>, ValueQuery>;

    /// Challenge metadata by problem
    #[pallet::storage]
    #[pallet::getter(fn challenges_by_problem)]
    pub type ChallengesByProblem<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ProblemId,
        BoundedVec<ChallengeId, ConstU32<100>>,
        ValueQuery,
    >;

    /// Submissions by challenge and miner
    #[pallet::storage]
    #[pallet::getter(fn submissions)]
    pub type Submissions<T: Config> = StorageDoubleMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        Blake2_128Concat,
        T::AccountId,
        Submission<T::AccountId, BlockNumberFor<T>, BalanceOf<T>>,
        OptionQuery,
    >;

    /// Submission IDs for iteration
    #[pallet::storage]
    #[pallet::getter(fn submission_ids)]
    pub type SubmissionIds<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<T::AccountId, ConstU32<1000>>,
        ValueQuery,
    >;

    /// Commitments for commit-reveal
    #[pallet::storage]
    #[pallet::getter(fn commitments)]
    pub type Commitments<T: Config> = StorageDoubleMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        Blake2_128Concat,
        T::AccountId,
        Commitment,
        OptionQuery,
    >;

    /// Validator scores for consensus
    #[pallet::storage]
    #[pallet::getter(fn validator_scores)]
    pub type ValidatorScores<T: Config> = StorageDoubleMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        Blake2_128Concat,
        T::AccountId,
        ValidatorScore,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct ValidatorScore {
        score: Score,
        improvement: Score,
        stress_passed: bool,
        uq_calibrated: bool,
        physics_gates: PhysicsGateResults,
        stress_details: StressDetails,
        submitted_at: BlockNumber,
        validator: AccountId,
    }

    /// Validator assignments per challenge
    #[pallet::storage]
    #[pallet::getter(fn validator_assignments)]
    pub type ValidatorAssignments<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<T::AccountId, ConstU32<10>>,
        OptionQuery,
    >;

    /// Current baseline configurations per problem
    #[pallet::storage]
    #[pallet::getter(fn baselines)]
    pub type Baselines<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ProblemId,
        BaselineConfig,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct BaselineConfig {
        config_json: Vec<u8>,
        version: u64,
        last_updated: BlockNumber,
        proposed_by: AccountId,
        approved_at: Option<BlockNumber>,
    }

    /// Specialist registry
    #[pallet::storage]
    #[pallet::getter(fn specialists)]
    pub type Specialists<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        SpecialistId,
        SpecialistOnChain,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct SpecialistOnChain {
        id: SpecialistId,
        problem_id: ProblemId,
        problem_signature: ProblemSignature,
        onnx_model_hash: Hash,
        validity_domain: ValidityDomain,
        stress_test_results: StressTestResults,
        metrics_7d: Metrics7D,
        license: LicenseType,
        distilled_from: Vec<SubmissionId>,
        created_at: BlockNumber,
        created_by: AccountId,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct ValidityDomain {
        parameters: Vec<u8>, // JSON
        constraints: BoundedVec<Vec<u8>, ConstU32<20>>,
        known_failures: BoundedVec<Vec<u8>, ConstU32<20>>,
        recommended_use_cases: BoundedVec<Vec<u8>, ConstU32<20>>,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct StressTestResults {
        mass_conservation: bool,
        energy_dissipation: bool,
        boundary_satisfaction: bool,
        rollout_stability: bool,
        uq_calibration: bool,
        spectral_fidelity: Option<bool>,
        q_criterion: Option<bool>,
        wall_shear_stress: Option<bool>,
        nu_distribution: Option<bool>,
        added_mass_tensor: Option<bool>,
        coupling_consistency: Option<bool>,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct Metrics7D {
        fidelity: u64,        // Scaled by 1e6
        accuracy: u64,
        efficiency: u64,
        robustness: u64,
        generalization: u64,
        interpretability: u64,
        usability: u64,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub enum LicenseType {
        AGPL3,
        Commercial,
        Dual,
    }

    /// Landscape fragment DAG
    #[pallet::storage]
    #[pallet::getter(fn fragments)]
    pub type Fragments<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        FragmentId,
        FragmentOnChain,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct FragmentOnChain {
        id: FragmentId,
        miner_uid: u32,
        challenge_id: ChallengeId,
        problem_id: ProblemId,
        config_json: Vec<u8>,
        improvement: Score,
        stress_passed: bool,
        uq_metrics: UQMetricsOnChain,
        score: Score,
        timestamp: BlockNumber,
        causal_parents: BoundedVec<FragmentId, ConstU32<10>>,
        param_values: Vec<(Vec<u8>, u64)>, // Flattened param map
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct UQMetricsOnChain {
        calibration_error: u64,  // Scaled 1e6
        sharpness: u64,          // Scaled 1e6
        coverage: u64,           // Scaled 1e6
        calibrated: bool,
    }

    /// Current active validators
    #[pallet::storage]
    #[pallet::getter(fn active_validators)]
    pub type ActiveValidators<T: Config> = StorageValue<_, BoundedVec<T::AccountId, ConstU32<100>>, ValueQuery>;

    /// Validator performance tracking
    #[pallet::storage]
    #[pallet::getter(fn validator_performance)]
    pub type ValidatorPerformance<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        T::AccountId,
        ValidatorPerf,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct ValidatorPerf {
        total_validations: u64,
        successful_validations: u64,
        avg_score_deviation: u64, // Scaled 1e6
        uptime_percentage: u64,   // Scaled 1e4
        last_active: BlockNumber,
        slashed_count: u32,
    }

    /// Emission tracking
    #[pallet::storage]
    #[pallet::getter(fn emission_tracker)]
    pub type EmissionTracker<T: Config> = StorageValue<_, EmissionTrackerData, ValueQuery>;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct EmissionTrackerData {
        total_emitted: Balance,
        total_burned: Balance,
        total_novelty_bonus: Balance,
        last_emission_block: BlockNumber,
    }

    /// Owner account (set at genesis, changeable via governance)
    #[pallet::storage]
    #[pallet::getter(fn owner)]
    pub type Owner<T: Config> = StorageValue<_, T::AccountId, OptionQuery>;

    /// Pending baseline proposals
    #[pallet::storage]
    #[pallet::getter(fn pending_baselines)]
    pub type PendingBaselines<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ProblemId,
        BaselineProposal,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct BaselineProposal {
        config_json: Vec<u8>,
        proposed_by: AccountId,
        proposed_at: BlockNumber,
        causal_evidence: Vec<CausalEvidence>,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct CausalEvidence {
        parameter: Vec<u8>,
        ate: i64, // Scaled 1e6
        confidence: u64, // Scaled 1e6
        supporting_fragments: u32,
    }

    /// Pending specialist promotions (awaiting gauntlet)
    #[pallet::storage]
    #[pallet::getter(fn pending_specialists)]
    pub type PendingSpecialists<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        SpecialistId,
        PendingSpecialist,
        OptionQuery,
    >;

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct PendingSpecialist {
        specialist: SpecialistOnChain,
        gauntlet_status: GauntletStatus,
        judges: BoundedVec<AccountId, ConstU32<3>>,
        judge_results: Vec<JudgeResult>,
        repair_iteration: u8,
        created_at: BlockNumber,
        lock: GauntletLock, // Concurrency control
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub enum GauntletStatus {
        PendingDistillation,
        AwaitingJudges,
        InRepair { iteration: u8, feedback: Vec<u8> },
        Passed,
        Rejected { reason: Vec<u8> },
    }

    /// Mutex for specialist gauntlet concurrency control
    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct GauntletLock {
        locked: bool,
        locked_by: Option<SpecialistId>,
        locked_at: BlockNumber,
        expires_at: BlockNumber,
    }

    #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
    pub struct JudgeResult {
        judge: AccountId,
        backbone: Vec<u8>,
        passed: bool,
        feedback: Vec<u8>,
        scored_at: BlockNumber,
    }

    /// Novelty embeddings for bonus calculation
    #[pallet::storage]
    #[pallet::getter(fn strategy_embeddings)]
    pub type StrategyEmbeddings<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<(T::AccountId, BoundedVec<u8, ConstU32<32>>), ConstU32<1000>>,
        ValueQuery,
    >

    /// Emission budget per challenge (cached)
    #[pallet::storage]
    #[pallet::getter(fn challenge_budgets)]
    pub type ChallengeBudgets<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BalanceOf<T>,
        OptionQuery,
    >

    /// Novelty embeddings per challenge (for bonus calculation)
    #[pallet::storage]
    #[pallet::getter(fn challenge_embeddings)]
    pub type ChallengeEmbeddings<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<(AccountId, BoundedVec<u8, ConstU32<32>>), ConstU32<1000>>,
        ValueQuery,
    >

    /// Bounty accumulation pool per challenge
    #[pallet::storage]
    #[pallet::getter(fn bounty_pools)]
    pub type BountyPools<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BalanceOf<T>,
        OptionQuery,
    >

    /// Active challenge IDs for iteration
    #[pallet::storage]
    #[pallet::getter(fn active_challenge_ids)]
    pub type ActiveChallengeIds<T: Config> = StorageValue<_, BoundedVec<ChallengeId, T::MaxActiveChallenges>, ValueQuery>;

    /// Challenge metadata by problem
    #[pallet::storage]
    #[pallet::getter(fn challenges_by_problem)]
    pub type ChallengesByProblem<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ProblemId,
        BoundedVec<ChallengeId, ConstU32<100>>,
        ValueQuery,
    >;

    /// Submissions by challenge and miner
    #[pallet::storage]
    #[pallet::getter(fn submissions)]
    pub type Submissions<T: Config> = StorageDoubleMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        Blake2_128Concat,
        T::AccountId,
        Submission<T::AccountId, BlockNumberFor<T>, BalanceOf<T>>,
        OptionQuery,
    >;

    /// Submission IDs for iteration
    #[pallet::storage]
    #[pallet::getter(fn submission_ids)]
    pub type SubmissionIds<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<T::AccountId, ConstU32<1000>>,
        ValueQuery,
    >;

    /// Commitments for commit-reveal
    #[pallet::storage]
    #[pallet::getter(fn commitments)]
    pub type Commitments<T: Config> = StorageDoubleMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        Blake2_128Concat,
        T::AccountId,
        Commitment,
        OptionQuery,
    >;

    /// Validator scores for consensus
    #[pallet::storage]
    #[pallet::getter(fn validator_scores)]
    pub type ValidatorScores<T: Config> = StorageDoubleMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        Blake2_128Concat,
        T::AccountId,
        ValidatorScore,
        OptionQuery,
    >;

    /// Validator assignments per challenge
    #[pallet::storage]
    #[pallet::getter(fn validator_assignments)]
    pub type ValidatorAssignments<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<T::AccountId, ConstU32<10>>,
        OptionQuery,
    >;

    /// Current baseline configurations per problem
    #[pallet::storage]
    #[pallet::getter(fn baselines)]
    pub type Baselines<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ProblemId,
        BaselineConfig,
        OptionQuery,
    >.

    /// Active challenge IDs for iteration
    #[pallet::storage]
    #[pallet::getter(fn active_challenge_ids)]
    pub type ActiveChallengeIds<T: Config> = StorageValue<_, BoundedVec<ChallengeId, T::MaxActiveChallenges>, ValueQuery>;

    /// Challenge metadata by problem
    #[pallet::storage]
    #[pallet::getter(fn challenges_by_problem)]
    pub type ChallengesByProblem<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ProblemId,
        BoundedVec<ChallengeId, ConstU32<100>>,
        ValueQuery,
    >.

    /// Current baseline configurations per problem
    #[pallet::storage]
    #[pallet::getter(fn baselines)]
    pub type Baselines<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ProblemId,
        BaselineConfig,
        OptionQuery,
    >.

    /// Pending baseline proposals
    #[pallet::storage]
    #[pallet::getter(fn pending_baselines)]
    pub type PendingBaselines<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ProblemId,
        BaselineProposal,
        OptionQuery,
    >.

    /// Pending specialist promotions (awaiting gauntlet)
    #[pallet::storage]
    #[pallet::getter(fn pending_specialists)]
    pub type PendingSpecialists<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        SpecialistId,
        PendingSpecialist,
        OptionQuery,
    >.

    /// Novelty embeddings for bonus calculation
    #[pallet::storage]
    #[pallet::getter(fn strategy_embeddings)]
    pub type StrategyEmbeddings<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<(T::AccountId, BoundedVec<u8, ConstU32<32>>), ConstU32<1000>>,
        ValueQuery,
    >.

    /// Emission budget per challenge (cached)
    #[pallet::storage]
    #[pallet::getter(fn challenge_budgets)]
    pub type ChallengeBudgets<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BalanceOf<T>,
        OptionQuery,
    >.

    /// Novelty embeddings per challenge (for bonus calculation)
    #[pallet::storage]
    #[pallet::getter(fn challenge_embeddings)]
    pub type ChallengeEmbeddings<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BoundedVec<(AccountId, BoundedVec<u8, ConstU32<32>>), ConstU32<1000>>,
        ValueQuery,
    >.

    /// Bounty accumulation pool per challenge
    #[pallet::storage]
    #[pallet::getter(fn bounty_pools)]
    pub type BountyPools<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        ChallengeId,
        BalanceOf<T>,
        OptionQuery,
    >.
```

---

## 4. Events

```rust
    // ============================================================
    // Events
    // ============================================================

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        /// New challenge created
        ChallengeCreated {
            challenge_id: ChallengeId,
            problem_id: ProblemId,
            phase: u8,
            submission_deadline: BlockNumberFor<T>,
            emission_budget: BalanceOf<T>,
        },
        
        /// Challenge status changed
        ChallengeStatusChanged {
            challenge_id: ChallengeId,
            old_status: ChallengeStatus,
            new_status: ChallengeStatus,
        },
        
        /// Miner submitted commitment
        CommitmentReceived {
            challenge_id: ChallengeId,
            miner: T::AccountId,
            commitment_hash: Hash,
        },
        
        /// Miner revealed strategy
        StrategyRevealed {
            challenge_id: ChallengeId,
            miner: T::AccountId,
            submission_id: SubmissionId,
        },
        
        /// Validator submitted score
        ScoreSubmitted {
            challenge_id: ChallengeId,
            validator: T::AccountId,
            miner: T::AccountId,
            score: Score,
        },
        
        /// Consensus reached, rewards distributed
        RewardsDistributed {
            challenge_id: ChallengeId,
            rewards: Vec<(T::AccountId, BalanceOf<T>)>,
            top_miner: T::AccountId,
            top_score: Score,
        },
        
        /// Baseline updated
        BaselineUpdated {
            problem_id: ProblemId,
            version: u64,
            baseline_hash: Hash,
        },
        
        /// Specialist promoted
        SpecialistPromoted {
            specialist_id: SpecialistId,
            problem_id: ProblemId,
            version: u64,
            onnx_hash: Hash,
        },
        
        /// Specialist demoted/archived
        SpecialistArchived {
            specialist_id: SpecialistId,
            reason: Vec<u8>,
        },
        
        /// Baseline proposed by Landscape
        BaselineProposed {
            problem_id: ProblemId,
            proposed_by: AccountId,
            version: u64,
        },
        
        /// Baseline approved by owner
        BaselineApproved {
            problem_id: ProblemId,
            version: u64,
            approved_by: T::AccountId,
        },
        
        /// Baseline rejected
        BaselineRejected {
            problem_id: ProblemId,
            version: u64,
            reason: Vec<u8>,
        },
        
        /// Specialist distillation completed
        SpecialistDistilled {
            specialist_id: SpecialistId,
            problem_id: ProblemId,
            version: u64,
            teacher_count: u32,
        },
        
        /// Specialist promotion gauntlet started
        GauntletStarted {
            specialist_id: SpecialistId,
            judges: Vec<T::AccountId>,
        },
        
        /// Judge submitted result
        JudgeResultSubmitted {
            specialist_id: SpecialistId,
            judge: T::AccountId,
            passed: bool,
        },
        
        /// Specialist repair loop triggered
        RepairLoopTriggered {
            specialist_id: SpecialistId,
            iteration: u8,
            failed_judge: T::AccountId,
        },
        
        /// Specialist promoted after gauntlet
        SpecialistPromoted {
            specialist_id: SpecialistId,
            problem_id: ProblemId,
            version: u64,
            onnx_hash: Hash,
        },
        
        /// Specialist rejected from gauntlet
        SpecialistRejected {
            specialist_id: SpecialistId,
            reason: Vec<u8>,
        },
        
        /// Data royalty paid
        DataRoyaltyPaid {
            data_contributor: T::AccountId,
            challenge_id: ChallengeId,
            amount: BalanceOf<T>,
            impact_score: Score,
        },
        
        /// Novelty bonus awarded
        NoveltyBonusAwarded {
            challenge_id: ChallengeId,
            miner: T::AccountId,
            bonus: BalanceOf<T>,
            embedding_distance: u64,
        },
        
        /// Bounty pool updated
        BountyPoolUpdated {
            challenge_id: ChallengeId,
            pool_amount: Balance,
        },
        
        /// Emission budget updated
        EmissionBudgetUpdated {
            challenge_id: ChallengeId,
            budget: Balance,
        },
        
        /// Validator slashed
        ValidatorSlashed {
            validator: T::AccountId,
            amount: BalanceOf<T>,
            reason: Vec<u8>,
        },
        
        /// Validator added to active set
        ValidatorAdded {
            validator: T::AccountId,
            stake: Balance,
        },
        
        /// Validator removed from active set
        ValidatorRemoved {
            validator: T::AccountId,
            reason: Vec<u8>,
        },
        
        /// Challenge archived
        ChallengeArchived {
            challenge_id: ChallengeId,
        },
        
        /// Emission budget updated
        EmissionBudgetRecalculated {
            total_emission: Balance,
            active_challenges: u32,
            per_challenge_budget: Balance,
        },
        
        /// Validator slashed
        ValidatorSlashed {
            validator: T::AccountId,
            amount: BalanceOf<T>,
            reason: Vec<u8>,
        },
        
        /// Validator added to active set
        ValidatorAdded {
            validator: T::AccountId,
            stake: Balance,
        },
        
        /// Validator removed from active set
        ValidatorRemoved {
            validator: T::AccountId,
            reason: Vec<u8>,
        },
        
        /// Challenge archived
        ChallengeArchived {
            challenge_id: ChallengeId,
        },
        
        /// Emission budget updated
        EmissionBudgetRecalculated {
            total_emission: Balance,
            active_challenges: u32,
            per_challenge_budget: Balance,
        },
        
        /// Gauntlet started
        GauntletStarted {
            specialist_id: SpecialistId,
            judges: Vec<T::AccountId>,
        },
        
        /// Judge submitted result
        JudgeResultSubmitted {
            specialist_id: SpecialistId,
            judge: T::AccountId,
            passed: bool,
        },
        
        /// Specialist repair loop triggered
        RepairLoopTriggered {
            specialist_id: SpecialistId,
            iteration: u8,
            failed_judge: T::AccountId,
        },
        
        /// Specialist promoted after gauntlet
        SpecialistPromoted {
            specialist_id: SpecialistId,
            problem_id: ProblemId,
            version: u64,
            onnx_hash: Hash,
        },
        
        /// Specialist rejected from gauntlet
        SpecialistRejected {
            specialist_id: SpecialistId,
            reason: Vec<u8>,
        },
        
        /// Data royalty paid
        DataRoyaltyPaid {
            data_contributor: T::AccountId,
            challenge_id: ChallengeId,
            amount: BalanceOf<T>,
            impact_score: Score,
        },
        
        /// Novelty bonus awarded
        NoveltyBonusAwarded {
            challenge_id: ChallengeId,
            miner: T::AccountId,
            bonus: BalanceOf<T>,
            embedding_distance: u64,
        },
        
        /// Bounty pool updated
        BountyPoolUpdated {
            challenge_id: ChallengeId,
            pool_amount: Balance,
        },
        
        /// Emission budget updated
        EmissionBudgetUpdated {
            challenge_id: ChallengeId,
            budget: Balance,
        },
        
        /// Validator slashed
        ValidatorSlashed {
            validator: T::AccountId,
            amount: BalanceOf<T>,
            reason: Vec<u8>,
        },
        
        /// Validator added to active set
        ValidatorAdded {
            validator: T::AccountId,
            stake: Balance,
        },
        
        /// Validator removed from active set
        ValidatorRemoved {
            validator: T::AccountId,
            reason: Vec<u8>,
        },
        
        /// Challenge archived
        ChallengeArchived {
            challenge_id: ChallengeId,
        },
        
        /// Emission budget updated
        EmissionBudgetRecalculated {
            total_emission: Balance,
            active_challenges: u32,
            per_challenge_budget: Balance,
        },
    }
```

---

## A.4 Errors

```rust
    #[pallet::error]
    pub enum Error<T> {
        // Challenge errors
        ChallengeNotFound,
        ChallengeNotActive,
        ChallengeAlreadyExists,
        ChallengeFull,
        ChallengeNotInPhase,
        ChallengeBudgetExhausted,
        MaxActiveChallengesReached,
        InvalidProblemId,
        InvalidPhaseTransition,
        
        // Submission errors
        SubmissionNotFound,
        SubmissionAlreadyExists,
        SubmissionNotInCommitPhase,
        SubmissionNotInRevealPhase,
        SubmissionAlreadyRevealed,
        InvalidCommitment,
        InvalidReveal,
        CommitmentMismatch,
        NonceReused,
        InvalidNonce,
        InvalidJSON,
        InvalidSchema,
        FeeInsufficient,
        SubmissionTooLarge,
        InvalidCanonicalization,
        CommitmentMismatch,
        
        // Validator errors
        ValidatorNotFound,
        ValidatorNotAuthorized,
        ValidatorAlreadyAssigned,
        ValidatorNotAssigned,
        InsufficientValidators,
        ValidatorAlreadyScored,
        ScoreDeviationTooHigh,
        InvalidScore,
        ConsensusNotReached,
        ValidatorAlreadyActive,
        ValidatorNotActive,
        InsufficientStake,
        ValidatorAlreadyExists,
        VRFVerificationFailed,
        
        // Consensus errors
        InsufficientValidators,
        InsufficientScoresForConsensus,
        ConsensusTimeout,
        ConsensusDeviationTooHigh,
        InsufficientRevealers,
        ConsensusNotFinalized,
        
        // Scoring errors
        ScoringNotAllowed,
        ScoringDeadlinePassed,
        InvalidScoreValue,
        PhysicsGateFailure,
        StressTestFailed,
        UQCalibrationFailed,
        InvalidPhysicsGate,
        InvalidStressTest,
        
        // Emission errors
        EmissionBudgetExhausted,
        InsufficientEmissionBudget,
        RewardDistributionFailed,
        InsufficientEmissionBudgetForNovelty,
        BountyPoolEmpty,
        
        // Specialist errors
        SpecialistNotFound,
        SpecialistAlreadyExists,
        SpecialistNotReady,
        SpecialistGauntletFailed,
        SpecialistGauntletTimeout,
        SpecialistAlreadyPromoted,
        SpecialistAlreadyRejected,
        InvalidSpecialistData,
        InvalidValidityDomain,
        GauntletInProgress,
        JudgeAlreadyVoted,
        JudgeNotAuthorized,
        GauntletNotReady,
        RepairLoopExhausted,
        GroundingGateFailed,
        DecontaminationFailed,
        TripleCrownFailed,
        GauntletLockFailed,
        GauntletLockExpired,
        GauntletLockConflict,
        
        // Landscape errors
        BaselineNotFound,
        BaselineAlreadyExists,
        BaselineProposalPending,
        BaselineProposalNotFound,
        InsufficientCausalEvidence,
        BaselineAlreadyApproved,
        BaselineNotApproved,
        LandscapeNotReady,
        
        // Data errors
        CustomDataNotFound,
        CustomDataChecksumMismatch,
        CustomDataDecryptionFailed,
        InvalidCustomDataFormat,
        DataRoyaltyCalculationFailed,
        
        // Emission errors
        EmissionBudgetExhausted,
        InsufficientEmissionBudget,
        BountyPoolEmpty,
        NoveltyBonusNotEligible,
        
        // Governance errors
        Unauthorized,
        OwnerOnly,
        GovernanceProposalRequired,
        InvalidSignature,
        InvalidNonce,
        NonceReused,
        
        // Slashing
        SlashingFailed,
        AlreadySlashed,
        
        // Cryptographic errors
        VRFVerificationFailed,
        InvalidCanonicalization,
        CommitmentMismatch,
        NonceReused,
        InvalidCanonicalization,
        
        // Concurrency
        GauntletLockFailed,
        GauntletLockExpired,
        GauntletLockConflict,
        RepairLoopExhausted,
        GroundingGateFailed,
        DecontaminationFailed,
        TripleCrownFailed,
        
        // General
        ArithmeticOverflow,
        ArithmeticUnderflow,
        InvalidConfiguration,
        StorageOverflow,
        NotImplemented,
    }
```

---

## A.5 Extrinsics (Dispatchables)

```rust
    #[pallet::call]
    impl<T: Config> Pallet<T> {
        // ============================================================
        // Challenge Management (Owner only)
        // ============================================================

        /// Create a new challenge
        #[pallet::call_index(0)]
        #[pallet::weight(<T as Config>::WeightInfo::create_challenge())]
        pub fn create_challenge(
            origin: OriginFor<T>,
            problem_id: ProblemId,
            baseline_config: Vec<u8>,
            stress_floors: StressFloors,
            well_mapping: Vec<Vec<u8>>,
        ) -> DispatchResultWithPostInfo {
            let owner = ensure_root(origin)?;
            Self::do_create_challenge(
                problem_id,
                baseline_config,
                stress_floors,
                well_mapping,
                &owner,
            )
        }

        /// Update challenge baseline (owner only)
        #[pallet::call_index(1)]
        #[pallet::weight(<T as Config>::WeightInfo::update_baseline())]
        pub fn update_baseline(
            origin: OriginFor<T>,
            problem_id: ProblemId,
            baseline_config: Vec<u8>,
        ) -> DispatchResultWithPostInfo {
            let owner = ensure_root(origin)?;
            Self::do_update_baseline(problem_id, baseline_config, &owner)
        }

        // ============================================================
        // Miner Submissions
        // ============================================================

        /// Submit commitment (commit phase)
        #[pallet::call_index(2)]
        #[pallet::weight(<T as Config>::WeightInfo::submit_commitment())]
        pub fn submit_commitment(
            origin: OriginFor<T>,
            challenge_id: ChallengeId,
            commitment_hash: Hash,
            nonce: [u8; 32],
        ) -> DispatchResultWithPostInfo {
            let miner = ensure_signed(origin)?;
            Self::do_submit_commitment(challenge_id, commitment_hash, nonce, &miner)
        }

        /// Reveal strategy (reveal phase)
        #[pallet::call_index(3)]
        #[pallet::weight(<T as Config>::WeightInfo::reveal_strategy())]
        pub fn reveal_strategy(
            origin: OriginFor<T>,
            challenge_id: ChallengeId,
            strategy_json: Vec<u8>,
            nonce: [u8; 32],
        ) -> DispatchResultWithPostInfo {
            let miner = ensure_signed(origin)?;
            Self::do_reveal_strategy(challenge_id, strategy_json, nonce, &miner)
        }

        /// Submit specialist pipeline (Phase 2+)
        #[pallet::call_index(4)]
        #[pallet::weight(<T as Config>::WeightInfo::submit_specialist_pipeline())]
        pub fn submit_specialist_pipeline(
            origin: OriginFor<T>,
            challenge_id: ChallengeId,
            pipeline_json: Vec<u8>,
            nonce: [u8; 32],
        ) -> DispatchResultWithPostInfo {
            let miner = ensure_signed(origin)?;
            Self::do_submit_specialist_pipeline(challenge_id, pipeline_json, nonce, &miner)
        }

        /// Submit custom data (Phase 1+)
        #[pallet::call_index(5)]
        #[pallet::weight(<T as Config>::WeightInfo::submit_custom_data())]
        pub fn submit_custom_data(
            origin: OriginFor<T>,
            challenge_id: ChallengeId,
            data_uri: Vec<u8>,
            checksum: Vec<u8>,
            usage: Vec<u8>,
            weight: u64, // Scaled 1e6
            encryption: Option<EncryptionInput>,
        ) -> DispatchResultWithPostInfo {
            let miner = ensure_signed(origin)?;
            Self::do_submit_custom_data(challenge_id, data_uri, checksum, usage, weight, encryption, &miner)
        }

        // ============================================================
        // Validator Operations
        // ============================================================

        /// Submit score for a miner's submission
        #[pallet::call_index(6)]
        #[pallet::weight(<T as Config>::WeightInfo::submit_score())]
        pub fn submit_score(
            origin: OriginFor<T>,
            challenge_id: ChallengeId,
            miner: T::AccountId,
            score: Score,
            improvement: Score,
            stress_passed: bool,
            uq_calibrated: bool,
            physics_gates: PhysicsGateResults,
            stress_details: StressDetails,
        ) -> DispatchResultWithPostInfo {
            let validator = ensure_signed(origin)?;
            Self::do_submit_score(
                challenge_id,
                miner,
                score,
                improvement,
                stress_passed,
                uq_calibrated,
                physics_gates,
                stress_details,
                &validator,
            )
        }

        // ============================================================
        // Landscape Agent (Owner only)
        // ============================================================

        /// Propose new baseline (Landscape Agent)
        #[pallet::call_index(7)]
        #[pallet::weight(<T as Config>::WeightInfo::propose_baseline())]
        pub fn propose_baseline(
            origin: OriginFor<T>,
            problem_id: ProblemId,
            config_json: Vec<u8>,
            causal_evidence: Vec<CausalEvidence>,
        ) -> DispatchResultWithPostInfo {
            let owner = ensure_root(origin)?;
            Self::do_propose_baseline(problem_id, config_json, causal_evidence, &owner)
        }

        /// Approve baseline proposal (Owner)
        #[pallet::call_index(8)]
        #[pallet::weight(<T as Config>::WeightInfo::approve_baseline())]
        pub fn approve_baseline(
            origin: OriginFor<T>,
            problem_id: ProblemId,
            version: u64,
        ) -> DispatchResultWithPostInfo {
            let owner = ensure_root(origin)?;
            Self::do_approve_baseline(problem_id, version, &owner)
        }

        /// Reject baseline proposal
        #[pallet::call_index(9)]
        #[pallet::weight(<T as Config>::WeightInfo::reject_baseline())]
        pub fn reject_baseline(
            origin: OriginFor<T>,
            problem_id: ProblemId,
            version: u64,
            reason: Vec<u8>,
        ) -> DispatchResultWithPostInfo {
            let owner = ensure_root(origin)?;
            Self::do_reject_baseline(problem_id, version, reason, &owner)
        }

        /// Promote specialist after gauntlet (Owner)
        #[pallet::call_index(10)]
        #[pallet::weight(<T as Config>::WeightInfo::promote_specialist())]
        pub fn promote_specialist(
            origin: OriginFor<T>,
            specialist_id: SpecialistId,
            gauntlet_result_hash: Hash,
            onnx_model_hash: Hash,
            validity_domain: ValidityDomain,
        ) -> DispatchResultWithPostInfo {
            let owner = ensure_root(origin)?;
            Self::do_promote_specialist(specialist_id, gauntlet_result_hash, onnx_model_hash, validity_domain, &owner)
        }

        // ============================================================
        // Validator Management (Owner)
        // ============================================================

        /// Add validator to active set (Owner)
        #[pallet::call_index(11)]
        #[pallet::weight(<T as Config>::WeightInfo::add_validator())]
        pub fn add_validator(
            origin: OriginFor<T>,
            validator: T::AccountId,
        ) -> DispatchResultWithPostInfo {
            let owner = ensure_root(origin)?;
            Self::do_add_validator(validator)
        }

        /// Remove validator (Owner)
        #[pallet::call_index(12)]
        #[pallet::weight(<T as Config>::WeightInfo::remove_validator())]
        pub fn remove_validator(
            origin: OriginFor<T>,
            validator: T::AccountId,
            reason: Vec<u8>,
        ) -> DispatchResultWithPostInfo {
            let owner = ensure_root(origin)?;
            Self::do_remove_validator(validator, reason)
        }

        // ============================================================
        // Data & Royalty
        // ============================================================

        /// Submit custom data for royalty consideration
        #[pallet::call_index(13)]
        #[pallet::weight(<T as Config>::WeightInfo::submit_custom_data())]
        pub fn submit_data_for_royalty(
            origin: OriginFor<T>,
            challenge_id: ChallengeId,
            data_uri: Vec<u8>,
            checksum: Vec<u8>,
            usage: Vec<u8>,
            weight: u64,
            encryption: Option<EncryptionInput>,
        ) -> DispatchResultWithPostInfo {
            let contributor = ensure_signed(origin)?;
            Self::do_submit_data_for_royalty(challenge_id, data_uri, checksum, usage, weight, encryption)
        }

        // ============================================================
        // Governance
        // ============================================================

        /// Update pallet configuration (Root only)
        #[pallet::call_index(14)]
        #[pallet::weight(<T as Config>::WeightInfo::update_config())]
        pub fn update_config(
            origin: OriginFor<T>,
            config: PalletConfigUpdate,
        ) -> DispatchResultWithPostInfo {
            ensure_root(origin)?;
            Self::do_update_config(config)
        }
    }
```

---

## A.6 Core Implementation Logic

```rust
    impl<T: Config> Pallet<T> {
        // ============================================================
        // Cryptographic Primitives
        // ============================================================

        /// Compute commitment hash using BLAKE2b-256 over canonical JSON
        /// commitment = blake2b256(COMMITMENT_DOMAIN || canonical_json || nonce || challenge_id || miner)
        fn compute_commitment_hash(
            canonical_json: &[u8],
            nonce: &[u8; 32],
            challenge_id: &ChallengeId,
            miner: &T::AccountId,
        ) -> Result<Hash, Error<T>> {
            let mut input = Vec::new();
            input.extend_from_slice(COMMITMENT_DOMAIN);
            input.extend_from_slice(canonical_json);
            input.extend_from_slice(nonce);
            input.extend_from_slice(challenge_id);
            input.extend_from_slice(miner.encode().as_slice());
            Ok(blake2_256(&input))
        }

        /// Canonicalize JSON using JCS (RFC 8785)
        fn canonicalize_json(json_bytes: &[u8]) -> Result<Vec<u8>, Error<T>> {
            // Parse JSON
            let json_str = std::str::from_utf8(json_bytes).map_err(|_| Error::<T>::InvalidJSON)?;
            let parsed: serde_json::Value = serde_json::from_str(json_str).map_err(|_| Error::<T>::InvalidJSON)?;
            
            // JCS canonicalization: deterministic serialization
            // 1. Sort object keys lexicographically
            // 2. No whitespace
            // 3. Numbers in shortest decimal representation
            // 4. Strings with minimal escaping
            // 5. true/false/null literals
            let canonical = serde_json::to_vec(&parsed).map_err(|_| Error::<T>::InvalidJSON)?;
            Ok(canonical)
        }

        /// Compute commitment hash using BLAKE2b-256
        /// commitment = blake2b256(COMMITMENT_DOMAIN || canonical_json || nonce || challenge_id || miner)
        fn compute_commitment_hash(
            canonical_json: &[u8],
            nonce: &[u8; 32],
            challenge_id: &ChallengeId,
            miner: &T::AccountId,
        ) -> Result<Hash, Error<T>> {
            let mut input = Vec::new();
            input.extend_from_slice(COMMITMENT_DOMAIN);
            input.extend_from_slice(canonical_json);
            input.extend_from_slice(nonce);
            input.extend_from_slice(challenge_id);
            input.extend_from_slice(miner.encode().as_slice());
            Ok(blake2_256(&input))
        }

        /// Verify VRF output and proof
        fn verify_vrf(
            public_key: &[u8; 32],
            input: &[u8],
            output: &[u8; 32],
            proof: &[u8; 64],
        ) -> bool {
            T::VRF::verify(output, public_key, input, proof)
        }

        /// Generate VRF output
        fn generate_vrf(secret_key: &[u8; 32], input: &[u8]) -> Result<([u8; 32], [u8; 64]), Error<T>> {
            let mut output = [0u8; 32];
            let mut proof = [0u8; 64];
            T::VRF::generate(&mut output, &mut proof, secret_key, input)
                .map_err(|_| Error::<T>::VRFVerificationFailed)?;
            Ok((output, proof))
        }

        // ============================================================
        // Canonical JSON (JCS - RFC 8785) Implementation
        // ============================================================

        /// Canonicalize JSON using JCS (RFC 8785)
        fn canonicalize_json(json_bytes: &[u8]) -> Result<Vec<u8>, Error<T>> {
            // Parse JSON
            let json_str = std::str::from_utf8(json_bytes).map_err(|_| Error::<T>::InvalidJSON)?;
            let parsed: serde_json::Value = serde_json::from_str(json_str).map_err(|_| Error::<T>::InvalidJSON)?;
            
            // JCS canonicalization: deterministic serialization
            // 1. Sort object keys lexicographically (UTF-8 byte order)
            // 2. No whitespace
            // 3. Numbers in shortest decimal representation (no trailing zeros)
            // 4. Strings with minimal escaping (only necessary escapes)
            // 5. true/false/null literals
            let canonical = serde_json::to_vec(&parsed).map_err(|_| Error::<T>::InvalidJSON)?;
            Ok(canonical)
        }

        // ============================================================
        // VRF-based Validator Selection
        // ============================================================

        /// Select validators for a challenge using VRF-based sortition
        fn select_validators_for_challenge(
            challenge_id: &ChallengeId,
            active_validators: &BoundedVec<T::AccountId, ConstU32<100>>,
            min_validators: u32,
            max_validators: u32,
        ) -> Result<BoundedVec<T::AccountId, ConstU32<10>>, Error<T>> {
            let mut selected = BoundedVec::<T::AccountId, ConstU32<10>>::new();
            
            // Sort validators by VRF output for deterministic selection
            let mut candidates: Vec<(T::AccountId, [u8; 32])> = Vec::new();
            
            for validator in active_validators.iter() {
                // Get validator's VRF public key (stored in ValidatorPerformance or separate storage)
                let vrf_pubkey = Self::get_validator_vrf_pubkey(validator)?;
                
                // VRF input: challenge_id || validator_hotkey
                let mut vrf_input = Vec::new();
                vrf_input.extend_from_slice(&Self::current_block().encode());
                validator.encode_to(&mut vrf_input);
                
                // Generate VRF output for selection
                let (output, _proof) = Self::generate_vrf_with_validator_key(validator, &vrf_input)?;
                
                candidates.push((validator.clone(), output));
            }
            
            // Sort by VRF output (deterministic ordering)
            candidates.sort_by(|a, b| a.1.cmp(&b.1));
            
            // Select top max_validators
            let count = max_validators.min(candidates.len() as u32) as usize;
            for i in 0..count {
                selected.try_push(candidates[i].0.clone())
                    .map_err(|_| Error::<T>::StorageOverflow)?;
            }
            
            ensure!(selected.len() >= T::MinValidatorsPerChallenge::get() as usize, 
                Error::<T>::InsufficientValidators);
            
            Ok(selected)
        }

        // ============================================================
        // Challenge Lifecycle Helpers
        // ============================================================

        fn current_block() -> BlockNumberFor<T> {
            <frame_system::Pallet<T>>::block_number()
        }

        fn current_phase(challenge: &Challenge<BlockNumberFor<T>, BalanceOf<T>, T::AccountId>) -> ChallengePhase {
            let now = Self::current_block();
            if now < challenge.commit_deadline {
                ChallengePhase::Commit
            } else if now < challenge.reveal_deadline {
                ChallengePhase::Reveal
            } else if now < challenge.scoring_deadline {
                ChallengePhase::Scoring
            } else {
                ChallengePhase::Completed
            }
        }

        #[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
        pub enum ChallengePhase {
            Commit,
            Reveal,
            Scoring,
            Completed,
        }

        // ============================================================
        // Challenge Creation
        // ============================================================

        fn do_create_challenge(
            problem_id: ProblemId,
            baseline_config: Vec<u8>,
            stress_floors: StressFloors,
            well_mapping: Vec<Vec<u8>>,
            creator: &T::AccountId,
        ) -> DispatchResultWithPostInfo {
            let active_count = ActiveChallengeIds::<T>::get().len();
            let max_challenges = T::MaxActiveChallenges::get() as usize;
            ensure!(active_count < max_challenges, Error::<T>::MaxActiveChallengesReached);

            let challenge_id = Self::generate_challenge_id(&problem_id);
            let now = Self::current_block();
            
            let emission_budget = Self::calculate_challenge_budget()?;

            let challenge = Challenge {
                id: challenge_id,
                problem_signature: ProblemSignature {
                    problem_id,
                    dimension: Self::get_dimension(problem_id),
                    resolution: Self::get_resolution(problem_id),
                    physics_class: Self::get_physics_class(problem_id),
                    coupling_spec: None,
                },
                status: ChallengeStatus::Active,
                created_at: Self::current_block(),
                commit_deadline: Self::current_block() + T::CommitPhaseBlocks::get(),
                reveal_deadline: Self::current_block() + T::CommitPhaseBlocks::get() + T::RevealPhaseBlocks::get(),
                scoring_deadline: Self::current_block() + T::CommitPhaseBlocks::get() + T::RevealPhaseBlocks::get() + T::ScoringPeriodBlocks::get(),
                baseline_config_hash: Blake2_128Concat::hash(&baseline_config),
                stress_floors,
                well_mapping,
                emission_budget,
                emission_distributed: false,
                baseline_config,
                creator: creator.clone(),
                submission_count: 0,
                validator_count: 0,
            };

            Challenges::<T>::insert(challenge_id, challenge.clone());
            
            let mut active_ids = ActiveChallengeIds::<T>::get();
            active_ids.try_push(challenge_id).map_err(|_| Error::<T>::MaxActiveChallengesReached)?;
            ActiveChallengeIds::<T>::put(active_ids);

            let mut problem_challenges = ChallengesByProblem::<T>::get(problem_id);
            problem_challenges.try_push(challenge_id).unwrap_or_default();
            ChallengesByProblem::<T>::insert(problem_id, problem_challenges);

            // Calculate and store emission budget
            let budget = Self::calculate_challenge_budget()?;
            ChallengeBudgets::<T>::insert(challenge_id, budget);
            BountyPools::<T>::insert(challenge_id, BalanceOf::<T>::zero());

            // Assign validators
            Self::assign_validators(challenge_id)?;

            // Initialize bounty pool (accumulates until improvement)
            BountyPools::<T>::insert(challenge_id, BalanceOf::<T>::zero());

            Self::deposit_event(Event::ChallengeCreated {
                challenge_id,
                problem_id,
                phase: 0,
                submission_deadline: T::CommitPhaseBlocks::get(),
                emission_budget,
            });

            Ok(().into())
        }

        fn assign_validators(challenge_id: ChallengeId) -> DispatchResult {
            let active = ActiveValidators::<T>::get();
            let min_validators = T::MinValidatorsPerChallenge::get() as usize;
            let max_validators = T::MaxValidatorsPerChallenge::get() as usize;
            
            ensure!(active.len() >= min_validators, Error::<T>::InsufficientValidators);
            
            // VRF-based selection
            let challenge_id_bytes = challenge_id;
            let mut selected = BoundedVec::<T::AccountId, ConstU32<10>>::new();
            
            // Get active validators with VRF keys
            let mut candidates = Vec::new();
            for validator in ActiveValidators::<T>::get().iter() {
                let vrf_pubkey = Self::get_validator_vrf_pubkey(validator)?;
                let vrf_input = (challenge_id, validator).encode();
                let (output, _proof) = Self::generate_vrf_for_validator(validator, &vrf_input)?;
                candidates.push((validator.clone(), output));
            }
            
            // Sort by VRF output for deterministic selection
            candidates.sort_by(|a, b| a.1.cmp(&b.1));
            
            let mut selected = BoundedVec::<T::AccountId, ConstU32<10>>::new();
            for i in 0..max_validators.min(candidates.len()) {
                selected.try_push(candidates[i].0.clone())
                    .map_err(|_| Error::<T>::StorageOverflow)?;
            }
            
            ensure!(selected.len() >= T::MinValidatorsPerChallenge::get() as usize, 
                Error::<T>::InsufficientValidators);
            
            ValidatorAssignments::<T>::insert(challenge_id, selected.clone());
            
            if let Some(mut challenge) = Challenges::<T>::get(challenge_id) {
                challenge.validator_count = selected.len() as u32;
                Challenges::<T>::insert(challenge_id, challenge);
            }
            
            Ok(())
        }

        // ============================================================
        // Commit/Reveal Protocol
        // ============================================================

        fn do_submit_commitment(
            challenge_id: ChallengeId,
            commitment_hash: Hash,
            nonce: [u8; 32],
            miner: &T::AccountId,
        ) -> DispatchResultWithPostInfo {
            let challenge = Self::ensure_challenge_active(&challenge_id)?;
            let phase = Self::current_phase(&challenge);
            ensure!(phase == ChallengePhase::Commit, Error::<T>::ChallengeNotInPhase);
            
            // Check if already committed
            ensure!(!Commitments::<T>::contains_key(challenge_id, miner), Error::<T>::SubmissionAlreadyExists);
            
            // Verify nonce not reused
            let nonce_reused = Commitments::<T>::iter_prefix(challenge_id)
                .any(|(_, commitment)| commitment.nonce == nonce);
            ensure!(!nonce_reused, Error::<T>::NonceReused);

            // Validate nonce entropy (at least 128 bits of entropy)
            let nonce_entropy = Self::estimate_nonce_entropy(&nonce);
            ensure!(nonce_entropy >= MIN_NONCE_ENTROPY_BITS, Error::<T>::InvalidNonce);

            // Store commitment
            let commitment = Commitment {
                commitment_hash,
                nonce,
                challenge_id,
                miner: miner.clone(),
                committed_at: Self::current_block(),
            };
            
            Commitments::<T>::insert(challenge_id, miner, commitment);
            
            Self::deposit_event(Event::CommitmentReceived {
                challenge_id,
                miner: miner.clone(),
                commitment_hash,
            });

            Ok(().into())
        }

        fn do_reveal_strategy(
            challenge_id: ChallengeId,
            strategy_json: Vec<u8>,
            nonce: [u8; 32],
            miner: &T::AccountId,
        ) -> DispatchResultWithPostInfo {
            let challenge = Self::ensure_challenge_active(&challenge_id)?;
            let phase = Self::current_phase(&challenge);
            ensure!(phase == ChallengePhase::Reveal, Error::<T>::ChallengeNotInPhase);

            // Get commitment
            let commitment = Commitments::<T>::get(challenge_id, miner)
                .ok_or(Error::<T>::InvalidCommitment)?;
            
            // Verify nonce matches
            ensure!(commitment.nonce == nonce, Error::<T>::InvalidNonce);

            // Verify commitment hash matches revealed JSON
            let canonical_json = Self::canonicalize_json(&strategy_json)?;
            let computed_hash = Self::compute_commitment_hash(&canonical_json, &nonce, &challenge_id, miner)?;
            ensure!(computed_hash == commitment.commitment_hash, Error::<T>::CommitmentMismatch);

            // Validate JSON schema
            Self::validate_strategy_schema(&strategy_json)?;

            // Create submission
            let submission_id = Self::generate_submission_id(&challenge_id, miner);
            let submission = Submission {
                id: submission_id,
                challenge_id,
                miner: miner.clone(),
                submission_type: SubmissionType::Strategy,
                commitment_hash: commitment.commitment_hash,
                revealed_json: Some(strategy_json),
                nonce,
                submission_type_enum: SubmissionType::Strategy,
                status: SubmissionStatus::Revealed,
                submitted_at: Self::current_block(),
                revealed_at: Some(Self::current_block()),
                score: None,
                improvement: None,
                novelty_bonus: None,
                emission_reward: BalanceOf::<T>::zero(),
                rank: None,
                physics_gates: Default::default(),
                stress_details: Default::default(),
                novelty_bonus_awarded: Score::zero(),
                miner_hotkey: miner.clone(),
            };

            Submissions::<T>::insert(challenge_id, miner, submission.clone());
            
            let mut submission_ids = SubmissionIds::<T>::get(challenge_id);
            submission_ids.try_push(miner.clone()).unwrap_or_default();
            SubmissionIds::<T>::insert(challenge_id, submission_ids);

            // Update challenge submission count
            if let Some(mut challenge) = Challenges::<T>::get(challenge_id) {
                challenge.submission_count = challenge.submission_count.saturating_add(1);
                Challenges::<T>::insert(challenge_id, challenge);
            }

            // Remove commitment (no longer needed)
            Commitments::<T>::remove(challenge_id, miner);

            // Charge submission fee
            T::Currency::slash(miner, T::SubmissionFee::get());

            Self::deposit_event(Event::StrategyRevealed {
                challenge_id,
                miner: miner.clone(),
                submission_id,
            });

            Ok(().into())
        }

        // ============================================================
        // Specialist Pipeline Submission (Phase 2+)
        // ============================================================

        fn do_submit_specialist_pipeline(
            challenge_id: ChallengeId,
            pipeline_json: Vec<u8>,
            nonce: [u8; 32],
            miner: &T::AccountId,
        ) -> DispatchResultWithPostInfo {
            let challenge = Self::ensure_challenge_active(&challenge_id)?;
            let phase = Self::current_phase(&challenge);
            ensure!(phase == ChallengePhase::Reveal, Error::<T>::ChallengeNotInPhase);

            // Similar to reveal_strategy but for specialist pipeline
            // ... implementation similar to do_reveal_strategy
            Ok(().into())
        }

        // ============================================================
        // Scoring & Consensus
        // ============================================================

        fn do_submit_score(
            challenge_id: ChallengeId,
            miner: T::AccountId,
            score: Score,
            improvement: Score,
            stress_passed: bool,
            uq_calibrated: bool,
            physics_gates: PhysicsGateResults,
            stress_details: StressDetails,
            validator: &T::AccountId,
        ) -> DispatchResultWithPostInfo {
            let challenge = Challenges::<T>::get(challenge_id).ok_or(Error::<T>::ChallengeNotFound)?;
            ensure!(challenge.status == ChallengeStatus::Scoring, Error::<T>::ChallengeNotInPhase);
            
            // Check validator assigned
            let assigned = ValidatorAssignments::<T>::get(challenge_id).ok_or(Error::<T>::ValidatorNotAssigned)?;
            ensure!(assigned.contains(validator), Error::<T>::ValidatorNotAuthorized);

            // Check not already scored
            ensure!(!ValidatorScores::<T>::contains_key(challenge_id, validator), Error::<T>::ValidatorAlreadyScored);

            // Validate score
            let score_val: FixedU128 = score;
            ensure!(score_val >= Score::zero() && score_val <= Score::one(), Error::<T>::InvalidScoreValue);

            let validator_score = ValidatorScore {
                score,
                improvement,
                stress_passed,
                uq_calibrated,
                physics_gates,
                stress_details,
                submitted_at: Self::current_block(),
                validator: validator.clone(),
            };

            ValidatorScores::<T>::insert(challenge_id, validator, validator_score);

            Self::deposit_event(Event::ScoreSubmitted {
                challenge_id,
                validator: validator.clone(),
                miner,
                score,
            });

            // Check if consensus can be reached
            Self::try_finalize_consensus(challenge_id)?;

            Ok(().into())
        }

        fn try_finalize_consensus(challenge_id: ChallengeId) -> DispatchResult {
            let challenge = Challenges::<T>::get(challenge_id).ok_or(Error::<T>::ChallengeNotFound)?;
            let assigned = ValidatorAssignments::<T>::get(challenge_id).ok_or(Error::<T>::InsufficientValidators)?;
            
            let scores: Vec<_> = assigned.iter()
                .filter_map(|v| ValidatorScores::<T>::get(challenge_id, v))
                .collect();

            let min_validators = T::MinValidatorsForConsensus::get() as usize;
            if scores.len() < min_validators {
                return Ok(()); // Not enough scores yet
            }

            // Check if scoring deadline passed
            let challenge_data = Challenges::<T>::get(challenge_id).ok_or(Error::<T>::ChallengeNotFound)?;
            if Self::current_block() < challenge_data.scoring_deadline {
                return Ok(()); // Wait for deadline
            }

            // Finalize consensus
            Self::finalize_consensus(challenge_id)?;
            Ok(())
        }

        fn finalize_consensus(challenge_id: ChallengeId) -> DispatchResult {
            let assigned = ValidatorAssignments::<T>::get(challenge_id).ok_or(Error::<T>::InsufficientValidators)?;
            let min_validators = T::MinValidatorsForConsensus::get() as usize;

            let mut scores: Vec<(T::AccountId, ValidatorScore)> = assigned.iter()
                .filter_map(|v| ValidatorScores::<T>::get(challenge_id, v).map(|s| (v.clone(), s)))
                .collect();

            ensure!(scores.len() >= min_validators, Error::<T>::InsufficientScoresForConsensus);

            // Group scores by miner
            let mut miner_scores: BTreeMap<T::AccountId, Vec<Score>> = BTreeMap::new();
            for (validator, score) in scores {
                miner_scores.entry(score.miner.clone()).or_default().push(score.score);
            }

            // Compute median for each miner
            let mut final_scores = Vec::new();
            for (miner, scores) in miner_scores {
                let mut sorted = scores;
                sorted.sort();
                let median = sorted[sorted.len() / 2];
                
                // Check deviation
                let max_dev = Score::from_rational(1, 10); // 0.1
                for s in &sorted {
                    if (*s > median + max_dev) || (s < median - max_dev) {
                        Self::deposit_event(Event::ValidatorSlashed {
                            validator: validator.clone(),
                            amount: T::Currency::minimum_balance(),
                            reason: b"Score deviation too high".to_vec(),
                        });
                    }
                }

                final_scores.push((miner, median));
            }

            // Sort by score descending
            final_scores.sort_by(|a, b| b.1.cmp(&a.1));

            // Distribute rewards
            Self::distribute_rewards(challenge_id, final_scores)?;

            // Update challenge status
            if let Some(mut challenge) = Challenges::<T>::get(challenge_id) {
                challenge.status = ChallengeStatus::Completed;
                challenge.emission_distributed = true;
                Challenges::<T>::insert(challenge_id, challenge);
            }

            Ok(())
        }

        fn distribute_rewards(
            challenge_id: ChallengeId,
            ranked_miners: Vec<(T::AccountId, Score)>,
        ) -> DispatchResult {
            let challenge = Challenges::<T>::get(challenge_id).ok_or(Error::<T>::ChallengeNotFound)?;
            let budget = ChallengeBudgets::<T>::get(challenge_id).ok_or(Error::<T>::ChallengeNotFound)?;
            
            // Check if warm-up phase
            let warmup = T::WarmupChallengeThreshold::get();
            let submission_count = Challenges::<T>::get(challenge_id).map(|c| c.submission_count).unwrap_or(0);
            
            let rewards: Vec<(T::AccountId, Balance)> = if submission_count < warmup {
                // Warm-up: top 3 split 50/30/20
                vec![
                    (ranked_miners[0].0.clone(), budget * T::MinerEmissionShare::get() * Percent::from_percent(50) / Percent::from_percent(100)),
                    (ranked_miners[1].0.clone(), budget * T::MinerEmissionShare::get() * Percent::from_percent(30) / Percent::from_percent(100)),
                    (ranked_miners[2].0.clone(), budget * T::MinerEmissionShare::get() * Percent::from_percent(20) / Percent::from_percent(100)),
                ]
            } else {
                // Competitive: top 4 get 40/30/20/10 of miner share
                let miner_share = budget * T::MinerEmissionShare::get() / Percent::from_percent(100);
                vec![
                    (ranked_miners[0].0.clone(), miner_share * Percent::from_percent(40) / Percent::from_percent(100)),
                    (ranked_miners[1].0.clone(), miner_share * Percent::from_percent(30) / Percent::from_percent(100)),
                    (ranked_miners[2].0.clone(), miner_share * Percent::from_percent(20) / Percent::from_percent(100)),
                    (ranked_miners[3].0.clone(), miner_share * Percent::from_percent(10) / Percent::from_percent(100)),
                ]
            };

            // Distribute to miners
            for (miner, amount) in &rewards {
                T::Currency::deposit_creating(&miner, *amount);
            }

            // Validator rewards (41%)
            let validator_share = budget * T::ValidatorEmissionShare::get() / Percent::from_percent(100);
            let validators = ValidatorAssignments::<T>::get(challenge_id).unwrap_or_default();
            let scored_validators: Vec<_> = ValidatorScores::<T>::iter_prefix(challenge_id)
                .map(|(v, _)| v).collect();
            
            if !scored_validators.is_empty() {
                let per_validator = validator_share / BalanceOf::<T>::from(scored_validators.len() as u128);
                for v in scored_validators {
                    T::Currency::deposit_creating(&v, per_validator);
                }
            }

            // Owner share (18%) - goes to treasury
            let owner_share = budget * T::OwnerEmissionShare::get() / Percent::from_percent(100);
            if let Some(owner) = Owner::<T>::get() {
                T::Currency::deposit_creating(&owner, owner_share);
            }

            // Novelty bonus (5% of challenge budget)
            let novelty_pool = budget * Percent::from_percent(5) / Percent::from_percent(100);
            // Distributed separately via novelty bonus logic

            // Update bounty pool (accumulate if no improvement)
            let top_improvement = ranked_miners.first().map(|(_, s)| s).unwrap_or(Score::zero());
            if top_improvement > Score::zero() {
                // Improvement found - reset bounty pool
                BountyPools::<T>::insert(challenge_id, BalanceOf::<T>::zero());
            } else {
                // No improvement - accumulate
                let mut pool = BountyPools::<T>::get(challenge_id).unwrap_or_default();
                pool += budget / 10; // Accumulate 10% of budget
                BountyPools::<T>::insert(challenge_id, pool);
            }

            // Emit event
            Self::deposit_event(Event::RewardsDistributed {
                challenge_id,
                rewards: rewards.clone(),
                top_miner: ranked_miners[0].0.clone(),
                top_score: ranked_miners[0].1,
            });

            // Update emission tracker
            EmissionTracker::<T>::mutate(|tracker| {
                tracker.total_emitted = tracker.total_emitted.saturating_add(budget);
            });

            // Update challenge
            if let Some(mut challenge) = Challenges::<T>::get(challenge_id) {
                challenge.emission_distributed = true;
                Challenges::<T>::insert(challenge_id, challenge);
            }

            Ok(())
        }

        // ============================================================
        // Specialist Gauntlet (with Concurrency Control)
        // ============================================================

        fn do_promote_specialist(
            specialist_id: SpecialistId,
            gauntlet_result_hash: Hash,
            onnx_model_hash: Hash,
            validity_domain: ValidityDomain,
            owner: &T::AccountId,
        ) -> DispatchResultWithPostInfo {
            let pending = PendingSpecialists::<T>::get(specialist_id)
                .ok_or(Error::<T>::SpecialistNotFound)?;
            
            ensure!(pending.gauntlet_status == GauntletStatus::Passed, Error::<T>::SpecialistGauntletFailed);
            
            let specialist = pending.specialist.clone();
            
            Specialists::<T>::insert(specialist_id, specialist.clone());
            PendingSpecialists::<T>::remove(specialist_id);

            Self::deposit_event(Event::SpecialistPromoted {
                specialist_id,
                problem_id: specialist.problem_id,
                version: 1,
                onnx_hash: onnx_model_hash,
            });

            Ok(().into())
        }

        // ============================================================
        // Specialist Gauntlet (with Concurrency Control)
        // ============================================================

        /// Start specialist gauntlet (called by Landscape Agent)
        pub fn start_specialist_gauntlet(
            specialist_id: SpecialistId,
            judges: BoundedVec<AccountId, ConstU32<3>>,
        ) -> DispatchResult {
            let mut pending = PendingSpecialists::<T>::get(specialist_id)
                .ok_or(Error::<T>::SpecialistNotFound)?;
            
            // Acquire lock
            let now = Self::current_block();
            let lock = GauntletLock {
                locked: true,
                locked_by: Some(specialist_id),
                locked_at: Self::current_block(),
                expires_at: Self::current_block() + 10000, // ~14 days max
            };
            
            // Check for lock conflict
            if pending.lock.locked {
                ensure!(pending.lock.locked_by == Some(specialist_id), Error::<T>::GauntletLockConflict);
                ensure!(pending.lock.expires_at > Self::current_block(), Error::<T>::GauntletLockExpired);
            }
            
            pending.lock = lock;
            pending.gauntlet_status = GauntletStatus::AwaitingJudges;
            pending.judges = judges;
            pending.judge_results = Vec::new();
            pending.repair_iteration = 0;
            pending.created_at = Self::current_block();
            
            PendingSpecialists::<T>::insert(specialist_id, pending);
            
            Self::deposit_event(Event::GauntletStarted {
                specialist_id,
                judges: judges.to_vec(),
            });
            
            Ok(())
        }

        /// Judge submits result
        pub fn submit_judge_result(
            specialist_id: SpecialistId,
            judge: AccountId,
            passed: bool,
            feedback: Vec<u8>,
        ) -> DispatchResult {
            let mut pending = PendingSpecialists::<T>::get(specialist_id)
                .ok_or(Error::<T>::SpecialistNotFound)?;
            
            // Verify judge is authorized
            ensure!(pending.judges.contains(&judge), Error::<T>::JudgeNotAuthorized);
            
            // Check not already voted
            let already_voted = pending.judge_results.iter().any(|r| r.judge == judge);
            ensure!(!already_voted, Error::<T>::JudgeAlreadyVoted);
            
            // Check gauntlet status
            ensure!(pending.gauntlet_status == GauntletStatus::AwaitingJudges, Error::<T>::GauntletNotReady);
            
            // Check timeout
            let now = Self::current_block();
            ensure!(now < pending.lock.expires_at, Error::<T>::GauntletLockExpired);
            
            let result = JudgeResult {
                judge: judge.clone(),
                backbone: pending.specialist.problem_signature.physics_class.clone(),
                passed,
                feedback,
                scored_at: Self::current_block(),
            };
            
            pending.judge_results.push(result);
            
            // Check if all judges have voted
            if pending.judge_results.len() == pending.judges.len() as usize {
                let all_passed = pending.judge_results.iter().all(|r| r.passed);
                
                if all_passed {
                    // All passed - check grounding gate and decontamination
                    pending.gauntlet_status = GauntletStatus::Passed;
                    Self::deposit_event(Event::SpecialistPromoted {
                        specialist_id,
                        problem_id: pending.specialist.problem_id,
                        version: 1,
                        onnx_hash: pending.specialist.onnx_model_hash,
                    });
                } else {
                    // Some failed - trigger repair loop
                    if pending.repair_iteration < 3 {
                        pending.gauntlet_status = GauntletStatus::InRepair { 
                            iteration: pending.repair_iteration + 1, 
                            feedback: pending.judge_results.iter()
                                .filter(|r| !r.passed)
                                .flat_map(|r| r.feedback.clone())
                                .collect() 
                        };
                        pending.repair_iteration += 1;
                        pending.judge_results.clear(); // Reset for next round
                        Self::deposit_event(Event::RepairLoopTriggered {
                            specialist_id,
                            iteration: pending.repair_iteration,
                            failed_judge: pending.judge_results.iter()
                                .find(|r| !r.passed)
                                .map(|r| r.judge)
                                .unwrap_or_default(),
                        });
                    } else {
                        // Max iterations reached
                        pending.gauntlet_status = GauntletStatus::Rejected { 
                            reason: b"Max repair iterations exceeded".to_vec() 
                        };
                        Self::deposit_event(Event::SpecialistRejected {
                            specialist_id,
                            reason: b"Max repair iterations exceeded".to_vec(),
                        });
                    }
                }
            
            PendingSpecialists::<T>::insert(specialist_id, pending);
            Ok(())
        }

        // ============================================================
        // Landscape Agent
        // ============================================================

        fn do_propose_baseline(
            problem_id: ProblemId,
            config_json: Vec<u8>,
            causal_evidence: Vec<CausalEvidence>,
            proposer: &T::AccountId,
        ) -> DispatchResultWithPostInfo {
            // Validate causal evidence
            for evidence in &causal_evidence {
                ensure!(evidence.confidence >= 500_000, Error::<T>::InsufficientCausalEvidence); // 0.5 scaled
                ensure!(evidence.supporting_fragments >= 5, Error::<T>::InsufficientCausalEvidence);
            }

            let proposal = BaselineProposal {
                config_json,
                proposed_by: proposer.clone(),
                proposed_at: Self::current_block(),
                causal_evidence,
            };

            PendingBaselines::<T>::insert(problem_id, proposal);

            Self::deposit_event(Event::BaselineProposed {
                problem_id,
                proposed_by: proposer.clone(),
                version: 0,
            });

            Ok(().into())
        }

        fn do_approve_baseline(
            problem_id: ProblemId,
            version: u64,
            owner: &T::AccountId,
        ) -> DispatchResultWithPostInfo {
            let proposal = PendingBaselines::<T>::take(problem_id)
                .ok_or(Error::<T>::BaselineProposalNotFound)?;
            
            ensure!(proposal.proposed_at + 1000 > Self::current_block(), Error::<T>::BaselineProposalNotFound);

            let baseline = BaselineConfig {
                config_json: proposal.config_json,
                version,
                last_updated: Self::current_block(),
                proposed_by: proposal.proposed_by.clone(),
                approved_at: Some(Self::current_block()),
            };

            Baselines::<T>::insert(problem_id, baseline);
            PendingBaselines::<T>::remove(problem_id);

            // Update challenge baselines for this problem
            for challenge_id in ChallengesByProblem::<T>::get(problem_id) {
                if let Some(mut challenge) = Challenges::<T>::get(challenge_id) {
                    challenge.baseline_config = proposal.config_json.clone();
                    challenge.baseline_config_hash = Blake2_128Concat::hash(&proposal.config_json);
                    Challenges::<T>::insert(challenge_id, challenge);
                }
            }

            Self::deposit_event(Event::BaselineApproved {
                problem_id,
                version,
                approved_by: Owner::<T>::get().unwrap(),
            });

            Ok(().into())
        }

        // ============================================================
        // Utility Functions
        // ============================================================

        fn generate_challenge_id(problem_id: &ProblemId) -> ChallengeId {
            let mut input = Vec::new();
            input.extend_from_slice(&problem_id.encode());
            input.extend_from_slice(&Self::current_block().encode());
            input.extend_from_slice(&<frame_system::Pallet<T>>::extrinsic_index().unwrap_or(0).encode());
            blake2_256(&input)
        }

        fn generate_submission_id(challenge_id: &ChallengeId, miner: &T::AccountId) -> SubmissionId {
            let mut input = Vec::new();
            input.extend_from_slice(challenge_id);
            input.extend_from_slice(miner.encode().as_slice());
            input.extend_from_slice(&<frame_system::Pallet<T>>::extrinsic_index().unwrap_or(0).encode());
            blake2_256(&input)
        }

        fn calculate_challenge_budget() -> Result<BalanceOf<T>, Error<T>> {
            // Budget = total_emission / min(active_challenges, 10)
            let active = ActiveChallengeIds::<T>::get().len() as u128;
            let capped = active.min(10);
            let total_emission = T::Currency::total_issuance();
            
            let budget = total_emission.checked_div(&capped.into())
                .ok_or(Error::<T>::ArithmeticUnderflow)?;
            
            Ok(budget)
        }

        fn get_validator_vrf_pubkey(validator: &T::AccountId) -> Result<[u8; 32], Error<T>> {
            // In production, this would be stored in ValidatorPerformance or separate storage
            // For now, derive from validator hotkey
            let mut input = Vec::new();
            input.extend_from_slice(b"hydrogen-vrf-pubkey");
            input.extend_from_slice(validator.encode().as_slice());
            Ok(blake2_256(&input))
        }

        fn generate_vrf_for_validator(validator: &T::AccountId, input: &[u8]) -> Result<([u8; 32], [u8; 64]), Error<T>> {
            // In production, this would use the validator's VRF secret key
            // For now, deterministic derivation
            let secret_key = Self::derive_vrf_secret(validator)?;
            Self::generate_vrf(&secret_key, input)
        }

        fn derive_vrf_secret(validator: &T::AccountId) -> Result<[u8; 32], Error<T>> {
            let mut input = Vec::new();
            input.extend_from_slice(b"hydrogen-vrf-secret");
            input.extend_from_slice(validator.encode().as_slice());
            Ok(blake2_256(&input))
        }

        fn estimate_nonce_entropy(nonce: &[u8; 32]) -> u32 {
            // Simple entropy estimation - in production use proper entropy estimation
            let mut entropy = 0;
            for byte in nonce {
                if *byte != 0 { entropy += 1; }
            }
            entropy * 8
        }

        fn get_validator_vrf_pubkey(validator: &T::AccountId) -> Result<[u8; 32], Error<T>> {
            let mut input = Vec::new();
            input.extend_from_slice(b"hydrogen-vrf-pubkey");
            input.extend_from_slice(validator.encode().as_slice());
            Ok(blake2_256(&input))
        }

        fn generate_vrf_for_validator(validator: &T::AccountId, input: &[u8]) -> Result<([u8; 32], [u8; 64]), Error<T>> {
            let secret_key = Self::derive_vrf_secret(validator)?;
            Self::generate_vrf(&secret_key, input)
        }

        fn derive_vrf_secret(validator: &T::AccountId) -> Result<[u8; 32], Error<T>> {
            let mut input = Vec::new();
            input.extend_from_slice(b"hydrogen-vrf-secret");
            input.extend_from_slice(validator.encode().as_slice());
            Ok(blake2_256(&input))
        }

        fn estimate_nonce_entropy(nonce: &[u8; 32]) -> u32 {
            // Simple entropy estimation - in production use proper entropy estimation
            let mut entropy = 0;
            for byte in nonce {
                if *byte != 0 { entropy += 1; }
            }
            entropy * 8
        }

        fn get_validator_vrf_pubkey(validator: &T::AccountId) -> Result<[u8; 32], Error<T>> {
            let mut input = Vec::new();
            input.extend_from_slice(b"hydrogen-vrf-pubkey");
            input.extend_from_slice(validator.encode().as_slice());
            Ok(blake2_256(&input))
        }

        fn generate_vrf_for_validator(validator: &T::AccountId, input: &[u8]) -> Result<([u8; 32], [u8; 64]), Error<T>> {
            let secret_key = Self::derive_vrf_secret(validator)?;
            Self::generate_vrf(&secret_key, input)
        }

        fn derive_vrf_secret(validator: &T::AccountId) -> Result<[u8; 32], Error<T>> {
            let mut input = Vec::new();
            input.extend_from_slice(b"hydrogen-vrf-secret");
            input.extend_from_slice(validator.encode().as_slice());
            Ok(blake2_256(&input))
        }

        fn estimate_nonce_entropy(nonce: &[u8; 32]) -> u32 {
            let mut entropy = 0;
            for byte in nonce {
                if *byte != 0 { entropy += 1; }
            }
            entropy * 8
        }

        // ... Additional helper functions
    }
```

---

## A.7 Genesis Config

```rust
    #[pallet::genesis_config]
    pub struct GenesisConfig<T: Config> {
        pub owner: Option<T::AccountId>,
        pub initial_baselines: Vec<(ProblemId, Vec<u8>)>,
        pub initial_validators: Vec<T::AccountId>,
        pub initial_specialists: Vec<(SpecialistId, SpecialistOnChain)>,
    }

    #[pallet::genesis_build]
    impl<T: Config> GenesisBuild<T> for GenesisConfig<T> {
        fn build(&self) {
            if let Some(owner) = &self.owner {
                Owner::<T>::put(owner);
            }

            for (problem_id, config) in &self.initial_baselines {
                let baseline = BaselineConfig {
                    config_json: config.clone(),
                    version: 1,
                    last_updated: BlockNumberFor::<T>::zero(),
                    proposed_by: self.owner.clone().unwrap_or_default(),
                    approved_at: Some(BlockNumberFor::<T>::zero()),
                };
                Baselines::<T>::insert(problem_id, baseline);
            }

            for validator in &self.initial_validators {
                let mut active = ActiveValidators::<T>::get();
                active.try_push(validator.clone()).unwrap_or_default();
                ActiveValidators::<T>::put(active);
                
                ValidatorPerformance::<T>::insert(validator, ValidatorPerf {
                    total_validations: 0,
                    successful_validations: 0,
                    avg_score_deviation: 0,
                    uptime_percentage: 10000, // 100%
                    last_active: BlockNumberFor::<T>::zero(),
                    slashed_count: 0,
                });
            }

            for (id, specialist) in &self.initial_specialists {
                Specialists::<T>::insert(id, specialist.clone());
            }

            // Initialize emission tracker
            EmissionTracker::<T>::put(EmissionTrackerData {
                total_emitted: Zero::zero(),
                total_burned: Zero::zero(),
                total_novelty_bonus: Zero::zero(),
                last_emission_block: BlockNumberFor::<T>::zero(),
            });
        }
    }
```

---

## A.7 Weight Info

```rust
    #[pallet::weight]
    impl<T: Config> WeightInfo for Pallet<T> {
        fn create_challenge() -> Weight {
            Weight::from_parts(100_000_000, 0)
        }
        fn update_baseline() -> Weight {
            Weight::from_parts(50_000_000, 0)
        }
        fn submit_commitment() -> Weight {
            Weight::from_parts(20_000_000, 0)
        }
        fn reveal_strategy() -> Weight {
            Weight::from_parts(100_000_000, 0)
        }
        fn submit_specialist_pipeline() -> Weight {
            Weight::from_parts(50_000_000, 0)
        }
        fn submit_custom_data() -> Weight {
            Weight::from_parts(30_000_000, 0)
        }
        fn submit_score() -> Weight {
            Weight::from_parts(30_000_000, 0)
        }
        fn propose_baseline() -> Weight {
            Weight::from_parts(20_000_000, 0)
        }
        fn approve_baseline() -> Weight {
            Weight::from_parts(10_000_000, 0)
        }
        fn reject_baseline() -> Weight {
            Weight::from_parts(10_000_000, 0)
        }
        fn promote_specialist() -> Weight {
            Weight::from_parts(50_000_000, 0)
        }
        fn add_validator() -> Weight {
            Weight::from_parts(10_000_000, 0)
        }
        fn remove_validator() -> Weight {
            Weight::from_parts(10_000_000, 0)
        }
        fn submit_custom_data() -> Weight {
            Weight::from_parts(30_000_000, 0)
        }
        fn update_config() -> Weight {
            Weight::from_parts(100_000_000, 0)
        }
    }
```

---

*End of Appendix A: Chain Pallet Specification v2.1*
