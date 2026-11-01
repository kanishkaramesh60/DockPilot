
"""
DockPilot - Predictive Container Failure Detection

Uses historical Docker CPU and memory percentages.
This is a rule-based early-warning system, not a
guarantee that a container will fail.
"""

MIN_SAMPLES = 3

MEMORY_CRITICAL_PERCENT = 85
CPU_HIGH_PERCENT = 85
MEMORY_GROWTH_THRESHOLD = 10


def analyze_container_history(container_name, history):
    """Analyze historical metrics for one container."""

    samples = sorted(
        history,
        key=lambda item: item.get("id", 0)
    )

    if len(samples) < MIN_SAMPLES:
        return {
            "container": container_name,
            "risk_level": "Insufficient Data",
            "risk_score": 0,
            "sample_count": len(samples),
            "findings": [
                "Collect at least 3 metric samples for analysis."
            ],
            "recommendations": [
                "Open the predictive analysis endpoint again "
                "after collecting more monitoring samples."
            ],
        }

    memory_values = [
        float(item.get("memory_percent") or 0)
        for item in samples
    ]

    cpu_values = [
        float(item.get("cpu_percent") or 0)
        for item in samples
    ]

    latest_memory = memory_values[-1]
    latest_cpu = cpu_values[-1]

    recent_memory = memory_values[-3:]
    recent_cpu = cpu_values[-3:]

    score = 0
    findings = []
    recommendations = []

    # Check current memory pressure.
    if latest_memory >= MEMORY_CRITICAL_PERCENT:
        score += 40
        findings.append(
            f"Memory usage is critically high at "
            f"{latest_memory:.2f}%."
        )
        recommendations.append(
            "Inspect memory-intensive processes and consider "
            "optimizing the application or increasing its "
            "memory limit if appropriate."
        )

    # Check whether memory is consistently increasing.
    memory_increasing = all(
        recent_memory[index] < recent_memory[index + 1]
        for index in range(len(recent_memory) - 1)
    )

    memory_growth = recent_memory[-1] - recent_memory[0]

    if (
        memory_increasing
        and memory_growth >= MEMORY_GROWTH_THRESHOLD
    ):
        score += 35
        findings.append(
            f"Memory usage increased by {memory_growth:.2f} "
            "percentage points over the last 3 samples."
        )
        recommendations.append(
            "Investigate possible memory growth or a memory "
            "leak using application-level profiling."
        )

    # Check sustained CPU pressure.
    if all(value >= CPU_HIGH_PERCENT for value in recent_cpu):
        score += 25
        findings.append(
            "CPU usage has remained high across the last "
            "3 samples."
        )
        recommendations.append(
            "Inspect CPU-intensive processes and application "
            "workloads."
        )

    score = min(score, 100)

    if score >= 60:
        risk = "High"
    elif score >= 30:
        risk = "Medium"
    else:
        risk = "Low"

    if not findings:
        findings.append(
            "No significant memory growth or sustained CPU "
            "pressure detected in the available samples."
        )

    if not recommendations:
        recommendations.append(
            "Continue monitoring CPU and memory usage."
        )

    return {
        "container": container_name,
        "risk_level": risk,
        "risk_score": score,
        "sample_count": len(samples),
        "latest_memory_percent": round(latest_memory, 2),
        "latest_cpu_percent": round(latest_cpu, 2),
        "findings": findings,
        "recommendations": recommendations,
    }


def analyze_all_containers(metric_items):
    """Group metric history by container and analyze each one."""

    grouped = {}

    for item in metric_items:
        name = item.get("service_name")

        if not name:
            continue

        grouped.setdefault(name, []).append(item)

    results = [
        analyze_container_history(name, history)
        for name, history in grouped.items()
    ]

    risk_order = {
        "High": 0,
        "Medium": 1,
        "Low": 2,
        "Insufficient Data": 3,
    }

    results.sort(
        key=lambda item: risk_order[item["risk_level"]]
    )

    return {
        "total_containers_analyzed": len(results),
        "high_risk": sum(
            item["risk_level"] == "High" for item in results
        ),
        "medium_risk": sum(
            item["risk_level"] == "Medium" for item in results
        ),
        "low_risk": sum(
            item["risk_level"] == "Low" for item in results
        ),
        "insufficient_data": sum(
            item["risk_level"] == "Insufficient Data"
            for item in results
        ),
        "predictions": results,
        "analysis_type": "Rule-based historical trend analysis",
        "note": (
            "Risk indicators are early warnings based on "
            "historical metrics, not guaranteed failure predictions."
        ),
    }
