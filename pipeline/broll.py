"""
STEP 5a — B-ROLL FETCHER
Pexels + Pixabay free APIs for copyright-safe video b-roll. Falls back
Pexels -> Pixabay -> generated gradient card so render never fails.
"""
import os, random

from .util import http, WORK_DIR


def _download(url: str, dest) -> bool:
    try:
        r = http().get(url, timeout=120, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        return dest.stat().st_size > 50_000
    except Exception:
        return False


def pexels_video(query: str, dest, portrait=False) -> bool:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return False
    try:
        r = http().get("https://api.pexels.com/videos/search",
                       params={"query": query, "per_page": 6,
                               "orientation": "portrait" if portrait else "landscape"},
                       headers={"Authorization": key}, timeout=30)
        vids = r.json().get("videos", [])
        random.shuffle(vids)
        for v in vids:
            files = sorted(v["video_files"], key=lambda f: abs((f.get("width") or 1280) - 1920))
            for f in files:
                if f["file_type"] == "video/mp4" and _download(f["link"], dest):
                    return True
    except Exception:
        pass
    return False


def pixabay_video(query: str, dest) -> bool:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return False
    try:
        r = http().get("https://pixabay.com/api/videos/",
                       params={"key": key, "q": query, "per_page": 6},
                       timeout=30)
        hits = r.json().get("hits", [])
        random.shuffle(hits)
        for h in hits:
            v = h["videos"].get("large") or h["videos"].get("medium")
            if v and _download(v["url"], dest):
                return True
    except Exception:
        pass
    return False


def fetch_broll(slug: str, query: str, index: int, portrait=False):
    """Returns local path to an mp4 or None (editor falls back to card)."""
    d = WORK_DIR / slug / "broll"
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"broll_{index:03d}.mp4"
    if dest.exists():
        return dest
    if pexels_video(query, dest, portrait) or pixabay_video(query, dest):
        return dest
    # simplified retry with first word only
    if pexels_video(query.split()[0], dest, portrait):
        return dest
    return None
