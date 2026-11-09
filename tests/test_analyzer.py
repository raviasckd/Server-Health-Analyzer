"""Unit tests for host metric collection, thresholds, and report generation."""

from __future__ import annotations

import json
from unittest.mock import Mock, mock_open, patch
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
        return_value=type("Memory", (), {
            "total": 16 * 1024**3,
            "used": 4 * 1024**3,
            "percent": 25.0,
        })(),
    )
    def test_memory_metrics_are_reported_in_gigabytes(self, _virtual_memory) -> None:
        result = self.analyzer.fetch_memory_metrics()

        self.assertEqual(result, {
            "total_gb": 16.0,
            "used_gb": 4.0,
            "percent_used": 25.0,
        })

    @patch.object(
        analyzer.psutil,
        "virtual_memory",
        return_value=type("Memory", (), {
            "total": 8 * 1024**3,
            "used": 7 * 1024**3,
            "percent": 87.5,
        })(),
    )
    @patch.object(analyzer.logging, "error")
    def test_custom_memory_threshold_controls_alert(self, error, _virtual_memory) -> None:
        monitor = analyzer.ServerHealthAnalyzer(memory_threshold=80)
        monitor.fetch_memory_metrics()
        error.assert_called_once()

    def test_thresholds_outside_percentage_range_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            analyzer.ServerHealthAnalyzer(cpu_threshold=101)
        with self.assertRaises(ValueError):
            analyzer.ServerHealthAnalyzer(memory_threshold=-1)

    def test_non_finite_thresholds_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            analyzer.ServerHealthAnalyzer(cpu_threshold=float("nan"))

    def test_report_is_written_as_valid_json(self) -> None:
        self.analyzer.fetch_cpu_metrics = Mock(
            return_value={"usage_percent": 10.0, "cores": 2}
        )
        self.analyzer.fetch_memory_metrics = Mock(
            return_value={"total_gb": 8.0, "used_gb": 2.0, "percent_used": 25.0}
        )
        file_mock = mock_open()

        with patch("builtins.open", file_mock), patch(
            "analyzer.time.time", return_value=1234.5
        ), patch("builtins.print"):
            self.analyzer.generate_report()

        file_mock.assert_called_once_with(
            "latest_health_report.json", "w", encoding="utf-8"
        )
        handle = file_mock()
        output = "".join(call.args[0] for call in handle.write.call_args_list)
        report = json.loads(output)

        self.assertEqual(report["timestamp"], 1234.5)
        self.assertEqual(report["server"], self.analyzer.node_name)
        self.assertEqual(report["cpu"]["cores"], 2)
        self.assertEqual(report["memory"]["percent_used"], 25.0)

    @patch("analyzer.time.sleep")
    @patch("analyzer.ServerHealthAnalyzer")
    @patch("builtins.print")
    def test_cli_passes_custom_thresholds_to_analyzer(
        self, _print, analyzer_class, _sleep
    ) -> None:
        self.assertEqual(
            analyzer.main(["--cpu-threshold", "70", "--memory-threshold", "82"]),
            0,
        )
        analyzer_class.assert_called_once_with(
            cpu_threshold=70.0,
            memory_threshold=82.0,
        )
        self.assertEqual(analyzer_class.return_value.generate_report.call_count, 3)

    def test_cli_rejects_threshold_above_one_hundred(self) -> None:
        with self.assertRaises(SystemExit) as error:
            analyzer.main(["--cpu-threshold", "101"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
