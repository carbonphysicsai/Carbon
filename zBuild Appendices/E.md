# Appendix E: Local Development Environment

**Purpose:** This document specifies the complete local development stack for Hydrogen subnet development and testing. It includes Docker Compose stack for all services, Dockerfiles for each service, initialization scripts, test data generation, and quick-start commands. This enables developers to run the entire Hydrogen subnet locally for development and testing.

---

# Appendix E: Local Development Environment v2.1

---

## E.1 Docker Compose Stack

```yaml
# docker-compose.yml
version: '3.8'

services:
  # ============================================================
  # Blockchain Node (Substrate)
  # ============================================================
  subtensor:
    image: opentensor/subtensor:latest
    container_name: hydrogen-subtensor
    ports:
      - "9944:9944"    # WS RPC
      - "9933:9933"    # HTTP RPC
      - "30333:30333"  # P2P
    volumes:
      - subtensor_data:/data
    environment:
      - SUBTENSOR_NETWORK=local
      - SUBTENSOR_CHAIN=local
      - RUST_LOG=info
    command: [
      "--chain=local",
      "--dev",
      "--ws-external",
      "--rpc-external",
      "--rpc-cors=all",
      "--tmp"
    ]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9933/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ============================================================
  # PostgreSQL (Indexer + Dashboard)
  # ============================================================
  postgres:
    image: postgres:16-alpine
    container_name: hydrogen-postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: hydrogen_indexer
      POSTGRES_USER: hydrogen
      POSTGRES_PASSWORD: hydrogen_dev
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hydrogen -d hydrogen_indexer"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ============================================================
  # Redis (Caching, Sessions, Queue)
  # ============================================================
  redis:
    image: redis:7-alpine
    container_name: hydrogen-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ============================================================
  # Hydrogen API (GraphQL + REST)
  # ============================================================
  api:
    build:
      context: ..
      dockerfile: docker/api.Dockerfile
    container_name: hydrogen-api
    ports:
      - "8000:8000"    # REST API
      - "4000:4000"    # GraphQL
      - "4001:4001"    # GraphQL WS
    environment:
      - DATABASE_URL=postgresql://hydrogen:hydrogen_dev@postgres:5432/hydrogen_indexer
      - REDIS_URL=redis://redis:6379/0
      - SUBTENSOR_WS=ws://subtensor:9944
      - NETUID=107
      - OWNER_HOTKEY=5F_HydrogenOwnerHotkey
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - GRAPHQL_PORT=4000
      - LOG_LEVEL=DEBUG
      - RUST_LOG=debug
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      subtensor:
        condition: service_healthy
    volumes:
      - ./api:/app/api:ro  # Hot reload for development
    command: ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

  # ============================================================
  # Indexer (Blockchain Sync)
  # ============================================================
  indexer:
    build:
      context: ..
      dockerfile: docker/indexer.Dockerfile
    container_name: hydrogen-indexer
    environment:
      - DATABASE_URL=postgresql://hydrogen:hydrogen_dev@postgres:5432/hydrogen_indexer
      - REDIS_URL=redis://redis:6379/0
      - SUBTENSOR_WS=ws://subtensor:9944
      - NETUID=107
      - START_BLOCK=0
      - BATCH_SIZE=100
      - LOG_LEVEL=DEBUG
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      subtensor:
        condition: service_healthy
    command: ["python", "-m", "indexer.main"]

  # ============================================================
  # Validator (Development - CPU mode for CI)
  # ============================================================
  validator-dev:
    build:
      context: ..
      dockerfile: docker/validator.Dockerfile
      target: pino
    container_name: hydrogen-validator-dev
    environment:
      - CHALLENGE_ID=dev_test
      - SUBMISSION_JSON={"backbone":"PINO","physics_informed":true}
      - CHALLENGE_DATA_PATH=/data/challenge
      - CHALLENGE_PHASE=0
      - HYDROGEN_SEED=42
      - PYTHONUNBUFFERED=1
    volumes:
      - ./test_data:/data:ro
      - ./dev_output:/workspace/output
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    profiles: ["gpu"]  # Only run with --profile gpu

  # ============================================================
  # Miner CLI (Development)
  # ============================================================
  miner-cli:
    build:
      context: ..
      dockerfile: docker/miner.Dockerfile
    container_name: hydrogen-miner-cli
    environment:
      - WALLET_NAME=test_wallet
      - WALLET_HOTKEY=test_hotkey
      - NETUID=107
      - SUBTENSOR_NETWORK=local
      - SUBTENSOR_CHAIN_ENDPOINT=ws://subtensor:9944
      - API_URL=http://api:8000
    volumes:
      - ./miner_config:/root/.hydrogen
      - ./miner_strategies:/strategies
    entrypoint: ["bash"]
    stdin_open: true
    tty: true

  # ============================================================
  # Prometheus + Grafana (Monitoring)
  # ============================================================
  prometheus:
    image: prom/prometheus:v2.47.0
    container_name: hydrogen-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:10.1.0
    container_name: hydrogen-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=hydrogen_dev
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus

  # ============================================================
  # MinIO (S3-compatible storage for Well data, models)
  # ============================================================
  minio:
    image: minio/minio:RELEASE.2024-01-16T16-07-38Z
    container_name: hydrogen-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: hydrogen
      MINIO_ROOT_PASSWORD: hydrogen_dev
      MINIO_PROMETHEUS_AUTH_TYPE: public
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  # ============================================================
  # Well Data Downloader (Optional)
  # ============================================================
  well-downloader:
    build:
      context: ..
      dockerfile: docker/well-downloader.Dockerfile
    container_name: hydrogen-well-downloader
    environment:
      - WELL_DATASETS=turbulence,mhd,active_matter,viscoelastic,acoustic_scattering
      - MINIO_ENDPOINT=http://minio:9000
      - MINIO_ACCESS_KEY=hydrogen
      - MINIO_SECRET_KEY=hydrogen_dev
      - MINIO_BUCKET=well-data
    volumes:
      - minio_data:/data
    profiles: ["well-data"]
    command: ["python", "download_well.py"]

# ============================================================
# Volumes
# ============================================================
volumes:
  subtensor_data:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
  minio_data:
  dev_output:
```

---

## E.2 Dockerfiles

### E.2.1 API Dockerfile
```dockerfile
# docker/api.Dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code
COPY api/ ./api/
COPY shared/ ./shared/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000 4000 4001

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### E.2.2 Indexer Dockerfile
```dockerfile
# docker/indexer.Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY indexer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY indexer/ ./indexer/
COPY shared/ ./shared/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "indexer.main"]
```

### E.2.3 Validator Dockerfile (Multi-stage)
```dockerfile
# docker/validator.Dockerfile
# Base stage with all dependencies
FROM nvcr.io/nvidia/pytorch:24.09-py3 AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenmpi-dev openmpi-bin \
    git wget curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    physicsnemo==0.4.0 \
    neural-operator==0.3.0 \
    hydra-core \
    omegaconf \
    pyyaml \
    boto3 \
    requests \
    pyyaml

# Backbone-specific stages
FROM base AS fno
ENV BACKBONE=fno
COPY validator/ /workspace/validator/
WORKDIR /workspace/validator

FROM base AS pino
ENV BACKBONE=pino
COPY validator/ /workspace/validator/
WORKDIR /workspace/validator

FROM base AS deeponet
ENV BACKBONE=deeponet
COPY validator/ /workspace/validator/
WORKDIR /workspace/validator

FROM base AS gno
ENV BACKBONE=gno
COPY validator/ /workspace/validator/
WORKDIR /workspace/validator

FROM base AS oformer
ENV BACKBONE=oformer
COPY validator/ /workspace/validator/
WORKDIR /workspace/validator

# Final stage (select one at build time)
FROM pino AS final
WORKDIR /workspace/validator
COPY validator/ /workspace/validator/
ENTRYPOINT ["python", "entrypoint.py"]
```

### E.2.4 Miner CLI Dockerfile
```dockerfile
# docker/miner.Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY miner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY miner/ ./miner/
COPY shared/ ./shared/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "hydrogen_miner.cli"]
```

### E.2.5 Well Downloader Dockerfile
```dockerfile
# docker/well-downloader.Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    aria2 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    h5py \
    zarr \
    fsspec \
    s3fs \
    tqdm \
    boto3

COPY scripts/download_well.py .

CMD ["python", "download_well.py"]
```

---

## E.3 Initialization Scripts

### E.3.1 PostgreSQL Init Script
```sql
-- init-scripts/01-init.sql

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Custom types
CREATE TYPE challenge_status AS ENUM ('ACTIVE', 'SCORING', 'COMPLETED', 'ARCHIVED');
CREATE TYPE submission_status AS ENUM ('COMMITTED', 'REVEALED', 'VALIDATING', 'SCORED', 'REWARDED', 'REJECTED');
CREATE TYPE submission_type AS ENUM ('STRATEGY', 'SPECIALIST_PIPELINE');
CREATE TYPE license_type AS ENUM ('AGPL_3_0', 'COMMERCIAL', 'DUAL');
```

### E.3.2 Prometheus Config
```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'hydrogen-api'
    static_configs:
      - targets: ['api:8000']

  - job_name: 'hydrogen-indexer'
    static_configs:
      - targets: ['indexer:8080']

  - job_name: 'hydrogen-validator'
    static_configs:
      - targets: ['validator-dev:8080']

  - job_name: 'hydrogen-api-graphql'
    static_configs:
      - targets: ['api:4000']

  - job_name: 'subtensor'
    static_configs:
      - targets: ['subtensor:9615']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:9121']

  - job_name: 'minio'
    static_configs:
      - targets: ['minio:9000']
```

---

## E.4 Developer Scripts

### E.4.1 Start Script
```bash
#!/bin/bash
# scripts/start-dev.sh

set -e

echo "🚀 Starting Hydrogen Development Environment"

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker not running. Please start Docker."
    exit 1
fi

# Check NVIDIA Docker (for GPU)
if ! docker run --rm --gpus all nvidia/cuda:12.4-base nvidia-smi > /dev/null 2>&1; then
    echo "⚠️  NVIDIA Docker not available. GPU validator will not work."
    echo "   Run without --profile gpu for CPU-only development."
fi

# Create necessary directories
mkdir -p dev_output test_data miner_config miner_strategies

# Pull base images
echo "📦 Pulling base images..."
docker compose pull subtensor postgres redis minio

# Build custom images
echo "🔨 Building custom images..."
docker compose build api indexer

# Start core services
echo "🚀 Starting core services..."
docker compose up -d subtensor postgres redis minio

# Wait for health
echo "⏳ Waiting for core services..."
sleep 10

# Start indexer and API
echo "🔨 Starting indexer and API..."
docker compose up -d indexer api

# Wait for API
echo "⏳ Waiting for API..."
sleep 5

# Optional: Start GPU validator (requires --profile gpu)
if [[ "$1" == "--gpu" ]]; then
    echo "🎮 Starting GPU validator..."
    docker compose --profile gpu up -d validator-dev
fi

# Optional: Download Well data
if [[ "$1" == "--well-data" ]]; then
    echo "📥 Downloading Well data..."
    docker compose --profile well-data up well-downloader
fi

echo ""
echo "✅ Hydrogen Development Environment Ready!"
echo ""
echo "Services:"
echo "  - Subtensor:     ws://localhost:9944"
echo "  - API (REST):    http://localhost:8000"
echo "  - API (GraphQL): http://localhost:4000"
echo "  - GraphQL WS:    ws://localhost:4001"
echo "  - Indexer:       http://localhost:8080"
echo "  - MinIO Console: http://localhost:9001 (hydrogen/hydrogen_dev)"
echo "  - Grafana:       http://localhost:3000 (admin/hydrogen_dev)"
echo "  - Prometheus:    http://localhost:9090"
echo ""
echo "Commands:"
echo "  docker compose logs -f api          # Follow API logs"
echo "  docker compose logs -f indexer      # Follow indexer logs"
echo "  docker compose logs -f validator-dev # Follow validator logs"
echo "  docker compose exec miner-cli bash  # Enter miner CLI container"
echo "  docker compose down -v              # Stop and remove volumes"
```

### E.4.2 Test Data Generator
```python
# scripts/generate_test_data.py
#!/usr/bin/env python3
"""Generate synthetic test data for all 7 Phase 0 challenges."""

import numpy as np
import os
import json
from pathlib import Path

CHALLENGES = [
    {"id": 1, "name": "poisson_2d", "dim": 2, "resolution": [128, 128], "samples": 1000},
    {"id": 2, "name": "poisson_3d", "dim": 3, "resolution": [64, 64, 64], "samples": 200},
    {"id": 3, "name": "darcy_2d", "dim": 2, "resolution": [128, 128], "samples": 1000},
    {"id": 4, "name": "darcy_3d", "dim": 3, "resolution": [64, 64, 64], "samples": 200},
    {"id": 5, "name": "burgers_2d", "dim": 2, "resolution": [256, 100], "samples": 1000},
    {"id": 6, "name": "ns_2d", "dim": 2, "resolution": [128, 128], "samples": 1000},
    {"id": 7, "name": "ns_3d", "dim": 3, "resolution": [64, 64, 32], "samples": 200},
    {"id": 8, "name": "heat_2d", "dim": 2, "resolution": [128, 128, 50], "samples": 1000},
    {"id": 9, "name": "elasticity_2d", "dim": 2, "resolution": [128, 128], "samples": 1000},
    {"id": 10, "name": "thermo_elasticity_2d", "dim": 2, "resolution": [128, 128, 50], "samples": 500},
]

def generate_poisson_data(resolution, samples, dim):
    """Generate Poisson equation data: -∇²u = f"""
    if dim == 2:
        shape = (samples, *resolution, 1)  # f, u
    else:
        shape = (samples, *resolution, 1)
    
    f = np.random.randn(*shape).astype(np.float32)
    u = np.zeros_like(f)
    return {"inputs": f, "targets": u}

def generate_darcy_data(resolution, samples, dim):
    """Generate Darcy flow data: -∇·(k∇p) = f"""
    if dim == 2:
        k_shape = (samples, *resolution, 1)
    else:
        k_shape = (samples, *resolution, 1)
    
    log_k = np.random.randn(*k_shape).astype(np.float32) * 2  # log-permeability
    f = np.ones_like(log_k) * 0.1  # source term
    p = np.zeros_like(log_k)  # pressure (placeholder)
    return {"inputs": np.concatenate([log_k, f], axis=-1), "targets": p}

def generate_burgers_data(resolution, samples):
    """Generate Burgers equation data"""
    nx, nt = resolution
    u = np.random.randn(samples, nt, nx, 1).astype(np.float32) * 0.5
    return {"inputs": u[:, :1], "targets": u}

def generate_ns_data(resolution, samples, dim):
    """Generate Navier-Stokes data"""
    if dim == 2:
        shape = (samples, *resolution, 3)  # u, v, p
    else:
        shape = (samples, *resolution, 4)  # u, v, w, p
    u = np.random.randn(samples, *resolution, dim).astype(np.float32) * 0.1
    p = np.random.randn(samples, *resolution, 1).astype(np.float32) * 0.01
    return {"inputs": np.concatenate([u, p], axis=-1), "targets": u}

def generate_heat_data(resolution, samples):
    """Generate Heat equation data"""
    nx, ny, nt = resolution
    kappa = np.random.rand(samples, nx, ny, 1).astype(np.float32) + 0.5
    u = np.random.randn(samples, nt, nx, ny, 1).astype(np.float32) * 0.1
    return {"inputs": kappa, "targets": u}

def generate_elasticity_data(resolution, samples):
    """Generate Elasticity data"""
    shape = (samples, *resolution, 2)  # u_x, u_y
    u = np.random.randn(samples, *resolution, 2).astype(np.float32) * 0.01
    return {"inputs": np.random.randn(samples, *resolution, 2).astype(np.float32), "targets": u}

def generate_thermo_elasticity_data(resolution, samples):
    """Generate Thermo-elasticity data"""
    nx, ny, nt = resolution
    inputs = np.random.randn(samples, nx, ny, 4).astype(np.float32)  # lambda, mu, kappa, Q
    targets = np.random.randn(samples, nt, nx, ny, 3).astype(np.float32) * 0.01  # u_x, u_y, T
    return {"inputs": inputs, "targets": targets}

def main():
    base_path = Path("test_data")
    base_path.mkdir(parents=True, exist_ok=True)
    
    for challenge in CHALLENGES:
        cid = challenge["id"]
        name = challenge["name"]
        dim = challenge["dim"]
        resolution = challenge["resolution"]
        samples = challenge["samples"]
        
        print(f"Generating {name} ({samples} samples)...")
        
        # Determine generator
        if "poisson" in name:
            data = generate_poisson_data(resolution, samples, dim)
        elif "darcy" in name:
            data = generate_darcy_data(resolution, samples, dim)
        elif "burgers" in name:
            data = generate_burgers_data(resolution, samples)
        elif "ns" in name:
            data = generate_ns_data(resolution, samples, dim)
        elif "heat" in name:
            data = generate_heat_data(resolution, samples)
        elif "elasticity" in name and "thermo" not in name:
            data = generate_elasticity_data(resolution, samples)
        elif "thermo_elasticity" in name:
            data = generate_thermo_elasticity_data(resolution, samples)
        
        # Create challenge directory
        challenge_path = Path("test_data") / f"challenge_{cid}_{name}"
        challenge_path.mkdir(parents=True, exist_ok=True)
        
        # Split train/holdout (80/20)
        n_train = int(samples * 0.8)
        n_holdout = samples - n_train
        
        for split_name, n_samples in [("train", n_train), ("holdout", n_holdout)]:
            split_path = Path("test_data") / f"challenge_{cid}_{name}" / split_name
            split_path.mkdir(parents=True, exist_ok=True)
            
            # Slice data
            inputs = data["inputs"][:n_samples]
            targets = data["targets"][:n_samples]
            
            np.save(split_path / "inputs.npy", inputs)
            np.save(split_path / "targets.npy", targets)
        
        # Generate stress test data (smaller)
        stress_data = {k: v[:100] for k, v in data.items()}
        stress_path = Path("test_data") / f"challenge_{cid}_{name}" / "stress"
        stress_path.mkdir(parents=True, exist_ok=True)
        np.save(stress_path / "inputs.npy", stress_data["inputs"])
        np.save(stress_path / "targets.npy", stress_data["targets"])
        
        # Baseline error (placeholder)
        baseline_error = {"error": 0.01, "phase": 0}
        with open(Path("test_data") / f"challenge_{cid}_{name}" / "baseline_error.json", "w") as f:
            json.dump(baseline_error, f)
        
        # Metadata
        metadata = {
            "challenge_id": f"challenge_{cid}_{name}_0001",
            "problem_id": cid,
            "problem_name": name,
            "phase": 0,
            "physics_class": "test",
            "dimension": dim,
            "resolution": resolution,
            "stress_floors": {
                "mass_conservation": 1e-3,
                "energy_dissipation": 1e-4,
                "boundary": 1e-3,
                "rollout_steps": 100,
                "uq_target": 0.90
            },
            "well_mapping": [],
            "coupling_spec": None
        }
        with open(Path("test_data") / f"challenge_{cid}_{name}" / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"  ✅ {name} generated")

if __name__ == "__main__":
    main()
```

---

## E.5 Quick Start Commands

```bash
# 1. Start everything
chmod +x scripts/start-dev.sh scripts/generate_test_data.py
./scripts/generate_test_data.py
./scripts/start-dev.sh

# With GPU validator
./scripts/start-dev.sh --gpu

# With Well data download
./scripts/start-dev.sh --well-data

# Stop everything
docker compose down -v

# View logs
docker compose logs -f api
docker compose logs -f indexer
docker compose logs -f validator-dev

# Access containers
docker compose exec miner-cli bash
docker compose exec api bash
docker compose exec postgres psql -U hydrogen -d hydrogen_indexer
```

---

*End of Appendix E: Local Development Environment*
