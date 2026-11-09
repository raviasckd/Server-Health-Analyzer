# Server Health Analyzer

A lightweight Python utility that collects basic host CPU and memory metrics and writes a JSON health report.

## Current capabilities

- Captures CPU utilisation and logical CPU count using `psutil`.
- Captures total memory, used memory, and percentage used.
- Logs high CPU and memory utilisation according to fixed thresholds.
- Writes the latest report to `latest_health_report.json`.
- Writes operational messages to `system_health.log`.

## Requirements

- Python 3.10 or newer
- `psutil` (see `requirements.txt`)

## Setup

Clone the repository and install its dependency:

```bash
git clone https://github.com/raviasckd/Server-Health-Analyzer.git
cd Server-Health-Analyzer
python -m pip install -r requirements.txt
```

Run the analyzer:

```bash
python analyzer.py
```

The current script performs three report cycles and exits. Each cycle measures CPU utilisation, collects memory metrics, and overwrites `latest_health_report.json`. The log file is also created in the current working directory.

## Example report

```json
{
  "timestamp": 1794211200.0,
  "server": "example-host",
  "cpu": {
    "usage_percent": 12.5,
    "cores": 8
  },
  "memory": {
    "total_gb": 31.25,
    "used_gb": 9.5,
    "percent_used": 30.4
  }
}
```

The values above are illustrative; actual values depend on the host being monitored.

## Thresholds

The current implementation logs a CPU warning when utilisation exceeds 85% and a memory error when utilisation exceeds 90%. These thresholds are fixed in `analyzer.py`.

## Development

Install the project dependency and run the unit tests:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Scope and limitations

The current implementation is synchronous and runs a finite three-cycle loop in the foreground. It is not yet an asynchronous daemon or a service manager integration. Disk I/O, network statistics, process-level metrics, configurable thresholds, and long-running scheduling are not currently implemented.

## License

MIT. See [LICENSE](LICENSE).
