"""
prompt_bank.py — Shared module that wires prompt_bank.md into Igloo's
script generation step. Used by both generate_script.py (CLI) and web_app.py
(Flask UI) so the editorial voice is defined in exactly one place.

Implements the integration directive at integrate_prompt_bank.md:
  - Parses prompt_bank.md (universal rules + 5 niche prompts + good/bad examples)
  - Resolves a user-provided theme/niche to one of the 5 built-in niches,
    or generates+caches a new niche voice on the fly
  - Assembles the full system prompt per Step 3 of the directive
  - Validates the LLM output (Step 5) — catches AI-tells, listicle patterns,
    field-name typos like `naration_text`, and word-count drift

Public API:
  load_prompt_bank() -> dict
  resolve_niche(theme, explicit_niche=None, api_key=None) -> tuple[str, str, str]
  build_narration_prompt(theme, topic, duration, niche=None, ...) -> str
  validate_scenes(scenes, duration) -> list[str]   # empty list = valid
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gemini_client import call_gemini as _call_gemini  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_BANK_PATH = Path(__file__).resolve().parent / "prompt_bank.md"
NICHE_CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "niche_prompts"
VOICE_CALIBRATION_PATH = PROJECT_ROOT / "data" / "voice_calibration.json"

# Default wps used when a voice has no calibration entry yet. Deliberately
# generic — first reel for a new voice will be roughly right; auto-update
# converges within a few runs. See get_voice_wps() / update_voice_wps().
DEFAULT_WPS = 2.5
# Acceptable word-count band as a fraction of the calibrated target.
# Tight enough that PASS means PASS, loose enough to allow human variation.
WPS_BAND = 0.15  # ±15% around target word count

# Hard ceiling: no reel may exceed this 1x duration. At 1.2x final speed,
# MAX_DURATION_1X = 60 produces a ≤50s delivered reel.
MAX_DURATION_1X = 60

# Hard floor: no reel may fall below this 1x duration. At 1.2x final speed,
# MIN_DURATION_1X = 36 produces a ≥30s delivered reel (the product minimum).
MIN_DURATION_1X = 36

# Built-in niches in prompt_bank.md (order matches Part 2 sections)
BUILTIN_NICHES = ["spirituality", "fitness", "finance", "parenting", "wellness"]

# Theme keyword → niche mapping for default resolution
# Order matters: longer/more specific keys first
THEME_KEYWORDS: list[tuple[str, str]] = [
    ("spirituality", "spirituality"), ("spiritual", "spirituality"),
    ("meditation", "spirituality"), ("philosophy", "spirituality"),
    ("religion", "spirituality"), ("buddhism", "spirituality"),
    ("hinduism", "spirituality"), ("yoga", "spirituality"),
    ("fitness", "fitness"), ("workout", "fitness"), ("training", "fitness"),
    ("strength", "fitness"), ("gym", "fitness"), ("tennis", "fitness"),
    ("sports", "fitness"), ("athletic", "fitness"), ("running", "fitness"),
    ("finance", "finance"), ("investing", "finance"), ("stocks", "finance"),
    ("money", "finance"), ("crypto", "finance"), ("market", "finance"),
    ("trading", "finance"), ("economic", "finance"),
    ("parenting", "parenting"), ("kids", "parenting"), ("child", "parenting"),
    ("family", "parenting"), ("baby", "parenting"), ("toddler", "parenting"),
    ("wellness", "wellness"), ("health", "wellness"), ("nutrition", "wellness"),
    ("supplement", "wellness"), ("biohack", "wellness"), ("longevity", "wellness"),
    ("diet", "wellness"), ("sleep", "wellness"),
]

# AI-tell phrases that fail validation
AI_TELL_PHRASES = [
    "in today's fast-paced world", "in today's world", "let's dive in",
    "let's dive into", "here's the thing", "here are some", "here are the",
    "it's important to note", "it is important to note", "interestingly",
    "in this video", "in this reel", "stay tuned", "level up", "buckle up",
    "without further ado", "the truth is", "wealth mindset",
    "financial freedom", "passive income", "fitness fam", "hey fam",
    "make sure to", "if you found this", "if you enjoyed",
    "various institutions", "studies have shown", "research suggests",
    "experts recommend", "consult with healthcare professionals",
]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_BANK_CACHE: dict | None = None


def load_prompt_bank() -> dict:
    """Parse prompt_bank.md once and cache the result.

    Returns a dict with keys:
      universal_rules: str
      niches: dict[str, str]            # niche name → system prompt body
      good_examples: dict[str, str]
      bad_examples: dict[str, str]
    """
    global _BANK_CACHE
    if _BANK_CACHE is not None:
        return _BANK_CACHE

    if not PROMPT_BANK_PATH.exists():
        raise FileNotFoundError(
            f"prompt_bank.md not found at {PROMPT_BANK_PATH}. "
            "The script generator depends on this file — restore it before generating."
        )

    bank = PROMPT_BANK_PATH.read_text(encoding="utf-8")

    # Part 1 — universal rules
    try:
        part1 = bank.split("## Part 1")[1].split("## Part 2")[0]
    except IndexError:
        raise ValueError("prompt_bank.md is missing Part 1 (Universal Rules)")
    universal = "## Part 1" + part1

    # Part 2 — niche system prompts
    niches: dict[str, str] = {}
    niche_section_re = re.compile(
        r"### Niche \d+: (\w+)\s*\n+```\s*\n([\s\S]*?)\n```",
        re.MULTILINE,
    )
    for match in niche_section_re.finditer(bank):
        name = match.group(1).strip().lower()
        body = match.group(2).strip()
        niches[name] = body

    missing = [n for n in BUILTIN_NICHES if n not in niches]
    if missing:
        raise ValueError(
            f"prompt_bank.md is missing niches: {missing}. "
            f"Found: {list(niches.keys())}"
        )

    # Part 3 — good/bad examples per niche
    good_examples: dict[str, str] = {}
    bad_examples: dict[str, str] = {}
    for niche in BUILTIN_NICHES:
        good_examples[niche] = _extract_example(bank, niche, "GOOD")
        bad_examples[niche] = _extract_example(bank, niche, "BAD")

    _BANK_CACHE = {
        "universal_rules": universal.strip(),
        "niches": niches,
        "good_examples": good_examples,
        "bad_examples": bad_examples,
    }
    return _BANK_CACHE


def _extract_example(bank: str, niche: str, kind: str) -> str:
    """Extract a GOOD or BAD example block from Part 3."""
    title = niche.capitalize()
    header = f"### {title} — {kind} Example"
    if header not in bank:
        return ""
    after = bank.split(header, 1)[1]
    # Stop at the next "### " or "---" followed by a section
    end_markers = ["\n### ", "\n## "]
    end = len(after)
    for marker in end_markers:
        idx = after.find(marker)
        if idx != -1 and idx < end:
            end = idx
    return after[:end].strip()


# ---------------------------------------------------------------------------
# Niche resolution
# ---------------------------------------------------------------------------

def resolve_niche(
    theme: str,
    explicit_niche: str | None = None,
    api_key: str | None = None,
) -> tuple[str, str, str]:
    """Pick the niche voice for a given theme.

    Returns (niche_label, niche_prompt_body, source) where source is one of:
      "exact"   — explicit niche matched a built-in
      "keyword" — theme keyword matched a built-in
      "dynamic" — generated on the fly via LLM (cached)
    """
    bank = load_prompt_bank()

    # 1. Exact match on explicit niche
    if explicit_niche:
        key = explicit_niche.strip().lower()
        if key in bank["niches"]:
            return key, bank["niches"][key], "exact"
        # Explicit niche provided but not built-in → treat it as the dynamic key
        return _dynamic_niche(key, api_key), bank["niches"].get(key, ""), "dynamic"

    # 2. Keyword match on theme
    theme_lower = theme.lower()
    for keyword, niche in THEME_KEYWORDS:
        if keyword in theme_lower:
            return niche, bank["niches"][niche], "keyword"

    # 3. No match → dynamic generation, keyed by theme slug
    slug = _slug(theme) or "generic"
    return _dynamic_niche(slug, api_key, theme=theme), bank["niches"].get(slug, ""), "dynamic"


def _slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text.strip("_")


def _dynamic_niche(slug: str, api_key: str | None, theme: str = "") -> str:
    """Generate a new niche voice on the fly, cached by slug.

    Returns the niche label (slug). Side effect: populates the in-memory bank
    cache so build_narration_prompt() can find it.
    """
    bank = load_prompt_bank()

    # Already cached in memory?
    if slug in bank["niches"]:
        return slug

    # Disk cache?
    NICHE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = NICHE_CACHE_DIR / f"{slug}.txt"
    if cache_file.exists():
        bank["niches"][slug] = cache_file.read_text(encoding="utf-8").strip()
        # Borrow the closest existing examples (finance is a safe default —
        # it has the most documentary-toned examples)
        bank["good_examples"].setdefault(slug, bank["good_examples"]["finance"])
        bank["bad_examples"].setdefault(slug, bank["bad_examples"]["finance"])
        return slug

    if not api_key:
        # Can't generate without an API key — fall back to finance voice
        # (most universally documentary-toned of the five). Caller still gets
        # a prompt-bank-shaped output, just with a slightly mismatched niche.
        print(
            f"  [prompt_bank] WARNING: no API key for dynamic niche '{slug}', "
            f"falling back to finance voice",
            file=sys.stderr,
        )
        return "finance"

    # Generate via LLM using the 5 existing prompts as style examples
    examples = "\n\n---\n\n".join(
        f"=== {n.upper()} ===\n{bank['niches'][n]}" for n in BUILTIN_NICHES
    )
    gen_prompt = f"""=== TASK: GENERATE NICHE VOICE ===
Below are 5 niche voice prompts that define Igloo's editorial style. Each one:
- Assigns a specific character with deep domain expertise
- Defines a voice (tone, cadence, attitude)
- Names an enemy (the thing this niche's mainstream gets wrong)
- Names a weapon (the specific knowledge that separates this voice from generic content)
- Lists niche-specific script rules with banned words

Study these 5 examples, then generate a new niche voice for: {theme or slug}

Follow the exact same structure. The character must feel as distinct and authoritative
as the existing five. The enemy must be something practitioners in this niche
actually believe. The banned words must be the clichés AI defaults to in this niche.

{examples}

Now generate the voice prompt for: {theme or slug}

Return ONLY the prompt body — no preamble, no markdown fences, no explanation."""

    try:
        body = _call_gemini(gen_prompt, api_key, temperature=0.7).strip()
    except Exception as e:
        print(
            f"  [prompt_bank] WARNING: dynamic niche generation failed ({e}), "
            f"falling back to finance voice",
            file=sys.stderr,
        )
        return "finance"

    # Strip code fences if Gemini ignored the instruction
    if body.startswith("```"):
        body = "\n".join(body.split("\n")[1:])
        if body.endswith("```"):
            body = body[:-3]
        body = body.strip()

    cache_file.write_text(body, encoding="utf-8")
    bank["niches"][slug] = body
    bank["good_examples"].setdefault(slug, bank["good_examples"]["finance"])
    bank["bad_examples"].setdefault(slug, bank["bad_examples"]["finance"])
    print(f"  [prompt_bank] Generated and cached new niche voice: {slug}")
    return slug


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def build_narration_prompt(
    theme: str,
    topic: str,
    duration: int,
    niche: str | None = None,
    audience: str | None = None,
    tone_override: str | None = None,
    brand_notes: str | None = None,
    cta_target: str | None = None,
    api_key: str | None = None,
    voice_id: str | None = None,
) -> tuple[str, str]:
    """Assemble the full system prompt per integrate_prompt_bank.md Step 3.

    `voice_id` is used for calibrated word-count targeting. If omitted, falls
    back to DEFAULT_WPS (2.5). Pass it from generate_script.py / web_app.py
    so the script Gemini writes matches the actual voice's pace.

    Returns (assembled_prompt, resolved_niche_label).
    """
    bank = load_prompt_bank()
    niche_label, _, source = resolve_niche(theme, niche, api_key)
    niche_prompt = bank["niches"][niche_label]
    good_example = bank["good_examples"].get(niche_label, "")
    bad_example = bank["bad_examples"].get(niche_label, "")

    # Brand defaults
    audience_str = audience or "general audience in this niche"
    tone_str = tone_override or "use niche default"
    brand_str = brand_notes or "none"
    cta_str = cta_target or "drive curiosity toward a deeper breakdown (not a hard sell)"

    # Calibrated word-count target (clamped to hard ceiling)
    duration = min(duration, MAX_DURATION_1X)
    wps = get_voice_wps(voice_id)
    target_words = int(round(duration * wps))
    band = max(3, int(round(target_words * WPS_BAND)))
    min_words = target_words - band
    max_words = target_words + band

    return f"""=== UNIVERSAL RULES ===
{bank["universal_rules"]}

=== NICHE VOICE ({niche_label} — resolved via {source}) ===
{niche_prompt}

=== BRAND CUSTOMIZATION ===
Audience: {audience_str}
Tone override: {tone_str}
Brand constraints: {brand_str}
CTA target: {cta_str}

=== REFERENCE: GOOD SCRIPT (match this quality) ===
{good_example}

=== REFERENCE: BAD SCRIPT (avoid everything annotated here) ===
{bad_example}

=== YOUR TASK ===
Write a {duration}-second reel script about: {topic}

Follow every universal rule. Match the niche voice. Use the good example as a quality benchmark. Avoid every failure pattern shown in the bad example.

SIMPLICITY (non-negotiable):
- Keep narration conversational and breezy. Short sentences. Let the visuals breathe.
- One concrete detail per reframe is enough — do not stack multiple studies, texts, or figures.
- Pace the viewer can absorb on first watch. If a sentence needs re-reading, it is too complex.
- Think "friend explaining over coffee" not "documentary narrator cramming facts."
- Leave room for moments to land. Not every second needs words.

Structure the script as a JSON array of ~9 scenes alternating "anchor" (direct-to-camera) and "b-roll" (cinematic footage). Start and end on anchor (odd scene count). Each scene object MUST have these exact fields — field names must match exactly, no typos:
- scene_id (int, 1..N)
- type ("anchor" or "b-roll")
- voice_emotion (one of: firm, urgent, contemplative, informative, warm, reassuring, gentle, confident)
- purpose (one of: HOOK, AGITATION, REFRAME, CTA — uppercase, exactly these four)
- narration_text (spelled with TWO Rs — narration_text, NOT naration_text)
- caption_text (1-3 KEY words from the narration in ALL CAPS — REQUIRED on every scene)

BANNED in narration_text: the characters ! * ( ) ; AND ALL-CAPS shouting AND markdown emphasis like *word*.

WORD COUNT: total narration across all scenes must be EXACTLY {target_words} words (acceptable range {min_words}-{max_words}). This voice speaks at {wps:.2f} words/second, so {target_words} words = {duration}s. Do NOT exceed {max_words} words — HARD LIMIT. Shorter is better than longer. If in doubt, cut a detail. Overshoot = automatic rejection. Do NOT use a listicle structure. Do NOT use banned phrases from the niche voice. Do NOT hedge.

Return ONLY the JSON array. No preamble, no markdown fences, no explanation.""", niche_label


# ---------------------------------------------------------------------------
# Voice calibration
# ---------------------------------------------------------------------------

def _load_calibration() -> dict:
    """Read voice_calibration.json. Returns empty shell if missing."""
    if not VOICE_CALIBRATION_PATH.exists():
        return {"voices": {}}
    try:
        return json.loads(VOICE_CALIBRATION_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(
            f"  [calibration] WARNING: failed to read {VOICE_CALIBRATION_PATH.name}: {e}",
            file=sys.stderr,
        )
        return {"voices": {}}


def get_voice_wps(voice_id: str | None, default: float = DEFAULT_WPS) -> float:
    """Return measured words-per-second for a voice ID, or default if unknown.

    This is the function callers should use everywhere a "how fast does this
    voice talk" answer is needed (script word-count targets, validator bands,
    duration sanity checks).
    """
    if not voice_id:
        return default
    cal = _load_calibration()
    entry = (cal.get("voices") or {}).get(voice_id)
    if not entry:
        return default
    wps = entry.get("measured_wps")
    if not isinstance(wps, (int, float)) or wps <= 0:
        return default
    return float(wps)


def update_voice_wps(voice_id: str, sample_wps: float,
                     voice_name: str | None = None) -> float:
    """Append a measured wps sample for a voice and update the rolling mean.

    Called by generate_voiceover.py after every successful run. The rolling
    mean self-corrects: first reel for a new voice uses DEFAULT_WPS, by the
    third or fourth run the average converges to reality.

    Returns the new measured_wps after the update.
    """
    if not voice_id or not isinstance(sample_wps, (int, float)) or sample_wps <= 0:
        return DEFAULT_WPS

    cal = _load_calibration()
    cal.setdefault("voices", {})
    max_samples = int(cal.get("_max_samples", 20))

    entry = cal["voices"].get(voice_id, {})
    samples = list(entry.get("samples") or [])
    samples.append(round(float(sample_wps), 4))
    if len(samples) > max_samples:
        samples = samples[-max_samples:]

    new_mean = round(sum(samples) / len(samples), 4)
    entry["samples"] = samples
    entry["measured_wps"] = new_mean
    if voice_name and not entry.get("name"):
        entry["name"] = voice_name
    # Lightweight timestamp without bringing in datetime everywhere
    try:
        from datetime import date
        entry["last_updated"] = date.today().isoformat()
    except Exception:
        pass

    cal["voices"][voice_id] = entry

    try:
        VOICE_CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        VOICE_CALIBRATION_PATH.write_text(
            json.dumps(cal, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        print(
            f"  [calibration] WARNING: failed to persist update for {voice_id}: {e}",
            file=sys.stderr,
        )

    return new_mean


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {"scene_id", "type", "voice_emotion", "purpose",
                   "narration_text", "caption_text"}
VALID_TYPES = {"anchor", "b-roll"}
VALID_EMOTIONS = {"firm", "urgent", "contemplative", "informative", "warm",
                  "reassuring", "gentle", "confident"}
VALID_PHASES = {"HOOK", "AGITATION", "REFRAME", "CTA"}

# Aliases the LLM occasionally emits → canonical voice_emotion. Keep tiny
# and intentional. Each entry is one observed Gemini drift.
VOICE_EMOTION_ALIASES = {
    "reframe": "firm",      # session 19: Gemini wrote phase name into emotion field
    "hook": "urgent",       # same class of bug
    "agitation": "firm",
    "cta": "confident",
    "calm": "contemplative",
    "serious": "firm",
    "soft": "gentle",
}

# Common Gemini field-name typos → canonical key.
FIELD_NAME_ALIASES = {
    "naration_text": "narration_text",
    "naration": "narration_text",
    "narration": "narration_text",
    "caption": "caption_text",
    "captiontext": "caption_text",
    "scene": "scene_id",
    "id": "scene_id",
}


# ---------------------------------------------------------------------------
# Deterministic repair (Bug 2 Layer A)
# ---------------------------------------------------------------------------

# Part 3 banned chars from voice_prompt_bank.md — these break TTS annotation.
_BANNED_NARRATION_CHARS = ["!", "*", "(", ")", ";"]

# Words that legitimately stay uppercase even when we de-shout narration.
_PRESERVE_UPPER = {
    "I", "AI", "USA", "UK", "EU", "NYC", "LA", "DNA", "CEO", "ROI",
    "FBI", "CIA", "NASA", "TV", "PR", "PhD", "MBA", "ATM", "GPS",
    "URL", "API", "FAQ", "VIP", "VR", "AR",
}


def _deshout(text: str) -> str:
    """Lowercase ALL-CAPS words while preserving acronyms ≤4 letters."""
    def _fix(match: re.Match) -> str:
        word = match.group(0)
        if len(word) <= 4 and word in _PRESERVE_UPPER:
            return word
        # Sentence-case: keep first letter case from context (downstream
        # capitalization passes can re-cap sentence starts).
        return word.lower()
    # Match runs of 2+ uppercase letters (single uppercase letters are fine)
    return re.sub(r"\b[A-Z]{2,}\b", _fix, text)


def _strip_banned(text: str) -> str:
    """Remove Part 3 banned chars and collapse extra whitespace."""
    for ch in _BANNED_NARRATION_CHARS:
        text = text.replace(ch, "")
    return re.sub(r"\s{2,}", " ", text).strip()


def _backfill_caption(narration: str) -> str:
    """Generate a fallback caption_text from the first few words of narration.

    This is the LAST RESORT — the retry prompt restates the requirement, so
    the LLM should produce real captions in practice. If we still get a
    miss, we'd rather ship a dumb caption than crash the pipeline.
    """
    words = re.findall(r"[A-Za-z']+", narration)
    if not words:
        return ""
    return " ".join(words[:3]).upper()


def repair_scenes(scenes) -> tuple[list, list[str]]:
    """Mechanically fix recoverable bugs in a Gemini script response.

    Runs BEFORE validate_scenes. Handles the entire class of LLM-drift bugs
    that don't need an LLM to fix:
      - Field name typos (naration_text, etc.)
      - Banned characters in narration_text
      - ALL CAPS shouting in narration_text
      - Missing caption_text (backfilled from narration)
      - Voice_emotion that's actually a phase name ("reframe", "hook")
      - String scene_id that should be int
      - Lowercase phase values

    Returns (repaired_scenes, repair_log). The repair_log is a list of
    human-readable strings describing what was fixed, useful for debugging
    LLM drift trends without making them fail validation.
    """
    log: list[str] = []
    if not isinstance(scenes, list):
        return scenes, log

    repaired: list = []
    for idx, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            repaired.append(scene)
            continue

        # 1. Rename typo'd keys
        for bad, good in FIELD_NAME_ALIASES.items():
            if bad in scene and good not in scene:
                scene[good] = scene.pop(bad)
                log.append(f"scene {idx}: renamed key {bad!r} → {good!r}")

        # 2. Coerce scene_id to int
        sid = scene.get("scene_id")
        if isinstance(sid, str) and sid.strip().isdigit():
            scene["scene_id"] = int(sid.strip())
            log.append(f"scene {idx}: coerced scene_id str → int")

        # 3. Clean narration_text
        narration = scene.get("narration_text")
        if isinstance(narration, str):
            cleaned = _strip_banned(narration)
            cleaned = _deshout(cleaned)
            if cleaned != narration:
                scene["narration_text"] = cleaned
                log.append(f"scene {idx}: cleaned narration_text (banned chars / shouting)")

        # 4. Normalize voice_emotion (lowercase + alias map)
        emo = scene.get("voice_emotion")
        if isinstance(emo, str):
            emo_lower = emo.strip().lower()
            if emo_lower in VOICE_EMOTION_ALIASES:
                scene["voice_emotion"] = VOICE_EMOTION_ALIASES[emo_lower]
                log.append(
                    f"scene {idx}: voice_emotion {emo!r} → {scene['voice_emotion']!r} (alias)"
                )
            elif emo != emo_lower and emo_lower in VALID_EMOTIONS:
                scene["voice_emotion"] = emo_lower
                log.append(f"scene {idx}: voice_emotion lowercased")

        # 5. Normalize purpose to canonical phase
        purpose = scene.get("purpose")
        if isinstance(purpose, str):
            p_upper = purpose.strip().upper()
            if p_upper in VALID_PHASES and purpose != p_upper:
                scene["purpose"] = p_upper
                log.append(f"scene {idx}: purpose uppercased to {p_upper}")

        # 6. Normalize type
        t = scene.get("type")
        if isinstance(t, str):
            t_lower = t.strip().lower()
            if t_lower == "broll":
                t_lower = "b-roll"
            if t_lower in VALID_TYPES and t != t_lower:
                scene["type"] = t_lower
                log.append(f"scene {idx}: type normalized to {t_lower!r}")

        # 7. Backfill missing caption_text (last-resort safety net)
        if not scene.get("caption_text") and isinstance(scene.get("narration_text"), str):
            scene["caption_text"] = _backfill_caption(scene["narration_text"])
            log.append(f"scene {idx}: backfilled caption_text from narration")

        repaired.append(scene)

    return repaired, log


# ---------------------------------------------------------------------------
# Retry prompt (Bug 2 Layer B)
# ---------------------------------------------------------------------------

def build_retry_prompt(base_prompt: str, failures: list[str], duration: int,
                       voice_id: str | None = None) -> str:
    """Build a retry prompt that RESTATES the full schema, not just the failures.

    The original retry approach (just append "failed: {failures}, try again")
    was actively harmful: Gemini fixed the called-out problem and silently
    introduced new ones (caption drops, naration_text typo, asterisks,
    invalid voice_emotion). This version restates every constraint that has
    historically drifted.
    """
    duration = min(duration, MAX_DURATION_1X)
    wps = get_voice_wps(voice_id)
    target_words = int(round(duration * wps))
    band = max(3, int(round(target_words * WPS_BAND)))
    min_words = target_words - band
    max_words = target_words + band

    return f"""{base_prompt}

=== PREVIOUS ATTEMPT REJECTED ===
The previous attempt failed validation:
{chr(10).join(f"  - {f}" for f in failures)}

You MUST fix the failures AND keep every other field correct. Generate a
COMPLETE new script (all scenes), not a diff.

=== HARD SCHEMA — every scene MUST have these exact field names ===
  scene_id        — integer, 1-indexed, sequential
  type            — exactly "anchor" or "b-roll" (with the hyphen)
  voice_emotion   — one of: firm, urgent, contemplative, informative,
                    warm, reassuring, gentle, confident
                    (NOT a phase name. "reframe", "hook", "agitation",
                     "cta" are PHASES, not emotions.)
  purpose         — one of: HOOK, AGITATION, REFRAME, CTA (uppercase)
  narration_text  — spelled with TWO Rs: n-a-r-r-a-t-i-o-n_text.
                    NOT "naration_text". This is a recurring typo.
                    REQUIRED on every scene, never omit it.
  caption_text    — REQUIRED on every scene. 1-3 KEY words from the
                    narration in ALL CAPS. Never drop this field.

=== BANNED IN narration_text ===
  - Characters: ! * ( ) ;
  - ALL CAPS shouting (use natural sentence case)
  - Markdown emphasis like *word* or **word**

=== WORD COUNT ===
  Total narration across all scenes: {target_words} words
  Acceptable range: {min_words}-{max_words} words (HARD CEILING — exceeding {max_words} = automatic rejection, no exceptions)
  (Calibrated for this voice at {wps:.2f} words/second × {duration}s. Shorter is better.)

=== STRUCTURE ===
  - Start AND end on an "anchor" scene
  - Alternate anchor/b-roll
  - Odd number of scenes (~9)

Return ONLY the JSON array. No preamble, no markdown fences, no explanation."""


def validate_scenes(scenes: list, duration: int,
                    voice_id: str | None = None) -> list[str]:
    """Run the Step 5 validation checks. Returns list of failure reasons.
    Empty list = pass.

    `voice_id` is used for the calibrated word-count band. If omitted, falls
    back to DEFAULT_WPS — caller should always pass it from .env.
    """
    failures: list[str] = []
    duration = min(duration, MAX_DURATION_1X)

    if not isinstance(scenes, list) or not scenes:
        return ["Output is not a non-empty JSON array of scenes"]

    # Schema check — catches the `naration_text` typo class
    for i, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            failures.append(f"Scene {i} is not an object")
            continue
        missing = REQUIRED_FIELDS - set(scene.keys())
        if missing:
            failures.append(
                f"Scene {scene.get('scene_id', i)} missing/typo'd fields: "
                f"{sorted(missing)} (got: {sorted(scene.keys())})"
            )
        # Key present but value blank is the same class of Gemini drift as
        # a missing key — downstream voiceover/slicing assumes non-empty.
        narration = scene.get("narration_text")
        if isinstance(narration, str) and not narration.strip():
            failures.append(
                f"Scene {scene.get('scene_id', i)} has empty narration_text"
            )
        if scene.get("type") not in VALID_TYPES:
            failures.append(
                f"Scene {scene.get('scene_id', i)} has invalid type: "
                f"{scene.get('type')!r}"
            )
        if scene.get("voice_emotion") and scene["voice_emotion"] not in VALID_EMOTIONS:
            failures.append(
                f"Scene {scene.get('scene_id', i)} has invalid voice_emotion: "
                f"{scene['voice_emotion']!r}"
            )

    # If schema is broken, narration checks below will be noisy — bail early
    if failures:
        return failures

    # Structural checks
    if len(scenes) < 5:
        failures.append(
            f"Too few scenes ({len(scenes)}) — minimum 5 for valid reel structure"
        )
    types = [s["type"] for s in scenes]
    if types[0] != "anchor":
        failures.append(f"First scene must be anchor, got {types[0]!r}")
    if types[-1] != "anchor":
        failures.append(f"Last scene must be anchor, got {types[-1]!r}")

    full_text = " ".join(s["narration_text"] for s in scenes).strip()
    full_lower = full_text.lower()
    word_count = len(full_text.split())

    # Calibrated word-count band: target = duration * measured_wps for this
    # voice, with a ±WPS_BAND tolerance. Tight enough that PASS means PASS.
    wps = get_voice_wps(voice_id)
    target_words = int(round(duration * wps))
    band = max(3, int(round(target_words * WPS_BAND)))
    min_words = target_words - band
    max_words = target_words + band
    if word_count < min_words or word_count > max_words:
        failures.append(
            f"Word count {word_count} outside band {min_words}-{max_words} "
            f"(target {target_words} for {duration}s @ {wps:.2f} wps)"
        )

    # Hard ceiling — no script may exceed the absolute max regardless of
    # requested duration. Prevents reels from ever exceeding 50s at 1.2x.
    # No band tolerance here — this is the absolute wall.
    hard_max = int(round(MAX_DURATION_1X * wps))
    if word_count > hard_max:
        failures.append(
            f"HARD CEILING EXCEEDED: {word_count} words > absolute max "
            f"{hard_max} (max {MAX_DURATION_1X}s @ {wps:.2f} wps)"
        )

    # Hard floor — no script may fall below the absolute min. Prevents reels
    # from ever delivering below 30s at 1.2x (product contract).
    hard_min = int(round(MIN_DURATION_1X * wps))
    if word_count < hard_min:
        failures.append(
            f"HARD FLOOR EXCEEDED: {word_count} words < absolute min "
            f"{hard_min} (min {MIN_DURATION_1X}s @ {wps:.2f} wps)"
        )

    # AI-tell scan
    hits = [p for p in AI_TELL_PHRASES if p in full_lower]
    if hits:
        failures.append(f"AI-tell phrases detected: {hits}")

    # Listicle scan
    if re.search(r"\bfirst[,.]?\s+second[,.]?\s+third\b", full_lower):
        failures.append("Listicle pattern detected (first/second/third)")
    if re.search(r"^\s*[1-9][.)]\s", full_text, re.MULTILINE):
        failures.append("Numbered listicle pattern detected")

    return failures


