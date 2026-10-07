import { useEffect, useState } from 'react'
import AirWriter from './AirWriter'
import BlindChat from './BlindChat'
import BlindQuiz from './BlindQuiz'
import DeafQuiz from './DeafQuiz'
import LiveGestureCamera from './LiveGestureCamera'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || '/api'
const MODES = {
  deaf: {
    label: 'Deaf mode',
    icon: '◉',
    eyebrow: 'Visual learning assistant',
    headline: 'Visual Lessons & Interactive Quizzes',
    description: 'Read structured visual lessons at your pace, then test understanding with adaptive 5-question MCQs.',
  },
  blind: {
    label: 'Blind mode',
    icon: '◖',
    eyebrow: 'Groq Voice Assistant & Audio Learning',
    headline: 'Continuous Voice Mentor & Audio Lessons',
    description: 'Talk continuously with your AI voice mentor powered by Groq API, or generate audio lessons with real-time audio quiz.',
  },
  sign: {
    label: 'Sign / air-writing mode',
    icon: '✳',
    eyebrow: 'Air-writing studio',
    headline: 'Air-Writing & Gesture Recognition',
    description: 'Trace words in the air using finger gesture tracking, recognize text, and generate interactive visual lessons.',
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
  const [blindTab, setBlindTab] = useState('chat') // 'chat' or 'lesson'
  const [showBlindQuiz, setShowBlindQuiz] = useState(false)
  const [showDeafQuiz, setShowDeafQuiz] = useState(false)

  // MANDATORY: Instantly scroll window to top whenever mode changes or user switches views
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  }, [user?.role, user])

  useEffect(() => {
    if (!user) return
    let cancelled = false
    request(`/history?username=${encodeURIComponent(user.username)}`)
      .then((items) => { if (!cancelled) setHistory(items) })
      .catch(() => { if (!cancelled) setMessage('Recent lessons are unavailable right now.') })
    return () => { cancelled = true }
  }, [user])

  async function chooseMode(role) {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
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
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
    }
  }

  function handleBackToChooser() {
    setUser(null)
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  }

  async function handleGenerate(event) {
    event.preventDefault()
    if (!topic.trim()) return
    setBusy(true)
    setMessage('')
    setQuiz('')
    setShowBlindQuiz(false)
    setShowDeafQuiz(false)
    try {
      const data = await request('/generate', {
        method: 'POST',
        body: JSON.stringify({ topic, mode: user.role, username: user.username }),
      })
      setLesson(data.lesson)
      if (data.quiz) {
        setQuiz(data.quiz)
      } else {
        const quizData = await request('/quiz', {
          method: 'POST',
          body: JSON.stringify({ topic, lesson: data.lesson, username: user.username, mode: user.role }),
        }).catch(() => ({}))
        if (quizData.quiz) setQuiz(quizData.quiz)
      }
      setHistory(await request(`/history?username=${encodeURIComponent(user.username)}`))

      if (user.role === 'blind') {
        setShowBlindQuiz(true)
        if (window.speechSynthesis) {
          speakSummaryWithAutoQuiz(data.lesson)
        }
      }
      if (user.role === 'deaf') {
        setShowDeafQuiz(true)
      }
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
      if (data.quiz) {
        setQuiz(data.quiz)
      } else {
        const quizData = await request('/quiz', {
          method: 'POST',
          body: JSON.stringify({ topic: data.topic, lesson: data.lesson, username: user.username, mode: user.role }),
        }).catch(() => ({}))
        if (quizData.quiz) setQuiz(quizData.quiz)
      }
      setHistory(await request(`/history?username=${encodeURIComponent(user.username)}`))
      if (user.role === 'deaf') {
        setShowDeafQuiz(true)
      }
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  function speakSummaryWithAutoQuiz(lessonText) {
    if (!window.speechSynthesis) {
      setShowBlindQuiz(true)
      return
    }
    window.speechSynthesis.cancel()

    const sentences = lessonText.match(/[^.!?]+[.!?]+/g) || [lessonText]
    let index = 0

    function speakNextChunk() {
      if (index >= sentences.length) {
        const introUtterance = new SpeechSynthesisUtterance("Audio summary complete. Starting your real-time audio quiz now.")
        introUtterance.onend = () => setShowBlindQuiz(true)
        introUtterance.onerror = () => setShowBlindQuiz(true)
        window.speechSynthesis.speak(introUtterance)
        return
      }

      const chunk = sentences[index].trim()
      if (!chunk) {
        index++
        speakNextChunk()
        return
      }

      const utterance = new SpeechSynthesisUtterance(chunk)
      utterance.rate = 1.0
      utterance.pitch = 1.0
      utterance.onend = () => { index++; speakNextChunk() }
      utterance.onerror = () => { index++; speakNextChunk() }
      window.speechSynthesis.speak(utterance)
    }

    speakNextChunk()
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
      speakSummaryWithAutoQuiz(lesson)
    }
  }

  // ---------------------------------------------------------------------------
  // PAGE 1: MODE SELECTOR & GESTURE CAMERA LAUNCHER
  // ---------------------------------------------------------------------------
  if (!user) {
    return (
      <main className="app-shell">
        <section className="panel chooser">
          <header className="brand-lockup">
            <span className="brand-mark" aria-hidden="true">S</span>
            <span>Sign<strong>Bridge</strong></span>
          </header>
          <p className="eyebrow">Accessible gesture learning studio</p>
          <h1>Choose your mode with hand gestures.</h1>
          <p className="muted">
            Show a hand gesture to the webcam below to immediately jump into a dedicated mode page (no scrolling required), or click a button manually.
          </p>

          <label className="profile-field">
            Display name
            <input value={username} onChange={(event) => setUsername(event.target.value)} maxLength={80} />
          </label>

          {/* LIVE HAND GESTURE CAMERA */}
          <LiveGestureCamera activeMode={null} onSwitchMode={(targetRole) => chooseMode(targetRole)} autoStart={true} />

          {/* MANUAL FALLBACK PILLS */}
          <div className="manual-mode-bar">
            <span className="muted">Or click to launch dedicated page:</span>
            <div className="manual-mode-pills">
              {Object.entries(MODES).map(([role, m]) => (
                <button className="secondary manual-mode-btn" key={role} onClick={() => chooseMode(role)} disabled={busy}>
                  <span>{m.icon}</span> {m.label}
                </button>
              ))}
            </div>
          </div>
        </section>
      </main>
    )
  }

  // ---------------------------------------------------------------------------
  // PAGE 2: SEPARATE MODE SPECIFIC PAGES
  // ---------------------------------------------------------------------------
  const mode = MODES[user.role]

  return (
    <main className={`app-shell mode-${user.role} separate-mode-page`}>
      <section className="panel dashboard mode-page-container">

        {/* STANDALONE PAGE HEADER */}
        <header className="topbar mode-header">
          <div className="brand-lockup">
            <span className="brand-mark" aria-hidden="true">S</span>
            <span>Sign<strong>Bridge</strong></span>
            <span className="mode-badge-pill">{mode.label}</span>
          </div>

          <div className="account">
            <span className="user-name-tag">{user.username}</span>
            <button className="primary back-switcher-btn" onClick={handleBackToChooser}>
              🎥 Back to Gesture Switcher
            </button>
          </div>
        </header>

        {/* MODE BANNER */}
        <div className="mode-intro">
          <p className="eyebrow">{mode.eyebrow}</p>
          <h1>{mode.headline}</h1>
          <p className="muted">{mode.description}</p>
        </div>

        {message && <p className="notice" role="status">{message}</p>}

        {/* =================================================================== */}
        {/* SEPARATE PAGE SPECIFIC CONTENT FOR DEAF MODE                       */}
        {/* =================================================================== */}
        {user.role === 'deaf' && (
          <div className="deaf-mode-page-view">
            <form onSubmit={handleGenerate} className="topic-form">
              <label htmlFor="topic-input">Visual Learning Topic</label>
              <div className="topic-controls">
                <input
                  id="topic-input"
                  value={topic}
                  onChange={(event) => setTopic(event.target.value)}
                  placeholder="Enter any topic e.g. Photosynthesis, Newton's Laws, Solar System"
                  maxLength={200}
                  required
                />
                <button className="primary" disabled={busy}>{busy ? 'Generating Visual Lesson...' : 'Generate Lesson'}</button>
              </div>
            </form>

            {lesson && (
              <article className="lesson">
                <div className="lesson-heading">
                  <div>
                    <p className="eyebrow">Visual Structured Lesson</p>
                    <h2>{topic}</h2>
                  </div>
                  <button className="primary quiz-trigger deaf-trigger-bg" onClick={() => setShowDeafQuiz(true)}>
                    🧠 Start Adaptive 5-Question Quiz
                  </button>
                </div>
                <div className="lesson-content">{lesson}</div>

                <div className="deaf-quiz-prompt-bar">
                  <p className="muted mentor-prompt">Ready to test your visual comprehension? Track your progress with an adaptive 5-MCQ quiz!</p>
                  <button className="primary quiz-trigger-large deaf-trigger-bg" onClick={() => setShowDeafQuiz(true)}>
                    🧠 Take Real-time Visual Quiz (5 Questions)
                  </button>
                </div>
              </article>
            )}

            {showDeafQuiz && lesson && (
              <DeafQuiz
                topic={topic}
                summary={lesson}
                username={user.username}
                request={request}
                onClose={() => setShowDeafQuiz(false)}
              />
            )}
          </div>
        )}

        {/* =================================================================== */}
        {/* SEPARATE PAGE SPECIFIC CONTENT FOR BLIND MODE                      */}
        {/* =================================================================== */}
        {user.role === 'blind' && (
          <div className="blind-mode-page-view">
            <div className="blind-nav-tabs">
              <button
                className={`blind-tab-btn ${blindTab === 'chat' ? 'active' : ''}`}
                onClick={() => setBlindTab('chat')}
              >
                🎙️ Continuous Voice Conversation (Groq API)
              </button>
              <button
                className={`blind-tab-btn ${blindTab === 'lesson' ? 'active' : ''}`}
                onClick={() => setBlindTab('lesson')}
              >
                📖 Audio Lesson Generator & Audio Quiz
              </button>
            </div>

            {blindTab === 'chat' ? (
              <BlindChat
                username={user.username}
                request={request}
                onStartQuiz={(t, s) => {
                  setTopic(t || 'Voice Session Topic')
                  setLesson(s)
                  setShowBlindQuiz(true)
                }}
              />
            ) : (
              <div className="blind-lesson-subview">
                <section className="companion-tools" aria-label="Companion and mentor speech controls">
                  <div>
                    <h2>Voice Companion Controls</h2>
                    <p className="muted">Read, pause, continue, or stop the audio lesson.</p>
                  </div>
                  <div className="speech-controls">
                    <button className="secondary" onClick={() => speak('read')} disabled={!lesson}>Read Lesson</button>
                    <button className="secondary" onClick={() => speak('pause')}>Pause</button>
                    <button className="secondary" onClick={() => speak('resume')}>Continue</button>
                    <button className="secondary" onClick={() => speak('stop')}>Stop</button>
                  </div>
                </section>

                <form onSubmit={handleGenerate} className="topic-form">
                  <label htmlFor="topic-input">Audio Learning Topic</label>
                  <div className="topic-controls">
                    <input
                      id="topic-input"
                      value={topic}
                      onChange={(event) => setTopic(event.target.value)}
                      placeholder="e.g. Black Holes, Human Heart, Ecosystems"
                      maxLength={200}
                      required
                    />
                    <button className="primary" disabled={busy}>{busy ? 'Generating Audio Lesson...' : 'Generate Audio Lesson'}</button>
                  </div>
                </form>

                {lesson && (
                  <article className="lesson">
                    <div className="lesson-heading">
                      <div>
                        <p className="eyebrow">Audio Summary</p>
                        <h2>{topic}</h2>
                      </div>
                      <button className="primary quiz-trigger" onClick={() => setShowBlindQuiz(true)}>
                        🧠 Start Voice Audio Quiz (5 Questions)
                      </button>
                    </div>
                    <div className="lesson-content">{lesson}</div>

                    <div className="blind-quiz-prompt-bar">
                      <p className="muted mentor-prompt">Finished listening? Test your comprehension with a interactive 5-question voice quiz!</p>
                      <button className="primary quiz-trigger-large" onClick={() => setShowBlindQuiz(true)}>
                        🎙️ Take Audio Quiz (Say 1 of 4 options)
                      </button>
                    </div>
                  </article>
                )}
              </div>
            )}

            {showBlindQuiz && lesson && (
              <BlindQuiz
                topic={topic}
                summary={lesson}
                username={user.username}
                request={request}
                onClose={() => setShowBlindQuiz(false)}
              />
            )}
          </div>
        )}

        {/* =================================================================== */}
        {/* SEPARATE PAGE SPECIFIC CONTENT FOR SIGN / AIR-WRITING MODE        */}
        {/* =================================================================== */}
        {user.role === 'sign' && (
          <div className="sign-mode-page-view">
            {/* AIRWRITER CANVAS AT TOP OF PAGE */}
            <AirWriter busy={busy} onGenerateTopic={handleAirWritingTopic} />

            {lesson && (
              <article className="lesson">
                <div className="lesson-heading">
                  <div>
                    <p className="eyebrow">Recognized Topic Lesson</p>
                    <h2>{topic}</h2>
                  </div>
                </div>
                <div className="lesson-content">{lesson}</div>
                {quiz && (
                  <section className="quiz-result">
                    <h3>Knowledge check</h3>
                    <div>{quiz}</div>
                  </section>
                )}
              </article>
            )}
          </div>
        )}

        {/* RECENT HISTORY DRAWER / FOOTER */}
        <section className="history compact-history">
          <div className="section-heading">
            <h2>Recent lessons ({history.length})</h2>
          </div>
          {history.length ? (
            <ul>
              {history.map((item) => (
                <li key={`${item.id}-${item.topic}`}>
                  <strong>{item.topic}</strong>
                  <time>{item.created_at}</time>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Generated lessons will appear here.</p>
          )}
        </section>

      </section>
    </main>
  )
}

