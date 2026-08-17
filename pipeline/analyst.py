"""
STEP 8 — ANALYST (the learning loop)
Runs weekly: pulls per-video stats via YouTube Data API, computes what works
(pillar performance, title patterns, duration sweet spot), writes learnings
back to state so the topic engine & scriptwriter adapt over time.
"""
import json, statistics

from .util import load_state, save_state, gemini_json
from .publisher import yt_client


def collect_stats() -> list[dict]:
    uploads = load_state("uploads", [])
    if not uploads:
        return []
    yt = yt_client()
    rows = []
    ids = [u["video_id"] for u in uploads[-50:]]
    for i in range(0, len(ids), 50):
        resp = yt.videos().list(part="statistics,contentDetails",
                                id=",".join(ids[i:i + 50])).execute()
        for item in resp.get("items", []):
            st = item["statistics"]
            meta = next((u for u in uploads if u["video_id"] == item["id"]), {})
            rows.append({
                "video_id": item["id"],
                "title": meta.get("title", ""),
                "kind": meta.get("kind", ""),
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
                "duration": item["contentDetails"]["duration"],
            })
    save_state("video_stats", rows)
    return rows


def learn():
    rows = collect_stats()
    if len(rows) < 4:
        print("Not enough data yet to learn from.")
        return
    covered = load_state("covered_topics", [])
    pillar_of = {}
    for c in covered:
        pillar_of[c["topic"]] = c.get("pillar", "")

    med = statistics.median([r["views"] for r in rows]) or 1
    analysis = gemini_json(f"""You are the growth analyst for a YouTube research
channel. Median views: {med}. Video data:
{json.dumps(rows, indent=1)[:8000]}

Return JSON with actionable learnings:
{{"pillar_boost": {{"money": float, "scam": float, "viral": float}}  (1.0 = neutral,
   based on which topics overperform; infer pillar from titles),
 "title_patterns_that_work": [str],
 "title_patterns_to_avoid": [str],
 "notes": str}}""", temperature=0.3)
    save_state("learnings", analysis)
    print("📊 Learnings updated:", json.dumps(analysis.get("pillar_boost", {})))


if __name__ == "__main__":
    learn()
