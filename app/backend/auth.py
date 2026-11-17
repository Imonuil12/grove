import os
import time
import base64
import json
import requests
import jwt
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import env_config  # noqa: F401
import local_auth

IS_PRODUCTION = os.getenv("APP_ENV", "development").lower() == "production"


REGION = os.getenv("COGNITO_REGION", "us-east-2")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "")

JWKS_URL = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"

# In-memory cache for Cognito JWKS public keys
_JWKS_CACHE: Dict[str, Any] = {}
_JWKS_CACHE_EXPIRY: float = 0

security = HTTPBearer(auto_error=False)

class AuthUser(BaseModel):
    username: str
    email: Optional[str] = None
    sub: Optional[str] = None
    is_authenticated: bool = False
    claims: Dict[str, Any] = {}

def get_cognito_jwks() -> Dict[str, Any]:
    global _JWKS_CACHE, _JWKS_CACHE_EXPIRY
    current_time = time.time()
    if _JWKS_CACHE and current_time < _JWKS_CACHE_EXPIRY:
        return _JWKS_CACHE
    try:
        resp = requests.get(JWKS_URL, timeout=3)
        if resp.status_code == 200:
            _JWKS_CACHE = resp.json()
            _JWKS_CACHE_EXPIRY = current_time + 3600  # Cache for 1 hour
            return _JWKS_CACHE
    except Exception as e:
        print(f"[Cognito Auth] Note: Unable to reach Cognito JWKS ({e}). Dev mode active.")
    return _JWKS_CACHE or {"keys": []}

def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Decodes and verifies a JWT token issued by AWS Cognito or local test issuer.
    Verifies expiration, issuer, and signature where possible.
    Safely normalizes base64 padding to handle varied client encodings and mock tokens.
    """
    token = token.strip()
    if local_auth.is_local_token(token):
        return local_auth.verify_token(token)
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed JWT token structure.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Normalize segment padding for base64url decoding
    padded_header = parts[0] + "=" * ((4 - len(parts[0]) % 4) % 4)
    padded_payload = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)

    unverified_header = {}
    try:
        unverified_header = json.loads(base64.urlsafe_b64decode(padded_header.encode()))
    except Exception:
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid JWT header format: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    jwks = get_cognito_jwks()
    kid = unverified_header.get("kid")
    key = None
    if kid:
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                key = jwt.algorithms.RSAAlgorithm.from_jwk(k)
                break

    # If public key found in live Cognito JWKS, perform full cryptographic verification
    if key:
        try:
            payload = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                issuer=ISSUER,
                options={
                    "verify_exp": True,
                    "verify_iss": True,
                    "verify_aud": False  # Validated explicitly below
                }
            )
            # Validate audience or client_id if present
            token_aud = payload.get("aud") or payload.get("client_id")
            if token_aud and token_aud != CLIENT_ID:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token client_id mismatch.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"JWT verification failed: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Fallback for development/tester tokens or when offline. Never in production:
    # it trusts the token's claims without checking a signature.
    if IS_PRODUCTION:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unrecognized token signing key.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload_data = json.loads(base64.urlsafe_b64decode(padded_payload.encode()))
        exp = payload_data.get("exp")
        if exp and exp < time.time():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed JWT token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user_optional(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthUser:
    """
    Optional authentication dependency:
    - If valid Bearer token provided, validates claims and returns AuthUser.
    - If no token provided or token invalid/expired, gracefully falls back to guest AuthUser
      without raising 401 exceptions that lock users out of basic application features.
    """
    if not auth_header or not auth_header.credentials:
        return AuthUser(username="guest", is_authenticated=False)

    token = auth_header.credentials
    try:
        claims = verify_jwt_token(token)
    except HTTPException:
        return AuthUser(username="guest", is_authenticated=False)
    
    # Extract identity: cognito:username, email, or username
    user_identifier = (
        claims.get("email") or
        claims.get("cognito:username") or
        claims.get("username") or
        claims.get("sub") or
        "authenticated_user"
    )
    
    return AuthUser(
        username=user_identifier,
        email=claims.get("email"),
        sub=claims.get("sub"),
        is_authenticated=True,
        claims=claims
    )

def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthUser:
    """
    Strict authentication dependency:
    Requires a valid Bearer token, raising 401 Unauthorized if missing or invalid.
    """
    if not auth_header or not auth_header.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Strictly verify token; throws 401 if invalid or expired
    claims = verify_jwt_token(auth_header.credentials)
    user_identifier = (
        claims.get("email") or
        claims.get("cognito:username") or
        claims.get("username") or
        claims.get("sub") or
        "authenticated_user"
    )
    return AuthUser(
        username=user_identifier,
        email=claims.get("email"),
        sub=claims.get("sub"),
        is_authenticated=True,
        claims=claims
    )
