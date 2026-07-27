#!/bin/bash
# scripts/deploy.sh
set -euo pipefail

echo "Building Julia sysimage..."
julia --project scripts/build_sysimage.jl

echo "Building Docker image..."
docker build -f docker/Dockerfile.sciml -t ghcr.io/carbon/sciml-service:v2.1.0 .

echo "Pushing to registry..."
docker push ghcr.io/carbon/sciml-service:v2.1.0

echo "Deploying to Kubernetes..."
kubectl apply -f k8s/sciml-deployment.yaml
kubectl apply -f k8s/sciml-service.yaml
kubectl apply -f k8s/sciml-pvc.yaml
kubectl apply -f k8s/sciml-configmap.yaml

echo "Deployment complete"
