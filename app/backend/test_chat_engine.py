"""
Tests for the chatbot engine: prompt building, follow-up parsing, streaming,
history, and conversation ownership. The LLM is stubbed, so these run offline.

Run from app/backend:  ../../venv/bin/python -m pytest test_chat_engine.py -q
"""
import json
import os
import time
import uuid

import jwt

import pytest
from fastapi.testclient import TestClient

import account_cleanup
import chat_prompt
import llm
import main
import models
from database import SessionLocal


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def guest(client):
    data = client.post("/auth/guest").json()
    yield {"user": data["username"], "headers": {"X-Guest-Session": data["token"]}}
    client.delete("/auth/guest", headers={"X-Guest-Session": data["token"]})


@pytest.fixture
def fake_llm(monkeypatch):
    """Replaces the provider calls; records the prompt it was given."""
    calls = {}
    reply = "Amoxicillin is a **penicillin** antibiotic.\n\n- It treats bacterial infections\n- Not viral ones"
    full = reply + "\n" + chat_prompt.FOLLOWUP_MARKER + "\nHow do I take it?\nWhat are the side effects?\n"

    def fake_stream(system, messages):
        calls["system"], calls["messages"] = system, messages
        for i in range(0, len(full), 7):  # tiny chunks, so the marker arrives split
            yield full[i:i + 7]

    def fake_generate(system, messages):
        calls["system"], calls["messages"] = system, messages
        return full

    monkeypatch.setattr(main.llm, "is_configured", lambda: True)
    monkeypatch.setattr(main.llm, "stream", fake_stream)
    monkeypatch.setattr(main.llm, "generate", fake_generate)
    calls["reply"] = reply
    return calls


def stream_events(client, guest, **body):
    payload = {"username": guest["user"], "drug": "amoxicillin", **body}
    with client.stream("POST", "/chat/stream", json=payload, headers=guest["headers"]) as r:
        assert r.status_code == 200
        return [json.loads(line) for line in r.iter_lines() if line.strip()]


# ---------------------------------------------------------------- pure helpers

def test_split_followups_extracts_suggestions():
    body, sug = chat_prompt.split_followups("Answer here.\n<<<FOLLOWUPS>>>\n- First?\n2. Second one\n\"Third\"\nFourth")
    assert body == "Answer here."
    assert sug == ["First?", "Second one", "Third"]


def test_split_followups_without_marker_strips_partial_marker():
    body, sug = chat_prompt.split_followups("Answer here.\n<<<FOLL")
    assert body == "Answer here."
    assert sug == []


def test_split_followups_offers_hint_chips_after_a_question():
    _, sug = chat_prompt.split_followups("Which one is right?")
    assert sug == ["Give me a hint", "I'm not sure, can you explain?"]


def test_normalizers():
    assert chat_prompt.normalize_archetype("All In Until I’m Not") == "all in until i'm not"
    assert chat_prompt.normalize_archetype("nonsense") == "needs more explanations"
    assert chat_prompt.normalize_level("Advanced user") == "advanced"
    assert chat_prompt.normalize_level(None) == "beginner"


def test_describe_page_sanitizes_detail():
    assert "lesson" in chat_prompt.describe_page("lesson:Dosage")
    assert "<script>" not in chat_prompt.describe_page("lesson:<script>Dosage")
    assert chat_prompt.describe_page("unknown-page") == ""


def test_make_title():
    assert main.make_title("  short   question ") == "short question"
    long = main.make_title("word " * 30)
    assert len(long) <= 61 and long.endswith("…")


# ---------------------------------------------------------------- API

def test_context_has_progress_and_starters(client, guest):
    r = client.get(f"/chat/context/amoxicillin?username={guest['user']}", headers=guest["headers"])
    assert r.status_code == 200
    ctx = r.json()
    assert ctx["drug_name"] == "Amoxicillin"
    assert ctx["total_objectives"] > 0 and ctx["next_unit"]
    assert 2 <= len(ctx["starter_prompts"]) <= 4
    assert {d["key"] for d in ctx["drugs"]} >= {"amoxicillin", "ibuprofen"}
    assert "_profile" not in ctx and "intake_summary" not in ctx


def test_stream_hides_marker_and_returns_suggestions(client, guest, fake_llm):
    events = stream_events(client, guest, message="What is amoxicillin?", page_context="lesson:Facts")
    assert events[0]["type"] == "meta" and events[0]["conversation_id"]
    deltas = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "<<<" not in deltas and "How do I take it?" not in deltas
    done = events[-1]
    assert done["type"] == "done"
    assert done["response"] == fake_llm["reply"]
    assert done["suggestions"] == ["How do I take it?", "What are the side effects?"]
    assert done["conversation_title"] == "What is amoxicillin?"
    # The prompt is personalized and grounded in the course.
    assert "Learning path units" in fake_llm["system"]
    assert "(unit: Facts)" in fake_llm["system"]
    assert "[F1" in fake_llm["system"]


def test_history_is_multi_turn_and_persisted(client, guest, fake_llm):
    first = stream_events(client, guest, message="What is amoxicillin?")
    conv = first[0]["conversation_id"]
    stream_events(client, guest, message="And how do I take it?", conversation_id=conv)
    # Second call received the earlier exchange as real chat turns.
    roles = [m["role"] for m in fake_llm["messages"]]
    assert roles == ["user", "assistant", "user"]

    rows = client.get(f"/chat/history/{guest['user']}?conversation_id={conv}", headers=guest["headers"]).json()
    assert [r["sender"] for r in rows] == ["user", "bot", "user", "bot"]
    convs = client.get(f"/conversations/{guest['user']}", headers=guest["headers"]).json()
    assert len(convs) == 1 and convs[0]["conversation_id"] == conv


def test_safety_warning_survives_history_reload(client, guest, fake_llm):
    events = stream_events(client, guest, message="Can I take amoxicillin with warfarin?")
    assert "Warfarin" in (events[0]["safety_warning"] or "")
    conv = events[0]["conversation_id"]
    rows = client.get(f"/chat/history/{guest['user']}?conversation_id={conv}", headers=guest["headers"]).json()
    bot = [r for r in rows if r["sender"] == "bot"][0]
    assert "Warfarin" in bot["safety_warning"]


def test_falls_back_to_rule_based_answer_when_llm_fails(client, guest, monkeypatch):
    monkeypatch.setattr(main.llm, "is_configured", lambda: True)
    monkeypatch.setattr(main.llm, "stream", lambda s, m: iter(()))
    events = stream_events(client, guest, message="hello")
    assert events[-1]["type"] == "done"
    assert events[-1]["response"]  # the offline small-talk answer


def test_non_streaming_chat_still_works(client, guest, fake_llm):
    r = client.post("/chat", headers=guest["headers"],
                    json={"username": guest["user"], "message": "What is amoxicillin?", "drug": "amoxicillin", "archetype": "The Skeptic"})
    assert r.status_code == 200
    data = r.json()
    assert data["response"] == fake_llm["reply"]
    assert data["suggestions"]
    assert "**Short answer:**" in fake_llm["system"]  # The Skeptic's answer shape


def test_rename_and_delete(client, guest, fake_llm):
    conv = stream_events(client, guest, message="What is amoxicillin?")[0]["conversation_id"]
    r = client.patch(f"/conversations/{conv}", json={"title": "  Amoxicillin basics  "}, headers=guest["headers"])
    assert r.status_code == 200 and r.json()["title"] == "Amoxicillin basics"
    assert client.delete(f"/conversations/{conv}", headers=guest["headers"]).status_code == 200
    assert client.get(f"/conversations/{guest['user']}", headers=guest["headers"]).json() == []
    assert client.delete(f"/conversations/{conv}", headers=guest["headers"]).status_code == 404


@pytest.fixture
def accounts():
    """Signed-in test accounts (same local test tokens as the sprint scripts); deleted afterwards."""
    made = []

    def make():
        email = f"pytest.{uuid.uuid4().hex[:10]}@example.test"
        made.append(email)
        return email, {"Authorization": f"Bearer {signed_token(email)}"}
    yield make
    with SessionLocal() as db:
        for email in made:
            account_cleanup.delete_user(db, email)
        db.commit()


def signed_token(email):
    return jwt.encode({
        "email": email, "cognito:username": email, "sub": email, "exp": time.time() + 600,
        "iss": f"https://cognito-idp.{os.getenv('COGNITO_REGION', 'us-east-2')}.amazonaws.com/{os.getenv('COGNITO_USER_POOL_ID', 'us-east-2_TestPool')}",
    }, "test-secret-key-123456789012345678901234", algorithm="HS256")


def test_signed_out_requests_are_refused_and_create_no_account(client):
    before = _user_count()
    for headers in ({}, {"X-Dev-User": "pytest_fake_user"}):
        r = client.post("/chat", headers=headers, json={"username": "pytest_fake_user", "message": "hi", "drug": "amoxicillin"})
        assert r.status_code == 401
        assert client.get("/chat/context/amoxicillin?username=pytest_fake_user", headers=headers).status_code == 401
    assert _user_count() == before


def test_body_username_cannot_impersonate_another_user(client, accounts, fake_llm):
    owner, owner_h = accounts()
    other, other_h = accounts()
    conv = client.post("/chat", headers=owner_h, json={"username": owner, "message": "What is amoxicillin?", "drug": "amoxicillin"}).json()["conversation_id"]
    # The other account asks for the owner's data by name: it only ever gets its own.
    assert client.get(f"/conversations/{owner}", headers=other_h).json() == []
    assert client.get(f"/chat/history/{owner}?conversation_id={conv}", headers=other_h).json() == []
    r = client.post("/chat", headers=other_h, json={"username": owner, "message": "hello", "drug": "amoxicillin", "conversation_id": conv})
    assert r.json()["conversation_id"] != conv  # can't post into someone else's thread


def test_cannot_delete_someone_elses_conversation(client, accounts, fake_llm):
    owner, owner_h = accounts()
    other, other_h = accounts()
    r = client.post("/chat", headers=owner_h, json={"username": owner, "message": "What is amoxicillin?", "drug": "amoxicillin"})
    conv = r.json()["conversation_id"]
    assert client.delete(f"/conversations/{conv}", headers=other_h).status_code == 404
    a_guest = client.post("/auth/guest").json()
    assert client.delete(f"/conversations/{conv}", headers={"X-Guest-Session": a_guest["token"]}).status_code == 404
    assert any(c["conversation_id"] == conv for c in client.get(f"/conversations/{owner}", headers=owner_h).json())


def _user_count():
    with SessionLocal() as db:
        return db.query(models.User).count()


# ---------------------------------------------------------------- archetypes + adaptation

@pytest.mark.parametrize("archetype,marker", [
    ("Needs more explanations", "Think of it like this:"),
    ("The Skeptic", "**Short answer:**"),
    ("Trying not to get Worse", "**What to do:**"),
    ("All In Until I'm Not", "60 words maximum"),
])
def test_each_archetype_gets_its_own_answer_shape(archetype, marker):
    snapshot = {"archetype": archetype, "experience_level": "beginner", "drug_name": "Amoxicillin", "units": []}
    prompt = chat_prompt.build_system_prompt(snapshot, [], None, None, [])
    assert marker in prompt
    others = [m for a, m in [("n", "Think of it like this:"), ("s", "**Short answer:**"),
                             ("t", "**What to do:**"), ("a", "60 words maximum")] if m != marker]
    assert not any(o in prompt for o in others)


def test_conversation_signals_adapt_to_the_learner():
    assert any("NEW analogy" in n for n in chat_prompt.conversation_signals(["what is it", "I don't understand"]))
    assert any("more detailed" in n for n in chat_prompt.conversation_signals(["Can you go deeper on the mechanism?"]))
    assert any("Halve" in n for n in chat_prompt.conversation_signals(["shorter please, just tell me"]))
    assert chat_prompt.conversation_signals([]) == []


def test_quiz_question_is_not_given_away():
    snapshot = {"archetype": "the skeptic", "drug_name": "Amoxicillin", "units": []}
    prompt = chat_prompt.build_system_prompt(snapshot, [], None, "chat-quiz:Facts", [], quiz_question="Is amoxicillin an antibiotic?")
    assert "Is amoxicillin an antibiotic?" in prompt and "do NOT state the answer" in prompt


def test_saved_learning_style_reaches_the_chat_prompt(client, guest, fake_llm):
    r = client.post("/preferences", json={"username": guest["user"], "archetype": "All In Until I'm Not"}, headers=guest["headers"])
    assert r.status_code == 200 and r.json()["archetype"] == "All in until I'm not"
    ctx = client.get(f"/chat/context/amoxicillin?username={guest['user']}", headers=guest["headers"]).json()
    assert ctx["archetype"] == "all in until i'm not" and ctx["archetype_label"] == "All in until I'm not"
    stream_events(client, guest, message="What is amoxicillin?")  # no archetype sent, like the widget
    assert "60 words maximum" in fake_llm["system"]


def test_chat_without_archetype_keeps_saved_style(client, guest, fake_llm):
    client.post("/preferences", json={"username": guest["user"], "archetype": "The Skeptic"}, headers=guest["headers"])
    client.post("/chat", headers=guest["headers"], json={"username": guest["user"], "message": "hi", "drug": "amoxicillin",
                                                          "page_context": "chat-quiz:Facts", "quiz_question": "Q?"})
    ctx = client.get(f"/chat/context/amoxicillin?username={guest['user']}", headers=guest["headers"]).json()
    assert ctx["archetype"] == "the skeptic"


def test_preferences_rejects_unknown_style(client, guest):
    r = client.post("/preferences", json={"username": guest["user"], "archetype": "pirate"}, headers=guest["headers"])
    assert r.status_code == 400
