# 🔎 Actually Checked — Autonomous YouTube Research Channel

> "You asked. We checked. Here's the proof."

A fully automated, zero-cost pipeline that researches real questions people
search for (money methods, scam checks, viral claims), investigates them with
a headless browser (real screenshots, real user reports, domain checks),
writes retention-engineered scripts, renders professional videos with
word-synced captions and music ducking, and uploads them to YouTube on a
peak-time schedule — long-form + daily Shorts.

## Project Overview
- **Name**: Actually Checked bot
- **Goal**: Grow a monetizable faceless research channel on 100% free tools
- **Pillars**: 💰 money methods checked · 📱 apps/sites legit-or-scam · 🔥 viral claims debunked

## How it works
```
GitHub Actions (cron)
 1. topic_engine   → mines Google/YouTube autocomplete + Reddit/HN (live demand)
 2. investigator   → Playwright screenshots, DDG results, Reddit evidence, RDAP domain age
 3. scriptwriter   → Gemini: hook → open loops → proof → verdict (casual smart-friend voice)
 4. voice          → Edge-TTS neural narration (free, natural)
 5. editor         → FFmpeg: Ken-Burns, zoom-punch proof shots, karaoke captions,
                     transitions, music auto-ducking, branded cards
 6. thumbnail      → Pillow: high-CTR investigative style w/ real screenshot
 7. publisher      → YouTube API: SEO metadata, source links, chapters, peak-time scheduling
 8. analyst        → weekly: learns which pillars/titles perform → adapts topic picking
```

## Schedule (all automatic)
| What | When (produce) | Publishes at |
|---|---|---|
| Long-form (8–12 min) | Mon/Wed/Fri/Sat 06:00 UTC | Tue/Thu/Sat/Sun 14:00 ET |
| Short (30–50 s) | daily 08:30 UTC | daily 17:00 ET |
| Analytics learning | Mondays 04:00 UTC | — |

## Repo layout
```
run.py                  # orchestrator: python run.py long|short|analyze [--dry-run]
pipeline/               # the 8 modules above
config/channel.yml      # identity, pillars, schedule, safety rails, SEO
scripts/get_refresh_token.py  # one-time OAuth helper (run on your PC)
scripts/fetch_assets.sh # fonts + music fetch (CI)
.github/workflows/      # longform.yml, shorts.yml, analyst.yml
state/                  # bot memory: covered topics, uploads, learnings (committed)
docs/HUMAN_SETUP.md     # ← YOUR checklist (accounts, API keys, secrets)
```

## Setup
See **docs/HUMAN_SETUP.md** — ~45 min once, then the system runs itself.
Required GitHub secrets: `GEMINI_API_KEY, PEXELS_API_KEY, PIXABAY_API_KEY,
YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN`.

## Monetization-safety design
- Original research + real screenshots + cited sources = transformative
  content (passes YPP "repetitious/reused content" review)
- Cautious evidence language enforced ("red flags we found", never
  accusations-as-fact) — defamation-safe
- Ad-safe topic filter (no medical/tragedy/violence), banned words stripped
  from titles, education category, sources in every description
- Sustainable volume: 4 long + 7 shorts/week (never spam)

## Data & state
- **Storage**: JSON files in `state/`, committed back by CI (the bot's memory)
- **Artifacts**: every produced video kept 7 days in Actions artifacts for review

## Status
- **Tech stack**: Python · GitHub Actions · Gemini (free) · Edge-TTS ·
  faster-whisper · FFmpeg · Playwright · Pexels/Pixabay · YouTube Data API v3
- **Cost**: $0
- **Pipeline verified**: topic sources ✅ · investigation ✅ · TTS ✅ ·
  captions ✅ · render ✅ · thumbnail ✅ (sandbox smoke tests)
- **Last updated**: 2026-08-15
