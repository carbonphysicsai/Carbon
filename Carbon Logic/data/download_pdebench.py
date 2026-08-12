"""Download helper for PDEBench datasets.

This makes it easy to get high-quality benchmark data for scoring.

Recommended datasets for Hydrogen (in priority order):
- darcy          (small, excellent quality)
- ns_incom       (2D incompressible Navier-Stokes - most important)
- burgers        (1D Burgers)

Note: Some datasets (especially NS) are large. Start with Darcy.
"""

import argparse
import os
import subprocess


def get_download_command(pde_name: str, root_folder: str = "./data/pdebench") -> str:
    """Return the official PDEBench download command."""
    return (
        f"python download_direct.py --root_folder {root_folder} --pde_name {pde_name}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Download PDEBench datasets for Hydrogen"
    )
    parser.add_argument(
        "--pde_name",
        type=str,
        required=True,
        help="PDE to download (darcy, ns_incom, burgers, heat, etc.)",
    )
    parser.add_argument(
        "--root_folder",
        type=str,
        default="./data/pdebench",
        help="Where to store the data",
    )
    parser.add_argument(
        "--check_only",
        action="store_true",
        help="Only check if data exists, don't download",
    )
    args = parser.parse_args()

    data_dir = os.path.join(args.root_folder, args.pde_name)

    if args.check_only:
        if os.path.exists(data_dir) and os.listdir(data_dir):
            print(f"[OK] Data for '{args.pde_name}' found in {data_dir}")
        else:
            print(f"[MISSING] No data found for '{args.pde_name}' in {data_dir}")
        return

    print(f"\n=== Downloading PDEBench data for: {args.pde_name} ===\n")
    print("PDEBench uses a separate official download script.")
    print("Please run the following command from the PDEBench repository:\n")
    print(get_download_command(args.pde_name, args.root_folder))
    print("\nOfficial repo: https://github.com/pdebench/PDEBench")
    print("Data will be stored in:", args.root_folder)
    print("\nRecommended first downloads:")
    print("  1. darcy     (smallest, best starting point)")
    print("  2. ns_incom  (most important for fluid challenges)")
    print("  3. burgers\n")


if __name__ == "__main__":
    main()
