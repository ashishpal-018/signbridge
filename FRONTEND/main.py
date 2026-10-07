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
from ai_engine import generate_lesson, generate_quiz, generate_structured_blind_quiz, generate_structured_deaf_quiz, generate_chat_response

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

class BlindQuizPayload(BaseModel):
    topic: str
    summary: Optional[str] = ""
    username: Optional[str] = "Guest Learner"

class DeafQuizPayload(BaseModel):
    topic: str
    summary: Optional[str] = ""
    username: Optional[str] = "Guest Learner"

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

class AirWritingRecognizePayload(BaseModel):
    trajectory: List[Dict[str, float]]


class ChatMessagePayload(BaseModel):
    role: str
    content: str

class BlindChatPayload(BaseModel):
    username: Optional[str] = "Guest Learner"
    messages: List[ChatMessagePayload]
    mode: Optional[str] = "blind"


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
        escaped_topic = topic.replace('"', '&quot;').replace("'", "&#39;")
        escaped_username = username.replace('"', '&quot;').replace("'", "&#39;")

        lesson_section = f"""
        <section class="mt-8 p-6 bg-slate-950/70 rounded-2xl border border-slate-800 shadow-xl">
            <div class="flex justify-between items-center mb-4 pb-3 border-b border-slate-800">
                <h2 class="text-base font-bold text-emerald-400">Audio Lesson: {topic}</h2>
                <div class="flex gap-2">
                    <button onclick="speakLessonText()" class="bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded-xl text-xs font-bold transition shadow-md cursor-pointer flex items-center gap-1.5">🔊 Read Aloud</button>
                    <button onclick="window.speechSynthesis.cancel()" class="bg-rose-500/10 hover:bg-rose-500 text-rose-300 hover:text-white border border-rose-500/20 px-3 py-2 rounded-xl text-xs font-bold transition cursor-pointer">⏹ Stop</button>
                </div>
            </div>
            <div id="lesson-text" class="text-slate-200 text-base leading-relaxed whitespace-pre-line font-light mb-8">{lesson}</div>

            <!-- Real-Time Audio Quiz Section for Blind Learners -->
            <div id="blind-quiz-container" class="mt-8 p-6 bg-slate-900/90 rounded-2xl border border-blue-900/40 shadow-2xl">
                <div class="flex justify-between items-center mb-4 pb-3 border-b border-slate-800">
                    <div>
                        <span class="text-[10px] tracking-wider bg-blue-500/20 text-blue-300 border border-blue-500/30 px-3 py-1 rounded-full uppercase font-bold">🧠 Real-Time Audio Quiz</span>
                        <h3 class="text-lg font-bold text-white mt-2">Sequential Voice Comprehension Assessment</h3>
                    </div>
                    <button onclick="startBlindAudioQuiz()" class="bg-blue-600 hover:bg-blue-500 text-white font-bold px-4 py-2 rounded-xl text-xs uppercase tracking-wider transition shadow-lg cursor-pointer">🔄 Load / Retake 5-MCQ Audio Quiz</button>
                </div>

                <!-- Live Metrics Bar -->
                <div id="blind-metrics-bar" class="grid grid-cols-4 gap-2 mb-4 p-3 bg-slate-950/80 rounded-xl border border-slate-800 text-center">
                    <div><span class="text-[10px] text-slate-400 uppercase block">Progress</span><strong id="b-metric-progress" class="text-sm text-white">1 / 5</strong></div>
                    <div><span class="text-[10px] text-slate-400 uppercase block">Score</span><strong id="b-metric-score" class="text-sm text-blue-400">0 Correct</strong></div>
                    <div><span class="text-[10px] text-slate-400 uppercase block">Accuracy</span><strong id="b-metric-accuracy" class="text-sm text-emerald-400">100%</strong></div>
                    <div><span class="text-[10px] text-slate-400 uppercase block">Time</span><strong id="b-metric-timer" class="text-sm text-amber-400">⏱️ 0s</strong></div>
                </div>

                <!-- Live Audio Status Banner -->
                <div id="b-status-banner" class="p-3 mb-4 rounded-xl text-xs font-semibold text-center bg-blue-950/40 border border-blue-800/50 text-blue-200">
                    Click below to start your 5-question sequential voice quiz. The agent will read Question 1, listen for your spoken choice (Option 1, 2, 3, or 4), and proceed sequentially.
                </div>

                <!-- Main Quiz Area -->
                <div id="b-quiz-main-box" class="space-y-4">
                    <div id="b-question-card" class="p-4 bg-slate-950/90 rounded-xl border border-slate-800">
                        <div class="text-xs text-blue-400 font-bold uppercase mb-1" id="b-q-meta">Question 1 of 5 • Listen to Narration & Speak Option 1, 2, 3, or 4</div>
                        <div class="text-base text-white font-semibold" id="b-q-text">Click "Start Audio Quiz" to begin sequential narration.</div>
                    </div>

                    <!-- Audio Controls Bar -->
                    <div class="flex flex-wrap gap-2 items-center">
                        <button onclick="replayCurrentQuestion()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 px-3.5 py-2 rounded-xl text-xs font-bold transition border border-slate-700">🔊 Replay Narration</button>
                        <button id="b-mic-btn" onclick="toggleBlindMic()" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer">🎙️ Speak Answer (Option 1, 2, 3, or 4)</button>
                        <button onclick="window.speechSynthesis.cancel()" class="bg-slate-800 hover:bg-slate-700 text-rose-300 px-3 py-2 rounded-xl text-xs font-bold transition border border-slate-700">⏹ Stop Narration</button>
                    </div>

                    <!-- 4 Options Grid -->
                    <div id="b-options-grid" class="grid grid-cols-1 md:grid-cols-2 gap-3"></div>

                    <!-- Concept Explanation -->
                    <div id="b-explanation-box" class="hidden p-4 rounded-xl text-sm leading-relaxed border"></div>
                </div>

                <!-- Completion Dashboard (hidden initially) -->
                <div id="b-quiz-completion-card" class="hidden text-center py-6 space-y-4">
                    <div class="text-4xl mb-1">🏆</div>
                    <h3 class="text-xl font-bold text-blue-300">Learning Progress Dashboard</h3>
                    <p class="text-xs text-slate-400">Audio Learning Assessment Summary — Blind Mode</p>
                    <div class="grid grid-cols-3 gap-3 max-w-md mx-auto my-4">
                        <div class="p-3 bg-slate-950/80 rounded-xl border border-slate-800"><span class="text-[10px] text-slate-400 block uppercase">Final Score</span><strong id="b-final-score-val" class="text-lg text-white">0/5</strong></div>
                        <div class="p-3 bg-slate-950/80 rounded-xl border border-slate-800"><span class="text-[10px] text-slate-400 block uppercase">Accuracy</span><strong id="b-final-acc-val" class="text-lg text-emerald-400">0%</strong></div>
                        <div class="p-3 bg-slate-950/80 rounded-xl border border-slate-800"><span class="text-[10px] text-slate-400 block uppercase">Time Taken</span><strong id="b-final-time-val" class="text-lg text-amber-400">0s</strong></div>
                    </div>
                    <div id="b-badge-award-banner" class="hidden p-3 bg-gradient-to-r from-blue-900/50 to-indigo-900/50 border border-blue-500/40 rounded-xl text-sm font-bold text-blue-200"></div>
                    <div id="b-questions-review-list" class="text-left space-y-2 max-w-md mx-auto text-xs"></div>
                    <button onclick="startBlindAudioQuiz()" class="mt-4 bg-blue-600 hover:bg-blue-500 text-white font-bold px-6 py-3 rounded-xl text-sm transition shadow-lg cursor-pointer">🔄 Retake 5-MCQ Audio Quiz</button>
                </div>
            </div>

            <script>
                let bQuizQuestions = [];
                let bCurrentIdx = 0;
                let bScore = 0;
                let bAnswersHistory = [];
                let bQStartTime = Date.now();
                let bTimerInt = null;
                let bQuizStartMs = Date.now();
                let bSelectedOptIdx = null;
                let bIsListening = false;
                let bSpeechRec = null;

                function speakLessonText() {{
                    const el = document.getElementById("lesson-text");
                    if (!el) return;
                    window.speechSynthesis.cancel();
                    let utterance = new SpeechSynthesisUtterance(el.innerText);
                    window.speechSynthesis.speak(utterance);
                }}

                function initBlindSpeechRec() {{
                    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
                    if (!SpeechRec) return null;
                    const rec = new SpeechRec();
                    rec.continuous = false;
                    rec.interimResults = false;
                    rec.lang = 'en-US';

                    rec.onstart = () => {{
                        bIsListening = true;
                        const micBtn = document.getElementById("b-mic-btn");
                        if (micBtn) micBtn.innerHTML = "🔴 Listening... Speak Option 1, 2, 3, or 4";
                        const banner = document.getElementById("b-status-banner");
                        if (banner) banner.innerText = "🎙️ Listening for your answer for Question " + (bCurrentIdx + 1) + "... Say Option 1, Option 2, Option 3, or Option 4.";
                    }};

                    rec.onresult = (event) => {{
                        const transcript = (event.results[0][0].transcript || '').toLowerCase().trim();
                        bIsListening = false;
                        const micBtn = document.getElementById("b-mic-btn");
                        if (micBtn) micBtn.innerHTML = "🎙️ Speak Answer (Option 1, 2, 3, or 4)";
                        parseBlindSpokenAnswer(transcript);
                    }};

                    rec.onerror = (event) => {{
                        bIsListening = false;
                        const micBtn = document.getElementById("b-mic-btn");
                        if (micBtn) micBtn.innerHTML = "🎙️ Speak Answer (Option 1, 2, 3, or 4)";
                        const banner = document.getElementById("b-status-banner");
                        if (banner) banner.innerText = "⚠️ Voice error: " + event.error + ". Tap an option button or retry.";
                    }};

                    rec.onend = () => {{
                        bIsListening = false;
                        const micBtn = document.getElementById("b-mic-btn");
                        if (micBtn) micBtn.innerHTML = "🎙️ Speak Answer (Option 1, 2, 3, or 4)";
                    }};

                    return rec;
                }}

                function toggleBlindMic() {{
                    if (bIsListening) {{
                        if (bSpeechRec) try {{ bSpeechRec.stop(); }} catch(e) {{}}
                        bIsListening = false;
                        document.getElementById("b-mic-btn").innerHTML = "🎙️ Speak Answer (Option 1, 2, 3, or 4)";
                    }} else {{
                        window.speechSynthesis.cancel();
                        if (!bSpeechRec) bSpeechRec = initBlindSpeechRec();
                        if (bSpeechRec) {{
                            try {{ bSpeechRec.start(); }} catch(e) {{}}
                        }}
                    }}
                }}

                async function startBlindAudioQuiz() {{
                    window.speechSynthesis.cancel();
                    const compCard = document.getElementById("b-quiz-completion-card");
                    const mainBox = document.getElementById("b-quiz-main-box");
                    const banner = document.getElementById("b-status-banner");

                    compCard.classList.add("hidden");
                    mainBox.classList.remove("hidden");
                    banner.className = "p-3 mb-4 rounded-xl text-xs font-semibold text-center bg-blue-950/40 border border-blue-800/50 text-blue-200";
                    banner.innerText = "⏳ Generating 5 audio MCQ questions from LLM engine...";

                    bCurrentIdx = 0;
                    bScore = 0;
                    bAnswersHistory = [];
                    bSelectedOptIdx = null;
                    bQuizStartMs = Date.now();

                    try {{
                        const resp = await fetch("/api/blind/quiz", {{
                            method: "POST",
                            headers: {{ "Content-Type": "application/json" }},
                            body: JSON.stringify({{ topic: "{escaped_topic}", summary: `{lesson.replace('`', '')}`, username: "{escaped_username}" }})
                        }});
                        const data = await resp.json();
                        if (data.questions && data.questions.length > 0) {{
                            bQuizQuestions = data.questions;
                            renderBlindQuestion();
                        }} else {{
                            banner.innerText = "❌ Failed to load 5-question audio quiz. Retake to try again.";
                        }}
                    }} catch (e) {{
                        banner.innerText = "❌ Error loading audio quiz: " + e.message;
                    }}
                }}

                function renderBlindQuestion() {{
                    if (bCurrentIdx >= bQuizQuestions.length) {{
                        finishBlindQuiz();
                        return;
                    }}
                    bSelectedOptIdx = null;
                    bQStartTime = Date.now();
                    clearInterval(bTimerInt);
                    bTimerInt = setInterval(() => {{
                        const sec = Math.floor((Date.now() - bQStartTime) / 1000);
                        document.getElementById("b-metric-timer").innerText = "⏱️ " + sec + "s";
                    }}, 1000);

                    const q = bQuizQuestions[bCurrentIdx];
                    document.getElementById("b-metric-progress").innerText = (bCurrentIdx + 1) + " / " + bQuizQuestions.length;
                    document.getElementById("b-metric-score").innerText = bScore + " Correct";
                    const acc = bCurrentIdx > 0 ? Math.round((bScore / bCurrentIdx) * 100) : 100;
                    document.getElementById("b-metric-accuracy").innerText = acc + "%";

                    document.getElementById("b-q-meta").innerText = "Question " + (bCurrentIdx + 1) + " of " + bQuizQuestions.length + " • Listen & Speak Option 1, 2, 3, or 4";
                    document.getElementById("b-q-text").innerText = q.question;

                    const grid = document.getElementById("b-options-grid");
                    grid.innerHTML = "";
                    const letters = ["A", "B", "C", "D"];

                    q.options.forEach((optText, idx) => {{
                        const btn = document.createElement("button");
                        btn.className = "p-4 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 hover:border-blue-500 rounded-xl text-left transition flex flex-col gap-1 cursor-pointer";
                        btn.onclick = () => handleBlindSelectOption(idx);
                        btn.innerHTML = `<span class="text-[10px] font-extrabold uppercase bg-blue-900/40 text-blue-300 border border-blue-700/50 px-2 py-0.5 rounded w-fit">Option ${{letters[idx]}} (Choice ${{idx+1}})</span><span class="text-sm text-slate-200 font-medium">${{optText}}</span>`;
                        grid.appendChild(btn);
                    }});

                    document.getElementById("b-explanation-box").classList.add("hidden");

                    // Crucial requirement: Agent reads Question N & 4 Options, THEN automatically listens for learner's answer!
                    speakBlindQuestionAndOptions(bCurrentIdx);
                }}

                function speakBlindQuestionAndOptions(idx) {{
                    const q = bQuizQuestions[idx];
                    if (!q) return;
                    window.speechSynthesis.cancel();

                    const banner = document.getElementById("b-status-banner");
                    banner.className = "p-3 mb-4 rounded-xl text-xs font-semibold text-center bg-blue-950/40 border border-blue-800/50 text-blue-200";
                    banner.innerText = "🔊 Reading Question " + (idx + 1) + " of " + bQuizQuestions.length + " and options...";

                    const text = "Question " + (idx + 1) + " of " + bQuizQuestions.length + ": " + q.question + ". Option 1: " + q.options[0] + ". Option 2: " + q.options[1] + ". Option 3: " + q.options[2] + ". Option 4: " + q.options[3] + ". Please speak your choice now: Option 1, Option 2, Option 3, or Option 4.";

                    const utterance = new SpeechSynthesisUtterance(text);
                    utterance.rate = 1.0;
                    utterance.onend = () => {{
                        // Automatically start listening right after learner hears Question N!
                        if (bSelectedOptIdx === null) {{
                            if (!bSpeechRec) bSpeechRec = initBlindSpeechRec();
                            if (bSpeechRec) {{
                                try {{ bSpeechRec.start(); }} catch(e) {{}}
                            }}
                        }}
                    }};
                    window.speechSynthesis.speak(utterance);
                }}

                function replayCurrentQuestion() {{
                    speakBlindQuestionAndOptions(bCurrentIdx);
                }}

                function parseBlindSpokenAnswer(transcript) {{
                    if (bSelectedOptIdx !== null) return;
                    let matched = -1;
                    if (/\\b(one|1|first|option 1|option a|choice 1|choice a|^1$|^a$)\\b/i.test(transcript)) matched = 0;
                    else if (/\\b(two|to|too|2|second|option 2|option b|choice 2|choice b|^2$|^b$)\\b/i.test(transcript)) matched = 1;
                    else if (/\\b(three|tree|3|third|option 3|option c|choice 3|choice c|^3$|^c$)\\b/i.test(transcript)) matched = 2;
                    else if (/\\b(four|for|fore|4|fourth|option 4|option d|choice 4|choice d|^4$|^d$)\\b/i.test(transcript)) matched = 3;
                    else {{
                        const q = bQuizQuestions[bCurrentIdx];
                        if (q && q.options) {{
                            q.options.forEach((opt, idx) => {{
                                if (transcript.length > 2 && (transcript.includes(opt.toLowerCase()) || opt.toLowerCase().includes(transcript))) {{
                                    matched = idx;
                                }}
                            }});
                        }}
                    }}

                    if (matched >= 0 && matched < 4) {{
                        handleBlindSelectOption(matched);
                    }} else {{
                        const banner = document.getElementById("b-status-banner");
                        banner.innerText = '⚠️ Heard "' + transcript + '", but couldn\'t match Option 1, 2, 3, or 4. Please say Option 1, 2, 3, or 4.';
                        let retryUtterance = new SpeechSynthesisUtterance('I heard ' + transcript + ', but please say Option 1, Option 2, Option 3, or Option 4.');
                        retryUtterance.onend = () => {{
                            if (bSelectedOptIdx === null && bSpeechRec) {{
                                try {{ bSpeechRec.start(); }} catch(e) {{}}
                            }}
                        }};
                        window.speechSynthesis.speak(retryUtterance);
                    }}
                }}

                function handleBlindSelectOption(idx) {{
                    if (bSelectedOptIdx !== null) return;
                    bSelectedOptIdx = idx;
                    clearInterval(bTimerInt);
                    window.speechSynthesis.cancel();
                    if (bSpeechRec) try {{ bSpeechRec.stop(); }} catch(e) {{}}

                    const q = bQuizQuestions[bCurrentIdx];
                    const isCorrect = idx === q.correct_index;
                    bAnswersHistory.push({{ isCorrect, question: q.question }});
                    if (isCorrect) bScore++;

                    document.getElementById("b-metric-score").innerText = bScore + " Correct";
                    const acc = Math.round((bScore / bAnswersHistory.length) * 100);
                    document.getElementById("b-metric-accuracy").innerText = acc + "%";

                    const banner = document.getElementById("b-status-banner");
                    if (isCorrect) {{
                        banner.className = "p-3 mb-4 rounded-xl text-xs font-semibold text-center bg-emerald-950/60 border border-emerald-500/50 text-emerald-300";
                        banner.innerText = "✅ Correct! Great audio comprehension.";
                    }} else {{
                        banner.className = "p-3 mb-4 rounded-xl text-xs font-semibold text-center bg-rose-950/60 border border-rose-500/50 text-rose-300";
                        banner.innerText = "❌ Incorrect. Option " + ["A", "B", "C", "D"][q.correct_index] + " was the correct choice.";
                    }}

                    const gridBtns = document.getElementById("b-options-grid").children;
                    q.options.forEach((_, optIdx) => {{
                        const btn = gridBtns[optIdx];
                        btn.onclick = null;
                        btn.classList.remove("hover:bg-slate-800", "hover:border-blue-500");
                        if (optIdx === q.correct_index) {{
                            btn.className += " bg-emerald-950/50 border-emerald-500 text-emerald-200";
                        }} else if (optIdx === idx) {{
                            btn.className += " bg-rose-950/50 border-rose-500 text-rose-200";
                        }} else {{
                            btn.className += " opacity-40";
                        }}
                    }});

                    const expBox = document.getElementById("b-explanation-box");
                    expBox.classList.remove("hidden");
                    expBox.className = "p-4 rounded-xl text-xs leading-relaxed border " + (isCorrect ? "bg-emerald-950/30 border-emerald-800 text-emerald-200" : "bg-blue-950/30 border-blue-800 text-blue-200");
                    const isLastQ = bCurrentIdx >= bQuizQuestions.length - 1;
                    const nextBtnText = isLastQ ? "🏆 View Learning Progress Dashboard" : "➡️ Proceed to Next Question (Question " + (bCurrentIdx + 2) + " of " + bQuizQuestions.length + ")";
                    expBox.innerHTML = `<strong>${{isCorrect ? '🎉 Correct Understanding!' : '💡 Key Concept Explanation:'}}</strong><p class="mt-1">${{q.explanation}}</p><button onclick="proceedToNextBlindQuestion()" class="mt-3 w-full bg-blue-600 hover:bg-blue-500 text-white font-bold p-3 rounded-xl text-xs transition cursor-pointer shadow-lg">${{nextBtnText}}</button>`;

                    let feedbackText = isCorrect ? "Correct! " + q.explanation : "Incorrect. The correct answer was Option " + (q.correct_index + 1) + ". " + q.explanation;
                    let feedbackUtterance = new SpeechSynthesisUtterance(feedbackText);

                    // Crucial requirement: After feedback for Question N finishes, automatically proceed to Question N+1!
                    feedbackUtterance.onend = () => {{
                        setTimeout(() => {{
                            proceedToNextBlindQuestion();
                        }}, 500);
                    }};
                    window.speechSynthesis.speak(feedbackUtterance);
                }}

                function proceedToNextBlindQuestion() {{
                    window.speechSynthesis.cancel();
                    bCurrentIdx++;
                    renderBlindQuestion();
                }}

                async function finishBlindQuiz() {{
                    document.getElementById("b-quiz-main-box").classList.add("hidden");
                    document.getElementById("b-quiz-completion-card").classList.remove("hidden");

                    const totalTime = Math.floor((Date.now() - bQuizStartMs) / 1000);
                    const totalQ = bQuizQuestions.length;
                    const finalScorePct = Math.round((bScore / totalQ) * 100);

                    document.getElementById("b-final-score-val").innerText = bScore + " / " + totalQ;
                    document.getElementById("b-final-acc-val").innerText = finalScorePct + "%";
                    document.getElementById("b-final-time-val").innerText = totalTime + "s";

                    const reviewList = document.getElementById("b-questions-review-list");
                    reviewList.innerHTML = "";
                    bAnswersHistory.forEach((item, idx) => {{
                        const div = document.createElement("div");
                        div.className = "p-2.5 rounded-lg border flex items-center justify-between " + (item.isCorrect ? "bg-emerald-950/30 border-emerald-800 text-emerald-300" : "bg-rose-950/30 border-rose-800 text-rose-300");
                        div.innerHTML = `<span>${{item.isCorrect ? '✅' : '❌'}} Q${{idx + 1}}: ${{item.question.substring(0, 60)}}...</span>`;
                        reviewList.appendChild(div);
                    }});

                    const completionSpeech = "Quiz completed! You scored " + bScore + " out of " + totalQ + " questions correctly with an accuracy of " + finalScorePct + " percent.";
                    let compUtterance = new SpeechSynthesisUtterance(completionSpeech);
                    window.speechSynthesis.speak(compUtterance);

                    try {{
                        const res = await fetch("/api/quiz-result", {{
                            method: "POST",
                            headers: {{ "Content-Type": "application/json" }},
                            body: JSON.stringify({{
                                username: "{escaped_username}",
                                topic: "{escaped_topic}",
                                score: finalScorePct,
                                total_questions: totalQ,
                                correct_answers: bScore
                            }})
                        }});
                        const resData = await res.json();
                        if (resData.badge_earned) {{
                            const badgeBanner = document.getElementById("b-badge-award-banner");
                            badgeBanner.classList.remove("hidden");
                            badgeBanner.innerText = "🎉 Milestone Badge Awarded: " + resData.badge_earned;
                        }}
                    }} catch (e) {{}}
                }}

                window.addEventListener("DOMContentLoaded", () => {{
                    startBlindAudioQuiz();
                }});
            </script>
        </section>
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
        <p class="text-slate-400 text-sm mb-6">Enter any subject to generate a clean audio lesson and test your knowledge with a real-time 5-question voice quiz.</p>
        <form action="/blind-dashboard" method="POST" class="space-y-4">
            <input type="hidden" name="username" value="{username}">
            <input type="text" name="topic" required placeholder="e.g., Photosynthesis, Gravity..." class="w-full p-4 bg-slate-950/60 rounded-xl border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition">
            <button type="submit" class="w-full bg-blue-600 hover:bg-blue-500 p-4 rounded-xl font-bold transition shadow-lg shadow-blue-600/20 cursor-pointer">Generate Audio Lesson & Voice Quiz</button>
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
    quiz_text = generate_quiz(topic, lesson_text)
    return blind_dashboard(username=username, lesson=lesson_text, topic=topic, quiz=quiz_text)

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
        escaped_topic = topic.replace('"', '&quot;').replace("'", "&#39;")
        escaped_username = username.replace('"', '&quot;').replace("'", "&#39;")

        lesson_section = f"""
        <section class="mt-8 p-6 bg-slate-950/70 rounded-2xl border border-slate-800 shadow-xl">
            <h2 class="text-base font-bold text-purple-400 mb-4 pb-3 border-b border-slate-800 flex items-center gap-2">📖 Visual Module: {topic}</h2>
            <div class="text-slate-200 text-base leading-relaxed whitespace-pre-line space-y-3 font-normal mb-8">{lesson}</div>

            <!-- Real-Time Adaptive Quiz Section for Deaf Learners -->
            <div id="deaf-quiz-container" class="mt-8 p-6 bg-slate-900/90 rounded-2xl border border-purple-900/40 shadow-2xl">
                <div class="flex justify-between items-center mb-4 pb-3 border-b border-slate-800">
                    <div>
                        <span class="text-[10px] tracking-wider bg-purple-500/20 text-purple-300 border border-purple-500/30 px-3 py-1 rounded-full uppercase font-bold">🧠 Real-Time Adaptive Quiz</span>
                        <h3 class="text-lg font-bold text-white mt-2">Visual Comprehension Assessment</h3>
                    </div>
                    <button onclick="startDeafQuiz()" class="bg-purple-600 hover:bg-purple-500 text-white font-bold px-4 py-2 rounded-xl text-xs uppercase tracking-wider transition shadow-lg cursor-pointer">🔄 Load / Retake 5-MCQ Quiz</button>
                </div>

                <!-- Live Metrics Bar -->
                <div id="quiz-metrics-bar" class="grid grid-cols-4 gap-2 mb-4 p-3 bg-slate-950/80 rounded-xl border border-slate-800 text-center">
                    <div><span class="text-[10px] text-slate-400 uppercase block">Progress</span><strong id="metric-progress" class="text-sm text-white">1 / 5</strong></div>
                    <div><span class="text-[10px] text-slate-400 uppercase block">Score</span><strong id="metric-score" class="text-sm text-purple-400">0 Correct</strong></div>
                    <div><span class="text-[10px] text-slate-400 uppercase block">Accuracy</span><strong id="metric-accuracy" class="text-sm text-emerald-400">100%</strong></div>
                    <div><span class="text-[10px] text-slate-400 uppercase block">Time</span><strong id="metric-timer" class="text-sm text-amber-400">⏱️ 0s</strong></div>
                </div>

                <!-- Status Banner -->
                <div id="quiz-status-banner" class="p-3 mb-4 rounded-xl text-xs font-semibold text-center bg-purple-950/40 border border-purple-800/50 text-purple-200">
                    Click below to start your LLM-generated 5-question multiple choice adaptive quiz.
                </div>

                <!-- Quiz Main Area -->
                <div id="quiz-main-box" class="space-y-4">
                    <div id="question-card" class="p-4 bg-slate-950/90 rounded-xl border border-slate-800">
                        <div class="text-xs text-purple-400 font-bold uppercase mb-1" id="q-meta">Question 1 of 5 • Select 1 Option</div>
                        <div class="text-base text-white font-semibold" id="q-text">Click "Start Quiz" to generate visual questions.</div>
                    </div>

                    <!-- 4 Options Grid -->
                    <div id="options-grid" class="grid grid-cols-1 md:grid-cols-2 gap-3"></div>

                    <!-- Concept Explanation -->
                    <div id="explanation-box" class="hidden p-4 rounded-xl text-sm leading-relaxed border"></div>

                    <!-- Next Button -->
                    <div id="action-bar" class="flex justify-end hidden">
                        <button id="next-q-btn" onclick="nextQuestion()" class="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold px-6 py-3 rounded-xl text-sm transition shadow-lg cursor-pointer">Next Question ➔</button>
                    </div>
                </div>

                <!-- Completion Card (hidden initially) -->
                <div id="quiz-completion-card" class="hidden text-center py-6 space-y-4">
                    <div class="text-4xl mb-1">🏆</div>
                    <h3 class="text-xl font-bold text-purple-300">Quiz Completed!</h3>
                    <p class="text-xs text-slate-400">Real-Time Visual Learning Performance Breakdown</p>
                    <div class="grid grid-cols-3 gap-3 max-w-md mx-auto my-4">
                        <div class="p-3 bg-slate-950/80 rounded-xl border border-slate-800"><span class="text-[10px] text-slate-400 block uppercase">Final Score</span><strong id="final-score-val" class="text-lg text-white">0/5</strong></div>
                        <div class="p-3 bg-slate-950/80 rounded-xl border border-slate-800"><span class="text-[10px] text-slate-400 block uppercase">Accuracy</span><strong id="final-acc-val" class="text-lg text-emerald-400">0%</strong></div>
                        <div class="p-3 bg-slate-950/80 rounded-xl border border-slate-800"><span class="text-[10px] text-slate-400 block uppercase">Time Taken</span><strong id="final-time-val" class="text-lg text-amber-400">0s</strong></div>
                    </div>
                    <div id="badge-award-banner" class="hidden p-3 bg-gradient-to-r from-purple-900/50 to-indigo-900/50 border border-purple-500/40 rounded-xl text-sm font-bold text-purple-200"></div>
                    <div id="questions-review-list" class="text-left space-y-2 max-w-md mx-auto text-xs"></div>
                    <button onclick="startDeafQuiz()" class="mt-4 bg-purple-600 hover:bg-purple-500 text-white font-bold px-6 py-3 rounded-xl text-sm transition shadow-lg cursor-pointer">🔄 Retake 5-MCQ Quiz</button>
                </div>
            </div>

            <script>
                let currentQuizQuestions = [];
                let currentQIdx = 0;
                let userScore = 0;
                let userAnswersHistory = [];
                let qStartTime = Date.now();
                let timerInt = null;
                let quizStartMs = Date.now();
                let selectedOptIdx = null;

                async function startDeafQuiz() {{
                    const container = document.getElementById("deaf-quiz-container");
                    const statusBanner = document.getElementById("quiz-status-banner");
                    const qMainBox = document.getElementById("quiz-main-box");
                    const compCard = document.getElementById("quiz-completion-card");
                    
                    compCard.classList.add("hidden");
                    qMainBox.classList.remove("hidden");
                    statusBanner.className = "p-3 mb-4 rounded-xl text-xs font-semibold text-center bg-purple-950/40 border border-purple-800/50 text-purple-200";
                    statusBanner.innerText = "⏳ Generating 5 visual MCQ questions from LLM engine...";

                    currentQIdx = 0;
                    userScore = 0;
                    userAnswersHistory = [];
                    selectedOptIdx = null;
                    quizStartMs = Date.now();

                    try {{
                        const resp = await fetch("/api/deaf/quiz", {{
                            method: "POST",
                            headers: {{ "Content-Type": "application/json" }},
                            body: JSON.stringify({{ topic: "{escaped_topic}", summary: `{lesson.replace('`', '')}`, username: "{escaped_username}" }})
                        }});
                        const data = await resp.json();
                        if (data.questions && data.questions.length > 0) {{
                            currentQuizQuestions = data.questions;
                            renderQuestion();
                        }} else {{
                            statusBanner.innerText = "❌ Failed to load quiz questions. Click retake to try again.";
                        }}
                    }} catch (e) {{
                        statusBanner.innerText = "❌ Error connecting to quiz generator: " + e.message;
                    }}
                }}

                function renderQuestion() {{
                    if (currentQIdx >= currentQuizQuestions.length) {{
                        finishDeafQuiz();
                        return;
                    }}
                    selectedOptIdx = null;
                    qStartTime = Date.now();
                    clearInterval(timerInt);
                    timerInt = setInterval(() => {{
                        const sec = Math.floor((Date.now() - qStartTime) / 1000);
                        document.getElementById("metric-timer").innerText = "⏱️ " + sec + "s";
                    }}, 1000);

                    const q = currentQuizQuestions[currentQIdx];
                    document.getElementById("metric-progress").innerText = (currentQIdx + 1) + " / " + currentQuizQuestions.length;
                    document.getElementById("metric-score").innerText = userScore + " Correct";
                    const acc = currentQIdx > 0 ? Math.round((userScore / currentQIdx) * 100) : 100;
                    document.getElementById("metric-accuracy").innerText = acc + "%";

                    const statusBanner = document.getElementById("quiz-status-banner");
                    statusBanner.className = "p-3 mb-4 rounded-xl text-xs font-semibold text-center bg-purple-950/40 border border-purple-800/50 text-purple-200";
                    statusBanner.innerText = "Question " + (currentQIdx + 1) + " of " + currentQuizQuestions.length + " — Select 1 of 4 options below.";

                    document.getElementById("q-meta").innerText = "Question " + (currentQIdx + 1) + " of " + currentQuizQuestions.length + " • Select 1 Option";
                    document.getElementById("q-text").innerText = q.question;

                    const grid = document.getElementById("options-grid");
                    grid.innerHTML = "";
                    const letters = ["A", "B", "C", "D"];

                    q.options.forEach((optText, idx) => {{
                        const btn = document.createElement("button");
                        btn.className = "p-4 bg-slate-950/80 hover:bg-slate-800 border border-slate-800 hover:border-purple-500 rounded-xl text-left transition flex flex-col gap-1 cursor-pointer";
                        btn.onclick = () => handleSelectOption(idx);
                        btn.innerHTML = `<span class="text-[10px] font-extrabold uppercase bg-purple-900/40 text-purple-300 border border-purple-700/50 px-2 py-0.5 rounded w-fit">Option ${{letters[idx]}}</span><span class="text-sm text-slate-200 font-medium">${{optText}}</span>`;
                        grid.appendChild(btn);
                    }});

                    document.getElementById("explanation-box").classList.add("hidden");
                    document.getElementById("action-bar").classList.add("hidden");
                }}

                function handleSelectOption(idx) {{
                    if (selectedOptIdx !== null) return;
                    selectedOptIdx = idx;
                    clearInterval(timerInt);

                    const q = currentQuizQuestions[currentQIdx];
                    const isCorrect = idx === q.correct_index;
                    const elapsed = Math.floor((Date.now() - qStartTime) / 1000);

                    userAnswersHistory.push({{ isCorrect, question: q.question }});
                    if (isCorrect) userScore++;

                    document.getElementById("metric-score").innerText = userScore + " Correct";
                    const acc = Math.round((userScore / userAnswersHistory.length) * 100);
                    document.getElementById("metric-accuracy").innerText = acc + "%";

                    const statusBanner = document.getElementById("quiz-status-banner");
                    if (isCorrect) {{
                        statusBanner.className = "p-3 mb-4 rounded-xl text-xs font-semibold text-center bg-emerald-950/60 border border-emerald-500/50 text-emerald-300";
                        statusBanner.innerText = "✅ Correct! Great visual analysis.";
                    }} else {{
                        statusBanner.className = "p-3 mb-4 rounded-xl text-xs font-semibold text-center bg-rose-950/60 border border-rose-500/50 text-rose-300";
                        statusBanner.innerText = "❌ Incorrect. Option " + ["A", "B", "C", "D"][q.correct_index] + " was the correct choice.";
                    }}

                    const gridBtns = document.getElementById("options-grid").children;
                    q.options.forEach((_, optIdx) => {{
                        const btn = gridBtns[optIdx];
                        btn.onclick = null;
                        btn.classList.remove("hover:bg-slate-800", "hover:border-purple-500");
                        if (optIdx === q.correct_index) {{
                            btn.className += " bg-emerald-950/50 border-emerald-500 text-emerald-200";
                        }} else if (optIdx === idx) {{
                            btn.className += " bg-rose-950/50 border-rose-500 text-rose-200";
                        }} else {{
                            btn.className += " opacity-40";
                        }}
                    }});

                    const expBox = document.getElementById("explanation-box");
                    expBox.classList.remove("hidden");
                    expBox.className = "p-4 rounded-xl text-xs leading-relaxed border " + (isCorrect ? "bg-emerald-950/30 border-emerald-800 text-emerald-200" : "bg-purple-950/30 border-purple-800 text-purple-200");
                    expBox.innerHTML = `<strong>${{isCorrect ? '🎉 Correct Understanding!' : '💡 Key Concept Explanation:'}}</strong><p class="mt-1">${{q.explanation}}</p>`;

                    document.getElementById("action-bar").classList.remove("hidden");
                    document.getElementById("next-q-btn").innerText = (currentQIdx < currentQuizQuestions.length - 1) ? "Next Question ➔" : "View Final Quiz Summary 🏆";
                }}

                function nextQuestion() {{
                    currentQIdx++;
                    renderQuestion();
                }}

                async function finishDeafQuiz() {{
                    document.getElementById("quiz-main-box").classList.add("hidden");
                    document.getElementById("quiz-completion-card").classList.remove("hidden");

                    const totalTime = Math.floor((Date.now() - quizStartMs) / 1000);
                    const totalQ = currentQuizQuestions.length;
                    const finalScorePct = Math.round((userScore / totalQ) * 100);

                    document.getElementById("final-score-val").innerText = userScore + " / " + totalQ;
                    document.getElementById("final-acc-val").innerText = finalScorePct + "%";
                    document.getElementById("final-time-val").innerText = totalTime + "s";

                    const reviewList = document.getElementById("questions-review-list");
                    reviewList.innerHTML = "";
                    userAnswersHistory.forEach((item, idx) => {{
                        const div = document.createElement("div");
                        div.className = "p-2.5 rounded-lg border flex items-center justify-between " + (item.isCorrect ? "bg-emerald-950/30 border-emerald-800 text-emerald-300" : "bg-rose-950/30 border-rose-800 text-rose-300");
                        div.innerHTML = `<span>${{item.isCorrect ? '✅' : '❌'}} Q${{idx + 1}}: ${{item.question.substring(0, 60)}}...</span>`;
                        reviewList.appendChild(div);
                    }});

                    try {{
                        const res = await fetch("/api/quiz-result", {{
                            method: "POST",
                            headers: {{ "Content-Type": "application/json" }},
                            body: JSON.stringify({{
                                username: "{escaped_username}",
                                topic: "{escaped_topic}",
                                score: finalScorePct,
                                total_questions: totalQ,
                                correct_answers: userScore
                            }})
                        }});
                        const resData = await res.json();
                        if (resData.badge_earned) {{
                            const badgeBanner = document.getElementById("badge-award-banner");
                            badgeBanner.classList.remove("hidden");
                            badgeBanner.innerText = "🎉 Milestone Badge Awarded: " + resData.badge_earned;
                        }}
                    }} catch (e) {{}}
                }}

                // Auto-initialize quiz when visual module is displayed
                window.addEventListener("DOMContentLoaded", () => {{
                    startDeafQuiz();
                }});
            </script>
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
        <p class="text-slate-400 text-sm mb-6">Enter any subject to generate a structured visual text module and test your knowledge with a real-time adaptive quiz.</p>
        <form action="/deaf-dashboard" method="POST" class="space-y-4">
            <input type="hidden" name="username" value="{username}">
            <input type="text" name="topic" required placeholder="e.g., Quantum Physics, Solar System..." class="w-full p-4 bg-slate-950/60 rounded-xl border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-purple-500 transition">
            <button type="submit" class="w-full bg-purple-600 hover:bg-purple-500 p-4 rounded-xl font-bold transition shadow-lg shadow-purple-600/20 cursor-pointer">Generate Visual Module & Quiz</button>
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
    quiz_text = generate_quiz(topic, lesson_text)
    return deaf_dashboard(username=username, lesson=lesson_text, topic=topic, quiz=quiz_text)

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
    quiz_text = generate_quiz(topic, lesson_text)
    return sign_dashboard(username=username, lesson=lesson_text, topic=topic, sign=sign_key)

# --- REST API ENDPOINTS (For React client / mobile / headless) ---
@app.post("/api/generate")
def api_generate(data: GeneratePayload):
    lesson_text = generate_lesson(data.topic, mode=data.mode)
    quiz_text = generate_quiz(data.topic, lesson_text)
    if data.username:
        save_user_lesson(data.username, data.topic, lesson_text, mode=data.mode)
    return {"lesson": lesson_text, "quiz": quiz_text, "topic": data.topic, "mode": data.mode}

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
    quiz_text = generate_quiz(topic, lesson_text)
    save_user_lesson(username, topic, lesson_text, mode="sign")
    return {
        "gesture": gesture,
        "name": catalog_entry["name"],
        "symbol": catalog_entry["symbol"],
        "confidence": recognition.get("confidence", 0.0),
        "topic": topic,
        "lesson": lesson_text,
        "quiz": quiz_text,
        "username": username,
    }

@app.post("/api/air-writing/recognize")
def api_air_writing_recognize(data: AirWritingRecognizePayload):
    import math
    import re
    points = data.trajectory
    if not points or len(points) < 5:
        return {"success": False, "letter": None, "confidence": 0.0}

    xs = [p.get("x", 0.0) for p in points]
    ys = [p.get("y", 0.0) for p in points]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    w = max_x - min_x
    h = max_y - min_y

    aspect_ratio = w / h if h > 0.0001 else 1.0

    start_p = points[0]
    end_p = points[-1]
    mid_p = points[len(points) // 2]

    start_end_dist = math.hypot(end_p.get("x", 0) - start_p.get("x", 0), end_p.get("y", 0) - start_p.get("y", 0))
    is_closed = start_end_dist < 0.30 and len(points) >= 10

    min_y_idx = ys.index(min_y)
    max_y_idx = ys.index(max_y)

    is_top_apex = 3 <= min_y_idx <= len(points) - 4 and min_y < start_p.get("y", 0) - 0.15 and min_y < end_p.get("y", 0) - 0.15
    is_bottom_dip = 3 <= max_y_idx <= len(points) - 4 and max_y > start_p.get("y", 0) + 0.15 and max_y > end_p.get("y", 0) + 0.15

    scores = {}

    # Strict alphabet classification (NO numbers allowed)
    if is_closed and 0.5 <= aspect_ratio <= 1.6:
        scores['O'] = 0.95
    if is_top_apex and start_p.get("y", 0) > min_y + 0.2 and end_p.get("y", 0) > min_y + 0.2:
        scores['A'] = 0.96
    if aspect_ratio < 0.42 and abs(end_p.get("y", 0) - start_p.get("y", 0)) > 0.4:
        scores['I'] = 0.94
    if aspect_ratio > 0.35 and end_p.get("x", 0) > start_p.get("x", 0) + 0.2 and end_p.get("y", 0) > max_y - 0.25:
        scores['L'] = 0.93
    if not is_closed and start_p.get("x", 0) > min_x + 0.15 and end_p.get("x", 0) > min_x + 0.15 and mid_p.get("x", 0) < min_x + 0.15:
        scores['C'] = 0.93
    if is_bottom_dip and not is_closed:
        if aspect_ratio > 0.4:
            scores['V'] = 0.92
            scores['U'] = 0.89
    if not is_closed and aspect_ratio > 0.4:
        if start_p.get("x", 0) > mid_p.get("x", 0) and end_p.get("x", 0) < mid_p.get("x", 0):
            scores['S'] = 0.92
    if abs(start_p.get("y", 0) - min_y) < 0.2 and abs(end_p.get("y", 0) - max_y) < 0.25 and aspect_ratio > 0.45:
        scores['T'] = 0.91
    if start_p.get("x", 0) < max_x - 0.15 and end_p.get("x", 0) > min_x + 0.15 and min_y_idx < max_y_idx:
        scores['Z'] = 0.90
    if aspect_ratio > 0.7:
        if start_p.get("y", 0) < mid_p.get("y", 0) and end_p.get("y", 0) < mid_p.get("y", 0):
            scores['M'] = 0.91
        elif start_p.get("y", 0) > mid_p.get("y", 0) and end_p.get("y", 0) > mid_p.get("y", 0):
            scores['W'] = 0.91
    if max_y_idx >= len(points) // 2 and end_p.get("x", 0) < start_p.get("x", 0) - 0.1:
        scores['J'] = 0.90

    if not scores:
        if is_closed:
            scores['O'] = 0.85
        elif aspect_ratio < 0.45:
            scores['I'] = 0.85
        elif is_top_apex:
            scores['A'] = 0.85
        elif is_bottom_dip:
            scores['V'] = 0.85
        else:
            scores['E'] = 0.80

    best_letter = max(scores, key=scores.get)
    best_letter = re.sub(r'[^a-zA-Z]', '', best_letter).upper()
    return {"success": True, "letter": best_letter, "confidence": round(scores[best_letter], 2)}

@app.post("/api/air-writing-lesson")
def api_air_writing_lesson(data: AirWritingLessonPayload):
    import re
    topic = re.sub(r'[^a-zA-Z\s-]', '', data.topic or '').strip()
    if not topic:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recognized topic cannot be empty. Please trace alphabetic letters (A-Z).")
    if len(topic) > 120:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recognized topic must be 120 characters or fewer.")

    username = (data.username or "Guest Learner").strip() or "Guest Learner"
    update_profile_role(username, "sign")
    lesson_text = generate_lesson(topic, mode="sign")
    quiz_text = generate_quiz(topic, lesson_text)
    save_user_lesson(username, topic, lesson_text, mode="sign")
    return {"topic": topic, "lesson": lesson_text, "quiz": quiz_text, "username": username}

@app.post("/api/quiz")
def api_quiz(data: QuizPayload):
    quiz_text = generate_quiz(data.topic, data.lesson or "")
    return {"quiz": quiz_text, "topic": data.topic}

@app.post("/api/blind/quiz")
def api_blind_quiz(data: BlindQuizPayload):
    quiz_data = generate_structured_blind_quiz(data.topic, summary=data.summary or "")
    return quiz_data

@app.post("/api/deaf/quiz")
def api_deaf_quiz(data: DeafQuizPayload):
    quiz_data = generate_structured_deaf_quiz(data.topic, summary=data.summary or "")
    return quiz_data

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

@app.post("/api/blind/chat")
def api_blind_chat(data: BlindChatPayload):
    if not data.messages:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Messages list cannot be empty.")
    messages_list = [{"role": m.role, "content": m.content} for m in data.messages]
    res = generate_chat_response(messages_list, mode=data.mode or "blind")
    return {"reply": res["reply"], "provider": res["provider"]}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"[*] SignBridge starting on http://127.0.0.1:{port}")
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)