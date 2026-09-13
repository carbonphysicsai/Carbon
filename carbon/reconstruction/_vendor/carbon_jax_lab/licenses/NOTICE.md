# Source and reuse notice

This standalone research package was prepared for Carbon. It is not a release of the Carbon repository and does not set the licensing policy for Carbon's original code.

## Adapted code and equations

The optional PyTorch oracle in `third_party/transolver_reference.py` adapts the irregular-mesh Physics-Attention core from THUML/Transolver, commit `75e0f67643806a81cd1d3f6adc88dd8c02416fe7`. The JAX attention core implements the corresponding slice/attention/deslice operations. The adaptation removes the dependency on einops, fixes dropout to zero for comparison, and maps externally supplied shared weights. The JAX training version parameterizes temperature through softplus and offers point quadrature weights; these are declared departures. Preserve `third_party/TRANSOLVER_LICENSE.txt` and its copyright notice.

The FNO implementation follows the dense real 1D postactivation computation documented in Carbon PR #40 and the MIT-licensed neuraloperator implementation. Preserve `third_party/NEURALOPERATOR_LICENSE.txt`. Carbon PR #40 is a user-supplied, non-authoritative research source. This package does not assume that the whole Carbon repository has an MIT license. No native `poc` package, old scoring system, or reference implementation from that branch is bundled. The parameter bridge is new array-layout mapping code.

The Haar, graph, graph/Fourier hybrid, DeepONet, trainer, checkpoint, and demonstration reference implementations are research code authored for this package from the documented mathematical methods. They are not vendored WNO, GINO, GAOT, PhysicsNeMo, jNO, PDEquinox, or Exponax implementations. Those projects retain their own licenses. No model weights or datasets were downloaded from them.

## Unresolved third-party integrations

The GAOT repository's root license was not established in the inspected material. No GAOT code is copied here. The reviewed jNO metadata states EPL-2.0 and a different JAX version range; this package neither vendors it nor claims its license is equivalent to MIT. Any later integration must review its actual files and terms. Paper availability and a public repository do not by themselves grant authority for every commercial use.

Run the optional reference tests only with their separate PyTorch dependency. The JAX training runtime does not import that test oracle or Torch.
