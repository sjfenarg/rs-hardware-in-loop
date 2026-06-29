"""Template for a user-defined transmitter."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from hardware_in_loop import TxWaveform


def generate(params: dict, run_dir: Path) -> TxWaveform:
    """Return complex-baseband I/Q samples.

    Inputs:
        params: the dictionary under tx.params in the YAML config.
        run_dir: per-experiment folder for optional TX-side artifacts.

    Output:
        TxWaveform(samples, sample_rate_hz, name, metadata)
    """

    sample_rate_hz = float(params["sample_rate_hz"])
    num_samples = int(params.get("num_samples", 10000))
    samples = np.zeros(num_samples, dtype=np.complex128)

    return TxWaveform(
        samples=samples,
        sample_rate_hz=sample_rate_hz,
        name="replace_me",
        metadata={"note": "replace this template with your waveform metadata"},
    )
