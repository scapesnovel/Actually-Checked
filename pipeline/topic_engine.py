"""
STEP 1 — TOPIC ENGINE
Mines real search demand (Google & YouTube autocomplete, Reddit rising),
scores candidates by demand vs. competition vs. pillar weights (which the
analyst module adjusts over time), avoids repeats, picks today's topic.
All sources are free & keyless.
"""
import json, random, re, time
from urllib.parse import quote

from .util import http, load_config, load_state, save_state, gemini_json

SUBREDDITS = ["Scams", "beermoney", "passive_income", "personalfinance",
              "OutOfTheLoop", "IsItBullshit", "antiMLM", "WorkOnline",
              "sidehustle", "Frugal"]


def google_autocomplete(q: str) -> list[str]:
    s = http()
    try:
        r = s.get("https://suggestqueries.google.com/complete/search",
                  params={"client": "firefox", "q": q, "hl": "en"}, timeout=15)
        return r.json()[1]
    except Exception:
        return []


def youtube_autocomplete(q: str) -> list[str]:
    s = http()
    try:
        r = s.get("https://suggestqueries-clients6.youtube.com/complete/search",
                  params={"client": "youtube", "ds": "yt", "q": q, "hl": "en"},
                  timeout=15)
        txt = r.text
        m = re.search(r"\((.*)\)$", txt, re.S)
        data = json.loads(m.group(1)) if m else json.loads(txt)
        return [x[0] for x in data[1] if isinstance(x, list)]
    except Exception:
        return []


REDDIT_HOSTS = ["www.reddit.com", "old.reddit.com", "api.reddit.com"]


def reddit_rising() -> list[dict]:
    """Rising/hot questions from research subreddits. Reddit sometimes 403s
    datacenter IPs — we try several hosts and degrade gracefully; the
    autocomplete + HN sources carry the load if Reddit is unavailable."""
    import requests as rq
    out = []
    for sub in random.sample(SUBREDDITS, k=5):
        for host in REDDIT_HOSTS:
            try:
                r = rq.get(f"https://{host}/r/{sub}/hot.json?limit=25",
                           headers={"User-Agent":
                                    "actually-checked-research/1.0"},
                           timeout=15)
                if r.status_code != 200:
                    continue
                for post in r.json()["data"]["children"]:
                    d = post["data"]
                    if d.get("stickied"):
                        continue
                    out.append({"title": d["title"], "score": d["score"],
                                "num_comments": d["num_comments"],
                                "url": "https://reddit.com" + d["permalink"],
                                "subreddit": sub})
                time.sleep(1.2)
                break
            except Exception:
                continue
    return out


def hackernews_signals() -> list[dict]:
    """Free Algolia HN API — extra 'is this legit' discussion signal."""
    s = http()
    out = []
    for q in ["scam", "is it legit", "actually works"]:
        try:
            r = s.get("https://hn.algolia.com/api/v1/search_by_date",
                      params={"query": q, "tags": "story",
                              "numericFilters": "points>20"}, timeout=15)
            for h in r.json().get("hits", [])[:10]:
                out.append({"title": h.get("title", ""),
                            "score": h.get("points", 0),
                            "num_comments": h.get("num_comments", 0),
                            "url": f"https://news.ycombinator.com/item?id={h['objectID']}",
                            "subreddit": "hackernews"})
        except Exception:
            continue
    return out


def expand_seeds(cfg: dict) -> list[dict]:
    """Turn pillar seed patterns into live autocomplete candidates."""
    letters = list("abcdefghijklmnopqrstuvwxyz")
    candidates = []
    for pillar in cfg["pillars"]:
        for seed in pillar["seed_queries"]:
            base = seed.replace("*", random.choice(letters)) if "*" in seed else seed
            for fn in (google_autocomplete, youtube_autocomplete):
                for sugg in fn(base):
                    if len(sugg.split()) >= 3:
                        candidates.append({"query": sugg, "pillar": pillar["id"]})
            time.sleep(0.8)
    # also mine "is ... legit/scam" evergreen roots directly
    for root in ["is it legit", "is it a scam", "does it really work"]:
        for sugg in youtube_autocomplete(root):
            candidates.append({"query": sugg, "pillar": "scam"})
    return candidates


def competition_estimate(q: str) -> int:
    """Cheap proxy: count of autocomplete refinements (more = more supply)."""
    return len(youtube_autocomplete(q))


def pick_topic(kind: str = "long") -> dict:
    cfg = load_config()
    covered = load_state("covered_topics", [])
    learnings = load_state("learnings", {"pillar_boost": {}})
    covered_set = {c["slug_root"] for c in covered}

    candidates = expand_seeds(cfg)
    reddit = reddit_rising() + hackernews_signals()

    # de-dupe + drop covered
    seen, filtered = set(), []
    for c in candidates:
        key = re.sub(r"\W+", "", c["query"].lower())[:40]
        root = " ".join(c["query"].lower().split()[:4])
        if key in seen or any(root.startswith(cs) for cs in covered_set):
            continue
        seen.add(key)
        filtered.append(c)

    random.shuffle(filtered)
    shortlist = filtered[:40]

    # LLM ranks the shortlist using demand signals + reddit context
    boost = learnings.get("pillar_boost", {})
    prompt = f"""You pick topics for "Actually Checked", a faceless YouTube research
channel (casual smart-friend tone). Pillars: money methods checked, apps/sites
legit-or-scam, viral claims debunked. We do ONLINE research only (no physical
product testing) — websites, apps, money methods, viral claims.

Live autocomplete candidates (real search demand):
{json.dumps(shortlist, indent=1)}

Hot Reddit threads right now (real user pain):
{json.dumps([{k: r[k] for k in ('title', 'subreddit', 'score')} for r in reddit[:30]], indent=1)}

Performance boosts learned from our analytics (higher = our audience likes it):
{json.dumps(boost)}

Pick the SINGLE best topic for a {'8-12 min deep investigation' if kind == 'long' else '35-second quick-verdict Short'}.
Rules: must be answerable with online research + screenshots; searchable phrasing;
specific named subject (an app, site, method, or claim) beats generic; avoid
medical/tragedy/violence topics (ad-safety); avoid anything we covered: {sorted(covered_set)[:50]}

Return JSON: {{"topic": str  (the exact question, e.g. "Is CashKarma legit?"),
"subject": str (the named app/site/method/claim),
"pillar": "money"|"scam"|"viral",
"search_query": str (what people type),
"why": str,
"reddit_urls": [up to 3 relevant reddit thread URLs from the list, else []]}}"""
    choice = gemini_json(prompt, temperature=0.7)

    # attach matching reddit URLs if the model didn't
    if not choice.get("reddit_urls"):
        subj = choice["subject"].lower()
        choice["reddit_urls"] = [r["url"] for r in reddit
                                 if subj.split()[0] in r["title"].lower()][:3]

    # persist coverage
    covered.append({"slug_root": " ".join(choice["topic"].lower().split()[:4]),
                    "topic": choice["topic"], "kind": kind,
                    "ts": int(time.time())})
    save_state("covered_topics", covered[-500:])
    return choice


if __name__ == "__main__":
    import sys
    print(json.dumps(pick_topic(sys.argv[1] if len(sys.argv) > 1 else "long"),
                     indent=2))
