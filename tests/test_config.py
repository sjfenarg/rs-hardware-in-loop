from __future__ import annotations

from hardware_in_loop.config import load_config


def test_load_example_config() -> None:
    cfg = load_config("configs/example.yaml")

    assert cfg.hardware.center_freq_hz == 3.1e9
    assert cfg.run.dry_run is True
    assert cfg.tx.target == "examples/tone_tx.py:generate"
