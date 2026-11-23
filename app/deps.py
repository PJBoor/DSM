from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .errors import AppError
from .i18n import normalize_locale
from .models import User
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

ROLES = ("admin", "strategist", "contributor", "reader")


def get_locale(request: Request) -> str:
    return normalize_locale(request.headers.get("accept-language"))


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_token(token)
    except Exception:
        raise AppError("error.invalid_token", status_code=401)
    if payload.get("type") != "access":
        raise AppError("error.invalid_token", status_code=401)
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AppError("error.invalid_token", status_code=401)
    return user


def require_role(*roles: str) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role != "admin" and user.role not in roles:
            raise AppError("error.forbidden", status_code=403)
        return user

    return dependency


AnyAuth = Depends(get_current_user)
WriteAccess = Depends(require_role("strategist", "contributor"))
StrategyAccess = Depends(require_role("strategist"))
