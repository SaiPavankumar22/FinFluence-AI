"""Orchestrates the full pipeline for a single reel:
download -> extract audio -> transcribe -> translate -> LLM analysis -> store.
"""
import asyncio
import logging
import os
import shutil
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from app.database import reels_col, transcripts_col, analyses_col
from app.services import instagram_service, asr_service, translation_service, llm_service
from app.services.media_utils import extract_audio
from app.config import settings


async def _update_reel_state(reel_id: str, **fields) -> None:
    await reels_col.update_one({"reel_id": reel_id}, {"$set": fields})


async def process_reel(reel_doc: dict) -> None:
    reel_id = reel_doc["reel_id"]
    db_id = str(reel_doc.get("_id", "?"))
    work_dir = os.path.join(settings.download_dir, "_processing", reel_id)
    os.makedirs(work_dir, exist_ok=True)
    pipeline_started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    metrics: dict[str, float] = {}

    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("[pipeline] START  reel_id=%-20s  db_id=%s", reel_id, db_id)
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Mark as currently processing so the frontend can show a spinner
    await _update_reel_state(
        reel_id,
        processing=True,
        processed=False,
        process_error=None,
        processing_stage="queued",
        processing_started_at=pipeline_started_at,
    )

    try:
        # ── Step 1: Download video ─────────────────────────────
        await _update_reel_state(reel_id, processing_stage="downloading")
        logger.info("[pipeline] [1/5] Downloading video  reel_id=%s", reel_id)
        step_started = time.perf_counter()
        video_path = await asyncio.to_thread(
            instagram_service.download_reel_video,
            reel_id,
            work_dir,
            video_url=reel_doc.get("video_url"),
        )
        metrics["download_seconds"] = round(time.perf_counter() - step_started, 2)
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        logger.info("[pipeline] [1/5] ✓ Downloaded → %s  (%.2f MB)", video_path, size_mb)

        # ── Step 2: Extract audio ──────────────────────────────
        await _update_reel_state(reel_id, processing_stage="extracting_audio")
        logger.info("[pipeline] [2/5] Extracting audio …")
        audio_path = os.path.join(work_dir, "audio.wav")
        step_started = time.perf_counter()
        await asyncio.to_thread(
            extract_audio,
            video_path,
            audio_path,
            settings.reel_audio_max_seconds,
        )
        metrics["audio_extract_seconds"] = round(time.perf_counter() - step_started, 2)
        audio_mb = os.path.getsize(audio_path) / (1024 * 1024)
        logger.info("[pipeline] [2/5] ✓ Audio WAV → %s  (%.2f MB)", audio_path, audio_mb)

        # ── Step 3: Transcribe ─────────────────────────────────
        await _update_reel_state(reel_id, processing_stage="transcribing")
        logger.info(
            "[pipeline] [3/5] Transcribing with %s (%s) …",
            settings.transcription_provider,
            settings.sarvam_stt_model if settings.transcription_provider == "sarvam" else settings.whisper_model_size,
        )
        step_started = time.perf_counter()
        asr_result = await asyncio.to_thread(asr_service.transcribe_audio, audio_path)
        metrics["transcription_seconds"] = round(time.perf_counter() - step_started, 2)
        original_text = asr_result["text"]
        language = asr_result["language"]
        lang_prob = asr_result.get("language_probability", 0)
        metrics["transcription_chunks"] = asr_result.get("chunk_count", 1)
        logger.info(
            "[pipeline] [3/5] ✓ Transcript: lang=%s (%.0f%%) chars=%d chunks=%s",
            language, lang_prob * 100, len(original_text), asr_result.get("chunk_count", 1),
        )
        logger.info("[pipeline]        preview: %r", original_text[:150])

        # If speech-to-text returned nothing (silent / music / VAD wiped clip),
        # fall back to the Instagram caption so LLM still has content to analyse.
        caption = (reel_doc.get("caption") or "").strip()
        if not original_text and caption:
            logger.warning(
                "[pipeline] Empty ASR – using Instagram caption as source (%d chars)",
                len(caption),
            )
            original_text = caption
            language = "auto"

        if not original_text:
            raise RuntimeError(
                "No speech detected in audio and no caption available to analyse"
            )

        # ── Step 4: Translate ──────────────────────────────────
        await _update_reel_state(reel_id, processing_stage="translating")
        if not translation_service.should_translate(original_text, language):
            logger.info("[pipeline] [4/5] Already English – skipping translation")
            english_text = original_text
            metrics["translation_seconds"] = 0.0
        else:
            logger.info("[pipeline] [4/5] Translating %s → en …", language)
            step_started = time.perf_counter()
            english_text = await asyncio.to_thread(
                translation_service.translate_to_english,
                original_text,
                language,
            )
            metrics["translation_seconds"] = round(time.perf_counter() - step_started, 2)
            logger.info(
                "[pipeline] [4/5] ✓ Translation: chars=%d  preview: %r",
                len(english_text), english_text[:150],
            )

        # ── Step 5: LLM Analysis ───────────────────────────────
        await _update_reel_state(reel_id, processing_stage="summarizing")
        logger.info("[pipeline] [5/5] LLM analysis  model=%s …", settings.nebius_model)
        step_started = time.perf_counter()
        analysis = await asyncio.to_thread(
            llm_service.analyze_transcript,
            english_text,
            original_text=original_text,
            language=language,
        )
        metrics["analysis_seconds"] = round(time.perf_counter() - step_started, 2)
        logger.info(
            "[pipeline] [5/5] ✓ Analysis: sentiment=%s  stocks=%s  sectors=%s  ipos=%s",
            analysis.get("sentiment"),
            analysis.get("stocks", [])[:5],
            analysis.get("sectors", [])[:5],
            analysis.get("ipos", [])[:3],
        )
        logger.info("[pipeline]        summary: %r", (analysis.get("summary") or "")[:200])

        # ── Store results ──────────────────────────────────────
        logger.info("[pipeline] Persisting transcript and analysis to MongoDB …")
        now = datetime.now(timezone.utc)
        metrics["total_seconds"] = round(time.perf_counter() - started_perf, 2)

        await transcripts_col.update_one(
            {"reel_id": reel_id},
            {"$set": {
                "reel_id": reel_id,
                "language": language,
                "original_text": original_text,
                "english_translation": english_text,
                "updated_at": now,
            }},
            upsert=True,
        )

        await analyses_col.update_one(
            {"reel_id": reel_id},
            {"$set": {**analysis, "reel_id": reel_id, "updated_at": now}},
            upsert=True,
        )

        topics = sorted(set(
            (analysis.get("sectors") or []) + (analysis.get("stocks") or [])
        ))
        await reels_col.update_one(
            {"reel_id": reel_id},
            {"$set": {
                "processed": True,
                "processing": False,
                "processing_stage": "completed",
                "processing_started_at": pipeline_started_at,
                "processed_at": now,
                "processing_metrics": metrics,
                "transcript_language": language,
                "process_error": None,
                "sentiment": analysis.get("sentiment"),
                "topics": topics,
            }},
        )

        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info("[pipeline] DONE   reel_id=%s  sentiment=%s", reel_id, analysis.get("sentiment"))
        logger.info("[pipeline]        topics: %s", topics[:8])
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    except Exception as e:
        logger.error("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.error("[pipeline] FAILED  reel_id=%s  error=%s", reel_id, e, exc_info=True)
        logger.error("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        metrics["total_seconds"] = round(time.perf_counter() - started_perf, 2)
        await reels_col.update_one(
            {"reel_id": reel_id},
            {"$set": {
                "processed": False,
                "processing": False,
                "processing_stage": "failed",
                "processing_started_at": pipeline_started_at,
                "processing_metrics": metrics,
                "process_error": str(e),
            }},
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.info("[pipeline] Cleanup done  reel_id=%s", reel_id)
