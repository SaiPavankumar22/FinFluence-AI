"""Structured market-intelligence analysis via Nebius (OpenAI-compatible API).

The LLM receives BOTH the original transcript and its English translation so it
can resolve terms that the machine translator garbled (e.g. "Ipio" → IPO,
"bonans" → bonus/listing gains, transliterated company names, etc.).
"""
import json
import logging

from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)
_client = None


ANALYSIS_PROMPT = """\
You are a senior financial market-intelligence analyst specialising in Indian equity markets \
(NSE/BSE), IPOs, macroeconomics, RBI policy, and global markets.

You are analysing a short video clip from an Indian financial influencer on Instagram.
The transcript below may be:
  • A mix of Hindi/Telugu/English spoken naturally (Hinglish/Tenglish)
  • Machine-translated, so some words may be garbled (e.g. "ipio" = IPO, "bonans" = bonus/listing gains,
    transliterated company names written phonetically, etc.)
  • Informal and colloquial — interpret the financial intent, not just the literal words.

Your job: extract the actionable market intelligence and summarize it clearly.

──────────────────────────────────────
ORIGINAL TRANSCRIPT ({lang}):
{original}

MACHINE-TRANSLATED (English):
{translated}
──────────────────────────────────────

Return ONLY a single valid JSON object — no markdown fences, no commentary — with EXACTLY these keys:

{{
  "headline": "Write one crisp sentence of at most 12 words capturing the main investing takeaway.",

  "summary": "Write 3 strong sentences covering: what the influencer is talking about, the core market theme, \
specific stocks/IPOs/sectors mentioned, their stance (bullish/bearish/neutral), and any key data points or \
price targets mentioned. Be specific — avoid vague phrases like 'discusses markets'.",

  "sentiment": "Bullish" | "Bearish" | "Neutral",

  "stocks": ["list every stock name or ticker explicitly or implicitly mentioned — normalise to NSE ticker \
if recognisable (e.g. 'Reliance Industries' → 'RELIANCE'), else write the spoken name"],

  "ipos": ["every IPO mentioned — include GMP, listing gain, subscription status if mentioned"],

  "sectors": ["every sector, industry, or theme discussed — e.g. 'Banking', 'IT', 'Defence', 'SME IPO', \
'US-China trade', 'RBI rate cut', 'FII flows'"],

  "geopolitical_events": ["geopolitical events, trade wars, sanctions, elections, conflicts mentioned"],

  "economic_events": ["macro events: RBI MPC decision, inflation print, GDP data, budget announcements, \
Fed policy, currency moves, FII/DII data, etc."],

  "risks": ["specific risks or warnings the influencer flags — be concrete, not generic"],

  "opportunities": ["specific opportunities or trades the influencer recommends or implies — include \
price levels or catalysts if mentioned"],

  "takeaways": ["3 short, actionable bullet points a retail investor should remember after watching this"]
}}

Rules:
• Use [] for any category where nothing was mentioned — do NOT invent information.
• If a stock/IPO name is unclear due to translation, write your best interpretation in [brackets] with a \
note, e.g. ["[possibly Waaree Energies] - influencer mentioned 'wordi'"].
• The headline and summary must be specific to THIS content, not generic market commentary.
"""

EMPTY_ANALYSIS = {
    "headline": "",
    "summary": "",
    "sentiment": "Neutral",
    "stocks": [],
    "ipos": [],
    "sectors": [],
    "geopolitical_events": [],
    "economic_events": [],
    "risks": [],
    "opportunities": [],
    "takeaways": [],
}


def _client_instance() -> OpenAI:
    global _client
    if _client is None:
        logger.info("[llm] Initialising OpenAI client  model=%s", settings.nebius_model)
        _client = OpenAI(base_url=settings.nebius_base_url, api_key=settings.nebius_api_key)
    return _client


def analyze_transcript(
    english_text: str,
    original_text: str = "",
    language: str = "unknown",
) -> dict:
    if not english_text.strip() and not original_text.strip():
        logger.warning("[llm] Both original and translated text are empty — returning empty analysis")
        return dict(EMPTY_ANALYSIS)

    # If translation failed, fall back to original
    effective_translated = english_text.strip() or original_text.strip()
    effective_original = original_text.strip() or english_text.strip()

    client = _client_instance()
    prompt = ANALYSIS_PROMPT.format(
        lang=language.upper(),
        original=effective_original[:3500],
        translated=effective_translated[:3500],
    )

    logger.info("[llm] Sending to model=%s  orig_chars=%d  trans_chars=%d",
                settings.nebius_model, len(effective_original), len(effective_translated))

    try:
        response = client.chat.completions.create(
            model=settings.nebius_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
        )
        raw = response.choices[0].message.content.strip()
        logger.info("[llm] Response received  chars=%d", len(raw))
    except Exception as e:
        logger.error("[llm] API call failed: %s", e)
        raise

    # Strip any markdown fences the model might have added
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[llm] JSON parse failed — storing raw output as summary")
        data = dict(EMPTY_ANALYSIS)
        data["summary"] = raw[:1200] or "Analysis could not be parsed as structured JSON."
        return data

    # Merge with defaults so missing keys never cause KeyErrors downstream
    result = dict(EMPTY_ANALYSIS)
    result.update({k: data.get(k, v) for k, v in EMPTY_ANALYSIS.items()})

    logger.info("[llm] ✓ sentiment=%s  stocks=%s  ipos=%s",
                result["sentiment"], result["stocks"][:5], result["ipos"][:3])
    return result
