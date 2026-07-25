# Multi-backend Validator Image for Carbon
# Supports both PhysicsNeMo and NeuralOperator backbones

FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# System dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --upgrade pip setuptools wheel

# Core scientific + ML
RUN pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
RUN pip3 install numpy scipy pandas scikit-learn pyyaml tqdm h5py

# Bittensor
RUN pip3 install bittensor

# PhysicsNeMo (NVIDIA)
RUN pip3 install physicsnemo

# NeuralOperator (community standard)
RUN pip3 install neuraloperator

# Causal + Symbolic
RUN pip3 install econml pysr

# Optional: Docker SDK for some validator features
RUN pip3 install docker

# Create app directory
WORKDIR /app

# Copy Carbon code
COPY . /app

# Install Carbon in editable mode
RUN pip3 install -e .

# Default command
CMD ["python3", "-m", "neurons.validator"]
