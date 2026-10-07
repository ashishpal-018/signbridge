import { useState, useEffect, useRef } from 'react'

export default function BlindChat({ username, request, onStartQuiz }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I am your AI voice mentor. What subject or question would you like to explore today? You can speak to me directly or type your response.",
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [continuousMode, setContinuousMode] = useState(true)
  const [provider, setProvider] = useState('groq')
  const [speechSupported, setSpeechSupported] = useState(true)
  const [statusText, setStatusText] = useState('')

  const recognitionRef = useRef(null)
  const synthRef = useRef(window.speechSynthesis)
  const chatEndRef = useRef(null)

  // Initialize SpeechRecognition if available
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setSpeechSupported(false)
      setStatusText('Speech recognition is not supported in this browser. You can still type messages below.')
      return
    }

    const rec = new SpeechRecognition()
    rec.continuous = false
    rec.interimResults = false
    rec.lang = 'en-US'

    rec.onstart = () => {
      setIsListening(true)
      setStatusText('Listening... Speak clearly into your microphone.')
    }

    rec.onresult = (event) => {
      const transcript = event.results[0][0].transcript
      setIsListening(false)
      setStatusText(`Recognized: "${transcript}"`)
      if (transcript.trim()) {
        handleSendMessage(transcript.trim())
      }
    }

    rec.onerror = (event) => {
      setIsListening(false)
      if (event.error === 'no-speech') {
        setStatusText('No speech detected. Tap "Speak Now" when ready.')
      } else if (event.error === 'not-allowed') {
        setStatusText('Microphone access was denied. Please allow microphone permissions in browser settings.')
      } else {
        setStatusText(`Voice recognition notice: ${event.error}`)
      }
    }

    rec.onend = () => {
      setIsListening(false)
    }

    recognitionRef.current = rec
  }, [])

  // Auto-scroll transcript
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  function speakText(text, onComplete) {
    if (!synthRef.current) return
    synthRef.current.cancel()

    const sentences = text.match(/[^.!?]+[.!?]+/g) || [text]
    let index = 0

    function speakNextChunk() {
      if (index >= sentences.length) {
        setIsSpeaking(false)
        setStatusText('Response finished.')
        if (onComplete) onComplete()
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

      utterance.onstart = () => {
        setIsSpeaking(true)
        setStatusText('AI Voice Mentor is speaking...')
      }

      utterance.onend = () => {
        index++
        speakNextChunk()
      }

      utterance.onerror = () => {
        index++
        speakNextChunk()
      }

      synthRef.current.speak(utterance)
    }

    speakNextChunk()
  }

  function stopSpeech() {
    if (synthRef.current) {
      synthRef.current.cancel()
      setIsSpeaking(false)
      setStatusText('Speech stopped.')
    }
  }

  function startListening() {
    stopSpeech()
    if (recognitionRef.current) {
      try {
        recognitionRef.current.start()
      } catch (err) {
        // Recognition might already be running
      }
    }
  }

  function stopListening() {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      setIsListening(false)
      setStatusText('Voice listening stopped.')
    }
  }

  async function handleSendMessage(textToSend) {
    if (!textToSend || loading) return

    stopSpeech()
    const userMsg = { role: 'user', content: textToSend }
    const updatedMessages = [...messages, userMsg]
    setMessages(updatedMessages)
    setInput('')
    setLoading(true)
    setStatusText('Thinking...')

    try {
      const payloadMessages = updatedMessages.map((m) => ({ role: m.role, content: m.content }))
      const res = await request('/blind/chat', {
        method: 'POST',
        body: JSON.stringify({
          username: username || 'Guest Learner',
          messages: payloadMessages,
          mode: 'blind',
        }),
      })

      const aiMsg = { role: 'assistant', content: res.reply }
      setMessages([...updatedMessages, aiMsg])
      setProvider(res.provider || 'groq')

      // Auto-speak 500+ word response and trigger next turn if continuous mode is enabled
      speakText(res.reply, () => {
        if (continuousMode && speechSupported) {
          setTimeout(() => {
            startListening()
          }, 600)
        }
      })
    } catch (err) {
      setStatusText(`Error: ${err.message || 'Failed to get response'}`)
    } finally {
      setLoading(false)
    }
  }

  function handleFormSubmit(e) {
    e.preventDefault()
    if (input.trim()) {
      handleSendMessage(input.trim())
    }
  }

  function clearChat() {
    stopSpeech()
    stopListening()
    setMessages([
      {
        role: 'assistant',
        content: 'Conversation reset. What would you like to discuss next?',
      },
    ])
    setStatusText('Conversation cleared.')
  }

  return (
    <div className="blind-chat-container">
      {/* Top Header & Provider Info */}
      <div className="blind-chat-header">
        <div>
          <h2 className="blind-chat-title">🎙️ Continuous Voice Conversation</h2>
          <p className="muted">Hands-free voice dialog powered by high-speed Groq LLM inference.</p>
        </div>
        <div className="provider-badge">
          <span className="badge-groq">⚡ Groq API (Ultra-Fast Cloud LLM)</span>
        </div>
      </div>

      {/* Primary Voice Action Bar */}
      <div className="voice-controls-panel">
        <div className="voice-main-action">
          {!isListening ? (
            <button
              className="primary voice-talk-btn"
              onClick={startListening}
              disabled={loading}
              aria-label="Start speaking to AI assistant"
            >
              🎙️ {isSpeaking ? 'Interrupt & Speak' : 'Speak to Assistant'}
            </button>
          ) : (
            <button
              className="voice-stop-btn pulse-listening"
              onClick={stopListening}
              aria-label="Stop microphone listening"
            >
              🔴 Listening... (Tap to stop)
            </button>
          )}

          {isSpeaking && (
            <button className="secondary" onClick={stopSpeech} aria-label="Stop AI speech playback">
              ⏹️ Stop Speaking
            </button>
          )}
        </div>

        <div className="voice-toggles">
          <label className="toggle-label" title="Automatically re-open mic when AI finishes speaking">
            <input
              type="checkbox"
              checked={continuousMode}
              onChange={(e) => setContinuousMode(e.target.checked)}
            />
            <span>🔄 Continuous Loop ({continuousMode ? 'ON' : 'OFF'})</span>
          </label>
          <button className="secondary-sm" onClick={clearChat}>
            🧹 Reset Chat
          </button>
        </div>
      </div>

      {/* Live Audio Status */}
      {statusText && <div className="audio-status-banner" role="status">{statusText}</div>}

      {/* Messages Transcript */}
      <div className="transcript-box" aria-live="polite" aria-label="Conversation Transcript">
        {messages.map((msg, index) => (
          <div key={index} className={`chat-bubble-row bubble-${msg.role}`}>
            <div className="chat-bubble">
              <div className="bubble-header">
                <strong>{msg.role === 'user' ? 'You' : 'AI Voice Mentor'}</strong>
                {msg.role === 'assistant' && (
                  <button
                    className="replay-btn"
                    onClick={() => speakText(msg.content)}
                    title="Replay speech"
                    aria-label="Replay this response"
                  >
                    🔊 Play
                  </button>
                )}
              </div>
              <p className="bubble-text">{msg.content}</p>
              {msg.role === 'assistant' && index > 0 && onStartQuiz && (
                <button
                  className="secondary-sm"
                  onClick={() => onStartQuiz('Voice Conversation Topic', msg.content)}
                  style={{ marginTop: '10px', width: '100%', cursor: 'pointer' }}
                  title="Take a 5-question real-time audio quiz based on this response"
                  aria-label="Take a 5-question real-time audio quiz based on this response"
                >
                  🧠 Take Real-Time Audio Quiz (5 Questions)
                </button>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-bubble-row bubble-assistant">
            <div className="chat-bubble loading-bubble">
              <span className="dot-flashing">AI is thinking...</span>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Text Fallback Form */}
      <form onSubmit={handleFormSubmit} className="chat-input-form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={speechSupported ? "Type a message or use speech..." : "Type your message..."}
          disabled={loading}
          maxLength={500}
        />
        <button type="submit" className="primary" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
