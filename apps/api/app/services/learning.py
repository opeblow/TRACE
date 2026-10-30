"""Apply recalled user memory to deterministic findings (PRD §9 learning loop).

Rules (versioned as MEMORY_RULE_VERSION):
- A user label on a finding's counterparty lowers its priority one step
  (high -> medium -> low). The finding stays visible: a label is the user's
  assertion, not proof that a transfer is safe.
- Alert feedback on the exact transaction sets its review state:
  expected / incorrect -> low priority; needs_review -> at least medium.
- The newest record per subject wins, so a later correction supersedes an older
  one. An empty label removes an earlier label.
- Fresh chain facts are never changed: amounts, digests, and evidence are only
  annotated. The memory-free result is returned alongside for comparison.
"""
from __future__ import annotations

import copy
from typing import Any

from app.services.memory import RecalledMemory

MEMORY_RULE_VERSION = "memory-context-v1"
SEVERITIES = ["low", "medium", "high"]
FEEDBACK_STATES = {"expected": "marked_expected", "incorrect": "marked_incorrect", "needs_review": "needs_review"}


def _short(value: str) -> str:
    return f"{value[:8]}…{value[-6:]}" if len(value) > 16 else value


def _latest(memories: list[RecalledMemory], memory_type: str) -> dict[str, RecalledMemory]:
    latest: dict[str, RecalledMemory] = {}
    for memory in memories:  # already sorted oldest -> newest
        if memory.envelope.memory_type == memory_type:
            latest[memory.envelope.subject] = memory
    return latest


def active_labels(memories: list[RecalledMemory]) -> dict[str, RecalledMemory]:
    return {subject: m for subject, m in _latest(memories, "counterparty_label").items() if m.envelope.value}


def _step_down(severity: str) -> str:
    index = SEVERITIES.index(severity) if severity in SEVERITIES else 1
    return SEVERITIES[max(0, index - 1)]


def _context(memory: RecalledMemory, summary: str) -> dict[str, Any]:
    return {
        "memory_id": memory.memory_id,
        "memory_type": memory.envelope.memory_type,
        "summary": summary,
        "created_at": memory.envelope.created_at,
        "source_type": memory.envelope.source_type,
        "verified": memory.envelope.verified,
    }


def sort_by_priority(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(finding):
        try:
            amount = float(finding.get("amount_sui") or 0)
        except ValueError:
            amount = 0.0
        return (-SEVERITIES.index(finding.get("severity", "medium")), -amount)
    return sorted(findings, key=key)


def apply_memory(findings: list[dict[str, Any]], memories: list[RecalledMemory]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    """Return (adjusted findings, effects, ids of memories that changed a result)."""
    labels = active_labels(memories)
    feedback = _latest(memories, "alert_feedback")
    adjusted, effects, used = [], [], set()
    for original in findings:
        finding = copy.deepcopy(original)
        before = finding.get("severity", "medium")
        severity, state, contexts, reasons = before, "open", [], []

        counterparty = finding.get("counterparty")
        label = labels.get(counterparty) if counterparty else None
        if label:
            severity = _step_down(severity)
            text = (f"You labelled {_short(counterparty)} as \"{label.envelope.value}\" on {label.envelope.created_at[:10]}. "
                    "Priority lowered one step; this label is your assertion and was not independently verified.")
            contexts.append(_context(label, text))
            reasons.append("counterparty_label")

        note = feedback.get(finding.get("transaction_digest", ""))
        if note:
            state = FEEDBACK_STATES[note.envelope.value]
            if note.envelope.value in ("expected", "incorrect"):
                severity = "low"
            elif SEVERITIES.index(severity) < 1:
                severity = "medium"
            reason = f" Reason: {note.envelope.reason}" if note.envelope.reason else ""
            contexts.append(_context(note, f"You marked this alert as {note.envelope.value.replace('_', ' ')} on {note.envelope.created_at[:10]}.{reason}"))
            reasons.append("alert_feedback")

        finding.update({
            "severity_without_memory": before,
            "severity": severity,
            "state": state,
            "memory_context": contexts,
            "memory_rule_version": MEMORY_RULE_VERSION if contexts else None,
        })
        if contexts:
            ids = [c["memory_id"] for c in contexts]
            used.update(ids)
            if severity != before or state != "open":
                effects.append({
                    "transaction_digest": finding.get("transaction_digest"),
                    "severity_before": before,
                    "severity_after": severity,
                    "state_after": state,
                    "because": reasons,
                    "memory_ids": ids,
                })
        adjusted.append(finding)
    return sort_by_priority(adjusted), effects, used
