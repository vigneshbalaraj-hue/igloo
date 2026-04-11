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
import json
import re
import sys
from pathlib import Path


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


def update_script_timestamps(script_path: Path, words: list):
    """Match voiceover words to scenes and update narration_start/end + audio_slice."""
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    word_idx = 0
    total_words = len(words)

    for scene in script["scenes"]:
        narration = scene.get("narration_text", "")
        if not narration:
            continue

        # Tokenize scene narration into words
        scene_words = narration.split()
        if not scene_words:
            continue

        # Match the first word of this scene in the voiceover word list
        first_norm = normalize_word(scene_words[0])
        last_norm = normalize_word(scene_words[-1])

        # Find the starting position — scan forward from current index
        match_start = None
        for i in range(word_idx, min(word_idx + 10, total_words)):
            if normalize_word(words[i]["word"]) == first_norm:
                match_start = i
                break

        if match_start is None:
            print(f"  WARNING: Could not match scene {scene['scene_id']} "
                  f"first word '{scene_words[0]}' in voiceover words (searched idx {word_idx}-{min(word_idx+10, total_words)})")
            continue

        # Find the ending position — advance through scene words
        match_end = match_start + len(scene_words) - 1
        if match_end >= total_words:
            match_end = total_words - 1

        # Verify last word matches
        if normalize_word(words[match_end]["word"]) != last_norm:
            # Try scanning nearby for the last word
            for i in range(match_start + len(scene_words) - 2, min(match_start + len(scene_words) + 3, total_words)):
                if normalize_word(words[i]["word"]) == last_norm:
                    match_end = i
                    break

        narration_start = round(words[match_start]["start"], 3)
        narration_end = round(words[match_end]["end"], 3)
        scene_duration = round(narration_end - narration_start, 3)

        old_start = scene.get("narration_start")
        old_end = scene.get("narration_end")

        # Update scene fields
        scene["narration_start"] = narration_start
        scene["narration_end"] = narration_end
        scene["scene_duration"] = scene_duration

        # Update video_generation fields based on scene type
        vg = scene.get("video_generation", {})

        # Dynamic kling_duration for b-roll: 10s if narration > 5s, else 5s
        if vg.get("method") == "image-to-video":
            vg["kling_duration"] = 10 if scene_duration > 5.0 else 5

        if vg.get("method") == "lip-sync":
            vg["audio_slice"] = [narration_start, narration_end]
            vg["kling_duration"] = f"driven by audio ({scene_duration}s)"

        # Log changes
        if old_start is not None and (abs(old_start - narration_start) > 0.01 or abs(old_end - narration_end) > 0.01):
            print(f"  Scene {scene['scene_id']}: {old_start:.2f}-{old_end:.2f} -> {narration_start:.3f}-{narration_end:.3f} "
                  f"(delta: {narration_start - old_start:+.3f}s start, {narration_end - old_end:+.3f}s end)")
        else:
            print(f"  Scene {scene['scene_id']}: {narration_start:.3f}-{narration_end:.3f} ({scene_duration:.2f}s)")

        # Advance word index past this scene
        word_idx = match_end + 1

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
            scene_start = scene["narration_start"]

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
        update_script_timestamps(script_path, words)


if __name__ == "__main__":
    main()
