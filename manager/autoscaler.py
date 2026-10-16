
"""DockPilot automatic scaling decision engine.

This module calculates scaling decisions. It does not change containers.
Actual Docker Compose scaling will be integrated separately.
"""

from dataclasses import dataclass
from time import monotonic


@dataclass
class ScalingConfig:
    scale_up_cpu: float = 70.0
    scale_down_cpu: float = 20.0
    scale_up_seconds: int = 60
    scale_down_seconds: int = 180
    cooldown_seconds: int = 60
    min_replicas: int = 1
    max_replicas: int = 5
    sample_seconds: int = 10

    def validate(self):
        if not 0 <= self.scale_down_cpu < self.scale_up_cpu <= 100:
            raise ValueError("CPU thresholds must satisfy 0 <= scale-down < scale-up <= 100.")
        if self.scale_up_seconds <= 0 or self.scale_down_seconds <= 0:
            raise ValueError("Sustained CPU durations must be positive.")
        if self.cooldown_seconds < 0 or self.sample_seconds <= 0:
            raise ValueError("Cooldown must be non-negative and sample interval positive.")
        if self.min_replicas < 1 or self.max_replicas < self.min_replicas:
            raise ValueError("Replica limits must satisfy 1 <= min_replicas <= max_replicas.")


class ScalingDecisionEngine:
    """Track sustained CPU conditions and decide whether one replica should change."""

    def __init__(self, config=None, clock=monotonic):
        self.config = config or ScalingConfig()
        self.config.validate()
        self.clock = clock
        self.high_since = None
        self.low_since = None
        self.last_action_at = None

    def evaluate(self, cpu_percent, replicas, now=None):
        """Return a decision; never performs Docker operations."""
        if cpu_percent is None or not 0 <= cpu_percent <= 100:
            raise ValueError("cpu_percent must be a real percentage between 0 and 100.")
        if replicas < self.config.min_replicas or replicas > self.config.max_replicas:
            raise ValueError("replicas is outside the configured limits.")

        now = self.clock() if now is None else now
        result = {
            "action": "none",
            "reason": "CPU thresholds have not been sustained long enough.",
            "cpu_percent": round(float(cpu_percent), 2),
            "replicas": replicas,
        }

        if cpu_percent > self.config.scale_up_cpu:
            self.high_since = now if self.high_since is None else self.high_since
        else:
            self.high_since = None

        if cpu_percent < self.config.scale_down_cpu:
            self.low_since = now if self.low_since is None else self.low_since
        else:
            self.low_since = None

        if self.last_action_at is not None:
            if now - self.last_action_at < self.config.cooldown_seconds:
                result["reason"] = "Scaling cooldown is active."
                return result

        if (
            self.high_since is not None
            and now - self.high_since >= self.config.scale_up_seconds
        ):
            if replicas < self.config.max_replicas:
                result.update(
                    action="scale_up",
                    reason="CPU stayed above the scale-up threshold.",
                    replicas=replicas + 1,
                )
            else:
                result["reason"] = "Maximum replica count reached."
            self.high_since = None
            self.low_since = None
            return result

        if (
            self.low_since is not None
            and now - self.low_since >= self.config.scale_down_seconds
        ):
            if replicas > self.config.min_replicas:
                result.update(
                    action="scale_down",
                    reason="CPU stayed below the scale-down threshold.",
                    replicas=replicas - 1,
                )
            else:
                result["reason"] = "Minimum replica count reached."
            self.high_since = None
            self.low_since = None

        return result

    def record_action(self, now=None):
        """Start the cooldown after a successful real scaling operation."""
        self.last_action_at = self.clock() if now is None else now

