from __future__ import annotations


class AnomalyDetector:
    def inspect(self, metrics: dict[str, float], performance_summary: dict[str, float], execution) -> list[str]:
        anomalies: list[str] = []
        if metrics.get("memory_percent", 0.0) >= 90.0:
            anomalies.append("high_memory_usage")
        if metrics.get("cpu_percent", 0.0) >= 95.0:
            anomalies.append("high_cpu_usage")
        if performance_summary.get("avg_duration_ms", 0.0) >= 5000.0:
            anomalies.append("slow_average_runtime")
        if not execution.success:
            anomalies.append("execution_failure")
        return anomalies
