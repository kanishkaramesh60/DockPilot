
from manager.autoscaler import ScalingConfig, ScalingDecisionEngine
import pytest



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



@pytest.mark.parametrize(
    "kwargs",
    [
        {"scale_down_cpu": 70, "scale_up_cpu": 70},
        {"scale_down_cpu": -1},
        {"scale_up_cpu": 101},
        {"scale_up_seconds": 0},
        {"scale_down_seconds": 0},
        {"cooldown_seconds": -1},
        {"sample_seconds": 0},
        {"min_replicas": 0},
        {"min_replicas": 3, "max_replicas": 2},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        ScalingDecisionEngine(ScalingConfig(**kwargs))


@pytest.mark.parametrize("cpu", [20, 50, 70])
def test_threshold_boundaries_do_not_trigger_scaling(cpu):
    engine = ScalingDecisionEngine(
        ScalingConfig(scale_up_seconds=10, scale_down_seconds=10)
    )

    assert engine.evaluate(cpu, 2, now=0)["action"] == "none"
    assert engine.evaluate(cpu, 2, now=100)["action"] == "none"


def test_high_cpu_condition_resets_when_cpu_drops_to_threshold():
    engine = ScalingDecisionEngine(
        ScalingConfig(scale_up_seconds=10)
    )

    engine.evaluate(80, 1, now=0)
    engine.evaluate(70, 1, now=5)

    # The high-CPU timer restarted at t=10, so only 5 seconds have elapsed.
    assert engine.evaluate(80, 1, now=10)["action"] == "none"


def test_scale_up_stops_at_maximum_replicas():
    engine = ScalingDecisionEngine(
        ScalingConfig(max_replicas=2, scale_up_seconds=10)
    )

    engine.evaluate(80, 2, now=0)
    result = engine.evaluate(80, 2, now=10)

    assert result["action"] == "none"
    assert result["replicas"] == 2
    assert result["reason"] == "Maximum replica count reached."


def test_scale_down_stops_at_minimum_replicas():
    engine = ScalingDecisionEngine(
        ScalingConfig(min_replicas=1, scale_down_seconds=10)
    )

    engine.evaluate(10, 1, now=0)
    result = engine.evaluate(10, 1, now=10)

    assert result["action"] == "none"
    assert result["replicas"] == 1
    assert result["reason"] == "Minimum replica count reached."


@pytest.mark.parametrize("cpu", [None, -1, 101])
def test_invalid_cpu_values_are_rejected(cpu):
    engine = ScalingDecisionEngine()

    with pytest.raises(ValueError):
        engine.evaluate(cpu, 1, now=0)


@pytest.mark.parametrize("replicas", [0, 6])
def test_replica_count_outside_limits_is_rejected(replicas):
    engine = ScalingDecisionEngine()

    with pytest.raises(ValueError):
        engine.evaluate(50, replicas, now=0)


def test_cooldown_expires_at_configured_boundary():
    engine = ScalingDecisionEngine(
        ScalingConfig(scale_up_seconds=1, cooldown_seconds=10)
    )

    engine.evaluate(80, 1, now=0)
    assert engine.evaluate(80, 1, now=1)["action"] == "scale_up"

    engine.record_action(now=1)
    assert engine.evaluate(80, 2, now=10)["action"] == "none"

    # At exactly 10 seconds after the recorded action, cooldown has expired.
    assert engine.evaluate(80, 2, now=11)["action"] == "scale_up"
