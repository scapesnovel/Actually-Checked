"""
STEP 4 — VOICE
Edge-TTS (free Microsoft neural voices) narration, per-segment, so the editor
knows exact timing of every segment. Also produces word-level timestamps via
faster-whisper for animated captions.
"""
import asyncio, json, subprocess

import edge_tts

from .util import load_config, WORK_DIR


async def _tts(text: str, path: str, voice: str, rate: str):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(path)


def synth_segments(slug: str, script: dict) -> list[dict]:
    cfg = load_config()
    voice = cfg["video"]["voice"]
    rate = cfg["video"].get("voice_rate", "+8%")
    audio_dir = WORK_DIR / slug / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    meta = []
    for i, seg in enumerate(script["segments"]):
        mp3 = audio_dir / f"seg_{i:03d}.mp3"
        asyncio.run(_tts(seg["narration"], str(mp3), voice, rate))
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(mp3)]).decode().strip())
        meta.append({"index": i, "file": str(mp3), "duration": dur})

    (audio_dir / "segments.json").write_text(json.dumps(meta, indent=2),
                                             encoding="utf-8")
    return meta


def word_timestamps(slug: str, meta: list[dict]) -> list[list[dict]]:
    """Word-level timings per segment for karaoke captions (faster-whisper)."""
    from faster_whisper import WhisperModel
    model = WhisperModel("tiny.en", compute_type="int8")
    all_words = []
    for m in meta:
        words = []
        segments, _ = model.transcribe(m["file"], word_timestamps=True)
        for s in segments:
            for w in s.words or []:
                words.append({"word": w.word.strip(), "start": float(w.start),
                              "end": float(w.end)})
        all_words.append(words)
    (WORK_DIR / slug / "audio" / "words.json").write_text(
        json.dumps(all_words), encoding="utf-8")
    return all_words
