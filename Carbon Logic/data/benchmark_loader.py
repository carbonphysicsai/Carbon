"""Benchmark data loader with NeuralOperator integration.

Tries to use neuraloperator dataset utilities when available.
"""

import os
from typing import Optional, Tuple

import torch
from torch.utils.data import Dataset, DataLoader

try:
    from neuralop.datasets import load_darcy, load_burgers, load_poisson
    NEURALOPERATOR_DATA_AVAILABLE = True
except ImportError:
    NEURALOPERATOR_DATA_AVAILABLE = False


class PDEBenchDataset(Dataset):
    def __init__(self, file_path: str, split: str = "train", resolution: Optional[Tuple[int, int]] = None):
        self.file_path = file_path
        self.split = split
        self.resolution = resolution

        import h5py
        with h5py.File(file_path, "r") as f:
            self.keys = list(f.keys())

    def __len__(self):
        return len(self.keys)

    def __getitem__(self, idx):
        import h5py
        with h5py.File(self.file_path, "r") as f:
            key = self.keys[idx]
            data = f[key][...]

        x = torch.tensor(data["input"], dtype=torch.float32)
        y = torch.tensor(data["output"], dtype=torch.float32)

        return x, y


def get_pdebench_loader(
    challenge_id: str,
    data_dir: str = "./data/pdebench",
    batch_size: int = 8,
    split: str = "train",
):
    filename_map = {
        "poisson_2d_v1": "poisson_2d.h5",
        "darcy_2d_v1": "darcy_2d.h5",
        "burgers_v1": "burgers.h5",
        "heat_v1": "heat.h5",
        "ns_2d_laminar_v1": "navier_stokes_2d.h5",
    }

    filename = filename_map.get(challenge_id, "default.h5")
    file_path = os.path.join(data_dir, filename)

    if not os.path.exists(file_path):
        print(f"[Data] PDEBench file not found for {challenge_id}, using synthetic.")
        return get_synthetic_loader(batch_size=batch_size)

    dataset = PDEBenchDataset(file_path, split=split)
    return DataLoader(dataset, batch_size=batch_size, shuffle=(split == "train"))


def get_synthetic_loader(batch_size: int = 8, resolution: Tuple[int, int] = (64, 64)):
    class SyntheticDataset(Dataset):
        def __len__(self):
            return 100

        def __getitem__(self, idx):
            x = torch.randn(3, *resolution)
            y = torch.randn(1, *resolution)
            return x, y

    return DataLoader(SyntheticDataset(), batch_size=batch_size, shuffle=True)


def get_benchmark_loader(challenge_id: str, backbone: str = "default", **kwargs):
    """
    Unified benchmark loader.

    Tries NeuralOperator datasets first (if available), then PDEBench, then synthetic.
    """
    if NEURALOPERATOR_DATA_AVAILABLE:
        try:
            if "darcy" in challenge_id:
                return load_darcy(batch_size=kwargs.get("batch_size", 8), train_test_split="train")
            elif "burgers" in challenge_id:
                return load_burgers(batch_size=kwargs.get("batch_size", 8))
            elif "poisson" in challenge_id:
                return load_poisson(batch_size=kwargs.get("batch_size", 8))
        except Exception:
            pass  # Fall through to PDEBench

    return get_pdebench_loader(challenge_id, **kwargs)
