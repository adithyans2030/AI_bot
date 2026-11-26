"""The AI controller: an LLM decides what AI Co-host does next, and code
decides whether it is allowed to.

"The AI proposes, the rules dispose."

    observe ──► precheck (code) ──► decide (LLM) ──► validate (code) ──► act
                   │ hard "no"         │ fails            │ veto
                   ▼                   ▼                  ▼
              stay silent      fall back to the     stay silent
              (LLM not called)  rules pacing gate

- precheck: limits that never need judgement (paused, a student talking,
  nothing to ground a question in, too soon, hourly budget spent, teacher
  mid-flow). When one applies, the LLM isn't even called.
- decide: the LLM sees the moment (recent transcript, silence, slide,
  coverage, time left, what was already asked) and picks ONE action from a
  fixed list. Free text never becomes an action.
- validate: vetoes choices that break a rule (e.g. wrap-up early in class).
- After a question is generated, session_manager also checks it is
  grounded in the course notes (MIN_GROUNDING_SCORE) and drops it if not.

This module holds no session state: session_manager builds the
Observation, keeps the counters, and carries out the action.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from . import config

STAY_SILENT = "stay_silent"
ASK_QUESTION = "ask_question"
ASK_THE_CLASS = "ask_the_class"
RUN_WRAP_UP = "run_wrap_up"
ACTIONS = (STAY_SILENT, ASK_QUESTION, ASK_THE_CLASS, RUN_WRAP_UP)

# Plain-language explanations for precheck outcomes, shown in the UI.
PRECHECK_MESSAGES = {
    "paused": "Paused by the teacher.",
    "student_speaking": "A student is speaking, so the co-host waits.",
    "no_content": "Nothing has been said yet to base a question on.",
    "cooldown": "A question was asked recently.",
    "budget": "This hour's question budget is used up.",
    "teacher_speaking": "The teacher is talking, so the co-host waits for a pause.",
    "recently_decided": "The co-host checked this moment a few seconds ago.",
}


@dataclass
class Observation:
    elapsed_minutes: float
    minutes_remaining: float
    silence_seconds: float
    seconds_since_last_question: float
    questions_asked: int
    questions_last_hour: int
    coverage_ratio: float
    recent_transcript: str
    slide_title: Optional[str] = None
    recently_asked: List[str] = field(default_factory=list)
    wrap_up_done: bool = False
    has_content: bool = True


@dataclass
class Decision:
    action: str
    reason: str
    # "agent": the LLM chose it. "guardrail": code decided or vetoed.
    # "fallback": the LLM was unavailable, the rules pacing gate decided.
    source: str

    def as_dict(self) -> dict:
        return {"action": self.action, "reason": self.reason, "source": self.source}


# --- Code checks ---


def precheck(
    obs: Observation,
    *,
    paused: bool,
    student_speaking: bool,
    seconds_since_last_decision: Optional[float],
) -> Optional[str]:
    """A reason code if the co-host must stay silent without asking the
    LLM at all, else None (this moment is worth a decision)."""
    if paused:
        return "paused"
    if student_speaking:
        return "student_speaking"
    if not obs.has_content:
        return "no_content"
    if obs.seconds_since_last_question < config.MIN_SECONDS_BETWEEN_QUESTIONS:
        return "cooldown"
    if obs.questions_last_hour >= config.MAX_QUESTIONS_PER_HOUR:
        return "budget"
    quiet = obs.silence_seconds >= config.CONTROLLER_MIN_SILENCE_SECONDS
    long_gap = obs.seconds_since_last_question >= config.PACING_MAX_INTERVAL_SECONDS
    if not (quiet or long_gap):
        return "teacher_speaking"
    if seconds_since_last_decision is not None and seconds_since_last_decision < config.CONTROLLER_RECONSULT_SECONDS:
        return "recently_decided"
    return None


def validate(decision: Decision, obs: Observation) -> Decision:
    """Veto choices that break a rule. Returns the decision to carry out."""
    if decision.action not in ACTIONS:
        return Decision(STAY_SILENT, "The AI chose an unknown action, so the co-host stays silent.", "guardrail")
    if decision.action == RUN_WRAP_UP:
        if obs.wrap_up_done:
            return Decision(STAY_SILENT, "Wrap-up already ran this session.", "guardrail")
        if obs.minutes_remaining > config.WRAP_UP_WINDOW_MINUTES:
            return Decision(
                STAY_SILENT,
                f"Wrap-up is only allowed in the last {config.WRAP_UP_WINDOW_MINUTES} minutes of class.",
                "guardrail",
            )
    return decision


# --- The LLM decision ---

SYSTEM_PROMPT = (
    "You are the decision-maker for \"AI Co-host\", a clearly labelled AI assistant "
    "in a live online college class. It keeps sessions from going silent by now and "
    "then asking a question about the course material, so the teacher is not left "
    "talking to a silent room. It never pretends to be a student.\n\n"
    "Each time you are consulted, choose exactly ONE action:\n"
    "- stay_silent: do nothing right now.\n"
    "- ask_question: ask the teacher one question about what they are teaching.\n"
    "- ask_the_class: invite the students to answer or discuss something, to get "
    "real students talking.\n"
    "- run_wrap_up: near the end of class, ask about an important part of the unit "
    "that has not been covered.\n\n"
    "Go through these checks IN ORDER, and use the first one that matches:\n"
    "1. The teacher's last words stop mid-sentence, or they are about to show, "
    "draw, write or read something (\"let me\", \"so here\", \"look at this\") -> "
    "stay_silent. Never interrupt a teacher who is in the middle of something.\n"
    "2. \"Wrap-up allowed now\" is YES and either the teacher says they are "
    "wrapping up or ending the class, or the class is quiet -> run_wrap_up.\n"
    "3. The teacher's last words ask the class something (\"any doubts?\", \"any "
    "questions?\", \"does that make sense?\") -> ask_question.\n"
    "4. The teacher has clearly finished explaining a concept and it has been "
    "quiet for 10 seconds or more -> ask_question.\n"
    "5. No question for 8 minutes or more and the teacher has done all the "
    "talking -> ask_the_class.\n"
    "6. Otherwise -> stay_silent.\n"
    "Nothing outside the course material.\n"
    "Timing limits, question budgets and student priority are enforced separately; "
    "you only judge whether this moment is a good one.\n\n"
    'Reply with JSON only, no other text: {"action": "<one of the four>", '
    '"reason": "<one short sentence>"}'
)


def build_user_prompt(obs: Observation) -> str:
    asked = "\n".join(f"- {q}" for q in obs.recently_asked[-5:]) or "(none yet)"
    slide = obs.slide_title or "(no slide shared)"
    transcript = obs.recent_transcript.strip() or "(nothing said recently)"
    # The teacher's last few words matter most for checks 2 and 3, and small
    # models attend to them better when they are pulled out separately.
    last_words = " ".join(transcript.split()[-25:])
    # Precomputed yes/no: small models misjudge arithmetic like "10 minutes
    # or fewer left", but follow an explicit flag reliably. Mirrors the
    # code check in validate(), so the AI isn't steered into a veto.
    wrap_up_allowed = not obs.wrap_up_done and obs.minutes_remaining <= config.WRAP_UP_WINDOW_MINUTES
    return (
        f"Wrap-up allowed now: {'YES' if wrap_up_allowed else 'NO'}\n"
        f"Class time: {obs.elapsed_minutes:.0f} min elapsed, about {obs.minutes_remaining:.0f} min left.\n"
        f"Silence since the teacher last spoke: {obs.silence_seconds:.0f} s.\n"
        f"Time since the co-host's last question: {obs.seconds_since_last_question / 60:.1f} min.\n"
        f"Questions asked so far: {obs.questions_asked}. "
        f"Share of the unit covered: {obs.coverage_ratio:.0%}.\n"
        f"Wrap-up already done: {'yes' if obs.wrap_up_done else 'no'}.\n"
        f"Slide on screen: {slide}\n\n"
        f"Topics the co-host already asked about:\n{asked}\n\n"
        f"What the teacher said in the last 90 seconds:\n{transcript}\n\n"
        f"The teacher's LAST words: \"...{last_words}\"\n\n"
        "Go through the checks in order and choose the action now."
    )


_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def parse_decision(text: str) -> Optional[Decision]:
    """Pull {"action", "reason"} out of the model's reply. Tolerates code
    fences and chatter around the JSON; anything unusable returns None."""
    if not text:
        return None
    match = _JSON_OBJECT.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    action = str(data.get("action", "")).strip().lower()
    if action not in ACTIONS:
        return None
    reason = " ".join(str(data.get("reason") or "No reason given.").split())[:200]
    return Decision(action, reason, "agent")


def decide(obs: Observation) -> Optional[Decision]:
    """Ask the LLM what to do. None if it is unreachable or its reply is
    unusable; the caller then falls back to the rules pacing gate."""
    from .question_gen import get_client  # same OpenAI-compatible client and server

    try:
        response = get_client().chat.completions.create(
            model=config.CONTROLLER_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(obs)},
            ],
            temperature=0.2,
            max_tokens=120,
        )
        return parse_decision(response.choices[0].message.content or "")
    except Exception:
        return None
