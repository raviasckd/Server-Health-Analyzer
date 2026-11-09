# Server Health Analyzer

A Python host-monitoring utility for collecting CPU, memory, disk, and network metrics and writing structured JSON health reports.

## Features

- CPU utilisation and logical core count, with configurable warning threshold.
- Memory usage in gigabytes, with configurable alert threshold.
- Filesystem capacity and free-space metrics for the filesystem containing the current working directory.
- Aggregate disk I/O and network I/O counters where the operating system exposes them.
- Atomic JSON report replacement to avoid leaving a partially written report.
- Rotating application logs (5 MiB per file, three backups).
- Asynchronous monitoring orchestration; blocking system sampling and file I/O run in a worker thread.
- Finite execution by default, or continuous foreground monitoring until interrupted.

## Requirements

- Python 3.10 or newer
- psutil (see requirements.txt)

## Setup

```bash
git clone https://github.com/raviasckd/Server-Health-Analyzer.git
cd Server-Health-Analyzer
python -m pip install -r requirements.txt
```

## Usage

Run three report cycles with the default settings (CPU 85%, memory 90%, two-second interval):

```bash
python analyzer.py
```

Set custom thresholds and interval:

```bash
python analyzer.py --cpu-threshold 75 --memory-threshold 85 --interval 5
```

Run continuously until Ctrl+C:

```bash
python analyzer.py --cycles 0 --interval 10
```

Choose a different report destination:

```bash
python analyzer.py --output reports/health.json
```

Use `python analyzer.py --help` to see all options. Thresholds must be between 0 and 100; interval must be greater than zero; cycles must be non-negative. A cycle count of zero means continuous foreground monitoring.

## Report structure

Each report contains:

- `timestamp`: Unix timestamp when collection started.
- `server` and `os`: host identity.
- `cpu` and `memory`: utilisation metrics.
- `disk`: filesystem capacity and free space for the current working directory's filesystem.
- `disk_io`: cumulative aggregate read/write counters, or null when unavailable.
- `network`: cumulative network byte/packet counters since boot, or null when unavailable.

Disk and network I/O values are cumulative counters, not per-second rates. The current report does not calculate throughput deltas.

## Logging and report safety

Operational logs are written to `system_health.log` and rotated at 5 MiB, retaining three backups. JSON reports are written to a temporary file in the destination directory, flushed, and atomically moved into place. This protects the last complete report if serialization or a write fails before replacement.

## Development

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q analyzer.py tests
```

GitHub Actions runs the unit suite and CLI checks on Python 3.10, 3.11, and 3.12.

## Scope and limitations

This tool runs in the foreground; it does not install itself as a Windows service or Linux systemd unit. Asynchronous orchestration keeps the event loop responsive, while psutil's blocking sampling calls execute in a worker thread. Disk metrics describe the filesystem containing the selected working directory. Some platforms may not expose aggregate disk I/O counters.

This is a lightweight host diagnostics utility, not a centralised monitoring platform or an automated remediation system.

## License

MIT. See LICENSE.
