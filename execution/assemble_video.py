"""
assemble_video.py -- Assemble final reel from video clips, voiceover, and captions.

Uses ffmpeg for all video operations. Reads script JSON for timing and assembly notes.

Usage:
    py execution/assemble_video.py .tmp/screen_addiction_children/screen_addiction_36s_script.json

Output:
    {script_dir}/final_reel.mp4
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FFMPEG = str(PROJECT_ROOT / "tools" / "ffmpeg.exe")
if not Path(FFMPEG).exists():
    FFMPEG = "ffmpeg"

FFPROBE = str(PROJECT_ROOT / "tools" / "ffprobe.exe")
if not Path(FFPROBE).exists():
    FFPROBE = "ffprobe"

FONT_BOLD = str(PROJECT_ROOT / "tools" / "fonts" / "Kalam-Bold.ttf")
FONT_REGULAR = str(PROJECT_ROOT / "tools" / "fonts" / "Kalam-Regular.ttf")

XFADE_DURATION = 0.3  # seconds per cross transition
LIP_SYNC_OFFSET = 0.0  # disabled — Kling's issue is phoneme accuracy, not startup lag


# 10-minute wall clock for any single ffmpeg call. A corrupted input or pathological
# filter graph can otherwise hang the Fly worker indefinitely and starve the
# 3-slot pipeline queue.
FFMPEG_TIMEOUT_SECONDS = 600
FFPROBE_TIMEOUT_SECONDS = 60


def run_ffmpeg(args: list, label: str = "", verbose: bool = False):
    cmd = [FFMPEG, "-y"] + args
    print(f"  Running: {label or ' '.join(cmd[:6])}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        print(f"  FFMPEG TIMEOUT ({FFMPEG_TIMEOUT_SECONDS}s): {label}", file=sys.stderr)
        print("ERROR_CODE: FFMPEG_TIMEOUT", file=sys.stderr)
        raise RuntimeError(f"ffmpeg timed out after {FFMPEG_TIMEOUT_SECONDS}s: {label}")
    if result.returncode != 0:
        print(f"  FFMPEG ERROR: {result.stderr[-800:]}", file=sys.stderr)
        raise RuntimeError(f"ffmpeg failed: {label}")
    if verbose and result.stderr:
        # Print last few lines of ffmpeg stderr for debugging
        lines = result.stderr.strip().split('\n')
        for line in lines[-5:]:
            print(f"    [ffmpeg] {line}")
    return result


def get_duration(filepath: Path) -> float:
    cmd = [FFPROBE, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(filepath)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT_SECONDS)
    return float(result.stdout.strip())


# ========== CLIP ORDERING ==========

def extract_clip_order(script: dict, total_duration: float = 33.86) -> list:
    """Return ordered list of clips. Each clip's trim_to spans from its
    narration_start to the next scene's narration_start."""
    raw = []
    for scene in script["scenes"]:
        sid = scene["scene_id"]
        vg = scene.get("video_generation", {})
        method = vg.get("method", "")

        if "clips" in vg:
            for clip in vg["clips"]:
                cid = clip["clip_id"]
                raw.append({
                    "name": f"broll_scene{cid}",
                    "type": "broll",
                    "narration_start": clip.get("narration_start"),
                    "narration_end": clip.get("narration_end"),
                })
        elif method == "lip-sync":
            raw.append({
                "name": f"anchor_scene{sid}",
                "type": "anchor",
                "narration_start": scene.get("narration_start"),
                "narration_end": scene.get("narration_end"),
            })
        elif method == "image-to-video":
            raw.append({
                "name": f"broll_scene{sid}",
                "type": "broll",
                "narration_start": scene.get("narration_start"),
                "narration_end": scene.get("narration_end"),
            })

    # Drop clips with no narration timing (e.g. scenes whose narration came back
    # empty upstream — those produce narration_start=None and crash the trim math
    # below). Skipping them lets the previous clip extend naturally to fill the gap.
    skipped = [c["name"] for c in raw if c["narration_start"] is None]
    if skipped:
        print(f"WARNING: skipping {len(skipped)} clip(s) with no narration_start: {skipped}")
    raw = [c for c in raw if c["narration_start"] is not None]

    if not raw:
        raise ValueError("extract_clip_order: no clips with valid narration_start")

    # Each clip spans start-to-start of next scene
    for i in range(len(raw)):
        if i < len(raw) - 1:
            raw[i]["trim_to"] = raw[i + 1]["narration_start"] - raw[i]["narration_start"]
        else:
            raw[i]["trim_to"] = total_duration - raw[i]["narration_start"]

    return raw


# ========== VIDEO OPERATIONS ==========

def trim_and_normalize(input_path: Path, output_path: Path, duration: float, start_offset: float = 0.0):
    """Trim clip to target duration AND normalize resolution in a single ffmpeg pass.

    Merges the old trim_clip + normalize_clip into one decode→encode cycle (A2 optimisation).
    Source is trimmed/padded to `duration`, then scaled to 1080×1920@30fps.
    """
    NORM_VF = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"
    ss_args = ["-ss", f"{start_offset:.3f}"] if start_offset > 0 else []

    src_dur = get_duration(input_path) - start_offset
    if src_dur >= duration - 0.01:
        vf = NORM_VF
        label = f"trim+norm {input_path.name} to {duration:.2f}s"
    else:
        pad_dur = duration - src_dur
        vf = f"tpad=stop_mode=clone:stop_duration={pad_dur:.3f},{NORM_VF}"
        label = f"trim+pad+norm {input_path.name} to {duration:.2f}s (pad={pad_dur:.2f}s)"

    run_ffmpeg(
        ss_args + [
            "-i", str(input_path),
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-r", "30",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-an",
            str(output_path)
        ], label
    )


def build_xfade_concat(clips: list, output_path: Path, fade_dur: float = XFADE_DURATION, verbose: bool = False):
    """Concatenate clips with xfade cross transitions.

    Single-filtergraph chain — one ffmpeg invocation, N inputs, N-1 chained
    xfades. Memory is O(N) (ffmpeg demuxes all input streams concurrently),
    which is fine on shared-cpu-2x/4gb but OOM'd on shared-cpu-1x/2gb. See
    fly.toml [[vm]] comments and s32 checkpoint for the bounded-N + vertical-
    scaling rationale (the s31 pairwise refactor was reverted in s32).

    To preserve total duration matching the voiceover, each clip (except last)
    is extended by fade_dur so the overlap doesn't shrink the timeline.
    """
    n = len(clips)
    if n == 0:
        raise RuntimeError("No clips to concatenate")
    if n == 1:
        run_ffmpeg(["-i", str(clips[0]["path"]), "-c", "copy", str(output_path)], "copy single clip")
        return

    # Build inputs
    inputs = []
    for clip in clips:
        inputs.extend(["-i", str(clip["path"])])

    # Build xfade filter chain
    # offset for transition i = sum of effective durations of clips 0..i minus fade_dur
    # effective duration of clip j in the timeline = clip_dur - fade_dur (except last clip)
    filter_parts = []
    cumulative = clips[0]["duration"]  # first clip plays fully until the fade starts

    if n == 2:
        offset = cumulative - fade_dur
        filter_parts.append(
            f"[0:v][1:v]xfade=transition=fade:duration={fade_dur}:offset={offset:.3f}[v]"
        )
    else:
        # First transition
        offset = cumulative - fade_dur
        filter_parts.append(
            f"[0:v][1:v]xfade=transition=fade:duration={fade_dur}:offset={offset:.3f}[v1]"
        )
        # Subsequent transitions
        for i in range(2, n):
            # After the previous xfade, the timeline advanced by clips[i-1].duration - fade_dur
            cumulative += clips[i - 1]["duration"] - fade_dur
            offset = cumulative - fade_dur
            prev_label = f"v{i - 1}"
            out_label = "v" if i == n - 1 else f"v{i}"
            filter_parts.append(
                f"[{prev_label}][{i}:v]xfade=transition=fade:duration={fade_dur}:offset={offset:.3f}[{out_label}]"
            )

    filter_str = ";".join(filter_parts)

    if verbose:
        print(f"    Filter: {filter_str[:200]}...")
        for i, clip in enumerate(clips):
            print(f"    [{i}] {clip['name']}: duration={clip['duration']:.3f}s path={clip['path']}")

    run_ffmpeg(
        inputs + [
            "-filter_complex", filter_str,
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            str(output_path)
        ],
        "xfade cross concatenation",
        verbose=verbose
    )


def add_voiceover(video_path: Path, audio_path: Path, output_path: Path):
    run_ffmpeg([
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path)
    ], "add voiceover")


# ========== COMPOSITE VOICEOVER (Option A / Option C) ==========

def extract_audio_from_clip(video_path: Path, output_path: Path):
    """Extract audio track from avatar video clip as WAV."""
    run_ffmpeg([
        "-i", str(video_path),
        "-vn", "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "1",
        str(output_path)
    ], f"extract audio {video_path.name}")


def extract_voiceover_segment(voiceover_path: Path, start: float, duration: float, output_path: Path):
    """Extract a time segment from the voiceover file."""
    run_ffmpeg([
        "-i", str(voiceover_path),
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
        "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "1",
        str(output_path)
    ], f"extract VO {start:.2f}-{start+duration:.2f}s")


def build_composite_voiceover(clip_order: list, clips_dir: Path, voiceover_path: Path,
                              total_duration: float, tmp_dir: Path, output_path: Path,
                              trim_avatar: bool = True):
    """Build composite voiceover: avatar audio for anchors, original VO for b-roll.

    Args:
        trim_avatar: If True (Option C), trim avatar audio to match original narration
                     duration. If False (Option A), use avatar audio at full natural
                     length (preserves ~25ms padding that matches lip movements).
    """
    print(f"\n--- Building composite voiceover ({'Option C' if trim_avatar else 'Option A'}) ---")
    comp_dir = tmp_dir / "composite"
    comp_dir.mkdir(exist_ok=True)

    segments = []
    prev_end = 0.0

    for clip in clip_order:
        ns = clip["narration_start"]
        ne = clip["narration_end"]
        scene_dur = ne - ns

        # Fill gap between previous segment and this one (from original VO)
        if ns > prev_end + 0.001:
            gap_dur = ns - prev_end
            gap_path = comp_dir / f"gap_{len(segments):02d}.wav"
            extract_voiceover_segment(voiceover_path, prev_end, gap_dur, gap_path)
            segments.append(gap_path)
            print(f"  gap: {prev_end:.3f}-{ns:.3f}s ({gap_dur:.3f}s)")

        if clip["type"] == "anchor":
            src = clips_dir / f"{clip['name']}.mp4"
            audio_out = comp_dir / f"{clip['name']}_avatar.wav"
            extract_audio_from_clip(src, audio_out)
            actual_dur = get_duration(audio_out)

            # Guard 1: Duration sanity check
            delta_ms = (actual_dur - scene_dur) * 1000
            if actual_dur < scene_dur:
                print(f"  WARNING: {clip['name']} avatar audio ({actual_dur:.3f}s) is SHORTER "
                      f"than narration ({scene_dur:.3f}s) by {-delta_ms:.0f}ms — trimming would clip speech!")
            elif delta_ms > 100:
                print(f"  WARNING: {clip['name']} avatar audio delta is abnormally large "
                      f"({delta_ms:.0f}ms) — Avatar may have altered timing!")

            # Guard 2: Silence detection on the portion being trimmed
            if trim_avatar and actual_dur > scene_dur:
                trim_amount = actual_dur - scene_dur
                # Check if the tail being trimmed contains speech (energy above -40dB)
                tail_check = subprocess.run(
                    [FFMPEG, "-y", "-ss", f"{scene_dur:.3f}", "-i", str(audio_out),
                     "-af", "silencedetect=noise=-40dB:d=0.01",
                     "-f", "null", "-"],
                    capture_output=True, text=True, timeout=FFPROBE_TIMEOUT_SECONDS,
                )
                stderr = tail_check.stderr
                # If silencedetect does NOT report silence_start, the tail has speech energy
                if "silence_start" not in stderr and trim_amount > 0.005:
                    print(f"  WARNING: {clip['name']} tail being trimmed ({trim_amount*1000:.0f}ms) "
                          f"may contain speech — silence not detected at -40dB threshold!")

            if trim_avatar and abs(actual_dur - scene_dur) > 0.01:
                # Option C: trim to match original narration duration
                trimmed = comp_dir / f"{clip['name']}_avatar_trimmed.wav"
                run_ffmpeg([
                    "-i", str(audio_out),
                    "-t", f"{scene_dur:.3f}",
                    "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "1",
                    str(trimmed)
                ], f"trim avatar audio {clip['name']}")
                segments.append(trimmed)
                print(f"  {clip['name']}: avatar audio {actual_dur:.3f}s -> trimmed to {scene_dur:.3f}s")
                prev_end = ne
            else:
                # Option A: use full avatar audio (may be slightly longer)
                segments.append(audio_out)
                print(f"  {clip['name']}: avatar audio {actual_dur:.3f}s (full)")
                prev_end = ns + actual_dur  # advance by actual avatar duration
        else:
            seg_out = comp_dir / f"{clip['name']}_vo.wav"
            extract_voiceover_segment(voiceover_path, ns, scene_dur, seg_out)
            segments.append(seg_out)
            print(f"  {clip['name']}: VO segment {ns:.3f}-{ne:.3f}s ({scene_dur:.3f}s)")
            prev_end = ne

    # Trailing audio (if voiceover extends beyond last scene)
    if total_duration > prev_end + 0.01:
        tail_dur = total_duration - prev_end
        tail_path = comp_dir / f"tail.wav"
        extract_voiceover_segment(voiceover_path, prev_end, tail_dur, tail_path)
        segments.append(tail_path)
        print(f"  tail: {prev_end:.3f}-{total_duration:.3f}s ({tail_dur:.3f}s)")

    # Concatenate all segments
    list_file = comp_dir / "segments.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"file '{seg.resolve().as_posix()}'\n")

    run_ffmpeg([
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:a", "libmp3lame", "-q:a", "2",
        str(output_path)
    ], "concat composite voiceover")

    orig_dur = get_duration(voiceover_path)
    comp_dur = get_duration(output_path)
    print(f"  Composite: {comp_dur:.2f}s | Original: {orig_dur:.2f}s | Delta: {comp_dur - orig_dur:+.3f}s")


def mix_background_music(video_path: Path, music_path: Path, output_path: Path,
                         music_volume: float = 0.10, voice_volume: float = 1.0,
                         fadeout_seconds: float = 2.0):
    """Mix background music into video with configurable voice/music volumes.

    Args:
        music_volume: Music volume (0.10 = 10%). Lower = softer music.
        voice_volume: Voiceover volume boost (1.0 = no change, 1.5 = 50% louder).
        fadeout_seconds: Seconds before end to start fading out music.
    """
    video_duration = get_duration(video_path)
    fade_start = max(0, video_duration - fadeout_seconds)

    # Filter: boost voice, lower music, fade-out, then mix
    voice_filter = f"[0:a]volume={voice_volume}[voice];" if voice_volume != 1.0 else ""
    voice_label = "[voice]" if voice_volume != 1.0 else "[0:a]"
    filter_complex = (
        f"{voice_filter}"
        f"[1:a]volume={music_volume},afade=t=out:st={fade_start:.3f}:d={fadeout_seconds:.3f}[music];"
        f"{voice_label}[music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    run_ffmpeg([
        "-i", str(video_path),
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path)
    ], f"mix background music (vol={music_volume}, fadeout={fadeout_seconds}s)")


def speed_up_video(video_path: Path, output_path: Path, speed: float):
    """Speed up entire video by `speed` factor using setpts (video) + atempo (audio).

    Pitch-preserving (atempo uses WSOLA), so voice and music both compress in time
    without sounding chipmunked. Audio and video stretch by exactly the same factor,
    so lip-sync is preserved.

    Used as the final pipeline step to apply 1.2x reel pacing without burning the
    speed parameter into ElevenLabs (which has a hard cap at 1.2x and degrades
    quality when used).
    """
    if speed == 1.0:
        # No-op — just copy
        shutil.copy2(video_path, output_path)
        return

    setpts = f"PTS/{speed}"
    # atempo accepts 0.5..2.0 in a single instance; 1.2 is well within range
    run_ffmpeg([
        "-i", str(video_path),
        "-filter_complex", f"[0:v]setpts={setpts}[v];[0:a]atempo={speed}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path)
    ], f"speed up final reel by {speed}x (setpts + atempo, pitch-preserving)")


# ========== CAPTIONS (ASS SUBTITLES) ==========

def ts_to_ass(seconds: float) -> str:
    """Convert seconds to ASS timestamp format H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass_subtitles(script: dict, words: list, font_path: str, output_path: Path):
    """Generate ASS subtitle file with Kalam font, 60% height, yellow emphasis.

    Shows full narration_text as captions. Emphasis keywords (ALL CAPS words
    from caption_text) are rendered in yellow; all other words are white.
    Font: Kalam Bold.
    """
    # Identify emphasized words from caption_text across all scenes
    emphasis_words = set()
    for scene in script["scenes"]:
        caption = scene.get("caption_text", "")
        for word in caption.split():
            clean = word.strip(".,!?;:-")
            # If the word is ALL CAPS (and not a single char like 'a'), it's emphasized
            if clean.isupper() and len(clean) > 1:
                emphasis_words.add(clean)

    print(f"  Emphasis words (yellow): {emphasis_words}")

    # Build subtitle events -- one per scene, with inline color for emphasis
    # ASS color format: \c&HBBGGRR& (BGR order)
    # Yellow = R:FF G:FF B:00 -> &H0000FFFF& (but in ASS override: \c&H00FFFF&)
    # White = &HFFFFFF&
    YELLOW = "\\c&H00FFFF&"
    WHITE = "\\c&HFFFFFF&"

    font_name = "Kalam Bold"

    # Build ASS header
    # Position: 60% from top on 1920px = y=1152. Using Alignment 2 (bottom-center),
    # MarginV = 1920 - 1152 = 768
    ass_lines = []
    ass_lines.append("[Script Info]")
    ass_lines.append("ScriptType: v4.00+")
    ass_lines.append("PlayResX: 1080")
    ass_lines.append("PlayResY: 1920")
    ass_lines.append("WrapStyle: 0")
    ass_lines.append("")
    ass_lines.append("[V4+ Styles]")
    ass_lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    ass_lines.append(f"Style: Default,{font_name},59,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,0,2,40,40,576,1")
    ass_lines.append("")
    ass_lines.append("[Events]")
    ass_lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

    # Scenes to skip captions for (e.g. brand card already has text)
    skip_caption_scenes = script.get("skip_caption_scenes", [])

    for scene in script["scenes"]:
        if scene["scene_id"] in skip_caption_scenes:
            continue
        caption = scene.get("narration_text", "")
        if not caption:
            continue

        start = scene.get("narration_start", 0)
        end = scene.get("narration_end", start + 3)

        # Build text with inline color overrides
        parts = []
        for word in caption.split():
            clean = word.strip(".,!?;:-")
            # Check if this word matches an emphasis keyword from caption_text
            if clean.upper() in emphasis_words:
                parts.append(f"{{{YELLOW}}}{word}{{{WHITE}}}")
            else:
                parts.append(word)

        styled_text = " ".join(parts)

        # Wrap to ~25 chars per line using ASS line break \N
        wrapped = ass_word_wrap(styled_text, max_chars=25)

        ass_lines.append(
            f"Dialogue: 0,{ts_to_ass(start)},{ts_to_ass(end)},Default,,0,0,0,,{wrapped}"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ass_lines) + "\n")

    print(f"  ASS subtitles saved: {output_path}")


def ass_word_wrap(text: str, max_chars: int = 25) -> str:
    """Wrap text for ASS subtitles using \\N line breaks.
    Skips ASS override tags when counting characters."""
    words = text.split()
    lines = []
    current_line = ""
    current_len = 0  # visible char count (excluding tags)

    for word in words:
        # Calculate visible length (strip ASS tags like {\c&H00FFFF&})
        visible = re.sub(r'\{[^}]*\}', '', word)
        word_len = len(visible)

        if current_len + word_len + (1 if current_line else 0) > max_chars and current_line:
            lines.append(current_line)
            current_line = word
            current_len = word_len
        else:
            current_line = f"{current_line} {word}".strip() if current_line else word
            current_len += word_len + (1 if current_len > 0 else 0)

    if current_line:
        lines.append(current_line)

    return "\\N".join(lines)


def burn_subtitles(video_path: Path, ass_path: Path, font_dir: Path, output_path: Path,
                   speed: float = 1.0):
    """Burn ASS subtitles into video, optionally applying speed-adjust in the same pass.

    A1 optimisation: when speed != 1.0, the subtitles filter reads frames at their
    original 1.0× PTS (so ASS timestamps align correctly), then setpts compresses
    the timeline. This replaces two separate libx264 encodes with one.
    """
    fonts_dir_str = str(font_dir.resolve()).replace("\\", "/").replace(":", "\\:")
    ass_str = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:")

    sub_filter = f"subtitles='{ass_str}':fontsdir='{fonts_dir_str}'"

    if speed != 1.0:
        vf = f"{sub_filter},setpts=PTS/{speed}"
        af = f"atempo={speed}"
        run_ffmpeg([
            "-i", str(video_path),
            "-filter_complex", f"[0:v]{vf}[v];[0:a]{af}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ], f"burn captions + speed {speed}x (A1 merged)")
    else:
        run_ffmpeg([
            "-i", str(video_path),
            "-vf", sub_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy",
            str(output_path)
        ], "burn ASS captions")


# ========== MAIN ==========

def main():
    parser = argparse.ArgumentParser(description="Assemble final reel from clips")
    parser.add_argument("script", help="Path to script JSON file")
    parser.add_argument("--no-captions", action="store_true", help="Skip caption burn-in")
    parser.add_argument("--audio-mode", choices=["original", "option-a", "option-c"],
                        default="original",
                        help="Audio mode: original (voiceover.mp3 as-is), "
                             "option-a (avatar audio full-length on anchors), "
                             "option-c (avatar audio trimmed + VO on b-roll)")
    parser.add_argument("--music-volume", type=float, default=0.30,
                        help="Background music volume (0.0-1.0, default: 0.30)")
    parser.add_argument("--voice-volume", type=float, default=1.0,
                        help="Voiceover volume boost (1.0=normal, 1.5=50%% louder)")
    parser.add_argument("--final-speed", type=float, default=1.2,
                        help="Final reel playback speed (default 1.2). "
                             "Applied as the LAST step via setpts+atempo (pitch-preserving). "
                             "Set to 1.0 to disable.")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    base_dir = script_path.parent
    clips_root = base_dir / "video_clips"
    voiceover_path = base_dir / "voiceover.mp3"
    words_path = base_dir / "voiceover_words.json"
    font_dir = PROJECT_ROOT / "tools" / "fonts"

    # Find latest video clips run
    latest_file = clips_root / ".latest"
    if latest_file.exists():
        run_name = latest_file.read_text().strip()
        clips_dir = clips_root / run_name
        print(f"Using video clips from: {clips_dir}")
    else:
        # Fallback: look for clips directly in video_clips/ (legacy layout)
        clips_dir = clips_root
        print(f"No .latest pointer found, using: {clips_dir}")

    # Always start fresh assembly — delete stale intermediates
    tmp_dir = base_dir / "assembly_tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    total_duration = script.get("actual_duration_seconds", 33.86)
    clip_order = extract_clip_order(script, total_duration)
    n_clips = len(clip_order)
    print(f"Assembly: {n_clips} clips, xfade={XFADE_DURATION}s")

    # To compensate for xfade shrinking the timeline,
    # extend each clip (except last) by XFADE_DURATION
    for i, clip in enumerate(clip_order):
        if i < n_clips - 1:
            clip["trim_to"] += XFADE_DURATION

    # Step 1+2: Trim + normalize in a single pass per clip (A2 optimisation)
    print(f"\n--- Step 1+2: Trim + normalize (lip-sync offset={LIP_SYNC_OFFSET}s) ---")
    normalized = []
    for clip in clip_order:
        name = clip["name"]
        src = clips_dir / f"{name}.mp4"
        if not src.exists():
            print(f"  WARNING: Missing {src}, skipping")
            continue

        trim_to = clip["trim_to"]
        offset = LIP_SYNC_OFFSET if clip["type"] == "anchor" else 0.0
        dst = tmp_dir / f"{name}_norm.mp4"
        trim_and_normalize(src, dst, trim_to, start_offset=offset)

        actual_dur = get_duration(dst)
        normalized.append({"path": dst, "duration": actual_dur, "name": name})
        print(f"  {name}: {trim_to:.2f}s{f' (offset {offset}s)' if offset > 0 else ''}")

    # Step 3: Concatenate with xfade cross transitions
    print("\n--- Step 3: xfade cross transitions ---")
    concat_path = tmp_dir / "concat_xfade.mp4"
    build_xfade_concat(normalized, concat_path, XFADE_DURATION, verbose=True)
    concat_dur = get_duration(concat_path)
    print(f"  Concat duration: {concat_dur:.2f}s")

    # Guard: fail if video is too short for the voiceover
    if voiceover_path.exists():
        vo_dur = get_duration(voiceover_path)
        if concat_dur < vo_dur - 0.5:
            raise RuntimeError(
                f"SYNC ERROR: Video ({concat_dur:.2f}s) shorter than voiceover ({vo_dur:.2f}s) by {vo_dur - concat_dur:.2f}s. "
                f"Source clips too short — re-generate with longer Kling durations."
            )

    # Step 4: Add voiceover
    print("\n--- Step 4: Adding voiceover ---")
    with_audio_path = tmp_dir / "with_audio.mp4"

    if args.audio_mode in ("option-a", "option-c"):
        # Build composite voiceover from avatar audio + original VO segments
        composite_path = tmp_dir / f"voiceover_composite_{args.audio_mode.replace('-', '')}.mp3"
        trim_avatar = (args.audio_mode == "option-c")
        build_composite_voiceover(clip_order, clips_dir, voiceover_path,
                                  total_duration, tmp_dir, composite_path,
                                  trim_avatar=trim_avatar)
        add_voiceover(concat_path, composite_path, with_audio_path)
    elif voiceover_path.exists():
        add_voiceover(concat_path, voiceover_path, with_audio_path)
    else:
        print("  WARNING: No voiceover found, proceeding without audio")
        with_audio_path = concat_path

    # Step 5: Mix background music
    music_path = base_dir / "background_music.mp3"
    with_music_path = tmp_dir / "with_music.mp4"
    if music_path.exists():
        print(f"\n--- Step 5: Mixing background music (music={args.music_volume}, voice={args.voice_volume}) ---")
        mix_background_music(with_audio_path, music_path, with_music_path,
                             music_volume=args.music_volume,
                             voice_volume=args.voice_volume,
                             fadeout_seconds=2.0)
    else:
        print("\n--- Step 5: No background music found, skipping ---")
        with_music_path = with_audio_path

    # Step 6+7: Build captions and burn into video (with speed-adjust folded in via A1)
    suffix = f"_{args.audio_mode.replace('-', '')}" if args.audio_mode != "original" else ""
    reel_name = f"final_reel{suffix}.mp4"
    final_path = base_dir / reel_name

    if args.no_captions:
        if args.final_speed != 1.0:
            print(f"\n--- Step 6: Speed-adjust only ({args.final_speed}x) ---")
            speed_up_video(with_music_path, final_path, args.final_speed)
        else:
            final_path = with_music_path
    else:
        print("\n--- Step 6: Building ASS captions (Kalam, yellow emphasis) ---")
        words = []
        if words_path.exists():
            with open(words_path, encoding="utf-8") as f:
                words = json.load(f)

        ass_path = tmp_dir / "captions.ass"
        build_ass_subtitles(script, words, FONT_BOLD, ass_path)

        speed_label = f" + speed {args.final_speed}x" if args.final_speed != 1.0 else ""
        print(f"\n--- Step 7: Burning captions{speed_label} (A1 merged) ---")
        burn_subtitles(with_music_path, ass_path, font_dir, final_path,
                       speed=args.final_speed)

    dur = get_duration(final_path)
    print(f"\n=== DONE ===")
    print(f"Final reel: {final_path}")
    print(f"Duration: {dur:.2f}s")
    print(f"Voiceover: {total_duration:.2f}s (1.0x source)")
    if args.final_speed != 1.0:
        print(f"Final speed: {args.final_speed}x (applied via setpts+atempo)")
        print(f"Expected reel duration: {total_duration / args.final_speed:.2f}s")
    print(f"Sync delta: {abs(dur - total_duration / args.final_speed):.2f}s")


if __name__ == "__main__":
    main()
