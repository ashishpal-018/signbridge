import re

def prepare_text_for_speech(raw_text: str) -> str:
    """
    Cleans markdown characters, bullet points, and code block formatting 
    so that Text-to-Speech (TTS) engines or screen readers can narrate 
    the text smoothly without reading out symbols like *, #, or markdown tags.
    """
    if not raw_text:
        return ""

    # Remove markdown headers (e.g., ### Title -> Title)
    text = re.sub(r"#{1,6}|[*`_~-]", " ", raw_text)
    
    # Replace multiple spaces or newlines with smooth spacing
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text