"""The evidence JSON must match docs/research/EVIDENCE.md, and every entry must be complete."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_evidence", ROOT / "scripts" / "build_evidence.py")
build_evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_evidence)


def test_evidence_json_is_up_to_date():
    assert build_evidence.TARGET.read_text(encoding="utf-8") == build_evidence.build(), \
        "Run: python3 scripts/build_evidence.py"


def test_every_entry_is_complete_and_unique():
    entries = build_evidence.parse(build_evidence.SOURCE.read_text(encoding="utf-8"))
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))
    for e in entries:
        assert e["grade"] in "ABC" and e["citation"] and e["use"], e["id"]
        assert "(" in e["citation"] and ")" in e["citation"], e["id"]  # has a year
