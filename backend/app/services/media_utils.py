import subprocess
from pathlib import Path


def _run_ffmpeg(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def extract_audio(video_path: str, audio_path: str, max_duration_seconds: int | None = None) -> str:
    """Extract mono 16kHz WAV audio from a video file using ffmpeg (must be on PATH)."""
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
    ]
    if max_duration_seconds and max_duration_seconds > 0:
        cmd.extend(["-t", str(max_duration_seconds)])
    cmd.append(audio_path)
    _run_ffmpeg(cmd)
    return audio_path


def split_audio(audio_path: str, output_dir: str, chunk_seconds: int) -> list[str]:
    """Split a WAV file into smaller WAV chunks for APIs that prefer short clips."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    chunk_pattern = str(Path(output_dir) / "chunk_%03d.wav")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        audio_path,
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-reset_timestamps",
        "1",
        "-c",
        "copy",
        chunk_pattern,
    ]
    _run_ffmpeg(cmd)
    return sorted(str(path) for path in Path(output_dir).glob("chunk_*.wav"))
