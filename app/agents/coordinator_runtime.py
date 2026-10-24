
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import uuid4

from pydantic import ValidationError
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from app.agents.network_messages import AgentTask, AgentTaskResult
from app.config import AGENT_SEEDS
from app.schemas.financial_models import (
    Bill,
    BillPriority,
    FinancialProfile,
    PlanningResult,
    PlanningScenario,
    SavingsGoal,
    VerificationReport,
)
from app.services.explanation_service import build_explanation
from app.services.parsing_service import parse_financial_request


LOGGER = logging.getLogger("rupeepilot.coordinator_runtime")

AGENT_NAME = "rupeepilot-coordinator"
DEFAULT_PORT = 8010
WORKFLOW_TIMEOUT_SECONDS = 120

ANALYSIS_AGENTS = {
    "expense",
    "cashflow",
    "bills",
    "goal",
}

REQUIRED_SPECIALISTS = ANALYSIS_AGENTS | {
    "scenario",
    "verification",
}


@dataclass
class WorkflowState:
    """State for one independently tracked chat request."""

    request_id: str
    chat_sender: str
    profile: FinancialProfile
    bills: list[Bill]
    goals: list[SavingsGoal]
    reference_date: date

    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    pending_analysis: set[str] = field(
        default_factory=lambda: set(ANALYSIS_AGENTS)
    )
    analysis_results: dict[str, dict] = field(default_factory=dict)

    scenarios: dict[str, PlanningScenario] = field(
        default_factory=dict
    )
    pending_verification: set[str] = field(default_factory=set)

    verified_scenarios: dict[
        str,
        tuple[PlanningScenario, VerificationReport],
    ] = field(default_factory=dict)

    verification_failures: list[str] = field(default_factory=list)

    created_at: float = field(default_factory=time.monotonic)


def _unique(items: list[str]) -> list[str]:
    """Remove duplicate strings while preserving their order."""

    return list(dict.fromkeys(items))


def _ranking_key(
    scenario: PlanningScenario,
) -> tuple:
    """Rank candidate plans with explicit deterministic priorities."""

    balance = scenario.projected_closing_balance

    total_adjustment = (
        scenario.adjustment.spending_reduction
        + scenario.adjustment.savings_reduction
    )

    if balance >= Decimal("0"):
        return (
            not scenario.mandatory_bills_covered,
            0,
            not scenario.preserves_minimum_buffer,
            total_adjustment,
            scenario.adjustment.savings_reduction,
            scenario.adjustment.spending_reduction,
            -balance,
        )

    return (
        not scenario.mandatory_bills_covered,
        1,
        -balance,
        not scenario.preserves_minimum_buffer,
        total_adjustment,
        scenario.adjustment.savings_reduction,
        scenario.adjustment.spending_reduction,
    )


def build_coordinator_agent(
    specialist_addresses: dict[str, str],
    seed: str | None = None,
    port: int = DEFAULT_PORT,
    mailbox: bool = False,
) -> Agent:
    """Construct the Coordinator with an ACP interface.

    specialist_addresses must contain the registered addresses of
    expense, cashflow, bills, goal, scenario, and verification.

    Set mailbox=True when configuring the agent for a supported
    Agentverse mailbox deployment.
    """

    missing_agents = REQUIRED_SPECIALISTS - set(
        specialist_addresses
    )

    if missing_agents:
        raise ValueError(
            "Missing specialist addresses: "
            + ", ".join(sorted(missing_agents))
        )

    for name in REQUIRED_SPECIALISTS:
        address = specialist_addresses[name]

        if not isinstance(address, str) or not address.startswith(
            "agent"
        ):
            raise ValueError(
                f"The address for '{name}' is invalid."
            )

    resolved_seed = (
        seed or AGENT_SEEDS["coordinator"]
    ).strip()

    if not resolved_seed:
        raise ValueError(
            "COORDINATOR_SEED is missing from .env."
        )

    if not 1024 <= port <= 65535:
        raise ValueError(
            "port must be between 1024 and 65535."
        )

    agent_options = {
        "name": AGENT_NAME,
        "seed": resolved_seed,
        "port": port,
        "endpoint": [f"http://127.0.0.1:{port}/submit"],
    }

    if mailbox:
        agent_options["mailbox"] = True

    coordinator = Agent(**agent_options)

    # One dictionary entry per active planning request.
    workflows: dict[str, WorkflowState] = {}

    # Correlation ID -> (parent request, stage, item key, expected agent).
    task_routes: dict[
        str,
        tuple[str, str, str, str],
    ] = {}

    chat_protocol = Protocol(spec=chat_protocol_spec)

    async def send_chat_text(
        ctx: Context,
        recipient: str,
        text: str,
    ) -> None:
        """Send a text response using the ACP message format."""

        await ctx.send(
            recipient,
            ChatMessage(
                content=[
                    TextContent(
                        type="text",
                        text=text,
                    )
                ]
            ),
        )

    def forget_workflow(request_id: str) -> None:
        """Remove a completed workflow and its outstanding routes."""

        workflows.pop(request_id, None)

        stale_routes = [
            task_id
            for task_id, route in task_routes.items()
            if route[0] == request_id
        ]

        for task_id in stale_routes:
            task_routes.pop(task_id, None)

    def add_warnings(
        state: WorkflowState,
        values: list[str],
    ) -> None:
        """Collect warnings without duplicating them."""

        state.warnings = _unique(
            state.warnings + values
        )

    async def fail_workflow(
        ctx: Context,
        state: WorkflowState,
        reason: str,
    ) -> None:
        """Return a clear failure instead of an unverified plan."""

        ctx.logger.error(
            "Request %s failed: %s",
            state.request_id,
            reason,
        )

        try:
            await send_chat_text(
                ctx,
                state.chat_sender,
                (
                    "RupeePilot could not complete a verified plan.\n\n"
                    f"Reason: {reason}\n\n"
                    "No recommendation from this failed workflow "
                    "is being presented as verified. Please correct "
                    "the issue and submit the request again."
                ),
            )
        except Exception:
            ctx.logger.exception(
                "Could not send the failure response."
            )
        finally:
            forget_workflow(state.request_id)

    async def dispatch_task(
        ctx: Context,
        state: WorkflowState,
        agent_key: str,
        task_type: str,
        payload: dict,
        stage: str,
        item_key: str,
        correlation_id: str | None = None,
    ) -> None:
        """Register a task before sending it, preventing fast-response races."""

        task_id = correlation_id or (
            f"{state.request_id}:{task_type}"
        )

        task_routes[task_id] = (
            state.request_id,
            stage,
            item_key,
            agent_key,
        )

        message = AgentTask(
            request_id=task_id,
            task_type=task_type,
            payload_json=json.dumps(
                payload,
                separators=(",", ":"),
            ),
        )

        await ctx.send(
            specialist_addresses[agent_key],
            message,
        )

        ctx.logger.info(
            "Sent %s task %s to %s.",
            task_type,
            task_id,
            agent_key,
        )

    async def start_scenario_stage(
        ctx: Context,
        state: WorkflowState,
    ) -> None:
        """Request alternative plans after required analyses finish."""

        try:
            profile_data = state.profile.model_dump(mode="json")

            await dispatch_task(
                ctx=ctx,
                state=state,
                agent_key="scenario",
                task_type="scenario",
                payload={
                    "profile": profile_data,
                    "max_scenarios": 6,
                },
                stage="scenario",
                item_key="scenario",
            )
        except Exception as exc:
            await fail_workflow(
                ctx,
                state,
                f"Could not start scenario planning: {exc}",
            )

    async def start_verification_stage(
        ctx: Context,
        state: WorkflowState,
        scenarios: list[PlanningScenario],
    ) -> None:
        """Request independent verification for every candidate."""

        if not scenarios:
            await fail_workflow(
                ctx,
                state,
                "The Scenario Agent returned no candidate plans.",
            )
            return

        state.scenarios = {
            scenario.scenario_id: scenario
            for scenario in scenarios
        }

        state.pending_verification = set(
            state.scenarios.keys()
        )

        try:
            # Create a separate correlation ID for every candidate.
            for scenario in scenarios:
                await dispatch_task(
                    ctx=ctx,
                    state=state,
                    agent_key="verification",
                    task_type="verification",
                    payload={
                        "profile": state.profile.model_dump(
                            mode="json"
                        ),
                        "candidate": scenario.model_dump(
                            mode="json"
                        ),
                    },
                    stage="verification",
                    item_key=scenario.scenario_id,
                    correlation_id=(
                        f"{state.request_id}:verify:"
                        f"{scenario.scenario_id}"
                    ),
                )
        except Exception as exc:
            await fail_workflow(
                ctx,
                state,
                f"Could not start plan verification: {exc}",
            )

    async def finish_verification(
        ctx: Context,
        state: WorkflowState,
    ) -> None:
        """Choose only a candidate that passed verification."""

        verified = list(
            state.verified_scenarios.values()
        )

        if not verified:
            report = VerificationReport(
                approved=False,
                checks_passed=[],
                discrepancies=_unique(
                    state.verification_failures
                    or [
                        "No candidate passed independent verification."
                    ]
                ),
                warnings=state.warnings,
            )

            result = PlanningResult(
                request_id=state.request_id,
                status="verification_failed",
                summary=(
                    "No candidate plan passed independent verification. "
                    "RupeePilot cannot provide a verified recommendation."
                ),
                recommended_scenario=None,
                alternatives=[],
                verification=report,
                assumptions=_unique(
                    state.assumptions + state.warnings
                ),
            )

        else:
            verified.sort(
                key=lambda item: _ranking_key(item[0])
            )

            recommended, report = verified[0]
            alternatives = [
                scenario
                for scenario, _ in verified[1:]
            ]

            balance = recommended.projected_closing_balance

            if balance < Decimal("0"):
                status = "verified_with_shortfall"
                summary = (
                    "The best verified candidate is: "
                    f"{recommended.description} "
                    "The projected closing balance remains "
                    f"-₹{-balance}, so a shortfall remains."
                )

            elif balance < state.profile.minimum_cash_buffer:
                status = "verified_below_buffer"
                summary = (
                    "Recommended verified plan: "
                    f"{recommended.description} "
                    "The projected balance does not preserve "
                    "the requested minimum cash buffer."
                )

            else:
                status = "verified"
                summary = (
                    "Recommended verified plan: "
                    f"{recommended.description} "
                    "The plan passed independent consistency checks."
                )

            result = PlanningResult(
                request_id=state.request_id,
                status=status,
                summary=summary,
                recommended_scenario=recommended,
                alternatives=alternatives,
                verification=report,
                assumptions=_unique(
                    state.assumptions + state.warnings
                ),
            )

        try:
            await send_chat_text(
                ctx,
                state.chat_sender,
                build_explanation(result),
            )
        except Exception:
            ctx.logger.exception(
                "Could not send the completed planning result."
            )
        finally:
            forget_workflow(state.request_id)

    async def start_workflow(
        ctx: Context,
        sender: str,
        user_text: str,
    ) -> None:
        """Extract, validate, and dispatch a natural-language request."""

        try:
            # The ASI:One client uses a synchronous HTTP interface;
            # put the call in a worker thread to avoid blocking the
            # Coordinator's event loop while the API responds.
            parsed = await asyncio.to_thread(
                parse_financial_request,
                user_text,
            )

        except Exception as exc:
            ctx.logger.exception(
                "Financial request parsing failed."
            )

            await send_chat_text(
                ctx,
                sender,
                (
                    "RupeePilot could not parse your financial request. "
                    "Check the ASI:One API configuration and connection, "
                    "then try again.\n\n"
                    f"Details: {type(exc).__name__}: {exc}"
                ),
            )
            return

        missing = list(parsed.missing_fields)

        # Do not silently treat an unknown opening balance as zero.
        if parsed.opening_balance is None:
            missing.append(
                "opening cash balance (or explicitly confirm ₹0)"
            )

        if missing:
            prompt = (
                "RupeePilot needs a few more details before it can "
                "build a financial plan:\n\n"
                + "\n".join(f"- {item}" for item in _unique(missing))
                + "\n\nPlease submit the complete financial details "
                "including these missing values."
            )

            await send_chat_text(ctx, sender, prompt)
            return

        reference_date = date.today()

        try:
            # These required amounts have been checked above.
            profile = FinancialProfile(
                currency=parsed.currency,
                monthly_income=parsed.monthly_income,
                opening_balance=parsed.opening_balance,
                fixed_bills=parsed.fixed_bills,
                regular_spending=parsed.regular_spending,
                planned_savings=parsed.planned_savings,
                unexpected_expenses=parsed.unexpected_expenses,
                max_spending_cut=(
                    parsed.max_spending_cut
                    if parsed.max_spending_cut is not None
                    else Decimal("0")
                ),
                minimum_cash_buffer=(
                    parsed.minimum_cash_buffer
                    if parsed.minimum_cash_buffer is not None
                    else Decimal("0")
                ),
            )

            bills = []

            for item in parsed.bills:
                if item.priority is None:
                    parsed.assumptions.append(
                        f"Priority for bill '{item.name}' was not "
                        "specified; treated as mandatory."
                    )

                if item.paid is None:
                    parsed.assumptions.append(
                        f"Payment status for bill '{item.name}' was "
                        "not specified; treated as unpaid."
                    )

                bills.append(
                    Bill(
                        name=item.name,
                        amount=item.amount,
                        due_date=item.due_date,
                        priority=BillPriority(
                            item.priority or "mandatory"
                        ),
                        paid=(
                            item.paid
                            if item.paid is not None
                            else False
                        ),
                    )
                )

            goals = [
                SavingsGoal(
                    name=item.name,
                    target_amount=item.target_amount,
                    current_amount=item.current_amount,
                    monthly_contribution=item.monthly_contribution,
                    target_date=item.target_date,
                )
                for item in parsed.goals
            ]

        except (ValidationError, ValueError, TypeError) as exc:
            ctx.logger.exception(
                "Validated financial profile could not be built."
            )

            await send_chat_text(
                ctx,
                sender,
                (
                    "The financial details could not be converted "
                    "into a valid profile. Please clarify the "
                    f"amounts and dates. Details: {exc}"
                ),
            )
            return

        assumptions = list(parsed.assumptions)

        for note in parsed.notes:
            assumptions.append(f"User-provided note: {note}")

        if parsed.max_spending_cut is None:
            assumptions.append(
                "Spending cuts were not authorized and will not "
                "be proposed."
            )

        if parsed.minimum_cash_buffer is None:
            assumptions.append(
                "No minimum cash-buffer preference was provided; "
                "the minimum buffer is set to ₹0."
            )

        state = WorkflowState(
            request_id=str(uuid4()),
            chat_sender=sender,
            profile=profile,
            bills=bills,
            goals=goals,
            reference_date=reference_date,
            assumptions=_unique(assumptions),
        )

        workflows[state.request_id] = state

        profile_payload = profile.model_dump(mode="json")

        bills_payload = {
            "bills": [
                bill.model_dump(mode="json")
                for bill in bills
            ],
            "reference_date": reference_date.isoformat(),
            "horizon_days": 7,
        }

        goals_payload = {
            "goals": [
                goal.model_dump(mode="json")
                for goal in goals
            ],
            "reference_date": reference_date.isoformat(),
        }

        tasks = [
            (
                "expense",
                "expense",
                {"profile": profile_payload},
            ),
            (
                "cashflow",
                "cashflow",
                {"profile": profile_payload},
            ),
            (
                "bills",
                "bills",
                bills_payload,
            ),
            (
                "goal",
                "goal",
                goals_payload,
            ),
        ]

        try:
            for agent_key, task_type, payload in tasks:
                await dispatch_task(
                    ctx=ctx,
                    state=state,
                    agent_key=agent_key,
                    task_type=task_type,
                    payload=payload,
                    stage="analysis",
                    item_key=agent_key,
                )

            ctx.logger.info(
                "Dispatched specialist analyses for request %s.",
                state.request_id,
            )

        except Exception as exc:
            await fail_workflow(
                ctx,
                state,
                f"Could not dispatch specialist tasks: {exc}",
            )

    @chat_protocol.on_message(ChatMessage)
    async def handle_chat_message(
        ctx: Context,
        sender: str,
        msg: ChatMessage,
    ) -> None:
        """Acknowledge an ACP message and start planning."""

        try:
            await ctx.send(
                sender,
                ChatAcknowledgement(
                    acknowledged_msg_id=msg.msg_id
                ),
            )
        except Exception:
            ctx.logger.exception(
                "Could not acknowledge the incoming chat message."
            )
            return

        user_text = "\n".join(
            item.text
            for item in msg.content
            if isinstance(item, TextContent)
        ).strip()

        if not user_text:
            await send_chat_text(
                ctx,
                sender,
                "Please send your financial question as a text message.",
            )
            return

        ctx.logger.info(
            "Received an ACP chat request from %s.",
            sender,
        )

        await start_workflow(ctx, sender, user_text)

    @chat_protocol.on_message(ChatAcknowledgement)
    async def handle_chat_acknowledgement(
        ctx: Context,
        sender: str,
        msg: ChatAcknowledgement,
    ) -> None:
        ctx.logger.info(
            "Received chat acknowledgement from %s for %s.",
            sender,
            msg.acknowledged_msg_id,
        )

    @coordinator.on_message(model=AgentTaskResult)
    async def handle_agent_result(
        ctx: Context,
        sender: str,
        msg: AgentTaskResult,
    ) -> None:
        """Route asynchronous specialist responses by correlation ID."""

        route = task_routes.pop(msg.request_id, None)

        if route is None:
            ctx.logger.warning(
                "Ignoring an unknown or expired task result: %s",
                msg.request_id,
            )
            return

        parent_id, stage, item_key, expected_agent = route
        state = workflows.get(parent_id)

        if state is None:
            ctx.logger.warning(
                "Workflow %s has expired.",
                parent_id,
            )
            return

        if msg.agent_name != expected_agent:
            await fail_workflow(
                ctx,
                state,
                (
                    f"Expected a response from '{expected_agent}', "
                    f"but received one from '{msg.agent_name}'."
                ),
            )
            return

        if not msg.success:
            await fail_workflow(
                ctx,
                state,
                f"{msg.agent_name} agent failed: {msg.error}",
            )
            return

        try:
            body = json.loads(msg.result_json)

            if not isinstance(body, dict):
                raise ValueError(
                    "Agent result must be a JSON object."
                )

            add_warnings(
                state,
                body.get("warnings", []),
            )

            if stage == "analysis":
                state.analysis_results[item_key] = body
                state.pending_analysis.discard(item_key)

                if not state.pending_analysis:
                    await start_scenario_stage(ctx, state)

                return

            if stage == "scenario":
                raw_scenarios = body.get("scenarios", [])

                if not isinstance(raw_scenarios, list):
                    raise ValueError(
                        "Scenario Agent returned an invalid scenarios field."
                    )

                scenarios = [
                    PlanningScenario.model_validate(item)
                    for item in raw_scenarios
                ]

                await start_verification_stage(
                    ctx,
                    state,
                    scenarios,
                )
                return

            if stage == "verification":
                report_data = body.get("report")

                if not isinstance(report_data, dict):
                    raise ValueError(
                        "Verification report is missing or malformed."
                    )

                report = VerificationReport.model_validate(
                    report_data
                )

                candidate = state.scenarios.get(item_key)

                if candidate is None:
                    raise ValueError(
                        "Verified scenario was not found in workflow state."
                    )

                if body.get("approved") is True and report.approved:
                    state.verified_scenarios[item_key] = (
                        candidate,
                        report,
                    )
                else:
                    state.verification_failures.extend(
                        report.discrepancies
                    )

                add_warnings(state, report.warnings)
                state.pending_verification.discard(item_key)

                if not state.pending_verification:
                    await finish_verification(ctx, state)

                return

            raise ValueError(
                f"Unexpected workflow stage: {stage}"
            )

        except Exception as exc:
            ctx.logger.exception(
                "Could not process result %s from %s.",
                msg.request_id,
                sender,
            )

            await fail_workflow(
                ctx,
                state,
                f"Invalid response from {msg.agent_name}: {exc}",
            )

    @coordinator.on_interval(period=5.0)
    async def expire_stalled_workflows(ctx: Context) -> None:
        """Fail requests that have stopped receiving responses."""

        now = time.monotonic()

        expired = [
            state
            for state in workflows.values()
            if (
                now - state.created_at
                > WORKFLOW_TIMEOUT_SECONDS
            )
        ]

        for state in expired:
            await fail_workflow(
                ctx,
                state,
                (
                    "A specialist did not respond before the "
                    "workflow timeout."
                ),
            )

    coordinator.include(
        chat_protocol,
        publish_manifest=True,
    )

    return coordinator