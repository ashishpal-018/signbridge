import { useEffect, useRef, useState } from 'react'

const VIDEO_WIDTH = 640
const VIDEO_HEIGHT = 480
const CAMERA_UTILS_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3.1675466862/camera_utils.js'
const HANDS_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/hands.js'

function loadScript(globalName, source) {
  if (window[globalName]) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = source
    script.crossOrigin = 'anonymous'
    script.onload = () => (window[globalName] ? resolve() : reject(new Error(`MediaPipe ${globalName} unavailable.`)))
    script.onerror = () => reject(new Error(`Could not load script ${source}`))
    document.head.appendChild(script)
  })
}

const GESTURE_MODES = [
  {
    key: 'deaf',
    name: 'Deaf Mode',
    sign: 'Open Palm',
    icon: '✋',
    color: '#62d6c5',
    description: 'Show an open palm (all 5 fingers spread)',
  },
  {
    key: 'blind',
    name: 'Blind Mode',
    sign: 'Thumbs Up',
    icon: '👍',
    color: '#f4b95f',
    description: 'Show a thumbs up (thumb extended, fingers closed)',
  },
  {
    key: 'sign',
    name: 'Air-Writing Mode',
    sign: 'Peace / Point',
    icon: '✌️',
    color: '#8fc5fa',
    description: 'Show peace sign (V shape) or point index finger',
  },
]

function calcDist(p1, p2) {
  const dx = (p1.x - p2.x)
  const dy = (p1.y - p2.y)
  const dz = (p1.z || 0) - (p2.z || 0)
  return Math.sqrt(dx * dx + dy * dy + dz * dz)
}

function analyzeGesture(landmarks) {
  if (!landmarks || landmarks.length < 21) return null

  const wrist = landmarks[0]
  const thumbTip = landmarks[4]
  const thumbMcp = landmarks[2]
  const indexTip = landmarks[8]
  const indexPip = landmarks[6]
  const middleTip = landmarks[12]
  const middlePip = landmarks[10]
  const ringTip = landmarks[16]
  const ringPip = landmarks[14]
  const pinkyTip = landmarks[20]
  const pinkyPip = landmarks[18]
  const pinkyMcp = landmarks[17]

  const indexExt = calcDist(wrist, indexTip) > calcDist(wrist, indexPip) * 1.15
  const middleExt = calcDist(wrist, middleTip) > calcDist(wrist, middlePip) * 1.15
  const ringExt = calcDist(wrist, ringTip) > calcDist(wrist, ringPip) * 1.15
  const pinkyExt = calcDist(wrist, pinkyTip) > calcDist(wrist, pinkyPip) * 1.15
  const thumbExt = calcDist(pinkyMcp, thumbTip) > calcDist(pinkyMcp, thumbMcp) * 1.15

  // 1. Thumbs Up -> Blind Mode
  if (thumbExt && !indexExt && !middleExt && !ringExt && !pinkyExt) {
    return { mode: 'blind', label: 'Thumbs Up', icon: '👍' }
  }

  // 2. Open Palm (Hello / 5 fingers) -> Deaf Mode
  if (indexExt && middleExt && ringExt && pinkyExt) {
    return { mode: 'deaf', label: 'Open Palm', icon: '✋' }
  }

  // 3. Peace sign or Pointing -> Sign / Air-writing Mode
  if ((indexExt && middleExt && !ringExt && !pinkyExt) || (indexExt && !middleExt && !ringExt && !pinkyExt)) {
    return { mode: 'sign', label: indexExt && middleExt ? 'Peace Sign' : 'Index Pointing', icon: '✌️' }
  }

  return null
}

export default function LiveGestureCamera({ activeMode, onSwitchMode, autoStart = false }) {
  const [cameraActive, setCameraActive] = useState(false)
  const [cameraLoading, setCameraLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState('Camera initializing...')
  const [detectedGesture, setDetectedGesture] = useState(null)
  const [holdProgress, setHoldProgress] = useState(0) // 0 to 100%

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const cameraInstanceRef = useRef(null)
  const handsInstanceRef = useRef(null)
  const holdStartRef = useRef(null)
  const lastTargetModeRef = useRef(null)
  const isSwitchingRef = useRef(false)
  const autoStartedRef = useRef(false)

  useEffect(() => {
    if (autoStart && !autoStartedRef.current) {
      autoStartedRef.current = true
      startCamera()
    }
    return () => {
      stopCamera()
    }
  }, [autoStart])

  function stopCamera() {
    try {
      if (cameraInstanceRef.current) {
        cameraInstanceRef.current.stop()
        cameraInstanceRef.current = null
      }
    } catch {
      // ignore stop errors
    }
    if (handsInstanceRef.current) {
      try {
        handsInstanceRef.current.close()
      } catch {
        // ignore
      }
      handsInstanceRef.current = null
    }

    if (videoRef.current && videoRef.current.srcObject) {
      const tracks = videoRef.current.srcObject.getTracks()
      tracks.forEach(track => track.stop())
      videoRef.current.srcObject = null
    }

    setCameraActive(false)
    setCameraLoading(false)
    setDetectedGesture(null)
    setHoldProgress(0)
    setStatusMessage('Camera stopped.')
  }

  async function startCamera() {
    setCameraLoading(true)
    setStatusMessage('Initializing MediaPipe gesture recognition engine...')

    try {
      await loadScript('Camera', CAMERA_UTILS_URL)
      await loadScript('Hands', HANDS_URL)

      if (!window.Hands || !window.Camera) {
        throw new Error('MediaPipe script failed to attach to window.')
      }

      const hands = new window.Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/${file}`,
      })

      hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.65,
        minTrackingConfidence: 0.65,
      })

      hands.onResults(handleHandResults)
      handsInstanceRef.current = hands

      if (!videoRef.current) throw new Error('Video element reference is missing.')

      const camera = new window.Camera(videoRef.current, {
        onFrame: async () => {
          if (videoRef.current && handsInstanceRef.current) {
            await handsInstanceRef.current.send({ image: videoRef.current })
          }
        },
        width: VIDEO_WIDTH,
        height: VIDEO_HEIGHT,
      })

      await camera.start()
      cameraInstanceRef.current = camera

      setCameraActive(true)
      setCameraLoading(false)
      setStatusMessage('Live camera active! Show hand sign (Open Palm ✋, Thumbs Up 👍, Peace ✌️) to switch modes.')
    } catch (err) {
      console.error(err)
      stopCamera()
      setStatusMessage(`Camera setup error: ${err.message}`)
    }
  }

  function handleHandResults(results) {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0) {
      setDetectedGesture(null)
      setHoldProgress(0)
      holdStartRef.current = null
      lastTargetModeRef.current = null
      return
    }

    const landmarks = results.multiHandLandmarks[0]

    // Draw landmark connections on canvas
    ctx.fillStyle = '#62d6c5'
    ctx.strokeStyle = '#45e8ff'
    ctx.lineWidth = 3

    // Draw hand skeletal lines
    const connections = [
      [0,1],[1,2],[2,3],[3,4], // Thumb
      [0,5],[5,6],[6,7],[7,8], // Index
      [0,9],[9,10],[10,11],[11,12], // Middle
      [0,13],[13,14],[14,15],[15,16], // Ring
      [0,17],[17,18],[18,19],[19,20], // Pinky
      [5,9],[9,13],[13,17] // Palm
    ]

    connections.forEach(([i, j]) => {
      const p1 = landmarks[i]
      const p2 = landmarks[j]
      ctx.beginPath()
      ctx.moveTo(p1.x * canvas.width, p1.y * canvas.height)
      ctx.lineTo(p2.x * canvas.width, p2.y * canvas.height)
      ctx.stroke()
    })

    // Draw landmark joints
    landmarks.forEach((p, idx) => {
      ctx.beginPath()
      ctx.arc(p.x * canvas.width, p.y * canvas.height, idx === 4 || idx === 8 ? 6 : 4, 0, 2 * Math.PI)
      ctx.fillStyle = idx === 4 || idx === 8 ? '#f4b95f' : '#62d6c5'
      ctx.fill()
    })

    // Analyze Hand Sign Gesture
    const gesture = analyzeGesture(landmarks)

    if (gesture) {
      setDetectedGesture(gesture)

      // Hold countdown logic for seamless mode switching
      const targetMode = gesture.mode
      const now = Date.now()

      if (lastTargetModeRef.current !== targetMode) {
        lastTargetModeRef.current = targetMode
        holdStartRef.current = now
        setHoldProgress(10)
      } else {
        const elapsed = now - (holdStartRef.current || now)
        const holdDurationNeeded = 1000 // 1 second continuous hold
        const pct = Math.min(100, Math.round((elapsed / holdDurationNeeded) * 100))
        setHoldProgress(pct)

        if (pct >= 100 && !isSwitchingRef.current && targetMode !== activeMode) {
          isSwitchingRef.current = true
          setStatusMessage(`✨ Hand Sign Confirmed! Switching to ${targetMode.toUpperCase()} mode...`)
          onSwitchMode(targetMode)

          setTimeout(() => {
            isSwitchingRef.current = false
            holdStartRef.current = null
            setHoldProgress(0)
          }, 1500)
        }
      }
    } else {
      setDetectedGesture(null)
      setHoldProgress(0)
      holdStartRef.current = null
      lastTargetModeRef.current = null
    }
  }

  return (
    <div className="live-gesture-camera-card">
      <div className="lgc-header">
        <div className="lgc-title">
          <span className="lgc-icon">🎥</span>
          <div>
            <h3>Live Hand-Sign Mode Controller</h3>
            <p className="muted">Switch UI learning pathways hands-free using webcam signs</p>
          </div>
        </div>

        <button
          className={cameraActive ? 'secondary lgc-stop-btn' : 'primary lgc-start-btn'}
          onClick={cameraActive ? stopCamera : startCamera}
          disabled={cameraLoading}
        >
          {cameraLoading ? 'Loading Camera...' : cameraActive ? '⏹ Stop Live Camera' : '📷 Start Live Gesture Camera'}
        </button>
      </div>

      {/* GESTURE LEGEND / MAP */}
      <div className="lgc-legend-row">
        {GESTURE_MODES.map((item) => {
          const isActive = activeMode === item.key
          const isDetected = detectedGesture?.mode === item.key
          return (
            <div
              key={item.key}
              className={`lgc-legend-card ${isActive ? 'active-mode' : ''} ${isDetected ? 'detected-gesture' : ''}`}
            >
              <div className="lgc-legend-badge" style={{ borderColor: item.color }}>
                <span className="lgc-legend-icon">{item.icon}</span>
                <div>
                  <strong>{item.sign}</strong>
                  <span className="lgc-target-name">{item.name}</span>
                </div>
              </div>
              <p className="lgc-legend-desc">{item.description}</p>
              {isActive && <span className="lgc-current-tag">Current Mode</span>}
              {isDetected && targetModeHighlight(holdProgress, item.color)}
            </div>
          )
        })}
      </div>

      {/* LIVE CAMERA DISPLAY - ALWAYS RENDERED FOR AUTO-START */}
      <div className="lgc-stage-wrapper">
        <div className="lgc-stage">
          <video ref={videoRef} className="lgc-video" width={VIDEO_WIDTH} height={VIDEO_HEIGHT} playsInline muted />
          <canvas ref={canvasRef} className="lgc-canvas" width={VIDEO_WIDTH} height={VIDEO_HEIGHT} />

          {!cameraActive && (
            <div className="lgc-stage-loading-overlay">
              <div className="lgc-spinner" />
              <p>{cameraLoading ? 'Connecting to camera...' : 'Camera stopped'}</p>
              {!cameraLoading && (
                <button className="primary" onClick={startCamera}>Turn On Camera</button>
              )}
            </div>
          )}

          {/* LIVE OVERLAY BANNER */}
          {cameraActive && (
            <div className="lgc-overlay-banner">
              {detectedGesture ? (
                <div className="lgc-detected-box">
                  <span className="lgc-detected-icon">{detectedGesture.icon}</span>
                  <div>
                    <strong>Sign Detected: {detectedGesture.label}</strong>
                    <span>Target: {detectedGesture.mode.toUpperCase()} Mode</span>
                  </div>
                </div>
              ) : (
                <div className="lgc-searching-box">
                  <span>✋ Show hand sign to camera</span>
                </div>
              )}
            </div>
          )}

          {/* HOLD PROGRESS BAR OVERLAY */}
          {cameraActive && holdProgress > 0 && detectedGesture && detectedGesture.mode !== activeMode && (
            <div className="lgc-hold-bar-container">
              <div className="lgc-hold-bar-label">
                Holding sign... {holdProgress}%
              </div>
              <div className="lgc-hold-bar-track">
                <div className="lgc-hold-bar-fill" style={{ width: `${holdProgress}%` }} />
              </div>
            </div>
          )}
        </div>

        <p className="lgc-status-bar">{statusMessage}</p>
      </div>
    </div>
  )
}

function targetModeHighlight(progress, color) {
  return (
    <div className="lgc-detect-ring" style={{ borderColor: color }}>
      <span className="lgc-detect-pulse" style={{ background: color, width: `${progress}%` }} />
    </div>
  )
}
