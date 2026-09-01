"""Authentication & authorization utilities"""
from datetime import datetime, timezone, timedelta
from typing import Optional
import jwt
from jwt import InvalidTokenError as JWTError
import bcrypt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import re
import logging
import hmac
import secrets

logger = logging.getLogger("quickid.auth")

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    environment = os.environ.get("APP_ENV", os.environ.get("ENVIRONMENT", "development")).lower()
    if environment in {"production", "prod", "staging"}:
        raise RuntimeError("JWT_SECRET production/staging ortamında zorunludur")
    JWT_SECRET = secrets.token_urlsafe(48)
    logger.warning("JWT_SECRET ayarlanmadı; yalnız bu süreç için geçici development anahtarı üretildi")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "24"))

# ===== Password Policy =====
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
ACCOUNT_LOCKOUT_THRESHOLD = 5      # Başarısız deneme sayısı
ACCOUNT_LOCKOUT_DURATION_MINUTES = 15  # Kilitleme süresi (dakika)
ACCOUNT_LOCKOUT_WINDOW_MINUTES = 15    # Deneme penceresi (dakika)

security = HTTPBearer(auto_error=False)


def validate_password_strength(password: str) -> dict:
    """Şifre güçlülük kontrolü - kurallar ve puan döndürür"""
    errors = []
    score = 0

    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Şifre en az {PASSWORD_MIN_LENGTH} karakter olmalı")
    else:
        score += 1

    if len(password) > PASSWORD_MAX_LENGTH:
        errors.append(f"Şifre en fazla {PASSWORD_MAX_LENGTH} karakter olabilir")

    if not re.search(r'[A-Z]', password):
        errors.append("En az 1 büyük harf gerekli (A-Z)")
    else:
        score += 1

    if not re.search(r'[a-z]', password):
        errors.append("En az 1 küçük harf gerekli (a-z)")
    else:
        score += 1

    if not re.search(r'[0-9]', password):
        errors.append("En az 1 rakam gerekli (0-9)")
    else:
        score += 1

    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/~`]', password):
        errors.append("En az 1 özel karakter gerekli (!@#$%^&*...)")
    else:
        score += 1

    # Bonus: length
    if len(password) >= 12:
        score += 1
    if len(password) >= 16:
        score += 1

    # Strength label
    if score <= 2:
        strength = "weak"
        strength_label = "Zayıf"
    elif score <= 4:
        strength = "medium"
        strength_label = "Orta"
    elif score <= 5:
        strength = "strong"
        strength_label = "Güçlü"
    else:
        strength = "very_strong"
        strength_label = "Çok Güçlü"

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "score": score,
        "max_score": 7,
        "strength": strength,
        "strength_label": strength_label,
    }


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=JWT_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency: extract current user from JWT token. Returns None if no token."""
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    return payload


async def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency: require valid auth token"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Giriş yapmanız gerekiyor")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş token")
    return payload


async def require_user_or_service(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_service_key: Optional[str] = Header(default=None, alias="X-Service-Key"),
    x_acting_user: Optional[str] = Header(default=None, alias="X-Acting-User"),
):
    """Accept a normal user JWT or the PMS service-to-service credential.

    The shared service key is deliberately opt-in: if QUICKID_SERVICE_KEY is not
    configured, service authentication is disabled instead of accepting an
    empty/default value.
    """
    if credentials:
        payload = decode_token(credentials.credentials)
        if payload:
            return payload
        raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş token")

    configured_key = os.environ.get("QUICKID_SERVICE_KEY", "").strip()
    supplied_key = (x_service_key or "").strip()
    if configured_key and supplied_key and hmac.compare_digest(configured_key, supplied_key):
        return {
            "email": (x_acting_user or "pms-service")[:254],
            "role": "service",
            "auth_type": "service_key",
        }

    raise HTTPException(status_code=401, detail="Geçerli kullanıcı veya servis kimlik bilgisi gerekiyor")


async def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency: require admin role"""
    user = await require_auth(credentials)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için admin yetkisi gerekiyor")
    return user


# ===== Account Lockout Helpers =====
async def check_account_lockout(db, email: str) -> dict:
    """Hesap kilidi kontrolü - kilitliyse bilgi döndürür"""
    lockout_col = db["login_attempts"]
    window_start = datetime.now(timezone.utc) - timedelta(minutes=ACCOUNT_LOCKOUT_WINDOW_MINUTES)

    # Son penceredeki başarısız denemeleri say
    failed_count = await lockout_col.count_documents({
        "email": email,
        "success": False,
        "timestamp": {"$gte": window_start}
    })

    if failed_count >= ACCOUNT_LOCKOUT_THRESHOLD:
        # En son denemeyi bul
        last_attempt = await lockout_col.find_one(
            {"email": email, "success": False},
            sort=[("timestamp", -1)]
        )
        if last_attempt:
            lockout_until = last_attempt["timestamp"] + timedelta(minutes=ACCOUNT_LOCKOUT_DURATION_MINUTES)
            now = datetime.now(timezone.utc)
            if now < lockout_until:
                remaining_seconds = int((lockout_until - now).total_seconds())
                remaining_minutes = remaining_seconds // 60 + 1
                return {
                    "locked": True,
                    "remaining_minutes": remaining_minutes,
                    "remaining_seconds": remaining_seconds,
                    "failed_attempts": failed_count,
                    "message": f"Hesap kilitlendi. {remaining_minutes} dakika sonra tekrar deneyin."
                }

    remaining_attempts = ACCOUNT_LOCKOUT_THRESHOLD - failed_count
    return {
        "locked": False,
        "failed_attempts": failed_count,
        "remaining_attempts": remaining_attempts,
    }


async def record_login_attempt(db, email: str, success: bool, ip_address: str = None):
    """Giriş denemesini kaydet"""
    lockout_col = db["login_attempts"]
    await lockout_col.insert_one({
        "email": email,
        "success": success,
        "ip_address": ip_address,
        "timestamp": datetime.now(timezone.utc),
    })

    # Başarılı girişte eski başarısız denemeleri temizle
    if success:
        await lockout_col.delete_many({
            "email": email,
            "success": False,
        })


async def unlock_account(db, email: str):
    """Admin tarafından hesap kilidini aç"""
    lockout_col = db["login_attempts"]
    result = await lockout_col.delete_many({
        "email": email,
        "success": False,
    })
    return {"cleared_attempts": result.deleted_count}
