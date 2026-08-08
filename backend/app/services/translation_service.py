"""Translate transcripts to English while the original transcript is kept separately."""
from deep_translator import GoogleTranslator

CHUNK_SIZE = 4500  # translators generally cap around 5000 chars per call
ENGLISH_LANGS = {"en", "en-us", "en-gb"}


def should_translate(text: str, source_lang: str = "auto") -> bool:
    if not text.strip():
        return False
    lang = (source_lang or "auto").lower()
    if lang in ENGLISH_LANGS:
        return False
    if lang in {"auto", "unknown"}:
        alpha_chars = [ch for ch in text if ch.isalpha()]
        if alpha_chars:
            ascii_ratio = sum(1 for ch in alpha_chars if ch.isascii()) / len(alpha_chars)
            if ascii_ratio >= 0.92:
                return False
    return True


def translate_to_english(text: str, source_lang: str = "auto") -> str:
    if not text:
        return ""
    if not should_translate(text, source_lang):
        return text
    try:
        chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)] or [text]
        translator = GoogleTranslator(source="auto", target="en")
        translated_chunks = [
            translator.translate(chunk) for chunk in chunks
        ]
        return " ".join(t for t in translated_chunks if t)
    except Exception as e:
        # Never lose the pipeline over a translation hiccup; flag it instead.
        return f"[translation_failed: {e}] {text}"
