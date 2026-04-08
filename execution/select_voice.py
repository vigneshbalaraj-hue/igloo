"""
select_voice.py — Auto-select the best ElevenLabs voice for a script's character profile.

Two-pass approach:
  Pass 1: Search ElevenLabs shared voice library with structured filters + text search.
          Use Gemini to rank candidates against the character profile.
  Pass 2 (fallback): If no good library match, generate a custom AI voice via
          ElevenLabs text-to-voice/design endpoint.

Usage:
    py execution/select_voice.py .tmp/screen_addiction_children/screen_addiction_36s_script.json
    py execution/select_voice.py .tmp/screen_addiction_children/screen_addiction_36s_script.json --top 5
    py execution/select_voice.py .tmp/screen_addiction_children/screen_addiction_36s_script.json --fallback-only

Output:
    Updates script JSON with new voice_id in anchor_character.voice and audio.voice_over
    Updates .env ELEVENLABS_VOICE_ID
    Saves preview audio to {script_dir}/voice_previews/
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path


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


def update_env(key: str, value: str):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    lines = env_path.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# ElevenLabs API helpers
# ---------------------------------------------------------------------------

def api_get(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("xi-api-key", api_key)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def api_post(url: str, api_key: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("xi-api-key", api_key)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def download_file(url: str, dest: Path):
    urllib.request.urlretrieve(url, str(dest))


# ---------------------------------------------------------------------------
# Pass 1: Search shared voice library
# ---------------------------------------------------------------------------

def build_voice_profile(script: dict) -> dict:
    """Extract a structured voice profile from the script JSON."""
    anchor = script.get("anchor_character", {})
    voice_block = anchor.get("voice", {})
    description = anchor.get("description", "")

    profile = {
        "gender": voice_block.get("gender", ""),
        "accent": voice_block.get("accent", ""),
        "tone": voice_block.get("tone", ""),
        "character_description": description,
    }

    # Map to ElevenLabs API filter values
    gender_raw = profile["gender"].lower()
    if "female" in gender_raw or "woman" in gender_raw:
        profile["api_gender"] = "female"
    elif "male" in gender_raw or "man" in gender_raw:
        profile["api_gender"] = "male"
    else:
        profile["api_gender"] = ""

    accent_raw = profile["accent"].lower()
    if "american" in accent_raw:
        profile["api_accent"] = "american"
    elif "british" in accent_raw:
        profile["api_accent"] = "british"
    elif "australian" in accent_raw:
        profile["api_accent"] = "australian"
    elif "indian" in accent_raw:
        profile["api_accent"] = "indian"
    else:
        profile["api_accent"] = ""

    # Age inference from character description
    desc_lower = description.lower()
    if "mid-30" in desc_lower or "30s" in desc_lower or "mid-40" in desc_lower or "40s" in desc_lower:
        profile["api_age"] = "middle_aged"
    elif "young" in desc_lower or "20s" in desc_lower or "teen" in desc_lower:
        profile["api_age"] = "young"
    elif "elder" in desc_lower or "60s" in desc_lower or "70s" in desc_lower:
        profile["api_age"] = "old"
    else:
        profile["api_age"] = "middle_aged"

    # Build a natural language summary for Gemini ranking
    parts = []
    if profile["gender"]:
        parts.append(profile["gender"])
    if profile["accent"]:
        parts.append(profile["accent"])
    if profile["tone"]:
        parts.append(f"tone: {profile['tone']}")
    if description:
        parts.append(f"character: {description[:200]}")
    profile["natural_language"] = ". ".join(parts)

    return profile


def search_shared_voices(api_key: str, profile: dict, page_size: int = 30) -> list:
    """Search ElevenLabs shared voice library with structured filters."""
    params = {"page_size": str(page_size)}

    if profile["api_gender"]:
        params["gender"] = profile["api_gender"]
    if profile["api_accent"]:
        params["accent"] = profile["api_accent"]
    if profile["api_age"]:
        params["age"] = profile["api_age"]

    # Use short, broad keywords for search — full tone phrases return too few results
    tone = profile.get("tone", "")
    if tone:
        # Extract just the key adjectives, drop filler words
        skip = {"speaking", "to", "a", "the", "and", "with", "for", "like", "as", "in", "of", "parent-to-parent"}
        words = [w.strip().lower() for w in tone.replace(",", " ").split()]
        keywords = [w for w in words if w not in skip and len(w) > 2]
        params["search"] = " ".join(keywords[:3])  # Max 3 keywords

    # Try with category=professional first for higher quality
    params["category"] = "professional"

    url = "https://api.elevenlabs.io/v1/shared-voices?" + urllib.parse.urlencode(params)
    print(f"Searching voice library: gender={profile['api_gender']}, accent={profile['api_accent']}, "
          f"age={profile['api_age']}, search=\"{params.get('search', '')}\"")

    try:
        result = api_get(url, api_key)
        voices = result.get("voices", [])
        print(f"  Found {len(voices)} professional voices")

        # If too few results, broaden the search progressively
        if len(voices) < 10:
            # Try without category filter
            params.pop("category", None)
            url2 = "https://api.elevenlabs.io/v1/shared-voices?" + urllib.parse.urlencode(params)
            result2 = api_get(url2, api_key)
            extra = result2.get("voices", [])
            seen_ids = {v["voice_id"] for v in voices}
            for v in extra:
                if v["voice_id"] not in seen_ids:
                    voices.append(v)
            print(f"  Expanded to {len(voices)} voices (dropped category filter)")

        if len(voices) < 10:
            # Try without search text — just gender + accent + age
            params.pop("search", None)
            url3 = "https://api.elevenlabs.io/v1/shared-voices?" + urllib.parse.urlencode(params)
            result3 = api_get(url3, api_key)
            extra = result3.get("voices", [])
            seen_ids = {v["voice_id"] for v in voices}
            for v in extra:
                if v["voice_id"] not in seen_ids:
                    voices.append(v)
            print(f"  Expanded to {len(voices)} voices (dropped search text)")

        return voices

    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  Voice library search failed ({e.code}): {error_body}", file=sys.stderr)
        return []


def download_previews(voices: list, preview_dir: Path) -> list:
    """Download preview audio for each voice candidate."""
    preview_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for v in voices:
        preview_url = v.get("preview_url", "")
        if not preview_url:
            continue
        fname = f"{v['voice_id']}.mp3"
        dest = preview_dir / fname
        if not dest.exists():
            try:
                download_file(preview_url, dest)
            except Exception as e:
                print(f"  Warning: failed to download preview for {v.get('name', v['voice_id'])}: {e}")
                continue
        results.append({
            "voice_id": v["voice_id"],
            "name": v.get("name", ""),
            "description": v.get("description", ""),
            "category": v.get("category", ""),
            "labels": v.get("labels", {}),
            "preview_path": str(dest),
            "preview_url": preview_url,
            "cloned_by_count": v.get("cloned_by_count", 0),
            "liked_by_count": v.get("liked_by_count", 0),
            "rate": v.get("rate", 0),
        })
    return results


# ---------------------------------------------------------------------------
# Gemini ranking
# ---------------------------------------------------------------------------

def rank_with_gemini(candidates: list, profile: dict, gemini_key: str, top_n: int = 3) -> list:
    """Use Gemini to rank voice candidates against the character profile."""
    if not candidates:
        return []

    # Build candidate descriptions for Gemini
    candidate_lines = []
    for i, c in enumerate(candidates):
        labels = c.get("labels", {})
        label_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if labels else "no labels"
        desc = c.get("description", "no description")[:200]
        candidate_lines.append(
            f"{i+1}. NAME: {c['name']} | LABELS: {label_str} | "
            f"DESC: {desc} | POPULARITY: {c.get('cloned_by_count', 0)} clones, "
            f"{c.get('liked_by_count', 0)} likes"
        )

    candidates_text = "\n".join(candidate_lines)

    prompt = f"""You are a voice casting director. Pick the {top_n} best voices for this character.

CHARACTER PROFILE:
- Gender: {profile.get('gender', 'unspecified')}
- Accent: {profile.get('accent', 'unspecified')}
- Tone: {profile.get('tone', 'unspecified')}
- Character: {profile.get('character_description', 'unspecified')[:300]}

VOICE CANDIDATES:
{candidates_text}

SELECTION CRITERIA (in priority order):
1. Voice must sound STRONG, CONFIDENT, and AUTHORITATIVE — not feeble, breathy, or whisper-like
2. Accent match (American English)
3. Tone match (calm but direct, parent-to-parent — think news anchor or confident podcast host)
4. Professional quality / popularity as a quality signal
5. Age-appropriate for the described character

IMPORTANT: Reject any voice described as "soft", "gentle", "whisper", "ASMR", "soothing", or "breathy" — these produce feeble output. Prefer voices described as "clear", "confident", "strong", "authoritative", "professional", "bold", or "engaging".

Return ONLY a JSON array of the top {top_n} candidate numbers (1-indexed), best first. Example: [3, 7, 1]
No explanation, just the JSON array."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200,
                             "thinkingConfig": {"thinkingBudget": 0}}
    }

    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())

        # Extract text from response — may have multiple parts (thinking + answer)
        parts = result["candidates"][0]["content"]["parts"]
        text = ""
        for part in parts:
            if "text" in part:
                text = part["text"].strip()  # Last text part is the answer

        # Extract JSON array — handle markdown code blocks or raw JSON
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        # Find the array in the text
        import re
        match = re.search(r'\[[\d,\s]+\]', text)
        if match:
            text = match.group(0)
        rankings = json.loads(text)

        ranked = []
        for idx in rankings:
            if 1 <= idx <= len(candidates):
                ranked.append(candidates[idx - 1])
        return ranked[:top_n]

    except Exception as e:
        print(f"  Gemini ranking failed: {e}", file=sys.stderr)
        # Fallback: sort by popularity
        print("  Falling back to popularity-based ranking")
        sorted_candidates = sorted(candidates, key=lambda c: c.get("cloned_by_count", 0), reverse=True)
        return sorted_candidates[:top_n]


# ---------------------------------------------------------------------------
# Pass 2: Generate custom voice (fallback)
# ---------------------------------------------------------------------------

def design_voice(api_key: str, profile: dict, sample_text: str) -> dict | None:
    """Generate a custom AI voice via ElevenLabs text-to-voice/design."""
    description = (
        f"A {profile.get('gender', 'female')} voice with a {profile.get('accent', 'American')} accent. "
        f"Tone: {profile.get('tone', 'confident and direct')}. "
        f"The voice should be strong, clear, and authoritative — NOT soft, breathy, or whispery. "
        f"Think confident podcast host or news anchor. Mid-30s, professional, engaging."
    )

    # Trim sample text to reasonable length
    if len(sample_text) > 500:
        sample_text = sample_text[:500]

    url = "https://api.elevenlabs.io/v1/text-to-voice/create-previews"
    payload = {
        "voice_description": description,
        "text": sample_text,
    }

    print(f"\nDesigning custom voice...")
    print(f"  Description: {description}")

    try:
        result = api_post(url, api_key, payload)
        previews = result.get("previews", [])
        if not previews:
            print("  No previews returned", file=sys.stderr)
            return None

        print(f"  Got {len(previews)} preview(s)")
        return {
            "previews": previews,
            "description": description,
        }

    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  Voice design failed ({e.code}): {error_body}", file=sys.stderr)
        return None


def save_designed_voice(api_key: str, generated_voice_id: str, name: str) -> str | None:
    """Save a designed voice preview to the account, returns usable voice_id."""
    url = "https://api.elevenlabs.io/v1/text-to-voice/create-voice-from-preview"
    payload = {
        "voice_name": name,
        "voice_description": "Auto-selected voice for reel factory pipeline",
        "generated_voice_id": generated_voice_id,
    }

    try:
        result = api_post(url, api_key, payload)
        voice_id = result.get("voice_id", "")
        if voice_id:
            print(f"  Saved designed voice: {voice_id} as \"{name}\"")
            return voice_id
        return None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  Save voice failed ({e.code}): {error_body}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Add shared library voice to account
# ---------------------------------------------------------------------------

def add_library_voice(api_key: str, voice_id: str, public_user_id: str, name: str) -> str | None:
    """Add a shared library voice to the user's account."""
    url = f"https://api.elevenlabs.io/v1/voices/add/{public_user_id}/{voice_id}"
    payload = {"new_name": name}

    try:
        result = api_post(url, api_key, payload)
        added_id = result.get("voice_id", voice_id)
        print(f"  Added library voice to account: {added_id}")
        return added_id
    except urllib.error.HTTPError as e:
        # 422 often means already added — voice_id is directly usable
        if e.code == 422:
            print(f"  Voice {voice_id} may already be in account, using directly")
            return voice_id
        error_body = e.read().decode()
        print(f"  Add voice failed ({e.code}): {error_body}", file=sys.stderr)
        return voice_id  # Try using it anyway


# ---------------------------------------------------------------------------
# Update script JSON
# ---------------------------------------------------------------------------

def update_script(script_path: Path, voice_id: str):
    """Update the script JSON with the new voice ID."""
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    # Update anchor_character.voice.elevenlabs_voice_id
    if "anchor_character" in script and "voice" in script["anchor_character"]:
        script["anchor_character"]["voice"]["elevenlabs_voice_id"] = voice_id

    # Update audio.voice_over.voice_id
    if "audio" in script and "voice_over" in script["audio"]:
        script["audio"]["voice_over"]["voice_id"] = voice_id

    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  Updated script: {script_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Auto-select best ElevenLabs voice for script")
    parser.add_argument("script", help="Path to script JSON file")
    parser.add_argument("--top", type=int, default=3, help="Number of top candidates to show (default: 3)")
    parser.add_argument("--fallback-only", action="store_true", help="Skip library search, go straight to voice design")
    parser.add_argument("--auto", action="store_true", help="Automatically select #1 ranked voice without prompting")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    el_key = load_env("ELEVENLABS_API_KEY")
    gemini_key = load_env("GEMINI_API_KEY")

    # Build voice profile from script
    profile = build_voice_profile(script)
    print(f"\n{'='*60}")
    print("VOICE PROFILE (from script)")
    print(f"{'='*60}")
    print(f"  Gender:  {profile['gender']}")
    print(f"  Accent:  {profile['accent']}")
    print(f"  Tone:    {profile['tone']}")
    print(f"  Age:     {profile['api_age']}")
    print(f"  Summary: {profile['natural_language'][:200]}")

    preview_dir = script_path.parent / "voice_previews"
    selected_voice_id = None

    # Get sample text for voice preview / design
    full_text = script.get("audio", {}).get("voice_over", {}).get("full_script", "")
    sample_text = full_text[:300] if full_text else "Your child spent three hours on a screen today. That's one hour more than doctors recommend."

    # -----------------------------------------------------------------------
    # Pass 1: Library search
    # -----------------------------------------------------------------------
    if not args.fallback_only:
        print(f"\n{'='*60}")
        print("PASS 1: Searching ElevenLabs voice library")
        print(f"{'='*60}")

        voices = search_shared_voices(el_key, profile, page_size=30)

        if voices:
            # Download previews
            print(f"\n  Downloading previews...")
            candidates = download_previews(voices, preview_dir)
            print(f"  Downloaded {len(candidates)} previews to {preview_dir}/")

            if candidates:
                # Rank with Gemini
                print(f"\n  Ranking candidates with Gemini...")
                ranked = rank_with_gemini(candidates, profile, gemini_key, top_n=args.top)

                if ranked:
                    print(f"\n{'='*60}")
                    print(f"TOP {len(ranked)} VOICE CANDIDATES")
                    print(f"{'='*60}")
                    for i, c in enumerate(ranked):
                        labels = c.get("labels", {})
                        label_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if labels else "-"
                        print(f"\n  #{i+1}: {c['name']}")
                        print(f"      ID:          {c['voice_id']}")
                        print(f"      Labels:      {label_str}")
                        print(f"      Description: {c.get('description', '-')[:150]}")
                        print(f"      Popularity:  {c.get('cloned_by_count', 0)} clones, {c.get('liked_by_count', 0)} likes")
                        print(f"      Preview:     {c['preview_path']}")

                    if args.auto:
                        choice = 1
                    else:
                        print(f"\n  Enter choice (1-{len(ranked)}), 'f' for fallback voice design, or 'q' to quit:")
                        try:
                            raw = input("  > ").strip().lower()
                        except (EOFError, KeyboardInterrupt):
                            print("\n  Aborted.")
                            sys.exit(0)

                        if raw == "q":
                            print("  Aborted.")
                            sys.exit(0)
                        elif raw == "f":
                            choice = None  # Will trigger fallback
                        else:
                            try:
                                choice = int(raw)
                                if choice < 1 or choice > len(ranked):
                                    print(f"  Invalid choice, using #1")
                                    choice = 1
                            except ValueError:
                                print(f"  Invalid input, using #1")
                                choice = 1

                    if choice is not None:
                        selected = ranked[choice - 1]
                        selected_voice_id = selected["voice_id"]
                        print(f"\n  Selected: {selected['name']} ({selected_voice_id})")

    # -----------------------------------------------------------------------
    # Pass 2: Design custom voice (fallback)
    # -----------------------------------------------------------------------
    if selected_voice_id is None:
        print(f"\n{'='*60}")
        print("PASS 2: Designing custom AI voice")
        print(f"{'='*60}")

        result = design_voice(el_key, profile, sample_text)
        if result and result["previews"]:
            previews = result["previews"]
            preview_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n  Generated {len(previews)} voice preview(s):")
            for i, p in enumerate(previews):
                gen_id = p.get("generated_voice_id", "")
                # Save preview audio
                audio_b64 = p.get("audio_base64", "")
                if audio_b64:
                    preview_path = preview_dir / f"designed_{i+1}.mp3"
                    with open(preview_path, "wb") as f:
                        f.write(base64.b64decode(audio_b64))
                    print(f"  #{i+1}: {preview_path} (generated_id: {gen_id[:20]}...)")

            # Pick first preview (or let user choose)
            if args.auto:
                pick = 0
            else:
                print(f"\n  Enter choice (1-{len(previews)}) or 'q' to quit:")
                try:
                    raw = input("  > ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n  Aborted.")
                    sys.exit(0)
                if raw.lower() == "q":
                    sys.exit(0)
                try:
                    pick = int(raw) - 1
                except ValueError:
                    pick = 0

            chosen = previews[pick]
            gen_id = chosen.get("generated_voice_id", "")

            # Save the designed voice to account
            voice_name = f"ReelFactory_{profile['api_gender']}_{profile['api_accent']}_{int(time.time())}"
            selected_voice_id = save_designed_voice(el_key, gen_id, voice_name)

    # -----------------------------------------------------------------------
    # Apply selection
    # -----------------------------------------------------------------------
    if selected_voice_id:
        print(f"\n{'='*60}")
        print("APPLYING VOICE SELECTION")
        print(f"{'='*60}")

        # Update .env
        update_env("ELEVENLABS_VOICE_ID", selected_voice_id)
        print(f"  Updated .env: ELEVENLABS_VOICE_ID={selected_voice_id}")

        # Update script JSON
        update_script(script_path, selected_voice_id)

        print(f"\n  Done! New voice ID: {selected_voice_id}")
        print(f"  Preview audio saved in: {preview_dir}/")
        print(f"\n  Next step: regenerate voiceover with:")
        print(f"    py execution/generate_voiceover.py {script_path}")
    else:
        print("\n  No voice selected. No changes made.")
        sys.exit(1)


if __name__ == "__main__":
    main()
