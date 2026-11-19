"""Build app/frontend/data/evidence.json from docs/research/EVIDENCE.md.

The Markdown file is the single source of truth. Run after editing it:
    python3 scripts/build_evidence.py
A test (test_evidence.py) fails if the JSON is out of date.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "research" / "EVIDENCE.md"
TARGET = ROOT / "app" / "frontend" / "data" / "evidence.json"

HEADING = re.compile(r"^### (?P<id>[A-Z]+-\d+) · (?P<title>.+?) · \*\*(?P<grade>[ABC])\*\*\s*$")


def plain(text):
    """Markdown emphasis to plain text."""
    return re.sub(r"\*\*?(.+?)\*\*?", r"\1", text).strip()


def parse(markdown):
    entries, category, current = [], None, None
    for line in markdown.splitlines():
        if line.startswith("## ") and not line.startswith("## Grades"):
            category = line[3:].strip()
            continue
        match = HEADING.match(line)
        if match:
            current = {"id": match["id"], "title": match["title"], "grade": match["grade"],
                       "category": category, "citation": "", "finding": "", "use": ""}
            entries.append(current)
            continue
        if current is None or not line.strip() or line.startswith(("---", "## ")):
            if line.startswith("## "):
                current = None
            continue
        bullet = re.match(r"^- \*\*(Finding|Guideline|We use it for|Use):\*\* (.+)$", line)
        if bullet:
            key = "use" if bullet[1] in ("We use it for", "Use") else "finding"
            current[key] = plain(bullet[2])
        elif line.startswith("  ") and current:
            last = "use" if current["use"] else "finding"
            current[last] = (current[last] + " " + plain(line)).strip()
        elif not line.startswith("-"):
            current["citation"] = (current["citation"] + " " + plain(line)).strip()
    return entries


def build():
    entries = parse(SOURCE.read_text(encoding="utf-8"))
    return json.dumps({"source": "docs/research/EVIDENCE.md", "entries": entries}, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(build(), encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(ROOT)} ({len(json.loads(build())['entries'])} entries)")
    sys.exit(0)
