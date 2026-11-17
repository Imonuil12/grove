"""Built-in email/password accounts (used while no Cognito pool is configured)."""
import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

import auth
import local_auth
import main
import models
from database import SessionLocal


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("COGNITO_USER_POOL_ID", raising=False)
    return TestClient(main.app)


@pytest.fixture
def email():
    address = f"local.{uuid.uuid4().hex[:10]}@example.com"
    yield address
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email=address).one_or_none()
        db.query(models.LocalCredential).filter_by(email=address).delete()
        if user:
            db.delete(user)
        db.commit()


def test_config_reports_local_provider(client):
    assert client.get("/auth/config").json()["provider"] == "local"


def test_signup_login_and_use_token(client, email):
    r = client.post("/auth/local/signup", json={"email": email.upper(), "password": "correct horse"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == email

    with SessionLocal() as db:
        cred = db.query(models.LocalCredential).filter_by(email=email).one()
        assert "correct horse" not in cred.password_hash

    r = client.post("/auth/local/login", json={"email": email, "password": "correct horse"})
    assert r.status_code == 200
    token = r.json()["id_token"]

    r = client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == email
    assert main.require_authenticated_user(x_guest_session=None, authorization=f"Bearer {token}", x_turnstile_session=None) == email


def test_duplicate_signup_and_bad_password(client, email):
    assert client.post("/auth/local/signup", json={"email": email, "password": "password123"}).status_code == 200
    assert client.post("/auth/local/signup", json={"email": email, "password": "password123"}).status_code == 409
    assert client.post("/auth/local/login", json={"email": email, "password": "wrong-password"}).status_code == 401
    assert client.post("/auth/local/login", json={"email": "nobody@example.com", "password": "x" * 8}).status_code == 401


def test_signup_validation(client):
    assert client.post("/auth/local/signup", json={"email": "not-an-email", "password": "password123"}).status_code == 400
    assert client.post("/auth/local/signup", json={"email": "short@example.com", "password": "short"}).status_code == 400


def test_forged_local_token_rejected(client, email):
    forged = jwt.encode(
        {"iss": local_auth.ISSUER, "email": email, "exp": time.time() + 600},
        "attacker-secret-attacker-secret-attacker",
        algorithm="HS256",
    )
    assert client.get("/auth/verify", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_unsigned_fallback_blocked_in_production(monkeypatch):
    token = jwt.encode({"email": "x@example.com", "exp": time.time() + 600}, "any-secret-any-secret-any-secret-12", algorithm="HS256")
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)
    with pytest.raises(Exception) as err:
        auth.verify_jwt_token(token)
    assert getattr(err.value, "status_code", None) == 401
