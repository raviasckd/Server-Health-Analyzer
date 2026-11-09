"""Collect host CPU and memory metrics and write a JSON health report."""

from __future__ import annotations

import argparse
import json
import logging
import math
import platform
import time

try:
    import psutil
except ImportError as exc:
    raise SystemExit(
        "Critical: 'psutil' module not found. Run 'python -m pip install -r requirements.txt'."
    ) from exc


logging.basicConfig(
    filename="system_health.log",
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
)


class ServerHealthAnalyzer:
    """Collect basic host metrics using configurable alert thresholds."""

    def __init__(
        self,
        cpu_threshold: float = 85.0,
        memory_threshold: float = 90.0,
    ) -> None:
        self.cpu_threshold = self._validate_threshold("CPU", cpu_threshold)
        self.memory_threshold = self._validate_threshold("memory", memory_threshold)
        self.os_info = platform.system()
        self.node_name = platform.node()
        logging.info(
            "Analyzer initialized on %s (%s); CPU threshold=%s%%, memory threshold=%s%%",
            self.node_name,
            self.os_info,
            self.cpu_threshold,
            self.memory_threshold,
        )

    @staticmethod
    def _validate_threshold(name: str, value: float) -> float:
        """Reject non-numeric, non-finite, or out-of-range thresholds."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} threshold must be a number between 0 and 100")
        if not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError(f"{name} threshold must be between 0 and 100")
        return float(value)

    def fetch_cpu_metrics(self) -> dict[str, float | int | None]:
        """Fetch CPU utilisation and logical core count."""
        usage = psutil.cpu_percent(interval=1)
        core_count = psutil.cpu_count(logical=True)
        if usage > self.cpu_threshold:
            logging.warning(
                "HIGH CPU USAGE DETECTED: %.1f%% (threshold: %.1f%%)",
                usage,
                self.cpu_threshold,
            )
        return {"usage_percent": usage, "cores": core_count}

    def fetch_memory_metrics(self) -> dict[str, float]:
        """Fetch memory usage in gigabytes and evaluate the alert threshold."""
        memory = psutil.virtual_memory()
        usage = memory.percent
        if usage > self.memory_threshold:
            logging.error(
                "CRITICAL MEMORY ALERT: %.1f%% used (threshold: %.1f%%)",
                usage,
                self.memory_threshold,
            )
        return {
            "total_gb": round(memory.total / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "percent_used": usage,
        }

    def generate_report(self) -> None:
        """Collect metrics and write the latest health report."""
        try:
            report = {
                "timestamp": time.time(),
                "server": self.node_name,
                "cpu": self.fetch_cpu_metrics(),
                "memory": self.fetch_memory_metrics(),
            }
            with open("latest_health_report.json", "w", encoding="utf-8") as report_file:
                json.dump(report, report_file, indent=4)
                report_file.write("\n")

            logging.info("Health report successfully generated and saved.")
            print(f"[{time.strftime('%X')}] Report generated successfully.")
        except (OSError, psutil.Error, TypeError, ValueError):
            logging.exception("Failed to generate health report.")


def _percentage_argument(value: str) -> float:
    """Parse a percentage value for argparse."""
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("threshold must be a number") from exc
    if not math.isfinite(number) or not 0 <= number <= 100:
        raise argparse.ArgumentTypeError("threshold must be between 0 and 100")
    return number


def main(argv: list[str] | None = None) -> int:
    """Run three monitoring cycles with optional alert thresholds."""
    parser = argparse.ArgumentParser(
        description="Collect host CPU and memory metrics and write a JSON report."
    )
    parser.add_argument(
        "--cpu-threshold",
        type=_percentage_argument,
        default=85.0,
        metavar="PERCENT",
        help="CPU warning threshold from 0 to 100 (default: 85)",
    )
    parser.add_argument(
        "--memory-threshold",
        type=_percentage_argument,
        default=90.0,
        metavar="PERCENT",
        help="memory alert threshold from 0 to 100 (default: 90)",
    )
    args = parser.parse_args(argv)

    analyzer = ServerHealthAnalyzer(
        cpu_threshold=args.cpu_threshold,
        memory_threshold=args.memory_threshold,
    )
    print("Starting Server Health Analyzer...")
    for cycle in range(3):
        analyzer.generate_report()
        if cycle < 2:
            time.sleep(2)
    print("Execution completed. Check system_health.log for details.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
