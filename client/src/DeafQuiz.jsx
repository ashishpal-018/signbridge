import { useState, useEffect, useRef } from 'react'

export default function DeafQuiz({ topic, summary, username, request, onClose }) {
  const [questions, setQuestions] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [userAnswers, setUserAnswers] = useState([])
  const [score, setScore] = useState(0)
  const [quizStage, setQuizStage] = useState('loading') // 'loading' | 'active' | 'answered' | 'completed' | 'error'
  const [selectedOption, setSelectedOption] = useState(null)
  const [statusText, setStatusText] = useState('Generating real-time visual quiz from your lesson...')
  const [badgeEarned, setBadgeEarned] = useState(null)
  
  // Real-time tracking stats
  const [questionStartTime, setQuestionStartTime] = useState(Date.now())
  const [timeSpentSeconds, setTimeSpentSeconds] = useState(0)
  const [quizStartTime] = useState(Date.now())
  const [totalTimeTaken, setTotalTimeTaken] = useState(0)

  const isComponentMounted = useRef(true)

  // Live timer tick for real-time engagement tracking
  useEffect(() => {
    let timerInterval = null
    if (quizStage === 'active') {
      timerInterval = setInterval(() => {
        setTimeSpentSeconds(Math.floor((Date.now() - questionStartTime) / 1000))
      }, 1000)
    }
    return () => {
      if (timerInterval) clearInterval(timerInterval)
    }
  }, [quizStage, questionStartTime])

  // Fetch structured 5-question deaf quiz on mount
  useEffect(() => {
    isComponentMounted.current = true
    let isCancelled = false

    async function fetchQuiz() {
      try {
        setStatusText('Analyzing lesson concepts to generate 5 real-time MCQ questions...')
        const data = await request('/deaf/quiz', {
          method: 'POST',
          body: JSON.stringify({ topic, summary, username }),
        })

        if (isCancelled || !isComponentMounted.current) return

        if (data.questions && data.questions.length > 0) {
          setQuestions(data.questions)
          setQuizStage('active')
          setQuestionStartTime(Date.now())
          setTimeSpentSeconds(0)
          setStatusText('Quiz ready! Answer 5 adaptive questions based on your lesson.')
        } else {
          setQuizStage('error')
          setStatusText('Failed to generate quiz questions. Please try again.')
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
    }
  }, [topic, summary])

  // Option selection handler
  async function handleOptionSelect(optionIndex) {
    if (quizStage !== 'active' || !questions[currentIndex]) return

    setSelectedOption(optionIndex)
    setQuizStage('answered')

    const currentQ = questions[currentIndex]
    const isCorrect = optionIndex === currentQ.correct_index
    const duration = Math.floor((Date.now() - questionStartTime) / 1000)

    const answerRecord = {
      questionId: currentQ.id,
      selected: optionIndex,
      correctIndex: currentQ.correct_index,
      isCorrect,
      timeSeconds: duration,
    }

    const newAnswers = [...userAnswers, answerRecord]
    setUserAnswers(newAnswers)

    let updatedScore = score
    if (isCorrect) {
      updatedScore = score + 1
      setScore(updatedScore)
      setStatusText('✅ Correct answer! Great visual analysis.')
    } else {
      setStatusText(`❌ Incorrect. Option ${currentQ.correct_index + 1} was the correct choice.`)
    }
  }

  function handleNextQuestion() {
    if (currentIndex < questions.length - 1) {
      const nextIdx = currentIndex + 1
      setCurrentIndex(nextIdx)
      setSelectedOption(null)
      setQuizStage('active')
      setQuestionStartTime(Date.now())
      setTimeSpentSeconds(0)
      setStatusText(`Question ${nextIdx + 1} of ${questions.length} — Select 1 option.`)
    } else {
      finishQuiz()
    }
  }

  async function finishQuiz() {
    setQuizStage('completed')
    const elapsedTotal = Math.floor((Date.now() - quizStartTime) / 1000)
    setTotalTimeTaken(elapsedTotal)

    const calculatedScore = Math.round((score / questions.length) * 100)
    setStatusText(`🎉 Quiz completed! You scored ${score} / ${questions.length} (${calculatedScore}%)`)

    try {
      const res = await request('/quiz-result', {
        method: 'POST',
        body: JSON.stringify({
          username: username || 'Guest Learner',
          topic,
          score: calculatedScore,
          total_questions: questions.length,
          correct_answers: score,
        }),
      })

      if (res.badge_earned) {
        setBadgeEarned(res.badge_earned)
      }
    } catch (e) {
      // Non-critical background save failure
    }
  }

  function restartQuiz() {
    setCurrentIndex(0)
    setUserAnswers([])
    setScore(0)
    setSelectedOption(null)
    setBadgeEarned(null)
    setQuizStage('active')
    setQuestionStartTime(Date.now())
    setTimeSpentSeconds(0)
    setStatusText('Quiz restarted. Answer 5 questions below.')
  }

  const currentQ = questions[currentIndex]
  const accuracyPct = userAnswers.length > 0 ? Math.round((score / userAnswers.length) * 100) : 0

  return (
    <div className="deaf-quiz-overlay" role="dialog" aria-modal="true" aria-label="Real-time Deaf Visual Quiz">
      <div className="deaf-quiz-card">
        {/* Header with visual badge & score tracking */}
        <div className="deaf-quiz-header">
          <div>
            <span className="deaf-quiz-badge">🧠 Real-time Adaptive Quiz — Deaf Mode</span>
            <h2 className="deaf-quiz-title">Topic: {topic}</h2>
          </div>
          <button className="secondary-sm quiz-close-btn" onClick={onClose} aria-label="Exit quiz">
            ✕ Exit Quiz
          </button>
        </div>

        {/* Real-time metrics bar */}
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
              <strong className="metric-value">{userAnswers.length > 0 ? `${accuracyPct}%` : '100%'}</strong>
            </div>
            {quizStage === 'active' && (
              <div className="metric-chip timer">
                <span className="metric-label">Time</span>
                <strong className="metric-value">⏱️ {timeSpentSeconds}s</strong>
              </div>
            )}
          </div>
        )}

        {/* Status notice banner */}
        <div className={`deaf-status-banner ${quizStage === 'answered' ? (selectedOption === currentQ?.correct_index ? 'correct' : 'incorrect') : ''}`} role="status">
          {statusText}
        </div>

        {/* LOADING STAGE */}
        {quizStage === 'loading' && (
          <div className="quiz-loading-state">
            <div className="deaf-spinner"></div>
            <p>Generating 5 adaptive MCQ questions from your visual lesson...</p>
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
          <div className="deaf-quiz-body">
            {/* Visual Progress Bar */}
            <div className="deaf-progress-bar" aria-label={`Question ${currentIndex + 1} of 5`}>
              <div className="deaf-progress-fill" style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}></div>
            </div>

            {/* Question Text Box */}
            <div className="deaf-question-box">
              <div className="deaf-question-meta">
                <span className="deaf-q-num">Question {currentIndex + 1} of {questions.length}</span>
                <span className="deaf-q-type">Select 1 of 4 Options</span>
              </div>
              <h3 className="deaf-q-text">{currentQ.question}</h3>
            </div>

            {/* 4 Options Grid */}
            <div className="deaf-options-grid" aria-label="4 Multiple Choice Options">
              {currentQ.options.map((optText, optIdx) => {
                let btnClass = 'deaf-option-btn'
                const isSelected = selectedOption === optIdx
                const isTargetCorrect = optIdx === currentQ.correct_index

                if (quizStage === 'answered') {
                  if (isSelected) {
                    btnClass += isTargetCorrect ? ' option-correct' : ' option-incorrect'
                  } else if (isTargetCorrect) {
                    btnClass += ' option-correct'
                  } else {
                    btnClass += ' option-dimmed'
                  }
                } else if (isSelected) {
                  btnClass += ' option-selected'
                }

                const optionLetter = ['A', 'B', 'C', 'D'][optIdx]

                return (
                  <button
                    key={optIdx}
                    className={btnClass}
                    onClick={() => handleOptionSelect(optIdx)}
                    disabled={quizStage === 'answered'}
                    aria-label={`Option ${optionLetter}: ${optText}`}
                  >
                    <div className="deaf-option-header">
                      <span className="deaf-opt-letter">Option {optionLetter}</span>
                      {quizStage === 'answered' && isTargetCorrect && <span className="deaf-check-badge">✓ Correct</span>}
                      {quizStage === 'answered' && isSelected && !isTargetCorrect && <span className="deaf-cross-badge">✕ Your Choice</span>}
                    </div>
                    <span className="deaf-opt-body">{optText}</span>
                  </button>
                )
              })}
            </div>

            {/* Explanation box after answering */}
            {quizStage === 'answered' && (
              <div className={`deaf-explanation-card ${selectedOption === currentQ.correct_index ? 'correct' : 'incorrect'}`}>
                <div className="exp-title">
                  {selectedOption === currentQ.correct_index ? '🎉 Correct Understanding!' : '💡 Key Concept Explanation:'}
                </div>
                <p className="exp-text">{currentQ.explanation}</p>
              </div>
            )}

            {/* Navigation action button */}
            {quizStage === 'answered' && (
              <div className="deaf-action-footer">
                <button className="primary deaf-next-btn" onClick={handleNextQuestion}>
                  {currentIndex < questions.length - 1 ? 'Next Question ➔' : 'View Final Quiz Summary 🏆'}
                </button>
              </div>
            )}
          </div>
        )}

        {/* COMPLETED STAGE */}
        {quizStage === 'completed' && (
          <div className="deaf-completed-box">
            <div className="deaf-completed-header">
              <div className="trophy-badge">🏆</div>
              <h3>Real-Time Quiz Completed!</h3>
              <p className="subtitle">Visual Knowledge Assessment Summary</p>
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
                <span>Awarded Badge:</span>
                <strong>{badgeEarned}</strong>
              </div>
            )}

            {/* Answers Breakdown */}
            <div className="deaf-review-section">
              <h4>Questions Overview</h4>
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
                🔄 Retake 5-Question Quiz
              </button>
              <button className="secondary" onClick={onClose}>
                📖 Return to Lesson
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
