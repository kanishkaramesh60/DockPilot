
from manager.autoscaler import ScalingConfig, ScalingDecisionEngine


def test_high_cpu_must_be_sustained_for_one_minute():
    engine = ScalingDecisionEngine()

    assert engine.evaluate(80, 1, now=0)["action"] == "none"
    assert engine.evaluate(80, 1, now=50)["action"] == "none"

    result = engine.evaluate(80, 1, now=60)
    assert result["action"] == "scale_up"
    assert result["replicas"] == 2


def test_low_cpu_must_be_sustained_for_three_minutes():
    engine = ScalingDecisionEngine()

    assert engine.evaluate(10, 2, now=0)["action"] == "none"
    assert engine.evaluate(10, 2, now=179)["action"] == "none"

    result = engine.evaluate(10, 2, now=180)
    assert result["action"] == "scale_down"
    assert result["replicas"] == 1


def test_cpu_between_thresholds_resets_sustained_condition():
    engine = ScalingDecisionEngine()

    engine.evaluate(80, 1, now=0)
    engine.evaluate(80, 1, now=30)
    engine.evaluate(50, 1, now=40)

    assert engine.evaluate(80, 1, now=90)["action"] == "none"


def test_minimum_and_maximum_replica_limits():
    engine = ScalingDecisionEngine()

    result = engine.evaluate(10, 1, now=0)
    assert result["replicas"] == 1

    result = engine.evaluate(80, 5, now=0)
    assert result["replicas"] == 5


def test_cooldown_after_successful_action():
    config = ScalingConfig(scale_up_seconds=10, cooldown_seconds=60)
    engine = ScalingDecisionEngine(config)

    engine.evaluate(80, 1, now=0)
    result = engine.evaluate(80, 1, now=10)

    assert result["action"] == "scale_up"

    engine.record_action(now=10)
    result = engine.evaluate(80, 2, now=20)

    assert result["action"] == "none"
    assert result["reason"] == "Scaling cooldown is active."
