"""YAML configuration for the generic HIL runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class SignalGeneratorConfig:
    visa: str = ""
    remote_waveform_path: str = "/var/user/signal.wv"
    enabled: bool = True


@dataclass(slots=True)
class AnalyzerConfig:
    visa: str = ""
    remote_capture_path: str = r"C:\R_S\Instr\user\capture.iq.tar"
    enabled: bool = True
    record_length: int | None = None
    capture_multiplier: float = 2.0
    auto_level: bool = True


@dataclass(slots=True)
class HardwareConfig:
    center_freq_hz: float = 3.1e9
    sample_rate_hz: float | None = None
    power_dbm: float = -10.0
    timeout_ms: int = 60000
    reset_on_connect: bool = True
    signal_generator: SignalGeneratorConfig = field(default_factory=SignalGeneratorConfig)
    analyzer: AnalyzerConfig = field(default_factory=AnalyzerConfig)


@dataclass(slots=True)
class RunConfig:
    output_dir: str = "runs"
    tag: str = "hil"
    dry_run: bool = False
    keep_rf_on: bool = False


@dataclass(slots=True)
class EndpointConfig:
    target: str = ""
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HilConfig:
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    run: RunConfig = field(default_factory=RunConfig)
    tx: EndpointConfig = field(default_factory=EndpointConfig)
    rx: EndpointConfig = field(default_factory=EndpointConfig)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_config(path: str | Path) -> HilConfig:
    """Load a YAML config file."""

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    hardware_raw = _as_dict(raw.get("hardware"))
    sg_raw = _as_dict(hardware_raw.get("signal_generator"))
    analyzer_raw = _as_dict(hardware_raw.get("analyzer"))

    hardware = HardwareConfig(
        center_freq_hz=float(hardware_raw.get("center_freq_hz", 3.1e9)),
        sample_rate_hz=(
            None
            if hardware_raw.get("sample_rate_hz") is None
            else float(hardware_raw["sample_rate_hz"])
        ),
        power_dbm=float(hardware_raw.get("power_dbm", -10.0)),
        timeout_ms=int(hardware_raw.get("timeout_ms", 60000)),
        reset_on_connect=bool(hardware_raw.get("reset_on_connect", True)),
        signal_generator=SignalGeneratorConfig(
            visa=str(sg_raw.get("visa", "")),
            remote_waveform_path=str(sg_raw.get("remote_waveform_path", "/var/user/signal.wv")),
            enabled=bool(sg_raw.get("enabled", True)),
        ),
        analyzer=AnalyzerConfig(
            visa=str(analyzer_raw.get("visa", "")),
            remote_capture_path=str(
                analyzer_raw.get("remote_capture_path", r"C:\R_S\Instr\user\capture.iq.tar")
            ),
            enabled=bool(analyzer_raw.get("enabled", True)),
            record_length=(
                None
                if analyzer_raw.get("record_length") is None
                else int(analyzer_raw["record_length"])
            ),
            capture_multiplier=float(analyzer_raw.get("capture_multiplier", 2.0)),
            auto_level=bool(analyzer_raw.get("auto_level", True)),
        ),
    )

    run_raw = _as_dict(raw.get("run"))
    tx_raw = _as_dict(raw.get("tx"))
    rx_raw = _as_dict(raw.get("rx"))

    return HilConfig(
        hardware=hardware,
        run=RunConfig(
            output_dir=str(run_raw.get("output_dir", "runs")),
            tag=str(run_raw.get("tag", "hil")),
            dry_run=bool(run_raw.get("dry_run", False)),
            keep_rf_on=bool(run_raw.get("keep_rf_on", False)),
        ),
        tx=EndpointConfig(
            target=str(tx_raw.get("target", "")),
            params=_as_dict(tx_raw.get("params")),
        ),
        rx=EndpointConfig(
            target=str(rx_raw.get("target", "")),
            params=_as_dict(rx_raw.get("params")),
        ),
    )
