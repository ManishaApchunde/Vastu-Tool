"""Narration voices. Every provider writes a mono WAV and returns its length in seconds.

  edge   Microsoft Edge neural voices (free, needs internet): mr-IN-AarohiNeural / en-IN-NeerjaNeural
  gtts   Google Translate voice (free, needs internet; pip install gTTS)
  silent no voice: on-screen text and subtitles only, timed to a natural reading pace

VIDEO_TTS=auto tries edge, then gtts, then silent, and keeps the first one that works for the
whole video so the voice never changes half-way."""
import asyncio
import logging
import re
import subprocess
import wave
from pathlib import Path

from app.core.config import settings
from app.videos.compose import ffmpeg_exe

log = logging.getLogger("vastu.video")
VOICE_LANG = {"en": "en-IN", "mr": "mr-IN"}
CHARS_PER_SECOND = {"en": 15.0, "mr": 12.5}


class TTSUnavailable(RuntimeError):
    pass


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def _to_wav(src: Path, dst: Path) -> float:
    r = subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "24000",
                        str(dst)], capture_output=True, timeout=120)
    if r.returncode != 0:
        raise TTSUnavailable(r.stderr.decode(errors="ignore")[-300:])
    return wav_seconds(dst)


class Narrator:
    name = "base"

    def synth(self, text: str, language: str, out: Path) -> float:
        raise NotImplementedError


class EdgeNarrator(Narrator):
    name = "edge"

    def __init__(self):
        try:
            import edge_tts  # noqa: F401
        except ImportError as exc:
            raise TTSUnavailable("edge-tts is not installed") from exc

    def synth(self, text, language, out):
        import edge_tts

        voice = settings.video_voice_mr if language == "mr" else settings.video_voice_en
        mp3 = out.with_suffix(".mp3")

        async def run():
            await edge_tts.Communicate(text, voice, rate=settings.video_voice_rate).save(str(mp3))
        try:
            asyncio.run(asyncio.wait_for(run(), timeout=90))
        except Exception as exc:  # noqa: BLE001 - network, voice or service errors
            raise TTSUnavailable(f"edge-tts failed: {exc}") from exc
        if not mp3.exists() or mp3.stat().st_size < 1000:
            raise TTSUnavailable("edge-tts returned no audio")
        return _to_wav(mp3, out)


class GTTSNarrator(Narrator):
    name = "gtts"

    def __init__(self):
        try:
            import gtts  # noqa: F401
        except ImportError as exc:
            raise TTSUnavailable("gTTS is not installed") from exc

    def synth(self, text, language, out):
        from gtts import gTTS

        mp3 = out.with_suffix(".mp3")
        try:
            gTTS(text=text, lang=language, tld="co.in").save(str(mp3))
        except Exception as exc:  # noqa: BLE001
            raise TTSUnavailable(f"gTTS failed: {exc}") from exc
        return _to_wav(mp3, out)


class SilentNarrator(Narrator):
    name = "silent"

    def synth(self, text, language, out):
        seconds = max(5.0, len(re.sub(r"\s+", " ", text)) / CHARS_PER_SECOND.get(language, 14.0))
        rate = 24000
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"\x00\x00" * int(seconds * rate))
        return seconds


PROVIDERS = {"edge": EdgeNarrator, "gtts": GTTSNarrator, "silent": SilentNarrator}


def candidates() -> list[str]:
    choice = (settings.video_tts or "auto").lower()
    if choice == "auto":
        return ["edge", "gtts", "silent"]
    return [choice] if choice in PROVIDERS else ["silent"]


def pick_narrator(sample_text: str, language: str, workdir: Path) -> Narrator:
    """First provider that can actually speak this language right now (tested on a short sample)."""
    for name in candidates():
        try:
            n = PROVIDERS[name]()
            if name != "silent":
                n.synth(sample_text[:120], language, workdir / f"probe-{name}.wav")
            return n
        except TTSUnavailable as exc:
            log.warning("video narration: %s unavailable (%s)", name, exc)
    return SilentNarrator()
