"""
Built-in email/password accounts, used when no Cognito pool is configured.

Passwords are hashed with scrypt (standard library). Sign-in returns an HS256
JWT signed with JWT_SECRET, carrying the same "email" claim the rest of the
app already reads from Cognito ID tokens, so no other code has to change.
"""
import hashlib
import hmac
import os
import re
import secrets
import time

import jwt
from fastapi import HTTPException

import env_config  # noqa: F401

ISSUER = "local-auth"
TOKEN_TTL_SECONDS = int(os.getenv("LOCAL_AUTH_TTL_SECONDS", str(60 * 60 * 24 * 14)))
MIN_PASSWORD_LENGTH = 8
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 64}


def _secret() -> str:
    return os.getenv("JWT_SECRET") or "local-development-only-change-me"


def enabled() -> bool:
    """Local accounts are on unless a Cognito pool is configured."""
    return not os.getenv("COGNITO_USER_POOL_ID")


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    return email


def check_password_rules(password: str) -> None:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )
    if len(password) > 256:
        raise HTTPException(status_code=400, detail="Password is too long.")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def issue_token(email: str) -> tuple[str, int]:
    now = int(time.time())
    expires_at = now + TOKEN_TTL_SECONDS
    token = jwt.encode(
        {"iss": ISSUER, "sub": email, "email": email, "token_use": "id", "iat": now, "exp": expires_at},
        _secret(),
        algorithm="HS256",
    )
    return token, expires_at


def is_local_token(token: str) -> bool:
    try:
        return jwt.decode(token, options={"verify_signature": False}).get("iss") == ISSUER
    except jwt.PyJWTError:
        return False


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"], issuer=ISSUER)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Your session is invalid. Please log in again.")
