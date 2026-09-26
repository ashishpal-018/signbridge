from typing import Any

try:
    import ollama
except ImportError:
    ollama = None

SUPPORTED_MODES = {"blind", "deaf"}


def generate_lesson(topic: str, mode: str = "blind") -> str:
    """
    Sends a prompt to the local Ollama LLM.
    - If mode == 'blind': Formats content to sound natural when read aloud.
    - If mode == 'deaf': Formats content into structured visual text with headers and bullets.
    """
    topic = topic.strip()
    if not topic:
        return "Please enter a topic to generate a lesson."
    if mode not in SUPPORTED_MODES:
        return "Unsupported learning mode. Choose blind or deaf."
    if ollama is None:
        return "Local AI is unavailable because the Ollama Python package is not installed."
    try:
        if mode == "blind":
            prompt = (
                f"Explain the topic '{topic}' concisely for a blind student. "
                "Keep sentences flowing smoothly, avoid complex visual formatting symbols, "
                "and make it sound engaging when read aloud by a screen reader."
            )
        else:
            prompt = (
                f"Explain the topic '{topic}' for a deaf student. "
                "Format the response with clear headings, bullet points, and simplified definitions "
                "optimized for a visual reading dashboard."
            )

        response: Any = ollama.chat(
            model="qwen2.5:3b",
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.get("message", {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            return "The local AI returned an empty lesson. Please try again."
        return content.strip()
    except Exception:
        return "The local AI is unavailable. Make sure Ollama is running and try again."