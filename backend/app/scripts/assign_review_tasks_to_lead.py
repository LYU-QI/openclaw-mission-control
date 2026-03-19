#!/usr/bin/env python3
"""
Script to assign review tasks to Lead agents and send notifications.

Usage:
    python -m app.scripts.assign_review_tasks_to_lead
"""

import asyncio
import sys
from sqlmodel import select, col

from app.db.session import async_session_maker
from app.models.tasks import Task
from app.models.agents import Agent
from app.models.boards import Board
from app.services.webhooks.dispatch import GatewayDispatchService
from app.services.openclaw.gateway_dispatch import optional_gateway_client_config


async def _get_gateway_config(session, board: Board):
    """Get gateway config for a board."""
    from app.models.gateways import Gateway

    if board.gateway_id is None:
        return None
    gateway = await session.get(Gateway, board.gateway_id)
    if gateway is None:
        return None
    return optional_gateway_client_config(gateway)


async def _send_notification(dispatch, session_key, config, agent_name, message):
    """Send notification to an agent."""
    from app.services.openclaw.gateway_dispatch import send_message, ensure_session

    try:
        await ensure_session(session_key, config=config, label=agent_name)
        await send_message(message, session_key=session_key, config=config, deliver=False)
        return None
    except Exception as e:
        return str(e)


async def _assignment_notification_message(board: Board, task: Task, agent: Agent) -> str:
    """Generate notification message for task assignment."""
    details = [
        f"Board: {board.name}",
        f"Task: {task.title}",
        f"Task ID: {task.id}",
        f"Status: {task.status}",
    ]
    details.append(
        "Take action: review the deliverables now. "
        "Approve by moving to done or return to inbox with clear feedback."
    )
    return "TASK READY FOR LEAD REVIEW\n" + "\n".join(details)


async def assign_review_tasks_to_lead():
    """Assign all review tasks to their board's Lead agent and send notifications."""
    async with async_session_maker() as session:
        # Get all review tasks
        result = await session.exec(select(Task).where(Task.status == "review"))
        review_tasks = result.all()

        if not review_tasks:
            print("No review tasks found.")
            return

        print(f"Found {len(review_tasks)} review tasks.")

        for task in review_tasks:
            if task.board_id is None:
                print(f"  Task {task.id} has no board_id, skipping.")
                continue

            # Get board
            board = await session.get(Board, task.board_id)
            if board is None:
                print(f"  Task {task.id}: Board not found, skipping.")
                continue

            # Get Lead agent
            result = await session.exec(
                select(Agent)
                .where(col(Agent.board_id) == task.board_id)
                .where(col(Agent.is_board_lead) == True)
            )
            lead = result.first()

            if lead is None:
                print(f"  Task {task.id}: No Lead agent found for board {board.name}, skipping.")
                continue

            # Check if already assigned
            if task.assigned_agent_id == lead.id:
                print(f"  Task {task.id}: Already assigned to Lead ({lead.name}), skipping.")
                continue

            # Get gateway config
            config = await _get_gateway_config(session, board)

            # Assign to Lead
            old_assignee = task.assigned_agent_id
            task.assigned_agent_id = lead.id
            session.add(task)
            await session.commit()

            print(f"  Task {task.id}: Assigned to Lead ({lead.name})")

            # Send notification if gateway config available
            if config and lead.openclaw_session_id:
                message = await _assignment_notification_message(board, task, lead)
                error = await _send_notification(
                    None,  # dispatch not needed for direct call
                    lead.openclaw_session_id,
                    config,
                    lead.name,
                    message,
                )
                if error:
                    print(f"    Notification failed: {error}")
                else:
                    print(f"    Notification sent to {lead.name}")
            else:
                if not config:
                    print(f"    No gateway config, notification skipped")
                if not lead.openclaw_session_id:
                    print(f"    Lead has no session ID, notification skipped")

        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(assign_review_tasks_to_lead())
