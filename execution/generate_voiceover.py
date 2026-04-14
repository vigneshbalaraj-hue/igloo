"""
generate_voiceover.py — Generate voice-over audio with word-level timestamps via ElevenLabs API.

Voice prompt bank wired in (session 20):
  - TTS voice_settings come from each scene's PHASE field (HOOK / AGITATION / REFRAME / CTA),
    not its `voice_emotion` field. Phase profiles from voice_prompt_bank.md Part 2.
  - Narration text is annotated per voice_prompt_bank.md Part 3 before the TTS call:
    universal cleanup of banned chars + per-phase beat/pacing rules.
  - Voice is ALWAYS generated at 1.0x. The 1.2x reel pacing is applied at the end of
    assemble_video.py via ffmpeg setpts+atempo (pitch-preserving), not via the
    ElevenLabs `speed` parameter (which caps at 1.2x and degrades quality).

Supports two modes:
  - Scene-by-scene (default): generates each scene separately with phase-aware settings.
  - Single-pass (--single): generates the full script in one API call (legacy, monotone).

Usage:
    py execution/generate_voiceover.py .tmp/.../script.json
    py execution/generate_voiceover.py .tmp/.../script.json --gap 250

Output:
    {script_dir}/voiceover.mp3               — final concatenated audio (1.0x)
    {script_dir}/voiceover_timestamps.json   — character-level timestamps (merged)
    {script_dir}/voiceover_scenes/           — per-scene audio files
    {script_dir}/voiceover_annotated.json    — per-scene phase + annotated text log
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Local — shared with generate_script.py for voice calibration
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompt_bank as pb  # noqa: E402


# ---------------------------------------------------------------------------
# Phase TTS profiles — voice_prompt_bank.md Part 2
# ---------------------------------------------------------------------------

PHASE_TTS = {
    "HOOK": {
        "stability": 0.35,
        "similarity_boost": 0.75,
        "style": 0.70,
        "use_speaker_boost": True,
    },
    "AGITATION": {
        "stability": 0.40,
        "similarity_boost": 0.75,
        "style": 0.65,
        "use_speaker_boost": True,
    },
    "REFRAME": {
        "stability": 0.30,
        "similarity_boost": 0.75,
        "style": 0.75,
        "use_speaker_boost": True,
    },
    "CTA": {
        "stability": 0.50,
        "similarity_boost": 0.75,
        "style": 0.55,
        "use_speaker_boost": True,
    },
}

DEFAULT_PHASE = "AGITATION"  # fallback for scenes without a `purpose` field


# ---------------------------------------------------------------------------
# Annotation rules — voice_prompt_bank.md Part 3
# ---------------------------------------------------------------------------

BANNED_CHARS = ["!", "*", "(", ")", ";"]


def universal_clean(text: str) -> str:
    """Strip Part 3 banned chars and collapse double spaces."""
    for ch in BANNED_CHARS:
        text = text.replace(ch, "")
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def annotate_hook(text: str) -> str:
    """Add `...` after first clause if not already present.

    Heuristic: if text contains `?`, leave as-is (rhetorical questions already
    create the beat). Otherwise insert `...` after the first comma if it sits
    in the first 50 chars; else after the first 8 words.
    """
    if "..." in text or "?" in text:
        return text
    first_comma = text.find(",")
    if 0 < first_comma < 50:
        return text[:first_comma] + "..." + text[first_comma + 1:]
    words = text.split()
    if len(words) > 8:
        return " ".join(words[:8]) + "... " + " ".join(words[8:])
    return text


def annotate_agitation(text: str) -> str:
    """No-op. Script-bank-generated agitation already uses commas well."""
    return text


def annotate_reframe(text: str) -> str:
    """Force beats: turn clause-joining commas into periods on the payload section."""
    return re.sub(
        r",\s+(but|and|not|yet|so)\b",
        lambda m: ". " + m.group(1).capitalize(),
        text,
        flags=re.IGNORECASE,
    )


def annotate_cta(text: str) -> str:
    """Strip ellipses; CTA must be definitive."""
    return text.replace("...", " ").replace("…", " ")


ANNOTATORS = {
    "HOOK": annotate_hook,
    "AGITATION": annotate_agitation,
    "REFRAME": annotate_reframe,
    "CTA": annotate_cta,
}


def annotate(text: str, phase: str) -> str:
    cleaned = universal_clean(text)
    return ANNOTATORS.get(phase, annotate_agitation)(cleaned)


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


def find_ffmpeg() -> str:
    for candidate in ["ffmpeg", r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"]:
        try:
            subprocess.run([candidate, "-version"], capture_output=True, check=True, timeout=10)
            return candidate
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    print("ERROR: ffmpeg not found", file=sys.stderr)
    sys.exit(1)


def find_ffprobe() -> str:
    for candidate in ["ffprobe", r"C:\ffmpeg\bin\ffprobe.exe", r"C:\ProgramData\chocolatey\bin\ffprobe.exe"]:
        try:
            subprocess.run([candidate, "-version"], capture_output=True, check=True, timeout=10)
            return candidate
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    print("ERROR: ffprobe not found", file=sys.stderr)
    sys.exit(1)


def get_audio_duration_s(filepath: str) -> float:
    ffprobe = find_ffprobe()
    result = subprocess.run(
        [ffprobe, "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", filepath],
        capture_output=True, text=True, timeout=60,
    )
    return float(result.stdout.strip())


# ---------------------------------------------------------------------------
# ElevenLabs TTS — single scene
# ---------------------------------------------------------------------------

def generate_scene_audio(text: str, voice_id: str, api_key: str, settings: dict,
                         output_path: Path) -> dict:
    """Generate TTS for a single text segment at 1.0x. Returns alignment dict.

    `settings` is a phase TTS profile (e.g. PHASE_TTS["HOOK"]). Speed is NOT sent
    to the API — final reel pacing is handled by assemble_video.py via ffmpeg
    setpts+atempo. The ElevenLabs speed param degrades voice quality and caps at
    1.2x, so we generate clean 1.0x audio and time-stretch downstream.
    """
    import urllib.request
    import urllib.error

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"

    settings = dict(settings)  # don't mutate caller's dict
    settings.setdefault("use_speaker_boost", True)

    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": settings,
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("xi-api-key", api_key)
    req.add_header("Content-Type", "application/json")

    from http_retry import retry_with_backoff, RetryExhaustedError

    def _do_call():
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())

    try:
        result = retry_with_backoff(_do_call, label="elevenlabs-tts")
    except urllib.error.HTTPError as e:
        # Non-retryable (4xx) — bubble typed error for the UI.
        error_body = ""
        try:
            error_body = e.read().decode()
        except Exception:
            pass
        print(f"  ERROR {e.code}: {error_body}", file=sys.stderr)
        print(f"ERROR_CODE: TTS_FAILED", file=sys.stderr)
        sys.exit(1)
    except RetryExhaustedError as e:
        print(f"  ERROR: ElevenLabs TTS failed after retries: {e}", file=sys.stderr)
        print(f"ERROR_CODE: TTS_FAILED", file=sys.stderr)
        sys.exit(1)

    audio_b64 = result.get("audio_base64", "")
    if not audio_b64:
        print(f"  ERROR: No audio returned for: {text[:50]}...", file=sys.stderr)
        print(f"ERROR_CODE: TTS_FAILED", file=sys.stderr)
        sys.exit(1)

    audio_bytes = base64.b64decode(audio_b64)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    return result.get("alignment", {})


# ---------------------------------------------------------------------------
# Extract scenes from script JSON
# ---------------------------------------------------------------------------

def _normalize_phase(raw: str) -> str:
    """Coerce a scene's `purpose` field to a known phase, defaulting if absent/unknown."""
    if not raw:
        return DEFAULT_PHASE
    p = raw.strip().upper()
    return p if p in PHASE_TTS else DEFAULT_PHASE


def extract_narration_segments(script: dict) -> list:
    """Extract ordered narration segments from script, handling sub-clips.

    Each segment carries its phase (HOOK/AGITATION/REFRAME/CTA), derived from
    the scene's `purpose` field. Sub-clips inherit the parent scene's phase.
    """
    segments = []
    for scene in script.get("scenes", []):
        vid = scene.get("video_generation", {})
        phase = _normalize_phase(scene.get("purpose", ""))

        # Check for sub-clips (e.g., scene 4 with clips 4a, 4b)
        if "clips" in vid:
            for clip in vid["clips"]:
                text = clip.get("narration_text", "")
                clip_id = clip.get("clip_id", "")
                clip_phase = _normalize_phase(clip.get("purpose", "")) if clip.get("purpose") else phase
                if text.strip():
                    segments.append({
                        "id": f"scene{scene['scene_id']}_{clip_id}",
                        "text": text.strip(),
                        "phase": clip_phase,
                    })
        else:
            text = scene.get("narration_text", "")
            if text.strip():
                segments.append({
                    "id": f"scene{scene['scene_id']}",
                    "text": text.strip(),
                    "phase": phase,
                })
    return segments


# ---------------------------------------------------------------------------
# Scene-by-scene generation + concatenation
# ---------------------------------------------------------------------------

def generate_scene_by_scene(script: dict, voice_id: str, api_key: str,
                            output_dir: Path, gap_ms: int):
    """Generate each scene separately at 1.0x, concatenate with ffmpeg."""
    segments = extract_narration_segments(script)
    if not segments:
        print("ERROR: No narration segments found", file=sys.stderr)
        sys.exit(1)

    scenes_dir = output_dir / "voiceover_scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg = find_ffmpeg()

    # Generate silence file for inter-scene gaps
    gap_path = scenes_dir / "gap.mp3"
    if gap_ms > 0:
        subprocess.run([
            ffmpeg, "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
            "-t", f"{gap_ms / 1000:.3f}", "-q:a", "9", str(gap_path)
        ], capture_output=True, check=True, timeout=60)

    # Generate each segment
    scene_files = []
    all_alignments = []
    annotated_log = []
    cumulative_offset = 0.0

    print(f"\nGenerating {len(segments)} scene segments at 1.0x (voice: {voice_id[:12]}...)")
    print(f"{'='*60}")

    for i, seg in enumerate(segments):
        scene_path = scenes_dir / f"{seg['id']}.mp3"
        phase = seg["phase"]
        settings = PHASE_TTS[phase]
        original_text = seg["text"]
        annotated_text = annotate(original_text, phase)

        print(f"  [{i+1}/{len(segments)}] {seg['id']} phase={phase}")
        print(f"           stab={settings['stability']} style={settings['style']}")
        print(f"           text: \"{annotated_text[:60]}...\"")
        if annotated_text != original_text:
            print(f"           (annotated from original)")

        alignment = generate_scene_audio(
            text=annotated_text,
            voice_id=voice_id,
            api_key=api_key,
            settings=settings,
            output_path=scene_path,
        )

        # Get actual duration via ffprobe
        duration = get_audio_duration_s(str(scene_path))
        print(f"           duration={duration:.2f}s")

        annotated_log.append({
            "id": seg["id"],
            "phase": phase,
            "tts_settings": settings,
            "original_text": original_text,
            "annotated_text": annotated_text,
            "duration_s": round(duration, 3),
        })

        # Offset alignment timestamps
        chars = alignment.get("characters", [])
        starts = alignment.get("character_start_times_seconds", [])
        ends = alignment.get("character_end_times_seconds", [])

        offset_starts = [t + cumulative_offset for t in starts]
        offset_ends = [t + cumulative_offset for t in ends]

        all_alignments.append({
            "characters": chars,
            "character_start_times_seconds": offset_starts,
            "character_end_times_seconds": offset_ends,
        })

        scene_files.append(str(scene_path))
        cumulative_offset += duration

        # Add space separator between scenes so extract_word_timestamps can split at boundaries
        if i < len(segments) - 1:
            space_time = cumulative_offset
            all_alignments.append({
                "characters": [" "],
                "character_start_times_seconds": [space_time],
                "character_end_times_seconds": [space_time],
            })

        # Add gap after each segment (except the last)
        if gap_ms > 0 and i < len(segments) - 1:
            scene_files.append(str(gap_path))
            cumulative_offset += gap_ms / 1000.0

    # Merge all alignments and write timestamps FIRST (before concat, so they survive crashes)
    merged = {"characters": [], "character_start_times_seconds": [], "character_end_times_seconds": []}
    for a in all_alignments:
        merged["characters"].extend(a["characters"])
        merged["character_start_times_seconds"].extend(a["character_start_times_seconds"])
        merged["character_end_times_seconds"].extend(a["character_end_times_seconds"])

    ts_path = output_dir / "voiceover_timestamps.json"
    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    # Persist annotation log for debugging/audit
    log_path = output_dir / "voiceover_annotated.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(annotated_log, f, indent=2, ensure_ascii=False)

    # Concatenate with ffmpeg
    print(f"\nConcatenating {len(scene_files)} files...")
    concat_list = scenes_dir / "concat.txt"
    with open(concat_list, "w") as f:
        for sf in scene_files:
            # Use absolute paths with forward slashes for ffmpeg compatibility on Windows
            abs_path = str(Path(sf).resolve()).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")

    audio_path = output_dir / "voiceover.mp3"
    subprocess.run([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c:a", "libmp3lame", "-q:a", "2", str(audio_path)
    ], capture_output=True, check=True, timeout=600)

    total_duration = get_audio_duration_s(str(audio_path))
    file_size = audio_path.stat().st_size / 1024

    print(f"\n{'='*60}")
    print(f"Audio saved: {audio_path} ({file_size:.1f} KB)")
    print(f"Timestamps saved: {ts_path}")
    print(f"Annotation log: {log_path}")
    print(f"Audio duration: ~{total_duration:.1f}s")
    print(f"Scene audio: {scenes_dir}/")

    # Auto-update voice calibration: every successful run feeds a fresh
    # words-per-second sample back into data/voice_calibration.json. After
    # ~3 samples the rolling mean converges, so adding a new voice is
    # zero-config — first run uses DEFAULT_WPS, subsequent runs self-correct.
    total_words = sum(
        len(entry["original_text"].split()) for entry in annotated_log
    )
    if total_words > 0 and total_duration > 0:
        sample_wps = total_words / total_duration
        new_mean = pb.update_voice_wps(voice_id, sample_wps)
        print(
            f"  [calibration] sample={sample_wps:.2f} wps "
            f"(words={total_words}, dur={total_duration:.1f}s) "
            f"→ rolling mean={new_mean:.3f}"
        )

    # Duration sanity check vs the script's target duration. The band is
    # tight now that calibration is wired — outside [0.92, 1.08] means the
    # script genuinely overshot/undershot, not "voice runs slow."
    target = (
        script.get("target_duration_seconds")
        or script.get("duration_seconds")
        or (script.get("_meta") or {}).get("duration_target_s")
    )
    if target:
        ratio = total_duration / float(target)
        if ratio > 1.08 or ratio < 0.92:
            print(
                f"\n  WARNING: actual duration {total_duration:.1f}s vs target {target}s "
                f"(ratio {ratio:.2f}). Outside the 0.92-1.08 calibrated band — "
                f"the script word count is wrong for this voice.",
                file=sys.stderr,
            )

    return audio_path, ts_path


# ---------------------------------------------------------------------------
# Single-pass generation (legacy)
# ---------------------------------------------------------------------------

def generate_single_pass(script: dict, voice_id: str, api_key: str,
                         output_dir: Path):
    """Generate full script in one API call (legacy mode)."""
    full_text = script.get("audio", {}).get("voice_over", {}).get("full_script", "")
    if not full_text:
        print("ERROR: No full_script found in script JSON", file=sys.stderr)
        sys.exit(1)

    print(f"Generating voice-over single-pass ({len(full_text)} chars)...")

    audio_path = output_dir / "voiceover.mp3"
    alignment = generate_scene_audio(
        text=full_text,
        voice_id=voice_id,
        api_key=api_key,
        settings=PHASE_TTS[DEFAULT_PHASE],
        output_path=audio_path,
    )

    ts_path = output_dir / "voiceover_timestamps.json"
    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(alignment, f, indent=2, ensure_ascii=False)

    file_size = audio_path.stat().st_size / 1024
    ends = alignment.get("character_end_times_seconds", [])
    total_duration = max(ends) if ends else 0

    print(f"Audio saved: {audio_path} ({file_size:.1f} KB)")
    print(f"Timestamps saved: {ts_path}")
    print(f"Audio duration: ~{total_duration:.1f}s")

    return audio_path, ts_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate voice-over via ElevenLabs")
    parser.add_argument("script", help="Path to script JSON file")
    parser.add_argument("--single", action="store_true", help="Single-pass mode (no per-scene emotions)")
    parser.add_argument("--gap", type=int, default=200, help="Inter-scene silence in ms (default: 200)")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    api_key = load_env("ELEVENLABS_API_KEY")
    # Prefer voice_id baked into the script (set by wizard or select_voice.py)
    # over env var. The env var is process-wide on Fly and leaks across runs
    # when a prior run wrote it via select_voice.update_env() — that caused the
    # s48 migraine reel to ship with a stale male voice over a female anchor.
    script_voice_id = (script.get("anchor_character", {})
                             .get("voice", {}).get("elevenlabs_voice_id")
                       or script.get("audio", {})
                                .get("voice_over", {}).get("voice_id"))
    voice_id = script_voice_id or load_env("ELEVENLABS_VOICE_ID")
    if not voice_id:
        print("ERROR: no voice_id in script and ELEVENLABS_VOICE_ID not set", file=sys.stderr)
        sys.exit(1)
    output_dir = script_path.parent

    if args.single:
        generate_single_pass(script, voice_id, api_key, output_dir)
    else:
        generate_scene_by_scene(script, voice_id, api_key, output_dir, args.gap)


if __name__ == "__main__":
    main()
