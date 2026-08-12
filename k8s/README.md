# Kubernetes Deployment for Carbon Validator

This directory contains basic Kubernetes manifests for deploying the Carbon validator.

## Files

- `validator-deployment.yaml`: Main deployment with GPU request
- `validator-service.yaml`: Service for internal access

## Quick Start

```bash
kubectl apply -f k8s/
```

## Important Notes

1. **GPU Nodes**: Make sure your cluster has nodes with NVIDIA GPUs and the NVIDIA device plugin installed.
2. **Data Volume**: Update the `hostPath` in the deployment to point to where your PDEBench data lives.
3. **Image**: Build and push your image first, or use an image from a registry.
4. **Secrets**: For wallet hotkeys / coldkeys, use Kubernetes Secrets instead of hardcoding.

## Production Recommendations

- Use a proper image registry (not `latest` tag)
- Add resource limits and requests properly
- Use ConfigMaps / Secrets for configuration
- Consider HorizontalPodAutoscaler if running multiple validators
- Add liveness/readiness probes

This is a starting point for Phase 0.
