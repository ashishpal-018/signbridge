import { useEffect, useRef, useState } from 'react'
import { createWorker } from 'tesseract.js'

const VIDEO_WIDTH = 640
const VIDEO_HEIGHT = 480
const TOTAL_WRITING_LINES = 5
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

// ------------------------------------------------------------------
// Render All Drawn Strokes to High-Contrast Binary Offscreen Canvas
// (Captures the FINAL PICTURE for OCR Vision — supports Capital, Lowercase & Cursive)
// ------------------------------------------------------------------
function prepareOcrCanvasFromStrokes(strokes, canvasWidth = 640, canvasHeight = 480) {
  if (!strokes || strokes.length === 0) return null

  let minX = canvasWidth, maxX = 0, minY = canvasHeight, maxY = 0
  let pointCount = 0

  strokes.forEach(stroke => {
    stroke.forEach(p => {
      const px = p.x * canvasWidth
      const py = p.y * canvasHeight
      if (px < minX) minX = px
      if (px > maxX) maxX = px
      if (py < minY) minY = py
      if (py > maxY) maxY = py
      pointCount++
    })
  })

  if (pointCount < 5) return null

  const margin = 48
  const left = Math.max(0, Math.floor(minX - margin))
  const top = Math.max(0, Math.floor(minY - margin))
  const right = Math.min(canvasWidth, Math.ceil(maxX + margin))
  const bottom = Math.min(canvasHeight, Math.ceil(maxY + margin))
  const cropW = Math.max(40, right - left)
  const cropH = Math.max(40, bottom - top)

  // Full-size offscreen canvas
  const drawCanvas = document.createElement('canvas')
  drawCanvas.width = canvasWidth
  drawCanvas.height = canvasHeight
  const ctx = drawCanvas.getContext('2d')

  // Clean white background for contrast
  ctx.fillStyle = '#FFFFFF'
  ctx.fillRect(0, 0, canvasWidth, canvasHeight)

  // High-contrast bold black stroke tuned for alphabet OCR vision
  const calculatedLineWidth = Math.max(14, Math.round(Math.min(cropW, cropH) * 0.08))
  ctx.lineWidth = calculatedLineWidth
  ctx.strokeStyle = '#000000'
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'

  strokes.forEach(stroke => {
    if (stroke.length > 1) {
      ctx.beginPath()
      for (let i = 0; i < stroke.length; i++) {
        const px = stroke[i].x * canvasWidth
        const py = stroke[i].y * canvasHeight
        if (i === 0) ctx.moveTo(px, py)
        else ctx.lineTo(px, py)
      }
      ctx.stroke()
    }
  })

  // Crop & scale 3.5x for high resolution alphabet recognition
  const scaleFactor = 3.5
  const cropCanvas = document.createElement('canvas')
  cropCanvas.width = Math.round(cropW * scaleFactor)
  cropCanvas.height = Math.round(cropH * scaleFactor)
  const cropCtx = cropCanvas.getContext('2d')
  cropCtx.fillStyle = '#FFFFFF'
  cropCtx.fillRect(0, 0, cropCanvas.width, cropCanvas.height)
  cropCtx.imageSmoothingEnabled = true
  cropCtx.imageSmoothingQuality = 'high'
  cropCtx.drawImage(drawCanvas, left, top, cropW, cropH, 0, 0, cropCanvas.width, cropCanvas.height)

  return cropCanvas
}

// ------------------------------------------------------------------
// Geometric Trajectory Processing & Letter Classifier Fallback
// ------------------------------------------------------------------
function smoothTrajectory(points, alpha = 0.40) {
  if (!points || points.length <= 1) return points
  const smoothed = [points[0]]
  for (let i = 1; i < points.length; i++) {
    const prev = smoothed[smoothed.length - 1]
    const curr = points[i]
    smoothed.push({
      x: alpha * curr.x + (1 - alpha) * prev.x,
      y: alpha * curr.y + (1 - alpha) * prev.y,
      t: curr.t || 0,
    })
  }
  return smoothed
}

function normalizeTrajectory(points) {
  if (!points || points.length === 0) return []
  const xs = points.map(p => p.x)
  const ys = points.map(p => p.y)

  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)

  const width = maxX - minX
  const height = maxY - minY
  const scale = Math.max(width, height)

  if (scale < 0.001) return points.map(p => ({ x: 0, y: 0, t: p.t || 0 }))

  const centerX = (minX + maxX) / 2
  const centerY = (minY + maxY) / 2

  return points.map(p => ({
    x: (p.x - centerX) / scale,
    y: (p.y - centerY) / scale,
    t: p.t || 0,
  }))
}

function resampleTrajectory(points, numSamples = 32) {
  if (!points || points.length === 0) return []
  if (points.length === 1) return Array(numSamples).fill(points[0])

  let totalLen = 0
  const distances = [0]
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x
    const dy = points[i].y - points[i - 1].y
    const d = Math.sqrt(dx * dx + dy * dy)
    totalLen += d
    distances.push(totalLen)
  }

  if (totalLen < 0.0001) return Array(numSamples).fill(points[0])

  const interval = totalLen / (numSamples - 1)
  const resampled = [points[0]]
  let currIdx = 0

  for (let i = 1; i < numSamples - 1; i++) {
    const targetDist = i * interval
    while (currIdx < distances.length - 1 && distances[currIdx + 1] < targetDist) {
      currIdx++
    }
    if (currIdx >= distances.length - 1) {
      resampled.push(points[points.length - 1])
      continue
    }

    const d1 = distances[currIdx]
    const d2 = distances[currIdx + 1]
    const segT = d2 > d1 ? (targetDist - d1) / (d2 - d1) : 0

    const p1 = points[currIdx]
    const p2 = points[currIdx + 1]
    resampled.push({
      x: p1.x + segT * (p2.x - p1.x),
      y: p1.y + segT * (p2.y - p1.y),
      t: p1.t || 0,
    })
  }

  resampled.push(points[points.length - 1])
  return resampled
}

function classifyLocalTrajectory(rawPoints) {
  if (!rawPoints || rawPoints.length < 5) {
    return {
      success: false,
      letter: null,
      confidence: 0,
      message: 'Trajectory too short. Trace an alphabet letter clearly in the air.',
    }
  }

  const smoothed = smoothTrajectory(rawPoints)
  const normalized = normalizeTrajectory(smoothed)
  const resampled = resampleTrajectory(normalized, 32)

  const xs = resampled.map(p => p.x)
  const ys = resampled.map(p => p.y)

  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minY = Math.min(...ys), maxY = Math.max(...ys)
  const width = maxX - minX
  const height = maxY - minY
  const aspectRatio = height > 0.0001 ? width / height : 1.0

  const startP = resampled[0]
  const endP = resampled[resampled.length - 1]
  const midP = resampled[16]

  const minYIdx = ys.indexOf(minY)
  const maxYIdx = ys.indexOf(maxY)

  const startEndDist = Math.hypot(endP.x - startP.x, endP.y - startP.y)
  const isClosedLoop = startEndDist < 0.35 && resampled.length >= 10

  const isTopApex = minYIdx >= 3 && minYIdx <= 28 && minY < startP.y - 0.15 && minY < endP.y - 0.15
  const isBottomDip = maxYIdx >= 3 && maxYIdx <= 28 && maxY > startP.y + 0.15 && maxY > endP.y + 0.15

  const scores = {}

  // 1. LETTER O: Closed circular loop
  if (isClosedLoop && aspectRatio >= 0.45 && aspectRatio <= 1.7) {
    scores['O'] = 0.96
  }

  // 2. LETTER A: Peak top apex with start & end at bottom
  if (isTopApex && startP.y > minY + 0.20 && endP.y > minY + 0.20 && aspectRatio > 0.35) {
    scores['A'] = 0.95
  }

  // 3. LETTER I: Narrow vertical straight line
  if (aspectRatio < 0.45 && Math.abs(endP.y - startP.y) > 0.40) {
    scores['I'] = 0.95
  }

  // 4. LETTER L: Down vertical stem + right bottom horizontal
  if (endP.x > startP.x + 0.20 && endP.y > maxY - 0.25 && aspectRatio > 0.35) {
    scores['L'] = 0.94
  }

  // 5. LETTER C: Open arc facing left
  if (!isClosedLoop && startP.x > minX + 0.12 && endP.x > minX + 0.12 && midP.x < minX + 0.15) {
    scores['C'] = 0.93
  }

  // 6. LETTER J: Vertical down stroke with bottom left hook
  if (maxYIdx >= 12 && endP.x < startP.x - 0.08) {
    scores['J'] = 0.93
  }

  // 7. LETTER V: Sharp bottom dip apex
  if (isBottomDip && startP.y < maxY - 0.20 && endP.y < maxY - 0.20 && !isClosedLoop) {
    scores['V'] = 0.93
    scores['U'] = 0.88
  }

  // 8. LETTER U: Smooth bottom curve
  if (isBottomDip && (startP.x < midP.x || endP.x > midP.x)) {
    scores['U'] = 0.92
  }

  // 9. LETTER S: Serpentine curve (starts top-right, curves left, then right)
  if (!isClosedLoop && aspectRatio > 0.38 && startP.x > midP.x && endP.x < midP.x) {
    scores['S'] = 0.93
  }

  // 10. LETTER T: Top horizontal line with vertical stem
  if (Math.abs(startP.y - minY) < 0.20 && Math.abs(endP.y - maxY) < 0.25 && aspectRatio > 0.45) {
    scores['T'] = 0.92
  }

  // 11. LETTER Z: Top horizontal right, diagonal down left, bottom horizontal right
  if (startP.x < maxX - 0.15 && endP.x > minX + 0.15 && minYIdx < maxYIdx) {
    scores['Z'] = 0.91
  }

  // 12. LETTER W / M: Dual peaks / dips
  if (aspectRatio > 0.65) {
    if (startP.y < midP.y && endP.y < midP.y) scores['M'] = 0.92
    else if (startP.y > midP.y && endP.y > midP.y) scores['W'] = 0.92
  }

  // 13. LETTER N: Up, diagonal down, up
  if (startP.y > midP.y && endP.y < midP.y && endP.x > startP.x + 0.20) {
    scores['N'] = 0.91
  }

  // 14. LETTER P / R / B / D: Left vertical stem + right curves
  if (startP.y < midP.y && endP.y > midP.y) {
    if (endP.x > minX + 0.20) scores['R'] = 0.90
    else scores['P'] = 0.90
  }

  // 15. LETTER E / F / H / X / G / K / Y / Q
  if (!scores['A'] && !scores['O'] && !scores['I'] && !scores['C']) {
    if (startP.x > minX + 0.15 && endP.x < maxX - 0.15) scores['X'] = 0.89
    else if (endP.x > midP.x && endP.y > midP.y) scores['G'] = 0.88
    else scores['E'] = 0.85
  }

  // Safe fallback guarantees ONLY ALPHABETS (A-Z)
  if (Object.keys(scores).length === 0) {
    if (isClosedLoop) scores['O'] = 0.85
    else if (aspectRatio < 0.45) scores['I'] = 0.85
    else if (isTopApex) scores['A'] = 0.85
    else if (isBottomDip) scores['V'] = 0.85
    else scores['E'] = 0.80
  }

  const bestLetter = Object.keys(scores).reduce((a, b) => (scores[a] > scores[b] ? a : b))
  const sanitizedLetter = String(bestLetter).replace(/[^a-zA-Z]/g, '').toUpperCase() || 'A'
  const confidence = Math.round(scores[bestLetter] * 100) / 100

  return {
    success: true,
    letter: sanitizedLetter,
    confidence,
    message: `Alphabet ${sanitizedLetter} recognized`,
  }
}

export default function AirWriter({ busy, onGenerateTopic }) {
  // Session & Camera State
  const [sessionActive, setSessionActive] = useState(false)
  const [cameraState, setCameraState] = useState('off') // 'off', 'loading', 'active', 'error'
  const [trackingHand, setTrackingHand] = useState(false)
  const [recognizing, setRecognizing] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('Camera off. Click "Start Air Writing" to begin.')

  // Gesture Control Mode: 'gesture' (Pointing=Write, Open Hand=Hover) or 'continuous' (Always Write)
  const [trackingMode, setTrackingMode] = useState('gesture')
  const [penState, setPenState] = useState('hover') // 'write' or 'hover'

  // Sentence & Word Accumulation State
  const [completedWords, setCompletedWords] = useState([])
  const [currentWord, setCurrentWord] = useState('')
  const [currentSentence, setCurrentSentence] = useState('')
  const [currentLineIndex, setCurrentLineIndex] = useState(0) // 0..4

  // Manual topic override / editor
  const [editableTopic, setEditableTopic] = useState('')

  // Sensitivity & Auto-Recognize Speed Mode: '2200' (Relaxed), '3500' (Slow), 'manual' (Manual Only)
  const [autoDelayMode, setAutoDelayMode] = useState('2200')

  // Refs
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const cameraRef = useRef(null)
  const handsRef = useRef(null)
  const workerRef = useRef(null)
  
  // MULTI-STROKE STORAGE: Array of stroke arrays -> [ [p1, p2], [p3, p4] ]
  const strokesRef = useRef([])
  const smoothedPointRef = useRef(null)
  const lastPosRef = useRef(null)
  const sessionActiveRef = useRef(false)
  const trackingModeRef = useRef('gesture')
  const autoDelayModeRef = useRef('2200')
  const currentLineIndexRef = useRef(0)
  const inactivityTimerRef = useRef(null)
  const isRecognizingRef = useRef(false)
  const requestIdRef = useRef(0)

  useEffect(() => {
    sessionActiveRef.current = sessionActive
  }, [sessionActive])

  useEffect(() => {
    trackingModeRef.current = trackingMode
  }, [trackingMode])

  useEffect(() => {
    autoDelayModeRef.current = autoDelayMode
  }, [autoDelayMode])

  useEffect(() => {
    currentLineIndexRef.current = currentLineIndex
  }, [currentLineIndex])

  // Global Keyboard Shortcuts (Space & Backspace)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return
      if (e.code === 'Space') {
        e.preventDefault()
        handleAddSpaceWord()
      } else if (e.code === 'Backspace' && !e.repeat) {
        handleBackspaceWord()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [currentWord, completedWords])

  // Sync sentence updates to editable topic field
  useEffect(() => {
    const full = [currentSentence, currentWord].filter(Boolean).join(' ')
    setEditableTopic(full)
  }, [currentSentence, currentWord])

  function announce(msg) {
    setStatus(msg)
  }

  // ------------------------------------------------------------------
  // Main Hand Tracking & Multi-Stroke Rendering Callback
  // ------------------------------------------------------------------
  function handleResults(results, requestId) {
    if (requestId !== requestIdRef.current) return
    const landmarks = results.multiHandLandmarks?.[0]
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (!canvas || !context) return

    context.save()
    context.clearRect(0, 0, canvas.width, canvas.height)

    // 1. Render Digital Notebook Writing Lines (LINE 1 to 5)
    const lineMargin = 24
    const startYPercent = 0.22
    const lineSpacingPercent = 0.155

    for (let i = 0; i < TOTAL_WRITING_LINES; i++) {
      const lineY = canvas.height * (startYPercent + i * lineSpacingPercent)
      const isActiveLine = i === currentLineIndexRef.current

      context.beginPath()
      context.moveTo(lineMargin, lineY)
      context.lineTo(canvas.width - lineMargin, lineY)

      if (isActiveLine) {
        context.lineWidth = 3
        context.strokeStyle = '#45e8ff'
        context.shadowColor = '#45e8ff'
        context.shadowBlur = 10
        context.setLineDash([8, 6])
      } else {
        context.lineWidth = 1
        context.strokeStyle = 'rgba(255, 255, 255, 0.18)'
        context.shadowBlur = 0
        context.setLineDash([4, 4])
      }
      context.stroke()
      context.setLineDash([])

      // Line Label
      context.font = 'bold 11px system-ui, sans-serif'
      context.fillStyle = isActiveLine ? '#45e8ff' : 'rgba(168, 217, 235, 0.5)'
      context.textAlign = 'left'
      context.fillText(`LINE ${i + 1}${isActiveLine ? ' ◄ WRITE WORD HERE' : ''}`, lineMargin + 5, lineY - 6)
    }

    // 2. Process Fingertip Landmark & Hand Gesture (Mirrored coordinates)
    if (landmarks) {
      if (!trackingHand) setTrackingHand(true)

      const rawNormX = 1 - landmarks[8].x
      const rawNormY = landmarks[8].y

      // Ultra-Stable Exponential Smoothing (alpha = 0.20 for maximum stability & jitter reduction)
      if (!smoothedPointRef.current) {
        smoothedPointRef.current = { x: rawNormX, y: rawNormY }
      } else {
        const alpha = 0.20
        smoothedPointRef.current = {
          x: alpha * rawNormX + (1 - alpha) * smoothedPointRef.current.x,
          y: alpha * rawNormY + (1 - alpha) * smoothedPointRef.current.y,
        }
      }

      const normX = smoothedPointRef.current.x
      const normY = smoothedPointRef.current.y
      const canvasX = normX * canvas.width
      const canvasY = normY * canvas.height

      // Detect Gesture Mode: Track index finger continuously until hand is fully OPEN (Open Palm 🖐)
      let isWritingGesture = true
      if (trackingModeRef.current === 'gesture') {
        const isMiddleExtended = landmarks[12].y < landmarks[9].y
        const isRingExtended = landmarks[16].y < landmarks[13].y
        const isPinkyExtended = landmarks[20].y < landmarks[17].y
        const isOpenHand = isMiddleExtended && isRingExtended && isPinkyExtended

        // Track index finger continuously as long as hand is NOT open!
        isWritingGesture = !isOpenHand
      }

      const nextPenState = isWritingGesture ? 'write' : 'hover'
      setPenState(nextPenState)

      // Render Fingertip Reticle / Marker
      if (isWritingGesture) {
        // Glowing Blue Pen Tip (Writing Mode)
        context.shadowColor = '#45e8ff'
        context.shadowBlur = 18
        context.fillStyle = '#45e8ff'
        context.beginPath()
        context.arc(canvasX, canvasY, 9, 0, 2 * Math.PI)
        context.fill()
        context.lineWidth = 2.5
        context.strokeStyle = '#ffffff'
        context.stroke()
        context.shadowBlur = 0

        // "DRAWING" Badge
        context.font = 'bold 10px system-ui, sans-serif'
        context.fillStyle = '#45e8ff'
        context.textAlign = 'center'
        context.fillText('✍️ WRITING', canvasX, canvasY - 14)
      } else {
        // Dashed Cursor (Hover Mode - Moving finger without drawing line)
        context.beginPath()
        context.arc(canvasX, canvasY, 12, 0, 2 * Math.PI)
        context.strokeStyle = '#f4b95f'
        context.lineWidth = 2
        context.setLineDash([4, 4])
        context.stroke()
        context.setLineDash([])

        // "HOVERING" Badge
        context.font = '10px system-ui, sans-serif'
        context.fillStyle = '#f4b95f'
        context.textAlign = 'center'
        context.fillText('🖐 HOVER (Point to write)', canvasX, canvasY - 16)
      }

      // Collect Multi-Stroke Trajectory when writing gesture is active
      if (sessionActiveRef.current && isWritingGesture && !isRecognizingRef.current) {
        const newPoint = { x: normX, y: normY, t: Date.now() }

        if (strokesRef.current.length === 0) {
          strokesRef.current.push([newPoint])
        } else {
          const currentStroke = strokesRef.current[strokesRef.current.length - 1]
          const lastPoint = currentStroke[currentStroke.length - 1]

          const spatialDist = Math.hypot(newPoint.x - lastPoint.x, newPoint.y - lastPoint.y)
          const timeDiff = newPoint.t - lastPoint.t

          // STABLE STROKE SPLIT: Spatial jump > 0.055 or time gap > 450ms
          if (spatialDist > 0.055 || timeDiff > 450) {
            strokesRef.current.push([newPoint])
          } else {
            currentStroke.push(newPoint)
          }
        }

        // Controlled Auto-Recognize pause detector
        const mode = autoDelayModeRef.current
        if (mode !== 'manual') {
          const delayMs = parseInt(mode, 10) || 2200
          const allStrokesPoints = strokesRef.current.flat()
          const totalPoints = allStrokesPoints.length

          let minX = 1, maxX = 0, minY = 1, maxY = 0
          allStrokesPoints.forEach(p => {
            if (p.x < minX) minX = p.x
            if (p.x > maxX) maxX = p.x
            if (p.y < minY) minY = p.y
            if (p.y > maxY) maxY = p.y
          })
          const boundingSpan = Math.hypot(maxX - minX, maxY - minY)

          if (lastPosRef.current) {
            const dist = Math.hypot(normX - lastPosRef.current.x, normY - lastPosRef.current.y)
            // Require steady hand (dist < 0.008), at least 16 points, and substantial drawing size (boundingSpan >= 0.12)
            if (dist < 0.008 && totalPoints >= 16 && boundingSpan >= 0.12) {
              if (!inactivityTimerRef.current) {
                inactivityTimerRef.current = setTimeout(() => {
                  handleRecognizeTrajectory()
                }, delayMs)
              }
            } else {
              if (inactivityTimerRef.current) {
                clearTimeout(inactivityTimerRef.current)
                inactivityTimerRef.current = null
              }
            }
          }
          lastPosRef.current = { x: normX, y: normY }
        }
      }
    } else {
      if (trackingHand) setTrackingHand(false)
      smoothedPointRef.current = null
    }

    // 3. Render Independent Strokes (No diagonal cross-lines between disconnected strokes!)
    strokesRef.current.forEach((stroke) => {
      if (stroke.length > 1) {
        context.beginPath()
        context.lineWidth = 6
        context.strokeStyle = '#45e8ff'
        context.lineCap = 'round'
        context.lineJoin = 'round'
        context.shadowColor = '#45e8ff'
        context.shadowBlur = 12

        for (let i = 0; i < stroke.length; i++) {
          const px = stroke[i].x * canvas.width
          const py = stroke[i].y * canvas.height
          if (i === 0) context.moveTo(px, py)
          else context.lineTo(px, py)
        }
        context.stroke()
        context.shadowBlur = 0
      }
    })

    context.restore()
  }

  // ------------------------------------------------------------------
  // Camera Management
  // ------------------------------------------------------------------
  async function startCamera() {
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    setCameraState('loading')
    setError('')
    announce('Starting webcam and smart finger gesture engine...')

    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access is unavailable in this browser.')
      const video = videoRef.current
      const canvas = canvasRef.current
      canvas.width = VIDEO_WIDTH
      canvas.height = VIDEO_HEIGHT

      await loadScript('Camera', CAMERA_UTILS_URL)
      await loadScript('Hands', HANDS_URL)

      if (requestId !== requestIdRef.current) return

      const hands = new window.Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/${file}`,
      })
      hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.55,
        minTrackingConfidence: 0.55,
      })
      hands.onResults((results) => handleResults(results, requestId))
      handsRef.current = hands

      const camera = new window.Camera(video, {
        onFrame: async () => {
          if (requestId === requestIdRef.current && handsRef.current && videoRef.current) {
            try {
              await handsRef.current.send({ image: videoRef.current })
            } catch (_) {}
          }
        },
        width: VIDEO_WIDTH,
        height: VIDEO_HEIGHT,
      })
      cameraRef.current = camera
      await camera.start()

      if (requestId !== requestIdRef.current) {
        camera.stop()
        await hands.close()
        return
      }

      setCameraState('active')
      announce('Camera active. Point index finger to write; open hand to move without drawing.')
    } catch (startError) {
      if (requestId !== requestIdRef.current) return
      cameraRef.current?.stop()
      cameraRef.current = null
      void handsRef.current?.close()
      handsRef.current = null
      setCameraState('error')
      setError(`${startError.message} Check camera permissions.`)
      announce('Camera unavailable.')
    }
  }

  async function stopCamera() {
    requestIdRef.current += 1
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current)
    smoothedPointRef.current = null
    strokesRef.current = []
    cameraRef.current?.stop()
    cameraRef.current = null
    setTrackingHand(false)
    setSessionActive(false)
    setCameraState('off')
    announce('Camera turned off.')
  }

  // Toggle Continuous Air Writing Session
  async function toggleSession() {
    if (!sessionActive) {
      if (cameraState !== 'active') {
        await startCamera()
      }
      setSessionActive(true)
      strokesRef.current = []
      smoothedPointRef.current = null
      announce(`Air-writing session active on Line ${currentLineIndex + 1}. Point finger to write!`)
    } else {
      setSessionActive(false)
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current)
      announce('Air-writing session paused.')
    }
  }

  // ------------------------------------------------------------------
  // High-Precision Hybrid Recognition: FINAL PICTURE OCR + Trajectory AI
  // (Recognizes capital & lowercase letters, cursive, and multi-letter words)
  // ------------------------------------------------------------------
  async function handleRecognizeTrajectory() {
    if (isRecognizingRef.current) return

    // 1. CAPTURE THE FINAL PICTURE (Snapshot of all combined strokes)
    const strokeSnapshot = [...strokesRef.current]
    const allPoints = strokeSnapshot.flat()

    // 2. INSTANT VISUAL RESET: Clear strokes so screen stays clean!
    strokesRef.current = []
    smoothedPointRef.current = null
    lastPosRef.current = null
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current)
      inactivityTimerRef.current = null
    }

    let minX = 1, maxX = 0, minY = 1, maxY = 0
    allPoints.forEach(p => {
      if (p.x < minX) minX = p.x
      if (p.x > maxX) maxX = p.x
      if (p.y < minY) minY = p.y
      if (p.y > maxY) maxY = p.y
    })
    const boundingSpan = Math.hypot(maxX - minX, maxY - minY)

    if (allPoints.length < 14 || boundingSpan < 0.10) {
      announce('Stroke too short or quick. Trace an alphabet letter clearly in the air.')
      return
    }

    isRecognizingRef.current = true
    setRecognizing(true)
    announce('Analyzing final stroke picture with OCR Vision...')

    let recognizedText = ''

    // ENGINE 1: Image OCR Vision on the FINAL PICTURE (Strictly Alphabets A-Z, a-z — NO NUMBERS)
    try {
      const ocrImageCanvas = prepareOcrCanvasFromStrokes(strokeSnapshot)
      if (ocrImageCanvas) {
        if (!workerRef.current) {
          const worker = await createWorker('eng')
          workerRef.current = worker
        }
        await workerRef.current.setParameters({
          tessedit_char_whitelist: 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
          tessedit_pageseg_mode: '6',
        })
        const ocrResult = await workerRef.current.recognize(ocrImageCanvas)
        if (ocrResult && ocrResult.data && ocrResult.data.text) {
          const rawOcrText = ocrResult.data.text
            .replace(/[^a-zA-Z\s]/g, '') // STRICT ALPHABET ONLY - REMOVE ALL NUMBERS & SYMBOLS
            .replace(/\s+/g, ' ')
            .trim()

          if (rawOcrText && rawOcrText.length > 0) {
            recognizedText = rawOcrText
          }
        }
      }
    } catch (ocrErr) {
      console.warn('OCR vision error:', ocrErr)
    }

    // ENGINE 2: Dual Backend API + Local Geometric Trajectory Classifier Fallback
    if (!recognizedText) {
      try {
        const response = await fetch('/api/air-writing/recognize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ trajectory: allPoints }),
        })
        if (response.ok) {
          const data = await response.json()
          if (data && data.success && data.letter) {
            recognizedText = String(data.letter).replace(/[^a-zA-Z\s]/g, '')
          }
        }
      } catch (_) {}

      if (!recognizedText) {
        const geomResult = classifyLocalTrajectory(allPoints)
        if (geomResult.success && geomResult.letter) {
          recognizedText = String(geomResult.letter).replace(/[^a-zA-Z\s]/g, '')
        }
      }
    }

    // Enforce strict alphabet restriction on final output
    if (recognizedText) {
      recognizedText = recognizedText.replace(/[^a-zA-Z\s]/g, '').trim()
    }

    isRecognizingRef.current = false
    setRecognizing(false)

    if (recognizedText) {
      setCurrentWord(prev => (prev ? prev + ' ' + recognizedText : recognizedText))
      announce(`Recognized: "${recognizedText}". Ready for next stroke or word space!`)
    } else {
      announce('Could not read letter. Try drawing an alphabet (A-Z, a-z) clearly in the air.')
    }
  }

  // Commit Word / Space: Advances to fresh notebook line and resets starting stroke!
  function handleAddSpaceWord() {
    if (!currentWord.trim() && strokesRef.current.length === 0) return

    const wordToAdd = currentWord.trim()
    if (wordToAdd) {
      setCompletedWords(prev => {
        const updated = [...prev, wordToAdd]
        setCurrentSentence(updated.join(' '))
        return updated
      })
      setCurrentWord('')
    }

    // Reset Visual Strokes & Advance Writing Line for Fresh Word Start
    strokesRef.current = []
    smoothedPointRef.current = null
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current)

    setCurrentLineIndex(prev => (prev + 1) % TOTAL_WRITING_LINES)
    announce(`Word committed! Moved to Line ${((currentLineIndex + 1) % TOTAL_WRITING_LINES) + 1} for next word.`)
  }

  function handleBackspaceWord() {
    if (currentWord) {
      setCurrentWord(prev => prev.slice(0, -1))
      announce('Deleted last letter.')
    } else if (completedWords.length > 0) {
      const updated = completedWords.slice(0, -1)
      setCompletedWords(updated)
      setCurrentSentence(updated.join(' '))
      announce('Deleted last word.')
    }
  }

  function handleClearAll() {
    setCurrentWord('')
    setCompletedWords([])
    setCurrentSentence('')
    setEditableTopic('')
    strokesRef.current = []
    smoothedPointRef.current = null
    setCurrentLineIndex(0)
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current)
    announce('Cleared all text and visual strokes.')
  }

  function handleGenerateSubmittedTopic() {
    const finalTopic = editableTopic.trim() || [currentSentence, currentWord].filter(Boolean).join(' ').trim()
    if (!finalTopic) {
      announce('Please write or enter a topic first.')
      return
    }
    onGenerateTopic(finalTopic)
  }

  useEffect(() => () => {
    requestIdRef.current += 1
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current)
    cameraRef.current?.stop()
    void handsRef.current?.close()
    if (workerRef.current) {
      void workerRef.current.terminate()
    }
  }, [])

  const fullLiveText = [currentSentence, currentWord].filter(Boolean).join(' ')

  return (
    <section className="airwriter-panel" aria-label="Continuous Air-Writing Studio">
      <header className="airwriter-heading">
        <div>
          <p className="eyebrow">Continuous Air-Writing Notebook Studio</p>
          <h2>Write continuous words with clean strokes</h2>
        </div>
        <span className={`airwriter-state state-${cameraState}`} role="status">
          {sessionActive
            ? penState === 'write'
              ? '✍️ Writing Mode'
              : '🖐 Hover Mode (Open Hand)'
            : cameraState === 'active'
            ? 'Camera Ready'
            : cameraState === 'loading'
            ? 'Starting Camera'
            : cameraState === 'error'
            ? 'Camera Error'
            : 'Camera Off'}
        </span>
      </header>

      <p className="airwriter-instructions">
        <strong>Gesture Controls:</strong> Point index finger 👆 to write. Open hand 🖐 to move cursor without drawing line.
        <strong>Alphabet-Only Precision Mode:</strong> Exclusively recognizes capital (A-Z) and lowercase (a-z) letters. Number detection is disabled for maximum alphabet accuracy!
      </p>

      {/* Mode & Auto-Capture Delay Selectors */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '14px', alignItems: 'center' }}>
        <span style={{ fontSize: '0.82rem', color: '#a8c6d5' }}>Tracking Mode:</span>
        <button
          className={trackingMode === 'gesture' ? 'primary' : 'secondary'}
          style={{ minHeight: '32px', fontSize: '0.8rem', padding: '4px 12px' }}
          onClick={() => setTrackingMode('gesture')}
        >
          👆 Smart Gesture (Index=Write, Open=Hover)
        </button>
        <button
          className={trackingMode === 'continuous' ? 'primary' : 'secondary'}
          style={{ minHeight: '32px', fontSize: '0.8rem', padding: '4px 12px' }}
          onClick={() => setTrackingMode('continuous')}
        >
          ✏️ Always Draw
        </button>

        <span style={{ fontSize: '0.82rem', color: '#a8c6d5', marginLeft: '12px' }}>Auto Capture Speed:</span>
        <button
          className={autoDelayMode === '2200' ? 'primary' : 'secondary'}
          style={{ minHeight: '32px', fontSize: '0.8rem', padding: '4px 12px' }}
          onClick={() => setAutoDelayMode('2200')}
        >
          🐢 Relaxed (2.2s Pause)
        </button>
        <button
          className={autoDelayMode === '3500' ? 'primary' : 'secondary'}
          style={{ minHeight: '32px', fontSize: '0.8rem', padding: '4px 12px' }}
          onClick={() => setAutoDelayMode('3500')}
        >
          🧘 Slow (3.5s Pause)
        </button>
        <button
          className={autoDelayMode === 'manual' ? 'primary' : 'secondary'}
          style={{ minHeight: '32px', fontSize: '0.8rem', padding: '4px 12px' }}
          onClick={() => setAutoDelayMode('manual')}
        >
          🎯 Manual Button Only
        </button>
      </div>

      {/* Camera Viewport Stage */}
      <div className="airwriter-stage">
        <video
          ref={videoRef}
          className="airwriter-video"
          autoPlay
          muted
          playsInline
          aria-label="Webcam feed for index finger tracking"
        />
        <canvas
          ref={canvasRef}
          className="airwriter-canvas"
          aria-label="Live index-finger notebook trail"
          role="img"
        />

        {cameraState !== 'active' && (
          <div className="airwriter-placeholder">
            {cameraState === 'loading' ? 'Initializing Hand Tracker & Gesture Engine…' : 'Camera preview will appear here'}
          </div>
        )}

        <div className="tracking-reticle" aria-hidden="true" />
      </div>

      <p className="airwriter-status" role="status" aria-live="polite">
        {status}
      </p>

      {error && <p className="notice airwriter-error">{error}</p>}

      {/* Control Buttons */}
      <div className="airwriter-controls">
        {cameraState !== 'active' ? (
          <button className="primary" onClick={startCamera} disabled={busy || cameraState === 'loading'}>
            📷 Enable Camera
          </button>
        ) : (
          <button
            className={sessionActive ? 'secondary' : 'primary'}
            onClick={toggleSession}
            disabled={busy}
          >
            {sessionActive ? '⏸ Pause Writing Session' : '▶ Start Air Writing'}
          </button>
        )}

        {cameraState === 'active' && (
          <button className="secondary" onClick={stopCamera} disabled={busy}>
            🛑 Stop Camera
          </button>
        )}

        <button
          className="secondary"
          onClick={handleRecognizeTrajectory}
          disabled={busy || recognizing || !sessionActive}
        >
          {recognizing ? '✨ Recognizing Picture…' : '✨ Recognize Stroke Picture'}
        </button>

        <button className="secondary" onClick={handleAddSpaceWord} disabled={busy}>
          ␣ Add Word / Space (Line {currentLineIndex + 1})
        </button>

        <button className="secondary" onClick={handleBackspaceWord} disabled={busy}>
          ⌫ Backspace
        </button>

        <button className="secondary" onClick={handleClearAll} disabled={busy}>
          🗑 Clear All
        </button>
      </div>

      {/* Live Sentence Display & Topic Generator Form */}
      <div className="airwriter-topic-editor" style={{ marginTop: '16px' }}>
        <label className="airwriter-topic-label" htmlFor="airwriter-topic-input">
          Recognized Topic / Sentence:
        </label>
        <div className="airwriter-submit-row">
          <input
            id="airwriter-topic-input"
            value={editableTopic}
            onChange={(e) => setEditableTopic(e.target.value)}
            placeholder="Continuous air-written letters will appear here..."
            maxLength={200}
          />
          <button
            className="primary"
            onClick={handleGenerateSubmittedTopic}
            disabled={busy || (!editableTopic.trim() && !fullLiveText)}
          >
            {busy ? 'Generating…' : 'Generate lesson'}
          </button>
        </div>
      </div>

      <p className="airwriter-footnote">
        💡 <strong>Tip:</strong> You can trace multi-stroke characters and words across notebook lines! The engine captures the <strong>FINAL PICTURE</strong> with high-precision vision tuned exclusively for capital & lowercase alphabets.
      </p>
    </section>
  )
}