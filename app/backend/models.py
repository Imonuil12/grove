"""Grove database models.

Milestone 1 keeps only accounts and the coach. Each tracker (Habits, Books,
Training, Feed) adds its own tables in its milestone; see docs/features/.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    profile_data = Column(String, default="{}")  # unused legacy column, kept so existing accounts migrate in place
    created_at = Column(DateTime, default=datetime.utcnow)
    username = Column(String, unique=True, nullable=True, index=True)
    external_id = Column(String, unique=True, nullable=True)
    display_name = Column(String, nullable=True)

    conversations = relationship("CoachConversation", back_populates="user", cascade="all, delete-orphan")


class LocalCredential(Base):
    """Email/password login for built-in accounts (used when Cognito is off)."""
    __tablename__ = "local_credentials"

    credential_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_local_credential_user"), nullable=False, unique=True)
    email = Column(String(254), nullable=False, unique=True, index=True)
    password_hash = Column(String(300), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class CoachConversation(Base):
    __tablename__ = "coach_conversations"

    id = Column(Integer, primary_key=True)
    public_id = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_coach_conversation_user", ondelete="CASCADE"),
                     nullable=False, index=True)
    title = Column(String(120), nullable=False, default="New conversation")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("CoachMessage", back_populates="conversation", cascade="all, delete-orphan",
                            order_by="CoachMessage.id")


class CoachMessage(Base):
    __tablename__ = "coach_messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("coach_conversations.id", name="fk_coach_message_conversation",
                                                 ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # "user" or "assistant"
    body = Column(Text, nullable=False)  # encrypted at rest (encryption.encrypt_data)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    conversation = relationship("CoachConversation", back_populates="messages")
