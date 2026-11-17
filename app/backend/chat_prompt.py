"""
Prompt building and reply post-processing for the Grove coach.

Everything here is pure (no DB access) so it is easy to test. main.py builds a
"learner snapshot" dict and passes it in.
"""
import re
from typing import Dict, List, Optional, Tuple

FOLLOWUP_MARKER = "<<<FOLLOWUPS>>>"

ARCHETYPE_LABELS = {
    "needs more explanations": "Needs more explanations",
    "the skeptic": "The Skeptic",
    "trying not to get worse": "Trying not to get worse",
    "all in until i'm not": "All in until I'm not",
}

# Each learning style is a concrete answer *shape*, not just a tone, so the four
# styles look clearly different on screen. Word budgets are for normal answers;
# quiz turns keep the same voice but stay short.
ARCHETYPE_STYLES = {
    "needs more explanations": {
        "who": "wants things explained slowly and simply, and may feel lost with medical language",
        "voice": "warm, patient, encouraging; never condescending",
        "shape": (
            "1. Start with one plain-language sentence that answers the question.\n"
            "2. Then a line starting with \"Think of it like this:\" giving one everyday analogy.\n"
            "3. Then 2–4 short numbered steps or points. Define every medical word in parentheses the first time, e.g. \"resistance (when germs stop responding to a medicine)\".\n"
            "4. End with a gentle check-in such as \"Does that make sense, or should I explain it another way?\""
        ),
        "length": "120–200 words",
        "avoid": "jargon without a definition, long paragraphs, more than one idea per sentence",
    },
    "the skeptic": {
        "who": "wants to know *why* before trusting advice, and dislikes being told what to do without reasons",
        "voice": "calm, straight, respectful, evidence-minded; no cheerleading and no exclamation marks",
        "shape": (
            "1. Start with \"**Short answer:**\" and the bottom line in one sentence.\n"
            "2. Then \"**Why:**\" explaining the mechanism (what actually happens in the body or to the bacteria/enzyme).\n"
            "3. Then \"**What the evidence says:**\" summarizing what clinical guidelines or research generally support, in general terms. Never invent statistics, study names or citations.\n"
            "4. If there is real nuance or debate (for example, newer research on shorter antibiotic courses), say so honestly, and say who should make the call (their prescriber)."
        ),
        "length": "130–220 words",
        "avoid": "vague reassurance (\"just trust your doctor\"), rules without reasons, hype",
    },
    "trying not to get worse": {
        "who": "is worried about their health getting worse and wants to know how to stay safe",
        "voice": "calm, practical and reassuring; safety-first but never alarming",
        "shape": (
            "1. Start with \"**Bottom line:**\" in one sentence.\n"
            "2. Then \"**What to do:**\" with 2–4 concrete actions as bullets.\n"
            "3. Then \"**Watch for:**\" with the warning signs that mean they should call their doctor or pharmacist, and any emergency signs that mean calling 911.\n"
            "4. Optionally one reassuring closing line."
        ),
        "length": "90–170 words",
        "avoid": "scary wording, long explanations of mechanisms, anything that sounds like a diagnosis",
    },
    "all in until i'm not": {
        "who": "is motivated but has a short attention span and drops off if things get long",
        "voice": "brief, upbeat, direct, like a coach",
        "shape": (
            "1. One bold sentence that answers the question.\n"
            "2. At most 3 bullets, each 12 words or fewer.\n"
            "3. No introduction, no filler, no summary, and no closing question unless you are quizzing them."
        ),
        "length": "60 words maximum (hard limit)",
        "avoid": "headings, paragraphs longer than two lines, repeating the question back",
    },
}

LEVEL_STYLES = {
    "beginner": "Assume no medical background. Everyday words only.",
    "intermediate": "They know the basics; you can use common medical terms, briefly defined.",
    "advanced": "They are comfortable with clinical terms; you can name drug classes, mechanisms and pharmacology directly.",
}

PAGE_CONTEXTS = {
    "home": "the home page",
    "intake": "their health-profile (intake) form",
    "path": "their learning path overview",
    "progress": "their progress page",
    "chatbot": "the full-screen chatbot",
    "focused": "the Focused learning mode lesson list",
    "game": "the Game learning mode lesson map",
    "lesson": "a lesson",
    "chat-quiz": "a conversational quiz",
}

CONFUSED = re.compile(
    r"\b(i\s*(do\s*not|don'?t|dont)\s*(get|understand)|confus|lost me|i'?m lost|makes? no sense|what does that mean|"
    r"simpler|too (long|complicated|much)|explain (it )?again|eli5|huh)\b", re.I)
WANTS_DEPTH = re.compile(r"\b(more detail|go deeper|in depth|more technical|be specific|why exactly|mechanism|tell me more|elaborate)\b", re.I)
WANTS_SHORT = re.compile(r"\b(tl;?dr|shorter|short version|briefly|in short|too long|just tell me|bottom line)\b", re.I)


def normalize_archetype(value: Optional[str]) -> str:
    value = (value or "").strip().lower()
    for ch in ("’", "‘", "`"):
        value = value.replace(ch, "'")
    return value if value in ARCHETYPE_STYLES else "needs more explanations"


def normalize_level(value: Optional[str]) -> str:
    value = (value or "").lower()
    if "advanced" in value:
        return "advanced"
    if "intermediate" in value:
        return "intermediate"
    return "beginner"


def describe_page(page_context: Optional[str]) -> str:
    """page_context looks like "lesson:Dosage" or "path"."""
    if not page_context:
        return ""
    page, _, detail = page_context.partition(":")
    label = PAGE_CONTEXTS.get(page.strip().lower())
    if not label:
        return ""
    detail = re.sub(r"[^A-Za-z0-9 _-]", "", detail)[:40].strip()
    if detail:
        return f"The learner is currently on {label} (unit: {detail})."
    return f"The learner is currently on {label}."


def conversation_signals(user_messages: List[str]) -> List[str]:
    """Live adaptation from what the learner has said in this conversation."""
    recent = [m for m in user_messages[-4:] if m]
    last = recent[-1] if recent else ""
    notes = []
    confused_count = sum(1 for m in recent if CONFUSED.search(m))
    if CONFUSED.search(last):
        notes.append("They just said they are confused. Re-explain more simply than before, with a NEW analogy and shorter sentences. Do not repeat your previous explanation.")
    elif confused_count >= 2:
        notes.append("They have been confused more than once recently. Keep explanations one level simpler than their stated experience level.")
    if WANTS_DEPTH.search(last):
        notes.append("They asked for more depth. Go one level more detailed than usual (still in their style).")
    if WANTS_SHORT.search(last):
        notes.append("They asked for it shorter. Halve your usual length.")
    if len(last) <= 25 and recent and not notes:
        notes.append("Their messages are short; keep your reply compact.")
    return notes


def format_progress(snapshot: Dict) -> str:
    lines = []
    units = snapshot.get("units") or []
    if units:
        parts = []
        for u in units:
            status = {"done": "complete", "in_progress": "in progress", "open": "not started", "locked": "locked"}[u["status"]]
            parts.append(f"{u['category']} {u['mastered']}/{u['total']} ({status})")
        lines.append("Learning path units: " + "; ".join(parts))
    lines.append(f"Objectives mastered: {snapshot.get('mastered_count', 0)} of {snapshot.get('total_objectives', 0)}")
    if snapshot.get("next_unit"):
        lines.append(f"Suggested next unit: {snapshot['next_unit']}")
    lines.append(
        f"XP: {snapshot.get('xp', 0)} · Day streak: {snapshot.get('streak', 0)} · Hearts: {snapshot.get('hearts', 5)}/5"
        + (f" · Badges: {', '.join(snapshot['badges'])}" if snapshot.get("badges") else "")
    )
    struggling = snapshot.get("struggling") or []
    if struggling:
        lines.append("Concepts they are struggling with: " + "; ".join(f"{s['title']} ({s['category']})" for s in struggling[:5]))
    else:
        lines.append("Concepts they are struggling with: none flagged yet")
    missed = snapshot.get("missed_questions") or []
    if missed:
        lines.append("Recently missed quiz questions: " + " | ".join(f"\"{q}\"" for q in missed[:4]))
    return "\n".join(f"- {line}" for line in lines)


def format_curriculum(objectives, focus_oid: Optional[str], level: str) -> str:
    """Compact curriculum outline so answers stay grounded in the course content."""
    rows = []
    for obj in objectives:
        text = obj.lesson_text
        if isinstance(text, dict):
            text = text.get(level) or text.get("beginner") or next(iter(text.values()), "")
        text = re.sub(r"\s+", " ", str(text or "")).strip()
        marker = " ← MOST RELEVANT TO THIS QUESTION" if obj.oid == focus_oid else ""
        rows.append(f"[{obj.oid} · {obj.category}] {obj.objective_text}{marker}\n  Key facts: {text}")
    return "\n".join(rows)


def format_style(archetype: str, level: str) -> str:
    s = ARCHETYPE_STYLES[archetype]
    return (
        f"The learner picked the style **{ARCHETYPE_LABELS[archetype]}**: someone who {s['who']}.\n"
        f"Voice: {s['voice']}.\n"
        f"Every answer MUST follow this shape:\n{s['shape']}\n"
        f"Length: {s['length']}.\n"
        f"Avoid: {s['avoid']}.\n"
        f"Experience level: {level}. {LEVEL_STYLES[level]}\n"
        "The four learning styles in this app must produce visibly different answers, so stick to this shape on every "
        "turn (including follow-ups), unless the learner explicitly asks for a different format. "
        "When you are quizzing them, keep the voice but drop the shape: ask one question at a time."
    )


def build_system_prompt(snapshot: Dict, objectives, focus_oid: Optional[str], page_context: Optional[str],
                        other_drugs: List[str], user_messages: Optional[List[str]] = None,
                        quiz_question: Optional[str] = None) -> str:
    archetype = normalize_archetype(snapshot.get("archetype"))
    level = normalize_level(snapshot.get("experience_level"))
    drug_name = snapshot.get("drug_name", "their medication")
    page = describe_page(page_context)
    intake = snapshot.get("intake_summary") or "The learner has not filled in their health profile yet."

    adapt = conversation_signals(user_messages or [])
    done_units = [u["category"] for u in snapshot.get("units") or [] if u["status"] == "done"]
    if done_units:
        adapt.append(f"They have completed the {', '.join(done_units)} unit(s): build on that knowledge instead of re-teaching basics.")
    if snapshot.get("struggling"):
        adapt.append("When a question touches a concept they struggle with, gently mention it, explain it from a new angle, and end with one short check-for-understanding question.")
    quiz = ""
    if quiz_question:
        clean_q = re.sub(r"\s+", " ", quiz_question)[:300]
        quiz = (f"\n# They are in the middle of a quiz\nThe quiz question they are answering is: \"{clean_q}\"\n"
                "Help them understand the idea, but do NOT state the answer to that quiz question outright. Give a hint or "
                "explain the underlying concept, then encourage them to try answering. Keep it short; they will go back to the quiz.\n")

    return f"""You are the Grove coach: a friendly, knowledgeable tutor inside Grove, a personal growth app. Right now you help people understand the topic they are studying (currently health and medication lessons). You are an educational tool, not a clinician.

# How to write for THIS learner (most important)
{format_style(archetype, level)}

# Adapt right now
{chr(10).join(f"- {a}" for a in adapt) if adapt else "- No special adjustments; follow their style."}
{quiz}
# Context
- Focused medication: {drug_name}{f" (the course also covers: {', '.join(other_drugs)})" if other_drugs else ""}
{f"- {page}" if page else ""}

## Health profile they submitted
{intake}

## Their learning progress for {drug_name}
{format_progress(snapshot)}

## Course content for {drug_name} (ground medication answers in this; you may add widely accepted general medical knowledge)
{format_curriculum(objectives, focus_oid, level)}

# Rules
1. Answer the actual question, in the learner's style above.
2. Personalize with their health profile and progress when relevant (allergies, other medications, kidney disease, pregnancy, lifestyle). Refer to it naturally ("since you mentioned..."). Never claim you cannot see their profile, and never invent profile details that are not listed.
3. Tutor, don't just answer: if they ask to be quizzed or to practice, ask ONE question at a time, wait for their answer, then say whether it is right, explain briefly, and offer the next one. When they answer a question you asked, give clear feedback first.
4. When it fits (not every message), point them to the next step in their learning path, e.g. the {snapshot.get('next_unit') or 'next'} unit.
5. Safety: if they describe emergency symptoms (trouble breathing, swelling of face/lips/throat, severe allergic reaction, chest pain, fainting, overdose), tell them to call 911 or local emergency services first. Never tell them to start, stop or change a prescribed dose; explain general guidance and tell them to confirm with their prescriber or pharmacist.
6. General health and wellness questions (diet, sleep, exercise) are welcome: give general guidance tailored to their profile. Off-topic questions: answer briefly and kindly, then steer back.
7. Formatting: Markdown in a chat bubble. **Bold** key terms, short paragraphs, lists for steps. No tables.

# Follow-up suggestions (required)
After your reply, on its own line write exactly {FOLLOWUP_MARKER} and then 2 or 3 short follow-up messages the learner might send next, one per line, in the learner's voice (max 60 characters each, no numbering, no quotes). If you just asked them a question, make these plausible answers or "Give me a hint".
"""


def build_topic_quiz_prompt(context, archetype=None, experience_level=None):
    style = format_style(normalize_archetype(archetype), normalize_level(experience_level))
    notes = "\n".join(f"- {unit}: {text}" for unit, text in context["notes"])
    question = context["quiz_question"]
    quiz_context = (
        f'Current quiz question: "{question}"\n'
        "Explain the concept or give a clue. Withhold the answer to the current quiz question and let the learner try."
        if question else "The learner is between quiz sections. Answer their question about the topic."
    )
    return f"""You are the Grove coach. Help the learner understand this health topic in plain language.
Topic: {context["topic"]}
Current skill: {context["unit"]}
{quiz_context}

{style}

Use these lesson notes as your source:
{notes}

Answer the learner's question briefly. For anything outside these notes, explain what the course covers and avoid guessing.
Give general education. Do not diagnose, interpret a personal reading, or recommend starting, stopping, or changing medication.
Direct personal health questions to a healthcare professional. If they describe possible emergency symptoms, tell them to call local emergency services first, even during the quiz.
Use short Markdown paragraphs or lists.
"""


def split_followups(text: str) -> Tuple[str, List[str]]:
    """Separates the reply from the follow-up suggestions the model appends."""
    if not text:
        return "", []
    idx = text.find(FOLLOWUP_MARKER)
    suggestions = []
    if idx == -1:
        # Tolerate a partially-written marker at the very end of a stream.
        partial = re.search(r"\n?<{1,3}F?O?L?L?O?W?U?P?S?>{0,3}\s*$", text)
        body = (text[: partial.start()] if partial else text).strip()
    else:
        body = text[:idx].strip()
        for line in text[idx + len(FOLLOWUP_MARKER):].splitlines():
            line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip().strip('"').strip()
            if line and len(line) <= 90 and line not in suggestions:
                suggestions.append(line)
    if not suggestions and body.rstrip().endswith("?"):
        # The model asked the learner something but skipped the suggestions.
        suggestions = ["Give me a hint", "I'm not sure, can you explain?"]
    return body, suggestions[:3]
