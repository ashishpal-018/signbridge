import { useEffect, useState } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || '/api'

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
  const [registering, setRegistering] = useState(false)
  const [credentials, setCredentials] = useState({ username: '', password: '', role: 'blind' })
  const [topic, setTopic] = useState('')
  const [lesson, setLesson] = useState('')
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!user) return
    request('/history').then(setHistory).catch(() => setMessage('Your session has expired. Please log in again.'))
  }, [user])

  async function handleAuth(event) {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    try {
      const data = await request(registering ? '/register' : '/login', {
        method: 'POST',
        body: JSON.stringify(credentials),
      })
      if (registering) {
        setRegistering(false)
        setMessage(data.message)
      } else {
        setUser({ username: data.username, role: data.role })
        setCredentials((current) => ({ ...current, password: '' }))
      }
    } catch (error) {
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
        body: JSON.stringify({ topic, mode: user.role }),
      })
      setLesson(data.lesson)
      setHistory(await request('/history'))
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  if (!user) {
    return (
      <main className="auth-shell">
        <section className="panel auth-panel">
          <p className="eyebrow">Accessible learning studio</p>
          <h1>Sign<span>Bridge</span></h1>
          <p className="muted">Short, useful lessons shaped for the way you learn.</p>
          {message && <p className="notice" role="status">{message}</p>}
          <form onSubmit={handleAuth} className="form-stack">
            <label>Username<input value={credentials.username} onChange={(event) => setCredentials({ ...credentials, username: event.target.value })} required /></label>
            <label>Password<input type="password" value={credentials.password} onChange={(event) => setCredentials({ ...credentials, password: event.target.value })} minLength={8} required /></label>
            {registering && <label>Learning mode<select value={credentials.role} onChange={(event) => setCredentials({ ...credentials, role: event.target.value })}><option value="blind">Blind learner</option><option value="deaf">Deaf learner</option></select></label>}
            <button className="primary" disabled={busy}>{busy ? 'Working...' : registering ? 'Create account' : 'Log in'}</button>
          </form>
          <button className="link-button" onClick={() => { setRegistering(!registering); setMessage('') }}>
            {registering ? 'Already have an account? Log in' : 'Need an account? Create one'}
          </button>
        </section>
      </main>
    )
  }

  const blind = user.role === 'blind'
  return (
    <main className="app-shell">
      <section className="panel dashboard">
        <header className="topbar"><div><strong>Sign<span>Bridge</span></strong><small>{blind ? 'Audio mode' : 'Visual mode'}</small></div><div className="account">{user.username}<button className="secondary" onClick={() => setUser(null)}>Log out</button></div></header>
        <p className="eyebrow">{blind ? 'Audio learning assistant' : 'Visual learning assistant'}</p>
        <h1>{blind ? 'Make a difficult topic easier to hear.' : 'Turn a difficult topic into a clear module.'}</h1>
        <p className="muted">Enter a subject and the local AI will prepare a focused lesson.</p>
        {message && <p className="notice" role="status">{message}</p>}
        <form onSubmit={handleGenerate} className="topic-form"><input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="Try photosynthesis or gravity" maxLength={200} required /><button className="primary" disabled={busy}>{busy ? 'Generating...' : 'Generate lesson'}</button></form>
        {lesson && <article className="lesson"><div className="lesson-heading"><h2>{topic}</h2>{blind && <button className="secondary" onClick={() => window.speechSynthesis.speak(new SpeechSynthesisUtterance(lesson))}>Read aloud</button>}</div><p>{lesson}</p></article>}
        <section className="history"><h2>Recent lessons</h2>{history.length ? <ul>{history.map((item) => <li key={`${item.created_at}-${item.topic}`}><strong>{item.topic}</strong><time>{item.created_at}</time></li>)}</ul> : <p className="muted">Your generated lessons will appear here.</p>}</section>
      </section>
    </main>
  )
}
