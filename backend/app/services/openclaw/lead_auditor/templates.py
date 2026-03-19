"""Prompt templates for Lead Auditor."""

from __future__ import annotations

from typing import Any


def build_audit_prompt(
    *,
    mission_goal: str,
    task_title: str,
    result_summary: str | None,
    result_risk: str | None,
    result_next_action: str | None,
    subtask_results: list[dict[str, Any]],
    anomalies: list[str],
) -> str:
    """Build the audit prompt for Lead Agent to evaluate mission results.

    Args:
        mission_goal: The original goal of the mission
        task_title: Title of the parent task
        result_summary: Summary of mission results
        result_risk: Risk level (low/medium/high)
        result_next_action: Suggested next action
        subtask_results: List of subtask execution results
        anomalies: List of anomalies detected during execution

    Returns:
        Formatted prompt string for LLM audit
    """
    subtasks_text = _format_subtask_results(subtask_results)
    anomalies_text = _format_anomalies(anomalies)

    return f"""# Mission Result Audit

You are the **Chief Auditor** for this mission. Your role is to critically evaluate the execution results from sub-agents and determine if the mission has successfully achieved its goals.

## Mission Context

- **Task Title**: {task_title}
- **Mission Goal**: {mission_goal}
- **Risk Assessment**: {result_risk or "not provided"}
- **Suggested Next Action**: {result_next_action or "not provided"}

## Execution Summary

{result_summary or "No summary provided."}

## Subtask Results

{subtasks_text}

## Anomalies Detected

{anomalies_text}

---

## Audit Criteria

Please evaluate the mission results against the following criteria:

1. **Goal Achievement**: Did the sub-agents successfully complete the mission goal?
2. **Output Quality**: Is the output complete, accurate, and actionable?
3. **Risk Assessment**: Are the identified risks appropriate? Any missing risks?
4. **Edge Cases**: Are there any overlooked edge cases or failure modes?
5. **Completeness**: Are there any incomplete parts or missing deliverables?

---

## Output Format

You MUST respond with a JSON object containing your audit decision:

```json
{{
  "decision": "approve" | "request_changes",
  "summary": "Brief summary of your audit conclusion (1-2 sentences)",
  "reason": "Detailed reasoning for your decision. If requesting changes, be specific about what needs to be fixed.",
  "suggestions": ["Specific suggestion 1", "Specific suggestion 2", "Specific suggestion 3"],
  "risk_confirmed": true/false,
  "missing_items": ["Any missing deliverables or considerations"]
}}
```

## Important

- Be objective and analytical in your evaluation
- If there are any issues or incomplete items, set decision to "request_changes"
- Provide specific, actionable suggestions for improvement
- Your decision will be used to determine if the task needs to be returned to the sub-agent for revisions
"""


def _format_subtask_results(results: list[dict[str, Any]]) -> str:
    """Format subtask results for the prompt."""
    if not results:
        return "No subtask results available."

    lines = []
    for i, result in enumerate(results, 1):
        status = result.get("status", "unknown")
        label = result.get("label", f"Subtask {i}")
        summary = result.get("result_summary", "No summary")
        risk = result.get("result_risk", "unknown")
        error = result.get("error_message", "")

        lines.append(f"### Subtask {i}: {label}")
        lines.append(f"- **Status**: {status}")
        lines.append(f"- **Summary**: {summary}")
        lines.append(f"- **Risk**: {risk}")
        if error:
            lines.append(f"- **Error**: {error}")
        lines.append("")

    return "\n".join(lines)


def _format_anomalies(anomalies: list[str]) -> str:
    """Format anomalies for the prompt."""
    if not anomalies:
        return "No anomalies detected."

    lines = []
    for i, anomaly in enumerate(anomalies, 1):
        lines.append(f"{i}. {anomaly}")

    return "\n".join(lines)
