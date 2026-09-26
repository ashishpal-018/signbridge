"""FastAPI composition root for SignBridge."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from BACKEND.ai_engine import generate_lesson
from BACKEND.auth import authenticate_user, register_user
from BACKEND.database import get_user_history, init_db, save_user_lesson

app = FastAPI(title="SignBridge")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
SESSION_COOKIE = "signbridge_session"
SESSION_SECRET = os.environ.get("SIGNBRIDGE_SESSION_SECRET", "change-this-secret").encode()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class AuthPayload(BaseModel):
    username: str
    password: str
    role: str | None = None


class LessonPayload(BaseModel):
    topic: str
    mode: str | None = None


@app.on_event("startup")
def startup_event() -> None:
    init_db()


def render_login(request: Request, message: str = "") -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request, "message": message})


def _sign_session(username: str, role: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"username": username, "role": role}, separators=(",", ":")).encode()
    ).decode()
    signature = hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def current_user(request: Request) -> tuple[str, str] | None:
    value = request.cookies.get(SESSION_COOKIE, "")
    try:
        payload, signature = value.rsplit(".", 1)
        expected = hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        user = json.loads(base64.urlsafe_b64decode(payload).decode())
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(user, dict) or not user.get("username") or not user.get("role"):
        return None
    return str(user["username"]), str(user["role"])


def api_user(request: Request) -> tuple[str, str]:
    user = current_user(request)
    if user is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@app.post("/api/register")
def api_register(payload: AuthPayload) -> dict[str, str]:
    success, message = register_user(payload.username, payload.password, payload.role or "")
    if not success:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=message)
    return {"message": message}


@app.post("/api/login")
def api_login(request: Request, payload: AuthPayload) -> Response:
    success, role_or_message = authenticate_user(payload.username, payload.password)
    if not success:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail=role_or_message)
    response = Response(
        content=json.dumps({"username": payload.username.strip(), "role": role_or_message}),
        media_type="application/json",
    )
    response.set_cookie(
        SESSION_COOKIE,
        _sign_session(payload.username.strip(), role_or_message),
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/api/history")
def api_history(request: Request) -> list[dict[str, object]]:
    username, _ = api_user(request)
    return get_user_history(username)


@app.post("/api/generate")
def api_generate(request: Request, payload: LessonPayload) -> dict[str, str]:
    username, role = api_user(request)
    mode = payload.mode or role
    if mode != role:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Learning mode does not match the signed-in user")
    lesson = generate_lesson(payload.topic, mode=mode)
    save_user_lesson(username, payload.topic, lesson)
    return {"lesson": lesson}


@app.get("/", response_class=HTMLResponse)
def read_root(request: Request) -> Response:
    user = current_user(request)
    if user:
        return RedirectResponse(f"/{user[1]}-dashboard", status_code=303)
    return render_login(request)


@app.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
) -> HTMLResponse:
    _, message = register_user(username, password, role)
    return render_login(request, message)


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    success, role_or_message = authenticate_user(username, password)
    if not success:
        return render_login(request, role_or_message)
    response = RedirectResponse(f"/{role_or_message}-dashboard", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        _sign_session(username.strip(), role_or_message),
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


def dashboard_context(request: Request, role: str) -> dict[str, object] | None:
    user = current_user(request)
    if not user or user[1] != role:
        return None
    username = user[0]
    return {
        "request": request,
        "username": username,
        "lesson": "",
        "topic": "",
        "history": get_user_history(username),
    }


@app.get("/blind-dashboard", response_class=HTMLResponse)
def blind_dashboard(request: Request) -> Response:
    context = dashboard_context(request, "blind")
    if context is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("blind_portal.html", context)


@app.post("/blind-dashboard", response_class=HTMLResponse)
def post_blind_lesson(request: Request, topic: str = Form(...)) -> Response:
    context = dashboard_context(request, "blind")
    if context is None:
        return RedirectResponse("/", status_code=303)
    lesson = generate_lesson(topic, mode="blind")
    username = str(context["username"])
    save_user_lesson(username, topic, lesson)
    context.update(lesson=lesson, topic=topic, history=get_user_history(username))
    return templates.TemplateResponse("blind_portal.html", context)


@app.get("/deaf-dashboard", response_class=HTMLResponse)
def deaf_dashboard(request: Request) -> Response:
    context = dashboard_context(request, "deaf")
    if context is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("deaf_portal.html", context)


@app.post("/deaf-dashboard", response_class=HTMLResponse)
def post_deaf_lesson(request: Request, topic: str = Form(...)) -> Response:
    context = dashboard_context(request, "deaf")
    if context is None:
        return RedirectResponse("/", status_code=303)
    lesson = generate_lesson(topic, mode="deaf")
    username = str(context["username"])
    save_user_lesson(username, topic, lesson)
    context.update(lesson=lesson, topic=topic, history=get_user_history(username))
    return templates.TemplateResponse("deaf_portal.html", context)
