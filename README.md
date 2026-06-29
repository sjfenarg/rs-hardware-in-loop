# HardwareInLoop

Reusable Hardware-in-the-Loop runner for arbitrary complex-baseband waveforms.

This repository separates the experiment into three parts:

```text
Your TX code  ->  HIL instruments  ->  Your RX code
```

The middle part handles the lab equipment:

- Write complex I/Q samples to an R&S `.wv` waveform file.
- Upload the waveform to an R&S SMW200A vector signal generator.
- Configure RF frequency, power, and ARB sample clock.
- Configure an R&S FSW IQ Analyzer capture.
- Download the `.iq.tar` capture.
- Load the captured I/Q back into NumPy.

Your transmitter and receiver stay independent from the instrument control code.

## Repository Layout

```text
HardwareInLoop/
  configs/
    example.yaml          # Complete dry-run and hardware-ready config
  examples/
    tone_tx.py            # Example TX: tone or chirp waveform
    spectrum_rx.py        # Example RX: power and dominant frequency metrics
    tx_template.py        # Minimal TX template to copy
    rx_template.py        # Minimal RX template to copy
  src/hardware_in_loop/
    cli.py                # hil-run entry point
    config.py             # YAML config dataclasses
    instruments.py        # SMW200A and FSW SCPI wrappers
    waveform.py           # NumPy I/Q -> R&S .wv
    capture.py            # R&S .iq.tar -> NumPy I/Q
    pipeline.py           # Generic TX -> HIL -> RX orchestration
    types.py              # TxWaveform, CaptureResult, RxResult contracts
  tests/
```

## Installation

From this directory:

```bash
uv venv
uv pip install -e ".[dev,hil]"
```

If you only want to run software dry-runs and unit tests, the hardware extra is optional:

```bash
uv pip install -e ".[dev]"
```

The `hil` extra installs:

- `pyvisa`
- `pyvisa-py`
- `RsWaveform`

## Quick Start Without Instruments

The example config uses `dry_run: true`, so it does not connect to hardware. It generates a tone, loops it back in software, and runs the example receiver.

```bash
uv run hil-run --config configs/example.yaml --dry-run
```

The run creates a folder under `runs/` with:

- `signal.wv` when `RsWaveform` is installed, or `signal.npy` as a dry-run fallback
- `tx_metadata.json`
- `rx_metrics.json`
- `summary.json`

## Running With Hardware

Edit `configs/example.yaml`:

```yaml
run:
  dry_run: false

hardware:
  center_freq_hz: 3.1e9
  power_dbm: -10.0
  timeout_ms: 60000

  signal_generator:
    visa: "TCPIP::169.254.2.20::INSTR"
    remote_waveform_path: "/var/user/signal.wv"

  analyzer:
    visa: "TCPIP::169.254.177.255::5025::SOCKET"
    remote_capture_path: "C:\\R_S\\Instr\\user\\capture.iq.tar"
    capture_multiplier: 2.0
    auto_level: true
```

Then run:

```bash
uv run hil-run --config configs/example.yaml
```

The runner uses the TX sample rate unless `hardware.sample_rate_hz` is set. The analyzer record length is:

- `hardware.analyzer.record_length`, when explicitly set.
- Otherwise `len(tx.samples) * hardware.analyzer.capture_multiplier`.

## Writing A Transmitter

A transmitter is a Python function or class method that returns `TxWaveform`.

Minimal function:

```python
from pathlib import Path

import numpy as np

from hardware_in_loop import TxWaveform


def generate(params: dict, run_dir: Path) -> TxWaveform:
    sample_rate_hz = float(params["sample_rate_hz"])
    duration_s = float(params.get("duration_s", 1e-3))
    tone_freq_hz = float(params.get("tone_freq_hz", 1e6))

    n = int(duration_s * sample_rate_hz)
    t = np.arange(n) / sample_rate_hz
    samples = 0.7 * np.exp(1j * 2 * np.pi * tone_freq_hz * t)

    return TxWaveform(
        samples=samples,
        sample_rate_hz=sample_rate_hz,
        name="my_tone",
        metadata={"tone_freq_hz": tone_freq_hz},
    )
```

The contract is:

- `samples`: 1-D complex NumPy array at complex baseband.
- `sample_rate_hz`: ARB clock and analyzer I/Q sample rate.
- `name`: human-readable waveform name for logs and metadata.
- `metadata`: any JSON-friendly information your RX may need later.

Point the YAML to your transmitter:

```yaml
tx:
  target: "path/to/my_tx.py:generate"
  params:
    sample_rate_hz: 50.0e6
    duration_s: 1.0e-3
    tone_freq_hz: 1.0e6
```

## Writing A Receiver

A receiver is a Python function or class method that receives the captured I/Q.

Minimal function:

```python
from hardware_in_loop import CaptureResult, HilContext, RxResult


def process(capture: CaptureResult, context: HilContext, params: dict) -> RxResult:
    samples = capture.samples

    metrics = {
        "num_samples": len(samples),
        "sample_rate_hz": capture.sample_rate_hz,
        "center_freq_hz": capture.center_freq_hz,
    }
    return RxResult(metrics=metrics)
```

The receiver receives:

- `capture.samples`: complex-baseband I/Q from the analyzer, or loopback samples in dry-run.
- `capture.sample_rate_hz`: analyzer sample rate.
- `capture.center_freq_hz`: RF center frequency used by the experiment.
- `context.tx`: the original `TxWaveform`.
- `context.run_dir`: run output folder for plots, arrays, decoded files, or logs.
- `params`: the dictionary under `rx.params` in YAML.

Point the YAML to your receiver:

```yaml
rx:
  target: "path/to/my_rx.py:process"
  params:
    expected_tone_hz: 1.0e6
```

## Target Syntax

Targets can be regular import paths:

```yaml
tx:
  target: "my_package.my_tx:generate"
```

Or direct file paths:

```yaml
tx:
  target: "experiments/my_tx.py:generate"
```

Nested objects are also supported:

```yaml
rx:
  target: "my_package.receivers:ReceiverClass.process"
```

For most users, a file path plus a function is the simplest option.

## Configuration Reference

```yaml
hardware:
  center_freq_hz: 3.1e9       # RF carrier frequency
  sample_rate_hz:             # Optional override; default is TX sample rate
  power_dbm: -10.0            # SMW output power
  timeout_ms: 60000           # VISA/SCPI timeout
  reset_on_connect: true      # Send *RST on connection

  signal_generator:
    visa: "TCPIP::..."
    remote_waveform_path: "/var/user/signal.wv"

  analyzer:
    visa: "TCPIP::...::5025::SOCKET"
    remote_capture_path: "C:\\R_S\\Instr\\user\\capture.iq.tar"
    record_length:            # Optional exact analyzer capture length
    capture_multiplier: 2.0   # Used when record_length is empty
    auto_level: true          # Run SENS:ADJ:LEV before capture

run:
  output_dir: "runs"
  tag: "experiment_name"
  dry_run: false
  keep_rf_on: false

tx:
  target: "examples/tone_tx.py:generate"
  params: {}

rx:
  target: "examples/spectrum_rx.py:process"
  params: {}
```

## Notes On Scaling To New Experiments

Keep each experiment-specific idea inside TX or RX code:

- Modulation, packet framing, preambles, pilots, coding, and payload generation belong in TX.
- Synchronization, demodulation, decoding, metrics, and plots belong in RX.
- Frequency, power, sample rate overrides, capture length, VISA addresses, and instrument paths belong in YAML.
- Instrument commands and file formats belong in `hardware_in_loop`.

This keeps the HIL layer stable while different people bring different waveforms.

## Instrument Communication Notes

This project currently includes a built-in backend for the following Rohde & Schwarz instruments:

- R&S SMW200A vector signal generator.
- R&S FSW family signal and spectrum analyzer, used through the IQ Analyzer application.

Communication is done with SCPI commands over VISA/TCPIP. Two common LAN resource styles are supported:

```text
TCPIP::192.168.1.10::INSTR
TCPIP::192.168.1.20::5025::SOCKET
```

The first form normally uses VISA LAN protocols such as VXI-11. The second form uses RawSocket SCPI, usually on port `5025`. RawSocket commands must be terminated with line feed (`\n`); the backend handles that for normal text commands.

### SMW200A Flow

The generator flow is:

```text
write .wv file locally
upload .wv to SMW mass memory with MMEM:DATA
select waveform in ARB with SOUR:BB:ARB:WAV:SEL
set ARB clock with SOUR:BB:ARB:CLOC
enable ARB with SOUR:BB:ARB:STAT ON
set RF frequency and power
enable RF output
```

The `.wv` file is generated with `RsWaveform`, using complex-baseband NumPy samples normalized into the valid waveform range. The `sample_rate_hz` from `TxWaveform` is used as the ARB clock unless `hardware.sample_rate_hz` overrides it.

### FSW Flow

The analyzer flow is:

```text
open IQ Analyzer mode
disable continuous sweep
set center frequency
set IQ sample rate with TRAC:IQ:SRAT
set record length with TRAC:IQ:RLEN
optionally run auto-level
trigger one capture
store capture as .iq.tar
download .iq.tar
load captured complex I/Q into NumPy
```

The downloaded `.iq.tar` file is parsed with `RsWaveform` when available, with a pure Python fallback parser for the standard float32 I/Q payload.

## Troubleshooting Hardware Runs

Start with a dry-run before connecting instruments:

```bash
uv run hil-run --config configs/example.yaml --dry-run
```

If dry-run works but hardware fails, use the points below.

### Cannot Connect To Instrument

Check the VISA resource string first:

```yaml
signal_generator:
  visa: "TCPIP::169.254.2.20::INSTR"

analyzer:
  visa: "TCPIP::169.254.177.255::5025::SOCKET"
```

Try both styles if the instrument supports them:

```text
TCPIP::IP_ADDRESS::INSTR
TCPIP::IP_ADDRESS::5025::SOCKET
```

Also verify:

- The PC and instrument are on the same network.
- The IP address is reachable with `ping`.
- VISA can query `*IDN?` using R&S VISA Tester, NI MAX, or a small PyVISA script.
- RawSocket resources use port `5025` and line-feed termination.

### Upload To SMW Hangs Or Fails

The waveform upload uses `MMEM:DATA` with an IEEE 488.2 definite-length binary block. If upload hangs:

- Confirm that `RsWaveform` generated a valid `.wv` file.
- Confirm that `remote_waveform_path` points to a writable path, for example `/var/user/signal.wv`.
- Try a shorter waveform to rule out timeout or memory limits.
- Increase `hardware.timeout_ms`.
- Check whether your specific connection expects a final line feed after binary uploads.
- Use the SMW SCPI recorder or remote trace to compare the expected upload and ARB selection sequence.

After upload, the backend selects and enables the waveform with:

```text
SOUR:BB:ARB:WAV:SEL '<remote_waveform_path>'
SOUR:BB:ARB:CLOC <sample_rate_hz>
SOUR:BB:ARB:STAT ON
SOUR:FREQ <center_freq_hz>
SOUR:POW <power_dbm>
OUTP:STAT ON
```

If the SMW reports that the waveform cannot be selected, check the file path, file format, sample rate limits, and installed ARB/baseband options.

### FSW Does Not Enter IQ Analyzer Mode

The backend currently uses:

```text
INST:SEL IQ
```

On some firmware/application states, the more explicit command may be required:

```text
INST:CRE IQ, 'IQ Analyzer';*WAI
```

If IQ mode selection fails, try this command manually on the analyzer. If it works, the backend can be adjusted for that instrument/firmware.

### FSW Capture Does Not Start Or Returns No Data

The backend configures the acquisition with:

```text
INIT:CONT OFF
SENS:FREQ:CENT <center_freq_hz>
TRAC:IQ:SRAT <sample_rate_hz>
TRAC:IQ:RLEN <record_length>
SENS:ADJ:LEV
INIT
```

If capture fails:

- Try `INIT:IMM` manually instead of `INIT`.
- Reduce `record_length`.
- Check that `sample_rate_hz` is within the available IQ Analyzer bandwidth/options.
- Set analyzer reference level manually if auto-level is unreliable.
- Check for overload warnings on the FSW display.
- Confirm the RF input connector and external attenuation setup.

For difficult cases, configure the FSW manually first, then use the SCPI recorder or context help to capture the exact commands for that firmware version.

### `.iq.tar` Download Or Parsing Fails

The backend stores and downloads the capture with:

```text
MMEM:STOR:IQ:STAT 1, '<remote_capture_path>'
MMEM:DATA? '<remote_capture_path>'
```

If this fails:

- Confirm that `remote_capture_path` is writable by the FSW, for example `C:\R_S\Instr\user\capture.iq.tar`.
- Try saving the capture manually from the FSW UI.
- Increase `hardware.timeout_ms`.
- Confirm that the downloaded file is not empty.
- Try loading the file manually with `hardware_in_loop.capture.load_iqtar`.

### Silent Failures Or Strange Instrument State

SCPI instruments can accept a command, queue an error, and continue. When debugging, query the error queue manually after each block:

```text
SYST:ERR?
```

Repeat until the instrument returns no error. This is especially useful after mode selection, waveform selection, sample-rate setup, and file operations.
