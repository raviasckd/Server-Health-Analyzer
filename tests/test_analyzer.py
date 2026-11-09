"""Unit tests for metrics, thresholds, atomic writes, and async scheduling."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import unittest

import analyzer


class ServerHealthAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = analyzer.ServerHealthAnalyzer()

    @patch.object(analyzer.psutil, "cpu_percent", return_value=42.5)
    @patch.object(analyzer.psutil, "cpu_count", return_value=8)
    def test_cpu_metrics_include_usage_and_logical_cores(self, cpu_count, cpu_percent) -> None:
        result = self.analyzer.fetch_cpu_metrics()
        self.assertEqual(result, {"usage_percent": 42.5, "cores": 8})
        cpu_percent.assert_called_once_with(interval=1)
        cpu_count.assert_called_once_with(logical=True)

    @patch.object(analyzer.psutil, "cpu_percent", return_value=90.0)
    @patch.object(analyzer.psutil, "cpu_count", return_value=4)
    @patch.object(analyzer.logging, "warning")
    def test_default_cpu_threshold_emits_warning(self, warning, _cpu_count, _cpu_percent) -> None:
        self.analyzer.fetch_cpu_metrics()
        warning.assert_called_once()

    @patch.object(analyzer.psutil, "cpu_percent", return_value=78.0)
    @patch.object(analyzer.psutil, "cpu_count", return_value=4)
    @patch.object(analyzer.logging, "warning")
    def test_custom_cpu_threshold_controls_warning(
        self, warning, _cpu_count, _cpu_percent
    ) -> None:
        monitor = analyzer.ServerHealthAnalyzer(cpu_threshold=75)
        monitor.fetch_cpu_metrics()
        warning.assert_called_once()

    @patch.object(
        analyzer.psutil,
        "virtual_memory",
        return_value=SimpleNamespace(
            total=16 * 1024**3, used=4 * 1024**3, percent=25.0
        ),
    )
    def test_memory_metrics_are_reported_in_gigabytes(self, _virtual_memory) -> None:
        result = self.analyzer.fetch_memory_metrics()
        self.assertEqual(result, {
            "total_gb": 16.0, "used_gb": 4.0, "percent_used": 25.0,
        })

    @patch.object(
        analyzer.psutil,
        "virtual_memory",
        return_value=SimpleNamespace(
            total=8 * 1024**3, used=7 * 1024**3, percent=87.5
        ),
    )
    @patch.object(analyzer.logging, "error")
    def test_custom_memory_threshold_controls_alert(self, error, _virtual_memory) -> None:
        monitor = analyzer.ServerHealthAnalyzer(memory_threshold=80)
        monitor.fetch_memory_metrics()
        error.assert_called_once()

    def test_thresholds_reject_invalid_values(self) -> None:
        for value in (-1, 101, float("nan"), float("inf"), True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    analyzer.ServerHealthAnalyzer(cpu_threshold=value)

    @patch.object(
        analyzer.psutil,
        "disk_usage",
        return_value=SimpleNamespace(
            total=100 * 1024**3,
            used=60 * 1024**3,
            free=40 * 1024**3,
            percent=60.0,
        ),
    )
    def test_disk_metrics_report_capacity_and_free_space(self, disk_usage) -> None:
        result = self.analyzer.fetch_disk_metrics("/var")
        self.assertEqual(result, {
            "total_gb": 100.0,
            "used_gb": 60.0,
            "free_gb": 40.0,
            "percent_used": 60.0,
        })
        disk_usage.assert_called_once_with("/var")

    @patch.object(
        analyzer.psutil,
        "disk_io_counters",
        return_value=SimpleNamespace(
            read_bytes=1000, write_bytes=2000, read_count=10, write_count=20
        ),
    )
    def test_disk_io_counters_are_returned(self, _disk_io) -> None:
        self.assertEqual(self.analyzer.fetch_disk_io_metrics(), {
            "read_bytes": 1000,
            "write_bytes": 2000,
            "read_count": 10,
            "write_count": 20,
        })

    @patch.object(
        analyzer.psutil,
        "net_io_counters",
        return_value=SimpleNamespace(
            bytes_sent=100, bytes_recv=200, packets_sent=3, packets_recv=4
        ),
    )
    def test_network_counters_are_returned(self, _net_io) -> None:
        self.assertEqual(self.analyzer.fetch_network_metrics(), {
            "bytes_sent": 100,
            "bytes_received": 200,
            "packets_sent": 3,
            "packets_received": 4,
        })

    @patch.object(analyzer.psutil, "disk_io_counters", return_value=None)
    @patch.object(analyzer.psutil, "net_io_counters", return_value=None)
    def test_optional_counters_can_be_unavailable(self, _network, _disk) -> None:
        self.assertIsNone(self.analyzer.fetch_disk_io_metrics())
        self.assertIsNone(self.analyzer.fetch_network_metrics())

    def test_atomic_writer_replaces_destination_with_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "reports" / "health.json"
            analyzer.ServerHealthAnalyzer.write_report_atomic(
                {"status": "healthy", "cpu": {"usage_percent": 12.5}},
                destination,
            )
            payload = json.loads(destination.read_text(encoding="utf-8"))
            leftovers = list(destination.parent.glob("*.tmp"))

        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["cpu"]["usage_percent"], 12.5)
        self.assertEqual(leftovers, [])

    def test_atomic_writer_preserves_previous_file_on_serialization_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "health.json"
            destination.write_text("previous report", encoding="utf-8")

            with patch("analyzer.json.dump", side_effect=TypeError("not serializable")):
                with self.assertRaises(TypeError):
                    analyzer.ServerHealthAnalyzer.write_report_atomic(
                        {"invalid": object()}, destination
                    )

            self.assertEqual(destination.read_text(encoding="utf-8"), "previous report")
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    @patch("builtins.print")
    def test_generate_report_includes_all_metric_groups(self, _print) -> None:
        self.analyzer.fetch_cpu_metrics = Mock(return_value={"usage_percent": 10.0, "cores": 2})
        self.analyzer.fetch_memory_metrics = Mock(
            return_value={"total_gb": 8.0, "used_gb": 2.0, "percent_used": 25.0}
        )
        self.analyzer.fetch_disk_metrics = Mock(
            return_value={"total_gb": 100.0, "used_gb": 40.0, "free_gb": 60.0, "percent_used": 40.0}
        )
        self.analyzer.fetch_disk_io_metrics = Mock(return_value={"read_bytes": 10, "write_bytes": 20,
                                                                 "read_count": 1, "write_count": 2})
        self.analyzer.fetch_network_metrics = Mock(
            return_value={"bytes_sent": 3, "bytes_received": 4,
                          "packets_sent": 1, "packets_received": 2}
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "health.json"
            with patch("analyzer.time.time", return_value=1234.5):
                report = self.analyzer.generate_report(output)
            saved = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(report, saved)
        self.assertEqual(report["timestamp"], 1234.5)
        self.assertEqual(report["server"], self.analyzer.node_name)
        self.assertEqual(report["disk"]["free_gb"], 60.0)
        self.assertEqual(report["network"]["bytes_received"], 4)


class AsyncMonitoringTests(unittest.IsolatedAsyncioTestCase):
    async def test_monitor_runs_requested_number_of_cycles(self) -> None:
        monitor = analyzer.ServerHealthAnalyzer()
        with patch("analyzer.asyncio.to_thread", new_callable=AsyncMock) as worker, patch(
            "analyzer.asyncio.sleep", new_callable=AsyncMock
        ) as sleep:
            await monitor.run_monitoring(interval=0.25, cycles=3, output_path="report.json")

        self.assertEqual(worker.await_count, 3)
        self.assertEqual(sleep.await_count, 2)
        worker.assert_awaited_with(monitor.generate_report, "report.json")
        sleep.assert_awaited_with(0.25)

    async def test_invalid_monitoring_schedule_is_rejected(self) -> None:
        monitor = analyzer.ServerHealthAnalyzer()
        with self.assertRaises(ValueError):
            await monitor.run_monitoring(interval=0, cycles=1)
        with self.assertRaises(ValueError):
            await monitor.run_monitoring(interval=1, cycles=-1)


class CliArgumentTests(unittest.TestCase):
    def test_interval_argument_must_be_positive(self) -> None:
        self.assertEqual(analyzer._positive_float_argument("0.5"), 0.5)
        with self.assertRaises(Exception):
            analyzer._positive_float_argument("0")

    def test_cycle_argument_accepts_zero_for_continuous_mode(self) -> None:
        self.assertEqual(analyzer._non_negative_int_argument("0"), 0)
        with self.assertRaises(Exception):
            analyzer._non_negative_int_argument("-1")


if __name__ == "__main__":
    unittest.main()
