import React, { useState, useEffect } from 'react';

const API_URL = "/api";

export default function App() {
  const [user, setUser] = useState(null);
  const [isRegistering, setIsRegistering] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("blind");
  const [message, setMessage] = useState("");

  const [topic, setTopic] = useState("");
  const [lesson, setLesson] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (user) {
      fetch(`${API_URL}/history`, { credentials: "include" })
        .then(res => res.json())
        .then(data => setHistory(data))
        .catch(err => console.error(err));
    }
  }, [user]);

  const handleAuth = async (e) => {
    e.preventDefault();
    setMessage("");
    const endpoint = isRegistering ? `${API_URL}/register` : `${API_URL}/login`;
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, password, ...(isRegistering ? { role } : {}) })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Authentication failed");

      if (isRegistering) {
        setMessage("Registration successful! Please log in.");
        setIsRegistering(false);
      } else {
        setUser({ username: data.username, role: data.role });
      }
    } catch (err) {
      setMessage(err.message);
    }
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ topic, mode: user.role })
      });
      const data = await res.json();
      setLesson(data.lesson);
      
      const histRes = await fetch(`${API_URL}/history`, { credentials: "include" });
      setHistory(await histRes.json());
    } catch (err) {
      alert("Failed to generate lesson from local AI.");
    }
    setLoading(false);
  };

  const speak = (text) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-slate-900 p-8 rounded-3xl border border-slate-800 shadow-2xl">
          <h1 className="text-3xl font-extrabold text-blue-400 text-center mb-2">SignBridge</h1>
          <p className="text-slate-400 text-sm text-center mb-6">Accessible AI Learning Platform</p>
          
          {message && <div className="bg-indigo-950 text-indigo-300 p-3 rounded-xl mb-4 text-sm text-center font-medium">{message}</div>}

          <form onSubmit={handleAuth} className="space-y-4">
            <input type="text" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} required className="w-full p-3.5 bg-slate-950 rounded-xl border border-slate-800 text-white" />
            <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} required className="w-full p-3.5 bg-slate-950 rounded-xl border border-slate-800 text-white" />
            {isRegistering && (
              <select value={role} onChange={e => setRole(e.target.value)} className="w-full p-3.5 bg-slate-950 rounded-xl border border-slate-800 text-white">
                <option value="blind">Blind Learner (Audio)</option>
                <option value="deaf">Deaf Learner (Visual)</option>
              </select>
            )}
            <button type="submit" className="w-full bg-blue-600 hover:bg-blue-500 p-3.5 rounded-xl font-bold transition">
              {isRegistering ? "Register Account" : "Log In"}
            </button>
          </form>

          <button onClick={() => setIsRegistering(!isRegistering)} className="w-full mt-6 text-xs text-slate-400 hover:text-white underline text-center">
            {isRegistering ? "Already have an account? Log In" : "Need an account? Register"}
          </button>
        </div>
      </div>
    );
  }

  const isBlind = user.role === "blind";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-12">
      <div className="max-w-3xl mx-auto bg-slate-900 p-8 rounded-3xl border border-slate-800 shadow-2xl">
        <nav className="flex justify-between items-center mb-8 pb-4 border-b border-slate-800">
          <div>
            <span className="text-xl font-black text-white">Sign<span className={isBlind ? "text-blue-400" : "text-purple-400"}>Bridge</span></span>
            <span className="ml-3 text-xs bg-slate-800 px-3 py-1 rounded-full uppercase font-bold">{user.role} Mode</span>
          </div>
          <button onClick={() => setUser(null)} className="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg">Log Out</button>
        </nav>

        <h1 className={`text-2xl font-extrabold mb-2 ${isBlind ? "text-blue-400" : "text-purple-400"}`}>
          {isBlind ? "Audio Learning Assistant" : "Visual Learning Assistant"}
        </h1>
        <p className="text-slate-400 text-sm mb-6">Enter a topic to generate your tailored AI learning module.</p>

        <form onSubmit={handleGenerate} className="space-y-4">
          <input type="text" placeholder="e.g., Photosynthesis, Quantum Physics..." value={topic} onChange={e => setTopic(e.target.value)} required className="w-full p-4 bg-slate-950 rounded-xl border border-slate-800 text-white" />
          <button type="submit" disabled={loading} className={`w-full p-4 rounded-xl font-bold transition ${isBlind ? "bg-blue-600 hover:bg-blue-500" : "bg-purple-600 hover:bg-purple-500"}`}>
            {loading ? "AI is generating lesson..." : "Generate Lesson"}
          </button>
        </form>

        {lesson && (
          <div className="mt-8 p-6 bg-slate-950 rounded-2xl border border-slate-800">
            <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-800">
              <h2 className="font-bold text-lg">Module: {topic}</h2>
              {isBlind && (
                <div className="flex gap-2">
                  <button onClick={() => speak(lesson)} className="bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 rounded-lg text-xs font-bold">🔊 Read Aloud</button>
                  <button onClick={() => window.speechSynthesis.cancel()} className="bg-rose-600/20 text-rose-300 px-3 py-1.5 rounded-lg text-xs font-bold">⏹ Stop</button>
                </div>
              )}
            </div>
            <div className="text-slate-200 leading-relaxed whitespace-pre-line font-light">{lesson}</div>
          </div>
        )}

        <div className="mt-8 pt-6 border-t border-slate-800">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Your Learning History</h3>
          <ul className="space-y-2">
            {history.map((h, i) => (
              <li key={i} className="bg-slate-950/50 p-3.5 rounded-xl border border-slate-800 text-sm flex justify-between text-slate-300">
                <span>📚 <strong>{h.topic}</strong></span>
                <span className="text-xs text-slate-500">{h.created_at}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}