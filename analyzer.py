"""Collect host metrics and write atomic JSON health reports."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
from pathlib import Path
import platform
import tempfile
import time
from logging.handlers import RotatingFileHandler

try:
    import psutil
except ImportError as exc:
    raise SystemExit(
        "Critical: 'psutil' module not found. Run 'python -m pip install -r requirements.txt'."
    ) from exc


logging.basicConfig(
    handlers=[
        RotatingFileHandler(
            "system_health.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    ],
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
)


class ServerHealthAnalyzer:
    """Collect host resource metrics with configurable alert thresholds."""

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
            "Analyzer initialized on %s (%s); CPU threshold=%.1f%%, "
            "memory threshold=%.1f%%",
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

    @staticmethod
    def fetch_disk_metrics(path: str | Path | None = None) -> dict[str, float]:
        """Return usage for the filesystem containing path (current directory by default)."""
        target = Path(path) if path is not None else Path.cwd()
        usage = psutil.disk_usage(str(target))
        return {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": usage.percent,
        }

    @staticmethod
    def fetch_disk_io_metrics() -> dict[str, int] | None:
        """Return aggregate disk I/O counters, or None if the platform exposes none."""
        counters = psutil.disk_io_counters()
        if counters is None:
            return None
        return {
            "read_bytes": counters.read_bytes,
            "write_bytes": counters.write_bytes,
            "read_count": counters.read_count,
            "write_count": counters.write_count,
        }

    @staticmethod
    def fetch_network_metrics() -> dict[str, int] | None:
        """Return cumulative network interface counters since system boot."""
        counters = psutil.net_io_counters()
        if counters is None:
            return None
        return {
            "bytes_sent": counters.bytes_sent,
            "bytes_received": counters.bytes_recv,
            "packets_sent": counters.packets_sent,
            "packets_received": counters.packets_recv,
        }

    @staticmethod
    def write_report_atomic(report: dict[str, object], output_path: str | Path) -> None:
        """Write JSON to a same-directory temporary file, then atomically replace output."""
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(report, temporary_file, indent=4, sort_keys=True)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.replace(temporary_path, destination)
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass

    def generate_report(
        self,
        output_path: str | Path = "latest_health_report.json",
    ) -> dict[str, object]:
        """Collect host metrics and persist a complete report atomically."""
        report: dict[str, object] = {
            "timestamp": time.time(),
            "server": self.node_name,
            "os": self.os_info,
            "cpu": self.fetch_cpu_metrics(),
            "memory": self.fetch_memory_metrics(),
            "disk": self.fetch_disk_metrics(),
            "disk_io": self.fetch_disk_io_metrics(),
            "network": self.fetch_network_metrics(),
        }
        self.write_report_atomic(report, output_path)
        logging.info("Health report successfully generated: %s", output_path)
        print(f"[{time.strftime('%X')}] Report generated successfully.")
        return report

    async def run_monitoring(
        self,
        interval: float = 2.0,
        cycles: int = 3,
        output_path: str | Path = "latest_health_report.json",
    ) -> None:
        """Run monitoring cycles without blocking the asyncio event loop.

        Set cycles to zero to continue until the process is interrupted.
        Blocking psutil sampling and filesystem work run in a worker thread.
        """
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("interval must be a finite number greater than zero")
        if isinstance(cycles, bool) or not isinstance(cycles, int) or cycles < 0:
            raise ValueError("cycles must be a non-negative integer")

        completed = 0
        while cycles == 0 or completed < cycles:
            await asyncio.to_thread(self.generate_report, output_path)
            completed += 1
            if cycles == 0 or completed < cycles:
                await asyncio.sleep(interval)


def _percentage_argument(value: str) -> float:
    """Parse a percentage value for argparse."""
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("threshold must be a number") from exc
    if not math.isfinite(number) or not 0 <= number <= 100:
        raise argparse.ArgumentTypeError("threshold must be between 0 and 100")
    return number


def _positive_float_argument(value: str) -> float:
    """Parse a strictly positive finite interval."""
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("interval must be a number") from exc
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("interval must be greater than zero")
    return number


def _non_negative_int_argument(value: str) -> int:
    """Parse a non-negative monitoring cycle count."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("cycles must be an integer") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("cycles cannot be negative")
    return number


def main(argv: list[str] | None = None) -> int:
    """Run the monitor with configurable thresholds and scheduling."""
    parser = argparse.ArgumentParser(
        description="Collect host CPU, memory, disk, and network metrics."
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
    parser.add_argument(
        "--interval",
        type=_positive_float_argument,
        default=2.0,
        metavar="SECONDS",
        help="delay between report cycles (default: 2)",
    )
    parser.add_argument(
        "--cycles",
        type=_non_negative_int_argument,
        default=3,
        metavar="COUNT",
        help="number of report cycles; use 0 to run until interrupted (default: 3)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("latest_health_report.json"),
        help="JSON report destination (default: latest_health_report.json)",
    )
    args = parser.parse_args(argv)

    monitor = ServerHealthAnalyzer(
        cpu_threshold=args.cpu_threshold,
        memory_threshold=args.memory_threshold,
    )
    print("Starting Server Health Analyzer...")
    try:
        asyncio.run(
            monitor.run_monitoring(
                interval=args.interval,
                cycles=args.cycles,
                output_path=args.output,
            )
        )
    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user.")
        print("\nMonitoring stopped.")
        return 130
    except (OSError, psutil.Error, ValueError):
        logging.exception("Monitoring stopped after an error.")
        return 1

    print("Execution completed. Check the log file for details.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
