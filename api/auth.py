"""JurisMon Admin Authentication & Security."""

import os
import logging
import secrets
import datetime
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt

logger = logging.getLogger("jurismon.auth")

ALGORITHM = "HS256"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@jurismon.com")

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}

security = HTTPBearer()

# bcrypt silently ignores anything past 72 bytes, so a longer password would
# authenticate on its first 72 bytes alone. Reject it instead of truncating.
BCRYPT_MAX_BYTES = 72


def _load_secret_key() -> str:
    """Resolves the JWT signing key.

    In production a SECRET_KEY must be supplied by the environment; there is no
    fallback, since a predictable key allows anyone to forge admin tokens. In
    development an ephemeral key is generated so the app still boots, at the
    cost of invalidating tokens on restart.
    """
    key = os.getenv("SECRET_KEY", "").strip()
    if key:
        return key

    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY is not set. It is required when APP_ENV=production."
        )

    logger.warning(
        "SECRET_KEY is not set. Generated an ephemeral development key - "
        "issued tokens will not survive a restart. Set SECRET_KEY before deploying."
    )
    return secrets.token_urlsafe(48)


def _load_admin_password_hash() -> str:
    """Resolves the bcrypt hash the admin login is checked against."""
    password_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    if password_hash:
        return password_hash

    if IS_PRODUCTION:
        raise RuntimeError(
            "ADMIN_PASSWORD_HASH is not set. It is required when APP_ENV=production. "
            "Generate one with: python scripts/generate_admin_hash.py"
        )

    logger.warning(
        "ADMIN_PASSWORD_HASH is not set - admin login is disabled. "
        "Generate one with: python scripts/generate_admin_hash.py"
    )
    return ""


SECRET_KEY = _load_secret_key()
ADMIN_PASSWORD_HASH = _load_admin_password_hash()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        secret = plain_password.encode("utf-8")
        if len(secret) > BCRYPT_MAX_BYTES:
            return False
        return bcrypt.checkpw(secret, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # A malformed or truncated hash must read as a failed login, not a 500.
        logger.error("Stored admin password hash could not be parsed.")
        return False


def get_password_hash(password: str) -> str:
    secret = password.encode("utf-8")
    if len(secret) > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"Password must be {BCRYPT_MAX_BYTES} bytes or fewer (bcrypt limit)."
        )
    return bcrypt.hashpw(secret, bcrypt.gensalt()).decode("utf-8")


def authenticate_admin(email: str, password: str) -> bool:
    """Validates admin credentials against the configured bcrypt hash."""
    if not ADMIN_PASSWORD_HASH:
        logger.error("Admin login attempted but ADMIN_PASSWORD_HASH is not configured.")
        return False

    email_ok = secrets.compare_digest(
        (email or "").strip().lower(), ADMIN_EMAIL.strip().lower()
    )
    password_ok = verify_password(password or "", ADMIN_PASSWORD_HASH)

    # Both checks always run so the response time does not reveal which failed.
    return email_ok and password_ok


def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + (
        expires_delta or datetime.timedelta(days=7)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email != ADMIN_EMAIL:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized admin access"
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
