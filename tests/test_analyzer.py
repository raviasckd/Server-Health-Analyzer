"""Unit tests for host metric collection and report generation."""

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
    def test_high_cpu_usage_emits_warning(self, warning, _cpu_count, _cpu_percent) -> None:
        self.analyzer.fetch_cpu_metrics()
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

    def test_report_is_written_as_valid_json(self) -> None:
        self.analyzer.fetch_cpu_metrics = Mock(
            return_value={"usage_percent": 10.0, "cores": 2}
        )
        self.analyzer.fetch_memory_metrics = Mock(
            return_value={"total_gb": 8.0, "used_gb": 2.0, "percent_used": 25.0}
        )
        file_mock = mock_open()

        with patch("builtins.open", file_mock), patch("analyzer.time.time", return_value=1234.5), patch(
            "builtins.print"
        ):
            self.analyzer.generate_report()

        file_mock.assert_called_once_with("latest_health_report.json", "w")
        handle = file_mock()
        output = "".join(call.args[0] for call in handle.write.call_args_list)
        report = json.loads(output)

        self.assertEqual(report["timestamp"], 1234.5)
        self.assertEqual(report["server"], self.analyzer.node_name)
        self.assertEqual(report["cpu"]["cores"], 2)
        self.assertEqual(report["memory"]["percent_used"], 25.0)


if __name__ == "__main__":
    unittest.main()
