#!/usr/bin/env python3
"""
Tiered YouTube transcription strategy.

Strategy:
  1. Shorts / videos ≤5 minutes → always Whisper (fast enough, no API call needed)
  2. Long-form (>5 minutes) → try youtube-transcript-api first (fast, no audio download)
  3. If transcript API blocked/fails → fall back to yt-dlp audio + Whisper

Usage:
    python3 transcribe_tiered.py <url> [--format short|long] [--duration SECONDS] [--model turbo]

Output: plain-text transcript to stdout.
Exit code 1 on total failure (error message to stderr).
"""

import argparse
import os
import sys
import shutil


def try_transcript_api(video_id: str, language: str = "en") -> str | None:
    """Try youtube-transcript-api. Returns text or None if blocked/failed."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None

    try:
        api = YouTubeTranscriptApi()
        segments = api.fetch(video_id, languages=[language])
        text = " ".join(seg.text for seg in segments)
        return text.strip() if text.strip() else None
    except Exception as e:
        msg = str(e).lower()
        if "blocked" in msg or "ip" in msg or "requestblocked" in msg:
            print(f"[tiered] Transcript API blocked, will fall back to Whisper", file=sys.stderr)
            return None
        if "disabled" in msg or "no transcript" in msg:
            print(f"[tiered] No transcript available for this video", file=sys.stderr)
            return None
        # Transient error — log and fall back
        print(f"[tiered] Transcript API error ({e}), falling back to Whisper", file=sys.stderr)
        return None


def transcribe_whisper(url: str, model_size: str = "turbo", language: str = "en") -> str:
    """Download audio via yt-dlp and transcribe with Whisper."""
    import tempfile
    import yt_dlp
    from faster_whisper import WhisperModel

    tmp_dir = tempfile.mkdtemp(prefix="yt_whisper_")
    try:
        # Download audio
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(tmp_dir, "raw.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "socket_timeout": 30,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
            "postprocessor_args": ["-ar", "16000", "-ac", "1"],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find the WAV
        wav_path = None
        for f in os.listdir(tmp_dir):
            if f.endswith(".wav"):
                wav_path = os.path.join(tmp_dir, f)
                break
        if not wav_path:
            raise FileNotFoundError("No WAV output from yt-dlp")

        # Transcribe
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(
            wav_path, beam_size=5, temperature=0.0,
            language=language, vad_filter=True,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return text
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def extract_video_id(url: str) -> str:
    """Extract 11-char video ID from URL."""
    import re
    patterns = [
        r'(?:v=|youtu\.be/|shorts/|embed/|live/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for p in patterns:
        m = re.search(p, url.strip())
        if m:
            return m.group(1)
    return url.strip()


def get_duration(url: str) -> int | None:
    """Quick duration check via yt-dlp metadata (no download). Returns seconds or None."""
    import yt_dlp
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "print": "%(duration)s",
            "socket_timeout": 10,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            dur = info.get("duration") if info else None
            return int(dur) if dur else None
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Tiered YouTube transcription")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--format", choices=["short", "long"], default=None,
                        help="Video format (short/long). Auto-detected if omitted.")
    parser.add_argument("--duration", type=int, default=None,
                        help="Duration in seconds. Fetched if omitted and needed.")
    parser.add_argument("--model", default="turbo",
                        choices=["small", "medium", "large-v3", "turbo"],
                        help="Whisper model (default: turbo)")
    parser.add_argument("--language", default="en", help="Language code (default: en)")
    parser.add_argument("--always-whisper", action="store_true",
                        help="Skip transcript API, always use Whisper")
    args = parser.parse_args()

    video_id = extract_video_id(args.url)
    is_short = args.format == "short"
    duration = args.duration

    # Determine if short (explicit format or duration check)
    if is_short:
        print(f"[tiered] SHORT → Whisper directly", file=sys.stderr)
    elif args.format == "long" and duration is not None and duration < 300:
        is_short = True
        print(f"[tiered] Duration {duration}s < 300s → treating as short, Whisper", file=sys.stderr)
    elif args.format is None and duration is None:
        # No format or duration info — try a quick duration check
        duration = get_duration(args.url)
        if duration and duration < 300:
            is_short = True
            print(f"[tiered] Detected duration {duration}s < 300s → short, Whisper", file=sys.stderr)

    # ── Tier 1: Whisper for shorts ──
    if is_short or args.always_whisper:
        text = transcribe_whisper(args.url, model_size=args.model, language=args.language)
        print(text)
        return

    # ── Tier 2: Try transcript API for long-form ──
    print(f"[tiered] Long-form → trying transcript API first", file=sys.stderr)
    text = try_transcript_api(video_id, language=args.language)

    if text:
        print(text)
        return

    # ── Tier 3: Whisper fallback for long-form ──
    print(f"[tiered] Transcript API unavailable → Whisper fallback", file=sys.stderr)
    text = transcribe_whisper(args.url, model_size=args.model, language=args.language)
    print(text)


if __name__ == "__main__":
    main()
