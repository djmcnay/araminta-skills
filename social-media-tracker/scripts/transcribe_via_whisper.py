#!/usr/bin/env python3
"""
Download YouTube audio and transcribe via faster-whisper.

Bypasses youtube-transcript-api (which blocks cloud IPs) by using
yt-dlp to download audio + local Whisper for transcription.

Usage:
    python3 transcribe_via_whisper.py <url_or_video_id> [--model turbo|small|large-v3] [--language en]

Output: plain-text transcript to stdout.
Exit code 1 on failure (error message to stderr).
"""

import argparse
import os
import sys
import tempfile
import subprocess
import shutil


def check_deps():
    """Verify yt-dlp and faster_whisper are available."""
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        print("ERROR: yt-dlp not installed. Install the yt-dlp package in your Python environment", file=sys.stderr)
        sys.exit(1)
    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except ImportError:
        print("ERROR: faster-whisper not installed. Install the faster-whisper package in your Python environment", file=sys.stderr)
        sys.exit(1)


def download_audio(url: str, tmp_dir: str) -> str:
    """Download audio from YouTube URL as 16kHz mono WAV. Returns path."""
    import yt_dlp

    out_path = os.path.join(tmp_dir, "audio.wav")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(tmp_dir, "raw.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "socket_timeout": 30,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
        "postprocessor_args": [
            "-ar", "16000",
            "-ac", "1",
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if not os.path.exists(out_path):
        # yt-dlp might name it differently; find any wav
        for f in os.listdir(tmp_dir):
            if f.endswith(".wav"):
                return os.path.join(tmp_dir, f)
        raise FileNotFoundError(f"No WAV output found in {tmp_dir}")

    return out_path


def transcribe(audio_path: str, model_size: str = "turbo", language: str = "en") -> str:
    """Transcribe audio file using faster-whisper. Returns plain text."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        temperature=0.0,
        language=language,
        vad_filter=True,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    return text


def main():
    parser = argparse.ArgumentParser(description="Download + Whisper-transcribe a YouTube video")
    parser.add_argument("url", help="YouTube URL or video ID")
    parser.add_argument("--model", default="turbo", choices=["small", "medium", "large-v3", "turbo"],
                        help="Whisper model size (default: turbo)")
    parser.add_argument("--language", default="en", help="Language code (default: en)")
    args = parser.parse_args()

    check_deps()

    tmp_dir = tempfile.mkdtemp(prefix="yt_whisper_")
    try:
        audio_path = download_audio(args.url, tmp_dir)
        text = transcribe(audio_path, model_size=args.model, language=args.language)
        if not text:
            print("WARNING: Empty transcript produced.", file=sys.stderr)
        print(text)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
