# Server Health Analyzer

A lightweight Python utility that collects basic host CPU and memory metrics and writes a JSON health report.

## Current capabilities

- Captures CPU utilisation and logical CPU count using `psutil`.
- Captures total memory, used memory, and percentage used.
- Applies configurable CPU warning and memory alert thresholds.
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

## Run

Use the default thresholds (CPU 85%, memory 90%):

```bash
python analyzer.py
```

Override either threshold from the command line:

```bash
python analyzer.py --cpu-threshold 75
python analyzer.py --cpu-threshold 80 --memory-threshold 88
```

Both threshold values must be between 0 and 100. Values above the configured threshold trigger the corresponding log alert. Defaults remain 85% for CPU and 90% for memory.

The current script performs three report cycles in the foreground, with a two-second pause between cycles. It is not a continuously running service.

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

## Development

Install the project dependency and run the unit tests:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Scope and limitations

The current implementation is synchronous and runs a finite three-cycle loop in the foreground. Disk I/O, network statistics, process-level metrics, configurable polling intervals, and long-running service scheduling are not currently implemented.

## License

MIT. See [LICENSE](LICENSE).
