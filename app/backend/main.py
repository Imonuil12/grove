import env_config  # noqa: F401  (loads the repo-root .env first)
import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from fastapi import FastAPI, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import uvicorn
import os
from typing import Optional
from datetime import datetime
from database import SessionLocal, require_current_schema
import models
from sqlalchemy.orm import Session
import auth
import local_auth
import coach

APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV == "production"
TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "1x00000000000000000000AA")
TURNSTILE_SECRET_KEY = os.getenv(
    "TURNSTILE_SECRET_KEY", "1x0000000000000000000000000000000AA"
)
SESSION_SECRET = os.getenv("JWT_SECRET") or "local-development-only-change-me"
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(60 * 60 * 24 * 30)))
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
COGNITO_REGION = os.getenv("COGNITO_REGION", "us-east-2")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "")
COGNITO_ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
COGNITO_JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"
_cognito_jwks_cache = {"keys": {}, "expires_at": 0}
FRONTEND_URLS = [
    value.strip().rstrip("/")
    for value in os.getenv(
        "FRONTEND_URL", "http://127.0.0.1:5500,http://localhost:5500"
    ).split(",")
    if value.strip()
]

if IS_PRODUCTION:
    required = ["JWT_SECRET", "SESSION_ENCRYPTION_KEY"]
    if os.getenv("COGNITO_USER_POOL_ID"):
        required += ["COGNITO_REGION", "COGNITO_CLIENT_ID"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required production configuration: {', '.join(missing)}")
    if len(SESSION_SECRET) < 32 or SESSION_SECRET == "local-development-only-change-me":
        raise RuntimeError("JWT_SECRET must be a unique value of at least 32 characters in production")
require_current_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# Cognito supplies the account identity; Turnstile separately proves that the
# browser passed the bot check before protected API calls are accepted.
# Opaque guest tokens identify isolated, expiring in-memory profiles.
# Run one worker: guest profiles intentionally disappear on server restart.
GUEST_SESSIONS = {}
GUEST_TTL_SECONDS = 4 * 60 * 60

def guest_record(token):
    now = time.time()
    for key in list(GUEST_SESSIONS):
        if GUEST_SESSIONS[key]["expires"] <= now:
            GUEST_SESSIONS.pop(key, None)
    record = GUEST_SESSIONS.get(token)
    if not record:
        raise HTTPException(status_code=401, detail="Guest session expired.")
    return record

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not IS_PRODUCTION else FRONTEND_URLS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/auth/verify")
def verify_token(authorization: Optional[str] = Header(default=None)):
    """Verifies the AWS Cognito JWT Bearer token and returns user details."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization Bearer token.")
    claims = auth.verify_jwt_token(authorization[7:].strip())
    return {
        "authenticated": True,
        "username": claims.get("email") or claims.get("cognito:username") or claims.get("username"),
        "email": claims.get("email"),
        "sub": claims.get("sub"),
        "claims": claims
    }


class TurnstileAuthRequest(BaseModel):
    turnstile_token: str
    previous_session_token: Optional[str] = None


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_session_token(visitor_id: str) -> tuple[str, int]:
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = _base64url_encode(
        json.dumps({"sub": visitor_id, "exp": expires_at}, separators=(",", ":")).encode()
    )
    signature = _base64url_encode(
        hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    )
    return f"{payload}.{signature}", expires_at


def decode_session_token(token: str, check_expiry: bool = True) -> str:
    try:
        payload, supplied_signature = token.split(".", 1)
        expected_signature = _base64url_encode(
            hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("bad signature")
        data = json.loads(_base64url_decode(payload))
        if check_expiry and int(data["exp"]) < int(time.time()):
            raise ValueError("expired")
        visitor_id = str(data["sub"])
        if not visitor_id.startswith("visitor_"):
            raise ValueError("bad subject")
        return visitor_id
    except (binascii.Error, KeyError, TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Your verified session is invalid or expired.") from exc


def require_visitor(x_turnstile_session: Optional[str] = Header(default=None)) -> str:
    if not x_turnstile_session:
        if not IS_PRODUCTION or TURNSTILE_SECRET_KEY.startswith("1x000"):
            return "dev_visitor"
        raise HTTPException(status_code=401, detail="Complete the security check to continue.")
    return decode_session_token(x_turnstile_session)


def _load_cognito_key(kid: str):
    now = int(time.time())
    cached_key = _cognito_jwks_cache["keys"].get(kid)
    if cached_key and _cognito_jwks_cache["expires_at"] > now:
        return cached_key

    try:
        with urllib_request.urlopen(COGNITO_JWKS_URL, timeout=10) as response:
            keys = {key["kid"]: key for key in json.loads(response.read()).get("keys", [])}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Cognito token verification is unavailable.") from exc

    _cognito_jwks_cache["keys"] = keys
    _cognito_jwks_cache["expires_at"] = now + 3600
    if kid not in keys:
        raise HTTPException(status_code=401, detail="The Cognito token signing key is unknown.")
    return keys[kid]


def verify_cognito_id_token(token: str) -> dict:
    try:
        header_part, payload_part, signature_part = token.split(".")
        header = json.loads(_base64url_decode(header_part))
        claims = json.loads(_base64url_decode(payload_part))
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise ValueError("unexpected JWT header")
        if claims.get("iss") != COGNITO_ISSUER:
            raise ValueError("unexpected issuer")
        if claims.get("aud") != COGNITO_CLIENT_ID:
            raise ValueError("unexpected audience")
        if claims.get("token_use") != "id":
            raise ValueError("expected an ID token")
        if int(claims.get("exp", 0)) < int(time.time()):
            raise ValueError("expired token")

        jwk = _load_cognito_key(header["kid"])
        modulus = int.from_bytes(_base64url_decode(jwk["n"]), "big")
        exponent = int.from_bytes(_base64url_decode(jwk["e"]), "big")
        public_key = rsa.RSAPublicNumbers(exponent, modulus).public_key()
        public_key.verify(
            _base64url_decode(signature_part),
            f"{header_part}.{payload_part}".encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return claims
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="The Cognito session is invalid or expired.") from exc


def require_authenticated_user(
    x_guest_session: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    x_turnstile_session: Optional[str] = Header(default=None),
) -> str:
    if x_guest_session:
        guest_record(x_guest_session)
        return "guest_" + x_guest_session

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        try:
            claims = auth.verify_jwt_token(token)
            identity = claims.get("email") or claims.get("cognito:username") or claims.get("username") or claims.get("sub")
            if identity:
                return str(identity)
        except Exception:
            pass

    # No signed-in account and no guest session: there is no identity to use.
    # (Older builds invented "dev_user"/X-Dev-User identities here, which created fake accounts.)
    raise HTTPException(status_code=401, detail="Sign in or continue as a guest to use this feature.")


def verify_turnstile_token(token: str, remote_ip: Optional[str] = None) -> dict:
    if not token or len(token) > 2048:
        raise HTTPException(status_code=400, detail="Complete the security check to continue.")

    siteverify_data = {"secret": TURNSTILE_SECRET_KEY, "response": token}
    if remote_ip:
        siteverify_data["remoteip"] = remote_ip
    body = urllib_parse.urlencode(siteverify_data).encode()
    try:
        request = urllib_request.Request(
            TURNSTILE_VERIFY_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib_request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read())
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="The security service is temporarily unavailable."
        ) from exc

    if not result.get("success"):
        raise HTTPException(status_code=400, detail="Security verification failed. Please try again.")
    if result.get("action") and result["action"] != "access":
        raise HTTPException(status_code=400, detail="Security verification was issued for another action.")
    return result


@app.get("/auth/config")
def get_auth_config():
    # Public values only. The frontend reads these at load time, so the Cognito
    # pool is configured in one place (.env) instead of hard-coded in the browser.
    return {
        "site_key": TURNSTILE_SITE_KEY,
        "provider": "local" if local_auth.enabled() else "cognito",
        "cognito": {
            "region": COGNITO_REGION,
            "user_pool_id": COGNITO_USER_POOL_ID,
            "client_id": COGNITO_CLIENT_ID,
            "domain": os.getenv("COGNITO_DOMAIN", ""),
            "redirect_uri": os.getenv("COGNITO_REDIRECT_URI", ""),
        },
    }


# Simple in-memory rate limits for the built-in account routes (one worker).
_AUTH_HITS = {}


def _rate_limit(key: str, limit: int, window_seconds: int):
    now = time.time()
    hits = [t for t in _AUTH_HITS.get(key, []) if t > now - window_seconds]
    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a few minutes and try again.")
    hits.append(now)
    _AUTH_HITS[key] = hits
    if len(_AUTH_HITS) > 5000:  # keep memory bounded
        for k in list(_AUTH_HITS)[:1000]:
            _AUTH_HITS.pop(k, None)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class LocalAuthRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


def _local_auth_response(email: str) -> dict:
    token, expires_at = local_auth.issue_token(email)
    return {"email": email, "id_token": token, "expires_at": expires_at}


def _require_local_auth():
    if not local_auth.enabled():
        raise HTTPException(status_code=404, detail="Built-in accounts are turned off; this server uses Cognito.")


@app.post("/auth/local/signup")
def local_signup(payload: LocalAuthRequest, request: Request, db: Session = Depends(get_db)):
    _require_local_auth()
    _rate_limit("signup:" + _client_ip(request), 10, 60 * 60)
    email = local_auth.normalize_email(payload.email)
    local_auth.check_password_rules(payload.password)
    if db.query(models.LocalCredential).filter_by(email=email).one_or_none():
        raise HTTPException(status_code=409, detail="An account with this email already exists. Try logging in.")
    user = db.query(models.User).filter_by(email=email).one_or_none()
    if user is None:
        user = models.User(email=email, profile_data="{}")
        db.add(user)
        db.flush()
    db.add(models.LocalCredential(
        user_id=user.id, email=email, password_hash=local_auth.hash_password(payload.password),
    ))
    return _local_auth_response(email)


@app.post("/auth/local/login")
def local_login(payload: LocalAuthRequest, request: Request, db: Session = Depends(get_db)):
    _require_local_auth()
    email = (payload.email or "").strip().lower()
    _rate_limit("login-ip:" + _client_ip(request), 30, 15 * 60)
    _rate_limit("login-email:" + email, 10, 15 * 60)
    credential = db.query(models.LocalCredential).filter_by(email=email).one_or_none()
    if not credential or not local_auth.verify_password(payload.password or "", credential.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    credential.last_login_at = datetime.utcnow()
    return _local_auth_response(email)


@app.post("/auth/turnstile")
def turnstile_auth(payload: TurnstileAuthRequest, request: Request):
    remote_ip = request.client.host if request.client else None
    verify_turnstile_token(payload.turnstile_token, remote_ip)

    visitor_id = None
    if payload.previous_session_token:
        try:
            # A correctly signed expired token may recover this browser's profile
            # only after the visitor passes a fresh Turnstile challenge.
            visitor_id = decode_session_token(payload.previous_session_token, check_expiry=False)
        except HTTPException:
            pass
    if not visitor_id:
        visitor_id = f"visitor_{secrets.token_urlsafe(18)}"

    session_token, expires_at = create_session_token(visitor_id)
    return {
        "visitor_id": visitor_id,
        "session_token": session_token,
        "expires_at": expires_at,
    }


# Guest sessions: opaque tokens for isolated, expiring in-memory profiles.
# Run one worker: guest data intentionally disappears on server restart.
@app.post("/auth/guest")
def start_guest(request: Request):
    # Cap active sessions globally and per address to bound memory.
    now = time.time()
    for key in list(GUEST_SESSIONS):
        if GUEST_SESSIONS[key]["expires"] <= now:
            GUEST_SESSIONS.pop(key, None)
    address = _client_ip(request)
    if len(GUEST_SESSIONS) >= 1000 or sum(r["address"] == address for r in GUEST_SESSIONS.values()) >= 20:
        raise HTTPException(status_code=429, detail="Too many active guest sessions. Try again later.")
    token = secrets.token_urlsafe(32)
    GUEST_SESSIONS[token] = {"expires": now + GUEST_TTL_SECONDS, "address": address}
    return {"token": token, "username": "guest_" + token}


@app.delete("/auth/guest")
def end_guest(x_guest_session: Optional[str] = Header(default=None)):
    if x_guest_session:
        GUEST_SESSIONS.pop(x_guest_session, None)
    return {"ended": True}


@app.get("/me")
def me(identity: str = Depends(require_authenticated_user)):
    guest = identity.startswith("guest_")
    return {"guest": guest, "email": None if guest else identity}


app.include_router(coach.build_router(get_db, require_authenticated_user, guest_record))


@app.get("/healthz")
def healthz():
    return {"ok": True}


# Serve the website from the same server as the API (one deploy, no CORS).
# Mounted last so every API route above takes precedence.
from fastapi.staticfiles import StaticFiles  # noqa: E402

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
if os.getenv("SERVE_FRONTEND", "1") != "0" and os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
