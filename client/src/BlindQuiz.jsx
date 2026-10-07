import { useState, useEffect, useRef } from 'react'

export default function BlindQuiz({ topic, summary, username, request, onClose }) {
  const [questions, setQuestions] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [userAnswers, setUserAnswers] = useState([])
  const [score, setScore] = useState(0)
  const [quizStage, setQuizStage] = useState('loading') // 'loading' | 'active' | 'answered' | 'completed' | 'error'
  const [selectedOption, setSelectedOption] = useState(null)
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [statusText, setStatusText] = useState('Generating 5-question audio quiz from your lesson...')
  const [badgeEarned, setBadgeEarned] = useState(null)
  const [speechSupported, setSpeechSupported] = useState(true)

  // Real-time metrics
  const [qStartTime, setQStartTime] = useState(Date.now())
  const [timeSpentSeconds, setTimeSpentSeconds] = useState(0)
  const [quizStartMs] = useState(Date.now())
  const [totalTimeTaken, setTotalTimeTaken] = useState(0)

  const recognitionRef = useRef(null)
  const synthRef = useRef(window.speechSynthesis)
  const isComponentMounted = useRef(true)

  // Timer tick for live question duration
  useEffect(() => {
    let timerInterval = null
    if (quizStage === 'active') {
      timerInterval = setInterval(() => {
        setTimeSpentSeconds(Math.floor((Date.now() - qStartTime) / 1000))
      }, 1000)
    }
    return () => {
      if (timerInterval) clearInterval(timerInterval)
    }
  }, [quizStage, qStartTime])

  // Fetch structured 5-question blind audio quiz on mount
  useEffect(() => {
    isComponentMounted.current = true
    let isCancelled = false

    async function fetchQuiz() {
      try {
        setStatusText('Analyzing lesson summary to generate 5 real-time audio questions...')
        const data = await request('/blind/quiz', {
          method: 'POST',
          body: JSON.stringify({ topic, summary, username }),
        })

        if (isCancelled || !isComponentMounted.current) return

        if (data.questions && data.questions.length > 0) {
          setQuestions(data.questions)
          setQuizStage('active')
          setQStartTime(Date.now())
          setTimeSpentSeconds(0)
          setStatusText('Quiz loaded! Preparing to read Question 1 of 5...')
        } else {
          setQuizStage('error')
          setStatusText('Failed to generate 5-question audio quiz. Please try again.')
        }
      } catch (err) {
        if (isCancelled || !isComponentMounted.current) return
        setQuizStage('error')
        setStatusText(`Error creating quiz: ${err.message || 'Unknown error'}`)
      }
    }

    fetchQuiz()

    return () => {
      isCancelled = true
      isComponentMounted.current = false
      if (synthRef.current) synthRef.current.cancel()
      if (recognitionRef.current) {
        try { recognitionRef.current.stop() } catch (e) {}
      }
    }
  }, [topic, summary, username, request])

  // Setup SpeechRecognition engine
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setSpeechSupported(false)
      return
    }

    const rec = new SpeechRecognition()
    rec.continuous = false
    rec.interimResults = false
    rec.lang = 'en-US'

    rec.onstart = () => {
      setIsListening(true)
      setStatusText(`🎙️ Listening for Question ${currentIndex + 1}... Say Option 1, Option 2, Option 3, or Option 4 clearly.`)
    }

    rec.onresult = (event) => {
      const transcript = (event.results[0][0].transcript || '').toLowerCase().trim()
      setIsListening(false)
      setStatusText(`Recognized voice: "${transcript}"`)
      parseSpokenAnswer(transcript)
    }

    rec.onerror = (event) => {
      setIsListening(false)
      if (event.error === 'no-speech') {
        setStatusText('No speech detected. Tap "Speak Answer" to try again.')
      } else if (event.error === 'not-allowed') {
        setStatusText('Microphone access denied. You can tap options manually.')
      } else {
        setStatusText(`Voice input error: ${event.error}`)
      }
    }

    rec.onend = () => {
      setIsListening(false)
    }

    recognitionRef.current = rec
  }, [questions, currentIndex, quizStage])

  // Automatically narrate Question 1, Question 2, etc. when active question index changes
  useEffect(() => {
    if (quizStage === 'active' && questions.length > 0 && questions[currentIndex]) {
      speakQuestionAndOptions(currentIndex)
    }
  }, [currentIndex, quizStage, questions])

  function speakText(text, onComplete) {
    if (!synthRef.current) return
    synthRef.current.cancel()

    const sentences = text.match(/[^.!?]+[.!?]+/g) || [text]
    let index = 0

    function speakNextChunk() {
      if (index >= sentences.length) {
        setIsSpeaking(false)
        if (onComplete && isComponentMounted.current) {
          onComplete()
        }
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
    }
    stopListening()
  }

  function startListening() {
    stopSpeech()
    if (recognitionRef.current) {
      try {
        recognitionRef.current.start()
      } catch (err) {
        // Recognition already running or starting
      }
    }
  }

  function stopListening() {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch (e) {}
      setIsListening(false)
    }
  }

  // Reads Question N and 4 Options aloud, then AUTOMATICALLY activates listening for learner's voice answer
  function speakQuestionAndOptions(index) {
    const q = questions[index]
    if (!q) return

    stopSpeech()
    setSelectedOption(null)
    setQStartTime(Date.now())
    setTimeSpentSeconds(0)

    const questionNarration = `Question ${index + 1} of ${questions.length}: ${q.question}. Option 1: ${q.options[0]}. Option 2: ${q.options[1]}. Option 3: ${q.options[2]}. Option 4: ${q.options[3]}. Please speak your choice now: Option 1, Option 2, Option 3, or Option 4.`

    setStatusText(`🔊 Reading Question ${index + 1} of ${questions.length} and 4 options...`)

    // Crucial requirement: Learner responds IMMEDIATELY after hearing Question N narration
    speakText(questionNarration, () => {
      if (speechSupported && isComponentMounted.current) {
        setTimeout(() => {
          if (isComponentMounted.current && quizStage === 'active') {
            startListening()
          }
        }, 300)
      } else {
        setStatusText('Select your answer by speaking into microphone or tapping Option 1, 2, 3, or 4.')
      }
    })
  }

  function parseSpokenAnswer(transcript) {
    if (quizStage === 'completed') {
      if (/\b(retake|restart|again|try again)\b/i.test(transcript)) {
        restartQuiz()
        return
      }
      if (/\b(exit|close|back|done|return)\b/i.test(transcript)) {
        stopSpeech()
        onClose()
        return
      }
    }

    if (quizStage !== 'active' || !questions[currentIndex]) return

    const currentOptions = questions[currentIndex].options
    let matchedIndex = -1

    if (/\b(one|1|first|option 1|option a|option one|choice 1|choice a|^1$|^a$)\b/i.test(transcript)) {
      matchedIndex = 0
    } else if (/\b(two|to|too|2|second|option 2|option b|option two|choice 2|choice b|^2$|^b$)\b/i.test(transcript)) {
      matchedIndex = 1
    } else if (/\b(three|tree|3|third|option 3|option c|option three|choice 3|choice c|^3$|^c$)\b/i.test(transcript)) {
      matchedIndex = 2
    } else if (/\b(four|for|fore|4|fourth|option 4|option d|option four|choice 4|choice d|^4$|^d$)\b/i.test(transcript)) {
      matchedIndex = 3
    } else {
      for (let i = 0; i < currentOptions.length; i++) {
        const optLower = currentOptions[i].toLowerCase()
        if (transcript.length > 2 && (transcript.includes(optLower) || optLower.includes(transcript))) {
          matchedIndex = i
          break
        }
      }
    }

    if (matchedIndex >= 0 && matchedIndex < 4) {
      handleOptionChoice(matchedIndex, true)
    } else {
      const retryMessage = `I heard "${transcript}", but couldn't match Option 1, 2, 3, or 4. Please say Option 1, Option 2, Option 3, or Option 4.`
      setStatusText(`⚠️ ${retryMessage}`)
      speakText(retryMessage, () => {
        setTimeout(() => {
          if (isComponentMounted.current && quizStage === 'active') startListening()
        }, 300)
      })
    }
  }

  function handleNextQuestion() {
    stopSpeech()
    stopListening()
    if (currentIndex < questions.length - 1) {
      const nextIdx = currentIndex + 1
      setCurrentIndex(nextIdx)
      setSelectedOption(null)
      setQuizStage('active')
      setQStartTime(Date.now())
      setTimeSpentSeconds(0)
    } else {
      finishQuiz(score, userAnswers)
    }
  }

  // Answer handler: speaks feedback, then AUTOMATICALLY proceeds to Question N+1
  async function handleOptionChoice(optionIndex) {
    if (quizStage !== 'active' || !questions[currentIndex]) return

    stopSpeech()
    stopListening()
    setSelectedOption(optionIndex)
    setQuizStage('answered')

    const currentQ = questions[currentIndex]
    const isCorrect = optionIndex === currentQ.correct_index
    const duration = Math.floor((Date.now() - qStartTime) / 1000)

    const newAnswers = [...userAnswers, { questionId: currentQ.id, selected: optionIndex, isCorrect, timeSeconds: duration, questionText: currentQ.question }]
    setUserAnswers(newAnswers)

    let updatedScore = score
    if (isCorrect) {
      updatedScore = score + 1
      setScore(updatedScore)
    }

    let feedbackText = ''
    if (isCorrect) {
      feedbackText = `Correct! Option ${optionIndex + 1} is the right answer. ${currentQ.explanation || ''}`
    } else {
      feedbackText = `Incorrect. You chose Option ${optionIndex + 1}. The correct answer is Option ${currentQ.correct_index + 1}: ${currentQ.options[currentQ.correct_index]}. ${currentQ.explanation || ''}`
    }

    setStatusText(isCorrect ? `✅ ${feedbackText}` : `❌ ${feedbackText}`)

    // Speak immediate feedback, then proceed to next question automatically if user hasn't clicked next
    speakText(feedbackText, () => {
      setTimeout(() => {
        if (!isComponentMounted.current) return
        if (currentIndex < questions.length - 1) {
          const nextIdx = currentIndex + 1
          setCurrentIndex(nextIdx)
          setSelectedOption(null)
          setQuizStage('active')
          setQStartTime(Date.now())
          setTimeSpentSeconds(0)
        } else {
          finishQuiz(updatedScore, newAnswers)
        }
      }, 700)
    })
  }

  async function finishQuiz(finalScore = score, finalAnswers = userAnswers) {
    setQuizStage('completed')
    stopSpeech()
    stopListening()

    const elapsedTotal = Math.floor((Date.now() - quizStartMs) / 1000)
    setTotalTimeTaken(elapsedTotal)

    const calculatedScorePct = Math.round((finalScore / questions.length) * 100)
    const completionMsg = `Quiz completed! You scored ${finalScore} out of ${questions.length} questions correctly with an accuracy of ${calculatedScorePct} percent.`
    setStatusText(`🎉 ${completionMsg}`)

    try {
      const res = await request('/quiz-result', {
        method: 'POST',
        body: JSON.stringify({
          username: username || 'Guest Learner',
          topic,
          score: calculatedScorePct,
          total_questions: questions.length,
          correct_answers: finalScore,
        }),
      })

      if (res.badge_earned) {
        setBadgeEarned(res.badge_earned)
      }
    } catch (e) {
      // Non-critical background save failure
    }

    speakText(completionMsg)
  }

  function restartQuiz() {
    stopSpeech()
    stopListening()
    setCurrentIndex(0)
    setUserAnswers([])
    setScore(0)
    setSelectedOption(null)
    setBadgeEarned(null)
    setQuizStage('active')
    setQStartTime(Date.now())
    setTimeSpentSeconds(0)
  }

  const currentQ = questions[currentIndex]
  const liveAccuracyPct = userAnswers.length > 0 ? Math.round((score / userAnswers.length) * 100) : 100

  return (
    <div className="blind-quiz-overlay" role="dialog" aria-modal="true" aria-label="Audio Quiz Section for Blind Learners">
      <div className="blind-quiz-card">
        {/* Top Header */}
        <div className="quiz-header">
          <div>
            <span className="quiz-badge">🧠 Real-Time Audio Quiz — Blind Mode</span>
            <h2 className="quiz-title">Topic: {topic}</h2>
          </div>
          <button className="secondary-sm quiz-close-btn" onClick={() => { stopSpeech(); onClose(); }} aria-label="Close quiz and return to lesson">
            ✕ Exit Quiz
          </button>
        </div>

        {/* Real-Time Metrics Bar */}
        {quizStage !== 'loading' && quizStage !== 'error' && (
          <div className="deaf-metrics-bar">
            <div className="metric-chip">
              <span className="metric-label">Progress</span>
              <strong className="metric-value">{currentIndex + 1} / {questions.length || 5}</strong>
            </div>
            <div className="metric-chip">
              <span className="metric-label">Current Score</span>
              <strong className="metric-value highlight">{score} Correct</strong>
            </div>
            <div className="metric-chip">
              <span className="metric-label">Live Accuracy</span>
              <strong className="metric-value">{liveAccuracyPct}%</strong>
            </div>
            {quizStage === 'active' && (
              <div className="metric-chip timer">
                <span className="metric-label">Question Timer</span>
                <strong className="metric-value">⏱️ {timeSpentSeconds}s</strong>
              </div>
            )}
          </div>
        )}

        {/* Live Audio Status Banner */}
        <div className={`audio-status-banner ${isListening ? 'listening' : ''} ${isSpeaking ? 'speaking' : ''}`} role="status" aria-live="polite">
          {statusText}
        </div>

        {/* LOADING STAGE */}
        {quizStage === 'loading' && (
          <div className="quiz-loading-state">
            <div className="spinner"></div>
            <p>Generating 5 adaptive MCQ audio questions from your lesson summary...</p>
          </div>
        )}

        {/* ERROR STAGE */}
        {quizStage === 'error' && (
          <div className="quiz-error-state">
            <p className="notice error">{statusText}</p>
            <button className="primary" onClick={onClose}>Return to Lesson</button>
          </div>
        )}

        {/* ACTIVE OR ANSWERED STAGE */}
        {(quizStage === 'active' || quizStage === 'answered') && currentQ && (
          <div className="quiz-body">
            {/* Progress bar */}
            <div className="quiz-progress-bar" aria-label={`Question ${currentIndex + 1} of ${questions.length}`}>
              <div className="progress-fill" style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}></div>
            </div>

            {/* Question Heading */}
            <div className="question-box">
              <span className="question-number">Question {currentIndex + 1} of {questions.length} • Hear narration & speak Option 1, 2, 3, or 4</span>
              <h3 className="question-text">{currentQ.question}</h3>
            </div>

            {/* Audio Voice Control Buttons */}
            <div className="voice-controls-bar">
              <button
                className="secondary speak-action-btn"
                onClick={() => speakQuestionAndOptions(currentIndex)}
                disabled={isSpeaking || isListening}
                aria-label="Replay current question and 4 options"
              >
                🔊 Replay Question & Options
              </button>

              {!isListening ? (
                <button
                  className="primary voice-talk-btn"
                  onClick={startListening}
                  disabled={isSpeaking || quizStage === 'answered'}
                  aria-label="Activate microphone to say your answer option 1, 2, 3, or 4"
                >
                  🎙️ {isSpeaking ? 'Interrupt & Speak Choice' : 'Speak Choice (Option 1, 2, 3, or 4)'}
                </button>
              ) : (
                <button
                  className="voice-stop-btn pulse-listening"
                  onClick={stopListening}
                  aria-label="Stop microphone listening"
                >
                  🔴 Listening for "1", "2", "3", or "4"... (Tap to cancel)
                </button>
              )}

              {isSpeaking && (
                <button className="secondary" onClick={stopSpeech} aria-label="Stop speech narration">
                  ⏹️ Stop Speech
                </button>
              )}
            </div>

            {/* 4 Options Grid */}
            <div className="options-grid" aria-label="4 Multiple Choice Options">
              {currentQ.options.map((optText, optIdx) => {
                let btnStyle = 'option-btn'
                if (selectedOption === optIdx) {
                  if (quizStage === 'answered') {
                    btnStyle += optIdx === currentQ.correct_index ? ' option-correct' : ' option-incorrect'
                  } else {
                    btnStyle += ' option-selected'
                  }
                } else if (quizStage === 'answered' && optIdx === currentQ.correct_index) {
                  btnStyle += ' option-correct'
                }

                return (
                  <button
                    key={optIdx}
                    className={btnStyle}
                    onClick={() => handleOptionChoice(optIdx)}
                    disabled={quizStage === 'answered'}
                    aria-label={`Option ${optIdx + 1}: ${optText}`}
                  >
                    <span className="option-num">Option {optIdx + 1}</span>
                    <span className="option-text">{optText}</span>
                  </button>
                )
              })}
            </div>

            {/* Explanation box after answer */}
            {quizStage === 'answered' && (
              <div className={`explanation-box ${selectedOption === currentQ.correct_index ? 'correct' : 'incorrect'}`}>
                <strong>{selectedOption === currentQ.correct_index ? '🎉 Correct Understanding!' : '💡 Key Concept Explanation:'}</strong>
                <p>{currentQ.explanation}</p>
                <div style={{ marginTop: '16px' }}>
                  <button
                    className="primary quiz-proceed-btn"
                    onClick={handleNextQuestion}
                    style={{ width: '100%', padding: '14px', fontSize: '1rem', fontWeight: 'bold', borderRadius: '12px', cursor: 'pointer' }}
                    aria-label={currentIndex < questions.length - 1 ? `Proceed to Next Question (Question ${currentIndex + 2} of ${questions.length})` : "View Learning Progress Dashboard"}
                  >
                    {currentIndex < questions.length - 1
                      ? `➡️ Proceed to Next Question (Question ${currentIndex + 2} of ${questions.length})`
                      : '🏆 View Learning Progress Dashboard'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* COMPLETED STAGE: Real-Time Learning Progress Dashboard */}
        {quizStage === 'completed' && (
          <div className="deaf-completed-box">
            <div className="deaf-completed-header">
              <div className="trophy-badge">🏆</div>
              <h3>Learning Progress Dashboard</h3>
              <p className="subtitle">Audio Learning Assessment Summary — Blind Mode</p>
            </div>

            <div className="deaf-summary-grid">
              <div className="summary-stat-card">
                <span className="stat-label">Final Score</span>
                <strong className="stat-value">{score} / {questions.length}</strong>
              </div>
              <div className="summary-stat-card">
                <span className="stat-label">Accuracy</span>
                <strong className="stat-value">{Math.round((score / questions.length) * 100)}%</strong>
              </div>
              <div className="summary-stat-card">
                <span className="stat-label">Total Time Taken</span>
                <strong className="stat-value">{totalTimeTaken}s</strong>
              </div>
            </div>

            {badgeEarned && (
              <div className="deaf-badge-award">
                <span>Awarded Milestone Badge:</span>
                <strong>{badgeEarned}</strong>
              </div>
            )}

            {/* Questions Overview */}
            <div className="deaf-review-section">
              <h4>Questions Learning Breakdown</h4>
              <div className="review-list">
                {questions.map((q, idx) => {
                  const userAns = userAnswers[idx]
                  const wasCorrect = userAns?.isCorrect
                  return (
                    <div key={q.id || idx} className={`review-item ${wasCorrect ? 'item-pass' : 'item-fail'}`}>
                      <span className="item-status">{wasCorrect ? '✅' : '❌'} Q{idx + 1}</span>
                      <span className="item-question">{q.question}</span>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="completed-actions">
              <button className="primary" onClick={restartQuiz}>
                🔄 Retake 5-Question Audio Quiz
              </button>
              <button className="secondary" onClick={() => { stopSpeech(); onClose(); }}>
                📖 Back to Audio Summary
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

