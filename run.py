#!/usr/bin/env python3
"""
ACTUALLY CHECKED — main orchestrator.
Usage:
  python run.py long            # research -> script -> render -> upload (long-form)
  python run.py short           # same, vertical Short
  python run.py long --dry-run  # everything except the actual upload
  python run.py analyze         # weekly analytics learning pass
"""
import json, sys, traceback

from pipeline.util import WORK_DIR
from pipeline.topic_engine import pick_topic
from pipeline.investigator import investigate
from pipeline.scriptwriter import write_script
from pipeline.voice import synth_segments, word_timestamps
from pipeline.editor import render
from pipeline.thumbnail import make_thumbnail
from pipeline.publisher import upload


def produce(kind: str, dry_run: bool = False):
    print(f"=== ACTUALLY CHECKED · producing {kind}-form video ===")

    print("[1/7] Picking topic from live search demand...")
    topic = pick_topic(kind)
    print(f"      → {topic['topic']}  (pillar: {topic['pillar']})")

    print("[2/7] Investigating (screenshots, reviews, domain checks)...")
    dossier = investigate(topic)
    print(f"      → verdict: {dossier['findings']['verdict']} "
          f"({len(dossier.get('screenshots', []))} screenshots, "
          f"{len(dossier['findings'].get('sources', []))} sources)")

    print("[3/7] Writing retention-engineered script...")
    script = write_script(dossier, kind)
    print(f"      → \"{script['title']}\" · {len(script['segments'])} segments")

    print("[4/7] Synthesizing narration (Edge-TTS)...")
    seg_meta = synth_segments(dossier["slug"], script)
    total = sum(m["duration"] for m in seg_meta)
    print(f"      → {total / 60:.1f} min of narration")

    print("[5/7] Word timestamps for captions (whisper)...")
    words = word_timestamps(dossier["slug"], seg_meta)

    print("[6/7] Rendering video (this is the slow part)...")
    video = render(dossier["slug"], script, seg_meta, words)
    thumb = make_thumbnail(dossier["slug"], script) if kind == "long" else None
    print(f"      → {video}")

    print("[7/7] Uploading + scheduling...")
    result = upload(dossier["slug"], script, seg_meta, str(video),
                    str(thumb) if thumb else None, dry_run=dry_run)

    if not dry_run:
        from pipeline.publisher import post_due_comments
        post_due_comments()   # post community comments on now-live videos
    print("=== DONE ===")
    return result


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "long"
    dry = "--dry-run" in sys.argv
    if cmd == "analyze":
        from pipeline.analyst import learn
        learn()
    elif cmd in ("long", "short"):
        try:
            produce(cmd, dry_run=dry)
        except Exception:
            traceback.print_exc()
            sys.exit(1)
    else:
        print(__doc__)
