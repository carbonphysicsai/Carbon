# Data Strategy for Hydrogen

## Goal
Score miners against the highest quality reference solutions possible so that emissions reward *actually useful* scientific work.

## Recommended Sources

### 1. PDEBench (Primary)
Best public benchmark for PINO/FNO work.

**Priority downloads:**
- `darcy` (small, high quality)
- `ns_incom` (2D incompressible Navier-Stokes — highest value)
- `burgers`

### How to Download

```bash
# From Hydrogen root
python -m hydrogen.data.download_pdebench --pde_name darcy
python -m hydrogen.data.download_pdebench --pde_name ns_incom
```

Then place the downloaded `.h5` files inside `./data/pdebench/` (or the path configured in `PDEBenchLoader`).

The loader will automatically discover them.

## Current Status
- PDEBenchLoader fully implemented with HDF5 parsing
- All major challenges support benchmark mode
- Validator scores against real benchmark data by default

## Caching & Usability
- `PDEBenchLoader` has `ensure_data()` helper
- Download script gives clear instructions
- Falls back gracefully to synthetic data
