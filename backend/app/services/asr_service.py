"""Speech-to-text service with Sarvam as the primary provider.

Sarvam's REST speech-to-text API is optimized for short clips, so longer reel
audio is split into small WAV chunks and transcribed in parallel. This keeps
full-audio coverage while avoiding the slow CPU-bound Whisper path.
"""
from __future__ import annotations

import logging
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.media_utils import split_audio

logger = logging.getLogger(__name__)

try:
    from sarvamai import SarvamAI
except ImportError:  # pragma: no cover - depends on optional runtime dependency
    SarvamAI = None

_client = None


def _response_attr(response: Any, key: str, default: Any = None) -> Any:
    if hasattr(response, key):
        return getattr(response, key)
    if isinstance(response, dict):
        return response.get(key, default)
    return default


def _client_instance() -> Any:
    global _client
    if SarvamAI is None:
        raise RuntimeError(
            "Sarvam SDK is not installed. Run `pip install -r backend/requirements.txt`."
        )
    if not settings.sarvam_api_subscription_key:
        raise RuntimeError(
            "SARVAM_API_SUBSCRIPTION_KEY is missing. Add it in backend/.env."
        )
    if _client is None:
        _client = SarvamAI(api_subscription_key=settings.sarvam_api_subscription_key)
    return _client


def _transcribe_chunk(chunk_path: str) -> dict[str, Any]:
    client = _client_instance()
    last_error = None

    for attempt in range(1, settings.sarvam_max_retries + 2):
        started = time.perf_counter()
        try:
            with open(chunk_path, "rb") as audio_file:
                response = client.speech_to_text.transcribe(
                    file=audio_file,
                    model=settings.sarvam_stt_model,
                    language_code=settings.sarvam_language_code,
                    mode=settings.sarvam_mode,
                    input_audio_codec="wav",
                )

            transcript = (_response_attr(response, "transcript", "") or "").strip()
            language_code = _response_attr(response, "language_code", None) or "unknown"
            language_probability = float(
                _response_attr(response, "language_probability", 0.0) or 0.0
            )
            elapsed = round(time.perf_counter() - started, 2)
            logger.info(
                "[asr] chunk=%s transcribed in %.2fs lang=%s chars=%d",
                Path(chunk_path).name,
                elapsed,
                language_code,
                len(transcript),
            )
            return {
                "chunk_path": chunk_path,
                "transcript": transcript,
                "language_code": language_code,
                "language_probability": language_probability,
                "elapsed_seconds": elapsed,
            }
        except Exception as exc:  # pragma: no cover - depends on external API
            last_error = exc
            logger.warning(
                "[asr] chunk=%s attempt=%d failed: %s",
                Path(chunk_path).name,
                attempt,
                exc,
            )

    raise RuntimeError(f"Sarvam transcription failed for {Path(chunk_path).name}: {last_error}")


def _combine_chunk_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    transcripts = [item["transcript"].strip() for item in results if item["transcript"].strip()]
    text = " ".join(transcripts).strip()

    languages = [item["language_code"] for item in results if item["language_code"] not in {None, "unknown"}]
    if languages:
        language = Counter(languages).most_common(1)[0][0]
    else:
        language = settings.sarvam_language_code if settings.sarvam_language_code != "unknown" else "unknown"

    probs = [float(item.get("language_probability", 0.0) or 0.0) for item in results]
    language_probability = max(probs) if probs else 0.0

    return {
        "text": text,
        "language": language,
        "language_probability": language_probability,
        "chunk_count": len(results),
    }


def transcribe_audio(audio_path: str) -> dict[str, Any]:
    logger.info("[asr] Sarvam transcription start path=%s", audio_path)

    size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
    if size < 2048:
        logger.warning("[asr] Audio file too small (%d bytes) - treating as empty", size)
        return {"text": "", "language": "unknown", "language_probability": 0.0, "chunk_count": 0}

    chunk_seconds = max(10, settings.sarvam_chunk_seconds)
    chunk_dir = os.path.join(os.path.dirname(audio_path), "sarvam_chunks")
    chunk_paths = split_audio(audio_path, chunk_dir, chunk_seconds)
    if not chunk_paths:
        chunk_paths = [audio_path]

    workers = min(max(1, settings.sarvam_parallel_chunks), len(chunk_paths))
    logger.info(
        "[asr] Using Sarvam model=%s language_code=%s mode=%s chunks=%d workers=%d",
        settings.sarvam_stt_model,
        settings.sarvam_language_code,
        settings.sarvam_mode,
        len(chunk_paths),
        workers,
    )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_transcribe_chunk, chunk_paths))

    combined = _combine_chunk_results(results)
    logger.info(
        "[asr] Sarvam transcription done lang=%s (%.0f%%) chars=%d chunks=%d",
        combined["language"],
        combined["language_probability"] * 100,
        len(combined["text"]),
        combined["chunk_count"],
    )
    return combined
