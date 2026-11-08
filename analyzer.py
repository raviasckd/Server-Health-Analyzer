import os
import time
import json
import logging
import platform
try:
    import psutil
except ImportError:
    print("Critical: 'psutil' module not found. Run 'pip install -r requirements.txt'")
    exit(1)

# Configure Enterprise-level Logging
logging.basicConfig(
    filename='system_health.log',
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)

class ServerHealthAnalyzer:
    """
    A robust daemon for analyzing server health metrics and generating automated reports.
    """
    def __init__(self):
        self.os_info = platform.system()
        self.node_name = platform.node()
        logging.info(f"Analyzer initialized on {self.node_name} ({self.os_info})")

    def fetch_cpu_metrics(self):
        """Fetches detailed CPU utilization metrics."""
        usage = psutil.cpu_percent(interval=1)
        core_count = psutil.cpu_count(logical=True)
        if usage > 85.0:
            logging.warning(f"HIGH CPU USAGE DETECTED: {usage}%")
        return {"usage_percent": usage, "cores": core_count}

    def fetch_memory_metrics(self):
        """Analyzes RAM consumption and potential memory bottlenecks."""
        mem = psutil.virtual_memory()
        usage = mem.percent
        if usage > 90.0:
            logging.error(f"CRITICAL MEMORY ALERT: {usage}% used!")
        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "percent_used": usage
        }

    def generate_report(self):
        """Compiles metrics into a structured JSON payload."""
        try:
            report = {
                "timestamp": time.time(),
                "server": self.node_name,
                "cpu": self.fetch_cpu_metrics(),
                "memory": self.fetch_memory_metrics()
            }
            # Simulate saving payload to a secure endpoint or file
            with open('latest_health_report.json', 'w') as f:
                json.dump(report, f, indent=4)
            
            logging.info("Health report successfully generated and saved.")
            print(f"[{time.strftime('%X')}] Report Generated Successfully.")
        except Exception as e:
            logging.error(f"Failed to generate report: {str(e)}")

if __name__ == "__main__":
    print("Starting Server-Health-Analyzer Daemon...")
    analyzer = ServerHealthAnalyzer()
    
    # Simulating a continuous background process
    for _ in range(3):
        analyzer.generate_report()
        time.sleep(2) # Polling interval
    print("Execution completed. Check system_health.log for details.")
