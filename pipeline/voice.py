"""
STEP 4 — VOICE
Edge-TTS (free Microsoft neural voices) narration, per-segment, so the editor
knows exact timing of every segment. Also produces word-level timestamps via
faster-whisper for animated captions.

Delivery engineering:
- Sentence-by-sentence synthesis with real silence gaps between sentences
  (natural "breath") — fixes the rushed, run-on feel of single-call TTS.
- Question sentences get a slightly higher pitch; emphasis sentences
  (short, punchy) get a tiny slow-down — subtle prosody variation.
"""
import asyncio, json, re, subprocess, tempfile
from pathlib import Path

import edge_tts

from .util import load_config, WORK_DIR

# silence inserted between sentences (natural breathing room)
SENTENCE_GAP = 0.42
# extra pause after a question or a "reveal" sentence ending in "..."
DRAMATIC_GAP = 0.65


async def _tts(text: str, path: str, voice: str, rate: str, pitch: str = "+0Hz"):
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(path)


def _split_sentences(text: str) -> list[str]:
    """Split narration into speakable sentences (keep the delimiter)."""
    parts = re.split(r'(?<=[.!?])\s+|(?<=\.\.\.)\s+', text.strip())
    return [p.strip() for p in parts if p and p.strip()]


def _synth_segment(text: str, out_mp3: Path, voice: str, rate: str):
    """Synthesize one narration segment sentence-by-sentence with breathing
    gaps, then concat into a single mp3. Falls back to single-call TTS."""
    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        asyncio.run(_tts(text, str(out_mp3), voice, rate))
        return
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        pieces = []
        for si, sent in enumerate(sentences):
            p = td / f"s{si:02d}.mp3"
            # prosody variation: questions lift slightly, short punch
            # sentences slow down a touch for weight
            pitch = "+12Hz" if sent.rstrip().endswith("?") else "+0Hz"
            srate = rate
            if len(sent.split()) <= 5 and not sent.endswith("?"):
                srate = "-4%"   # short punch line -> lands heavier
            try:
                asyncio.run(_tts(sent, str(p), voice, srate, pitch))
                pieces.append((p, sent))
            except Exception:
                continue
        if not pieces:
            asyncio.run(_tts(text, str(out_mp3), voice, rate))
            return
        # build concat with silence gaps
        concat_parts = []
        for pi, (p, sent) in enumerate(pieces):
            wav = td / f"s{pi:02d}.wav"
            subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-i", str(p),
                            "-ar", "44100", "-ac", "1", str(wav)], check=True)
            concat_parts.append(str(wav))
            if pi < len(pieces) - 1:
                gap = DRAMATIC_GAP if (sent.rstrip().endswith("?") or
                                       sent.rstrip().endswith("...")) else SENTENCE_GAP
                sil = td / f"gap{pi:02d}.wav"
                subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
                                "-i", f"anullsrc=r=44100:cl=mono",
                                "-t", f"{gap:.2f}", str(sil)], check=True)
                concat_parts.append(str(sil))
        listfile = td / "list.txt"
        listfile.write_text("".join(f"file '{c}'\n" for c in concat_parts))
        subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-f", "concat",
                        "-safe", "0", "-i", str(listfile),
                        "-c:a", "libmp3lame", "-q:a", "2", str(out_mp3)],
                       check=True)


def synth_segments(slug: str, script: dict) -> list[dict]:
    cfg = load_config()
    voice = cfg["video"]["voice"]
    rate = cfg["video"].get("voice_rate", "+0%")
    audio_dir = WORK_DIR / slug / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    meta = []
    for i, seg in enumerate(script["segments"]):
        mp3 = audio_dir / f"seg_{i:03d}.mp3"
        _synth_segment(seg["narration"], mp3, voice, rate)
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(mp3)]).decode().strip())
        meta.append({"index": i, "file": str(mp3), "duration": dur})

    (audio_dir / "segments.json").write_text(json.dumps(meta, indent=2),
                                             encoding="utf-8")
    return meta


def word_timestamps(slug: str, meta: list[dict]) -> list[list[dict]]:
    """Word-level timings per segment for karaoke captions (faster-whisper).
    base.en aligns word boundaries much better than tiny.en = tighter
    caption/voice sync."""
    from faster_whisper import WhisperModel
    model = WhisperModel("base.en", compute_type="int8")
    all_words = []
    for m in meta:
        words = []
        segments, _ = model.transcribe(m["file"], word_timestamps=True,
                                       beam_size=5)
        for s in segments:
            for w in s.words or []:
                words.append({"word": w.word.strip(), "start": float(w.start),
                              "end": float(w.end)})
        all_words.append(words)
    (WORK_DIR / slug / "audio" / "words.json").write_text(
        json.dumps(all_words), encoding="utf-8")
    return all_words
