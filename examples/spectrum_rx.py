"""Example receiver: compute basic spectrum and power metrics."""

from __future__ import annotations

import json

import numpy as np

from hardware_in_loop import CaptureResult, HilContext, RxResult


def process(capture: CaptureResult, context: HilContext, params: dict) -> RxResult:
    samples = capture.samples
    sample_rate_hz = capture.sample_rate_hz

    rms_power = float(np.mean(np.abs(samples) ** 2))
    peak_power = float(np.max(np.abs(samples) ** 2))

    window = np.hanning(len(samples))
    spectrum = np.fft.fftshift(np.fft.fft(samples * window))
    freqs = np.fft.fftshift(np.fft.fftfreq(len(samples), d=1.0 / sample_rate_hz))
    peak_idx = int(np.argmax(np.abs(spectrum)))
    dominant_baseband_freq_hz = float(freqs[peak_idx])

    metrics = {
        "rms_power": rms_power,
        "peak_power": peak_power,
        "dominant_baseband_freq_hz": dominant_baseband_freq_hz,
        "num_samples": int(len(samples)),
    }

    metrics_path = context.run_dir / "rx_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    return RxResult(metrics=metrics, artifacts={"metrics": str(metrics_path)})
