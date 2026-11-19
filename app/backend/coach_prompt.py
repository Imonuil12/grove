"""System prompt, evidence grounding and offline answers for the Grove coach.

Pure functions only (no database), so they are easy to test. The evidence comes
from app/frontend/data/evidence.json, which is generated from
docs/research/EVIDENCE.md (see the research-backed skill).
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

EVIDENCE_PATH = Path(__file__).resolve().parents[1] / "frontend" / "data" / "evidence.json"
FOLLOWUP_MARKER = "<<<FOLLOWUPS>>>"

PAGES = {
    "today": "the Today page (their daily overview)",
    "habits": "the Habits page",
    "books": "the Books page",
    "training": "the Training page",
    "feed": "the Feed",
    "profile": "their Profile",
}


@lru_cache(maxsize=1)
def evidence() -> List[Dict]:
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))["entries"]


def evidence_ids() -> set:
    return {entry["id"] for entry in evidence()}


def format_evidence() -> str:
    lines = []
    for e in evidence():
        if e["grade"] == "C":
            continue  # practitioner sources guide design but are not cited as research
        lines.append(f"- {e['id']} (grade {e['grade']}): {e['title']}. {e['finding']}".strip())
    return "\n".join(lines)


def build_system_prompt(name: Optional[str] = None, page: Optional[str] = None) -> str:
    where = PAGES.get((page or "").lower())
    return f"""You are the Grove coach. Grove helps people build habits for physical, cognitive and personal growth:
daily habits, reading, training, sleep, and focus. You are warm, direct and practical.

How you coach:
- Support the person's own choices; never shame or guilt them. A missed day is normal (HAB-1).
- Turn goals into small, specific plans written as "After I [cue], I will [tiny action] at [place/time]" (HAB-2, HAB-3).
- Prefer one concrete next step over a list of ten ideas.
- Keep answers short: usually under 150 words, plain language, short paragraphs or a few bullets.

Research rules (Grove's promise is that advice is research-backed):
- Base factual claims on the evidence list below and cite the ID in parentheses, like (HAB-2).
- Only cite IDs from the list. Never invent studies, authors, numbers or IDs.
- If something isn't covered, say it's general guidance rather than research Grove has reviewed.
- Match the strength of the evidence: "a study found" for single studies, and mention the population when it matters.

Safety:
- You are not a doctor. Don't diagnose, don't advise on medication, and don't suggest extreme diets or
  very low calorie targets. For injuries, pain, pregnancy, eating disorders, or medical conditions,
  encourage talking to a qualified professional.
- If someone mentions self-harm or a crisis, respond with care and urge them to contact local emergency
  services or a crisis line right away.

Grove's features (some are still being built, say so if asked): Habits with reminders, Books with recall
questions, Training with workouts and body metrics, a weekly review from you, and a Feed for milestones.

{"The person is on " + where + "." if where else ""}{" Their name is " + name + "." if name else ""}

Evidence list:
{format_evidence()}

After your answer, add a line with exactly {FOLLOWUP_MARKER} and then up to 3 short follow-up questions the
person might tap next, one per line, each under 60 characters. Nothing after them."""


def split_followups(text: str) -> Tuple[str, List[str]]:
    """Separates the reply from the follow-up suggestions the model appends."""
    if not text:
        return "", []
    idx = text.find(FOLLOWUP_MARKER)
    suggestions: List[str] = []
    if idx == -1:
        # Tolerate a partially written marker at the very end of a stream.
        partial = re.search(r"\n?<{1,3}F?O?L?L?O?W?U?P?S?>{0,3}\s*$", text)
        body = (text[: partial.start()] if partial else text).strip()
    else:
        body = text[:idx].strip()
        for line in text[idx + len(FOLLOWUP_MARKER):].splitlines():
            line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip().strip('"').strip()
            if line and len(line) <= 90 and line not in suggestions:
                suggestions.append(line)
    return body, suggestions[:3]


def cited_ids(text: str) -> List[str]:
    """Evidence IDs the reply cites, in order, limited to real ones."""
    known, seen = evidence_ids(), []
    for match in re.findall(r"\b([A-Z]{2,4}-\d+)\b", text or ""):
        if match in known and match not in seen:
            seen.append(match)
    return seen


# Offline answers, used when no AI provider is configured or reachable.
OFFLINE_TOPICS = [
    (("habit", "routine", "consisten", "streak", "motivat", "discipline"),
     "Start with one habit and make it tiny and specific. Write it as an if-then plan: "
     "\"After I pour my morning coffee, I will read two pages at the kitchen table.\" Plans like this "
     "clearly improve follow-through (HAB-2), and tying the habit to the same cue and place helps it "
     "become automatic (HAB-3). Expect it to take a while; in one study it took a median of 66 days, "
     "and missing a single day didn't hurt (HAB-1). So the rule is: never miss twice.",
     ["Help me write my first if-then plan", "What should my first habit be?"]),
    (("read", "book", "remember", "forget", "study", "learn"),
     "To remember what you read, test yourself instead of rereading. After a session, write two or "
     "three questions about what you just read and answer them from memory a few days later. "
     "Retrieval practice beats rereading (LRN-1), and spacing reviews out over days and weeks makes "
     "it stick longer (LRN-2).",
     ["How many pages a day should I read?", "Help me build a reading habit"]),
    (("run", "cardio", "walk", "5k", "jog", "active", "exercise"),
     "Aim for 150–300 minutes of moderate activity a week (or 75–150 vigorous), plus strength work on "
     "two or more days. That's the WHO guideline for adults (FIT-1). If you're new to running, start "
     "with run/walk intervals three times a week and build up slowly.",
     ["Plan my first week of runs", "How do I fit 150 minutes in?"]),
    (("strength", "lift", "gym", "workout", "muscle", "push-up", "pushup", "squat"),
     "Pick a few big movements and add a little difficulty over time: more reps, then more weight once "
     "you can beat your target reps. That's progressive overload (FIT-2). Two or more strength days a "
     "week meets the guideline (FIT-1).",
     ["Give me a simple 2-day plan", "How much protein do I need?"]),
    (("protein", "calorie", "diet", "eat", "nutrition", "weight", "fat"),
     "For people who strength train, a review found muscle gains leveled off around 1.6 g of protein "
     "per kg of body weight per day (FIT-3). If you track weight, look at the 7-day average rather "
     "than single days, since daily numbers swing (WT-1). For specific diet plans, a registered "
     "dietitian is the right person.",
     ["How do I track my weight trend?", "Ideas for easy protein"]),
    (("sleep", "tired", "rest", "bed"),
     "Adults need 7 or more hours of sleep a night (SLP-1). A good first habit: \"After I brush my "
     "teeth, I will put my phone on the charger outside the bedroom.\" Keep the same bedtime cue each "
     "night so it becomes automatic (HAB-3).",
     ["Help me build a bedtime routine", "What if I wake up at night?"]),
    (("meditat", "stress", "anxi", "calm", "mindful", "focus"),
     "A review of meditation programs found moderate evidence that mindfulness programs improve "
     "anxiety, depression and pain (MND-1). Start with two minutes after an existing routine, like "
     "right after your morning coffee. If stress is overwhelming, please talk to a professional.",
     ["Give me a 2-minute starter practice", "When is the best time to meditate?"]),
]

OFFLINE_DEFAULT = (
    "I'm your Grove coach. I can help you build habits, plan reading, set up training, sleep better "
    "and stay consistent, using methods that research supports. What's one thing you'd like to get "
    "better at this month?",
    ["Help me build a reading habit", "Plan my workouts for the week", "How do habits actually form?"],
)


def offline_reply(message: str) -> Tuple[str, List[str]]:
    text = (message or "").lower()
    for keywords, reply, suggestions in OFFLINE_TOPICS:
        if any(k in text for k in keywords):
            return reply, suggestions
    return OFFLINE_DEFAULT


def title_from(message: str) -> str:
    words = re.sub(r"\s+", " ", (message or "").strip()).split(" ")
    title = " ".join(words[:7])
    return (title[:60] + "…") if len(title) > 60 else (title or "New conversation")
