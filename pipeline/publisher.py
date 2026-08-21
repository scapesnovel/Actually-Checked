"""
STEP 7 — PUBLISHER
Uploads via YouTube Data API v3 with SEO metadata, source links, chapters,
and schedules publish for the configured peak slot. Uses a long-lived OAuth
refresh token stored as a GitHub secret (see scripts/get_refresh_token.py).
"""
import datetime as dt
import json, os

from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .util import WORK_DIR, load_config, load_state, save_state

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/youtube.force-ssl"]


def yt_client():
    # NOTE: scopes=None on refresh — Google rejects the refresh with
    # 'invalid_scope' if we assert scopes the token wasn't granted.
    # The token keeps whatever scopes the user consented to (upload is
    # all we need to publish); asserting nothing = always refreshable.
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token")
    creds.refresh(Request())
    # FAIL FAST with a clear message if the token can't upload — much
    # better than rendering for 25 minutes and dying on the last step.
    granted = set(getattr(creds, "granted_scopes", None) or
                  getattr(creds, "scopes", None) or [])
    print(f"      YouTube token scopes: {sorted(granted) or '(unknown)'}")
    need = {"https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtube.force-ssl"}
    if granted and not (granted & need):
        raise SystemExit(
            "\nERROR: The YouTube refresh token has NO upload permission.\n"
            f"Granted scopes: {sorted(granted)}\n\n"
            "FIX (2 minutes, on your computer):\n"
            "  1) python scripts/get_refresh_token.py\n"
            "  2) On the Google consent screen, CHECK ALL the permission "
            "boxes\n     (especially 'Manage your YouTube videos' / upload)\n"
            "  3) Update the YT_REFRESH_TOKEN secret in GitHub repo "
            "Settings ->\n     Secrets and variables -> Actions\n")
    return build("youtube", "v3", credentials=creds)


def next_publish_time(kind: str) -> str:
    """Next configured slot in ET, returned as RFC3339 UTC."""
    cfg = load_config()["schedule"]
    et = ZoneInfo("America/New_York")
    now = dt.datetime.now(et)
    hour = (cfg["longform_publish_hour_et"] if kind == "long"
            else cfg["shorts_publish_hour_et"])
    days = cfg["longform_days"] if kind == "long" else \
        ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    names = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    for delta in range(0, 8):
        cand = (now + dt.timedelta(days=delta)).replace(
            hour=hour, minute=0, second=0, microsecond=0)
        if cand <= now:
            continue
        if names[cand.weekday()] in days:
            return cand.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (now + dt.timedelta(days=1)).astimezone(
        dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_description(slug: str, script: dict, seg_meta: list[dict]) -> str:
    cfg = load_config()
    dossier = json.loads((WORK_DIR / slug / "dossier.json").read_text(encoding="utf-8"))
    # GUARANTEED links first (the ones actually SHOWN in the video), then
    # whatever else the distill model cited. Viewers must always find the
    # site being talked about + the review pages we screenshotted.
    sources = []

    def _add(u):
        if not (u and u.startswith("http")):
            return
        u = u.replace("old.reddit.com", "www.reddit.com").rstrip("/")
        if u not in sources:
            sources.append(u)

    _add(dossier.get("official_site"))                       # the subject
    _add((dossier.get("trustpilot_rating") or {}).get("page"))  # trustpilot
    for r in dossier.get("reddit_evidence", []):             # reddit threads
        _add(r.get("url"))
    for u in dossier.get("topic", {}).get("reddit_urls", []) or []:
        _add(u)
    for u in dossier.get("findings", {}).get("sources", []) or []:
        _add(u)                                              # distill extras
    src_txt = "\n".join(f"• {u}" for u in sources[:12]) or "• Research compiled from public sources"

    # chapters from segment timings (long-form only)
    chapters = ""
    if script["kind"] == "long":
        t = 0.0
        marks = ["00:00 The question"]
        for i, m in enumerate(seg_meta[1:], start=1):
            t += seg_meta[i - 1]["duration"] + 0.18
            seg = script["segments"][i]
            label = (seg.get("onscreen_text") or
                     seg["narration"].split(".")[0][:40])
            if i % 2 == 1:  # every other segment = clean chapter list
                marks.append(f"{int(t // 60):02d}:{int(t % 60):02d} {label}")
        chapters = "\n".join(marks[:10])

    desc = script["description"]
    desc = desc.replace("{SOURCES}", src_txt).replace("{CHAPTERS}", chapters)
    footer = cfg["seo"]["description_footer"].replace(
        "{disclaimer}", cfg["safety"]["disclaimer"].strip())
    return (desc + "\n\n" + footer)[:4900]


def upload(slug: str, script: dict, seg_meta: list[dict],
           video_path: str, thumb_path: str | None, dry_run=False) -> dict:
    cfg = load_config()
    kind = script["kind"]
    title = script["title"][:100]
    if kind == "short" and "#shorts" not in title.lower():
        title = title[:91] + " #Shorts"
    for bad in cfg["safety"]["banned_words_in_title"]:
        title = title.replace(bad, "").replace(bad.title(), "")

    body = {
        "snippet": {
            "title": title,
            "description": build_description(slug, script, seg_meta),
            "tags": (script.get("tags", []) + cfg["seo"]["tags_base"])[:30],
            "categoryId": "27",  # Education
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": next_publish_time(kind),
            "selfDeclaredMadeForKids": False,
        },
    }
    if dry_run:
        print(json.dumps(body, indent=2))
        return {"dry_run": True, "body": body}

    yt = yt_client()
    media = MediaFileUpload(video_path, chunksize=8 * 1024 * 1024,
                            resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]

    if thumb_path and kind == "long":
        try:
            yt.thumbnails().set(videoId=vid,
                                media_body=MediaFileUpload(thumb_path)).execute()
        except Exception as e:  # thumbnail perms need phone verification
            print(f"[warn] thumbnail set failed: {e}")

    uploads = load_state("uploads", [])
    uploads.append({"video_id": vid, "title": title, "kind": kind,
                    "slug": slug, "publish_at": body["status"]["publishAt"]})
    save_state("uploads", uploads[-300:])

    # queue the community comment — posted automatically once video is live
    if script.get("pinned_comment"):
        pending = load_state("pending_comments", [])
        pending.append({"video_id": vid,
                        "publish_at": body["status"]["publishAt"],
                        "text": script["pinned_comment"][:900]})
        save_state("pending_comments", pending)
    print(f"✅ Uploaded {kind}: https://youtu.be/{vid} (publishes {body['status']['publishAt']})")
    return {"video_id": vid, "publish_at": body["status"]["publishAt"]}


def post_due_comments():
    """Post queued community comments on videos that have gone live.
    (Comments can't be added while a scheduled video is still private.)
    Runs on every daily pipeline pass. Pinning is one manual click — the
    API can't pin — but an owner comment shows prominently regardless."""
    pending = load_state("pending_comments", [])
    if not pending:
        return
    now = dt.datetime.now(dt.timezone.utc)
    yt = yt_client()
    remaining = []
    for p in pending:
        due = dt.datetime.strptime(p["publish_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
        if due > now:
            remaining.append(p)
            continue
        try:
            yt.commentThreads().insert(part="snippet", body={"snippet": {
                "videoId": p["video_id"],
                "topLevelComment": {"snippet": {"textOriginal": p["text"]}}
            }}).execute()
            print(f"💬 Comment posted on {p['video_id']}")
        except Exception as e:
            print(f"[warn] comment on {p['video_id']} failed: {e}")
            if "disabled" not in str(e).lower():
                remaining.append(p)  # retry next run unless comments disabled
    save_state("pending_comments", remaining)
