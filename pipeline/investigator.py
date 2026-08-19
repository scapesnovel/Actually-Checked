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


def trustpilot_rating(subject: str, site: str | None) -> dict | None:
    """Best-effort Trustpilot TrustScore + review count + star distribution.
    Numbers like '2.3 TrustScore, 61% 1-star' are GOLD for the script."""
    s = http()
    hosts = []
    if site:
        hosts.append(urlparse(site).netloc.replace("www.", ""))
    hosts.append(re.sub(r"[^a-z0-9]", "", subject.lower()) + ".com")
    for host in hosts:
        try:
            r = s.get(f"https://www.trustpilot.com/review/{host}", timeout=20,
                      headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if r.status_code != 200:
                continue
            out = {"page": f"https://www.trustpilot.com/review/{host}"}
            m = re.search(r'"aggregateRating"[^}]*"ratingValue"\s*:\s*"?([\d.]+)', r.text)
            if m:
                out["trust_score"] = float(m.group(1))
            m = re.search(r'"reviewCount"\s*:\s*"?(\d+)', r.text)
            if m:
                out["review_count"] = int(m.group(1))
            # star distribution percentages (5-star .. 1-star)
            dist = re.findall(r'(\d+)%</p>', r.text)[:5]
            if len(dist) == 5:
                out["distribution_pct"] = {"5_star": int(dist[0]),
                                           "4_star": int(dist[1]),
                                           "3_star": int(dist[2]),
                                           "2_star": int(dist[3]),
                                           "1_star": int(dist[4])}
            if "trust_score" in out:
                return out
        except Exception:
            continue
    return None


def reddit_search(subject: str, n: int = 6) -> list[dict]:
    """Free Reddit search JSON — finds threads we didn't already know about."""
    try:
        r = http().get("https://www.reddit.com/search.json",
                       params={"q": f'"{subject}" (scam OR legit OR review OR payout)',
                               "sort": "relevance", "limit": n, "t": "year"},
                       timeout=20)
        out = []
        for c in r.json().get("data", {}).get("children", []):
            d = c.get("data", {})
            out.append({"title": d.get("title", ""),
                        "subreddit": d.get("subreddit", ""),
                        "score": d.get("score", 0),
                        "num_comments": d.get("num_comments", 0),
                        "url": "https://www.reddit.com" + d.get("permalink", ""),
                        "selftext": (d.get("selftext") or "")[:300]})
        return out
    except Exception:
        return []


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
                     reddit_urls: list | None = None,
                     trustpilot_url: str | None = None) -> list[dict]:
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
                    trustpilot_url or
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
        # NARROW viewport + 2x scale = big readable text when the shot is
        # scaled into the video (mobile-legibility fix)
        page = browser.new_page(viewport={"width": 880, "height": 900},
                                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                            "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"),
                                device_scale_factor=2)
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
                    if im.height > 7000:
                        im.crop((0, 0, im.width, 7000)).save(path)
                except Exception:
                    page.screenshot(path=str(path), full_page=False)
                shots.append({"name": name, "url": url, "path": str(path),
                              "source": badge, "scrollable": scrollable})
            except Exception:
                continue
        browser.close()
    return shots


def read_screenshots(shots: list[dict], subject: str) -> list[dict]:
    """The bot READS every screenshot before it's allowed in a video.
    For each shot Gemini vision returns:
      - usable: is this actually showing content about the subject?
        (drops cookie walls, captchas, 404s, empty search pages)
      - summary: what the page ACTUALLY shows (scriptwriter must match this)
      - highlights: the juiciest regions (a review, a rating, a claim)
        with normalized y-coords so the editor can crop + pop them."""
    from .util import gemini_vision_json
    from PIL import Image as _Im
    checked = []
    for s in shots:
        try:
            im = _Im.open(s["path"])
            iw, ih = im.size
            info = gemini_vision_json(f"""You are QC for a fact-check video about "{subject}".
Read this screenshot of {s.get('url','a page')} (source: {s.get('source')}).
The image is {iw}x{ih}px, top of page at y=0.

Return JSON:
{{"usable": true|false (false if it's a cookie wall, captcha, error page,
    empty/no-results page, or shows nothing about {subject}),
 "summary": str (2-3 sentences: what the page ACTUALLY shows — visible
    ratings, star scores, review counts, claims, headlines. Only what is
    truly visible, never invented),
 "visible_rating": str|null (e.g. "2.9/5 from 11,203 reviews" if visible),
 "highlights": [up to 4 of the most quotable regions — a single user review,
    a rating block, a marketing claim. STRICT: every highlight MUST contain
    real readable sentence(s) or a rating number. NEVER highlight search
    boxes, nav bars, buttons, empty space, footers, or link lists — if the
    page has no meaningful quotable region, return an empty list. Each:
    {{"kind": "review"|"rating"|"claim"|"headline",
      "text": str (the visible text, verbatim, <=220 chars),
      "y_top_pct": float (0-100, top of the region as % of image height),
      "y_bottom_pct": float (0-100, bottom of region; keep the region
         TIGHT around the text block, 5-20% tall typically)}}]
}}""", s["path"])
            s["usable"] = bool(info.get("usable"))
            s["reads"] = info.get("summary", "")
            s["visible_rating"] = info.get("visible_rating")
            hl = []
            for h in (info.get("highlights") or [])[:4]:
                try:
                    yt = max(0.0, min(99.0, float(h["y_top_pct"])))
                    yb = max(yt + 2.0, min(100.0, float(h["y_bottom_pct"])))
                    hl.append({"kind": h.get("kind", "review"),
                               "text": (h.get("text") or "")[:220],
                               "y_top_pct": yt, "y_bottom_pct": yb})
                except Exception:
                    continue
            s["highlights"] = hl
        except Exception:
            # vision unavailable -> keep the shot but mark unverified
            s["usable"] = True
            s["reads"] = ""
            s["highlights"] = []
        if s["usable"]:
            checked.append(s)
        time.sleep(1.0)
    return checked


def investigate(topic: dict) -> dict:
    """Full investigation dossier for the scriptwriter."""
    subject = topic["subject"]
    slug = slugify(topic["topic"])
    site = find_official_site(subject)

    # merge discovered reddit threads into the evidence pool
    found_reddit = [t["url"] for t in reddit_search(subject)[:2]]
    reddit_urls = list(dict.fromkeys(
        (topic.get("reddit_urls") or []) + found_reddit))
    topic["reddit_urls"] = reddit_urls

    dossier = {
        "topic": topic,
        "slug": slug,
        "official_site": site,
        "domain_info": domain_age(site) if site else None,
        "search_results": ddg_results(f'{subject} review scam complaints'),
        "search_results_2": ddg_results(f'{subject} payment proof OR "does it work"'),
        "search_results_trustpilot": ddg_results(f'{subject} site:trustpilot.com'),
        "search_results_bbb": ddg_results(f'{subject} site:bbb.org OR site:sitejabber.com'),
        "search_results_appstores": ddg_results(
            f'{subject} site:play.google.com OR site:apps.apple.com'),
        "search_results_social": ddg_results(
            f'{subject} scam OR legit site:twitter.com OR site:x.com'),
        "trustpilot_rating": (tp := trustpilot_rating(subject, site)),
        "reddit_search": reddit_search(subject),
        "reddit_evidence": reddit_thread_evidence(topic.get("reddit_urls", [])),
        "screenshots": read_screenshots(
            screenshot_pages(subject, site, slug,
                             topic.get("reddit_urls", []),
                             (tp or {}).get("page")), subject),
        "collected_at": time.strftime("%Y-%m-%d"),
    }

    # LLM distills a verdict + key evidence points (grounded, cautious language)
    distill = gemini_json(f"""You are the research analyst for "Actually Checked".
Analyze this raw dossier and produce grounded findings. NEVER invent facts —
only use what's in the dossier. Use cautious evidence language ("red flags we
found", "users report", "we couldn't verify") — never state accusations as fact.

DOSSIER:
{json.dumps({k: v for k, v in dossier.items() if k != 'screenshots'}, indent=1)[:12000]}

WHAT OUR SCREENSHOTS ACTUALLY SHOW (verified by reading them — these are the
visuals the video will display, so findings MUST be consistent with them):
{json.dumps([{'name': s['name'], 'source': s.get('source'),
              'shows': s.get('reads'), 'visible_rating': s.get('visible_rating'),
              'quotable': [h['text'] for h in s.get('highlights', [])]}
             for s in dossier['screenshots']], indent=1)[:6000]}

Return JSON:
{{"verdict": "legit"|"scam_likely"|"mixed"|"works"|"doesnt_work"|"unverified",
 "confidence": "high"|"medium"|"low",
 "what_it_claims": str (1-2 sentences: what the app/site promises users,
    from its own marketing — the video opens with this),
 "rating_stats": str|null (concrete numbers if present in the dossier, e.g.
    "Trustpilot TrustScore 2.3 from 1,204 reviews — 58% are 1-star". Only
    real numbers from the dossier, never invented),
 "key_findings": [6-10 specific evidence-backed bullet points, each naming
    its source (Trustpilot / Reddit r/sub / web search / official site / BBB)],
 "red_flags": [list],
 "green_flags": [list],
 "best_user_quotes": [up to 5 short REAL quotes from reddit/review evidence,
    each with where it came from — the narrator reads these on camera],
 "risk_assessment": str (2-3 sentences: what a user actually risks by trying
    this — time, money, personal data — grounded in the evidence),
 "way_forward": str (2-3 sentences of practical advice: what to do/check
    before trying, e.g. start small, never pay upfront, read recent reviews),
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
