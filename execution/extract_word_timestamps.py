"""
extract_word_timestamps.py — Convert ElevenLabs character-level timestamps to word-level,
then update the script JSON with actual narration_start/narration_end/audio_slice values.

This is the single source of truth for all timing in the pipeline.
After running this, the script JSON's timestamps reflect the real voiceover audio.

Usage:
    py execution/extract_word_timestamps.py .tmp/screen_addiction_children/voiceover_timestamps.json

    # Also update script JSON with actual timestamps:
    py execution/extract_word_timestamps.py .tmp/screen_addiction_children/voiceover_timestamps.json --update-script .tmp/screen_addiction_children/screen_addiction_36s_script.json
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path


# Fallback WPS when interpolating a missed scene's duration (default voice cadence).
# Matches the default used in prompt_bank's per-voice calibration table.
WPS_ESTIMATE = 2.5

# Max scenes allowed to fall back to interpolation before we hard-fail the run.
# Rationale: single miss ≈ imperceptible caption drift; 2 scenes compounds but
# stays watchable; 3+ drifts visibly on the back half.
MAX_INTERPOLATED_SCENES = 2


class AlignmentQualityError(RuntimeError):
    """Too many scenes required interpolation to align; output would drift."""


class AlignmentHardError(RuntimeError):
    """Whisper produced no usable word timestamps; cannot align at all."""


def extract_words(data):
    chars = data["characters"]
    starts = data["character_start_times_seconds"]
    ends = data["character_end_times_seconds"]

    words = []
    current_word = ""
    word_start = None

    for i, ch in enumerate(chars):
        if ch == " ":
            if current_word:
                words.append({
                    "word": current_word,
                    "start": round(word_start, 3),
                    "end": round(ends[i - 1], 3)
                })
                current_word = ""
                word_start = None
        else:
            if word_start is None:
                word_start = starts[i]
            current_word += ch

    # Last word
    if current_word:
        words.append({
            "word": current_word,
            "start": round(word_start, 3),
            "end": round(ends[len(chars) - 1], 3)
        })

    return words


def normalize_word(w: str) -> str:
    """Strip punctuation and lowercase for matching."""
    return re.sub(r'[^a-z0-9]', '', w.lower())


def _match_first_word(words, target_norm, start_idx, exact_window=10, fuzzy_window=30):
    """Find the starting word index for a scene.

    Returns (match_idx, mode) where mode is 'exact', 'fuzzy', or None (no match).
    - Pass 1: exact normalized-equal scan within exact_window.
    - Pass 2: difflib fuzzy match (ratio ≥ 0.8) within fuzzy_window.
    """
    total = len(words)
    # Pass 1: exact
    for i in range(start_idx, min(start_idx + exact_window, total)):
        if normalize_word(words[i]["word"]) == target_norm:
            return i, "exact"
    # Pass 2: fuzzy
    best_i, best_ratio = None, 0.0
    for i in range(start_idx, min(start_idx + fuzzy_window, total)):
        candidate = normalize_word(words[i]["word"])
        if not candidate:
            continue
        ratio = difflib.SequenceMatcher(None, target_norm, candidate).ratio()
        if ratio >= 0.8 and ratio > best_ratio:
            best_i, best_ratio = i, ratio
    if best_i is not None:
        return best_i, "fuzzy"
    return None, None


def update_script_timestamps(script_path: Path, words: list):
    """Match voiceover words to scenes and update narration_start/end + audio_slice.

    Three-pass alignment per scene: exact → fuzzy → interpolation. If more than
    MAX_INTERPOLATED_SCENES scenes require interpolation, raises
    AlignmentQualityError (output would visibly drift). If Whisper produced zero
    words, raises AlignmentHardError immediately.
    """
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    total_words = len(words)
    if total_words == 0:
        raise AlignmentHardError(
            "Whisper returned zero word timestamps — cannot align any scene"
        )

    word_idx = 0
    interpolated_scenes = []  # scene_ids that fell back to interpolation
    last_end_seconds = 0.0    # for interpolation fallback

    for scene in script["scenes"]:
        narration = scene.get("narration_text", "")
        if not narration:
            continue

        scene_words = narration.split()
        if not scene_words:
            continue

        first_norm = normalize_word(scene_words[0])
        last_norm = normalize_word(scene_words[-1])

        match_start, mode = _match_first_word(words, first_norm, word_idx)

        if match_start is None:
            # Pass 3: interpolate from previous scene's end using word-count estimate.
            interpolated_scenes.append(scene["scene_id"])
            if len(interpolated_scenes) > MAX_INTERPOLATED_SCENES:
                raise AlignmentQualityError(
                    f"{len(interpolated_scenes)} scenes required interpolation "
                    f"(max {MAX_INTERPOLATED_SCENES}); caption sync would drift. "
                    f"Interpolated scenes: {interpolated_scenes}"
                )
            narration_start = round(last_end_seconds, 3)
            estimated_duration = round(len(scene_words) / WPS_ESTIMATE, 3)
            narration_end = round(narration_start + estimated_duration, 3)
            scene_duration = estimated_duration
            print(f"  Scene {scene['scene_id']}: INTERPOLATED "
                  f"{narration_start:.3f}-{narration_end:.3f} ({scene_duration:.2f}s) "
                  f"— first word '{scene_words[0]}' not in voiceover words near idx {word_idx}")
        else:
            # Find ending position
            match_end = match_start + len(scene_words) - 1
            if match_end >= total_words:
                match_end = total_words - 1
            if normalize_word(words[match_end]["word"]) != last_norm:
                for i in range(match_start + len(scene_words) - 2,
                               min(match_start + len(scene_words) + 3, total_words)):
                    if normalize_word(words[i]["word"]) == last_norm:
                        match_end = i
                        break

            narration_start = round(words[match_start]["start"], 3)
            narration_end = round(words[match_end]["end"], 3)
            scene_duration = round(narration_end - narration_start, 3)
            word_idx = match_end + 1

            tag = f" [{mode}]" if mode == "fuzzy" else ""
            print(f"  Scene {scene['scene_id']}:{tag} "
                  f"{narration_start:.3f}-{narration_end:.3f} ({scene_duration:.2f}s)")

        # Update scene fields
        scene["narration_start"] = narration_start
        scene["narration_end"] = narration_end
        scene["scene_duration"] = scene_duration
        last_end_seconds = narration_end

        # Update video_generation fields based on scene type
        vg = scene.get("video_generation", {})
        if vg.get("method") == "image-to-video":
            vg["kling_duration"] = 10 if scene_duration > 5.0 else 5
        if vg.get("method") == "lip-sync":
            vg["audio_slice"] = [narration_start, narration_end]
            vg["kling_duration"] = f"driven by audio ({scene_duration}s)"

    if interpolated_scenes:
        print(f"  NOTE: {len(interpolated_scenes)} scene(s) used interpolation "
              f"(<={MAX_INTERPOLATED_SCENES} allowed): {interpolated_scenes}")

    # Update top-level actual_duration from last scene's end
    all_ends = [s.get("narration_end", 0) for s in script["scenes"]]
    if all_ends:
        actual_duration = round(max(all_ends), 3)
        script["actual_duration_seconds"] = actual_duration
        if "audio" in script and "voice_over" in script["audio"]:
            script["audio"]["voice_over"]["total_duration_seconds"] = actual_duration
        print(f"\n  actual_duration_seconds: {actual_duration}")

    # Also update clip-level narration_start/narration_end for scenes with sub-clips
    # (e.g., scene 4 with clips 4a/4b) — these need proportional redistribution
    for scene in script["scenes"]:
        vg = scene.get("video_generation", {})
        if "clips" in vg:
            clips = vg["clips"]
            scene_start = scene.get("narration_start", 0.0)

            # Match each sub-clip's narration text to word timestamps
            clip_word_idx = 0
            # Find starting word index for this scene
            for wi in range(total_words):
                if abs(words[wi]["start"] - scene_start) < 0.05:
                    clip_word_idx = wi
                    break

            for clip in clips:
                clip_narration = clip.get("narration_text", "")
                if not clip_narration:
                    continue
                clip_words_list = clip_narration.split()
                if not clip_words_list:
                    continue

                first_norm = normalize_word(clip_words_list[0])
                # Find start
                for i in range(clip_word_idx, min(clip_word_idx + 10, total_words)):
                    if normalize_word(words[i]["word"]) == first_norm:
                        clip_word_idx = i
                        break

                clip_end_idx = clip_word_idx + len(clip_words_list) - 1
                if clip_end_idx >= total_words:
                    clip_end_idx = total_words - 1

                clip["narration_start"] = round(words[clip_word_idx]["start"], 3)
                clip["narration_end"] = round(words[clip_end_idx]["end"], 3)
                clip["clip_duration_in_video"] = round(clip["narration_end"] - clip["narration_start"], 3)
                clip["trim_to"] = clip["clip_duration_in_video"]

                clip_word_idx = clip_end_idx + 1

    # Write updated script
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\n  Script updated: {script_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract word timestamps and optionally update script JSON")
    parser.add_argument("timestamps", help="Path to voiceover_timestamps.json")
    parser.add_argument("--update-script", help="Path to script JSON to update with actual timestamps")
    args = parser.parse_args()

    path = Path(args.timestamps)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    words = extract_words(data)

    # Print with sentence grouping
    sentence = []
    for w in words:
        sentence.append(w)
        if w["word"].endswith((".")) :
            text = " ".join(x["word"] for x in sentence)
            start = sentence[0]["start"]
            end = sentence[-1]["end"]
            print(f"[{start:6.2f} - {end:6.2f}] ({end - start:4.1f}s)  {text}")
            sentence = []

    if sentence:
        text = " ".join(x["word"] for x in sentence)
        start = sentence[0]["start"]
        end = sentence[-1]["end"]
        print(f"[{start:6.2f} - {end:6.2f}] ({end - start:4.1f}s)  {text}")

    # Save word timestamps
    out_path = path.parent / "voiceover_words.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(words, f, indent=2)
    print(f"\nWord timestamps saved to {out_path}")

    # Update script JSON if requested
    if args.update_script:
        script_path = Path(args.update_script)
        if not script_path.exists():
            print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
            sys.exit(1)
        print(f"\nUpdating script timestamps from actual voiceover...")
        try:
            update_script_timestamps(script_path, words)
        except AlignmentQualityError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            print("ERROR_CODE: ALIGNMENT_POOR", file=sys.stderr)
            sys.exit(1)
        except AlignmentHardError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            print("ERROR_CODE: ALIGNMENT_FAILED", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
