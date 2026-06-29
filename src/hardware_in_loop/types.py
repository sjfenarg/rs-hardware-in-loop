"""Small data contracts used by user TX/RX code and the HIL runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray


ComplexArray = NDArray[np.complex128]


@dataclass(slots=True)
class TxWaveform:
    """Output produced by a user-defined transmitter."""

    samples: ComplexArray
    sample_rate_hz: float
    name: str = "waveform"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.samples = np.asarray(self.samples, dtype=np.complex128)
        if self.samples.ndim != 1:
            raise ValueError("TxWaveform.samples must be a 1-D complex array")
        if len(self.samples) == 0:
            raise ValueError("TxWaveform.samples cannot be empty")
        if self.sample_rate_hz <= 0:
            raise ValueError("TxWaveform.sample_rate_hz must be positive")


@dataclass(slots=True)
class CaptureResult:
    """I/Q returned by the analyzer or dry-run loopback."""

    samples: ComplexArray
    sample_rate_hz: float
    center_freq_hz: float
    source_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.samples = np.asarray(self.samples, dtype=np.complex128)
        if self.samples.ndim != 1:
            raise ValueError("CaptureResult.samples must be a 1-D complex array")


@dataclass(slots=True)
class HilContext:
    """Context passed to user RX code."""

    run_dir: Path
    tx: TxWaveform
    config: Any


@dataclass(slots=True)
class RxResult:
    """Result produced by a user-defined receiver."""

    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)


class Transmitter(Protocol):
    """Protocol for class-based transmitters."""

    def generate(self, params: dict[str, Any], run_dir: Path) -> TxWaveform:
        """Generate a transmit waveform."""


class Receiver(Protocol):
    """Protocol for class-based receivers."""

    def process(
        self,
        capture: CaptureResult,
        context: HilContext,
        params: dict[str, Any],
    ) -> RxResult | dict[str, Any]:
        """Process captured I/Q."""
