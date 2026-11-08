# 🖥️ Server-Health-Analyzer (SHA)
![Build Status](https://img.shields.io/badge/build-passing-brightgreen) ![Version](https://img.shields.io/badge/version-v1.2.0-blue) ![License](https://img.shields.io/badge/license-MIT-green)

An enterprise-grade, asynchronous monitoring daemon designed to track server resources, analyze performance bottlenecks, and generate automated health reports. 

## 🚀 Why this project?
In large-scale microservice architectures, keeping track of node health is critical. **Server-Health-Analyzer** acts as a lightweight daemon that continuously runs in the background, logging vital statistics (CPU spikes, memory leaks, disk I/O) without consuming high system resources itself.

## ⚙️ Architecture & Features
- **Asynchronous Execution:** Utilizes Python's `asyncio` for non-blocking resource polling.
- **Data Serialization:** Exports health metrics in structured JSON formats for easy integration with dashboards like Grafana or ELK stack.
- **Extensible Logging:** Built-in rotating file handlers to prevent log bloating.

## 🛠️ Installation & Setup
```bash
# Clone the repository
git clone [https://github.com/raviasckd/Server-Health-Analyzer.git](https://github.com/raviasckd/Server-Health-Analyzer.git)

# Navigate to the directory
cd Server-Health-Analyzer

# Install required dependencies
pip install -r requirements.txt

# Run the analyzer daemon
python analyzer.py# Server-Health-Analyzer
An enterprise-grade, asynchronous monitoring daemon to track server resources, performance bottlenecks, and generate automated health reports.
