import sys
import os
from datetime import date
from typing import Any, Dict, List, Optional

# Add BACKEND folder to Python path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../BACKEND'))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from fastapi import FastAPI, Form, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import (
    init_db,
    save_user_lesson, get_user_history,
    get_user_streak, update_user_streak,
    get_user_stats, record_quiz_result,
    get_or_create_profile, update_profile_role
)
from sign_detector import SIGN_CATALOG, analyze_landmarks
from ai_engine import generate_lesson, generate_quiz

app = FastAPI(title="SignBridge API & Web App", version="1.0.0")

# Enable CORS for the React frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

# --- Pydantic Data Models for /api Endpoints ---
class ProfilePayload(BaseModel):
    username: str = "Guest Learner"
    role: str = "deaf"

class GeneratePayload(BaseModel):
    topic: str
    mode: str = "blind"
    username: Optional[str] = None

class QuizPayload(BaseModel):
    topic: str
    lesson: Optional[str] = None
    username: Optional[str] = None
    mode: Optional[str] = "blind"

class QuizResultPayload(BaseModel):
    username: str
    topic: str
    score: int
    total_questions: int = 3
    correct_answers: int = 0

class SignLessonPayload(BaseModel):
    username: Optional[str] = "Guest Learner"
    landmarks: List[Dict[str, float]]

class AirWritingLessonPayload(BaseModel):
    username: Optional[str] = "Guest Learner"
    topic: str

# --- MODERN WEB LAYOUT ---
def layout(title: str, content: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
        </style>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4 md:p-8 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.15),rgba(255,255,255,0))]">
        <div class="w-full max-w-2xl bg-slate-900/90 backdrop-blur-2xl p-8 rounded-3xl border border-slate-800 shadow-2xl shadow-indigo-950/40">
            {content}
        </div>
    </body>
    </html>
    """

# --- WEB PORTAL: AUTHENTICATION ---
@app.get("/", response_class=HTMLResponse)
def read_root(message: str = ""):
    msg_box = f'<div class="bg-indigo-950/60 border border-indigo-500/40 text-indigo-300 p-3.5 rounded-xl mb-6 text-sm text-center font-medium shadow-inner">{message}</div>' if message else ""

    html = f"""
        <div class="text-center mb-8">
            <div class="inline-block p-3 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-2xl shadow-lg shadow-blue-500/30 mb-3 text-2xl font-black text-white">✨</div>
            <h1 class="text-3xl font-extrabold tracking-tight text-white">Sign<span class="text-blue-400">Bridge</span></h1>
            <p class="text-slate-400 text-sm mt-1">Accessible AI learning for blind, deaf, and non-speaking users</p>
        </div>
        {msg_box}
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <a href="/blind-dashboard?username=Guest%20Learner" class="block p-5 rounded-2xl border border-blue-500/30 bg-blue-500/10 hover:bg-blue-500/20 transition">
                <div class="text-3xl mb-2">🎧</div>
                <div class="text-sm font-bold uppercase tracking-wider text-blue-300">Blind Mode</div>
                <p class="text-xs text-slate-300 mt-2">Audio-first lessons with speech controls and guided mentoring cues.</p>
            </a>
            <a href="/deaf-dashboard?username=Guest%20Learner" class="block p-5 rounded-2xl border border-purple-500/30 bg-purple-500/10 hover:bg-purple-500/20 transition">
                <div class="text-3xl mb-2">🧠</div>
                <div class="text-sm font-bold uppercase tracking-wider text-purple-300">Deaf Mode</div>
                <p class="text-xs text-slate-300 mt-2">Visual text modules and structured reading experiences for clear comprehension.</p>
            </a>
            <a href="/sign-dashboard?username=Guest%20Learner" class="block p-5 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 transition">
                <div class="text-3xl mb-2">🤟</div>
                <div class="text-sm font-bold uppercase tracking-wider text-emerald-300">Sign Mode</div>
                <p class="text-xs text-slate-300 mt-2">Gesture-driven topics and dynamic lesson generation for non-speaking learners.</p>
            </a>
        </div>
        <div class="rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
            <h2 class="text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800 pb-2 mb-3">Quick session profile</h2>
            <form action="/mode-select" method="POST" class="space-y-4">
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">Display name</label>
                    <input type="text" name="username" value="Guest Learner" class="w-full p-3.5 bg-slate-950/60 rounded-xl border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition">
                </div>
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">Choose learning pathway</label>
                    <select name="mode" class="w-full p-3.5 bg-slate-950/60 rounded-xl border border-slate-800 text-white focus:outline-none focus:border-emerald-500 transition">
                        <option value="deaf">Deaf learner</option>
                        <option value="blind">Blind learner</option>
                        <option value="sign">Sign / non-speaking learner</option>
                    </select>
                </div>
                <button type="submit" class="w-full bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 p-3.5 rounded-xl font-bold transition shadow-lg shadow-indigo-600/30 cursor-pointer">Open selected portal</button>
            </form>
        </div>
    """
    return layout("SignBridge - Mode Selection", html)

@app.post("/mode-select")
def mode_select(username: str = Form("Guest Learner"), mode: str = Form("deaf")):
    clean_username = (username or "Guest Learner").strip() or "Guest Learner"
    selected_mode = mode if mode in {"blind", "deaf", "sign"} else "deaf"
    get_or_create_profile(clean_username, selected_mode)
    update_profile_role(clean_username, selected_mode)
    if selected_mode == "blind":
        return RedirectResponse(url=f"/blind-dashboard?username={clean_username}", status_code=303)
    if selected_mode == "sign":
        return RedirectResponse(url=f"/sign-dashboard?username={clean_username}", status_code=303)
    return RedirectResponse(url=f"/deaf-dashboard?username={clean_username}", status_code=303)

# --- BLIND LEARNER PORTAL ---
@app.get("/blind-dashboard", response_class=HTMLResponse)
def blind_dashboard(username: str = "Guest Learner", lesson: str = "", topic: str = "", quiz: str = ""):
    profile = get_or_create_profile(username, "blind")
    history = get_user_history(profile["username"])
    streak = get_user_streak(profile["username"])
    username = profile["username"]

    history_items = []
    for h in history:
        item_topic = h.get("topic") if isinstance(h, dict) else h[0]
        item_time = h.get("timestamp", h.get("created_at", "")) if isinstance(h, dict) else h[2]
        history_items.append(
            f'<li class="bg-slate-950/50 p-3.5 rounded-xl border border-slate-800/80 text-sm flex justify-between items-center text-slate-300">'
            f'<span>📚 <strong class="text-white">{item_topic}</strong></span>'
            f'<span class="text-xs text-slate-500">{item_time}</span>'
            f'</li>'
        )
    history_html = "".join(history_items) if history_items else '<li class="text-slate-500 text-xs italic py-2">No lessons recorded yet. Start learning above!</li>'

    lesson_section = ""
    if lesson:
        if quiz:
            quiz_section = f"""
            <div class="mt-6 p-5 bg-indigo-950/40 rounded-xl border border-indigo-900/50">
                <h3 class="font-bold text-indigo-300 text-sm uppercase tracking-wider mb-2">🧠 Knowledge Check Quiz</h3>
                <div class="text-indigo-100 text-sm leading-relaxed whitespace-pre-line font-light">{quiz}</div>
            </div>
            """
        else:
            quiz_section = f"""
            <form action="/blind-quiz" method="POST" class="mt-6">
                <input type="hidden" name="username" value="{username}">
                <input type="hidden" name="topic" value="{topic}">
                <input type="hidden" name="lesson" value="{lesson}">
                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-500 p-3 rounded-xl font-bold text-xs uppercase tracking-wider transition shadow-md cursor-pointer">🧠 Generate & Take Quiz</button>
            </form>
            """

        lesson_section = f"""
        <section class="mt-8 p-6 bg-slate-950/70 rounded-2xl border border-slate-800 shadow-xl">
            <div class="flex justify-between items-center mb-4 pb-3 border-b border-slate-800">
                <h2 class="text-base font-bold text-emerald-400">Lesson: {topic}</h2>
                <div class="flex gap-2">
                    <button onclick="speakText()" class="bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded-xl text-xs font-bold transition shadow-md cursor-pointer flex items-center gap-1.5">🔊 Read Aloud</button>
                    <button onclick="window.speechSynthesis.cancel()" class="bg-rose-500/10 hover:bg-rose-500 text-rose-300 hover:text-white border border-rose-500/20 px-3 py-2 rounded-xl text-xs font-bold transition cursor-pointer">⏹ Stop</button>
                </div>
            </div>
            <div id="lesson-text" class="text-slate-200 text-base leading-relaxed whitespace-pre-line font-light">{lesson}</div>
            {quiz_section}
        </section>
        <script>
            function speakText() {{
                const el = document.getElementById("lesson-text");
                if (!el) return;
                const text = el.innerText;
                window.speechSynthesis.cancel();
                let utterance = new SpeechSynthesisUtterance(text);
                window.speechSynthesis.speak(utterance);
            }}
        </script>
        """

    html = f"""
        <nav class="flex justify-between items-center mb-8 pb-4 border-b border-slate-800">
            <div><span class="text-lg font-black text-white">Sign<span class="text-blue-400">Bridge</span></span> <span class="ml-2 text-[10px] tracking-wider bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2.5 py-1 rounded-full uppercase font-bold">Blind Mode</span></div>
            <div class="flex items-center gap-3">
                <span class="text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-3 py-1 rounded-full font-bold">🔥 {streak} Day Streak</span>
                <span class="text-sm text-slate-300"><b>{username}</b></span>
                <a href="/" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded-lg transition font-medium border border-slate-700">Log Out</a>
            </div>
        </nav>
        <h1 class="text-2xl font-extrabold text-blue-400 mb-2">Audio Learning Assistant</h1>
        <p class="text-slate-400 text-sm mb-6">Enter any subject to generate a clean, audio-optimized lesson and test your knowledge.</p>
        <form action="/blind-dashboard" method="POST" class="space-y-4">
            <input type="hidden" name="username" value="{username}">
            <input type="text" name="topic" required placeholder="e.g., Photosynthesis, Gravity..." class="w-full p-4 bg-slate-950/60 rounded-xl border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition">
            <button type="submit" class="w-full bg-blue-600 hover:bg-blue-500 p-4 rounded-xl font-bold transition shadow-lg shadow-blue-600/20 cursor-pointer">Generate Audio Lesson</button>
        </form>
        {lesson_section}
        <section class="mt-8 pt-6 border-t border-slate-800">
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Recent Lessons History</h3>
            <ul class="space-y-2.5">{history_html}</ul>
        </section>
    """
    return layout("SignBridge - Blind Portal", html)

@app.post("/blind-dashboard", response_class=HTMLResponse)
def post_blind_lesson(username: str = Form(...), topic: str = Form(...)):
    lesson_text = generate_lesson(topic, mode="blind")
    save_user_lesson(username, topic, lesson_text, mode="blind")
    update_user_streak(username)
    return blind_dashboard(username=username, lesson=lesson_text, topic=topic)

@app.post("/blind-quiz", response_class=HTMLResponse)
def post_blind_quiz(username: str = Form(...), topic: str = Form(...), lesson: str = Form(...)):
    quiz_text = generate_quiz(topic, lesson)
    return blind_dashboard(username=username, lesson=lesson, topic=topic, quiz=quiz_text)

# --- DEAF LEARNER PORTAL ---
@app.get("/deaf-dashboard", response_class=HTMLResponse)
def deaf_dashboard(username: str = "Guest Learner", lesson: str = "", topic: str = "", quiz: str = ""):
    profile = get_or_create_profile(username, "deaf")
    history = get_user_history(profile["username"])
    streak = get_user_streak(profile["username"])
    username = profile["username"]

    history_items = []
    for h in history:
        item_topic = h.get("topic") if isinstance(h, dict) else h[0]
        item_time = h.get("timestamp", h.get("created_at", "")) if isinstance(h, dict) else h[2]
        history_items.append(
            f'<li class="bg-slate-950/50 p-3.5 rounded-xl border border-slate-800/80 text-sm flex justify-between items-center text-slate-300">'
            f'<span>📖 <strong class="text-white">{item_topic}</strong></span>'
            f'<span class="text-xs text-slate-500">{item_time}</span>'
            f'</li>'
        )
    history_html = "".join(history_items) if history_items else '<li class="text-slate-500 text-xs italic py-2">No lessons recorded yet. Start learning above!</li>'

    lesson_section = ""
    if lesson:
        if quiz:
            quiz_section = f"""
            <div class="mt-6 p-5 bg-purple-950/40 rounded-xl border border-purple-900/50">
                <h3 class="font-bold text-purple-300 text-sm uppercase tracking-wider mb-2">🧠 Knowledge Check Quiz</h3>
                <div class="text-purple-100 text-sm leading-relaxed whitespace-pre-line font-light">{quiz}</div>
            </div>
            """
        else:
            quiz_section = f"""
            <form action="/deaf-quiz" method="POST" class="mt-6">
                <input type="hidden" name="username" value="{username}">
                <input type="hidden" name="topic" value="{topic}">
                <input type="hidden" name="lesson" value="{lesson}">
                <button type="submit" class="w-full bg-purple-600 hover:bg-purple-500 p-3 rounded-xl font-bold text-xs uppercase tracking-wider transition shadow-md cursor-pointer">🧠 Generate & Take Quiz</button>
            </form>
            """

        lesson_section = f"""
        <section class="mt-8 p-6 bg-slate-950/70 rounded-2xl border border-slate-800 shadow-xl">
            <h2 class="text-base font-bold text-purple-400 mb-4 pb-3 border-b border-slate-800 flex items-center gap-2">📖 Module: {topic}</h2>
            <div class="text-slate-200 text-base leading-relaxed whitespace-pre-line space-y-3 font-normal">{lesson}</div>
            {quiz_section}
        </section>
        """

    html = f"""
        <nav class="flex justify-between items-center mb-8 pb-4 border-b border-slate-800">
            <div><span class="text-lg font-black text-white">Sign<span class="text-purple-400">Bridge</span></span> <span class="ml-2 text-[10px] tracking-wider bg-purple-500/10 text-purple-400 border border-purple-500/20 px-2.5 py-1 rounded-full uppercase font-bold">Deaf Mode</span></div>
            <div class="flex items-center gap-3">
                <span class="text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-3 py-1 rounded-full font-bold">🔥 {streak} Day Streak</span>
                <span class="text-sm text-slate-300"><b>{username}</b></span>
                <a href="/" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded-lg transition font-medium border border-slate-700">Log Out</a>
            </div>
        </nav>
        <h1 class="text-2xl font-extrabold text-purple-400 mb-2">Visual Learning Assistant</h1>
        <p class="text-slate-400 text-sm mb-6">Enter any subject to generate a structured visual text module and test your knowledge.</p>
        <form action="/deaf-dashboard" method="POST" class="space-y-4">
            <input type="hidden" name="username" value="{username}">
            <input type="text" name="topic" required placeholder="e.g., Quantum Physics, Solar System..." class="w-full p-4 bg-slate-950/60 rounded-xl border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-purple-500 transition">
            <button type="submit" class="w-full bg-purple-600 hover:bg-purple-500 p-4 rounded-xl font-bold transition shadow-lg shadow-purple-600/20 cursor-pointer">Generate Visual Module</button>
        </form>
        {lesson_section}
        <section class="mt-8 pt-6 border-t border-slate-800">
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Recent Lessons History</h3>
            <ul class="space-y-2.5">{history_html}</ul>
        </section>
    """
    return layout("SignBridge - Deaf Portal", html)

@app.post("/deaf-dashboard", response_class=HTMLResponse)
def post_deaf_lesson(username: str = Form(...), topic: str = Form(...)):
    lesson_text = generate_lesson(topic, mode="deaf")
    save_user_lesson(username, topic, lesson_text, mode="deaf")
    update_user_streak(username)
    return deaf_dashboard(username=username, lesson=lesson_text, topic=topic)

@app.post("/deaf-quiz", response_class=HTMLResponse)
def post_deaf_quiz(username: str = Form(...), topic: str = Form(...), lesson: str = Form(...)):
    quiz_text = generate_quiz(topic, lesson)
    return deaf_dashboard(username=username, lesson=lesson, topic=topic, quiz=quiz_text)

# --- SIGN / NON-SPEAKING LEARNER PORTAL ---
@app.get("/sign-dashboard", response_class=HTMLResponse)
def sign_dashboard(username: str = "Guest Learner", lesson: str = "", topic: str = "", sign: str = "LEARN"):
    profile = get_or_create_profile(username, "sign")
    history = get_user_history(profile["username"])
    streak = get_user_streak(profile["username"])
    username = profile["username"]

    sign_details = SIGN_CATALOG.get(sign.upper(), SIGN_CATALOG["LEARN"])
    summary = lesson or ""
    if not summary:
        summary = f"Detected gesture: {sign_details['gesture']} — {sign_details['name']}\n\nSuggested topic: {sign_details['recommended_topic']}"

    option_items = []
    for key, value in SIGN_CATALOG.items():
        selected = " selected" if key == sign.upper() else ""
        option_items.append(f'<option value="{key}"{selected}>{value["symbol"]} {value["name"]}</option>')
    option_html = "".join(option_items)

    history_items = []
    for item in history:
        if isinstance(item, dict):
            entry_topic = item.get("topic", "Recent topic")
            entry_time = item.get("timestamp", item.get("created_at", ""))
        else:
            entry_topic = item[0] if len(item) > 0 else "Recent topic"
            entry_time = item[2] if len(item) > 2 else ""
        history_items.append(
            f'<li class="bg-slate-950/50 p-3.5 rounded-xl border border-slate-800/80 text-sm flex justify-between items-center text-slate-300">'
            f'<span>🤟 <strong class="text-white">{entry_topic}</strong></span>'
            f'<span class="text-xs text-slate-500">{entry_time}</span></li>'
        )
    history_html = "".join(history_items) if history_items else '<li class="text-slate-500 text-xs italic py-2">No lessons recorded yet. Start learning above!</li>'

    summary_html = f'''
    <section class="mt-8 p-6 bg-slate-950/70 rounded-2xl border border-slate-800 shadow-xl">
        <h2 class="text-base font-bold text-emerald-400 mb-4">Detected Sign: {sign_details['name']}</h2>
        <div class="text-slate-200 text-base leading-relaxed whitespace-pre-line font-light">{summary}</div>
    </section>
    ''' if summary else ""

    html = f"""
        <nav class="flex justify-between items-center mb-8 pb-4 border-b border-slate-800">
            <div><span class="text-lg font-black text-white">Sign<span class="text-emerald-400">Bridge</span></span> <span class="ml-2 text-[10px] tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2.5 py-1 rounded-full uppercase font-bold">Sign Mode</span></div>
            <div class="flex items-center gap-3">
                <span class="text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-3 py-1 rounded-full font-bold">🔥 {streak} Day Streak</span>
                <span class="text-sm text-slate-300"><b>{username}</b></span>
                <a href="/" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded-lg transition font-medium border border-slate-700">Back to mode selection</a>
            </div>
        </nav>
        <h1 class="text-2xl font-extrabold text-emerald-400 mb-2">Gesture-to-Lesson Studio</h1>
        <p class="text-slate-400 text-sm mb-6">Choose or detect a sign gesture to generate a tailored lesson topic for non-speaking learners.</p>
        <form action="/sign-dashboard" method="POST" class="space-y-4">
            <input type="hidden" name="username" value="{username}">
            <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">Detected or chosen sign</label>
            <select name="sign" class="w-full p-3.5 bg-slate-950/60 rounded-xl border border-slate-800 text-white focus:outline-none focus:border-emerald-500 transition">
                {option_html}
            </select>
            <button type="submit" class="w-full bg-emerald-600 hover:bg-emerald-500 p-4 rounded-xl font-bold transition shadow-lg shadow-emerald-600/20 cursor-pointer">Generate sign-based lesson</button>
        </form>
        {summary_html}
        <section class="mt-8 pt-6 border-t border-slate-800">
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Recent Lessons History</h3>
            <ul class="space-y-2.5">{history_html}</ul>
        </section>
    """
    return layout("SignBridge - Sign Portal", html)

@app.post("/sign-dashboard", response_class=HTMLResponse)
def post_sign_dashboard(username: str = Form(...), sign: str = Form("LEARN")):
    profile = get_or_create_profile(username, "sign")
    username = profile["username"]
    sign_key = sign.upper() if sign else "LEARN"
    catalog = SIGN_CATALOG.get(sign_key, SIGN_CATALOG["LEARN"])
    topic = catalog["recommended_topic"]
    lesson_text = generate_lesson(topic, mode="sign")
    save_user_lesson(username, topic, lesson_text, mode="sign")
    update_user_streak(username)
    return sign_dashboard(username=username, lesson=lesson_text, topic=topic, sign=sign_key)

# --- REST API ENDPOINTS (For React client / mobile / headless) ---
@app.post("/api/generate")
def api_generate(data: GeneratePayload):
    lesson_text = generate_lesson(data.topic, mode=data.mode)
    if data.username:
        save_user_lesson(data.username, data.topic, lesson_text, mode=data.mode)
    return {"lesson": lesson_text, "topic": data.topic, "mode": data.mode}

@app.post("/api/profile")
def api_profile(data: ProfilePayload):
    if data.role not in {"blind", "deaf", "sign", "non_speaking"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose blind, deaf, or sign mode.")
    username = (data.username or "Guest Learner").strip() or "Guest Learner"
    update_profile_role(username, data.role)
    profile = get_or_create_profile(username, data.role)
    return {"username": profile["username"], "role": data.role, "streak": profile["streak"]}

@app.post("/api/sign/lesson")
def api_sign_lesson(data: SignLessonPayload):
    recognition = analyze_landmarks(data.landmarks)
    gesture = recognition.get("gesture", "UNKNOWN")
    catalog_entry = SIGN_CATALOG.get(gesture)
    if not recognition.get("hand_detected") or not catalog_entry:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No supported sign gesture was detected.")

    username = (data.username or "Guest Learner").strip() or "Guest Learner"
    update_profile_role(username, "sign")
    topic = catalog_entry["recommended_topic"]
    lesson_text = generate_lesson(topic, mode="sign")
    save_user_lesson(username, topic, lesson_text, mode="sign")
    return {
        "gesture": gesture,
        "name": catalog_entry["name"],
        "symbol": catalog_entry["symbol"],
        "confidence": recognition.get("confidence", 0.0),
        "topic": topic,
        "lesson": lesson_text,
        "username": username,
    }

@app.post("/api/air-writing-lesson")
def api_air_writing_lesson(data: AirWritingLessonPayload):
    topic = data.topic.strip()
    if not topic:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recognized topic cannot be empty.")
    if len(topic) > 120:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recognized topic must be 120 characters or fewer.")

    username = (data.username or "Guest Learner").strip() or "Guest Learner"
    update_profile_role(username, "sign")
    lesson_text = generate_lesson(topic, mode="sign")
    save_user_lesson(username, topic, lesson_text, mode="sign")
    return {"topic": topic, "lesson": lesson_text, "username": username}

@app.post("/api/quiz")
def api_quiz(data: QuizPayload):
    quiz_text = generate_quiz(data.topic, data.lesson or "")
    return {"quiz": quiz_text, "topic": data.topic}

@app.get("/api/history")
def api_history(username: Optional[str] = None):
    if not username:
        return []
    return get_user_history(username)

@app.get("/api/history/{username}")
def api_history_by_user(username: str):
    history = get_user_history(username)
    streak = get_user_streak(username)
    return {"history": history, "streak": streak}

@app.get("/api/stats/{username}")
def api_stats(username: str):
    return get_user_stats(username)

@app.post("/api/quiz-result")
def api_record_quiz(data: QuizResultPayload):
    result = record_quiz_result(data.username, data.topic, data.score, data.total_questions, data.correct_answers)
    return result

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"[*] SignBridge starting on http://127.0.0.1:{port}")
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)