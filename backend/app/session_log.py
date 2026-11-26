"""Session log structure + honest end-of-session report generation.

The report is derived purely from the accumulated log — no attendance
figures, no invented data. See product guardrails in the build spec.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from . import config


def new_session_record(
    session_id: str, unit_id: str, unit_name: str, started_at: float, total_chunks: int = 0
) -> Dict[str, Any]:
    session = {
        "id": session_id,
        "unit_id": unit_id,
        "unit_name": unit_name,
        "started_at": started_at,
        "ended_at": None,
        "ai_label": config.AI_LABEL,
        # Snapshotted at session start so the report can compute coverage
        # (topics_covered / topics_total below) purely from the persisted
        # log, without needing the in-memory SessionRuntime — works the
        # same whether the report is requested for an active session or
        # loaded from disk after the session ended.
        "total_chunks": total_chunks,
        "transcript": [],
        "log": [],
    }
    log_event(session, "session_start", unit_id=unit_id, unit_name=unit_name)
    return session


def log_event(
    session: Dict[str, Any], event_type: str, timestamp: float | None = None, **fields: Any
) -> Dict[str, Any]:
    event = {"type": event_type, "timestamp": timestamp if timestamp is not None else time.time(), **fields}
    session["log"].append(event)
    return event


def _fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def generate_report(session: Dict[str, Any]) -> Dict[str, Any]:
    started_at = session["started_at"]
    ended_at = session["ended_at"] or time.time()
    duration_seconds = max(0.0, ended_at - started_at)

    questions = [e for e in session["log"] if e["type"] == "question_generated"]
    topic_matches = [e for e in session["log"] if e["type"] == "topic_match"]
    notes = [e for e in session["log"] if e["type"] == "teacher_note"]

    topics_covered_preview = []
    seen = set()
    for m in topic_matches:
        for c in m.get("top_chunks", []):
            key = c["chunk_id"]
            if key not in seen:
                seen.add(key)
                topics_covered_preview.append(c["preview"])

    # Coverage: which unit chunks were actually the basis of a fired
    # question this session — mirrors SessionRuntime.asked_chunk_ids, but
    # derived purely from the persisted log (topic_chunk_ids on each
    # question_generated event), so this works identically for an active
    # session or one already ended and reloaded from disk. This is
    # deliberately topic/content coverage, never attendance or
    # participation — "X of Y unit topics were touched," full stop.
    covered_chunk_ids = set()
    for q in questions:
        covered_chunk_ids.update(q.get("topic_chunk_ids", []))

    # Audit summary of the AI controller's own behaviour (agent mode):
    # how often it was consulted and what it chose. About the AI only —
    # nothing here describes students.
    decisions = [e for e in session["log"] if e["type"] == "agent_decision"]
    by_action: Dict[str, int] = {}
    for d in decisions:
        by_action[d.get("action", "unknown")] = by_action.get(d.get("action", "unknown"), 0) + 1
    ai_decisions = {
        "consulted": len(decisions),
        "by_action": by_action,
        "fallbacks": sum(1 for d in decisions if d.get("source") == "fallback"),
        "vetoed": sum(1 for e in session["log"] if e["type"] == "agent_veto"),
        "rejected_off_topic": sum(1 for e in session["log"] if e["type"] == "question_rejected"),
    }

    return {
        "session_id": session["id"],
        "unit_id": session["unit_id"],
        "unit_name": session["unit_name"],
        "ai_label": session["ai_label"],
        "started_at": started_at,
        "ended_at": ended_at,
        "started_at_iso": _fmt_ts(started_at),
        "ended_at_iso": _fmt_ts(ended_at),
        "duration_seconds": duration_seconds,
        "duration_minutes": round(duration_seconds / 60, 1),
        "topic_match_count": len(topic_matches),
        "topics_covered_preview": topics_covered_preview,
        "topics_covered": len(covered_chunk_ids),
        "topics_total": session.get("total_chunks", 0),
        "questions": [
            {
                "timestamp": q["timestamp"],
                "timestamp_iso": _fmt_ts(q["timestamp"]),
                "question": q["question"],
                "trigger_reason": q.get("trigger_reason"),
                "shown": q.get("shown", True),
                "slide_informed": q.get("slide_informed", False),
                "wrap_up": q.get("wrap_up", False),
                "audience": q.get("audience", "teacher"),
                "agent_reason": q.get("agent_reason"),
            }
            for q in questions
        ],
        "ai_decisions": ai_decisions,
        "teacher_notes": [
            {"timestamp": n["timestamp"], "timestamp_iso": _fmt_ts(n["timestamp"]), "text": n["text"]}
            for n in notes
        ],
    }


def render_report_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Doubt-Clearing Session Report")
    lines.append("")
    lines.append(f"**AI participant:** {report['ai_label']} (one clearly-labeled AI assistant; no attendance claims below)")
    lines.append(f"- Session ID: `{report['session_id']}`")
    lines.append(f"- Unit: {report['unit_name']}")
    lines.append(f"- Start: {report['started_at_iso']}")
    lines.append(f"- End: {report['ended_at_iso']}")
    lines.append(f"- Duration: {report['duration_minutes']} minutes")
    lines.append(f"- Unit coverage: {report['topics_covered']} of {report['topics_total']} unit topics touched")
    lines.append("")
    lines.append(f"## Topics matched ({report['topic_match_count']} topic-match events)")
    if report["topics_covered_preview"]:
        for preview in report["topics_covered_preview"]:
            lines.append(f"- {preview}")
    else:
        lines.append("- (no topic matches recorded)")
    lines.append("")
    lines.append(f"## Questions asked by the AI co-host ({len(report['questions'])})")
    if report["questions"]:
        for q in report["questions"]:
            reason = f" _(trigger: {q['trigger_reason']})_" if q.get("trigger_reason") else ""
            slide_tag = " _(slide-informed)_" if q.get("slide_informed") else ""
            wrap_up_tag = " _(wrap-up)_" if q.get("wrap_up") else ""
            class_tag = " _(to the class)_" if q.get("audience") == "class" else ""
            lines.append(f"- [{q['timestamp_iso']}] {q['question']}{reason}{slide_tag}{wrap_up_tag}{class_tag}")
            if q.get("agent_reason"):
                lines.append(f"  - Why the AI asked: {q['agent_reason']}")
    else:
        lines.append("- (no questions were generated this session)")
    decisions = report.get("ai_decisions") or {}
    if decisions.get("consulted"):
        lines.append("")
        lines.append("## AI controller decisions")
        actions = ", ".join(f"{a}: {n}" for a, n in sorted(decisions.get("by_action", {}).items()))
        lines.append(f"- Consulted {decisions['consulted']} times ({actions})")
        lines.append(
            f"- Fallbacks to the pacing rules: {decisions.get('fallbacks', 0)}; "
            f"vetoed by code checks: {decisions.get('vetoed', 0)}; "
            f"questions dropped as off-topic: {decisions.get('rejected_off_topic', 0)}"
        )
    lines.append("")
    lines.append(f"## Teacher notes ({len(report['teacher_notes'])})")
    if report["teacher_notes"]:
        for n in report["teacher_notes"]:
            lines.append(f"- [{n['timestamp_iso']}] {n['text']}")
    else:
        lines.append("- (none added)")
    return "\n".join(lines)
