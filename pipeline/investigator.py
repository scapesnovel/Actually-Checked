"""
STEP 2 — INVESTIGATOR
The originality engine. Actually visits the subject's website with a headless
browser, takes real screenshots (our visual proof), pulls real user reviews
(Reddit, Trustpilot search), checks domain age via RDAP, and Google results.
Everything gets cited in the video description = transformative content.
"""
import datetime as dt
import json, re, time
from urllib.parse import quote_plus, urlparse

from .util import http, WORK_DIR, gemini_json, slugify


def _shots_dir(topic_slug: str):
    d = WORK_DIR / topic_slug / "shots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_official_site(subject: str) -> str | None:
    """DuckDuckGo HTML search (keyless) to locate the subject's site."""
    s = http()
    try:
        r = s.get("https://html.duckduckgo.com/html/",
                  params={"q": subject + " official site"}, timeout=20)
        links = re.findall(r'href="(https?://[^"]+)"', r.text)
        for url in links:
            host = urlparse(url).netloc.lower()
            if any(b in host for b in ("duckduckgo", "wikipedia", "youtube",
                                       "reddit", "facebook", "twitter")):
                continue
            return url.split("&")[0]
    except Exception:
        pass
    return None


def ddg_results(query: str, n: int = 8) -> list[dict]:
    s = http()
    out = []
    try:
        r = s.get("https://html.duckduckgo.com/html/", params={"q": query},
                  timeout=20)
        blocks = re.findall(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</a>', r.text, re.S)
        for url, title, snip in blocks[:n]:
            clean = lambda t: re.sub(r"<[^>]+>", "", t).strip()
            out.append({"url": url, "title": clean(title),
                        "snippet": clean(snip)})
    except Exception:
        pass
    return out


def reddit_thread_evidence(urls: list[str]) -> list[dict]:
    """Pull top comments from relevant reddit threads (real user experiences)."""
    s = http()
    evidence = []
    for u in urls[:3]:
        try:
            r = s.get(u.rstrip("/") + ".json?limit=15", timeout=20)
            data = r.json()
            post = data[0]["data"]["children"][0]["data"]
            comments = []
            for c in data[1]["data"]["children"]:
                cd = c.get("data", {})
                body = cd.get("body", "")
                if body and len(body) > 40 and cd.get("score", 0) >= 3:
                    comments.append({"text": body[:400], "score": cd["score"]})
            evidence.append({"url": u, "title": post["title"],
                             "selftext": post.get("selftext", "")[:500],
                             "top_comments": comments[:5]})
            time.sleep(1.5)
        except Exception:
            continue
    return evidence


def domain_age(url: str) -> dict | None:
    """RDAP (free, official) — young domains are a classic scam red flag."""
    try:
        host = urlparse(url).netloc.replace("www.", "")
        r = http().get(f"https://rdap.org/domain/{host}", timeout=20)
        if r.status_code != 200:
            return None
        events = {e["eventAction"]: e["eventDate"] for e in r.json().get("events", [])}
        reg = events.get("registration")
        if reg:
            age_days = (dt.datetime.now(dt.timezone.utc) -
                        dt.datetime.fromisoformat(reg.replace("Z", "+00:00"))).days
            return {"domain": host, "registered": reg[:10],
                    "age_days": age_days,
                    "red_flag_young": age_days < 365}
    except Exception:
        pass
    return None


def screenshot_pages(subject: str, site: str | None, topic_slug: str,
                     reddit_urls: list | None = None) -> list[dict]:
    """Playwright headless screenshots — the visual proof used in the video.
    Captures TALL (multi-viewport) screenshots so the editor can slowly
    SCROLL through them on screen (reviews, comments, search results).
    Each shot carries a `source` label shown as an on-screen badge."""
    shots = []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return shots
    targets = []  # (name, url, source_badge, scrollable)
    if site:
        host = urlparse(site).netloc.replace("www.", "").upper()
        targets.append(("official_site", site, host, True))
    targets.append(("trustpilot",
                    f"https://www.trustpilot.com/search?query={quote_plus(subject)}",
                    "TRUSTPILOT.COM", True))
    targets.append(("search_results",
                    f"https://www.bing.com/search?q={quote_plus(subject + ' reviews scam')}",
                    "WEB SEARCH", True))
    # real Reddit threads = the strongest trust evidence (user comments)
    for j, rurl in enumerate((reddit_urls or [])[:2]):
        old = rurl.replace("www.reddit.com", "old.reddit.com")
        targets.append((f"reddit_{j}", old, "REDDIT", True))
    d = _shots_dir(topic_slug)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 900},
                                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                            "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"))
        for name, url, badge, scrollable in targets:
            try:
                page.goto(url, timeout=35000, wait_until="domcontentloaded")
                page.wait_for_timeout(3500)
                # nudge lazy content to load before the tall capture
                for _ in range(3):
                    page.mouse.wheel(0, 900)
                    page.wait_for_timeout(600)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(400)
                path = d / f"{name}.png"
                try:  # tall capture (capped ~4 viewports) for the scroll effect
                    page.screenshot(path=str(path), full_page=True)
                    from PIL import Image as _Im
                    im = _Im.open(path)
                    if im.height > 3600:
                        im.crop((0, 0, im.width, 3600)).save(path)
                except Exception:
                    page.screenshot(path=str(path), full_page=False)
                shots.append({"name": name, "url": url, "path": str(path),
                              "source": badge, "scrollable": scrollable})
            except Exception:
                continue
        browser.close()
    return shots


def investigate(topic: dict) -> dict:
    """Full investigation dossier for the scriptwriter."""
    subject = topic["subject"]
    slug = slugify(topic["topic"])
    site = find_official_site(subject)

    dossier = {
        "topic": topic,
        "slug": slug,
        "official_site": site,
        "domain_info": domain_age(site) if site else None,
        "search_results": ddg_results(f'{subject} review scam complaints'),
        "search_results_2": ddg_results(f'{subject} payment proof OR "does it work"'),
        "search_results_trustpilot": ddg_results(f'{subject} site:trustpilot.com'),
        "search_results_bbb": ddg_results(f'{subject} site:bbb.org OR site:sitejabber.com'),
        "reddit_evidence": reddit_thread_evidence(topic.get("reddit_urls", [])),
        "screenshots": screenshot_pages(subject, site, slug,
                                        topic.get("reddit_urls", [])),
        "collected_at": time.strftime("%Y-%m-%d"),
    }

    # LLM distills a verdict + key evidence points (grounded, cautious language)
    distill = gemini_json(f"""You are the research analyst for "Actually Checked".
Analyze this raw dossier and produce grounded findings. NEVER invent facts —
only use what's in the dossier. Use cautious evidence language ("red flags we
found", "users report", "we couldn't verify") — never state accusations as fact.

DOSSIER:
{json.dumps({k: v for k, v in dossier.items() if k != 'screenshots'}, indent=1)[:14000]}

Return JSON:
{{"verdict": "legit"|"scam_likely"|"mixed"|"works"|"doesnt_work"|"unverified",
 "confidence": "high"|"medium"|"low",
 "key_findings": [5-8 specific evidence-backed bullet points, each mentioning its source],
 "red_flags": [list],
 "green_flags": [list],
 "best_user_quotes": [up to 3 short real quotes from reddit evidence with sub name],
 "sources": [list of the URLs actually used]}}""", temperature=0.4)
    dossier["findings"] = distill
    (WORK_DIR / slug).mkdir(parents=True, exist_ok=True)
    (WORK_DIR / slug / "dossier.json").write_text(
        json.dumps(dossier, indent=2, ensure_ascii=False), encoding="utf-8")
    return dossier


if __name__ == "__main__":
    import sys
    t = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {
        "topic": sys.argv[1], "subject": sys.argv[2], "pillar": "scam",
        "search_query": sys.argv[1], "reddit_urls": []}
    print(json.dumps(investigate(t)["findings"], indent=2))
