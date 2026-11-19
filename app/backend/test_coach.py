"""Coach: research grounding, offline answers, conversations and guest isolation."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

import coach_prompt
import encryption
import llm
import local_auth
import main
import models
from database import SessionLocal


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("COGNITO_USER_POOL_ID", raising=False)
    return TestClient(main.app)


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(llm, "is_configured", lambda: False)


@pytest.fixture
def account():
    email = f"coach.{uuid.uuid4().hex[:10]}@example.com"
    yield email, {"Authorization": f"Bearer {local_auth.issue_token(email)[0]}"}
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email=email).one_or_none()
        if user:
            db.delete(user)
            db.commit()


def events(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_prompt_cites_only_graded_evidence():
    prompt = coach_prompt.build_system_prompt(page="habits")
    assert "HAB-2" in prompt and "the Habits page" in prompt
    assert "RUN-1" not in prompt  # grade C sources are design input, not citations
    assert "medication" in prompt  # safety rule present
    assert "amoxicillin" not in prompt.lower()


def test_cited_ids_ignores_made_up_ids():
    assert coach_prompt.cited_ids("Plans help (HAB-2), see also (XYZ-9) and HAB-2 again, LRN-1.") == ["HAB-2", "LRN-1"]


def test_every_offline_answer_cites_real_evidence():
    for _, reply, _ in coach_prompt.OFFLINE_TOPICS:
        ids = coach_prompt.cited_ids(reply)
        assert ids, reply
        assert set(ids) <= coach_prompt.evidence_ids()


def test_split_followups():
    body, tips = coach_prompt.split_followups(f"Do this.\n{coach_prompt.FOLLOWUP_MARKER}\n- One?\n2. Two?\n")
    assert body == "Do this." and tips == ["One?", "Two?"]


def test_requires_identity(client):
    assert client.post("/coach/stream", json={"message": "hi"}).status_code == 401


def test_account_conversation_is_stored_encrypted(client, offline, account):
    email, headers = account
    out = events(client.post("/coach/stream", json={"message": "How do I remember what I read?"}, headers=headers))
    assert [e["type"] for e in out][0] == "meta" and out[-1]["type"] == "done"
    done = out[-1]
    assert "LRN-1" in done["sources"] and done["suggestions"]
    conv_id = done["conversation_id"]

    with SessionLocal() as db:
        stored = db.query(models.CoachMessage).join(models.CoachConversation).filter(
            models.CoachConversation.public_id == conv_id).all()
        assert len(stored) == 2
        assert "remember what" not in stored[0].body  # encrypted at rest
        assert encryption.decrypt_data(stored[0].body) == "How do I remember what I read?"

    listed = client.get("/coach/conversations", headers=headers).json()
    assert listed[0]["id"] == conv_id
    detail = client.get(f"/coach/conversations/{conv_id}", headers=headers).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]

    # Another account can't read or delete it.
    other = {"Authorization": f"Bearer {local_auth.issue_token('someone.else@example.com')[0]}"}
    assert client.get(f"/coach/conversations/{conv_id}", headers=other).status_code == 404
    assert client.delete(f"/coach/conversations/{conv_id}", headers=other).status_code == 404

    assert client.delete(f"/coach/conversations/{conv_id}", headers=headers).json() == {"deleted": True}
    assert client.get("/coach/conversations", headers=headers).json() == []


def test_guest_conversations_stay_in_the_guest_session(client, offline):
    token = client.post("/auth/guest").json()["token"]
    headers = {"X-Guest-Session": token}
    done = events(client.post("/coach/stream", json={"message": "I can't sleep"}, headers=headers))[-1]
    assert "SLP-1" in done["sources"]
    conv_id = done["conversation_id"]
    follow = events(client.post("/coach/stream", json={"message": "and lifting?", "conversation_id": conv_id},
                                headers=headers))[-1]
    assert follow["conversation_id"] == conv_id
    assert len(client.get(f"/coach/conversations/{conv_id}", headers=headers).json()["messages"]) == 4

    other = {"X-Guest-Session": client.post("/auth/guest").json()["token"]}
    assert client.get(f"/coach/conversations/{conv_id}", headers=other).status_code == 404
    client.delete("/auth/guest", headers=headers)
    assert client.get("/coach/conversations", headers=headers).status_code == 401


def test_me(client, account):
    email, headers = account
    assert client.get("/me", headers=headers).json() == {"guest": False, "email": email}
