
from uagents import Model


class AgentTask(Model):
    """A task sent from the Coordinator to a specialist agent.

    Financial data is transported as JSON text. Monetary values
    inside that JSON should be decimal strings, not floating-point
    numbers, to preserve financial precision.
    """

    request_id: str
    task_type: str
    payload_json: str


class AgentTaskResult(Model):
    """A specialist agent's response to the Coordinator."""

    request_id: str
    agent_name: str
    success: bool
    result_json: str = "{}"
    error: str = ""
