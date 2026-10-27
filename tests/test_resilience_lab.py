
import pytest

from manager.resilience_lab import (
    is_eligible_container,
    validate_experiment_target,
)


class FakeContainer:
    def __init__(self, labels=None, status="running"):
        self.labels = labels or {}
        self.status = status
        self.short_id = "abc123"
        self.name = "resilience-test"


def test_allows_explicitly_labelled_running_container():
    container = FakeContainer(
        labels={"dockpilot.chaos": "allowed"}
    )

    assert is_eligible_container(container) is True
    result = validate_experiment_target(container)
    assert result["eligible"] is True
    assert result["container_name"] == "resilience-test"


def test_blocks_container_without_opt_in_label():
    container = FakeContainer()

    assert is_eligible_container(container) is False
    with pytest.raises(ValueError, match="Experiment blocked"):
        validate_experiment_target(container)


def test_blocks_container_with_wrong_label_value():
    container = FakeContainer(
        labels={"dockpilot.chaos": "true"}
    )

    with pytest.raises(ValueError, match="Experiment blocked"):
        validate_experiment_target(container)


def test_blocks_stopped_container_even_with_label():
    container = FakeContainer(
        labels={"dockpilot.chaos": "allowed"},
        status="exited",
    )

    with pytest.raises(ValueError, match="must be running"):
        validate_experiment_target(container)


def test_blocks_missing_container():
    with pytest.raises(ValueError, match="not found"):
        validate_experiment_target(None)
