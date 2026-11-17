import env_config  # noqa: F401  (loads the repo-root .env first)
import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from contextlib import contextmanager, nullcontext
from threading import Lock
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from fastapi import FastAPI, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import uvicorn
import re
from curriculum import load_catalog, drug_content
from copy import deepcopy
from learning_store import get_state as get_relational_state, save_state as save_relational_state, record_assessment as record_relational_assessment
import os
from typing import List, Optional
from typing import Dict
from datetime import date
from database import Base, SessionLocal, engine, require_current_schema
import models
import random
import llm
import chat_prompt
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
import encryption
import auth
import local_auth
import adaptive_learning
from topic_learning import TopicLearning

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


# Unit order comes from categories.display_order in the relational curriculum.


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Learning progress changed in another request. Reload and try again.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def blank_user_state():
    return {
        "selected_drug": "amoxicillin",
        "archetype": "needs more explanations",
        "intake": {},
        "warnings": [],
        "assessment_answers": {},
        "objective_mastery": {},
        "lesson_queue": [],
        "last_results": [],
        # --- Gamification (Phase 1) ---
        "xp_total": 0,
        "streak_current": 0,
        "streak_longest": 0,
        "last_active_date": None,
        "hearts_remaining": 5,
        "badges": [],
        "current_lesson": None,
        # Set once hearts hit 0: holds the missed-question remediation the
        # user must review before a new lesson attempt is allowed.
        "review_items": [],
    }

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

def get_user_state(username: str, db: Session, drug=None):
    if not username.startswith("guest_"):
        return get_relational_state(username, db, drug)
    record = guest_record(username[6:])
    state = deepcopy(record["state"])
    scope = (drug or state["selected_drug"]).lower()
    drug_content(db, scope)
    course = record.setdefault("courses", {}).get(scope, {})
    for key in ("objective_mastery", "lesson_queue", "last_results", "review_items"):
        state[key] = deepcopy(course.get(key, blank_user_state()[key]))
    state["_drug"] = scope
    return state

def save_user_state(username: str, state: dict, db: Session):
    if not username.startswith("guest_"):
        return save_relational_state(username, state, db, commit=False)
    record = guest_record(username[6:])
    scope = state.get("_drug", state["selected_drug"])
    record.setdefault("courses", {})[scope] = {
        key: deepcopy(state[key])
        for key in ("objective_mastery", "lesson_queue", "last_results", "review_items")
    }
    record["state"] = deepcopy({key: value for key, value in state.items() if not key.startswith("_")})


def record_assessment(username, drug, kind, answers, results, db, **kwargs):
    if username.startswith("guest_"):
        guest_record(username[6:])
        return None
    return record_relational_assessment(username, drug, kind, answers, results, db, **kwargs)

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

import uuid
from datetime import datetime


def normalize(text):
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower().strip())
    return re.sub(r"\s+", " ", text)


def answer_is_correct(user_answer, accepted_keyword_sets):
    answer = normalize(user_answer)
    return bool(answer) and any(
        keywords and all(keyword.lower() in answer for keyword in keywords)
        for keywords in accepted_keyword_sets
    )


def get_objective_by_id(objectives, oid: str):
    for obj in objectives:
        if obj.oid == oid:
            return obj
    return None

def detect_drug_from_message(message: str, selected_drug: str, db) -> str:
    msg = normalize(message)

    for drug_key, drug_data in load_catalog(db).items():
        display_name = normalize(drug_data["display_name"])
        if drug_key in msg or display_name in msg:
            return drug_key

    return selected_drug if selected_drug in load_catalog(db) else "amoxicillin"

def handle_small_talk(message: str, active_drug: str, db):
    msg = normalize(message)
    drug_name = load_catalog(db)[active_drug]["display_name"]

    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
    how_are_you = ["how are you", "how are you doing", "how s it going"]
    thanks = ["thanks", "thank you", "appreciate it"]

    if msg in greetings or any(msg.startswith(g) for g in greetings):
        return (
            f"Hi! I'm your learning assistant, and I'm currently focused on {drug_name}.\n\n"
            f"You can ask about:\n"
            f"• what {drug_name} is\n"
            f"• dosage basics\n"
            f"• how to take it\n"
            f"• side effects or allergies\n"
            f"• how it works"
        )

    if any(q in msg for q in how_are_you):
        return (
            f"I'm doing well! I'm here to help explain {drug_name}.\n\n"
            f"Try asking something like:\n"
            f"• What is {drug_name}?\n"
            f"• How do I take it?\n"
            f"• How does it work?"
        )

    if any(t in msg for t in thanks):
        return f"You're welcome! Let me know if you'd like to learn more about {drug_name}."

    return None

def simplify_text(text):
    import re

    # Replace technical words
    text = text.replace("an antibiotic", "a medicine")
    text = text.replace("bacteria", "germs")
    text = text.replace("bacterial", "caused by germs")

    # Break into sentences
    sentences = re.split(r'(?<=[.!?]) +', text)

    # Shorten sentences + soften tone
    simplified = []
    for s in sentences:
        if len(s) > 120:
            s = s[:120] + "..."
        simplified.append(s)

    # Add a light analogy sometimes
    import random
    analogies = [
        "It’s kind of like giving your body backup to fight off germs.",
        "Think of it as helping your body clear out the infection faster.",
        "",
    ]

    return " ".join(simplified) + "\n\n" + random.choice(analogies)

def clarify_text(text):
    import re

    # Slightly improve clarity without simplifying too much
    text = text.replace("antibiotic", "antibiotic (a drug that treats bacterial infections)")

    # Split sentences
    sentences = re.split(r'(?<=[.!?]) +', text)

    improved = []
    for s in sentences:
        # shorten very long sentences
        if len(s) > 140:
            s = s[:140] + "..."
        improved.append(s)

    # Add a light explanation sometimes
    import random
    additions = [
        "In short, it’s used when the infection is caused by bacteria.",
        "So the key idea is: it only works on certain types of infections.",
        "",
    ]

    return " ".join(improved) + "\n\n" + random.choice(additions)

def make_technical(text):
    # Upgrade wording
    text = text.replace("helps your body fight bacteria", "targets bacterial cell wall synthesis")
    text = text.replace("antibiotic", "beta-lactam antibiotic")
    text = text.replace("germs", "microorganisms")

    # Add mechanism detail
    extra = "\n\nMechanism: Inhibits bacterial cell wall synthesis, leading to cell lysis in susceptible organisms."

    return text + extra



def check_safety_warnings(username: str, active_drug: str, message: str, db: Session, state: dict = None) -> Optional[str]:
    """
    Automated Clinical Contraindication & Interaction Cross-Checker (Sprint 9).
    Cross-references patient intake profile (allergies, organ conditions, concurrent medications)
    against the active drug and chat message content to surface real-time clinical alerts.
    """
    if not username:
        return None

    preferences = db.query(models.UserLearningState).join(models.User, models.User.id == models.UserLearningState.user_id).filter(models.User.email == username).one_or_none()
    intake = db.get(models.UserIntake, preferences.latest_intake_id) if preferences and preferences.latest_intake_id else None
    state_intake = state.get("intake", {}) if state else {}

    penicillin_allergy = (intake and intake.penicillin_allergy) or state_intake.get("penicillin_allergy", False)
    anaphylaxis = (intake and intake.anaphylaxis_history) or state_intake.get("anaphylaxis_history", False)
    mono = (intake and intake.mono_suspected) or state_intake.get("mono_suspected", False)
    kidney = (intake and intake.kidney_disease) or state_intake.get("kidney_disease", False)
    breastfeeding = (intake and intake.breastfeeding) or state_intake.get("breastfeeding", False)
    pregnancy_status = (intake and intake.pregnancy_status) or state_intake.get("pregnancy_status", "Unknown")
    meds_text = ((intake and intake.meds_text) or state_intake.get("meds_text", "")).lower()

    drug_lower = active_drug.lower()
    msg_lower = message.lower()
    combined_meds = f"{meds_text} {msg_lower}"

    warnings = []

    # 1. Penicillin Allergy & Anaphylaxis Guardrail (Amoxicillin / Beta-lactams)
    if "amoxicillin" in drug_lower or "amoxicillin" in msg_lower or "penicillin" in msg_lower:
        if penicillin_allergy or anaphylaxis:
            warnings.append("⚠️ PATIENT SAFETY WARNING: Your Intake record flags a Penicillin allergy / Anaphylaxis history. Penicillins like Amoxicillin should be avoided or taken only under close specialist supervision.")
        if mono or "mono" in msg_lower or "mononucleosis" in msg_lower:
            warnings.append("⚠️ CLINICAL ADVISORY: Suspected Mononucleosis flagged in Intake. Amoxicillin can cause a widespread non-allergic maculopapular rash in patients with Mono.")

    # 2. Kidney Disease Guardrails
    if kidney:
        if "ibuprofen" in drug_lower or "ibuprofen" in msg_lower or "nsaid" in msg_lower or "advil" in msg_lower or "motrin" in msg_lower:
            warnings.append("⚠️ CONTRAINDICATION ALERT: Kidney disease flagged in Intake. NSAIDs like Ibuprofen inhibit renal prostaglandins, reducing renal blood flow and potentially causing acute kidney injury. Consult your clinician for renal-safe alternatives.")
        elif "amoxicillin" in drug_lower or "amoxicillin" in msg_lower:
            warnings.append("⚠️ CLINICAL ADVISORY: Kidney disease flagged in Intake. Amoxicillin is excreted predominantly via the kidneys; dose intervals may require reduction based on renal function (eGFR).")

    # 3. Drug-Drug Interactions
    # Warfarin / Anticoagulants
    if "warfarin" in combined_meds or "coumadin" in combined_meds or "blood thinner" in combined_meds:
        if "amoxicillin" in drug_lower or "amoxicillin" in msg_lower:
            warnings.append("⚠️ DRUG INTERACTION ALERT: Warfarin listed in profile/query. Amoxicillin can disrupt intestinal microflora and Vitamin K synthesis, elevating INR and bleeding risk. Close INR monitoring is advised.")
        if "ibuprofen" in drug_lower or "ibuprofen" in msg_lower or "nsaid" in msg_lower:
            warnings.append("⚠️ CRITICAL DRUG INTERACTION: Combining NSAIDs (Ibuprofen) with Warfarin significantly elevates the risk of severe, potentially life-threatening gastrointestinal hemorrhage.")

    # Methotrexate
    if "methotrexate" in combined_meds:
        if "amoxicillin" in drug_lower or "amoxicillin" in msg_lower or "penicillin" in msg_lower:
            warnings.append("⚠️ DRUG INTERACTION ALERT: Methotrexate listed in profile/query. Penicillins compete for renal tubular secretion, increasing serum methotrexate concentrations and toxicity risk.")

    # Aspirin + Ibuprofen
    if ("aspirin" in combined_meds or "bayer" in combined_meds) and ("ibuprofen" in drug_lower or "ibuprofen" in msg_lower):
        warnings.append("⚠️ DRUG INTERACTION ALERT: Ibuprofen can interfere with the cardio-protective antiplatelet effect of low-dose Aspirin and markedly increases gastrointestinal ulceration risk.")

    # Lisinopril / ACE Inhibitors + NSAIDs
    if any(ace in combined_meds for ace in ["lisinopril", "enalapril", "losartan", "ramipril"]) and ("ibuprofen" in drug_lower or "ibuprofen" in msg_lower):
        warnings.append("⚠️ DRUG INTERACTION ALERT: Combining NSAIDs (Ibuprofen) with ACE inhibitors/ARBs (e.g., Lisinopril) can antagonize blood pressure control and increase the risk of acute renal impairment.")

    # 4. Pregnancy & Lactation Safety
    is_pregnant = (
        any(k in str(pregnancy_status).lower() for k in ["pregnant", "trying", "1st", "2nd", "3rd", "trimester", "yes"]) or
        "pregnant" in msg_lower or "pregnancy" in msg_lower
    )
    if is_pregnant:
        if "ibuprofen" in drug_lower or "ibuprofen" in msg_lower or "nsaid" in msg_lower:
            warnings.append("⚠️ PREGNANCY WARNING: NSAIDs like Ibuprofen are strictly contraindicated in the third trimester (and avoided after 20 weeks) due to risks of premature closure of the fetal ductus arteriosus and oligohydramnios.")
        elif "amoxicillin" in drug_lower or "amoxicillin" in msg_lower:
            warnings.append("⚠️ PREGNANCY ADVISORY: Amoxicillin is generally considered FDA Category B, but all antibiotic therapy during pregnancy must be reviewed with your obstetrician.")

    if breastfeeding and ("nursing" in msg_lower or "breastfeed" in msg_lower or "infant" in msg_lower):
        warnings.append("⚠️ LACTATION ADVISORY: Small amounts of medication pass into breast milk. Monitor infant for symptoms such as diarrhea, candidiasis (thrush), or irritability, and consult your pediatrician.")

    if warnings:
        return "\n\n".join(warnings)

    return None



def get_recent_history(db: Session, session_id: str, limit: int = 5, conversation_id=None):
    if session_id.startswith("guest_"):
        rows = guest_record(session_id[6:]).get("messages", [])
        if conversation_id:
            rows = [row for row in rows if row["conversation_id"] == conversation_id]
        return [{"role": "user" if row["sender"] == "user" else "assistant", "content": row["message"]} for row in rows[-limit * 2:]]
    query = db.query(models.ChatMessage).filter_by(session_id=session_id)
    if conversation_id:
        query = query.filter_by(conversation_id=conversation_id)
    rows = query.order_by(models.ChatMessage.timestamp.desc(), models.ChatMessage.id.desc()).limit(limit * 2).all()
    return [{"role": "user" if row.sender == "user" else "assistant", "content": encryption.decrypt_data(row.message)} for row in reversed(rows)]


def conversation_dict(conv):
    return {"conversation_id": conv.conversation_id, "title": conv.title, "drug": conv.drug,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None}


def history_rows(username, db, drug=None, conversation_id=None, limit=50):
    limit = max(1, min(limit, 500))
    if username.startswith("guest_"):
        rows = guest_record(username[6:]).get("messages", [])
        rows = [dict(row) for row in rows if (not drug or row["drug"] == drug.lower()) and (not conversation_id or row["conversation_id"] == conversation_id)]
        return rows[-limit:]
    query = db.query(models.ChatMessage).filter_by(session_id=username)
    if drug:
        query = query.filter_by(drug=drug.lower())
    if conversation_id:
        query = query.filter_by(conversation_id=conversation_id)
    rows = list(reversed(query.order_by(models.ChatMessage.timestamp.desc(), models.ChatMessage.id.desc()).limit(limit).all()))
    return [{"id": row.id, "sender": row.sender, "message": encryption.decrypt_data(row.message),
             "drug": row.drug, "archetype": row.archetype, "has_safety_warning": row.has_safety_warning,
             "conversation_id": row.conversation_id, "timestamp": row.timestamp.isoformat() if row.timestamp else None} for row in rows]


def find_relevant_objective(message: str, active_drug: str, db):
    msg = normalize(message)
    objectives = load_catalog(db)[active_drug]["objectives"]

    if active_drug == "amoxicillin":
        if any(phrase in msg for phrase in [
            "what is amoxicillin", "what kind of medication", "is amoxicillin an antibiotic",
            "what does amoxicillin treat", "does amoxicillin treat colds", "does it treat viral infections"
        ]):
            return get_objective_by_id(objectives, "F1") or get_objective_by_id(objectives, "F2")

        if any(phrase in msg for phrase in [
            "side effects", "allergy signs", "allergic reaction", "serious allergy",
            "hives", "swelling", "trouble breathing", "wheezing", "rash"
        ]):
            return get_objective_by_id(objectives, "F3")

        if any(phrase in msg for phrase in [
            "dosage", "dose", "how much", "how many", "how often",
            "take exactly as prescribed", "share antibiotics", "leftover antibiotics"
        ]):
            return get_objective_by_id(objectives, "D1")

        if any(phrase in msg for phrase in [
            "missed dose", "miss a dose", "double up", "double the next one", "catch up"
        ]):
            return get_objective_by_id(objectives, "D2")

        if any(phrase in msg for phrase in [
            "finish antibiotics", "finish the course", "stopping early", "stop early",
            "why do i need to finish", "why finish the prescription", "resistance"
        ]):
            return get_objective_by_id(objectives, "D3")

        if any(phrase in msg for phrase in [
            "how do i take it", "how to take it", "take it with food", "with food",
            "meal", "stomach upset", "upsets my stomach"
        ]):
            return get_objective_by_id(objectives, "P1")

        if any(phrase in msg for phrase in [
            "same time", "schedule", "reminder", "consistent times",
            "when should i take it", "good habit"
        ]):
            return get_objective_by_id(objectives, "P2")

        if any(phrase in msg for phrase in [
            "when should i call a doctor", "when should i contact a clinician",
            "when to seek help", "severe diarrhea", "severe rash", "urgent"
        ]):
            return get_objective_by_id(objectives, "P3")

        if any(phrase in msg for phrase in [
            "how does it work", "how do antibiotics work", "mechanism", "cell wall",
            "how does amoxicillin affect bacteria"
        ]):
            return get_objective_by_id(objectives, "R1")

        if any(phrase in msg for phrase in [
            "why does penicillin allergy matter", "penicillin allergy",
            "why mention allergy", "why is allergy important"
        ]):
            return get_objective_by_id(objectives, "R2")

        if any(phrase in msg for phrase in [
            "consult a clinician", "why does the system recommend consult a clinician",
            "why warning", "why does it flag a warning", "safety warning"
        ]):
            return get_objective_by_id(objectives, "R3")

    elif active_drug == "ibuprofen":
        if any(phrase in msg for phrase in [
            "what is ibuprofen", "what kind of medication", "is ibuprofen an nsaid"
        ]):
            return get_objective_by_id(objectives, "F1")

        if any(phrase in msg for phrase in [
            "dosage", "dose", "how much", "how often"
        ]):
            return get_objective_by_id(objectives, "D1")

        if any(phrase in msg for phrase in [
            "how do i take it", "with food", "food", "milk", "stomach upset"
        ]):
            return get_objective_by_id(objectives, "P1")

        if any(phrase in msg for phrase in [
            "how does it work", "mechanism", "how does ibuprofen work"
        ]):
            return get_objective_by_id(objectives, "R1")

    # Score-based fallback search across clinical objective texts & questions
    best_obj = None
    best_score = 0
    words = [w for w in msg.split() if len(w) > 3]
    for obj in objectives:
        corpus = normalize(f"{obj.objective_text} {obj.category} {obj.question} {obj.remediation_lesson}")
        score = sum(1 for w in words if w in corpus)
        if score > best_score:
            best_score = score
            best_obj = obj

    return best_obj if best_score > 0 else None



def format_intake_summary(intake: dict) -> str:
    if not intake or not isinstance(intake, dict):
        return "No patient intake form submitted yet."

    details = []

    # Demographics & Experience
    demo = []
    if intake.get("gender"):
        demo.append(f"Gender: {intake.get('gender')}")
    if intake.get("dob"):
        demo.append(f"DOB/Age: {intake.get('dob')}")
    if intake.get("experience_level"):
        demo.append(f"Medication Experience Level: {intake.get('experience_level')}")
    if demo:
        details.append("• Profile & Demographics: " + ", ".join(demo))

    # Medical & Allergies
    med_items = []
    if intake.get("penicillin_allergy"):
        med_items.append("Penicillin Allergy (YES)")
    if intake.get("anaphylaxis_history"):
        med_items.append("Anaphylaxis History (YES)")
    if intake.get("mono_suspected"):
        med_items.append("Mononucleosis Suspected (YES)")
    if intake.get("kidney_disease"):
        med_items.append("Kidney Disease (YES)")
    if intake.get("pregnancy_status") and str(intake.get("pregnancy_status")).lower() != "unknown":
        med_items.append(f"Pregnancy Status: {intake.get('pregnancy_status')}")
    if intake.get("breastfeeding"):
        med_items.append("Breastfeeding (YES)")
    if intake.get("meds_text"):
        med_items.append(f"Current Medications: {intake.get('meds_text')}")
    if med_items:
        details.append("• Medical History & Allergies: " + "; ".join(med_items))
    else:
        details.append("• Medical History: No acute allergies or kidney conditions flagged.")

    # Diet & Lifestyle
    diet_items = []
    if intake.get("diet_type"):
        diet_items.append(f"Diet Type: {intake.get('diet_type')}")
    if intake.get("meals_per_day"):
        diet_items.append(f"Meals/Day: {intake.get('meals_per_day')}")
    if intake.get("water_cups"):
        diet_items.append(f"Water Intake: {intake.get('water_cups')} cups/day")
    if intake.get("calorie_restrict") and intake.get("calorie_restrict") != "No":
        diet_items.append(f"Calorie Restriction Goal: {intake.get('calorie_restrict')}")
    if intake.get("alcohol_drinks_per_week"):
        diet_items.append(f"Alcohol: {intake.get('alcohol_drinks_per_week')} drinks/week")
    if intake.get("cigarette_use") and intake.get("cigarette_use") != "Never":
        diet_items.append(f"Smoking: {intake.get('cigarette_use')}")
    if diet_items:
        details.append("• Diet & Lifestyle: " + "; ".join(diet_items))

    # Activity & Fitness
    act_items = []
    if intake.get("exercise_days") is not None:
        act_items.append(f"Exercise: {intake.get('exercise_days')} days/week")
    if intake.get("activity_types"):
        acts = intake.get("activity_types")
        act_str = ", ".join(acts) if isinstance(acts, list) else str(acts)
        if act_str:
            act_items.append(f"Activities: {act_str}")
    if intake.get("sedentary_level"):
        act_items.append(f"Sedentary level: {intake.get('sedentary_level')}")
    if intake.get("chronic_pain"):
        act_items.append("Chronic Pain: Yes")
    if intake.get("limited_mobility"):
        act_items.append("Limited Mobility: Yes")
    if act_items:
        details.append("• Physical Activity: " + "; ".join(act_items))

    # Sleep & Stress
    mental_items = []
    if intake.get("sleep_hours"):
        mental_items.append(f"Sleep: {intake.get('sleep_hours')} hrs/night ({intake.get('sleep_quality', 'Normal')})")
    if intake.get("stress_level"):
        mental_items.append(f"Stress Level: {intake.get('stress_level')}/10")
    if intake.get("mood"):
        mental_items.append(f"Mood: {intake.get('mood')}")
    if mental_items:
        details.append("• Sleep & Stress: " + "; ".join(mental_items))

    return "\n".join(details) if details else "Basic intake form submitted."


# ============================================================
# CHATBOT ENGINE
# Builds a learner snapshot (intake + learning path progress + weak spots),
# turns it into a personalized system prompt, and calls the LLM layer
# (llm.py). Falls back to rule_based_response() when no LLM is available.
# ============================================================

QUIZ_INTENT = re.compile(r"\b(quiz|test) me\b|\bpractice (question|quiz)|\bask me (a|some) question", re.I)
PROFILE_INTENT = re.compile(r"\babout me\b|\bmy (health )?profile\b|\bmy intake\b|\bfor me\b", re.I)


def objective_title(drug: str, obj) -> str:
    return adaptive_learning.ADAPTIVE_REINFORCEMENT.get(drug, {}).get(obj.oid, {}).get("title") or obj.objective_text


def build_learner_snapshot(username: str, drug: str, state: dict, db: Session) -> dict:
    """Everything the chatbot (and the chat UI side panel) knows about the learner for one drug."""
    catalog = load_catalog(db)
    drug = drug if drug in catalog else "amoxicillin"
    info = catalog[drug]
    objectives = info["objectives"]
    mastery = state.get("objective_mastery") or {}

    def mastered(oid):
        row = mastery.get(oid) or {}
        return row.get("level") == "Known" or (row.get("crown_level") or 0) >= 1

    units, next_unit = [], None
    for category in info["unit_order"]:
        objs = [o for o in objectives if o.category == category]
        if not objs:
            continue
        done = sum(1 for o in objs if mastered(o.oid))
        unlocked = unit_is_unlocked(drug, category, mastery, db)
        if done == len(objs):
            status = "done"
        elif not unlocked:
            status = "locked"
        elif done or any((mastery.get(o.oid) or {}).get("last_practiced") for o in objs):
            status = "in_progress"
        else:
            status = "open"
        if next_unit is None and unlocked and status != "done":
            next_unit = category
        units.append({"category": category, "mastered": done, "total": len(objs), "status": status, "unlocked": unlocked})

    profile = adaptive_learning.get_user_learning_profile(username, drug, db, state)
    by_oid = {o.oid: o for o in objectives}
    reinforcement = adaptive_learning.ADAPTIVE_REINFORCEMENT.get(drug, {})
    struggling = [
        {"oid": oid, "title": objective_title(drug, by_oid[oid]), "category": by_oid[oid].category,
         "analogy": reinforcement.get(oid, {}).get("analogy", ""), "check": reinforcement.get(oid, {}).get("follow_up", "")}
        for oid in profile.get("struggling_oids", []) if oid in by_oid
    ]
    missed = []
    for item in profile.get("missed_questions", []):
        question = item.get("question")
        if question and question not in missed:
            missed.append(question)

    intake = state.get("intake") or {}
    mastered_count = sum(u["mastered"] for u in units)
    total = sum(u["total"] for u in units)
    return {
        "drug": drug,
        "drug_name": info["display_name"],
        "archetype": chat_prompt.normalize_archetype(state.get("archetype") or profile.get("archetype")),
        "experience_level": chat_prompt.normalize_level(
            state.get("experience_level") or intake.get("experience_level") or profile.get("experience_level")),
        "has_intake": bool(intake),
        "intake_summary": format_intake_summary(intake) if intake else "",
        "units": units,
        "next_unit": next_unit,
        "mastered_count": mastered_count,
        "total_objectives": total,
        "percent": round(100 * mastered_count / total) if total else 0,
        "xp": state.get("xp_total", 0),
        "streak": state.get("streak_current", 0),
        "hearts": state.get("hearts_remaining", 5),
        "badges": state.get("badges") or [],
        "struggling": struggling,
        "missed_questions": missed[:5],
        "_profile": profile,
    }


def starter_prompts(snapshot: dict) -> list:
    """Personalized conversation starters for the empty chat screen."""
    d = snapshot["drug_name"]
    prompts = []
    if snapshot["struggling"]:
        s = snapshot["struggling"][0]
        prompts.append({"kind": "review", "label": f"Review: {s['title']}",
                        "prompt": f"Can we review {s['title'].lower()}? I've had trouble with it."})
    if snapshot.get("next_unit"):
        unit = snapshot["next_unit"]
        prompts.append({"kind": "learn", "label": f"Teach me the {unit} unit",
                        "prompt": f"Teach me the key ideas in the {unit} unit for {d}."})
    prompts.append({"kind": "quiz", "label": f"Quiz me on {d}", "prompt": f"Quiz me on {d}, one question at a time."})
    if snapshot["has_intake"]:
        prompts.append({"kind": "profile", "label": "What should I watch for, given my profile?",
                        "prompt": f"Based on my health profile, what should I watch out for while taking {d}?"})
    else:
        prompts.append({"kind": "learn", "label": f"What is {d} used for?", "prompt": f"What is {d} and what is it used for?"})
    prompts.append({"kind": "safety", "label": f"Can I drink alcohol while taking {d}?",
                    "prompt": f"Can I drink alcohol while taking {d}?"})
    return prompts[:4]


def suggest_actions(message: str, snapshot: dict, obj) -> list:
    """Deterministic links from the chat into the learning features."""
    actions = []

    def add_lesson(category, label):
        unit = next((u for u in snapshot["units"] if u["category"] == category), None)
        if not unit or any(a.get("category") == category for a in actions):
            return
        if unit["unlocked"]:
            actions.append({"type": "lesson", "category": category, "label": label})
        elif not any(a["type"] == "path" for a in actions):
            actions.append({"type": "path", "label": "See your learning path"})

    if adaptive_learning.is_review_intent(message) and snapshot["struggling"]:
        add_lesson(snapshot["struggling"][0]["category"], f"Practice {snapshot['struggling'][0]['category']}")
    if QUIZ_INTENT.search(message) and snapshot.get("next_unit"):
        add_lesson(snapshot["next_unit"], f"Take the {snapshot['next_unit']} lesson")
    if obj is not None:
        add_lesson(obj.category, f"Practice {obj.category} lesson")
    if not snapshot["has_intake"] and PROFILE_INTENT.search(message):
        actions.append({"type": "intake", "label": "Fill in your health profile"})
    return actions[:2]


def make_title(message: str) -> str:
    text = re.sub(r"\s+", " ", message).strip()
    if len(text) <= 60:
        return text or "New conversation"
    cut = text[:60].rsplit(" ", 1)[0]
    return (cut or text[:60]).rstrip(",.;:!?") + "…"


class TopicQuizExchange(BaseModel):
    question: str = Field(max_length=1000)
    reply: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    message: str
    drug: str = "amoxicillin"
    username: str
    archetype: Optional[str] = None
    conversation_id: Optional[str] = None
    experience_level: Optional[str] = None
    # Where the learner is chatting from, e.g. "lesson:Dosage" or "path".
    page_context: Optional[str] = None
    # Set by the chat quiz when the learner asks something mid-question.
    quiz_question: Optional[str] = None
    # Topic quizzes resolve the question and curriculum from the owned attempt.
    topic_code: Optional[str] = None
    attempt_id: Optional[str] = None
    quiz_oid: Optional[str] = None
    topic_history: list[TopicQuizExchange] = Field(default_factory=list, max_length=3)


def _conv_get(conv, key):
    return conv.get(key) if isinstance(conv, dict) else getattr(conv, key)


def resolve_conversation(user: str, conversation_id: Optional[str], drug: str, db: Session):
    is_guest = user.startswith("guest_")
    conv = None
    if conversation_id:
        if is_guest:
            conv = guest_record(user[6:]).get("conversations", {}).get(conversation_id)
        else:
            conv = db.query(models.Conversation).filter_by(conversation_id=conversation_id, username=user).one_or_none()
    if conv is None:
        # Missing, deleted or someone else's id: start a fresh thread.
        data = create_conversation(NewConversationRequest(username=user, drug=drug, title="New Conversation"), db, user)
        conv = data if is_guest else db.query(models.Conversation).filter_by(conversation_id=data["conversation_id"]).one()
    return conv


def prepare_chat(request: ChatRequest, db: Session, user: str) -> dict:
    message = (request.message or "").strip()[:4000]
    if not message:
        raise HTTPException(status_code=400, detail="Message is empty.")
    catalog = load_catalog(db)
    drug = (request.drug or "amoxicillin").lower()
    if drug not in catalog:
        drug = "amoxicillin"

    state = get_user_state(user, db, drug)
    state["selected_drug"] = drug
    if request.archetype:
        state["archetype"] = request.archetype
    if request.experience_level:
        state["experience_level"] = request.experience_level

    conv = resolve_conversation(user, request.conversation_id, drug, db)
    conv_id = _conv_get(conv, "conversation_id")
    history = get_recent_history(db, user, limit=8, conversation_id=conv_id)

    # A question can name the other drug ("can I take ibuprofen too?"): ground it in that drug's course.
    active_drug = detect_drug_from_message(message, drug, db)
    snap_state = state if active_drug == drug else get_user_state(user, db, active_drug)
    snapshot = build_learner_snapshot(user, active_drug, snap_state, db)
    obj = find_relevant_objective(message, active_drug, db)

    safety_warning = check_safety_warnings(user, drug, message, db, state)
    fallback = rule_based_response(message, snapshot["archetype"], active_drug, snap_state, db, snapshot["_profile"])

    system = None
    if llm.is_configured():
        other = [v["display_name"] for k, v in catalog.items() if k != active_drug]
        user_messages = [m["content"] for m in history if m["role"] == "user"] + [message]
        system = chat_prompt.build_system_prompt(snapshot, catalog[active_drug]["objectives"],
                                                 obj.oid if obj else None, request.page_context, other,
                                                 user_messages=user_messages, quiz_question=request.quiz_question)
        focus = next((s for s in snapshot["struggling"] if obj and s["oid"] == obj.oid), None)
        if focus and focus.get("analogy"):
            system += (f"\n# Reinforcement hint\nThis question touches \"{focus['title']}\", which the learner has struggled with. "
                       f"An analogy you can adapt: {focus['analogy']}\nA check question you can ask: {focus['check']}\n")

    save_user_state(user, state, db)
    return {
        "user": user, "is_guest": user.startswith("guest_"), "conversation_id": conv_id, "drug": drug,
        "archetype": request.archetype or state.get("archetype") or "needs more explanations",
        "message": message, "safety_warning": safety_warning, "system": system,
        "messages": history + [{"role": "user", "content": message}],
        "fallback": fallback, "actions": suggest_actions(message, snapshot, obj),
    }


def persist_exchange(ctx: dict, reply: str, db: Session) -> str:
    """Saves the user message + reply and returns the conversation title."""
    now = datetime.utcnow()
    user, conv_id = ctx["user"], ctx["conversation_id"]
    if ctx["is_guest"]:
        record = guest_record(user[6:])
        conv = record.setdefault("conversations", {}).get(conv_id)
        if conv is None:
            return "New conversation"
        if conv.get("title") in ("New Conversation", None, ""):
            conv["title"] = make_title(ctx["message"])
        conv["updated_at"] = now.isoformat()
        title = conv["title"]
    else:
        conv = db.query(models.Conversation).filter_by(conversation_id=conv_id, username=user).one_or_none()
        if conv is None:
            return "New conversation"
        if conv.title in ("New Conversation", None, ""):
            conv.title = make_title(ctx["message"])
        conv.updated_at = now
        title = conv.title

    for sender, text in (("user", ctx["message"]), ("bot", reply)):
        data = dict(session_id=user, conversation_id=conv_id, sender=sender, drug=ctx["drug"],
                    archetype=ctx["archetype"], has_safety_warning=bool(ctx["safety_warning"]) if sender == "bot" else False)
        if ctx["is_guest"]:
            messages = guest_record(user[6:]).setdefault("messages", [])
            messages.append(dict(data, id=len(messages) + 1, message=text, timestamp=now.isoformat()))
        else:
            db.add(models.ChatMessage(**data, message=encryption.encrypt_data(text), timestamp=now))
    if not ctx["is_guest"]:
        db.commit()
    return title


def rule_based_response(message: str, archetype: str, active_drug: str, state: dict, db, learning_profile: dict) -> str:
    """Offline answers used when no LLM key is configured or every provider fails."""
    archetype = chat_prompt.normalize_archetype(archetype)

    if adaptive_learning.is_review_intent(message):
        return adaptive_learning.generate_proactive_review_response(learning_profile, active_drug, archetype, db)

    obj = find_relevant_objective(message, active_drug, db)
    if obj and obj.oid in learning_profile.get("struggling_oids", []):
        level = chat_prompt.normalize_level(state.get("experience_level") or state.get("intake", {}).get("experience_level"))
        base_info = obj.lesson_text.get(level, obj.lesson_text.get("beginner", "")) if isinstance(obj.lesson_text, dict) else obj.lesson_text
        return adaptive_learning.build_adaptive_explanation(obj, base_info, archetype, learning_profile, active_drug)

    small_talk = handle_small_talk(message, active_drug, db)
    if small_talk:
        return small_talk

    if obj is None:
        drug_name = load_catalog(db)[active_drug]["display_name"]
        return (
            f"I can help explain {drug_name} topics like what it is, dosage basics, "
            f"how to take it, side effects, allergies, and how it works."
        )

    level = (state.get("experience_level") or state.get("intake", {}).get("experience_level") or "beginner").lower()
    if "intermediate" in level:
        level = "intermediate"
    elif "advanced" in level:
        level = "advanced"
    else:
        level = "beginner"

    if isinstance(obj.lesson_text, dict):
        base = obj.lesson_text.get(level, obj.lesson_text.get("beginner", ""))
    else:
        base = obj.lesson_text

    if level == "beginner":
        base = simplify_text(base)
    elif level == "intermediate":
        base = clarify_text(base)

    elif level == "advanced":
        base = make_technical(base)

    # Sprint 10: Adapt explanation with alternative analogies and follow-up question if struggling
    base = adaptive_learning.build_adaptive_explanation(obj, base, archetype, learning_profile, active_drug)

    # ─── NEEDS MORE EXPLANATIONS ───────────────────────────────────────────
    # Warm, patient, always leaves the door open. Feels like a friend
    # sitting next to you explaining something at your pace.
    if archetype == "needs more explanations":
        intro = random.choice([
            "Of course — let me walk you through this.",
            "Good question. Let's go through it together.",
            "Sure, let's slow this down a bit.",
            "Happy to explain this one.",
            "Let me break this down for you.",
        ])

        bridge = random.choice([
            "Here's what you need to know:",
            "So here's the simple version:",
            "Let's look at this piece by piece:",
            "Here's what this actually means:",
        ])

        closing = random.choice([
            "Does that help? Feel free to ask me to explain any part of that again.",
            "Let me know if you want me to go even simpler on any of that.",
            "You can ask me to rephrase anything — no question is too basic.",
            "If that raised more questions, that's totally fine. Ask away.",
            "We can go as slow as you need.",
        ])

        return f"{intro}\n\n{bridge}\n\n{base}\n\n{closing}"


    # ─── THE SKEPTIC ───────────────────────────────────────────────────────
    # Doesn't just state facts — backs them up. Anticipates doubt.
    # Treats the user like someone who wants to understand the *why*,
    # not just the *what*. Occasionally pushes back gently.
    elif archetype == "the skeptic":
        intro = random.choice([
            "Fair question — and worth understanding properly.",
            "Good to question this. Here's what's actually going on.",
            "Let's not just take this at face value.",
            "Here's the real reasoning behind this.",
            "Reasonable thing to push back on. Let's dig in.",
        ])

        rationale = random.choice([
            "This isn't an arbitrary rule — it's based on how the drug actually behaves in the body.",
            "The evidence behind this is solid, not just a precaution.",
            "There's a clear mechanism here, not just a guideline someone made up.",
            "This comes from how medications actually interact with your biology.",
        ])

        closing = random.choice([
            "If that still doesn't add up, ask me to go deeper.",
            "Still skeptical? I can walk through the reasoning in more detail.",
            "Questions are good. What else doesn't sit right?",
            "That's the logic. Push back if something feels off.",
        ])

        return f"{intro}\n\n{base}\n\n{rationale}\n\n{closing}"


    # ─── TRYING NOT TO GET WORSE ───────────────────────────────────────────
    # Safety-first framing. Every response connects the information
    # to a real consequence. Calm but direct — not scary, just honest.
    elif archetype == "trying not to get worse":
        intro = random.choice([
            "This one is worth paying close attention to.",
            "This part actually makes a real difference.",
            "Let's focus on what matters most here.",
            "This is the kind of thing that can affect how you feel.",
            "Pay attention to this — it's more important than it sounds.",
        ])

        consequence = random.choice([
            "Getting this wrong can slow your recovery or make symptoms worse.",
            "This is where a lot of people run into problems — so it's worth doing right.",
            "Skipping or mishandling this step can set you back.",
            "Following this correctly is one of the better things you can do for yourself right now.",
        ])

        closing = random.choice([
            "When in doubt, check with your clinician rather than guessing.",
            "If something feels off, that's worth flagging to someone who can help.",
            "Your job right now is to not make things harder on your body.",
            "Small things done consistently make a big difference here.",
        ])

        return f"{intro}\n\n{base}\n\n{consequence}\n\n{closing}"


    # ─── ALL IN UNTIL I'M NOT ──────────────────────────────────────────────
    # Minimal. No fluff. Gets to the point fast and stops.
    # Respects that the user doesn't want to be lectured.
    elif archetype == "all in until i'm not":
        sentences = [s.strip() for s in base.split(".") if s.strip()]

        if level == "beginner":
            core = sentences[0] if sentences else base
        else:
            core = ". ".join(sentences[:2]) if len(sentences) >= 2 else sentences[0]

        ending = random.choice([
            "That's it.",
            "That's all!",
            "Follow that.",
            "Simple as that.",
            "",  # sometimes just silence is right
        ])

        return f"{core}. {ending}".strip() if ending else f"{core}."


@app.get("/drugs")
def get_lesson_drugs(db: Session = Depends(get_db)):
    return [
        {"key": key, "name": entry["display_name"]}
        for key, entry in load_catalog(db).items()
        if entry["objectives"]
    ]


@app.get("/drug-content/{drug_name}")

def get_drug_content(drug_name: str, db: Session = Depends(get_db)):
    drug_key = drug_name.lower()

    drug_data = drug_content(db, drug_key)
    objectives = drug_data["objectives"]

    grouped = {
        "Facts": [],
        "Dosage": [],
        "Procedures": [],
        "Rationales": [],
    }

    for obj in objectives:
        grouped.setdefault(obj.category, []).append({
            "oid": obj.oid,
            "objective_text": obj.objective_text,
            "lesson_text": obj.lesson_text,
            "question": obj.questions["initial"].question_text,
            "remediation_lesson": obj.remediation_lesson,
        })

    return {
        "drug": drug_data["display_name"],
        "categories": grouped
    }


def build_mastery_for_drug(drug_key: str, db):
    objectives = load_catalog(db)[drug_key]["objectives"]
    return {
        obj.oid: {"level": "Unknown", "correct_streak": 0, "crown_level": 0, "last_practiced": None}
        for obj in objectives
    }

# ============================================================
# GAMIFICATION HELPERS (Phase 1)
# ============================================================

def category_crown_summary(drug: str, category: str, mastery: dict, db) -> dict:
    """Lowest/highest crown level across every objective in one category."""
    objectives = [o for o in load_catalog(db)[drug]["objectives"] if o.category == category]
    if not objectives:
        return {"min_crown": 0, "max_crown": 0, "total": 0}
    crowns = [mastery.get(o.oid, {}).get("crown_level", 0) for o in objectives]
    return {"min_crown": min(crowns), "max_crown": max(crowns), "total": len(objectives)}


def unit_is_unlocked(drug: str, category: str, mastery: dict, db) -> bool:
    """Units unlock sequentially: the first unit is always open, each later
    one opens once every objective in the previous unit has crown_level >= 1."""
    order = load_catalog(db)[drug]["unit_order"]
    if category not in order:
        raise HTTPException(status_code=404, detail="Category not found.")
    idx = order.index(category)
    if idx == 0:
        return True
    previous_category = order[idx - 1]
    summary = category_crown_summary(drug, previous_category, mastery, db)
    return summary["total"] == 0 or summary["min_crown"] >= 1


# One-line, archetype-flavored lesson feedback (kept short — this fires after
# every question, so it stays snappy rather than reusing the longer /chat
# templates in rule_based_response()).
FEEDBACK_FLAVOR = {
    "needs more explanations": {
        "correct": ["Nice work — that's exactly right.", "Got it! You're following this well.", "Correct — nicely done."],
        "wrong": ["Not quite, but that's okay — here's the idea:", "No worries, let's go over it again:", "Close, but let's slow down on this one:"],
    },
    "the skeptic": {
        "correct": ["Correct — and the reasoning holds up.", "Right, and here's why that's solid:", "Yes — backed by how the drug actually works."],
        "wrong": ["Not quite — here's the evidence:", "That's off. Here's the actual reasoning:", "Incorrect, but worth understanding why:"],
    },
    "trying not to get worse": {
        "correct": ["Correct — that's the safe answer.", "Right, and that matters for your safety.", "Yes — good, that's important to get right."],
        "wrong": ["Not quite — this one matters, so here's the safe answer:", "Off track here, and this is a safety-relevant one:", "Incorrect — pay attention to this:"],
    },
    "all in until i'm not": {
        "correct": ["Correct.", "Right.", "Yes, that's it."],
        "wrong": ["Wrong.", "Not that.", "Nope, here's the answer:"],
    },
}


def flavor_feedback(archetype: str, correct: bool) -> str:
    key = archetype.strip().lower().replace("’", "'").replace("‘", "'").replace("`", "'")
    bucket = FEEDBACK_FLAVOR.get(key, FEEDBACK_FLAVOR["needs more explanations"])
    options = bucket["correct"] if correct else bucket["wrong"]
    return random.choice(options)


def compute_xp(correct: bool, combo: int) -> int:
    """Base 10 XP per correct answer, plus up to +8 for a same-lesson combo."""
    if not correct:
        return 0
    base = 10
    bonus = min(max(combo - 1, 0), 4) * 2
    return base + bonus


def update_streak(state: dict) -> None:
    """Advances the daily streak at most once per calendar day."""
    today = date.today().isoformat()
    last = state.get("last_active_date")

    if last == today:
        pass  # already counted today, no change
    elif last is not None and (date.fromisoformat(today) - date.fromisoformat(last)).days == 1:
        state["streak_current"] = state.get("streak_current", 0) + 1
    else:
        state["streak_current"] = 1

    state["last_active_date"] = today
    state["streak_longest"] = max(state.get("streak_longest", 0), state["streak_current"])


def check_badges(state: dict, drug: str, db) -> list:
    """Awards any badges newly earned this lesson; returns just the new ones."""
    newly_earned = []
    badges = state.setdefault("badges", [])
    mastery = state.get("objective_mastery", {})
    lesson = state.get("current_lesson") or {}

    if state.get("streak_current", 0) >= 7 and "streak_7" not in badges:
        badges.append("streak_7")
        newly_earned.append("streak_7")

    if lesson.get("total", 0) > 0 and lesson.get("hearts", 0) == 5:
        badge_id = f"perfect_lesson_{drug}"
        if badge_id not in badges:
            badges.append(badge_id)
            newly_earned.append(badge_id)

    objectives = load_catalog(db)[drug]["objectives"]
    if objectives and all(mastery.get(o.oid, {}).get("crown_level", 0) >= 5 for o in objectives):
        badge_id = f"{drug}_mastered"
        if badge_id not in badges:
            badges.append(badge_id)
            newly_earned.append(badge_id)

    return newly_earned


def generate_intake_warnings(intake: dict) -> list[str]:
    warnings = []

    if intake.get("penicillin_allergy"):
        warnings.append("Penicillin allergy indicated. Amoxicillin is penicillin-family. Consult a clinician/pharmacist.")
    if intake.get("anaphylaxis_history"):
        warnings.append("History of severe allergic reactions/anaphylaxis. Consult a clinician.")
    if intake.get("mono_suspected"):
        warnings.append("If EBV/mono is present, amoxicillin can be associated with rash. Discuss with a clinician.")
    if intake.get("kidney_disease"):
        warnings.append("Kidney disease indicated. Some medicines need adjustments. Consult a clinician.")

    preg = intake.get("pregnancy_status", "Unknown")
    if preg in ("Pregnant", "Trying", "Unsure"):
        warnings.append(f"Pregnancy status: {preg}. Medication decisions should be reviewed with a clinician.")

    if intake.get("breastfeeding"):
        warnings.append("Breastfeeding indicated. Ask a clinician/pharmacist about medication safety.")

    meds = normalize(intake.get("meds_text", ""))
    if meds:
        if "warfarin" in meds:
            warnings.append("Warfarin listed. Some antibiotics can affect blood thinner management. Consult a clinician.")
        if "methotrexate" in meds:
            warnings.append("Methotrexate listed. Some antibiotics can affect side effects/levels. Consult a clinician.")

    if not warnings:
        warnings.append("No major warnings flagged by the prototype rules. Still follow the prescription label.")

    return warnings


class IntakeRequest(BaseModel):
    username: str
    drug: str
    experience_level: str = "beginner"
    # --- existing medical fields (unchanged) ---
    penicillin_allergy: bool = False
    anaphylaxis_history: bool = False
    mono_suspected: bool = False
    kidney_disease: bool = False
    breastfeeding: bool = False
    pregnancy_status: str = "Unknown"
    meds_text: str = ""
    # --- new: About Me ---
    dob: str = ""
    gender: str = ""
    archetype: str = ""
    alcohol_drinks_per_week: int = 0
    cigarette_use: str = ""
    cigarette_years: int = 0
    # --- new: Diet ---
    meals_per_day: str = ""
    skips_meals: str = ""
    water_cups: int = 0
    fruit_veg_servings: int = 0
    diet_type: str = ""
    calorie_restrict: str = "No"
    caffeine: str = ""
    # --- new: Sleep & Stress ---
    sleep_hours: int = 7
    sleep_quality: str = ""
    trouble_falling_asleep: bool = False
    waking_night: bool = False
    waking_early: bool = False
    stress_level: int = 5
    mood: str = ""
    stress_practices: List[str] = []
    # --- new: Activity ---
    exercise_days: int = 0
    activity_types: List[str] = []
    sedentary_level: str = ""
    chronic_pain: bool = False
    limited_mobility: bool = False

class AssessmentRequest(BaseModel):
    username: str
    drug: str
    answers: dict[str, str]

class CheckpointRequest(BaseModel):
    username: str
    drug: str
    answers: dict[str, str]


class LessonStartRequest(BaseModel):
    username: str
    drug: str
    category: str


class LessonAnswerRequest(BaseModel):
    username: str
    drug: str
    oid: str
    answer: str


class LessonCompleteRequest(BaseModel):
    username: str
    drug: str


@app.post("/intake")
def save_intake(request: IntakeRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    state = get_user_state(authenticated_email, db, request.drug)
    drug = request.drug.lower()
    previous_drug = state.get("selected_drug", "amoxicillin")
    intake = request.model_dump()
    intake["username"] = authenticated_email

    state["selected_drug"] = drug
    state["intake"] = intake
    # The archetype is now chosen inside the intake form itself (instead of a
    # sidebar dropdown that was easy to ignore), so persist it as soon as the
    # intake is saved rather than waiting for the user's first chat message.
    if request.archetype:
        state["archetype"] = request.archetype
    state["warnings"] = generate_intake_warnings(intake)

    if not state.get("objective_mastery"):
        state["objective_mastery"] = build_mastery_for_drug(drug, db)

    save_user_state(authenticated_email, state, db)

    return {
        "drug": drug,
        "warnings": state["warnings"]
    }

class NewConversationRequest(BaseModel):
    username: str
    drug: Optional[str] = "amoxicillin"
    title: Optional[str] = "New Conversation"

@app.get("/conversations/{username}")
def get_conversations(username: str, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    # The identity always comes from the sign-in token or guest session; the URL username is ignored.
    if authenticated_email.startswith("guest_"):
        convs = list(guest_record(authenticated_email[6:]).get("conversations", {}).values())
        return sorted(convs, key=lambda c: c.get("updated_at") or "", reverse=True)
    rows = db.query(models.Conversation).filter_by(username=authenticated_email).order_by(models.Conversation.updated_at.desc()).all()
    return [conversation_dict(row) for row in rows]

@app.post("/conversations/new")
def create_conversation(req: NewConversationRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    now = datetime.utcnow()
    conv_id = "conv_" + uuid.uuid4().hex
    drug = (req.drug or "amoxicillin").lower()
    drug_content(db, drug)
    if authenticated_email.startswith("guest_"):
        row = {"conversation_id": conv_id, "title": req.title or "New Conversation", "drug": drug, "created_at": now.isoformat(), "updated_at": now.isoformat()}
        guest_record(authenticated_email[6:]).setdefault("conversations", {})[conv_id] = row
        return row
    conv = models.Conversation(conversation_id=conv_id, username=authenticated_email, title=req.title or "New Conversation", drug=drug, created_at=now, updated_at=now)
    db.add(conv)
    db.flush()
    return conversation_dict(conv)

@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    if authenticated_email.startswith("guest_"):
        record = guest_record(authenticated_email[6:])
        if record.get("conversations", {}).pop(conversation_id, None) is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        record["messages"] = [row for row in record.get("messages", []) if row["conversation_id"] != conversation_id]
        return {"status": "deleted", "conversation_id": conversation_id}
    conv = db.query(models.Conversation).filter_by(conversation_id=conversation_id, username=authenticated_email).one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.query(models.ChatMessage).filter_by(conversation_id=conversation_id, session_id=authenticated_email).delete()
    db.delete(conv)
    return {"status": "deleted", "conversation_id": conversation_id}


class RenameConversationRequest(BaseModel):
    title: str


@app.patch("/conversations/{conversation_id}")
def rename_conversation(conversation_id: str, req: RenameConversationRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    title = re.sub(r"\s+", " ", req.title or "").strip()[:80]
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty.")
    if authenticated_email.startswith("guest_"):
        conv = guest_record(authenticated_email[6:]).get("conversations", {}).get(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        conv["title"] = title
        return conv
    conv = db.query(models.Conversation).filter_by(conversation_id=conversation_id, username=authenticated_email).one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    conv.title = title
    return conversation_dict(conv)


def _chat_user(request_username: Optional[str], authenticated_email: str) -> str:
    # Always the signed-in account or guest session, never a name sent by the browser.
    return authenticated_email


@app.post("/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    """Non-streaming chat (used by the chat quiz). Same brain as /chat/stream."""
    user = _chat_user(request.username, authenticated_email)
    if request.topic_code is not None:
        return chat_with_topic_quiz(request, db, user)
    ctx = prepare_chat(request, db, user)
    raw = llm.generate(ctx["system"], ctx["messages"]) if ctx["system"] else None
    reply, suggestions = chat_prompt.split_followups(raw) if raw else (ctx["fallback"], [])
    title = persist_exchange(ctx, reply, db)
    return {"response": reply, "safety_warning": ctx["safety_warning"], "drug": ctx["drug"],
            "archetype": ctx["archetype"], "conversation_id": ctx["conversation_id"], "conversation_title": title,
            "suggestions": suggestions, "actions": ctx["actions"]}


def chat_with_topic_quiz(request, db, user):
    message = request.message.strip()[:4000]
    if not message:
        raise HTTPException(400, "Message is empty.")
    if not request.attempt_id:
        raise HTTPException(400, "Start a topic quiz before asking for help.")
    with topic_learning(db, user, request.topic_code) as learning:
        context = learning.quiz_chat_context(request.attempt_id, request.quiz_oid)

    guest_state = guest_record(user[6:])["state"] if user.startswith("guest_") else None
    if guest_state is None:
        settings = db.query(models.UserLearningState).join(models.User).filter(models.User.email == user).one_or_none()
        archetype = settings.archetype if settings else None
        experience = settings.experience_level if settings else None
    else:
        archetype = guest_state.get("archetype")
        experience = guest_state.get("experience_level")
    warning = check_safety_warnings(user, "", message, db, guest_state)
    db.commit()  # release the read transaction before calling a provider

    messages = []
    for exchange in request.topic_history:
        messages.extend([
            {"role": "user", "content": exchange.question},
            {"role": "assistant", "content": exchange.reply},
        ])
    messages.append({"role": "user", "content": message})
    raw = None
    if llm.is_configured():
        try:
            system = chat_prompt.build_topic_quiz_prompt(context, archetype, experience)
            raw = llm.generate(system, messages)
        except Exception as error:
            print(f"[topic chat] provider unavailable: {type(error).__name__}")
    reply, _ = chat_prompt.split_followups(raw) if raw else ("", [])
    if not reply:
        reply = context["hint"] or "The assistant is unavailable right now. Start a quiz question for a lesson hint."
    return {"response": reply, "safety_warning": warning}


@app.post("/chat/stream")
def chat_stream(request: ChatRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    """
    Streams the reply as newline-delimited JSON events:
      {"type": "meta",  "conversation_id", "safety_warning"}
      {"type": "delta", "text"}            (repeated)
      {"type": "done",  "response", "suggestions", "actions", "conversation_id", "conversation_title"}
    """
    if request.topic_code is not None:
        raise HTTPException(400, "Topic quiz help is available through /chat.")
    user = _chat_user(request.username, authenticated_email)
    ctx = prepare_chat(request, db, user)
    db.commit()  # release SQLite's write lock before the long-running stream
    hold_back = len(chat_prompt.FOLLOWUP_MARKER)

    def event(payload):
        return json.dumps(payload) + "\n"

    def events():
        yield event({"type": "meta", "conversation_id": ctx["conversation_id"], "safety_warning": ctx["safety_warning"]})
        full, sent, saved = "", 0, False
        try:
            if ctx["system"]:
                for piece in llm.stream(ctx["system"], ctx["messages"]):
                    full += piece
                    marker_at = full.find(chat_prompt.FOLLOWUP_MARKER)
                    # Never show the follow-up block; hold back a few chars in case the marker is mid-arrival.
                    visible = full[:marker_at] if marker_at != -1 else full[:max(0, len(full) - hold_back)]
                    if len(visible) > sent:
                        yield event({"type": "delta", "text": visible[sent:]})
                        sent = len(visible)
            reply, suggestions = chat_prompt.split_followups(full) if full.strip() else (ctx["fallback"], [])
            if not full.strip():
                yield event({"type": "delta", "text": reply})
            with SessionLocal() as session:
                title = persist_exchange(ctx, reply, session)
            saved = True
            yield event({"type": "done", "response": reply, "suggestions": suggestions, "actions": ctx["actions"],
                         "conversation_id": ctx["conversation_id"], "conversation_title": title})
        finally:
            # The user hit Stop or closed the tab: keep what they already saw.
            if not saved and full.strip():
                try:
                    with SessionLocal() as session:
                        persist_exchange(ctx, chat_prompt.split_followups(full)[0], session)
                except Exception as e:
                    print(f"[chat/stream] could not save partial reply: {e}")

    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class PreferencesRequest(BaseModel):
    username: str
    archetype: Optional[str] = None
    experience_level: Optional[str] = None


@app.post("/preferences")
def save_preferences(request: PreferencesRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    """Saves the learning style / experience level right away, so the chatbot,
    lessons and chat quiz all use the new choice without re-submitting the intake form."""
    user = _chat_user(request.username, authenticated_email)
    state = get_user_state(user, db)
    if request.archetype:
        archetype = chat_prompt.normalize_archetype(request.archetype)
        if archetype != (request.archetype or "").strip().lower().replace("’", "'"):
            raise HTTPException(status_code=400, detail="Unknown learning style.")
        state["archetype"] = chat_prompt.ARCHETYPE_LABELS[archetype]
    if request.experience_level:
        state["experience_level"] = chat_prompt.normalize_level(request.experience_level)
    save_user_state(user, state, db)
    return {"archetype": state.get("archetype"), "experience_level": state.get("experience_level")}


@app.get("/chat/context/{drug}")
def chat_context(drug: str, username: str, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    """Learner snapshot for the chat UI: progress, weak spots and personalized starters."""
    # The identity always comes from the sign-in token or guest session; the URL username is ignored.
    catalog = load_catalog(db)
    drug = drug.lower() if drug.lower() in catalog else "amoxicillin"
    state = get_user_state(authenticated_email, db, drug)
    snapshot = build_learner_snapshot(authenticated_email, drug, state, db)
    snapshot.pop("_profile", None)
    snapshot.pop("intake_summary", None)
    for item in snapshot["struggling"]:
        item.pop("analogy", None)
        item.pop("check", None)
    snapshot["starter_prompts"] = starter_prompts(snapshot)
    snapshot["archetype_label"] = chat_prompt.ARCHETYPE_LABELS[snapshot["archetype"]]
    snapshot["drugs"] = [{"key": key, "name": value["display_name"]} for key, value in catalog.items()]
    snapshot["llm_enabled"] = llm.is_configured()
    return snapshot


@app.get("/chat/history/{username}")
def get_chat_history(username: str, conversation_id: Optional[str] = None, limit: int = 200, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    # The identity always comes from the sign-in token or guest session; the URL username is ignored.
    rows = history_rows(authenticated_email, db, conversation_id=conversation_id, limit=limit)
    # Only a flag is stored with each reply; rebuild the actual warning text from the question that triggered it.
    state = None
    for i, row in enumerate(rows):
        if row["sender"] == "bot" and row.get("has_safety_warning"):
            question = next((r["message"] for r in reversed(rows[:i]) if r["sender"] == "user"), "")
            if state is None:
                state = get_user_state(authenticated_email, db, row.get("drug") or "amoxicillin")
            row["safety_warning"] = check_safety_warnings(authenticated_email, row.get("drug") or "amoxicillin", question, db, state)
    return rows


@app.get("/learning-plan/{drug}")
def get_learning_plan(drug: str, username: str, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    state = get_user_state(authenticated_email, db, drug)
    drug = drug.lower()
    objectives = load_catalog(db)[drug]["objectives"]
    queue = state.get("lesson_queue", [])

    queued = []
    for obj in objectives:
        if obj.oid in queue:
            queued.append({
                "oid": obj.oid,
                "category": obj.category,
                "objective_text": obj.objective_text,
                "lesson_text": obj.lesson_text,
                "question": obj.questions["checkpoint"].question_text,
                "remediation_lesson": obj.remediation_lesson
            })

    has_started = bool(state.get("last_results"))

    return {
        "drug": load_catalog(db)[drug]["display_name"],
        "queued_objectives": queued,
        "has_started": has_started
    }

@app.post("/checkpoint")
def submit_checkpoint(request: CheckpointRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    state = get_user_state(authenticated_email, db, request.drug)
    drug = request.drug.lower()
    objectives = load_catalog(db)[drug]["objectives"]
    obj_map = {o.oid: o for o in objectives}

    results = []
    missed = []

    if not state.get("objective_mastery"):
        state["objective_mastery"] = build_mastery_for_drug(drug, db)

    for oid, user_ans in request.answers.items():
        if oid not in obj_map:
            continue

        obj = obj_map[oid]
        ok = answer_is_correct(user_ans, obj.keyword_sets_by_kind["checkpoint"])

        if ok:
            state["objective_mastery"][oid]["correct_streak"] += 1
            state["objective_mastery"][oid]["level"] = "Known"
        else:
            state["objective_mastery"][oid]["correct_streak"] = 0
            state["objective_mastery"][oid]["level"] = "Unknown"
            missed.append(oid)

        results.append({
            "oid": oid,
            "correct": ok,
            "message": "Correct" if ok else f"Review: {obj.objective_text}",
            "question": obj.questions["checkpoint"].question_text,
            "category": obj.category
        })

    state["lesson_queue"] = missed
    state["last_results"] = results
    record_assessment(authenticated_email, drug, "checkpoint", request.answers, results, db)
    save_user_state(authenticated_email, state, db)

    all_mastered = all(
        rec["level"] == "Known"
        for rec in state["objective_mastery"].values()
    )

    return {
        "results": results,
        "missed": [
            {
                "oid": oid,
                "question": obj_map[oid].question,
                "category": obj_map[oid].category
            }
            for oid in missed
        ],
        "all_mastered": all_mastered,
        "mastery": state["objective_mastery"]
    }

@app.get("/progress/{drug}")
def get_progress(drug: str, username: str, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    state = get_user_state(authenticated_email, db, drug)
    drug = drug.lower()
    objectives = load_catalog(db)[drug]["objectives"]
    mastery = state.get("objective_mastery", {})

    known = 0
    by_category = {}

    for obj in objectives:
        level = mastery.get(obj.oid, {}).get("level", "Unknown")
        if level == "Known":
            known += 1

        if obj.category not in by_category:
            by_category[obj.category] = {"known": 0, "total": 0}

        by_category[obj.category]["total"] += 1
        if level == "Known":
            by_category[obj.category]["known"] += 1

    return {
        "drug": load_catalog(db)[drug]["display_name"],
        "known": known,
        "total": len(objectives),
        "by_category": by_category,
        "last_results": state.get("last_results", [])
    }

@app.get("/profile/{username}")
def get_profile(username: str, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    if username != authenticated_email:
        raise HTTPException(status_code=403, detail="Cannot access another user profile.")
    state = get_user_state(authenticated_email, db)
    return {
        "username": username,
        "selected_drug": state.get("selected_drug", "amoxicillin"),
        "archetype": state.get("archetype", "needs more explanations"),
        "intake": state.get("intake", {}),
        "warnings": state.get("warnings", []),
        "lesson_queue": state.get("lesson_queue", []),
        "last_results": state.get("last_results", []),
        "objective_mastery": state.get("objective_mastery", {}),
        "xp_total": state.get("xp_total", 0),
        "streak_current": state.get("streak_current", 0),
        "streak_longest": state.get("streak_longest", 0),
        "hearts_remaining": state.get("hearts_remaining", 5),
        "badges": state.get("badges", []),
        "review_items": state.get("review_items", []),
    }


@app.post("/initial-assessment")
def initial_assessment(request: AssessmentRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    state = get_user_state(authenticated_email, db, request.drug)
    drug = request.drug.lower()
    objectives = load_catalog(db)[drug]["objectives"]

    state["selected_drug"] = drug
    state["assessment_answers"] = request.answers
    state["objective_mastery"] = build_mastery_for_drug(drug, db)

    results = []
    lesson_queue = []

    for obj in objectives:
        user_ans = request.answers.get(obj.oid, "")
        ok = answer_is_correct(user_ans, obj.keyword_sets_by_kind["initial"])

        if ok:
            state["objective_mastery"][obj.oid]["correct_streak"] = 1
            state["objective_mastery"][obj.oid]["level"] = "Known"
        else:
            state["objective_mastery"][obj.oid]["correct_streak"] = 0
            state["objective_mastery"][obj.oid]["level"] = "Unknown"
            lesson_queue.append(obj.oid)

        results.append({
            "oid": obj.oid,
            "correct": ok,
            "message": "Correct" if ok else f"Review: {obj.objective_text}",
            "question": obj.questions["initial"].question_text,
            "category": obj.category
        })

    state["lesson_queue"] = lesson_queue
    state["last_results"] = results
    record_assessment(authenticated_email, drug, "initial", request.answers, results, db)
    save_user_state(authenticated_email, state, db)

    return {
        "results": results,
        "lesson_queue": lesson_queue,
        "mastery": state["objective_mastery"]
    }


# ============================================================
# GAMIFIED LEARNING LOOP (Phase 1)
# ============================================================

class TopicLessonStart(BaseModel):
    category: str


class TopicLessonRun(BaseModel):
    attempt_id: str


class TopicLessonQuestion(TopicLessonRun):
    oid: str


class TopicLessonAnswer(TopicLessonQuestion):
    answer: str


@contextmanager
def topic_learning(db, username, topic_code):
    guest = guest_record(username[6:]) if username.startswith("guest_") else None
    with (guest.setdefault("topic_lock", Lock()) if guest is not None else nullcontext()):
        yield TopicLearning(db, username, topic_code, guest)


@app.get("/topics/{topic_code}/path")
def get_topic_path(topic_code: str, db: Session = Depends(get_db), username: str = Depends(require_authenticated_user)):
    with topic_learning(db, username, topic_code) as learning:
        return learning.path()


@app.get("/topics/{topic_code}/content")
def get_topic_quiz_content(topic_code: str, db: Session = Depends(get_db), username: str = Depends(require_authenticated_user)):
    with topic_learning(db, username, topic_code) as learning:
        return learning.content()


@app.post("/topics/{topic_code}/lesson/start")
def start_topic_lesson(topic_code: str, request: TopicLessonStart, db: Session = Depends(get_db), username: str = Depends(require_authenticated_user)):
    with topic_learning(db, username, topic_code) as learning:
        return learning.start(request.category)


@app.post("/topics/{topic_code}/lesson/answer")
def answer_topic_lesson(topic_code: str, request: TopicLessonAnswer, db: Session = Depends(get_db), username: str = Depends(require_authenticated_user)):
    with topic_learning(db, username, topic_code) as learning:
        return learning.answer(request.attempt_id, request.oid, request.answer, answer_is_correct)


@app.post("/topics/{topic_code}/lesson/hint")
def hint_for_topic_lesson(topic_code: str, request: TopicLessonQuestion, db: Session = Depends(get_db), username: str = Depends(require_authenticated_user)):
    with topic_learning(db, username, topic_code) as learning:
        return learning.hint(request.attempt_id, request.oid)


@app.post("/topics/{topic_code}/lesson/complete")
def complete_topic_lesson(topic_code: str, request: TopicLessonRun, db: Session = Depends(get_db), username: str = Depends(require_authenticated_user)):
    with topic_learning(db, username, topic_code) as learning:
        return learning.complete(request.attempt_id)


@app.get("/path/{drug}")
def get_path(drug: str, username: Optional[str] = None, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    """Returns the 4-unit skill path (Facts/Dosage/Procedures/Rationales) for
    one drug, with each unit's lock state and crown progress."""
    state = get_user_state(authenticated_email, db, drug)
    drug = drug.lower()

    if not state.get("objective_mastery"):
        state["objective_mastery"] = build_mastery_for_drug(drug, db)
        save_user_state(authenticated_email, state, db)

    mastery = state["objective_mastery"]
    units = []
    for category in load_catalog(db)[drug]["unit_order"]:
        summary = category_crown_summary(drug, category, mastery, db)
        if summary["total"] == 0:
            continue
        units.append({
            "category": category,
            "unlocked": unit_is_unlocked(drug, category, mastery, db),
            "min_crown": summary["min_crown"],
            "max_crown": summary["max_crown"],
            "objective_count": summary["total"],
        })

    return {
        "drug": load_catalog(db)[drug]["display_name"],
        "units": units,
        "xp_total": state.get("xp_total", 0),
        "streak_current": state.get("streak_current", 0),
        "hearts_remaining": state.get("hearts_remaining", 5),
        "badges": state.get("badges", []),
        "review_items": state.get("review_items", []),
    }


@app.post("/lesson/start")
def lesson_start(request: LessonStartRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    """Starts a short (up to 5 question) lesson for one unit, picking the
    objectives with the lowest crown level first."""
    state = get_user_state(authenticated_email, db, request.drug)
    drug = request.drug.lower()
    category = request.category

    if drug not in load_catalog(db):
        raise HTTPException(status_code=404, detail="Drug not found.")

    # Hearts are a persistent life pool, not a per-lesson freebie. Once they
    # hit 0, a new lesson attempt is blocked until the user has reviewed
    # their missed questions and called /lesson/review-complete to refill —
    # otherwise "running out of hearts" had no real consequence.
    if state.get("hearts_remaining", 5) <= 0:
        raise HTTPException(
            status_code=403,
            detail="You're out of hearts. Review your missed questions before starting a new lesson.",
        )

    if not state.get("objective_mastery"):
        state["objective_mastery"] = build_mastery_for_drug(drug, db)

    mastery = state["objective_mastery"]

    if not unit_is_unlocked(drug, category, mastery, db):
        raise HTTPException(status_code=400, detail=f"{category} is locked until the previous unit is started.")

    objectives = [o for o in load_catalog(db)[drug]["objectives"] if o.category == category]
    if not objectives:
        raise HTTPException(status_code=404, detail="No objectives found for this unit.")

    ordered = sorted(objectives, key=lambda o: mastery.get(o.oid, {}).get("crown_level", 0))
    lesson_objectives = ordered[:5]

    starting_hearts = state.get("hearts_remaining", 5)

    state["current_lesson"] = {
        "drug": drug,
        "category": category,
        "oids": [o.oid for o in lesson_objectives],
        "index": 0,
        "hearts": starting_hearts,
        "combo": 0,
        "xp_earned": 0,
        "total": len(lesson_objectives),
        "correct_count": 0,
    }
    state["selected_drug"] = drug
    # Keep the top-level hearts_remaining (shown on the path screen and in
    # /profile) in sync with the lesson's carried-over hearts.
    state["hearts_remaining"] = starting_hearts
    save_user_state(authenticated_email, state, db)

    first = lesson_objectives[0]
    return {
        "drug": load_catalog(db)[drug]["display_name"],
        "category": category,
        "total_questions": len(lesson_objectives),
        "hearts": starting_hearts,
        "question": {"oid": first.oid, "question": first.question, "category": first.category},
    }


@app.post("/lesson/answer")
def lesson_answer(request: LessonAnswerRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    """Grades one question inside the in-progress lesson and returns instant,
    archetype-flavored feedback plus the updated hearts/XP/crown state."""
    state = get_user_state(authenticated_email, db, request.drug)
    drug = request.drug.lower()
    lesson = state.get("current_lesson")

    if (not lesson or lesson.get("drug") != drug or lesson.get("hearts", 0) <= 0
            or lesson.get("index", 0) >= len(lesson.get("oids", []))
            or request.oid != lesson["oids"][lesson["index"]]):
        raise HTTPException(status_code=400, detail="No matching lesson in progress. Call /lesson/start first.")

    obj = get_objective_by_id(load_catalog(db)[drug]["objectives"], request.oid)
    if not obj:
        raise HTTPException(status_code=404, detail="Objective not found.")

    mastery = state.setdefault("objective_mastery", {})
    record = mastery.setdefault(request.oid, {"level": "Unknown", "correct_streak": 0, "crown_level": 0, "last_practiced": None})

    correct = answer_is_correct(request.answer, obj.accepted_keyword_sets)
    archetype = state.get("archetype", "needs more explanations")

    if correct:
        record["crown_level"] = min(5, record.get("crown_level", 0) + 1)
        record["correct_streak"] = record.get("correct_streak", 0) + 1
        lesson["combo"] = lesson.get("combo", 0) + 1
        lesson["correct_count"] = lesson.get("correct_count", 0) + 1
    else:
        record["correct_streak"] = 0
        lesson["combo"] = 0
        lesson["hearts"] = max(0, lesson.get("hearts", 5) - 1)
        missed = lesson.setdefault("missed_oids", [])
        if request.oid not in missed:
            missed.append(request.oid)

    record["level"] = "Known" if record["crown_level"] >= 1 else "Unknown"
    record["last_practiced"] = date.today().isoformat()

    xp_gained = compute_xp(correct, lesson["combo"])
    lesson["xp_earned"] = lesson.get("xp_earned", 0) + xp_gained
    state["xp_total"] = state.get("xp_total", 0) + xp_gained

    lesson["index"] = lesson.get("index", 0) + 1
    session_over = lesson["hearts"] <= 0 or lesson["index"] >= lesson.get("total", 0)

    # Keep the top-level hearts_remaining (path screen / profile) in sync
    # with what's actually left in this lesson, instead of staying frozen
    # at its blank-state default of 5.
    state["hearts_remaining"] = lesson["hearts"]

    next_question = None
    if not session_over:
        next_oid = lesson["oids"][lesson["index"]]
        next_obj = get_objective_by_id(load_catalog(db)[drug]["objectives"], next_oid)
        next_question = {"oid": next_obj.oid, "question": next_obj.question, "category": next_obj.category}

    feedback_line = flavor_feedback(archetype, correct)
    detail_text = obj.lesson_text if correct else obj.remediation_lesson

    record_assessment(authenticated_email, drug, "lesson", {request.oid: request.answer},
                      [{"oid": obj.oid, "correct": correct, "message": "Correct" if correct else f"Review: {obj.objective_text}"}],
                      db, make_latest=False)
    # Keep the legacy learning plan aligned with current relational mastery.
    state["lesson_queue"] = [item.oid for item in load_catalog(db)[drug]["objectives"]
                              if mastery.get(item.oid, {}).get("level", "Unknown") != "Known"]
    save_user_state(authenticated_email, state, db)

    return {
        "correct": correct,
        "feedback": feedback_line,
        "detail": detail_text,
        "xp_gained": xp_gained,
        "xp_total": state["xp_total"],
        "hearts": lesson["hearts"],
        "combo": lesson["combo"],
        "crown_level": record["crown_level"],
        "session_over": session_over,
        "next_question": next_question,
    }


@app.post("/lesson/complete")
def lesson_complete(request: LessonCompleteRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    """Finalizes the daily streak and any badges once a lesson session ends
    (either all questions answered or hearts ran out)."""
    state = get_user_state(authenticated_email, db, request.drug)
    drug = request.drug.lower()
    lesson = state.get("current_lesson")
    if not lesson or lesson.get("drug") != drug:
        raise HTTPException(status_code=400, detail="No matching lesson in progress.")
    if lesson["hearts"] > 0 and lesson["index"] < lesson["total"]:
        raise HTTPException(status_code=400, detail="Finish the current lesson before completing it.")

    update_streak(state)
    newly_earned = check_badges(state, drug, db)

    ran_out_of_hearts = lesson.get("hearts", 0) <= 0

    # Out of hearts: build the remediation review for exactly what they got
    # wrong this session. This is stored on the user's state (not just
    # returned once) so a "review pending" banner can be shown on the path
    # screen even if they navigate away before finishing the review.
    review_items = []
    if ran_out_of_hearts:
        for oid in lesson.get("missed_oids", []):
            obj = get_objective_by_id(load_catalog(db)[drug]["objectives"], oid)
            if obj:
                review_items.append({
                    "oid": obj.oid,
                    "question": obj.question,
                    "remediation": obj.remediation_lesson,
                    "category": obj.category,
                })
    state["review_items"] = review_items

    summary = {
        "drug": load_catalog(db)[drug]["display_name"],
        "category": lesson.get("category"),
        "xp_earned": lesson.get("xp_earned", 0),
        "xp_total": state.get("xp_total", 0),
        "hearts_remaining": lesson.get("hearts", 0),
        "streak_current": state.get("streak_current", 0),
        "streak_longest": state.get("streak_longest", 0),
        "badges_earned": newly_earned,
        "all_badges": state.get("badges", []),
        "questions_answered": lesson.get("index", 0),
        "questions_correct": lesson.get("correct_count", 0),
        "total_questions": lesson.get("total", 0),
        "ran_out_of_hearts": ran_out_of_hearts,
        "review_items": review_items,
    }

    state["current_lesson"] = None
    save_user_state(authenticated_email, state, db)
    return summary


class ReviewCompleteRequest(BaseModel):
    username: str


@app.post("/lesson/review-complete")
def lesson_review_complete(request: ReviewCompleteRequest, db: Session = Depends(get_db), authenticated_email: str = Depends(require_authenticated_user)):
    """Called once the user has read through the remediation for everything
    they missed after running out of hearts. Refills hearts so a new lesson
    attempt is allowed again — this is the only way hearts get refilled."""
    state = get_user_state(authenticated_email, db)
    state["hearts_remaining"] = 5
    state["review_items"] = []
    save_user_state(authenticated_email, state, db)
    return {"hearts": 5}




@app.get("/chat/history")
def chat_history(drug: Optional[str] = None, limit: int = 50, authenticated_email: str = Depends(require_authenticated_user), db: Session = Depends(get_db)):
    return history_rows(authenticated_email, db, drug=drug, limit=limit)


@app.post("/auth/guest")
def start_guest(request: Request):
    # Cap active sessions globally and per address to bound temporary memory.
    now = time.time()
    for key in list(GUEST_SESSIONS):
        if GUEST_SESSIONS[key]["expires"] <= now:
            GUEST_SESSIONS.pop(key, None)
    address = request.client.host if request.client else "unknown"
    if len(GUEST_SESSIONS) >= 1000 or sum(r["address"] == address for r in GUEST_SESSIONS.values()) >= 20:
        raise HTTPException(status_code=429, detail="Too many active guest sessions. Try again later.")
    token = secrets.token_urlsafe(32)
    GUEST_SESSIONS[token] = {"state": blank_user_state(), "expires": now + GUEST_TTL_SECONDS, "address": address}
    return {"token": token, "username": "guest_" + token}


@app.delete("/auth/guest")
def end_guest(x_guest_session: Optional[str] = Header(default=None)):
    if x_guest_session:
        GUEST_SESSIONS.pop(x_guest_session, None)
    return {"ended": True}


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
