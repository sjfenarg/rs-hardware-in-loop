"""Example transmitter: generate a complex sinusoid or linear chirp."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from hardware_in_loop import TxWaveform


def generate(params: dict, run_dir: Path) -> TxWaveform:
    sample_rate_hz = float(params.get("sample_rate_hz", 50e6))
    duration_s = float(params.get("duration_s", 1e-3))
    amplitude = float(params.get("amplitude", 0.7))
    mode = str(params.get("mode", "tone"))

    n = int(round(duration_s * sample_rate_hz))
    t = np.arange(n, dtype=np.float64) / sample_rate_hz

    if mode == "chirp":
        f0 = float(params.get("start_freq_hz", -5e6))
        f1 = float(params.get("stop_freq_hz", 5e6))
        k = (f1 - f0) / duration_s
        phase = 2 * np.pi * (f0 * t + 0.5 * k * t**2)
    else:
        tone_freq_hz = float(params.get("tone_freq_hz", 1e6))
        phase = 2 * np.pi * tone_freq_hz * t

    samples = amplitude * np.exp(1j * phase)
    return TxWaveform(
        samples=samples,
        sample_rate_hz=sample_rate_hz,
        name=f"example_{mode}",
        metadata={
            "mode": mode,
            "duration_s": duration_s,
            "amplitude": amplitude,
        },
    )
