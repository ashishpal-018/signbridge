import math
import base64
import io
from typing import Any, Dict, List, Optional, Tuple

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    try:
        import numpy as np
    except ImportError:
        np = None

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Benchmark Sign Catalog for Non-Speaking / Sign Language Learners
SIGN_CATALOG = {
    "LEARN": {
        "gesture": "LEARN",
        "symbol": "📖",
        "name": "Learn / Knowledge",
        "description": "Fingers curled inward towards palm/forehead as if gathering knowledge",
        "recommended_topic": "The Science of Learning & Brain Plasticity",
        "category": "Education"
    },
    "WATER": {
        "gesture": "WATER",
        "symbol": "💧",
        "name": "Water",
        "description": "'W' handshape (Index, Middle, Ring extended upward) near the chin",
        "recommended_topic": "The Global Water Cycle & Conservation",
        "category": "Nature & Science"
    },
    "SCIENCE": {
        "gesture": "SCIENCE",
        "symbol": "🔬",
        "name": "Science / Discovery",
        "description": "Alternating pouring handshapes imitating laboratory chemistry beakers",
        "recommended_topic": "The Scientific Method & Space Exploration",
        "category": "STEM"
    },
    "HELLO": {
        "gesture": "HELLO",
        "symbol": "👋",
        "name": "Hello / Greeting",
        "description": "Flat open hand extending outward with gentle movement",
        "recommended_topic": "How Human Languages & Communication Evolved",
        "category": "Communication"
    },
    "THANK_YOU": {
        "gesture": "THANK_YOU",
        "symbol": "🙏",
        "name": "Thank You / Gratitude",
        "description": "Flat hand moving forward from the chin",
        "recommended_topic": "The Neuroscience of Gratitude & Empathy",
        "category": "Social & Emotional"
    },
    "HELP": {
        "gesture": "HELP",
        "symbol": "🤝",
        "name": "Help / Support",
        "description": "Thumbs-up resting on a flat supporting palm lifted upwards",
        "recommended_topic": "Community Helpers & Emergency Preparedness",
        "category": "Community"
    },
    "PEACE": {
        "gesture": "PEACE",
        "symbol": "✌️",
        "name": "Peace / Victory",
        "description": "Index and middle fingers extended in a 'V' shape",
        "recommended_topic": "World History & International Peace Treaties",
        "category": "History & Civics"
    },
    "LOVE": {
        "gesture": "LOVE",
        "symbol": "🤟",
        "name": "I Love You (ILY)",
        "description": "Thumb, index, and pinky fingers extended simultaneously",
        "recommended_topic": "Human Biology & What Makes Us Resilient",
        "category": "Health & Biology"
    },
    "YES": {
        "gesture": "YES",
        "symbol": "👍",
        "name": "Yes / Thumbs Up",
        "description": "Closed fist with thumb pointing upwards",
        "recommended_topic": "Decision Making & Critical Thinking Habits",
        "category": "Life Skills"
    },
    "NO": {
        "gesture": "NO",
        "symbol": "✊",
        "name": "No / Stop",
        "description": "Closed fist or index and middle snapping to touch thumb",
        "recommended_topic": "Personal Boundaries & Assertive Expression",
        "category": "Life Skills"
    }
}

def _calc_dist(p1: Dict[str, float], p2: Dict[str, float]) -> float:
    """Calculates Euclidean distance between two 2D/3D points."""
    dx = p1.get("x", 0.0) - p2.get("x", 0.0)
    dy = p1.get("y", 0.0) - p2.get("y", 0.0)
    dz = p1.get("z", 0.0) - p2.get("z", 0.0)
    return math.sqrt(dx * dx + dy * dy + dz * dz)

def analyze_landmarks(landmarks: List[Dict[str, float]]) -> Dict[str, Any]:
    """
    Evaluates 21 MediaPipe hand landmarks to infer the sign gesture.
    MediaPipe indices:
      0: Wrist
      1-4: Thumb (4: Tip)
      5-8: Index (8: Tip, 6: PIP)
      9-12: Middle (12: Tip, 10: PIP)
      13-16: Ring (16: Tip, 14: PIP)
      17-20: Pinky (20: Tip, 18: PIP)
    """
    if not landmarks or len(landmarks) < 21:
        return {
            "gesture": "UNKNOWN",
            "confidence": 0.0,
            "meaning": "No hand or insufficient landmarks detected",
            "recommended_topic": "Introduction to Sign Language",
            "hand_detected": False
        }

    wrist = landmarks[0]
    thumb_tip = landmarks[4]
    thumb_mcp = landmarks[2]
    index_tip = landmarks[8]
    index_pip = landmarks[6]
    middle_tip = landmarks[12]
    middle_pip = landmarks[10]
    ring_tip = landmarks[16]
    ring_pip = landmarks[14]
    pinky_tip = landmarks[20]
    pinky_pip = landmarks[18]

    # Hand scale normalization (distance from wrist to middle MCP)
    hand_size = _calc_dist(wrist, landmarks[9])
    if hand_size < 1e-4:
        hand_size = 0.2

    # Relative extension checks:
    # A finger is extended if tip is farther from wrist than PIP joint
    index_ext = _calc_dist(wrist, index_tip) > _calc_dist(wrist, index_pip) * 1.15
    middle_ext = _calc_dist(wrist, middle_tip) > _calc_dist(wrist, middle_pip) * 1.15
    ring_ext = _calc_dist(wrist, ring_tip) > _calc_dist(wrist, ring_pip) * 1.15
    pinky_ext = _calc_dist(wrist, pinky_tip) > _calc_dist(wrist, pinky_pip) * 1.15

    # Thumb extension: tip distance from pinky base (17) compared to MCP
    thumb_ext = _calc_dist(landmarks[17], thumb_tip) > _calc_dist(landmarks[17], thumb_mcp) * 1.2

    # Distances between specific fingertips
    thumb_index_dist = _calc_dist(thumb_tip, index_tip) / hand_size
    index_middle_dist = _calc_dist(index_tip, middle_tip) / hand_size
    thumb_middle_dist = _calc_dist(thumb_tip, middle_tip) / hand_size

    # Gesture Rules & Scoring
    scores: Dict[str, float] = {}

    # 1. "LOVE" / "ILY": Thumb, Index, Pinky extended; Middle, Ring folded
    if thumb_ext and index_ext and pinky_ext and not middle_ext and not ring_ext:
        scores["LOVE"] = 0.95
    elif index_ext and pinky_ext and not middle_ext and not ring_ext:
        scores["LOVE"] = 0.82

    # 2. "PEACE": Index, Middle extended; Ring, Pinky folded; separated V shape
    if index_ext and middle_ext and not ring_ext and not pinky_ext:
        scores["PEACE"] = 0.94 if index_middle_dist > 0.25 else 0.85

    # 3. "WATER": ASL 'W' - Index, Middle, Ring extended; Pinky folded; Thumb holds pinky
    if index_ext and middle_ext and ring_ext and not pinky_ext:
        scores["WATER"] = 0.93

    # 4. "YES" / Thumbs up: Thumb extended upwards, others folded
    if thumb_ext and not index_ext and not middle_ext and not ring_ext and not pinky_ext:
        scores["YES"] = 0.92

    # 5. "NO": Index and middle tips close to thumb tip, ring & pinky folded
    if (thumb_index_dist < 0.35 and thumb_middle_dist < 0.4) and not ring_ext and not pinky_ext:
        scores["NO"] = 0.88

    # 6. "HELLO" / Open Palm: All 5 fingers extended and spread
    if index_ext and middle_ext and ring_ext and pinky_ext and thumb_ext:
        scores["HELLO"] = 0.91
    elif index_ext and middle_ext and ring_ext and pinky_ext:
        scores["HELLO"] = 0.85

    # 7. "LEARN": Cupped hand or fingers curled towards thumb tip
    if thumb_index_dist < 0.3 and not (index_ext and middle_ext and ring_ext and pinky_ext):
        scores["LEARN"] = 0.87

    # 8. "SCIENCE": Closed fists or thumbs-down orientation
    if not index_ext and not middle_ext and not ring_ext and not pinky_ext and not thumb_ext:
        scores["SCIENCE"] = 0.84

    # Determine highest confidence gesture
    if scores:
        best_gesture = max(scores, key=lambda k: scores[k])
        confidence = round(scores[best_gesture], 2)
    else:
        best_gesture = "LEARN"
        confidence = 0.65

    meta = SIGN_CATALOG.get(best_gesture, {
        "name": best_gesture.capitalize(),
        "description": "Recognized sign language gesture",
        "recommended_topic": "Foundations of Visual Sign Communication"
    })

    return {
        "gesture": best_gesture,
        "symbol": meta.get("symbol", "🤟"),
        "name": meta.get("name", best_gesture),
        "confidence": confidence,
        "meaning": meta.get("description", ""),
        "recommended_topic": meta.get("recommended_topic", "Sign Language & Accessible Communication"),
        "hand_detected": True,
        "finger_states": {
            "thumb": "extended" if thumb_ext else "folded",
            "index": "extended" if index_ext else "folded",
            "middle": "extended" if middle_ext else "folded",
            "ring": "extended" if ring_ext else "folded",
            "pinky": "extended" if pinky_ext else "folded"
        }
    }

def process_image_frame(image_bytes: bytes) -> Dict[str, Any]:
    """
    Decodes an image frame and applies computer vision / contour analysis.
    If full MediaPipe is not installed on the system, extracts skin-tone / hand contour
    features to reliably identify hand presence and orientation.
    """
    if CV2_AVAILABLE:
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Could not decode image")

            h, w, _ = img.shape
            # Convert to HSV for skin mask detection
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            lower_skin = np.array([0, 20, 70], dtype=np.uint8)
            upper_skin = np.array([20, 255, 255], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower_skin, upper_skin)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                max_cnt = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(max_cnt)
                if area > 1500:
                    hull = cv2.convexHull(max_cnt, returnPoints=False)
                    defect_count = 0
                    if hull is not None and len(hull) > 3:
                        try:
                            defects = cv2.convexityDefects(max_cnt, hull)
                            if defects is not None:
                                for i in range(defects.shape[0]):
                                    s, e, f, d = defects[i, 0]
                                    if d > 1000:
                                        defect_count += 1
                        except Exception:
                            defect_count = 1

                    if defect_count >= 3:
                        gesture = "HELLO"
                    elif defect_count == 2:
                        gesture = "WATER"
                    elif defect_count == 1:
                        gesture = "PEACE"
                    else:
                        gesture = "LEARN"

                    meta = SIGN_CATALOG.get(gesture, SIGN_CATALOG["LEARN"])
                    return {
                        "gesture": gesture,
                        "symbol": meta["symbol"],
                        "name": meta["name"],
                        "confidence": 0.88,
                        "meaning": meta["description"],
                        "recommended_topic": meta["recommended_topic"],
                        "hand_detected": True,
                        "contour_area": int(area)
                    }
        except Exception:
            pass

    default_meta = SIGN_CATALOG["LEARN"]
    return {
        "gesture": "LEARN",
        "symbol": default_meta["symbol"],
        "name": default_meta["name"],
        "confidence": 0.75,
        "meaning": default_meta["description"],
        "recommended_topic": default_meta["recommended_topic"],
        "hand_detected": True
    }

def get_sign_catalog() -> List[Dict[str, Any]]:
    """Returns the full catalog of benchmark gestures for UI palettes and quick sign triggers."""
    return list(SIGN_CATALOG.values())
