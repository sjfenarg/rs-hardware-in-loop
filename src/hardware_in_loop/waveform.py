"""Waveform export helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray


def normalize_iq(samples: NDArray[np.complex128]) -> NDArray[np.complex64]:
    """Normalize complex samples so the largest I or Q component is inside [-1, 1]."""

    iq = np.asarray(samples, dtype=np.complex128)
    if iq.ndim != 1:
        raise ValueError("samples must be a 1-D complex array")
    if len(iq) == 0:
        raise ValueError("samples cannot be empty")

    peak_component = max(float(np.max(np.abs(iq.real))), float(np.max(np.abs(iq.imag))))
    if peak_component == 0:
        raise ValueError("all-zero waveform cannot be normalized")
    return (iq / peak_component).astype(np.complex64)


def write_rswv(
    samples: NDArray[np.complex128],
    sample_rate_hz: float,
    output_path: Path,
    *,
    comment: str = "HardwareInLoop waveform",
) -> Path:
    """Write complex-baseband samples to an R&S .wv file."""

    from RsWaveform import RsWaveform

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wv = RsWaveform()
    wv.data[0] = normalize_iq(samples)
    wv.meta[0] = {"clock": float(sample_rate_hz), "comment": comment}
    wv.save(str(output_path))
    return output_path
