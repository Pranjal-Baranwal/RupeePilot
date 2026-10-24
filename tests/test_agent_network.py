
import pytest

from app.agents.coordinator_runtime import build_coordinator_agent
from app.agents.network_messages import (
    AgentTask,
    AgentTaskResult,
)
from app.config import AGENT_SEEDS, validate_agent_seeds
from run_network import build_network


@pytest.fixture
def temporary_agent_seeds(monkeypatch):
    """Use isolated test seeds instead of deployment credentials."""

    for name in AGENT_SEEDS:
        monkeypatch.setitem(
            AGENT_SEEDS,
            name,
            f"rupeepilot-test-seed-{name}-unique-value",
        )


def test_all_seven_agents_can_be_constructed(temporary_agent_seeds):
    """The network factory should construct six specialists and a coordinator."""

    bureau, specialists, coordinator = build_network()

    assert len(specialists) == 6

    expected_specialists = {
        "expense",
        "cashflow",
        "bills",
        "goal",
        "scenario",
        "verification",
    }

    assert set(specialists) == expected_specialists
    assert coordinator.name == "rupeepilot-coordinator"

    addresses = [
        coordinator.address,
        *(agent.address for agent in specialists.values()),
    ]

    assert len(addresses) == 7
    assert len(set(addresses)) == 7
    assert all(address.startswith("agent") for address in addresses)


def test_agent_task_round_trip():
    """Agent requests should serialize and deserialize correctly."""

    original = AgentTask(
        request_id="request-001:expense",
        task_type="expense",
        payload_json='{"profile":{"monthly_income":"28000"}}',
    )

    restored = AgentTask.model_validate_json(
        original.model_dump_json()
    )

    assert restored.request_id == original.request_id
    assert restored.task_type == original.task_type
    assert restored.payload_json == original.payload_json


def test_agent_result_round_trip():
    """Agent responses should preserve correlation IDs and status."""

    original = AgentTaskResult(
        request_id="request-001:expense",
        agent_name="expense",
        success=True,
        result_json='{"remaining_after_unexpected":"-4000"}',
    )

    restored = AgentTaskResult.model_validate_json(
        original.model_dump_json()
    )

    assert restored.request_id == original.request_id
    assert restored.agent_name == original.agent_name
    assert restored.success is True
    assert restored.result_json == original.result_json


def test_coordinator_rejects_missing_specialists():
    """The Coordinator must not start without all specialist addresses."""

    with pytest.raises(
        ValueError,
        match="Missing specialist addresses",
    ):
        build_coordinator_agent(
            specialist_addresses={},
            seed="rupeepilot-coordinator-test-only",
            port=8010,
        )


def test_duplicate_agent_seeds_are_rejected(
    temporary_agent_seeds,
    monkeypatch,
):
    """Each agent must have a distinct persistent identity."""

    monkeypatch.setitem(
        AGENT_SEEDS,
        "expense",
        AGENT_SEEDS["coordinator"],
    )

    with pytest.raises(
        ValueError,
        match="unique seed",
    ):
        validate_agent_seeds()
