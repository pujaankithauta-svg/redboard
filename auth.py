from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os, re

SECRET_KEY = os.environ.get("SECRET_KEY", "redboard-change-this-in-production-min-32-chars")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def validate_password(password: str) -> list:
    """Returns list of validation errors. Empty list = valid."""
    errors = []
    if len(password) < 10:
        errors.append("At least 10 characters required")
    if not re.search(r'[A-Z]', password):
        errors.append("At least one uppercase letter required")
    if not re.search(r'[a-z]', password):
        errors.append("At least one lowercase letter required")
    if not re.search(r'\d', password):
        errors.append("At least one number required")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("At least one special character required")
    return errors


def validate_phone(phone: str) -> bool:
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)
    return cleaned.isdigit() and 7 <= len(cleaned) <= 15


def validate_email(email: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))