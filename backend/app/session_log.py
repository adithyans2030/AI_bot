"""Session log structure + honest end-of-session report generation.

The report is derived purely from the accumulated log — no attendance
figures, no invented data. See product guardrails in the build spec.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from . import config


def new_session_record(session_id: str, unit_id: str, unit_name: str, started_at: float) -> Dict[str, Any]:
    session = {
        "id": session_id,
        "unit_id": unit_id,
        "unit_name": unit_name,
        "started_at": started_at,
        "ended_at": None,
        "ai_label": config.AI_LABEL,
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

    topics_covered = []
    seen = set()
    for m in topic_matches:
        for c in m.get("top_chunks", []):
            key = c["chunk_id"]
            if key not in seen:
                seen.add(key)
                topics_covered.append(c["preview"])

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
        "topics_covered_preview": topics_covered,
        "questions": [
            {
                "timestamp": q["timestamp"],
                "timestamp_iso": _fmt_ts(q["timestamp"]),
                "question": q["question"],
                "trigger_reason": q.get("trigger_reason"),
                "shown": q.get("shown", True),
            }
            for q in questions
        ],
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
            lines.append(f"- [{q['timestamp_iso']}] {q['question']}{reason}")
    else:
        lines.append("- (no questions were generated this session)")
    lines.append("")
    lines.append(f"## Teacher notes ({len(report['teacher_notes'])})")
    if report["teacher_notes"]:
        for n in report["teacher_notes"]:
            lines.append(f"- [{n['timestamp_iso']}] {n['text']}")
    else:
        lines.append("- (none added)")
    return "\n".join(lines)
