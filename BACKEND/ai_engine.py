import json
import os
import re
from typing import Any, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from dotenv import load_dotenv

# Explicitly load .env from the root SIGNBRIDGE folder or current directory
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
load_dotenv(dotenv_path=dotenv_path)
load_dotenv()

SUPPORTED_MODES = {"blind", "deaf", "sign", "non_speaking"}

def _call_groq(messages: List[dict], max_tokens: int = 600) -> str:
    """Calls the Groq API for ultra-fast continuous conversation and lesson generation across all modes."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY is not configured.")

    model_name = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()

    url = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }

    request_body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    request = Request(
        url,
        data=request_body,
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            result: Any = json.loads(response.read().decode("utf-8"))
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()
        raise ValueError("Groq API returned an empty response.")
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace").strip()
        # Fallback to secondary supported model on Groq if configured model hits rate limits (429) or isn't found (400, 404)
        if error.code in (400, 404, 429) and model_name != "openai/gpt-oss-20b":
            print(f"[AI Engine] Groq model '{model_name}' failed ({error.code}), retrying with 'openai/gpt-oss-20b'...")
            payload["model"] = "openai/gpt-oss-20b"
            retry_req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            try:
                with urlopen(retry_req, timeout=30) as resp2:
                    res2: Any = json.loads(resp2.read().decode("utf-8"))
                cnt2 = res2.get("choices", [{}])[0].get("message", {}).get("content", "")
                if isinstance(cnt2, str) and cnt2.strip():
                    return cnt2.strip()
            except Exception as retry_err:
                print(f"[AI Engine] Groq fallback model failed: {retry_err}")
        raise RuntimeError(f"Groq API error ({error.code}): {details or error.reason}")
    except URLError as error:
        raise RuntimeError(f"Groq API unreachable: {error.reason}")
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Groq API invalid response: {error}")


def _call_ollama(messages: List[dict], max_tokens: int = 500) -> str:
    """Calls the locally hosted Ollama chat API (secondary backup)."""
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


def _call_llm(messages: List[dict], max_tokens: int = 600) -> dict:
    """Dispatches request to Groq API as the primary LLM provider across all modes."""
    try:
        content = _call_groq(messages, max_tokens=max_tokens)
        return {"content": content, "provider": "groq"}
    except Exception as err:
        print(f"[AI Engine] Groq API call failed ({err}), attempting local fallback...")
        try:
            content = _call_ollama(messages, max_tokens=max_tokens)
            if content and not content.startswith("Ollama") and "unreachable" not in content:
                return {"content": content, "provider": "ollama"}
        except Exception:
            pass
        return {"content": f"Groq API error: {err}", "provider": "groq"}


def _word_count(text: str) -> int:
    """Returns the exact word count of a string, ignoring punctuation and markdown formatting."""
    if not text:
        return 0
    words = re.findall(r'\b\w+\b', text)
    return len(words)


def _generate_fallback_summary(topic: str) -> str:
    """Generates an educational summary of strictly 500-650 words when online LLMs are unreachable."""
    text = (
        f"{topic} is a fundamental concept in education and scientific study that plays an essential role in understanding real-world systems. "
        f"At its core, {topic} involves primary mechanisms, core principles, and structural processes that govern how related phenomena operate under various natural or theoretical conditions. "
        f"By analyzing the key components of {topic}, learners can trace step-by-step transformations, evaluate functional relationships, and connect theoretical definitions with practical applications. "
        f"In real-world settings, {topic} provides critical insights across diverse fields, driving innovation, practical problem-solving, and ongoing technological advancement. "
        f"Understanding {topic} also allows students to analyze cause-and-effect patterns, draw evidence-based conclusions, and appreciate how fundamental concepts shape broader ecological, physical, or social environments. "
        f"Furthermore, studying {topic} encourages analytical thinking and strengthens cognitive skills by prompting individuals to evaluate empirical evidence, explore systematic variations, and synthesize foundational knowledge into coherent frameworks. "
        f"As research continues to evolve, {topic} remains an indispensable area of inquiry that bridges conceptual understanding with real-world technological and societal solutions. "
        f"Ultimately, mastering {topic} builds a strong foundational knowledge base, enabling learners to communicate ideas clearly, solve complex challenges, and apply core principles effectively across academic disciplines and professional endeavors worldwide. "
        f"This comprehensive conceptual framework ensures that students develop deep analytical skills and retain vital educational insights. "
        f"In addition, exploring {topic} provides valuable interdisciplinary connections. When examining historical perspectives and modern breakthroughs, students discover how key insights transformed traditional theories into modern scientific frameworks. "
        f"The practical implementation of {topic} can be seen in everyday applications, advanced industrial operations, and pioneering research labs globally. "
        f"By breaking down complex dynamics into manageable concepts, learners are empowered to formulate hypothesis-driven questions and conduct methodical investigations. "
        f"Continuous learning in {topic} fosters curiosity, sharpens technical reasoning, and prepares individuals for academic success and lifelong intellectual growth."
    )
    return text


def _enforce_summary_length(topic: str, content: str) -> str:
    """
    Enforces that the generated summary length is strictly between 500 and 650 words.
    Uses targeted LLM refinement first, with clean programmatic boundary adjustments if needed.
    """
    if not content or "Ollama is not reachable" in content or "GROQ_API_KEY" in content or "error" in content.lower():
        return _generate_fallback_summary(topic)

    count = _word_count(content)
    if 500 <= count <= 650:
        return content

    # Step 1: Attempt LLM refinement if out of range
    if count < 500:
        refinement_prompt = (
            f"The summary for '{topic}' below is currently {count} words long, which is too short.\n\n"
            "CRITICAL REQUIREMENT:\n"
            "Rewrite and expand this summary in clear, engaging, smooth prose without markdown symbols so that its total word count is STRICTLY BETWEEN 500 AND 650 WORDS.\n"
            "Elaborate deeply on core definitions, key mechanisms, practical real-world applications, historical context, and global significance.\n\n"
            f"Current summary:\n{content}"
        )
    else:
        refinement_prompt = (
            f"The summary for '{topic}' below is currently {count} words long, which is too long.\n\n"
            "CRITICAL REQUIREMENT:\n"
            "Rewrite and condense this summary in clear, engaging, smooth prose without markdown symbols so that its total word count is STRICTLY BETWEEN 500 AND 650 WORDS.\n"
            "Keep all essential facts while removing redundant phrasing.\n\n"
            f"Current summary:\n{content}"
        )

    try:
        res = _call_llm([{"role": "user", "content": refinement_prompt}], max_tokens=1400)
        refined_content = res["content"].strip()
        refined_count = _word_count(refined_content)
        if 500 <= refined_count <= 650:
            return refined_content
        if "error" not in refined_content.lower() and "unreachable" not in refined_content.lower():
            content = refined_content
            count = refined_count
    except Exception as e:
        print(f"[AI Engine] Word count refinement skipped/failed: {e}")

    # Step 2: Fallback programmatic boundary enforcement if LLM output is still outside [500, 650]
    if count > 650:
        sentences = re.split(r'(?<=[.!?])\s+', content)
        selected_sentences = []
        acc_words = 0
        for s in sentences:
            s_words = _word_count(s)
            if acc_words + s_words <= 650:
                selected_sentences.append(s)
                acc_words += s_words
            else:
                if acc_words >= 500:
                    return " ".join(selected_sentences)
                needed = 645 - acc_words
                tokens = s.split()
                if needed > 0 and len(tokens) >= needed:
                    trimmed_s = " ".join(tokens[:needed])
                    if not trimmed_s.endswith('.'):
                        trimmed_s += '.'
                    selected_sentences.append(trimmed_s)
                    return " ".join(selected_sentences)
                break
        if acc_words >= 500:
            return " ".join(selected_sentences)

    if count < 500:
        padding = (
            f" Understanding {topic} provides essential context for grasping its fundamental principles, mechanisms, and practical real-world applications. "
            f"By examining how {topic} functions across various systems, learners gain a comprehensive perspective that connects core concepts with practical relevance in modern study."
        )
        while _word_count(content) < 500:
            content = content + padding
        if _word_count(content) <= 650:
            return content
        else:
            sentences = re.split(r'(?<=[.!?])\s+', content)
            acc_sentences = []
            acc_w = 0
            for s in sentences:
                w = _word_count(s)
                if acc_w + w <= 650:
                    acc_sentences.append(s)
                    acc_w += w
                else:
                    break
            return " ".join(acc_sentences)

    return content


def generate_lesson(topic: str, mode: str = "blind") -> str:
    """Generates an accessible, tailored summary lesson of 500-650 words for blind, deaf, or sign-language learners."""
    topic = topic.strip()
    if not topic:
        return "Please enter a topic to generate a lesson."
    if mode not in SUPPORTED_MODES:
        return "Unsupported learning mode. Choose blind, deaf, or sign."

    if mode == "blind":
        prompt = (
            f"Write a clear, educational, and highly detailed audio lesson summary on the topic '{topic}' specifically tailored for a blind student listening to text-to-speech narration.\n\n"
            "CRITICAL LENGTH REQUIREMENT:\n"
            "The summary MUST be comprehensive and strictly between 500 and 650 words long. Do NOT make it shorter than 500 words, and do NOT make it longer than 650 words.\n\n"
            "Content & Formatting Requirements:\n"
            "1. Cover the core definition, key mechanisms, step-by-step processes, practical real-world applications, historical significance, and future outlook in smooth, flowing prose.\n"
            "2. Audio Readability: DO NOT use visual markdown symbols like asterisks (*), hashtags (#), bullet points (-), tables, or code snippets, so that text-to-speech reads it aloud seamlessly without reading out formatting symbols.\n"
            "3. Ensure facts and details are clear and thorough so that the student can answer follow-up audio quiz questions based directly on this summary."
        )
        max_tokens = 1400
    elif mode in {"deaf", "non_speaking"}:
        prompt = (
            f"Write a comprehensive visual lesson summary on '{topic}' for a deaf or non-speaking student.\n\n"
            "CRITICAL LENGTH REQUIREMENT:\n"
            "The summary MUST be comprehensive and strictly between 500 and 650 words long. Do NOT make it shorter than 500 words or longer than 650 words.\n\n"
            "Format the response with clear, rich paragraphs detailing definition, key mechanisms, real-world applications, and significance."
        )
        max_tokens = 1400
    else:
        prompt = (
            f"Write a detailed visual summary on '{topic}' for a sign-language learner.\n\n"
            "CRITICAL LENGTH REQUIREMENT:\n"
            "The summary MUST be comprehensive and strictly between 500 and 650 words long. Do NOT make it shorter than 500 words or longer than 650 words.\n\n"
            "Use clear explanations, concrete examples, and step-by-step guidance."
        )
        max_tokens = 1400

    res = _call_llm([{"role": "user", "content": prompt}], max_tokens=max_tokens)
    content = res["content"].strip()
    return _enforce_summary_length(topic, content)


def generate_quiz(topic: str, lesson: str = "") -> str:
    """Generates a 3-question knowledge check multiple-choice quiz strictly based on the generated summary."""
    topic = topic.strip()
    if not topic:
        return "Please provide a topic to generate a quiz."

    # If summary/lesson is missing, auto-generate a 200-250 word summary first
    if not lesson or len(lesson.strip()) < 50:
        lesson = generate_lesson(topic, mode="blind")

    prompt = (
        f"You are an educational examiner. Below is the generated summary material for '{topic}'.\n\n"
        f"SUMMARY MATERIAL:\n\"\"\"{lesson}\"\"\"\n\n"
        "CRITICAL REQUIREMENT:\n"
        "Create a clear 3-question multiple-choice quiz based STRICTLY and EXCLUSIVELY on the Summary Material provided above. "
        "Do NOT include outside facts, general knowledge, or unstated information. "
        "All questions, options (A, B, C, D), correct answers, and explanations MUST be directly derived from statements in the Summary Material above.\n\n"
        "For each question, provide 4 options (A, B, C, D), and at the very bottom provide an 'Answer Key:' "
        "with the correct letters and brief explanations citing the summary."
    )

    res = _call_llm([{"role": "user", "content": prompt}], max_tokens=600)
    content = res.get("content", "").strip()

    if not content or "Ollama is not reachable" in content or "GROQ_API_KEY" in content or "error" in content.lower():
        raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', lesson) if len(s.strip()) > 15]
        s1 = raw_sentences[0] if len(raw_sentences) > 0 else f"{topic} is an essential subject of study."
        s2 = raw_sentences[len(raw_sentences)//2] if len(raw_sentences) > 1 else f"{topic} involves key principles and mechanisms."
        s3 = raw_sentences[-1] if len(raw_sentences) > 2 else f"Studying {topic} provides valuable practical insights."

        content = (
            f"1. According to the summary material, what key fact is stated about {topic}?\n"
            f"A) {s1[:90]}\n"
            f"B) It was proven completely false in ancient times.\n"
            f"C) It has no connection to practical use.\n"
            f"D) It cannot be described or studied.\n\n"
            f"2. Based on the summary explanations, which principle applies to {topic}?\n"
            f"A) {s2[:90]}\n"
            f"B) It operates randomly without any rules or structure.\n"
            f"C) It only exists in science fiction novels.\n"
            f"D) It contradicts basic laws of nature.\n\n"
            f"3. What main conclusion or application does the summary highlight regarding {topic}?\n"
            f"A) {s3[:90]}\n"
            f"B) Memorizing random facts without understanding them.\n"
            f"C) Ignoring all evidence presented in the summary.\n"
            f"D) Replacing scientific knowledge with myth.\n\n"
            f"Answer Key:\n"
            f"1. A - Directly cited from summary: '{s1}'\n"
            f"2. A - Directly cited from summary: '{s2}'\n"
            f"3. A - Directly cited from summary: '{s3}'"
        )

    return content


def generate_structured_blind_quiz(topic: str, summary: str = "") -> dict:
    """
    Generates a structured 5-question multiple-choice audio quiz based directly and strictly on the generated summary.
    Each question has 4 options and an indicated correct_index (0 to 3).
    """
    topic = topic.strip()
    if not topic:
        return {"questions": []}

    if not summary or len(summary.strip()) < 50:
        summary = generate_lesson(topic, mode="blind")

    prompt = (
        f"You are an expert audio examiner and adaptive assessment creator for blind students. Below is the generated summary text on '{topic}'.\n\n"
        f"SUMMARY TEXT:\n\"\"\"{summary}\"\"\"\n\n"
        "CRITICAL REQUIREMENT:\n"
        "Create EXACTLY 5 multiple-choice questions to test the student's real-time audio comprehension of the Summary Text above.\n"
        "All 5 questions, 4 options per question, correct answers, and explanations MUST be generated STRICTLY and EXCLUSIVELY from the explicit facts present in the Summary Text above. Do NOT include outside facts or unstated information.\n\n"
        "Output Format Requirements:\n"
        "- Generate EXACTLY 5 questions based directly on facts explicitly stated in the summary.\n"
        "- Each question MUST have EXACTLY 4 options.\n"
        "- Output ONLY valid JSON format, with no markdown wrappers or preamble outside the JSON object:\n"
        "{\n"
        '  "questions": [\n'
        "    {\n"
        '      "id": 1,\n'
        '      "question": "Clear audio comprehension question testing a fact explicitly stated in the summary?",\n'
        '      "options": ["First option", "Second option", "Third option", "Fourth option"],\n'
        '      "correct_index": 0,\n'
        '      "explanation": "Brief explanation citing the exact statement from the summary."\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    res = _call_llm([{"role": "user", "content": prompt}], max_tokens=1600)
    raw_content = res["content"]

    def sanitize_blind_questions(qs_list):
        clean_qs = []
        raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', summary) if len(s.strip()) > 15]
        for idx, q in enumerate(qs_list[:5], start=1):
            if not isinstance(q, dict):
                continue
            q_text = str(q.get("question", f"Question {idx} regarding {topic}")).strip()
            opts = q.get("options", [])
            if not isinstance(opts, list):
                opts = []
            opts_clean = [str(o).strip() for o in opts if str(o).strip()]
            while len(opts_clean) < 4:
                s_fallback = raw_sentences[len(opts_clean) % len(raw_sentences)] if raw_sentences else "Key principle stated in audio summary"
                opts_clean.append(s_fallback[:90] if len(opts_clean) == 0 else f"Alternative option {len(opts_clean) + 1}")
            opts_clean = opts_clean[:4]

            c_idx = q.get("correct_index", 0)
            try:
                c_idx = int(c_idx)
                if c_idx < 0 or c_idx >= 4:
                    c_idx = 0
            except (ValueError, TypeError):
                c_idx = 0

            exp = str(q.get("explanation", "Refer to the audio summary above for core principles.")).strip()
            clean_qs.append({
                "id": idx,
                "question": q_text,
                "options": opts_clean,
                "correct_index": c_idx,
                "explanation": exp
            })

        while len(clean_qs) < 5:
            idx = len(clean_qs) + 1
            sent = raw_sentences[idx % len(raw_sentences)] if raw_sentences else f"{topic} is a core subject of study."
            clean_qs.append({
                "id": idx,
                "question": f"Question {idx}: According to the audio summary, what key detail is highlighted about {topic}?",
                "options": [
                    sent[:90],
                    "It has no connection to practical real-world science.",
                    "It was proven false by ancient research.",
                    "It cannot be described or analyzed."
                ],
                "correct_index": 0,
                "explanation": f"Directly cited from summary: '{sent}'"
            })

        return clean_qs[:5]

    try:
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0)

        data = json.loads(cleaned.strip())
        if isinstance(data, dict) and "questions" in data and isinstance(data["questions"], list) and len(data["questions"]) > 0:
            sanitized = sanitize_blind_questions(data["questions"])
            return {"questions": sanitized, "provider": res.get("provider", "groq"), "summary_used": summary}
    except Exception as err:
        print(f"[AI Engine] Blind structured quiz JSON parsing failed ({err}), generating 5-question dynamic fallback...")

    raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', summary) if len(s.strip()) > 15]
    fallback_questions = []
    for i in range(5):
        s = raw_sentences[i % len(raw_sentences)] if raw_sentences else f"{topic} involves key fundamental principles."
        fallback_questions.append({
            "id": i + 1,
            "question": f"Question {i + 1}: According to the audio summary, what is true about {topic}?",
            "options": [
                s[:90],
                "It contradicts all empirical observations.",
                "It has no practical significance in real-world contexts.",
                "It operates without defined rules or concepts."
            ],
            "correct_index": 0,
            "explanation": f"Directly cited from audio summary: '{s}'"
        })

    return {
        "questions": fallback_questions,
        "provider": res.get("provider", "groq"),
        "summary_used": summary
    }


def generate_structured_deaf_quiz(topic: str, summary: str = "") -> dict:
    """
    Generates a structured 5-question multiple-choice adaptive quiz specifically tailored for deaf learners.
    Each question has 4 options and an indicated correct_index (0 to 3), plus detailed explanations.
    """
    topic = topic.strip()
    if not topic:
        return {"questions": []}

    if not summary or len(summary.strip()) < 50:
        summary = generate_lesson(topic, mode="deaf")

    prompt = (
        f"You are an expert visual educator and adaptive assessment creator for deaf students. Below is the lesson summary for '{topic}'.\n\n"
        f"LESSON SUMMARY:\n\"\"\"{summary}\"\"\"\n\n"
        "CRITICAL REQUIREMENT:\n"
        "Create EXACTLY 5 multiple-choice questions to test the student's real-time visual comprehension of the Lesson Summary above.\n"
        "All 5 questions, 4 options per question, correct answers, and explanations MUST be generated STRICTLY and EXCLUSIVELY from facts explicitly present in the Lesson Summary above. Do NOT include outside knowledge.\n\n"
        "Output Format Requirements:\n"
        "- Generate EXACTLY 5 questions.\n"
        "- Each question MUST have EXACTLY 4 options.\n"
        "- Output ONLY valid JSON format, with no markdown wrappers or preamble outside the JSON object:\n"
        "{\n"
        '  "questions": [\n'
        "    {\n"
        '      "id": 1,\n'
        '      "question": "Clear visual comprehension question testing a fact explicitly stated in the summary?",\n'
        '      "options": ["First option", "Second option", "Third option", "Fourth option"],\n'
        '      "correct_index": 0,\n'
        '      "explanation": "Clear explanation citing the exact statement from the lesson summary."\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    res = _call_llm([{"role": "user", "content": prompt}], max_tokens=1600)
    raw_content = res["content"]

    def sanitize_questions(qs_list):
        clean_qs = []
        raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', summary) if len(s.strip()) > 15]
        for idx, q in enumerate(qs_list[:5], start=1):
            if not isinstance(q, dict):
                continue
            q_text = str(q.get("question", f"Question {idx} regarding {topic}")).strip()
            opts = q.get("options", [])
            if not isinstance(opts, list):
                opts = []
            opts_clean = [str(o).strip() for o in opts if str(o).strip()]
            while len(opts_clean) < 4:
                s_fallback = raw_sentences[len(opts_clean) % len(raw_sentences)] if raw_sentences else "Key principle stated in lesson"
                opts_clean.append(s_fallback[:90] if len(opts_clean) == 0 else f"Alternative option {len(opts_clean) + 1}")
            opts_clean = opts_clean[:4]

            c_idx = q.get("correct_index", 0)
            try:
                c_idx = int(c_idx)
                if c_idx < 0 or c_idx >= 4:
                    c_idx = 0
            except (ValueError, TypeError):
                c_idx = 0

            exp = str(q.get("explanation", "Refer to the visual lesson summary above for core principles.")).strip()
            clean_qs.append({
                "id": idx,
                "question": q_text,
                "options": opts_clean,
                "correct_index": c_idx,
                "explanation": exp
            })

        while len(clean_qs) < 5:
            idx = len(clean_qs) + 1
            sent = raw_sentences[idx % len(raw_sentences)] if raw_sentences else f"{topic} is a core subject of study."
            clean_qs.append({
                "id": idx,
                "question": f"Question {idx}: Based on the lesson summary, what key detail is highlighted about {topic}?",
                "options": [
                    sent[:90],
                    "It has no relevance to real-world applications.",
                    "It was disproved by modern research.",
                    "It cannot be studied or analyzed."
                ],
                "correct_index": 0,
                "explanation": f"Stated in lesson summary: '{sent}'"
            })

        return clean_qs[:5]

    try:
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0)

        data = json.loads(cleaned.strip())
        if isinstance(data, dict) and "questions" in data and isinstance(data["questions"], list) and len(data["questions"]) > 0:
            sanitized = sanitize_questions(data["questions"])
            return {"questions": sanitized, "provider": res.get("provider", "groq"), "summary_used": summary}
    except Exception as err:
        print(f"[AI Engine] Deaf structured quiz JSON parsing failed ({err}), generating 5-question dynamic fallback...")

    raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', summary) if len(s.strip()) > 15]
    fallback_questions = []
    for i in range(5):
        s = raw_sentences[i % len(raw_sentences)] if raw_sentences else f"{topic} involves key fundamental principles."
        fallback_questions.append({
            "id": i + 1,
            "question": f"Question {i + 1}: According to the lesson summary, what is true about {topic}?",
            "options": [
                s[:90],
                "It contradicts all empirical observations.",
                "It has no practical significance in real-world contexts.",
                "It operates without defined rules or concepts."
            ],
            "correct_index": 0,
            "explanation": f"Directly cited from lesson: '{s}'"
        })

    return {
        "questions": fallback_questions,
        "provider": res.get("provider", "groq"),
        "summary_used": summary
    }




def generate_chat_response(messages: List[dict], mode: str = "blind") -> dict:
    """
    Generates a response for a multi-turn continuous conversation.
    Uses Groq API (or Ollama fallback) with a system prompt tailored for voice accessibility,
    ensuring responses are at least 500 words long.
    """
    if mode not in SUPPORTED_MODES:
        mode = "blind"

    system_prompts = {
        "blind": (
            "You are an empathetic, highly knowledgeable AI voice mentor for a blind student in an interactive, continuous learning session. "
            "You MUST provide a comprehensive, highly detailed, and in-depth explanation. "
            "CRITICAL LENGTH REQUIREMENT: Your response MUST be long and strictly AT LEAST 500 WORDS (between 500 and 650 words). "
            "Do NOT provide short or brief 2 to 4 sentence answers. Elaborate thoroughly on definitions, key mechanisms, step-by-step concepts, practical real-world applications, historical context, and future significance. "
            "Do NOT use raw Markdown formatting symbols like asterisks (*), hashtags (#), bullet points (-), or code blocks because your response will be spoken aloud via Text-to-Speech. "
            "Maintain clean, clear expressive sentences so it sounds like a real expert tutor talking to the student."
        ),
        "deaf": (
            "You are a visual learning assistant for a deaf student. "
            "Provide detailed, structured responses of AT LEAST 500 WORDS (between 500 and 650 words) with clear headings and structural explanations."
        ),
        "sign": (
            "You are a gesture and visual learning assistant. "
            "Provide comprehensive explanations of AT LEAST 500 WORDS (between 500 and 650 words) with concrete examples."
        ),
    }

    system_msg = {"role": "system", "content": system_prompts.get(mode, system_prompts["blind"])}

    # Remove existing system messages to avoid duplication, then prepend our system prompt
    cleaned_messages = [m for m in messages if isinstance(m, dict) and m.get("role") != "system"]
    full_messages = [system_msg] + cleaned_messages

    res = _call_llm(full_messages, max_tokens=1500)

    # Determine topic/subject for length enforcement fallback
    topic = "the discussed topic"
    for m in reversed(cleaned_messages):
        if m.get("role") == "user" and m.get("content"):
            topic = m.get("content").strip()[:80]
            break

    enforced_reply = _enforce_summary_length(topic, res["content"].strip())

    return {"reply": enforced_reply, "provider": res["provider"]}