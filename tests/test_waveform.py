from __future__ import annotations

import numpy as np
import pytest

from hardware_in_loop.waveform import normalize_iq


def test_normalize_iq_scales_largest_component_to_one() -> None:
    samples = np.array([2 + 0.5j, -1 + 4j], dtype=np.complex128)

    normalized = normalize_iq(samples)

    assert normalized.dtype == np.complex64
    assert np.max(np.abs(normalized.real)) <= 1.0
    assert np.max(np.abs(normalized.imag)) == pytest.approx(1.0)


def test_normalize_iq_rejects_empty_waveform() -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_iq(np.array([], dtype=np.complex128))
