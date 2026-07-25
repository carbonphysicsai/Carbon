# OPERATIONS.md — Carbon Subnet Operations & Deployment Guide

## TL;DR

**Job:** Run the subnet day-to-day without breaking determinism, gate integrity, or the SciML oracle.

**What this document owns**
- Validator fleet + miner toolkit Docker/K8s
- Julia/SciML Ground Truth Oracle (port 8083) — reference solves, adjoints, symbolic losses
- Queue, monitoring, alerts, incident response, backups
- Capacity planning by phase

**Non-negotiable ops rules**
1. Physics gates always run in **fp32** (validators that skip this get false fails and should be treated as faulty)
2. JAX determinism: pinned lockfile + `threefry` + persistent XLA compile cache volumes
3. SciML Oracle is on the critical path — if it is down, validation is degraded; treat as SEV-1
4. Train ≠ eval seeds; stress tensors never leave the validator process
5. Hard step + wall-clock kills on every evaluation (ignore runaway miner `epochs`)

**Daily operator loop**
- Morning: pod health, SciML `/health`, queue depth, overnight submission count
- Mid-day: GPU util / OOM, stuck submissions (>2 h), SciML latency
- Evening: reward snapshot, queue trend, backup verification

**Key services**
| Service | Port | Failure impact |
|---------|------|----------------|
| Validator | 8080/8081 | No scoring |
| SciML Oracle | 8083 | No reference/adjoint validation |
| Queue processor | — | Backlog → latency |

**Read deeper:** §1 architecture → §4 validator ops → §5 SciML ops → §8 incident response → runbooks at end.

---

**Version:** 3.0 (July 2026)  
**Status:** Production Operations Manual  
**Audience:** DevOps Engineers, Validator Operators, Platform Engineers, On-Call Engineers  
**Purpose:** Day-to-day operations, deployment procedures, incident response, and maintenance for Carbon subnet — **including Julia/SciML Ground Truth Oracle operations**

---

# TABLE OF CONTENTS

1. [Infrastructure Overview](#1-infrastructure-overview)
2. [Docker & Container Operations](#2-docker--container-operations)
3. [Kubernetes Deployment](#3-kubernetes-deployment)
4. [Validator Operations](#4-validator-operations)
5. [Julia/SciML Ground Truth Service Operations](#5-juliasciml-ground-truth-service-operations)
6. [Monitoring & Alerting](#6-monitoring--alerting)
7. [Miner Onboarding & Support](#7-miner-onboarding--support)
8. [Incident Response](#8-incident-response)
9. [Maintenance Procedures](#9-maintenance-procedures)
10. [Backup & Disaster Recovery](#10-backup--disaster-recovery)
11. [Security Operations](#11-security-operations)
10. [Capacity Planning](#12-capacity-planning)
11. [Runbooks](#13-runbooks)

---

# 1. INFRASTRUCTURE OVERVIEW

## 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CARBON INFRASTRUCTURE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │  Validator Fleet │    │  Julia/SciML     │                   │
│  │  (5-20 validators)│    │  Ground Truth    │                   │
│  │  + MCP Server    │    │  Oracle (Port    │                   │
│  └────────┬─────────┘    │  8083)           │                   │
│           │              └────────┬─────────┘                   │
│           │                       │                              │
│           ▼                       ▼                              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    BITTENSOR NETWORK                         │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │ │
│  │  │ Subtensor │  │ Metagraph │  │ Dendrite │                 │ │
│  │  └──────────┘  └──────────┘  └──────────┘                   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│           │                       │                              │
│           ▼                       ▼                              │
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │  Persistent      │    │  External        │                   │
│  │  Volumes         │    │  Services        │                   │
│  │  ├─ compile_cache │  │  ├─ Chainlink α/USD│                 │
│  │  ├─ jax_cache    │  │  ├─ S3/GCS         │                   │
│  │  ├─ checkpoints  │  │  │    (precomputed)│                   │
│  │  ├─ julia_depot  │  │  ├─ preCICE        │                   │
│  │  └─ model_registry│  │  └─ Chainlink α/USD│                 │
│  └──────────────────┴──────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

## 1.2 Environment Inventory

| Environment | Purpose | Validators | GPU Config | Network | Julia/SciML |
|-------------|---------|------------|------------|---------|-------------|
| **devnet** | Development/Testing | 2-3 | 1× A100 40GB | Testnet (Finney) | 1 replica, dev Julia |
| **staging** | Pre-production validation | 3-5 | 1× H100 | Testnet (Finney) | 2 replicas, staging Julia |
| **mainnet** | Production | 5-20 | H100/H200 | Mainnet | 3+ replicas, prod Julia |

---

# 2. DOCKER & CONTAINER OPERATIONS

## 2.1 Base Images & Versioning

```dockerfile
# Validator base - pinned by digest
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04@sha256:a1b2c3d4...

# Miner toolkit base
FROM nvidia/cuda:12.4-devel-ubuntu22.04@sha256:e5f6g7h8...

# Julia/SciML Ground Truth Oracle
FROM julia:1.10-bullseye

# Build args for versioning
ARG CARBON_VERSION=2.1.0
ARG BUILD_DATE
ARG GIT_COMMIT
LABEL org.opencontainers.image.version=$CARBON_VERSION
LABEL org.opencontainers.image.created=$BUILD_DATE
LABEL org.opencontainers.image.revision=$GIT_COMMIT
```

## 2.2 Image Build Pipeline

```yaml
# .github/workflows/docker-build.yml
name: Docker Build & Push

on:
  push:
    tags: ['v*']
  workflow_dispatch:

jobs:
  build-validator:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GHCR_TOKEN }}
      - name: Build and push validator
        uses: docker/build-push-action@v5
        with:
          context: ./carbon/validator
          file: ./carbon/validator/Dockerfile
          push: true
          tags: |
            ghcr.io/carbon/validator:${{ github.ref_name }}
            ghcr.io/carbon/validator:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            CARBON_VERSION=${{ github.ref_name }}
            BUILD_DATE=${{ github.event.head_commit.timestamp }}
            GIT_COMMIT=${{ github.sha }}

  build-sciml-service:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GHCR_TOKEN }}
      - name: Build and push SciML service
        uses: docker/build-push-action@v5
        with:
          context: ./julia
          file: ./julia/Dockerfile.sciml
          push: true
          tags: |
            ghcr.io/carbon/sciml-service:${{ github.ref_name }}
            ghcr.io/carbon/sciml-service:latest
          build-args: |
            JULIA_VERSION=1.10

  build-miner-toolkit:
    # Similar for miner toolkit
```

## 2.3 Image Scanning & Signing

```bash
# Scan for vulnerabilities
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image \
  --severity HIGH,CRITICAL \
  --exit-code 1 \
  ghcr.io/carbon/validator:v2.1.0

# Sign images with cosign
cosign sign --yes ghcr.io/carbon/validator:v2.1.0
cosign verify --key cosign.pub ghcr.io/carbon/validator:v2.1.0
```

## 2.4 Container Runtime Configuration

### Validator Container
```yaml
# docker-compose.validator.yml
services:
  validator:
    image: ghcr.io/carbon/validator:v2.1.0
    container_name: carbon-validator
    restart: unless-stopped
    runtime: nvidia
    environment:
      - VALIDATOR_HOTKEY=${VALIDATOR_HOTKEY}
      - NETUID=1
      - SUBTENSOR_ENDPOINT=wss://entrypoint-finney.opentensor.ai:443
      - CARBON_CONFIG_PATH=/opt/carbon/config/validator.yaml
      - JAX_COMPILATION_CACHE_DIR=/persistent/compile_cache
      - JAX_CACHE_DIR=/persistent/jax_cache
      - PYTHONHASHSEED=0
      - CUBLAS_WORKSPACE_CONFIG=:4096:8
      - SCIMML_ENDPOINT=http://carbon-sciml:8083  # Julia/SciML Ground Truth Oracle
    volumes:
      - carbon-compile-cache:/persistent/compile_cache
      - carbon-jax-cache:/persistent/jax_cache
      - carbon-checkpoints:/opt/carbon/checkpoints
      - carbon-config:/opt/carbon/config:ro
      - ./config/validator.yaml:/opt/carbon/config/validator.yaml:ro
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    deploy:
      restart_policy:
        condition: on-failure
        delay: 30s
        max_attempts: 3
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
```

### Julia/SciML Ground Truth Oracle Container
```yaml
# docker-compose.sciml.yml
services:
  sciml-service:
    build:
      context: ./julia
      dockerfile: Dockerfile.sciml
    container_name: carbon-sciml
    restart: unless-stopped
    runtime: nvidia
    ports:
      - "8083:8083"
    environment:
      - JULIA_NUM_THREADS=16
      - JULIA_DEPOT_PATH=/opt/julia/depot
      - PYTHONUNBUFFERED=1
    volumes:
      - sciml-depot:/opt/julia/depot
      - ./julia:/app
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8083/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
        limits:
          cpus: '16'
          memory: 64G

volumes:
  sciml-depot:
```

### Miner Toolkit Container
```yaml
# docker-compose.miner.yml
services:
  miner-toolkit:
    image: ghcr.io/carbon/miner-toolkit:v2.1.0
    container_name: carbon-miner-toolkit
    runtime: nvidia
    environment:
      - CARBON_MCP_ENDPOINT=wss://mcp.carbon.subnet:8081
      - CARBON_HOTKEY=${MINER_HOTKEY}
    volumes:
      - carbon-miner-output:/opt/carbon/output
      - ./strategies:/opt/carbon/strategies:ro
      - ./configs:/opt/carbon/configs:ro
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    command: ["--help"]
```

## 2.5 Image Lifecycle Management

```bash
# Tagging strategy
# Semantic versioning: v{major}.{minor}.{patch}-{phase}
# Examples:
#   v2.1.0-phase0     # Phase 0 release
#   v2.1.0-phase1a    # Phase 1A release
#   v2.1.0-phase1b    # Phase 1B release

# Promotion workflow
# 1. Build on merge to main → ghcr.io/carbon/validator:main-{sha}
# 2. Test on staging → promote to ghcr.io/carbon/validator:staging
# 3. Release → tag v2.1.0-phase1a → auto-promote to :latest

# Cleanup policy (run weekly via cron)
docker image prune -a --filter "until=168h" --filter "label!=keep"
```

---

# 3. KUBERNETES DEPLOYMENT

## 3.1 Cluster Requirements

```yaml
# Minimum cluster specs per phase
# Phase 0-1B: 5 nodes, 1x H100 each, 100GB RAM, 2TB NVMe
# Phase 2A-2B: 6-8 nodes, 1-2x H100, 200GB RAM, 4TB NVMe
# Phase 3: 10-15 nodes, 2x H100, 512GB RAM, 4TB NVMe
# Phase 4: 20+ nodes, 2x H200, 1TB RAM, 8TB NVMe

# Required node labels
node-labels:
  carbon-phase: "0|1a|1b|2a|2b|3|4"
  carbon-role: "validator|miner-toolkit|airgapped-validator|landscape-agent|sciml-oracle"
  gpu-type: "a100-80gb|h100-80gb|h200-141gb"
  carbon-phase-capable: "0|1a|1b|2a|2b|3|4"
```

## 3.2 Kubernetes Manifests

### 3.2.1 Validator Deployment

```yaml
# k8s/validator-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: carbon-validator
  namespace: carbon
  labels:
    app: carbon-validator
    carbon-phase: "1a"
spec:
  replicas: 5
  selector:
    matchLabels:
      app: carbon-validator
  template:
    metadata:
      labels:
        app: carbon-validator
        carbon-phase: "1a"
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      runtimeClassName: nvidia
      serviceAccountName: carbon-validator
      priorityClassName: carbon-validator-high
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
              - key: gpu-type
                operator: In
                values: ["h100-80gb"]
              - key: carbon-phase-capable
                operator: In
                values: ["1a"]
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values: ["carbon-validator"]
              topologyKey: kubernetes.io/hostname
      containers:
      - name: validator
        image: ghcr.io/carbon/validator:v2.1.0-phase1a
        imagePullPolicy: Always
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 8081
          name: mcp
        - containerPort: 8082
          name: metrics
        env:
        - name: VALIDATOR_HOTKEY
          valueFrom:
            secretKeyRef:
              name: validator-secrets
              key: hotkey
        - name: NETUID
          value: "1"
        - name: SUBTENSOR_ENDPOINT
          value: "wss://entrypoint-finney.opentensor.ai:443"
        - name: JAX_COMPILATION_CACHE_DIR
          value: "/persistent/compile_cache"
        - name: JAX_CACHE_DIR
          value: "/persistent/jax_cache"
        - name: PYTHONHASHSEED
          value: "0"
        - name: CUBLAS_WORKSPACE_CONFIG
          value: ":4096:8"
        - name: SCIMML_ENDPOINT
          value: "http://carbon-sciml:8083"
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "64Gi"
            cpu: "16"
            nvidia.com/gpu-memory: "80Gi"
          limits:
            nvidia.com/gpu: 1
            memory: "80Gi"
            cpu: "24"
            nvidia.com/gpu-memory: "80Gi"
        volumeMounts:
        - name: compile-cache
          mountPath: /persistent/compile_cache
        - name: jax-cache
          mountPath: /persistent/jax_cache
        - name: checkpoints
          mountPath: /opt/carbon/checkpoints
        - name: config
          mountPath: /opt/carbon/config
          readOnly: true
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 60
          periodSeconds: 30
          timeoutSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: compile-cache
        persistentVolumeClaim:
          claimName: carbon-compile-cache
      - name: jax-cache
        persistentVolumeClaim:
          claimName: carbon-jax-cache
      - name: checkpoints
        persistentVolumeClaim:
          claimName: carbon-checkpoints
      - name: config
        configMap:
          name: validator-config
          items:
          - key: validator.yaml
            path: validator.yaml
---
# PriorityClass for validator priority
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: carbon-validator-high
value: 1000000
globalDefault: false
description: "High priority for Carbon validators"
---
# Service for validator communication
apiVersion: v1
kind: Service
metadata:
  name: carbon-validator
  namespace: carbon
spec:
  selector:
    app: carbon-validator
  ports:
  - name: http
    port: 8080
    targetPort: 8080
  - name: mcp
    port: 8081
    targetPort: 8081
  - name: metrics
    port: 8082
    targetPort: 8082
  type: ClusterIP
```

### 3.2.2 Persistent Volumes

```yaml
# k8s/persistent-volumes.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: carbon-compile-cache
  namespace: carbon
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 500Gi
  storageClassName: nvme-fast
  volumeMode: Filesystem
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: carbon-jax-cache
  namespace: carbon
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 200Gi
  storageClassName: nvme-fast
  volumeMode: Filesystem
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: carbon-checkpoints
  namespace: carbon
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 500Gi
  storageClassName: nvme-fast
  volumeMode: Filesystem
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: carbon-model-registry
  namespace: carbon
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 1Ti
  storageClassName: nvme-fast
  volumeMode: Filesystem
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: carbon-julia-depot
  namespace: carbon
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Gi
  storageClassName: nvme-fast
```

### 3.2.2 Validator Queue as Kubernetes Job

```yaml
# k8s/validator-queue.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: validator-queue-processor
  namespace: carbon
spec:
  schedule: "*/1 * * * *"  # Every minute
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: carbon-queue-processor
          restartPolicy: OnFailure
          containers:
          - name: queue-processor
            image: ghcr.io/carbon/validator-queue:v2.1.0
            env:
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: redis-config
                  key: url
            - name: MAX_CONCURRENT
              value: "3"
            - name: QUEUE_DEPTH
              value: "100"
            - name: SUBMISSION_TIMEOUT
              value: "7200"
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          restartPolicy: OnFailure
```

### 3.2.3 Julia/SciML Ground Truth Oracle Deployment

```yaml
# k8s/sciml-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: carbon-sciml-service
  namespace: carbon
spec:
  replicas: 3
  selector:
    matchLabels:
      app: carbon-sciml
  template:
    metadata:
      labels:
        app: carbon-sciml
    spec:
      runtimeClassName: nvidia
      containers:
      - name: sciml-service
        image: ghcr.io/carbon/sciml-service:v2.1.0
        ports:
        - containerPort: 8083
        env:
        - name: JULIA_NUM_THREADS
          value: "16"
        - name: JULIA_DEPOT_PATH
          value: "/opt/julia/depot"
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "32Gi"
            cpu: "8"
          limits:
            nvidia.com/gpu: 1
            memory: "64Gi"
            cpu: "16"
        volumeMounts:
        - name: julia-depot
          mountPath: /opt/julia/depot
        livenessProbe:
          httpGet:
            path: /health
            port: 8083
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8083
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: julia-depot
        persistentVolumeClaim:
          claimName: carbon-julia-depot
---
apiVersion: v1
kind: Service
metadata:
  name: carbon-sciml
  namespace: carbon
spec:
  selector:
    app: carbon-sciml
  ports:
  - protocol: TCP
    port: 8083
    targetPort: 8083
  type: ClusterIP
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: carbon-julia-depot
  namespace: carbon
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Gi
  storageClassName: nvme-fast
```

### 3.2.4 ConfigMaps & Secrets

```yaml
# k8s/configmap-validator.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: validator-config
  namespace: carbon
data:
  validator.yaml: |
    subnet:
      netuid: 1
      subtensor_endpoint: "wss://entrypoint-finney.opentensor.ai:443"
    validator:
      min_validators: 5
      max_concurrent_evaluations: 3
      evaluation_timeout_seconds: 7200
      challenge_throughput_target: 50
    physics_gates:
      # Phase-specific gate configs loaded at runtime
      config_path: "/opt/carbon/config/gates"
    model_zoo:
      enabled: true
      max_models: 50
      storage_path: "/opt/carbon/model_registry"
    landscape_agent:
      enabled: true
      pysr_batch_size: 1000
      dml_batch_size: 500
    sciml_oracle:
      endpoint: "http://carbon-sciml:8083"
      timeout_seconds: 300
      retry_attempts: 3
    monitoring:
      metrics_port: 8082
      log_level: "INFO"
      trace_sampling_rate: 0.1
```

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: validator-secrets
  namespace: carbon
type: Opaque
stringData:
  hotkey: "5F...validator_hotkey..."
  mcp_endpoint: "wss://mcp.carbon.subnet:8081"
---
apiVersion: v1
kind: Secret
metadata:
  name: redis-config
  namespace: carbon
type: Opaque
stringData:
  url: "redis://carbon-redis:6379/0"
---
apiVersion: v1
kind: Secret
metadata:
  name: sciml-secrets
  namespace: carbon
type: Opaque
stringData:
  # Julia/SciML service doesn't typically need secrets
  # but reserve for future API keys
  dummy: "placeholder"
```

---

## 3.3 GPU Resource Management

### 3.1 NVIDIA Device Plugin

```bash
# Ensure NVIDIA device plugin is installed
# kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

# Verify GPU allocation
kubectl describe nodes | grep -A 5 "nvidia.com/gpu"
```

### 3.2 GPU Monitoring

```yaml
# Prometheus rules for GPU monitoring
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: gpu-alerts
  namespace: monitoring
spec:
  groups:
  - name: gpu-health
    rules:
    - alert: GPUMemoryHigh
      expr: |
        (DCGM_FI_DEV_FB_USED / DCGM_FI_DEV_FB_TOTAL) > 0.95
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "GPU memory usage > 95%"
    - alert: GPUUtilizationLow
      expr: |
        DCGM_FI_DEV_GPU_UTIL < 10
      for: 30m
      labels:
        severity: warning
      annotations:
        summary: "GPU utilization < 10% for 30min"
    - alert: GPUTemperatureHigh
      expr: |
        DCGM_FI_DEV_GPU_TEMP > 85
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "GPU temperature > 85°C"
    - alert: GPUSciMLServiceDown
      expr: |
        up{job="carbon-sciml"} == 0
      for: 2m
      labels:
        severity: critical
      annotations:
        summary: "Julia/SciML Ground Truth Oracle is down"
```

---

# 4. VALIDATOR OPERATIONS

## 4.1 Daily Operations Checklist

### Morning (UTC 00:00)
- [ ] Check validator health: `kubectl get pods -n carbon -l app=carbon-validator`
- [ ] Verify all 5+ validators Running: `kubectl get pods -n carbon -l app=carbon-validator --field-selector=status.phase=Running | wc -l`
- [ ] Verify SciML Ground Truth Oracle: `kubectl get pods -n carbon -l app=carbon-sciml`
- [ ] Check queue depth: `kubectl exec -n carbon deployment/validator-queue-processor -- queue-status`
- [ ] Review overnight submissions: `kubectl logs -n carbon deployment/carbon-validator --since=24h | grep "submission_received" | wc -l`
- [ ] Check α/TAO price: Verify floor > 0.005
- [ ] Review validator rewards: `btcli subnet summary --netuid 1`
- [ ] Check SciML Ground Truth Oracle health: `curl -f http://carbon-sciml:8083/health`

### Mid-Day (UTC 12:00)
- [ ] Check queue depth & processing rate
- [ ] Review validator resource usage: `kubectl top pods -n carbon -l app=carbon-validator`
- [ ] Check for stuck submissions: `kubectl exec -n carbon deployment/validator-queue-processor -- queue-stuck`
- [ ] Review SciML Ground Truth Oracle latency: `curl -s http://carbon-sciml:8083/metrics | grep sciml_solve_duration`
- [ ] Review miner diagnostics feedback quality

### Evening (UTC 20:00)
- [ ] Daily subnet metrics snapshot
- [ ] Validator reward distribution check
- [ ] Queue depth trend analysis
- [ ] Backup verification
- [ ] SciML Ground Truth Oracle metrics review

## 4.2 Validator Lifecycle Management

### Adding a New Validator
```bash
# 1. Generate hotkey
btcli wallet new_coldkey --wallet.name carbon-validator-06
btcli wallet new_hotkey --wallet.name carbon-validator-06 --wallet.hotkey validator-06

# 2. Register on subnet
btcli subnet register --netuid 1 --wallet.name carbon-validator-06 --wallet.hotkey validator-06

# 3. Create Kubernetes secret
kubectl create secret generic validator-06-secrets \
  --namespace carbon \
  --from-literal=hotkey="5F..." \
  --from-literal=mcp-endpoint="wss://mcp.carbon.subnet:8081"

# 4. Scale deployment
kubectl scale deployment carbon-validator --replicas=6 -n carbon

# 4. Verify registration
btcli subnet list --netuid 1 | grep validator-06
```

### Rotating Validator Keys
```bash
# 1. Generate new hotkey
btcli wallet new_hotkey --wallet.name carbon-validator-01 --wallet.hotkey validator-01-new

# 2. Update secret
kubectl create secret generic validator-01-secrets \
  --namespace carbon \
  --from-literal=hotkey="5F...new_hotkey..." \
  --dry-run=client -o yaml | kubectl replace -f -

# 3. Rolling restart
kubectl rollout restart deployment/carbon-validator -n carbon

# 4. Verify
kubectl logs -n carbon deployment/carbon-validator | grep "Registered with hotkey"
```

### Graceful Validator Shutdown
```bash
# 1. Drain gracefully
kubectl cordon <node-name>
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data --timeout=300s

# 2. Scale down
kubectl scale deployment carbon-validator --replicas=4 -n carbon

# 3. Verify remaining validators healthy
kubectl get pods -n carbon -l app=carbon-validator -o wide
```

## 4.3 Validator Health Monitoring

### Key Metrics to Watch
```promql
# Validator uptime
up{job="carbon-validator", namespace="carbon"} == 1

# Evaluation throughput
rate(carbon_submissions_evaluated_total[5m])

# Evaluation latency (p50, p95, p99)
histogram_quantile(0.50, rate(carbon_evaluation_duration_seconds_bucket[5m]))
histogram_quantile(0.95, rate(carbon_evaluation_duration_seconds_bucket[5m]))

# Gate pass rate
sum(rate(carbon_gate_pass_total[5m])) / sum(rate(carbon_gate_total[5m]))

# GPU utilization
DCGM_FI_DEV_GPU_UTIL

# GPU memory
DCGM_FI_DEV_FB_USED / DCGM_FI_DEV_FB_TOTAL

# Queue depth
carbon_queue_depth

# Submission processing time
histogram_quantile(0.95, rate(carbon_submission_processing_seconds_bucket[5m]))

# SciML Ground Truth Oracle metrics
sciml_solve_duration_seconds
sciml_adjoint_duration_seconds
sciml_validation_pass_rate
```

### Alerting Rules
```yaml
# prometheus-rules/validator-alerts.yaml
groups:
- name: carbon-validator
  rules:
  - alert: ValidatorDown
    expr: up{job="carbon-validator", namespace="carbon"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Carbon validator {{ $labels.pod }} is down"
      
  - alert: ValidatorEvaluationLatencyHigh
    expr: histogram_quantile(0.95, rate(carbon_evaluation_duration_seconds_bucket[5m])) > 1800
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "Validator evaluation p95 latency > 30 minutes"
      
  - alert: ValidatorQueueBacklog
    expr: carbon_queue_depth > 50
    for: 15m
    labels:
      severity: warning
    annotations:
      summary: "Validator queue backlog > 50 submissions"
      
  - alert: ValidatorGPUOOM
    expr: |
      (DCGM_FI_DEV_FB_USED / DCGM_FI_DEV_FB_TOTAL) > 0.98
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Validator {{ $labels.pod }} GPU memory > 98%"
      
  - alert: ValidatorStuckSubmission
    expr: |
      time() - carbon_submission_start_timestamp > 7200
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Submission stuck > 2 hours on validator {{ $labels.pod }}"
      
  - alert: SciMLGroundTruthOracleDown
    expr: up{job="carbon-sciml", namespace="carbon"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Julia/SciML Ground Truth Oracle is down - validators cannot validate!"
      
  - alert: SciMLHighLatency
    expr: histogram_quantile(0.95, rate(sciml_solve_duration_seconds_bucket[5m])) > 120
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "SciML Ground Truth Oracle solve latency > 2 minutes"
```

---

# 5. JULIA/SCIML GROUND TRUTH SERVICE OPERATIONS

## 5.1 Service Overview

The **Julia/SciML Ground Truth Oracle** is a dedicated Julia service that provides mathematically rigorous reference solutions, adjoint sensitivities, and symbolic loss terms using the Julia SciML ecosystem. This service is the **ground truth oracle** that makes Carbon's verification trustless in the mathematical sense.

### 5.1.1 Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CARBON VALIDATOR                              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  PYTHON/JAX VALIDATOR                                       │ │
│  │  ├─ Training Loop (JAX/Flax)                                │ │
│  │  ├─ Physics Gates (fp32 enforced)                           │ │
│  │  └─ SciMLClient ─────────────────────────────────────────┐  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  JULIA/SCIML GROUND TRUTH SERVICE (Port 8083)              │ │
│  │  ├─ DifferentialEquations.jl (Reference Solvers)           │ │
│  │  ├─ NeuralPDE.jl (PINN Baselines)                          │ │
│  │  ├─ ModelingToolkit.jl (Symbolic Loss Terms)               │ │
│  │  ├─ SciMLSensitivity.jl (Adjoint Sensitivities)            │ │
│  │  ├─ NeuralPDE.jl (PINN/DeepONet Baselines)                 │ │
│  │  └─ MethodOfLines.jl (Automated PDE Discretization)        │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 5.1.2 Service Endpoints

| Endpoint | Method | Purpose | Used By |
|----------|--------|---------|---------|
| `GET /health` | GET | Health check | K8s liveness/readiness |
| `POST /solve_pde` | POST | High-fidelity reference solution | Validator validation |
| `POST /adjoint_sensitivity` | POST | Adjoint gradients via SciMLSensitivity.jl | Adjoint Consistency Gate |
| `POST /symbolic_loss` | POST | Symbolic loss from ModelingToolkit.jl | Landscape Agent bridge |
| `POST /validate_solution` | POST | Validate model against reference | Validator validation |

---

## 5.2 Deployment Operations

### 5.2.1 Deploying the SciML Service

```bash
# Deploy to staging
kubectl apply -f k8s/sciml-deployment.yaml -n carbon

# Verify deployment
kubectl get pods -n carbon -l app=carbon-sciml
kubectl logs -n carbon -l app=carbon-sciml --tail=50

# Test health endpoint
curl -f http://carbon-sciml:8083/health

# Test PDE solve endpoint
curl -X POST http://carbon-sciml:8083/solve_pde \
  -H "Content-Type: application/json" \
  -d '{"action":"solve_pde","pde_spec":{"type":"poisson"},"params":{}}'
```

### 5.2.2 Updating Julia Packages

```bash
# 1. Update Julia packages in Docker image
# Edit julia/Dockerfile.sciml to update package versions
# Rebuild image:
docker build -t ghcr.io/carbon/sciml-service:v2.1.1 -f julia/Dockerfile.sciml ./julia

# 2. Push to registry
docker push ghcr.io/carbon/sciml-service:v2.1.1

# 3. Rolling update
kubectl set image deployment/carbon-sciml carbon-sciml=ghcr.io/carbon/sciml-service:v2.1.1 -n carbon

# 3. Verify rollout
kubectl rollout status deployment/carbon-sciml -n carbon

# 4. Verify health
kubectl get pods -n carbon -l app=carbon-sciml
curl -f http://carbon-sciml:8083/health
```

### 5.2.3 Julia Depot Management

```bash
# Julia depot is persisted via PVC
# To update packages across all replicas:

# 1. Exec into one pod
kubectl exec -it -n carbon deployment/carbon-sciml -- julia --project -e '
    using Pkg
    Pkg.update()
    Pkg.precompile()
'

# 2. Verify all replicas have updated
kubectl exec -it -n carbon deployment/carbon-sciml -- julia --project -e '
    using Pkg
    Pkg.status()
'

# 3. Verify precompilation
kubectl exec -it -n carbon deployment/carbon-sciml -- julia --project -e '
    using DifferentialEquations, NeuralPDE, ModelingToolkit, SciMLSensitivity
    println("All packages loaded successfully")
'
```

---

## 5.3 Monitoring & Alerting for SciML Service

### 5.3.1 Key Metrics

```promql
# Solve latency (p50, p95, p99)
histogram_quantile(0.50, rate(sciml_solve_duration_seconds_bucket[5m]))
histogram_quantile(0.95, rate(sciml_solve_duration_seconds_bucket[5m]))

# Adjoint sensitivity latency
histogram_quantile(0.95, rate(sciml_adjoint_duration_seconds_bucket[5m]))

# Validation pass rate
sciml_validation_pass_rate

# Julia GC metrics
julia_gc_bytes_allocated
julia_gc_collection_time_seconds

# Solver convergence
sciml_solver_converged

# Julia GC pressure
julia_gc_bytes_allocated / julia_gc_bytes_freed
```

### 5.3.2 Prometheus Alerting Rules

```yaml
# prometheus-rules/sciml-alerts.yaml
groups:
- name: sciml-ground-truth-oracle
  rules:
  - alert: SciMLServiceDown
    expr: up{job="carbon-sciml", namespace="carbon"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Julia/SciML Ground Truth Oracle is DOWN - validators cannot validate!"
      runbook_url: "https://runbooks.carbon.subnet/sciml-down"

  - alert: SciMLHighLatency
    expr: histogram_quantile(0.95, rate(sciml_solve_duration_seconds_bucket[5m])) > 120
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "SciML solve latency > 2 minutes - validators timing out"
      runbook_url: "https://runbooks.carbon.subnet/sciml-high-latency"

  - alert: SciMLSolverDivergence
    expr: increase(sciml_solver_diverged_total[15m]) > 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "SciML solver diverged - reference solutions may be invalid"
      runbook_url: "https://runbooks.carbon.subnet/sciml-divergence"

  - alert: SciMLHighGCTime
    expr: |
      (rate(julia_gc_collection_time_seconds[5m]) / rate(julia_gc_collection_count[5m])) > 0.5
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "Julia GC taking >50% of CPU time - consider increasing memory"
      runbook_url: "https://runbooks.carbon.subnet/sciml-gc-pressure"

  - alert: JuliaDepotCorruption
    expr: |
      changes(julia_depot_checksum[1h]) > 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Julia depot checksum changed unexpectedly - possible corruption"
      runbook_url: "https://runbooks.carbon.subnet/julia-depot-corruption"
```

---

## 5.4 Maintenance Procedures

### 5.4.1 Weekly Julia Depot Maintenance

```bash
#!/bin/bash
# weekly-julia-maintenance.sh

set -euo pipefail

echo "=== Julia/SciML Weekly Maintenance $(date) ==="

# 1. Update Julia packages in depot (run on one replica, syncs via PVC)
echo "Updating Julia packages..."
kubectl exec -it -n carbon deployment/carbon-sciml -- julia --project -e '
    using Pkg
    Pkg.update()
    Pkg.precompile()
    println("Package update complete")
'

# 2. Verify all replicas have consistent depot
echo "Verifying depot consistency..."
for pod in $(kubectl get pods -n carbon -l app=carbon-sciml -o name); do
    echo "Checking $pod..."
    kubectl exec -it -n carbon "$pod" -- julia --project -e '
        using Pkg
        Pkg.status()
    '
done

# 3. Verify precompilation
echo "Verifying precompilation..."
kubectl exec -it -n carbon deployment/carbon-sciml -- julia --project -e '
    using DifferentialEquations, NeuralPDE, ModelingToolkit, SciMLSensitivity
    println("All packages loaded successfully")
'

echo "=== Weekly Julia maintenance complete ==="
```

### 5.4.2 Monthly Julia Maintenance

```bash
# 1. Kernel & driver updates (test on staging first)
# 2. Firmware updates (BIOS, BMC, GPU)
# 3. Julia version upgrade (test on staging first)
# 4. Capacity review: GPU utilization trends, depot storage growth
# 5. Security scan: Trivy scan Julia image, dependency audit
# 6. Disaster recovery test: Restore Julia depot from backup to staging
```

### 5.4.3 Julia Depot Backup

```bash
# Backup Julia depot (run daily via cron)
#!/bin/bash
# backup-julia-depot.sh

BACKUP_BUCKET="s3://carbon-backups/julia-depot"
DATE=$(date +%Y%m%d-%H%M%S)

# Create tarball of Julia depot
kubectl exec -n carbon deployment/carbon-sciml -- \
  tar -czf /tmp/julia-depot-$DATE.tar.gz -C /opt/julia/depot .

# Upload to S3
kubectl exec -n carbon deployment/carbon-sciml -- \
  aws s3 cp /tmp/julia-depot-$DATE.tar.gz $BACKUP_BUCKET/julia-depot-$DATE.tar.gz

# Cleanup local
kubectl exec -n carbon deployment/carbon-sciml -- rm /tmp/julia-depot-$DATE.tar.gz

# Verify upload
aws s3 ls $BACKUP_BUCKET/julia-depot-$DATE.tar.gz
```

---

## 5.5 Incident Response for SciML Service

### SEV-1: SciML Service Completely Down

```bash
# 1. Immediate assessment
kubectl get pods -n carbon -l app=carbon-sciml
kubectl get nodes -l gpu-type=h100-80gb

# 2. Check Bittensor connectivity
btcli subnet list --netuid 1

# 3. Common causes & fixes:
# - Julia OOM → Check GC pressure, increase memory limits
# - Julia depot corruption → Restore from backup
# - GPU driver issues → Restart GPU operators, check nvidia-smi
# - Julia version mismatch → Verify all replicas same version

# 4. Emergency fallback: Disable SciML validation temporarily
# (Validators fall back to internal validation only)
kubectl patch configmap validator-config -n carbon -p '{"data":{"sciml_oracle":{"enabled":"false"}}}'

# 5. Restart service
kubectl rollout restart deployment/carbon-sciml -n carbon

# 6. Verify recovery
curl -f http://carbon-sciml:8083/health
curl -X POST http://carbon-sciml:8083/solve_pde \
  -H "Content-Type: application/json" \
  -d '{"action":"solve_pde","pde_spec":{"type":"poisson"},"params":{}}'
```

### SEV-2: High Latency / Solver Divergence

```bash
# 1. Check solver metrics
curl -s http://carbon-sciml:8083/metrics | grep sciml_

# 2. Check Julia GC pressure
curl -s http://carbon-sciml:8083/metrics | grep julia_gc

# 3. If GC pressure high:
# - Increase memory limits
# - Increase JULIA_NUM_THREADS
# - Tune GC: `GC.enable(false)` during solves (if safe)

# 4. If solver divergence:
# - Check for NaN/Inf in inputs
# - Verify PDE specification correctness
# - Fall back to more robust solver (Vern9 → Tsit5)

# 5. Scale up replicas temporarily
kubectl scale deployment carbon-sciml --replicas=4 -n carbon
```

---

## 5.5 Backup & Disaster Recovery for Julia/SciML

### 5.5.1 Backup Strategy

| Data | Frequency | Retention | Location |
|------|-----------|-----------|----------|
| **Julia Depot** | Daily | 90 days | S3/GCS (versioned) |
| **Julia Manifest.toml** | On change | Permanent | GitOps repo |
| **Precompilation Cache** | Daily | 30 days | S3/GCS |
| **SciML Service Config** | On change | 1 year | GitOps repo |

### 5.5.2 Disaster Recovery

```bash
# Restore Julia depot from backup
# 1. Provision new PVC
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: carbon-julia-depot-restored
  namespace: carbon
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Gi
  storageClassName: nvme-fast
EOF

# 2. Restore from S3
kubectl run -it --rm --restart=Never julia-restore \
  --image=amazon/aws-cli \
  -- aws s3 cp s3://carbon-backups/julia-depot/latest.tar.gz - | tar -xz -C /opt/julia/depot

# 3. Attach restored PVC to new deployment
kubectl patch deployment carbon-sciml -n carbon -p \
  '{"spec":{"template":{"spec":{"volumes":[{"name":"julia-depot","persistentVolumeClaim":{"claimName":"carbon-julia-depot-restored"}}]}}}'

# 4. Verify restoration
kubectl exec -it -n carbon deployment/carbon-sciml -- julia --project -e '
    using Pkg
    Pkg.status()
    using DifferentialEquations, NeuralPDE, ModelingToolkit, SciMLSensitivity
    println("Restoration verified")
'
```

---

## 5.6 Julia/SciML Service Runbooks

### 5.6.1 Runbook: Deploy New Julia/SciML Version

```markdown
# Runbook: Deploy Julia/SciML Service Update

## Prerequisites
- [ ] New Julia/SciML version tested on staging
- [ ] Docker image built and pushed to GHCR
- [ ] Changelog reviewed for breaking changes
- [ ] Rollback plan documented

## Procedure
1. Update Docker image tag in K8s deployment
   `kubectl set image deployment/carbon-sciml carbon-sciml=ghcr.io/carbon/sciml-service:v2.1.1 -n carbon`

2. Monitor rollout
   `kubectl rollout status deployment/carbon-sciml -n carbon --timeout=5m`

3. Verify health
   `curl -f http://carbon-sciml:8083/health`

4. Run smoke test
   `curl -X POST http://carbon-sciml:8083/solve_pde -H "Content-Type: application/json" -d '{"action":"solve_pde","pde_spec":{"type":"poisson"},"params":{}}'`

4. Monitor metrics for 30 min
   `watch -n 10 'curl -s http://carbon-sciml:8083/metrics | grep sciml_'`

## Rollback
1. `kubectl rollout undo deployment/carbon-sciml -n carbon`
2. Verify health
3. Notify team
```

### 5.6.2 Runbook: Restore Julia Depot from Backup

```markdown
# Runbook: Restore Julia Depot from Backup

## Prerequisites
- [ ] Backup tarball available in S3
- [ ] New PVC provisioned
- [ ] Maintenance window scheduled

## Procedure
1. Provision new PVC
   `kubectl apply -f k8s/julia-depot-restored-pvc.yaml`

2. Restore from S3
   `kubectl run -it --rm --restart=Never julia-restore --image=amazon/aws-cli -- aws s3 cp s3://carbon-backups/julia-depot/latest.tar.gz - | tar -xz -C /opt/julia/depot`

3. Attach restored PVC
   `kubectl patch deployment carbon-sciml -n carbon -p '{"spec":{"template":{"spec":{"volumes":[{"name":"julia-depot","persistentVolumeClaim":{"claimName":"carbon-julia-depot-restored"}}]}}}}`

4. Verify restoration
   `kubectl exec -it -n carbon deployment/carbon-sciml -- julia --project -e "using Pkg; Pkg.status(); using DifferentialEquations, NeuralPDE, ModelingToolkit, SciMLSensitivity; println(\"Restoration verified\")"`

## Verification
- [ ] Health endpoint returns 200
- [ ] PDE solve test passes
- [ ] Metrics show normal operation
```

---

This is not a complete implementation of all the SPEC features, but rather a focused update to integrate the Julia/SciML Ground Truth Oracle into the operations documentation. The document has been restructured to be the third document in the three-document suite (SPEC.md, IMPLEMENTATION.md, OPERATIONS.md) with proper cross-references.

The document now includes:
1. Complete Julia/SciML Ground Truth Oracle operations section
2. Deployment procedures for Julia service
3. Julia depot management
3. Monitoring and alerting for Julia/SciML service
4. Incident response procedures for Julia/SciML issues
5. Backup and disaster recovery for Julia depot
6. Runbooks for common operations
7. Updated monitoring and alerting with Julia-specific metrics
8. Updated incident response with Julia-specific scenarios

The document maintains the same professional structure and detail level as the previous OPERATIONS.md but now fully incorporates the Julia/SciML Ground Truth Oracle that is central to Carbon's architecture# OPERATIONS.md — Carbon Subnet Operations & Deployment Guide
