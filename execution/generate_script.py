"""
generate_script.py — Interactive script generator for the Reel Engine pipeline.

Guides the user through 4 sub-steps:
  0a. Theme + topic (from CLI)
  0b. Narration script (Gemini generates or adapts user-provided text)
  0c. Character selection (Gemini suggests 3 options, user picks)
  0d. Full JSON assembly (Gemini fills in all prompts, user approves)

Usage:
    py execution/generate_script.py --theme "Health & Wellness" --topic "Fasting when sick"
    py execution/generate_script.py --theme "Tennis" --topic "Forehand technique" --script "Your body naturally..."
    py execution/generate_script.py --theme "Parenting" --topic "Raising confident child" --duration 35

Output:
    .tmp/{topic_slug}/{topic_slug}_script.json
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Local — shared with web_app.py so the prompt bank lives in one place
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompt_bank as pb  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_env(key: str) -> str:
    # 1. Process environment (Modal secrets, CI, shell exports) — preferred
    val = os.environ.get(key)
    if val and not val.startswith("<"):
        return val
    # 2. Fall back to .env file (local dev convenience)
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v and not v.startswith("<"):
                        return v
    print(f"ERROR: {key} not set in environment or .env", file=sys.stderr)
    sys.exit(1)


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '_', text)
    return text.strip('_')


def call_gemini(prompt: str, api_key: str, temperature: float = 0.5,
                max_tokens: int = 8192, timeout: int = 60) -> str:
    """Call Gemini 2.5 Flash and return the text response."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingBudget": 0}
        }
    }

    data = json.dumps(payload).encode()

    # Retry on 429/5xx with exponential backoff. Gemini 2.5 Flash returns 503
    # "high demand" transient errors fairly often; blocking once on this would
    # fail production runs unnecessarily. Max ~90s total wait.
    import time as _time
    backoffs = [5, 10, 20, 40]
    last_err = None
    result = None
    for attempt, wait_s in enumerate([0] + backoffs):
        if wait_s:
            print(f"  [gemini] Retry {attempt}/{len(backoffs)} after {wait_s}s "
                  f"(last: {last_err})", file=sys.stderr)
            _time.sleep(wait_s)
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            last_err = f"HTTP {e.code}"
            # Retry on 429 (rate limit) and 5xx (server)
            if e.code == 429 or 500 <= e.code < 600:
                continue
            print(f"ERROR: Gemini API returned {e.code}: {body}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            last_err = f"URLError: {e.reason}"
            continue

    if result is None:
        print(f"ERROR: Gemini API failed after {len(backoffs) + 1} attempts: {last_err}",
              file=sys.stderr)
        sys.exit(1)

    parts = result["candidates"][0]["content"]["parts"]
    text = ""
    for part in parts:
        if "text" in part:
            text = part["text"].strip()
    return text


def extract_json(text: str) -> str:
    """Extract JSON from Gemini response, handling code fences."""
    if "```" in text:
        blocks = text.split("```")
        for block in blocks[1::2]:  # odd-indexed blocks are inside fences
            cleaned = block.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            return cleaned
    return text.strip()


def parse_json_response(text: str) -> dict | list:
    """Extract and parse JSON from Gemini response."""
    cleaned = extract_json(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find a JSON object or array
        obj_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned)
        if obj_match:
            return json.loads(obj_match.group(1))
        raise


# Module-level flag toggled by --non-interactive. When True, prompt_user
# returns the passed-in `default` instead of blocking on input(). Used by
# Modal/CI runs where stdin is closed.
NON_INTERACTIVE = False


def prompt_user(message: str, valid: list[str], default: str | None = None) -> str:
    """Prompt user for input, validating against allowed values."""
    if NON_INTERACTIVE:
        if default is None:
            print(f"ERROR: prompt_user called in non-interactive mode without "
                  f"a default for: {message}", file=sys.stderr)
            sys.exit(1)
        print(f"{message} [auto: {default}]")
        return default
    valid_lower = [v.lower() for v in valid]
    while True:
        response = input(f"{message} ").strip()
        if response.lower() in valid_lower:
            return response.lower()
        if not response and "" in valid:
            return ""
        print(f"  Please enter one of: {', '.join(valid)}")


def print_divider(title: str = ""):
    if title:
        print(f"\n{'=' * 55}")
        print(f"  {title}")
        print(f"{'=' * 55}")
    else:
        print(f"\n{'-' * 55}")


# ---------------------------------------------------------------------------
# Sub-step 0b: Narration Script
# ---------------------------------------------------------------------------

# NARRATION_GENERATE_PROMPT removed — the from-scratch path now goes through
# prompt_bank.build_narration_prompt() (see generate_narration() below).
# The adapt path is kept because user-supplied scripts must be preserved.

NARRATION_ADAPT_PROMPT = """You are a viral short-form video scriptwriter. The user has provided a narration script. Adapt it into a structured scene-by-scene format for a {duration}-second vertical reel.

TOPIC: {topic}
THEME: {theme}

USER'S SCRIPT:
{script}

RULES:
- Break the script into alternating "anchor" (direct-to-camera) and "b-roll" (cinematic footage) scenes
- Start and end with anchor scenes
- Aim for ~9 scenes (odd number)
- Preserve the user's words and voice as much as possible — only adjust for pacing and scene breaks
- If the script is too long/short for {duration}s, adjust slightly (trim wordiness or add a beat)
- Hook must be in the first scene, CTA in the last

For each scene provide:
- scene_id (integer, sequential starting at 1)
- type ("anchor" or "b-roll")
- voice_emotion (one of: firm, urgent, contemplative, informative, warm, reassuring, gentle, confident)
- purpose (short description: HOOK, WHY, STAKES, REFRAME, SCIENCE, SOLUTION, CTA, etc.)
- narration_text (the actual words spoken)
- caption_text (same as narration but with 1-2 KEY emphasis words in ALL CAPS)

Return ONLY a JSON array of scene objects. No explanation."""


NARRATION_EDIT_PROMPT = """You are a viral short-form video scriptwriter. Revise the following scene-by-scene script based on the user's feedback.

CURRENT SCRIPT:
{current_script}

USER'S FEEDBACK:
{feedback}

Apply the changes while maintaining the alternating anchor/b-roll structure. Keep scene_ids sequential.

Return ONLY the revised JSON array of scene objects. No explanation."""


def generate_narration(theme: str, topic: str, duration: int,
                       user_script: str | None, api_key: str,
                       niche: str | None = None,
                       voice_id: str | None = None) -> list:
    """Sub-step 0b: Generate or adapt narration, with user review loop.

    From-scratch path uses the prompt bank (execution/prompt_bank.md) — see
    integrate_prompt_bank.md. The user-supplied-script path keeps the legacy
    NARRATION_ADAPT_PROMPT because the user's words are sacred and we only
    re-shape them into scenes.
    """

    print_divider("Step 0b: Narration Script")

    if user_script:
        print("  Adapting your script into scene-by-scene format...")
        prompt = NARRATION_ADAPT_PROMPT.format(
            theme=theme, topic=topic, duration=duration, script=user_script)
        gen_temperature = 0.7
    else:
        print("  Generating narration script via prompt bank...")
        prompt, resolved_niche = pb.build_narration_prompt(
            theme=theme, topic=topic, duration=duration,
            niche=niche, api_key=api_key, voice_id=voice_id)
        print(f"  Niche voice: {resolved_niche}")
        print(f"  Calibrated wps: {pb.get_voice_wps(voice_id):.2f} "
              f"(target ~{int(round(duration * pb.get_voice_wps(voice_id)))} words)")
        gen_temperature = 0.9  # Step 4 of integrate_prompt_bank.md

    raw = call_gemini(prompt, api_key, temperature=gen_temperature)
    scenes = parse_json_response(raw)

    # Bug 2 fix: deterministic repair pass BEFORE validation. Fixes recoverable
    # LLM drift (typo'd field names, banned chars, missing captions, etc.)
    # without burning a retry call.
    if not user_script:
        scenes, repair_log = pb.repair_scenes(scenes)
        if repair_log:
            print(f"  [repair] Auto-fixed {len(repair_log)} issue(s):")
            for entry in repair_log:
                print(f"    - {entry}")

        # Step 5: validate. Regenerate once if the first attempt still fails
        # after repair. The retry prompt restates the FULL schema, not just
        # the failures, to prevent the multi-bug cascade from session 19.
        failures = pb.validate_scenes(scenes, duration, voice_id=voice_id)
        if failures:
            print(f"  [validator] First attempt rejected: {failures}")
            print("  Regenerating with full schema restatement...")
            retry_prompt = pb.build_retry_prompt(
                base_prompt=prompt,
                failures=failures,
                duration=duration,
                voice_id=voice_id,
            )
            raw = call_gemini(retry_prompt, api_key, temperature=gen_temperature)
            scenes = parse_json_response(raw)
            scenes, retry_repair_log = pb.repair_scenes(scenes)
            if retry_repair_log:
                print(f"  [repair] Post-retry auto-fixed {len(retry_repair_log)} issue(s):")
                for entry in retry_repair_log:
                    print(f"    - {entry}")
            failures = pb.validate_scenes(scenes, duration, voice_id=voice_id)
            if failures:
                if any("HARD CEILING" in f for f in failures):
                    print(f"  [validator] FATAL: hard ceiling exceeded after retry: {failures}")
                    print("  Cannot produce a reel that exceeds the duration limit. Aborting.")
                    sys.exit(1)
                print(f"  [validator] WARNING: still failing after retry: {failures}")
                print("  Continuing with warnings — flag for manual review.")

    while True:
        # Display scenes
        print_divider("Generated Script")
        full_narration = []
        for s in scenes:
            icon = "🎙" if s["type"] == "anchor" else "🎬"
            print(f"\n  {icon} Scene {s['scene_id']} ({s['type']}) — {s.get('purpose', '')}")
            print(f"     Emotion: {s.get('voice_emotion', 'default')}")
            print(f"     \"{s['narration_text']}\"")
            print(f"     Caption: {s.get('caption_text', '')}")
            full_narration.append(s["narration_text"])

        word_count = sum(len(t.split()) for t in full_narration)
        est_duration = word_count / 2.5
        print(f"\n  Total: {len(scenes)} scenes, {word_count} words, ~{est_duration:.0f}s estimated")
        print_divider()

        choice = prompt_user(
            "  [A]pprove  [E]dit  [R]egenerate  [Q]uit:",
            ["a", "approve", "e", "edit", "r", "regenerate", "q", "quit"],
            default="a")

        if choice in ("a", "approve"):
            print("  Script locked.")
            return scenes

        elif choice in ("e", "edit"):
            feedback = input("  Describe your changes: ").strip()
            if not feedback:
                continue
            print("  Revising...")
            edit_prompt = NARRATION_EDIT_PROMPT.format(
                current_script=json.dumps(scenes, indent=2),
                feedback=feedback)
            raw = call_gemini(edit_prompt, api_key, temperature=0.5)
            scenes = parse_json_response(raw)

        elif choice in ("r", "regenerate"):
            print("  Regenerating from scratch...")
            if user_script:
                raw = call_gemini(prompt, api_key, temperature=0.8)
            else:
                raw = call_gemini(prompt, api_key, temperature=0.9)
            scenes = parse_json_response(raw)

        elif choice in ("q", "quit"):
            print("  Aborted.")
            sys.exit(0)


# ---------------------------------------------------------------------------
# Sub-step 0c: Character Selection
# ---------------------------------------------------------------------------

CHARACTER_PROMPT = """Based on this script for a "{theme}" reel about "{topic}", suggest 3 anchor character options.

SCRIPT NARRATION:
{narration}

For each character option, provide a JSON object with these exact fields:
- "option": integer (1, 2, or 3)
- "description": A detailed description of who they are, what they look like, what they're wearing, and their setting/environment. Be specific about ethnicity, age, clothing, and surroundings.
- "image_prompt": A photorealistic Imagen-ready prompt. Must include: specific physical features, clothing, setting details, camera specs (e.g., "shot on Sony A7IV, 50mm f/1.8, shallow depth of field"), lighting description. NO abstract emotional cues.
- "voice": an object with "gender" (male/female), "accent" (e.g., "American English, neutral"), "tone" (e.g., "calm, confident, conversational")

Make the characters diverse and authentic to the content. Each option should feel distinctly different.

Return ONLY a JSON array of 3 character objects. No explanation."""


CHARACTER_CUSTOM_PROMPT = """The user wants a custom anchor character for their reel. Generate the full character object based on their description.

USER'S CHARACTER DESCRIPTION:
{description}

REEL TOPIC: {topic}

Generate a JSON object with:
- "description": Expand the user's description into a detailed character + setting description
- "image_prompt": A photorealistic Imagen-ready prompt with camera specs (e.g., "shot on Sony A7IV, 50mm f/1.8"), lighting, specific visual details. NO abstract emotional cues.
- "voice": an object with "gender", "accent", "tone"

Return ONLY the JSON object. No explanation."""


def select_character(theme: str, topic: str, scenes: list,
                     api_key: str) -> dict:
    """Sub-step 0c: Generate character options, let user pick."""

    print_divider("Step 0c: Character Selection")
    print("  Generating character options...")

    narration = " ".join(s["narration_text"] for s in scenes)
    prompt = CHARACTER_PROMPT.format(
        theme=theme, topic=topic, narration=narration)
    raw = call_gemini(prompt, api_key, temperature=0.7)
    options = parse_json_response(raw)

    while True:
        for i, opt in enumerate(options, 1):
            print(f"\n  --- Option {i} ---")
            print(f"  {opt.get('description', '')}")
            voice = opt.get("voice", {})
            print(f"  Voice: {voice.get('gender', '?')}, {voice.get('accent', '?')}, {voice.get('tone', '?')}")

        print_divider()
        choice = prompt_user(
            "  [1/2/3] to select  [C]ustom  [R]egenerate  [Q]uit:",
            ["1", "2", "3", "c", "custom", "r", "regenerate", "q", "quit"],
            default="1")

        if choice in ("1", "2", "3"):
            selected = options[int(choice) - 1]
            print(f"  Selected option {choice}.")
            return {
                "description": selected["description"],
                "image_prompt": selected["image_prompt"],
                "voice": selected["voice"]
            }

        elif choice in ("c", "custom"):
            desc = input("  Describe your character: ").strip()
            if not desc:
                continue
            print("  Generating full character from your description...")
            custom_prompt = CHARACTER_CUSTOM_PROMPT.format(
                description=desc, topic=topic)
            raw = call_gemini(custom_prompt, api_key, temperature=0.5)
            custom = parse_json_response(raw)
            print(f"\n  Description: {custom.get('description', '')}")
            voice = custom.get("voice", {})
            print(f"  Voice: {voice.get('gender', '?')}, {voice.get('accent', '?')}, {voice.get('tone', '?')}")

            ok = prompt_user("  [A]pprove  [C]ustom again  [B]ack to options:",
                             ["a", "approve", "c", "custom", "b", "back"],
                             default="a")
            if ok in ("a", "approve"):
                return {
                    "description": custom["description"],
                    "image_prompt": custom["image_prompt"],
                    "voice": custom["voice"]
                }
            elif ok in ("b", "back"):
                continue
            # else loop back to custom

        elif choice in ("r", "regenerate"):
            print("  Regenerating character options...")
            raw = call_gemini(prompt, api_key, temperature=0.9)
            options = parse_json_response(raw)

        elif choice in ("q", "quit"):
            print("  Aborted.")
            sys.exit(0)


# ---------------------------------------------------------------------------
# Sub-step 0d: Full JSON Assembly
# ---------------------------------------------------------------------------

ASSEMBLY_PROMPT = """You are generating a complete script JSON for the Reel Engine video pipeline.

THEME: {theme}
TOPIC: {topic}
TARGET DURATION: {duration}s

LOCKED SCENES (narration is final):
{scenes_json}

ANCHOR CHARACTER:
{character_json}

Generate the COMPLETE script JSON with all fields. Follow this exact structure:

{{
  "video_file": "{slug}.mp4",
  "theme": "{theme}",
  "topic": "{topic}",
  "total_scenes": <number of scenes>,
  "voiceover_speed": 1.3,
  "voiceover_model": "eleven_turbo_v2_5",
  "skip_caption_scenes": [],
  "anchor_character": {{
    "description": "<from character selection>",
    "image_prompt": "<from character selection>",
    "voice": {{
      "gender": "<from character selection>",
      "accent": "<from character selection>",
      "tone": "<from character selection>"
    }}
  }},
  "scenes": [
    <For each ANCHOR scene:>
    {{
      "scene_id": <int>,
      "type": "anchor",
      "voice_emotion": "<from narration>",
      "purpose": "<from narration>",
      "narration_text": "<from narration>",
      "video_generation": {{
        "method": "lip-sync",
        "kling_duration": "driven by audio",
        "image_prompt": <null for scenes after scene 1, full prompt for scene 1>,
        "image_note": "Reuse anchor image from scene 1" (for scenes after 1),
        "video_prompt": "<describe the character's gestures/expression matching the emotion, photorealistic, keep minimal to not override lip-sync>"
      }},
      "caption_text": "<from narration>"
    }},

    <For each B-ROLL scene:>
    {{
      "scene_id": <int>,
      "type": "b-roll",
      "voice_emotion": "<from narration>",
      "purpose": "<from narration>",
      "narration_text": "<from narration>",
      "video_generation": {{
        "method": "image-to-video",
        "kling_duration": 5,
        "trim_to": <estimate from word count, usually 3-5s>,
        "image_prompt": "<photorealistic, concrete visual, camera specs, NO abstract cues>",
        "video_prompt": "<describe slow camera movement + subtle motion matching narration>"
      }},
      "caption_text": "<from narration>"
    }}

  ],
  "audio": {{
    "voice_over": {{
      "full_script": "<all narration concatenated with spaces>",
      "file": "voiceover.mp3",
      "timestamps_file": "voiceover_words.json",
      "speed": 1.3,
      "model": "eleven_turbo_v2_5"
    }},
    "background_music": {{
      "description": "<music description matching the mood arc of the reel, MUST include 'instrumental only, no vocals'>",
      "bpm": <appropriate tempo>,
      "genre": "<genre>"
    }}
  }},
  "assembly_notes": {{
    "transitions": "0.3s cross-dissolve between all scenes.",
    "captions": "Large white text, bold emphasized words rendered yellow.",
    "color_grade": "<appropriate color grade>",
    "aspect_ratio": "9:16 (vertical reel format)",
    "audio_sync": "Anchor scenes: lip-sync via Avatar API. B-roll: voiceover plays over footage."
  }},
  "production_summary": {{
    "total_kling_generations": <count all clips>,
    "images_needed": {{
      "anchor": 1,
      "broll": <count b-roll images>,
      "total": <total>,
      "reuse": "Anchor image reused across all anchor scenes"
    }}
  }}
}}

IMPORTANT:
- Do NOT include narration_start, narration_end, scene_duration, audio_slice, or actual_duration_seconds — these are computed by the pipeline
- Do NOT include elevenlabs_voice_id — this is set by the voice selection step
- Image prompts: photorealistic, concrete visuals, camera specs (Canon R5/Sony A7IV, specific lens + aperture), lighting description, shallow depth of field. NO abstract emotional descriptions.
- Video prompts for anchors: keep minimal (character + simple gesture/expression). Strong motion directives hurt lip-sync quality.
- Video prompts for b-roll: describe slow camera movements (dolly, drift, push-in) + subtle motion in scene.
- Background music description MUST end with "Instrumental only, no vocals, no singing, no humming."

Return ONLY the JSON object. No explanation."""


def assemble_full_json(theme: str, topic: str, slug: str, duration: int,
                       scenes: list, character: dict,
                       api_key: str) -> dict:
    """Sub-step 0d: Gemini assembles the complete script JSON."""

    print_divider("Step 0d: Full Script Assembly")
    print("  Generating complete script JSON with all prompts...")

    prompt = ASSEMBLY_PROMPT.format(
        theme=theme, topic=topic, slug=slug, duration=duration,
        scenes_json=json.dumps(scenes, indent=2),
        character_json=json.dumps(character, indent=2))

    raw = call_gemini(prompt, api_key, temperature=0.3, max_tokens=16384,
                      timeout=120)
    script_json = parse_json_response(raw)

    while True:
        # Display summary
        s_list = script_json.get("scenes", [])
        anchor_count = sum(1 for s in s_list if s.get("type") == "anchor")
        broll_count = sum(1 for s in s_list if s.get("type") == "b-roll")
        clip_count = 0
        for s in s_list:
            vg = s.get("video_generation", {})
            if "clips" in vg:
                clip_count += len(vg["clips"])
            else:
                clip_count += 1

        char_desc = script_json.get("anchor_character", {}).get("description", "")
        music = script_json.get("audio", {}).get("background_music", {})

        print(f"\n  Scenes: {len(s_list)} ({anchor_count} anchor, {broll_count} b-roll)")
        print(f"  Video clips to generate: {clip_count}")
        print(f"  Character: {char_desc[:80]}...")
        print(f"  Music: {music.get('genre', '?')} @ {music.get('bpm', '?')} BPM")

        # Show scene overview
        for s in s_list:
            icon = "A" if s.get("type") == "anchor" else "B"
            text = s.get("narration_text", "")[:60]
            print(f"    [{icon}] Scene {s.get('scene_id', '?')}: {text}...")

        print_divider()
        choice = prompt_user(
            "  [A]pprove and save  [E]dit  [R]egenerate  [Q]uit:",
            ["a", "approve", "e", "edit", "r", "regenerate", "q", "quit"],
            default="a")

        if choice in ("a", "approve"):
            return script_json

        elif choice in ("e", "edit"):
            feedback = input("  Describe your changes: ").strip()
            if not feedback:
                continue
            print("  Revising...")
            edit_prompt = f"""Revise this script JSON based on user feedback.

CURRENT JSON:
{json.dumps(script_json, indent=2)}

USER FEEDBACK:
{feedback}

Return ONLY the revised complete JSON object. No explanation."""
            raw = call_gemini(edit_prompt, api_key, temperature=0.3,
                              max_tokens=16384, timeout=120)
            script_json = parse_json_response(raw)

        elif choice in ("r", "regenerate"):
            print("  Regenerating full JSON...")
            raw = call_gemini(prompt, api_key, temperature=0.5,
                              max_tokens=16384, timeout=120)
            script_json = parse_json_response(raw)

        elif choice in ("q", "quit"):
            print("  Aborted.")
            sys.exit(0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a script JSON for the Reel Engine pipeline")
    parser.add_argument("--theme", required=True,
                        help="Theme (e.g., 'Health & Wellness', 'Tennis', 'Parenting')")
    parser.add_argument("--topic", required=True,
                        help="Topic (e.g., 'Fasting when sick', 'Forehand technique')")
    parser.add_argument("--script", default=None,
                        help="User-provided narration text (if omitted, Gemini generates)")
    parser.add_argument("--niche", default=None,
                        help="Prompt-bank niche voice (spirituality/fitness/finance/parenting/wellness). "
                             "If omitted, derived from --theme keywords; unknown themes trigger dynamic generation.")
    parser.add_argument("--duration", type=int, default=40,
                        help="Target duration in seconds (default: 40)")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: .tmp/{topic_slug}/)")
    parser.add_argument("--non-interactive", action="store_true",
                        help="Auto-approve all review prompts. For Modal/CI runs "
                             "where stdin is closed. Defaults: approve narration, "
                             "pick character option 1, approve final script.")
    args = parser.parse_args()

    if args.non_interactive:
        global NON_INTERACTIVE
        NON_INTERACTIVE = True

    api_key = load_env("GEMINI_API_KEY")
    # Voice ID drives the calibrated word-count target so the script Gemini
    # writes matches the actual voice's pace. .env is the source of truth.
    try:
        voice_id = load_env("ELEVENLABS_VOICE_ID")
    except SystemExit:
        voice_id = None
        print("  [warn] ELEVENLABS_VOICE_ID not set — using default wps target")
    project_root = Path(__file__).resolve().parent.parent

    slug = slugify(args.topic)

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = project_root / ".tmp" / slug

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{slug}_script.json"

    # --- Sub-step 0a: Theme + Topic ---
    print_divider("Step 0a: Theme + Topic")
    print(f"  Theme: {args.theme}")
    print(f"  Topic: {args.topic}")
    print(f"  Target duration: {args.duration}s")
    print(f"  Output: {output_path}")

    if output_path.exists():
        choice = prompt_user(
            f"\n  Script already exists at {output_path}\n  [O]verwrite  [Q]uit:",
            ["o", "overwrite", "q", "quit"],
            default="o")
        if choice in ("q", "quit"):
            print("  Aborted.")
            sys.exit(0)

    # --- Sub-step 0b: Narration ---
    scenes = generate_narration(args.theme, args.topic, args.duration,
                                args.script, api_key, niche=args.niche,
                                voice_id=voice_id)

    # --- Sub-step 0c: Character ---
    character = select_character(args.theme, args.topic, scenes, api_key)

    # --- Sub-step 0d: Full JSON ---
    script_json = assemble_full_json(
        args.theme, args.topic, slug, args.duration,
        scenes, character, api_key)

    # Save
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(script_json, f, indent=2, ensure_ascii=False)

    print_divider("DONE")
    print(f"  Script saved to: {output_path}")
    print(f"  Next: py execution/run_pipeline.py {output_path}")


if __name__ == "__main__":
    main()
