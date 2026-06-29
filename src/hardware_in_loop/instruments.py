"""SCPI instrument wrappers for the R&S SMW200A and FSW family."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def open_scpi_resource(address: str, timeout_ms: int = 60000, *, reset: bool = True) -> Any:
    """Open a PyVISA resource, falling back to raw SCPI-over-TCP for SOCKET addresses."""

    import pyvisa

    try:
        rm = pyvisa.ResourceManager("@py")
        inst = rm.open_resource(address, open_timeout=timeout_ms)
        inst.timeout = timeout_ms
        if "SOCKET" in address.upper():
            inst.read_termination = "\n"
            inst.write_termination = "\n"
    except Exception:
        logger.warning("PyVISA open failed for %s; trying raw SCPI socket", address)
        inst = RawScpiSocket.from_visa_string(address, timeout_ms)

    if reset:
        inst.write("*CLS")
        inst.write("*RST")
        inst.query("*OPC?")

    idn = inst.query("*IDN?").strip()
    logger.info("Connected to %s", idn)
    return inst


class RawScpiSocket:
    """Minimal SCPI-over-TCP resource with the subset used by this project."""

    def __init__(self, host: str, port: int = 5025, timeout_ms: int = 60000) -> None:
        import socket

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(timeout_ms / 1000.0)
        self._sock.connect((host, port))
        self.timeout = timeout_ms

    @classmethod
    def from_visa_string(cls, address: str, timeout_ms: int = 60000) -> "RawScpiSocket":
        parts = address.split("::")
        host = parts[1]
        port = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 5025
        return cls(host, port, timeout_ms)

    def write(self, cmd: str) -> None:
        self._sock.sendall((cmd + "\n").encode("ascii"))

    def write_raw(self, data: bytes) -> None:
        self._sock.sendall(data)

    def query(self, cmd: str) -> str:
        self.write(cmd)
        return self._read_until().decode("ascii", errors="replace")

    def query_binary_values(self, cmd: str, datatype: str = "B", container=bytes) -> bytes:
        self.write(cmd)
        while True:
            ch = self._sock.recv(1)
            if not ch:
                raise ConnectionError("Socket closed before binary block delimiter")
            if ch == b"#":
                break

        num_digits = int(self._recv_exactly(1))
        data_len = int(self._recv_exactly(num_digits))
        data = self._recv_exactly(data_len)

        try:
            self._sock.settimeout(0.5)
            self._sock.recv(1)
        except Exception:
            pass
        finally:
            self._sock.settimeout(self.timeout / 1000.0)

        return data

    def _read_until(self, term: bytes = b"\n") -> bytes:
        buf = bytearray()
        while True:
            ch = self._sock.recv(1)
            if not ch:
                break
            buf.extend(ch)
            if buf.endswith(term):
                break
        return bytes(buf)

    def _recv_exactly(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError(f"Socket closed after {len(buf)}/{n} bytes")
            buf.extend(chunk)
        return bytes(buf)

    def close(self) -> None:
        self._sock.close()


class Smw200aSignalGenerator:
    """Upload an R&S .wv file and configure an SMW200A ARB RF output."""

    def __init__(self, visa_address: str, timeout_ms: int = 60000, *, reset: bool = True) -> None:
        self._inst = open_scpi_resource(visa_address, timeout_ms, reset=reset)

    def upload_waveform(self, local_path: Path, remote_path: str = "/var/user/signal.wv") -> None:
        data = local_path.read_bytes()
        size = str(len(data))
        header = f"MMEM:DATA '{remote_path}',#{len(size)}{size}"
        logger.info("Uploading %s to SMW path %s", local_path, remote_path)
        self._inst.write_raw(header.encode("ascii") + data)
        self._inst.query("*OPC?")

    def configure(
        self,
        *,
        remote_waveform_path: str,
        center_freq_hz: float,
        power_dbm: float,
        sample_rate_hz: float,
    ) -> None:
        commands = [
            f"SOUR:BB:ARB:WAV:SEL '{remote_waveform_path}'",
            f"SOUR:BB:ARB:CLOC {sample_rate_hz:.0f}",
            "SOUR:BB:ARB:STAT ON",
            f"SOUR:FREQ {center_freq_hz:.0f}",
            f"SOUR:POW {power_dbm:.2f}",
        ]
        for cmd in commands:
            self._inst.write(cmd)
            self._inst.query("*OPC?")

    def rf_on(self) -> None:
        self._inst.write("OUTP:STAT ON")
        self._inst.query("*OPC?")

    def rf_off(self) -> None:
        self._inst.write("OUTP:STAT OFF")
        self._inst.query("*OPC?")

    def close(self) -> None:
        self._inst.close()


class FswIqAnalyzer:
    """Configure an R&S FSW IQ Analyzer capture and download the .iq.tar file."""

    def __init__(self, visa_address: str, timeout_ms: int = 60000, *, reset: bool = True) -> None:
        self._inst = open_scpi_resource(visa_address, timeout_ms, reset=reset)

    def configure(
        self,
        *,
        center_freq_hz: float,
        sample_rate_hz: float,
        record_length: int,
    ) -> None:
        commands = [
            "INST:SEL IQ",
            "SYST:DISP:UPD OFF",
            "INIT:CONT OFF",
            f"SENS:FREQ:CENT {center_freq_hz:.0f}",
            f"TRAC:IQ:SRAT {sample_rate_hz:.0f}",
            f"TRAC:IQ:RLEN {record_length}",
        ]
        for cmd in commands:
            self._inst.write(cmd)
            self._inst.query("*OPC?")

    def auto_level(self) -> None:
        self._inst.write("SENS:ADJ:LEV")
        self._inst.query("*OPC?")

    def capture(self) -> None:
        self._inst.write("INIT")
        self._inst.query("*OPC?")

    def download_iqtar(
        self,
        local_path: Path,
        remote_path: str = r"C:\R_S\Instr\user\capture.iq.tar",
    ) -> None:
        self._inst.write(f"MMEM:STOR:IQ:STAT 1, '{remote_path}'")
        self._inst.query("*OPC?")

        previous_timeout = self._inst.timeout
        self._inst.timeout = max(previous_timeout, 60000)
        try:
            raw = self._inst.query_binary_values(
                f"MMEM:DATA? '{remote_path}'",
                datatype="B",
                container=bytes,
            )
        finally:
            self._inst.timeout = previous_timeout

        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(raw)

    def close(self) -> None:
        self._inst.close()
