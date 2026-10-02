import { useEffect, useState } from 'react'
import AirWriter from './AirWriter'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || '/api'
const MODES = {
  deaf: {
    label: 'Deaf mode',
    icon: '◉',
    eyebrow: 'Visual learning assistant',
    headline: 'Make a difficult topic clear.',
    description: 'Read structured lessons at your pace, then check understanding with a visual quiz.',
  },
  blind: {
    label: 'Blind mode',
    icon: '◖',
    eyebrow: 'Audio learning assistant',
    headline: 'Learn by listening and talking it through.',
    description: 'Generate concise lessons and use speech controls with a companion or mentor.',
  },
  sign: {
    label: 'Sign / air-writing mode',
    icon: '✳',
    eyebrow: 'Air-writing studio',
    headline: 'Write a learning topic with your finger.',
    description: 'Trace a word in the air, review its text recognition, then generate a visual lesson.',
  },
}

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || 'Request failed')
  return data
}

export default function App() {
  const [user, setUser] = useState(null)
  const [username, setUsername] = useState('Guest Learner')
  const [topic, setTopic] = useState('')
  const [lesson, setLesson] = useState('')
  const [quiz, setQuiz] = useState('')
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!user) return
    let cancelled = false
    request(`/history?username=${encodeURIComponent(user.username)}`)
      .then((items) => { if (!cancelled) setHistory(items) })
      .catch(() => { if (!cancelled) setMessage('Recent lessons are unavailable right now.') })
    return () => { cancelled = true }
  }, [user])

  async function chooseMode(role) {
    const selectedUsername = username.trim() || 'Guest Learner'
    setTopic('')
    setLesson('')
    setQuiz('')
    setMessage('')
    setBusy(true)
    try {
      const profile = await request('/profile', {
        method: 'POST',
        body: JSON.stringify({ username: selectedUsername, role }),
      })
      setUser({ username: profile.username, role: profile.role })
    } catch (error) {
      setUser({ username: selectedUsername, role })
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleGenerate(event) {
    event.preventDefault()
    if (!topic.trim()) return
    setBusy(true)
    setMessage('')
    try {
      const data = await request('/generate', {
        method: 'POST',
        body: JSON.stringify({ topic, mode: user.role, username: user.username }),
      })
      setLesson(data.lesson)
      setQuiz('')
      setHistory(await request(`/history?username=${encodeURIComponent(user.username)}`))
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleAirWritingTopic(recognizedTopic) {
    if (!recognizedTopic) return
    setBusy(true)
    setMessage('')
    try {
      const data = await request('/air-writing-lesson', {
        method: 'POST',
        body: JSON.stringify({ username: user.username, topic: recognizedTopic }),
      })
      setTopic(data.topic)
      setLesson(data.lesson)
      setQuiz('')
      setHistory(await request(`/history?username=${encodeURIComponent(user.username)}`))
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleQuiz() {
    if (!lesson || !topic) return
    setBusy(true)
    setMessage('')
    try {
      const data = await request('/quiz', {
        method: 'POST',
        body: JSON.stringify({ topic, lesson, username: user.username, mode: user.role }),
      })
      setQuiz(data.quiz)
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  function speak(action) {
    if (!window.speechSynthesis) {
      setMessage('Speech controls are not supported in this browser.')
      return
    }
    if (action === 'stop') window.speechSynthesis.cancel()
    if (action === 'pause') window.speechSynthesis.pause()
    if (action === 'resume') window.speechSynthesis.resume()
    if (action === 'read' && lesson) {
      window.speechSynthesis.cancel()
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(lesson))
    }
  }

  if (!user) {
    return (
      <main className="app-shell">
        <section className="panel chooser">
          <header className="brand-lockup"><span className="brand-mark" aria-hidden="true">S</span><span>Sign<strong>Bridge</strong></span></header>
          <p className="eyebrow">Accessible learning studio</p>
          <h1>Choose how you want to learn.</h1>
          <p className="muted">Open a pathway directly. No account or password required.</p>
          <label className="profile-field">Display name<input value={username} onChange={(event) => setUsername(event.target.value)} maxLength={80} /></label>
          <div className="mode-grid" aria-label="Learning pathways">
            {Object.entries(MODES).map(([role, mode]) => (
              <button className={`mode-card mode-card-${role}`} key={role} onClick={() => chooseMode(role)} disabled={busy}>
                <span className="mode-icon" aria-hidden="true">{mode.icon}</span>
                <strong>{mode.label}</strong>
                <span className="mode-description">{mode.description}</span>
              </button>
            ))}
          </div>
        </section>
      </main>
    )
  }

  const mode = MODES[user.role]
  return (
    <main className={`app-shell mode-${user.role}`}>
      <section className="panel dashboard">
        <header className="topbar">
          <div className="brand-lockup"><span className="brand-mark" aria-hidden="true">S</span><span>Sign<strong>Bridge</strong></span><small>{mode.label}</small></div>
          <div className="account"><span>{user.username}</span><button className="secondary" onClick={() => setUser(null)}>Change pathway</button></div>
        </header>
        <div className="mode-intro">
          <p className="eyebrow">{mode.eyebrow}</p>
          <h1>{mode.headline}</h1>
          <p className="muted">{mode.description}</p>
        </div>
        {message && <p className="notice" role="status">{message}</p>}
        {user.role === 'blind' && <section className="companion-tools" aria-label="Companion and mentor speech controls">
          <div><h2>Companion controls</h2><p className="muted">Read, pause, continue, or stop the current lesson together.</p></div>
          <div className="speech-controls">
            <button className="secondary" onClick={() => speak('read')} disabled={!lesson}>Read lesson</button>
            <button className="secondary" onClick={() => speak('pause')}>Pause</button>
            <button className="secondary" onClick={() => speak('resume')}>Continue</button>
            <button className="secondary" onClick={() => speak('stop')}>Stop</button>
          </div>
        </section>}
        {user.role === 'sign' && <AirWriter busy={busy} onGenerateTopic={handleAirWritingTopic} />}
        {user.role !== 'sign' && <form onSubmit={handleGenerate} className="topic-form">
          <label htmlFor="topic-input">{user.role === 'sign' ? 'Or enter a topic' : 'Learning topic'}</label>
          <div className="topic-controls"><input id="topic-input" value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="Try photosynthesis or gravity" maxLength={200} required /><button className="primary" disabled={busy}>{busy ? 'Generating...' : 'Generate lesson'}</button></div>
        </form>}
        {lesson && <article className="lesson">
          <div className="lesson-heading"><div><p className="eyebrow">Lesson</p><h2>{topic}</h2></div>{user.role !== 'blind' && <button className="secondary" onClick={handleQuiz} disabled={busy}>{busy ? 'Preparing...' : 'Generate quiz'}</button>}</div>
          {user.role === 'blind' && <button className="secondary quiz-trigger" onClick={handleQuiz} disabled={busy}>{busy ? 'Preparing...' : 'Generate quiz'}</button>}
          <div className="lesson-content">{lesson}</div>
          {user.role === 'blind' && <p className="muted mentor-prompt">Companion prompt: ask what part to repeat, then use Continue when ready.</p>}
          {quiz && <section className="quiz-result"><h3>Knowledge check</h3><div>{quiz}</div></section>}
        </article>}
        <section className="history"><div className="section-heading"><h2>Recent lessons</h2><span>{history.length}</span></div>{history.length ? <ul>{history.map((item) => <li key={`${item.id}-${item.topic}`}><strong>{item.topic}</strong><time>{item.created_at}</time></li>)}</ul> : <p className="muted">Generated lessons will appear here.</p>}</section>
      </section>
    </main>
  )
}
