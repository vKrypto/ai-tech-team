"""Login for the dashboard and the API.

- Browser: POST /api/auth/login sets a signed, HttpOnly session cookie (AI_TEAM_SESSION_DAYS long).
- Scripts: HTTP Basic auth with the same username/password.
- /api/health, /api/auth/* and the static page itself stay public (health checks, the login screen).
Credentials come from AI_TEAM_UI_USERNAME / AI_TEAM_UI_PASSWORD. The signing secret is
AI_TEAM_SESSION_SECRET, or generated once and stored in Mongo so sessions survive restarts.
"""
import base64
import hashlib
import hmac
import secrets
import threading
import time

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..persistence.store import db
from ..settings import settings

COOKIE = "ait_session"
PUBLIC = ("/api/health", "/api/auth/")
router = APIRouter(prefix="/api/auth", tags=["auth"])
_secret: bytes | None = None
_fails: dict[str, list[float]] = {}
_lock = threading.Lock()


def secret() -> bytes:
    global _secret
    if _secret is None:
        if settings.session_secret:
            _secret = settings.session_secret.encode()
        else:
            doc = db()["settings"].find_one_and_update(
                {"_id": "session_secret"}, {"$setOnInsert": {"value": secrets.token_hex(32)}},
                upsert=True, return_document=True)
            _secret = doc["value"].encode()
    return _secret


def _sign(payload: str) -> str:
    return hmac.new(secret(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(user: str) -> str:
    payload = f"{user}|{int(time.time()) + settings.session_days * 86400}"
    return base64.urlsafe_b64encode(payload.encode()).decode() + "." + _sign(payload)


def read_token(token: str | None) -> str | None:
    try:
        raw, sig = (token or "").split(".", 1)
        payload = base64.urlsafe_b64decode(raw.encode()).decode()
        user, exp = payload.rsplit("|", 1)
    except Exception:
        return None
    if not hmac.compare_digest(sig, _sign(payload)) or int(exp) < time.time():
        return None
    return user if user == settings.ui_username else None


def check_password(user: str, password: str) -> bool:
    ok_user = hmac.compare_digest(user.encode(), settings.ui_username.encode())
    ok_pass = hmac.compare_digest(password.encode(), settings.ui_password.encode())
    return ok_user and ok_pass


def _basic(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    if not h.lower().startswith("basic "):
        return None
    try:
        user, _, pw = base64.b64decode(h[6:]).decode().partition(":")
    except Exception:
        return None
    return user if check_password(user, pw) else None


def current_user(request: Request) -> str | None:
    return read_token(request.cookies.get(COOKIE)) or _basic(request)


async def middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not path.startswith(PUBLIC) and current_user(request) is None:
        return JSONResponse({"detail": "login required"}, status_code=401)
    return await call_next(request)


def _throttle(ip: str) -> None:
    """At most 5 failed logins per minute per client."""
    now = time.time()
    with _lock:
        recent = [t for t in _fails.get(ip, []) if now - t < 60]
        _fails[ip] = recent
        if len(recent) >= 5:
            raise HTTPException(429, "too many failed logins; wait a minute")


class Login(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: Login, request: Request, response: Response):
    ip = request.client.host if request.client else "?"
    _throttle(ip)
    if not check_password(body.username, body.password):
        with _lock:
            _fails.setdefault(ip, []).append(time.time())
        raise HTTPException(401, "wrong username or password")
    response.set_cookie(COOKIE, make_token(body.username), max_age=settings.session_days * 86400,
                        httponly=True, samesite="lax", secure=request.url.scheme == "https", path="/")
    return {"user": body.username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "login required")
    return {"user": user}
