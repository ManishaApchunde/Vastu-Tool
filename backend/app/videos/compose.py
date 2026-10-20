"""ffmpeg assembly: still slide + narration per scene (with short fades), concatenated, with
soft subtitles (English or Marathi) muxed into the MP4."""
import shutil
import subprocess
from pathlib import Path

FPS = 20
FADE = 0.35
TAIL = 0.8  # pause after each scene's narration


class VideoError(RuntimeError):
    pass


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - fall back to a system ffmpeg
        exe = shutil.which("ffmpeg")
        if not exe:
            raise VideoError("ffmpeg is not available. Install 'imageio-ffmpeg' (requirements.txt) or ffmpeg.")
        return exe


def _run(args: list[str], timeout: int = 600):
    r = subprocess.run([ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", *args], capture_output=True,
                       timeout=timeout)
    if r.returncode != 0:
        raise VideoError(r.stderr.decode(errors="ignore")[-600:])


def segment(frames: list[tuple[Path, float]], wav: Path, seconds: float, out: Path, workdir: Path) -> float:
    """One scene: a sequence of still frames (one per caption) over the scene's narration, with fades."""
    total = seconds + TAIL
    listing = out.with_suffix(".txt")
    lines, used = [], 0.0
    for i, (png, dur) in enumerate(frames):
        dur = (total - used) if i == len(frames) - 1 else dur
        used += dur
        lines.append(f"file '{png.as_posix()}'\nduration {max(0.05, dur):.3f}\n")
    lines.append(f"file '{frames[-1][0].as_posix()}'\n")  # concat demuxer needs the last frame repeated
    listing.write_text("".join(lines), encoding="utf-8")
    vf = (f"[0:v]fps={FPS},scale=1280:720:flags=lanczos,format=yuv420p,fade=t=in:st=0:d={FADE},"
          f"fade=t=out:st={max(0.0, total - FADE):.3f}:d={FADE}[v];[1:a]apad=pad_dur={TAIL}[a]")
    _run(["-f", "concat", "-safe", "0", "-i", str(listing), "-i", str(wav), "-filter_complex", vf,
          "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
          "-tune", "stillimage", "-crf", "24", "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "1",
          str(out)])
    return total


def join(segments: list[Path], subtitles: Path, language: str, out: Path, workdir: Path):
    listing = workdir / "segments.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
    joined = workdir / "joined.mp4"
    _run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)])
    lang3 = {"mr": "mar", "en": "eng"}[language]
    _run(["-i", str(joined), "-i", str(subtitles), "-map", "0", "-map", "1", "-c:v", "copy", "-c:a", "copy",
          "-c:s", "mov_text", "-metadata:s:s:0", f"language={lang3}", "-movflags", "+faststart", str(out)])


def _ts(t: float, sep: str) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)) % 1000:03d}"


def captions(cues: list[tuple[float, float, str]]) -> tuple[str, str]:
    """(srt, vtt) text for (start, end, text) cues."""
    srt = "".join(f"{i}\n{_ts(a, ',')} --> {_ts(b, ',')}\n{t}\n\n" for i, (a, b, t) in enumerate(cues, 1))
    vtt = "WEBVTT\n\n" + "".join(f"{_ts(a, '.')} --> {_ts(b, '.')}\n{t}\n\n" for a, b, t in cues)
    return srt, vtt
