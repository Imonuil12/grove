"""Coach API: conversations and streaming replies.

Signed-in users' conversations are stored (message text encrypted at rest).
Guest conversations live in the guest session's memory and end with it.
"""
import json
import secrets
from datetime import datetime
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import coach_prompt
import encryption
import llm
import models
from database import SessionLocal

HISTORY_TURNS = 12


class CoachMessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = Field(default=None, max_length=64)
    page: Optional[str] = Field(default=None, max_length=32)


def get_or_create_user(db: Session, email: str) -> models.User:
    user = db.query(models.User).filter_by(email=email).one_or_none()
    if user is None:
        user = models.User(email=email, profile_data="{}")
        db.add(user)
        db.flush()
    return user


def build_router(get_db: Callable, current_identity: Callable, guest_record: Callable) -> APIRouter:
    router = APIRouter(prefix="/coach", tags=["coach"])

    def guest_store(identity: str) -> dict:
        return guest_record(identity[len("guest_"):]).setdefault("coach", {})

    @router.get("/conversations")
    def list_conversations(identity: str = Depends(current_identity), db: Session = Depends(get_db)):
        if identity.startswith("guest_"):
            store = guest_store(identity)
            rows = sorted(store.items(), key=lambda item: item[1]["updated_at"], reverse=True)
            return [{"id": key, "title": c["title"], "updated_at": c["updated_at"]} for key, c in rows]
        user = get_or_create_user(db, identity)
        rows = (db.query(models.CoachConversation).filter_by(user_id=user.id)
                .order_by(models.CoachConversation.updated_at.desc()).limit(50).all())
        return [{"id": c.public_id, "title": c.title, "updated_at": c.updated_at.isoformat()} for c in rows]

    @router.get("/conversations/{conversation_id}")
    def get_conversation(conversation_id: str, identity: str = Depends(current_identity), db: Session = Depends(get_db)):
        if identity.startswith("guest_"):
            conv = guest_store(identity).get(conversation_id)
            if not conv:
                raise HTTPException(404, "Conversation not found.")
            return {"id": conversation_id, "title": conv["title"], "messages": conv["messages"]}
        conv = _owned(db, identity, conversation_id)
        return {"id": conv.public_id, "title": conv.title,
                "messages": [{"role": m.role, "text": encryption.decrypt_data(m.body)} for m in conv.messages]}

    @router.delete("/conversations/{conversation_id}")
    def delete_conversation(conversation_id: str, identity: str = Depends(current_identity), db: Session = Depends(get_db)):
        if identity.startswith("guest_"):
            guest_store(identity).pop(conversation_id, None)
        else:
            db.delete(_owned(db, identity, conversation_id))
        return {"deleted": True}

    @router.post("/stream")
    def stream(payload: CoachMessageIn, identity: str = Depends(current_identity), db: Session = Depends(get_db)):
        """
        Newline-delimited JSON events:
          {"type": "meta", "conversation_id"}
          {"type": "delta", "text"}  (repeated)
          {"type": "done", "response", "suggestions", "sources", "conversation_id", "title"}
        """
        message = payload.message.strip()
        if not message:
            raise HTTPException(400, "Message is empty.")
        guest = identity.startswith("guest_")
        history, conv_id, title = _load(db, identity, payload.conversation_id, message, guest)
        db.commit()  # release locks before the long-running stream
        system = coach_prompt.build_system_prompt(page=payload.page)
        messages = history + [{"role": "user", "content": message}]
        hold_back = len(coach_prompt.FOLLOWUP_MARKER)

        def event(data):
            return json.dumps(data) + "\n"

        def events():
            yield event({"type": "meta", "conversation_id": conv_id})
            full, sent, saved = "", 0, False
            try:
                for piece in llm.stream(system, messages) if llm.is_configured() else []:
                    full += piece
                    marker = full.find(coach_prompt.FOLLOWUP_MARKER)
                    visible = full[:marker] if marker != -1 else full[:max(0, len(full) - hold_back)]
                    if len(visible) > sent:
                        yield event({"type": "delta", "text": visible[sent:]})
                        sent = len(visible)
                if full.strip():
                    reply, suggestions = coach_prompt.split_followups(full)
                    if len(reply) > sent:
                        yield event({"type": "delta", "text": reply[sent:]})
                else:
                    reply, suggestions = coach_prompt.offline_reply(message)
                    yield event({"type": "delta", "text": reply})
                _save(identity, conv_id, title, message, reply, guest)
                saved = True
                yield event({"type": "done", "response": reply, "suggestions": suggestions,
                             "sources": coach_prompt.cited_ids(reply), "conversation_id": conv_id, "title": title})
            finally:
                if not saved and full.strip():  # the user pressed Stop: keep what they saw
                    try:
                        _save(identity, conv_id, title, message, coach_prompt.split_followups(full)[0], guest)
                    except Exception as e:  # noqa: BLE001
                        print(f"[coach] could not save partial reply: {e}")

        return StreamingResponse(events(), media_type="application/x-ndjson",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    def _owned(db: Session, email: str, public_id: str) -> models.CoachConversation:
        conv = (db.query(models.CoachConversation).join(models.User)
                .filter(models.CoachConversation.public_id == public_id, models.User.email == email).one_or_none())
        if conv is None:
            raise HTTPException(404, "Conversation not found.")
        return conv

    def _load(db, identity, conversation_id, message, guest):
        """Returns (history for the model, conversation id, title)."""
        if guest:
            store = guest_store(identity)
            conv = store.get(conversation_id) if conversation_id else None
            if conv is None:
                conversation_id = secrets.token_urlsafe(12)
                if len(store) >= 20:  # bound guest memory
                    store.pop(min(store, key=lambda key: store[key]["updated_at"]))
                conv = store[conversation_id] = {"title": coach_prompt.title_from(message), "messages": [],
                                                  "updated_at": datetime.utcnow().isoformat()}
            history = [{"role": m["role"], "content": m["text"]} for m in conv["messages"][-HISTORY_TURNS:]]
            return history, conversation_id, conv["title"]
        if conversation_id:
            conv = _owned(db, identity, conversation_id)
        else:
            conv = models.CoachConversation(public_id=secrets.token_urlsafe(12), title=coach_prompt.title_from(message),
                                            user_id=get_or_create_user(db, identity).id)
            db.add(conv)
            db.flush()
        recent = conv.messages[-HISTORY_TURNS:]
        history = [{"role": m.role, "content": encryption.decrypt_data(m.body)} for m in recent]
        return history, conv.public_id, conv.title

    def _save(identity, conv_id, title, message, reply, guest):
        now = datetime.utcnow()
        if guest:
            conv = guest_store(identity).get(conv_id)
            if conv is not None:
                conv["messages"] += [{"role": "user", "text": message}, {"role": "assistant", "text": reply}]
                conv["messages"] = conv["messages"][-60:]
                conv["updated_at"] = now.isoformat()
            return
        with SessionLocal() as session, session.begin():
            conv = session.query(models.CoachConversation).filter_by(public_id=conv_id).one()
            session.add_all([
                models.CoachMessage(conversation_id=conv.id, role="user", body=encryption.encrypt_data(message)),
                models.CoachMessage(conversation_id=conv.id, role="assistant", body=encryption.encrypt_data(reply)),
            ])
            conv.updated_at = now

    return router

