import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal, get_db


TOKEN_EXPIRE_HOURS = int(os.getenv("AUTH_TOKEN_EXPIRE_HOURS", "8"))
TOKEN_SECRET = os.getenv("AUTH_TOKEN_SECRET", "change-me-in-production")
INITIAL_ADMIN_USERNAME = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
INITIAL_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")
INITIAL_ADMIN_NOME = os.getenv("INITIAL_ADMIN_NOME", "Administrador")

ROLE_ADMIN = "admin"
ROLE_OPERADOR = "operador"

security = HTTPBearer(auto_error=False)


def _is_production_env() -> bool:
    return os.getenv("APP_ENV", "development").strip().lower() in {"production", "prod"}


def validate_auth_settings() -> None:
    """
    Falha rápido quando configuração insegura é usada em produção.
    """
    if not _is_production_env():
        return

    errors = []
    weak_secrets = {"", "change-me-in-production", "seara-fm-warning", "changeme", "secret"}
    weak_admin_passwords = {"", "admin123", "warning", "admin", "123456", "password"}

    if TOKEN_SECRET in weak_secrets or len(TOKEN_SECRET) < 32:
        errors.append("AUTH_TOKEN_SECRET deve ter pelo menos 32 caracteres e não pode ser padrão.")

    if INITIAL_ADMIN_PASSWORD in weak_admin_passwords or len(INITIAL_ADMIN_PASSWORD) < 10:
        errors.append(
            "INITIAL_ADMIN_PASSWORD está fraco/padrão. Use uma senha forte com 10+ caracteres."
        )

    if errors:
        raise RuntimeError("Configuração de autenticação insegura para produção: " + " ".join(errors))


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 390000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64url_encode(salt)}${_b64url_encode(dk)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, iterations_raw, salt_b64, hash_b64 = password_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(hash_b64)
    except Exception:
        return False

    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(dk, expected)


def create_access_token(usuario: models.Usuario) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id),
        "username": usuario.username,
        "role": usuario.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=TOKEN_EXPIRE_HOURS)).timestamp()),
    }

    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_json)
    sig = hmac.new(TOKEN_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> dict:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    expected_sig = hmac.new(
        TOKEN_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
    ).digest()
    signature = _b64url_decode(sig_b64)
    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    exp = payload.get("exp")
    if not exp or int(exp) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")

    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> models.Usuario:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação obrigatória")

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Esquema de autenticação inválido")

    payload = decode_access_token(credentials.credentials)
    user_id = int(payload.get("sub", 0))

    user = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
    if not user or not user.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido")

    return user


def require_roles(*roles: str) -> Callable:
    def dependency(user: models.Usuario = Depends(get_current_user)) -> models.Usuario:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissão")
        return user

    return dependency


def ensure_initial_admin() -> None:
    db = SessionLocal()
    try:
        admin_exists = db.query(models.Usuario).filter(models.Usuario.role == ROLE_ADMIN).first()
        if admin_exists:
            return

        username_exists = db.query(models.Usuario).filter(
            models.Usuario.username == INITIAL_ADMIN_USERNAME
        ).first()
        if username_exists:
            return

        admin = models.Usuario(
            username=INITIAL_ADMIN_USERNAME,
            nome=INITIAL_ADMIN_NOME,
            password_hash=hash_password(INITIAL_ADMIN_PASSWORD),
            role=ROLE_ADMIN,
            ativo=True,
        )
        db.add(admin)
        db.commit()
        print(f"🔐 Usuário admin inicial criado: {INITIAL_ADMIN_USERNAME}")
    finally:
        db.close()
