"""Generic HIL orchestration."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .capture import load_iqtar
from .config import HilConfig
from .instruments import FswIqAnalyzer, Smw200aSignalGenerator
from .types import CaptureResult, HilContext, RxResult, TxWaveform
from .waveform import write_rswv

logger = logging.getLogger(__name__)


def create_run_dir(base_dir: Path, tag: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = base_dir / f"{timestamp}_{tag}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def run_hil(
    *,
    config: HilConfig,
    tx_plugin: Any,
    rx_plugin: Any | None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    """Run a TX -> HIL -> RX experiment."""

    run_dir = run_dir or create_run_dir(Path(config.run.output_dir), config.run.tag)
    run_dir.mkdir(parents=True, exist_ok=True)

    tx = _generate_tx(tx_plugin, config.tx.params, run_dir)
    sample_rate_hz = config.hardware.sample_rate_hz or tx.sample_rate_hz
    record_length = _record_length(config, len(tx.samples))

    waveform_path = _write_waveform_file(tx, sample_rate_hz, run_dir, config.run.dry_run)
    _write_json(run_dir / "tx_metadata.json", {
        "name": tx.name,
        "sample_rate_hz": sample_rate_hz,
        "num_samples": len(tx.samples),
        "waveform_path": str(waveform_path),
        "metadata": tx.metadata,
    })

    if config.run.dry_run:
        capture = _dry_run_capture(tx, config, record_length, sample_rate_hz)
    else:
        capture = _hardware_capture(config, waveform_path, record_length, sample_rate_hz, run_dir)

    context = HilContext(run_dir=run_dir, tx=tx, config=config)
    rx_result = _process_rx(rx_plugin, capture, context, config.rx.params)

    summary = {
        "run_dir": str(run_dir),
        "dry_run": config.run.dry_run,
        "tx": {
            "name": tx.name,
            "sample_rate_hz": sample_rate_hz,
            "num_samples": len(tx.samples),
        },
        "capture": {
            "sample_rate_hz": capture.sample_rate_hz,
            "center_freq_hz": capture.center_freq_hz,
            "num_samples": len(capture.samples),
            "source_path": str(capture.source_path) if capture.source_path else None,
            "metadata": capture.metadata,
        },
        "rx": asdict(rx_result),
    }
    _write_json(run_dir / "summary.json", summary)
    return summary


def _generate_tx(plugin: Any, params: dict[str, Any], run_dir: Path) -> TxWaveform:
    if hasattr(plugin, "generate"):
        tx = plugin.generate(params, run_dir)
    elif callable(plugin):
        tx = plugin(params, run_dir)
    else:
        raise TypeError("TX target must be callable or expose generate(params, run_dir)")

    if not isinstance(tx, TxWaveform):
        raise TypeError("TX target must return hardware_in_loop.TxWaveform")
    return tx


def _process_rx(
    plugin: Any | None,
    capture: CaptureResult,
    context: HilContext,
    params: dict[str, Any],
) -> RxResult:
    if plugin is None:
        return RxResult(metrics={})

    if hasattr(plugin, "process"):
        result = plugin.process(capture, context, params)
    elif callable(plugin):
        result = plugin(capture, context, params)
    else:
        raise TypeError("RX target must be callable or expose process(capture, context, params)")

    if isinstance(result, RxResult):
        return result
    if isinstance(result, dict):
        return RxResult(metrics=result)
    raise TypeError("RX target must return RxResult or dict")


def _record_length(config: HilConfig, tx_len: int) -> int:
    analyzer = config.hardware.analyzer
    if analyzer.record_length is not None:
        return analyzer.record_length
    return int(np.ceil(tx_len * analyzer.capture_multiplier))


def _write_waveform_file(
    tx: TxWaveform,
    sample_rate_hz: float,
    run_dir: Path,
    dry_run: bool,
) -> Path:
    try:
        return write_rswv(
            tx.samples,
            sample_rate_hz,
            run_dir / "signal.wv",
            comment=f"HardwareInLoop: {tx.name}",
        )
    except ImportError:
        if not dry_run:
            raise
        fallback_path = run_dir / "signal.npy"
        np.save(fallback_path, tx.samples)
        logger.warning("RsWaveform is not installed; wrote dry-run fallback %s", fallback_path)
        return fallback_path


def _dry_run_capture(
    tx: TxWaveform,
    config: HilConfig,
    record_length: int,
    sample_rate_hz: float,
) -> CaptureResult:
    repeats = int(np.ceil(record_length / len(tx.samples)))
    samples = np.tile(tx.samples, repeats)[:record_length]
    return CaptureResult(
        samples=samples,
        sample_rate_hz=sample_rate_hz,
        center_freq_hz=config.hardware.center_freq_hz,
        metadata={"mode": "dry_run_loopback"},
    )


def _hardware_capture(
    config: HilConfig,
    wv_path: Path,
    record_length: int,
    sample_rate_hz: float,
    run_dir: Path,
) -> CaptureResult:
    hw = config.hardware
    sg_cfg = hw.signal_generator
    analyzer_cfg = hw.analyzer

    if not sg_cfg.visa:
        raise ValueError("hardware.signal_generator.visa is required for hardware runs")
    if not analyzer_cfg.visa:
        raise ValueError("hardware.analyzer.visa is required for hardware runs")

    sg = Smw200aSignalGenerator(sg_cfg.visa, hw.timeout_ms, reset=hw.reset_on_connect)
    try:
        sg.upload_waveform(wv_path, sg_cfg.remote_waveform_path)
        sg.configure(
            remote_waveform_path=sg_cfg.remote_waveform_path,
            center_freq_hz=hw.center_freq_hz,
            power_dbm=hw.power_dbm,
            sample_rate_hz=sample_rate_hz,
        )
        sg.rf_on()

        iqtar_path = run_dir / "capture.iq.tar"
        analyzer = FswIqAnalyzer(analyzer_cfg.visa, hw.timeout_ms, reset=hw.reset_on_connect)
        try:
            analyzer.configure(
                center_freq_hz=hw.center_freq_hz,
                sample_rate_hz=sample_rate_hz,
                record_length=record_length,
            )
            if analyzer_cfg.auto_level:
                analyzer.auto_level()
            analyzer.capture()
            analyzer.download_iqtar(iqtar_path, analyzer_cfg.remote_capture_path)
        finally:
            analyzer.close()
    finally:
        if not config.run.keep_rf_on:
            sg.rf_off()
        sg.close()

    samples, meta = load_iqtar(iqtar_path)
    return CaptureResult(
        samples=samples,
        sample_rate_hz=float(meta.get("sample_rate_hz") or sample_rate_hz),
        center_freq_hz=float(meta.get("center_freq_hz") or hw.center_freq_hz),
        source_path=iqtar_path,
        metadata=meta,
    )


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=_json_default)


def _json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    return str(value)
