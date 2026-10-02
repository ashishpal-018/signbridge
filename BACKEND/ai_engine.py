import json
import os
from typing import Any, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from dotenv import load_dotenv

# Explicitly load .env from the root SIGNBRIDGE folder or current directory
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
load_dotenv(dotenv_path=dotenv_path)
load_dotenv()

SUPPORTED_MODES = {"blind", "deaf", "sign", "non_speaking"}

def _call_ollama(messages: List[dict], max_tokens: int = 500) -> str:
    """Calls the locally hosted Ollama chat API."""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:3b").strip()
    timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    request_body = json.dumps({
        "model": model_name,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.7},
    }).encode("utf-8")
    request = Request(
        f"{base_url}/api/chat",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            result: Any = json.loads(response.read().decode("utf-8"))
        content = result.get("message", {}).get("content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()
        return "Ollama returned an empty response. Check the selected model and try again."
    except HTTPError as error:
        if error.code == 404:
            return f"Ollama model '{model_name}' was not found. Pull it with: ollama pull {model_name}"
        details = error.read().decode("utf-8", errors="replace").strip()
        return f"Ollama request failed ({error.code}): {details or error.reason}"
    except URLError:
        return f"Ollama is not reachable at {base_url}. Start the Ollama service and try again."
    except TimeoutError:
        return f"Ollama did not respond within {timeout:g} seconds. Try a smaller model or increase OLLAMA_TIMEOUT_SECONDS."
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return f"Ollama returned an invalid response: {error}"

def generate_lesson(topic: str, mode: str = "blind") -> str:
    """Generates an accessible, tailored lesson for blind, deaf, or sign-language learners."""
    topic = topic.strip()
    if not topic:
        return "Please enter a topic to generate a lesson."
    if mode not in SUPPORTED_MODES:
        return "Unsupported learning mode. Choose blind, deaf, or sign."

    if mode == "blind":
        prompt = (
            f"Explain the topic '{topic}' concisely for a blind student. "
            "Keep sentences flowing smoothly, avoid complex visual formatting symbols or tables, "
            "and make it sound engaging and clear when read aloud by a screen reader or text-to-speech."
        )
    elif mode in {"deaf", "non_speaking"}:
        prompt = (
            f"Explain the topic '{topic}' for a deaf or non-speaking student. "
            "Format the response with clear headings, bullet points, and simplified definitions "
            "optimized for a visual reading dashboard and accessible visual comprehension."
        )
    else:
        prompt = (
            f"Explain the topic '{topic}' for a sign-language learner. "
            "Use short, clear visual explanations, concrete examples, and step-by-step guidance that works well "
            "for a learner who depends on gesture-based communication and visual reinforcement."
        )

    return _call_ollama([{"role": "user", "content": prompt}], max_tokens=550)

def generate_quiz(topic: str, lesson: str = "") -> str:
    """Generates a 3-question knowledge check multiple-choice quiz."""
    topic = topic.strip()
    if not topic:
        return "Please provide a topic to generate a quiz."

    prompt = (
        f"Based on the subject '{topic}', create a clear 3-question multiple-choice quiz. "
        "For each question, provide 4 options (A, B, C, D), and at the very bottom provide an 'Answer Key:' "
        "with the correct letters and brief explanations."
    )
    if lesson and lesson.strip():
        prompt += f"\n\nLesson Reference Material:\n{lesson[:1000]}"

    return _call_ollama([{"role": "user", "content": prompt}], max_tokens=450)