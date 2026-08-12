"""PDEBench Data Loader for Hydrogen (with better usability)."""

import os
import glob
import h5py
import numpy as np
import torch
from typing import Dict, Any, Optional, Tuple, List


class PDEBenchLoader:
    def __init__(self, pde_name: str, data_root: str = "./data/pdebench"):
        self.pde_name = pde_name.lower()
        self.data_root = data_root
        os.makedirs(data_root, exist_ok=True)
        self.file_paths: List[str] = []
        self._discover_files()

    def _discover_files(self):
        patterns = {
            "darcy": ["*Darcy*.h5", "*darcy*.hdf5", "*DarcyFlow*.h5"],
            "ns_incom": ["*ns_incom*.h5", "*NS*.h5", "*incompressible*.h5"],
            "burgers": ["*Burgers*.h5", "*burgers*.hdf5"],
            "heat": ["*diffusion*.h5", "*Heat*.h5"],
        }
        search_patterns = patterns.get(self.pde_name, ["*.h5", "*.hdf5"])
        for pattern in search_patterns:
            self.file_paths.extend(
                glob.glob(os.path.join(self.data_root, "**", pattern), recursive=True)
            )

    def ensure_data(self):
        """Check if data exists and give helpful instructions if not."""
        if self.file_paths:
            return True

        print(f"\n[PDEBench] No data found for '{self.pde_name}'.")
        print("Please download it using:")
        print(f"  python -m hydrogen.data.download_pdebench --pde_name {self.pde_name}")
        print("Or run the official PDEBench downloader.")
        return False

    def load(
        self,
        split: str = "train",
        max_samples: Optional[int] = None,
        resolution: Optional[Tuple[int, int]] = None,
    ) -> Dict[str, torch.Tensor]:
        if not self.ensure_data():
            raise FileNotFoundError(f"PDEBench data for '{self.pde_name}' not found.")

        file_path = self.file_paths[0]
        print(f"[PDEBench] Loading from: {file_path}")

        with h5py.File(file_path, "r") as f:
            data = self._parse_file(f, self.pde_name)

        data = {k: torch.from_numpy(v).float() for k, v in data.items()}

        if max_samples is not None:
            for k in data:
                if isinstance(data[k], torch.Tensor) and data[k].dim() > 0:
                    data[k] = data[k][:max_samples]

        return data

    def _parse_file(self, f: h5py.File, pde_name: str) -> Dict[str, np.ndarray]:
        data = {}

        if pde_name in ["darcy", "darcy_2d"]:
            if "tensor" in f:
                tensor = f["tensor"][...]
                if tensor.shape[1] == 2:
                    data["a"] = tensor[:, 0]
                    data["u_true"] = tensor[:, 1]
                else:
                    data["u_true"] = tensor
            elif "a" in f and "u" in f:
                data["a"] = f["a"][...]
                data["u_true"] = f["u"][...]

        elif pde_name in ["ns_incom", "navier_stokes", "ns_2d"]:
            if "velocity" in f:
                data["velocity_true"] = f["velocity"][...]
            if "pressure" in f:
                data["pressure_true"] = f["pressure"][...]
            if not data and "tensor" in f:
                tensor = f["tensor"][...]
                if tensor.shape[1] >= 2:
                    data["velocity_true"] = tensor[:, :2]
                    if tensor.shape[1] > 2:
                        data["pressure_true"] = tensor[:, 2]

        elif pde_name == "burgers":
            if "tensor" in f:
                data["u_true"] = f["tensor"][...]
            elif "u" in f:
                data["u_true"] = f["u"][...]

        else:
            for key in list(f.keys())[:5]:
                if isinstance(f[key], h5py.Dataset):
                    data[key] = f[key][...]

        if not data:
            raise ValueError(f"Could not parse PDEBench file for {pde_name}")

        return data

    def get_baseline_error(self) -> float:
        baselines = {
            "darcy": 0.095,
            "ns_incom": 0.18,
            "burgers": 0.12,
            "heat": 0.09,
        }
        return baselines.get(self.pde_name, 0.15)
