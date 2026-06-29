"""Load analyzer I/Q captures."""

from __future__ import annotations

import logging
import tarfile
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


def load_iqtar(path: Path) -> tuple[NDArray[np.complex128], dict[str, Any]]:
    """Load an R&S .iq.tar capture as complex I/Q samples plus metadata."""

    try:
        return _load_via_rswaveform(path)
    except Exception:
        logger.info("RsWaveform could not load %s; using manual .iq.tar parser", path)
        return _load_manual(path)


def _load_via_rswaveform(path: Path) -> tuple[NDArray[np.complex128], dict[str, Any]]:
    from RsWaveform import IqTar

    iqtar = IqTar()
    iqtar.load(str(path))
    data = np.asarray(iqtar.data[0], dtype=np.complex128)
    raw_meta = iqtar.meta[0] if iqtar.meta else {}
    meta = {
        "sample_rate_hz": float(raw_meta.get("clock", 0.0)),
        "center_freq_hz": float(raw_meta.get("center_frequency", 0.0)),
        "loader": "RsWaveform",
    }
    return data, meta


def _load_manual(path: Path) -> tuple[NDArray[np.complex128], dict[str, Any]]:
    meta: dict[str, Any] = {"sample_rate_hz": 0.0, "center_freq_hz": 0.0, "loader": "manual"}
    iq_data: NDArray[np.complex128] | None = None

    with tarfile.open(str(path), "r") as tar:
        for member in tar.getmembers():
            if member.name.endswith(".complex.1ch.float32"):
                f = tar.extractfile(member)
                if f is None:
                    raise RuntimeError(f"Cannot read {member.name}")
                flat = np.frombuffer(f.read(), dtype=np.float32)
                iq_data = flat[0::2].astype(np.float64) + 1j * flat[1::2].astype(np.float64)
            elif member.name.endswith(".xml"):
                f = tar.extractfile(member)
                if f is not None:
                    import xml.etree.ElementTree as ET

                    root = ET.parse(f).getroot()
                    for elem in root.iter():
                        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        if tag == "Clock" and elem.text:
                            meta["sample_rate_hz"] = float(elem.text)
                        elif tag == "CenterFrequency" and elem.text:
                            meta["center_freq_hz"] = float(elem.text)

    if iq_data is None:
        raise RuntimeError(f"No .complex.1ch.float32 data found in {path}")
    return iq_data, meta
