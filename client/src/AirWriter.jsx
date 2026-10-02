import { useEffect, useRef, useState } from 'react'
import { createWorker } from 'tesseract.js'

const VIDEO_WIDTH = 640
const VIDEO_HEIGHT = 480
const IDLE_DELAY = 1200
const CAMERA_UTILS_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3.1675466862/camera_utils.js'
const HANDS_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/hands.js'

function loadScript(globalName, source) {
  if (window[globalName]) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = source
    script.crossOrigin = 'anonymous'
    script.onload = () => window[globalName] ? resolve() : reject(new Error(`MediaPipe did not expose ${globalName}.`))
    script.onerror = () => reject(new Error(`Could not load MediaPipe ${globalName}.`))
    document.head.appendChild(script)
  })
}

function prepareOcrCanvas(sourceCanvas, bounds) {
  const margin = 28
  const left = Math.max(0, Math.floor(bounds.minX - margin))
  const top = Math.max(0, Math.floor(bounds.minY - margin))
  const right = Math.min(sourceCanvas.width, Math.ceil(bounds.maxX + margin))
  const bottom = Math.min(sourceCanvas.height, Math.ceil(bounds.maxY + margin))
  const width = Math.max(1, right - left)
  const height = Math.max(1, bottom - top)
  const sourceContext = sourceCanvas.getContext('2d', { willReadFrequently: true })
  const sourcePixels = sourceContext.getImageData(left, top, width, height)
  const binaryCanvas = document.createElement('canvas')
  binaryCanvas.width = width
  binaryCanvas.height = height
  const binaryContext = binaryCanvas.getContext('2d')
  const binaryPixels = binaryContext.createImageData(width, height)

  for (let index = 0; index < sourcePixels.data.length; index += 4) {
    const isStroke = sourcePixels.data[index + 3] > 32
    const color = isStroke ? 12 : 255
    binaryPixels.data[index] = color
    binaryPixels.data[index + 1] = color
    binaryPixels.data[index + 2] = color
    binaryPixels.data[index + 3] = 255
  }
  binaryContext.putImageData(binaryPixels, 0, 0)

  const scaledCanvas = document.createElement('canvas')
  scaledCanvas.width = width * 3
  scaledCanvas.height = height * 3
  scaledCanvas.getContext('2d').drawImage(binaryCanvas, 0, 0, scaledCanvas.width, scaledCanvas.height)
  return scaledCanvas
}

export default function AirWriter({ busy, onGenerateTopic }) {
  const [cameraState, setCameraState] = useState('off')
  const [strokeReady, setStrokeReady] = useState(false)
  const [hasStroke, setHasStroke] = useState(false)
  const [trackingHand, setTrackingHand] = useState(false)
  const [recognizing, setRecognizing] = useState(false)
  const [topic, setTopic] = useState('')
  const [status, setStatus] = useState('Camera off. Start tracking to write in the air.')
  const [error, setError] = useState('')
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const cameraRef = useRef(null)
  const handsRef = useRef(null)
  const workerRef = useRef(null)
  const previousPointRef = useRef(null)
  const boundsRef = useRef(null)
  const hasStrokeRef = useRef(false)
  const strokeReadyRef = useRef(false)
  const trackingHandRef = useRef(false)
  const idleTimerRef = useRef(null)
  const requestIdRef = useRef(0)
  const statusRef = useRef(status)

  function announce(nextStatus) {
    if (statusRef.current !== nextStatus) {
      statusRef.current = nextStatus
      setStatus(nextStatus)
    }
  }

  function handleResults(results, requestId) {
    if (requestId !== requestIdRef.current) return
    const landmarks = results.multiHandLandmarks?.[0]
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (!landmarks || !context) {
      previousPointRef.current = null
      if (trackingHandRef.current) {
        trackingHandRef.current = false
        setTrackingHand(false)
      }
      if (hasStrokeRef.current && !strokeReadyRef.current) announce('Hand out of frame. Your stroke is preserved.')
      return
    }

    if (!trackingHandRef.current) {
      trackingHandRef.current = true
      setTrackingHand(true)
    }
    const tip = landmarks[8]
    const point = { x: (1 - tip.x) * canvas.width, y: tip.y * canvas.height }
    const previous = previousPointRef.current

    if (!previous) {
      previousPointRef.current = point
      return
    }

    const distance = Math.hypot(point.x - previous.x, point.y - previous.y)
    if (distance > 2) {
      context.beginPath()
      context.moveTo(previous.x, previous.y)
      context.lineTo(point.x, point.y)
      context.strokeStyle = '#45e8ff'
      context.lineWidth = 8
      context.lineCap = 'round'
      context.lineJoin = 'round'
      context.shadowColor = '#45e8ff'
      context.shadowBlur = 10
      context.stroke()
      context.shadowBlur = 0

      boundsRef.current = boundsRef.current
        ? {
            minX: Math.min(boundsRef.current.minX, previous.x, point.x),
            minY: Math.min(boundsRef.current.minY, previous.y, point.y),
            maxX: Math.max(boundsRef.current.maxX, previous.x, point.x),
            maxY: Math.max(boundsRef.current.maxY, previous.y, point.y),
          }
        : {
            minX: Math.min(previous.x, point.x),
            minY: Math.min(previous.y, point.y),
            maxX: Math.max(previous.x, point.x),
            maxY: Math.max(previous.y, point.y),
          }
      if (!hasStrokeRef.current) {
        hasStrokeRef.current = true
        setHasStroke(true)
      }
      if (strokeReadyRef.current) {
        strokeReadyRef.current = false
        setStrokeReady(false)
      }
      announce('Writing in progress. Pause briefly to finish the stroke.')
      window.clearTimeout(idleTimerRef.current)
      idleTimerRef.current = window.setTimeout(() => {
        strokeReadyRef.current = true
        setStrokeReady(true)
        announce('Stroke paused. Ready to recognize your writing.')
      }, IDLE_DELAY)
    }
    previousPointRef.current = point
  }

  async function startTracking() {
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    setCameraState('loading')
    setError('')
    announce('Requesting camera access and loading hand tracking.')

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
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
      })
      hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.65,
        minTrackingConfidence: 0.55,
      })
      hands.onResults((results) => handleResults(results, requestId))
      handsRef.current = hands

      const camera = new window.Camera(video, {
        onFrame: async () => {
          if (requestId === requestIdRef.current) await hands.send({ image: video })
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
      announce('Camera ready. Raise one index finger and trace block letters.')
    } catch (startError) {
      if (requestId !== requestIdRef.current) return
      cameraRef.current?.stop()
      cameraRef.current = null
      await handsRef.current?.close()
      handsRef.current = null
      setCameraState('error')
      setError(`${startError.message} Check camera permission and network access.`)
      announce('Camera unavailable.')
    }
  }

  async function stopTracking() {
    requestIdRef.current += 1
    window.clearTimeout(idleTimerRef.current)
    previousPointRef.current = null
    cameraRef.current?.stop()
    cameraRef.current = null
    await handsRef.current?.close()
    handsRef.current = null
    trackingHandRef.current = false
    setTrackingHand(false)
    setCameraState('off')
    strokeReadyRef.current = Boolean(boundsRef.current)
    setStrokeReady(strokeReadyRef.current)
    announce(boundsRef.current ? 'Tracking stopped. Your writing is preserved.' : 'Camera off.')
  }

  function clearStroke() {
    const canvas = canvasRef.current
    canvas?.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height)
    boundsRef.current = null
    previousPointRef.current = null
    hasStrokeRef.current = false
    strokeReadyRef.current = false
    window.clearTimeout(idleTimerRef.current)
    setHasStroke(false)
    setStrokeReady(false)
    setTopic('')
    announce(cameraState === 'active' ? 'Canvas cleared. Ready for a new word.' : 'Canvas cleared.')
  }

  async function recognizeStroke() {
    if (!canvasRef.current || !boundsRef.current || recognizing) return
    setRecognizing(true)
    setError('')
    announce('Reading your air-written text.')
    try {
      if (!workerRef.current) workerRef.current = await createWorker('eng')
      const image = prepareOcrCanvas(canvasRef.current, boundsRef.current)
      const result = await workerRef.current.recognize(image)
      const recognizedTopic = result.data.text
        .replace(/[^a-zA-Z0-9\s'-]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 120)
      if (!recognizedTopic) {
        announce('Could not read that stroke. Try larger block letters or type the topic below.')
        return
      }
      setTopic(recognizedTopic)
      setStrokeReady(true)
      announce(`Recognized: ${recognizedTopic}. Review or edit it before generating.`)
    } catch (recognitionError) {
      setError(`Text recognition failed: ${recognitionError.message}`)
      announce('Text recognition failed. You can enter the topic manually.')
    } finally {
      setRecognizing(false)
    }
  }

  useEffect(() => () => {
    requestIdRef.current += 1
    window.clearTimeout(idleTimerRef.current)
    cameraRef.current?.stop()
    void handsRef.current?.close()
    void workerRef.current?.terminate()
  }, [])

  return (
    <section className="airwriter-panel" aria-label="Air-writing and finger tracking">
      <header className="airwriter-heading">
        <div>
          <p className="eyebrow">Air-writing lab</p>
          <h2>Write a topic in the air</h2>
        </div>
        <span className={`airwriter-state state-${cameraState}`} role="status">{cameraState === 'active' ? (trackingHand ? 'Finger tracked' : 'Tracking ready') : cameraState === 'loading' ? 'Starting camera' : cameraState === 'error' ? 'Camera unavailable' : 'Camera off'}</span>
      </header>
      <p className="airwriter-instructions">Allow camera access, then use your index fingertip to write one large block word from left to right. Pause to finish; OCR will suggest editable text.</p>
      <div className="airwriter-stage">
        <video ref={videoRef} className="airwriter-video" autoPlay muted playsInline aria-label="Webcam feed for finger tracking" />
        <canvas ref={canvasRef} className="airwriter-canvas" aria-label="Live index-finger trail" role="img" />
        {cameraState !== 'active' && <div className="airwriter-placeholder">{cameraState === 'loading' ? 'Waiting for camera…' : 'Camera preview will appear here'}</div>}
        <div className="tracking-reticle" aria-hidden="true" />
      </div>
      <p className="airwriter-status" role="status" aria-live="polite">{status}</p>
      {error && <p className="notice airwriter-error" role="alert">{error}</p>}
      <div className="airwriter-controls">
        {cameraState === 'active'
          ? <button className="secondary" onClick={stopTracking}>Stop tracking</button>
          : cameraState === 'loading'
            ? <button className="secondary" onClick={stopTracking}>Cancel setup</button>
            : <button className="secondary" onClick={startTracking}>Start tracking</button>}
        <button className="secondary" onClick={clearStroke} disabled={!hasStroke}>Clear</button>
        <button className="secondary" onClick={recognizeStroke} disabled={!hasStroke || recognizing}>{recognizing ? 'Recognizing…' : strokeReady ? 'Recognize finished stroke' : 'Recognize writing'}</button>
      </div>
      <label className="airwriter-topic-label" htmlFor="airwriter-topic">Recognized topic (edit if needed)</label>
      <div className="airwriter-submit-row">
        <input id="airwriter-topic" value={topic} onChange={(event) => setTopic(event.target.value)} maxLength={120} placeholder="Write a word or enter a topic" />
        <button className="primary" onClick={() => onGenerateTopic(topic.trim())} disabled={!topic.trim() || busy}>{busy ? 'Generating…' : 'Generate lesson'}</button>
      </div>
      <p className="airwriter-footnote">Recognition is a best-effort OCR suggestion. Check the topic text before sending it to the lesson generator.</p>
    </section>
  )
}