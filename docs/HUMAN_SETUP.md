# 🙋 YOUR SETUP CHECKLIST (the only human work required)

Total time: ~45 minutes, once. Everything is free.

---

## STEP 1 — Create the YouTube channel (10 min)
1. Create a fresh Google account (recommended: dedicated to this channel).
2. Go to youtube.com → profile icon → **Create a channel**.
3. Name: **Actually Checked** · Handle: **@ActuallyChecked** (or nearest available:
   @ActuallyCheckedHQ, @WeActuallyChecked).
4. YouTube Studio → Settings → Channel → **Feature eligibility** →
   verify phone number (unlocks custom thumbnails — REQUIRED).
5. Channel description (paste):
   > You asked. We checked. Here's the proof. 🔎
   > We investigate money-making methods, suspicious apps & sites, and viral
   > claims — with real screenshots, real user reports, and sources for
   > everything in the description. New checks every week.
6. Upload the branding files — **already generated, in `assets/branding/`**:
   - `logo_800x800.png` → YouTube Studio → Customization → Branding → **Picture**
   - `banner_2048x1152.png` → same page → **Banner image**
   - `watermark_150x150.png` → same page → **Video watermark** → display: *Entire video*

## STEP 2 — Google Cloud + YouTube API (20 min) — PRODUCTION MODE
1. console.cloud.google.com (same Google account) → **New Project** → name: `actually-checked`.
2. **APIs & Services → Library** → search "YouTube Data API v3" → **Enable**.
3. **OAuth consent screen** → External → fill app name (`actually-checked`),
   your email as support + developer contact → add scopes
   `.../auth/youtube.upload`, `.../auth/youtube` and `.../auth/youtube.force-ssl`
   (the last one lets the bot post the community comment) → save.
4. **PUBLISH THE APP** (critical — avoids the 7-day token expiry of Testing
   mode): OAuth consent screen page → Publishing status → **Publish app** →
   Confirm. It will say "needs verification" — **ignore that**; verification
   is only required to remove the warning screen for OTHER users. You are the
   only user. Tokens from a published (production) app do NOT expire.
5. **Credentials → Create credentials → OAuth client ID** → type **Desktop app**
   → Download JSON → save as `client_secret.json`.
6. On your computer:
   ```
   pip install google-auth-oauthlib
   python scripts/get_refresh_token.py
   ```
   Browser opens → log in with the CHANNEL account → you'll see
   **"Google hasn't verified this app"** → click **Advanced** →
   **"Go to actually-checked (unsafe)"** → Continue → allow all permissions.
   (This warning is normal for personal apps — it's YOUR app.)
   Copy the 3 printed values for Step 5.

## STEP 2b — YouTube API audit form (5 min now, unlocks full publishing)
YouTube locks videos uploaded by **unaudited** API projects to *private*.
Until the audit passes, the bot's uploads sit as private/scheduled but may
not go public. The audit is free and routine — submit it on day 1:
1. Go to: https://support.google.com/youtube/contact/yt_api_form
2. Fill in: your API project number (Cloud console → Dashboard), channel URL,
   and describe usage honestly, e.g.:
   > "Personal automation that uploads my own original research/commentary
   > videos to my own channel on a schedule, sets titles/descriptions/
   > thumbnails, and posts one pinned-style comment per video. Single user
   > (me), no third parties, ~1-5 uploads/day."
3. Approval usually takes ~1–2 weeks. **You can start producing immediately**
   — worst case early videos stay private until approval, then you flip them
   public in Studio in one batch (or the bot's publishAt kicks in for new ones).
4. Meanwhile the default quota (10,000 units/day) covers ~6 uploads/day —
   more than the schedule needs. No quota extension required.

## STEP 3 — Gemini API key (2 min)
1. aistudio.google.com → **Get API key** → Create API key. Copy it.

## STEP 4 — Stock footage keys (5 min)
1. pexels.com/api → sign up → copy API key.
2. pixabay.com/api/docs → sign up → copy API key.

## STEP 5 — GitHub secrets (5 min)
Repo → **Settings → Secrets and variables → Actions → New repository secret**.
Add all six:

| Secret name | Value |
|---|---|
| `GEMINI_API_KEY` | from Step 3 |
| `PEXELS_API_KEY` | from Step 4 |
| `PIXABAY_API_KEY` | from Step 4 |
| `YT_CLIENT_ID` | from Step 2 |
| `YT_CLIENT_SECRET` | from Step 2 |
| `YT_REFRESH_TOKEN` | from Step 2 |

Also: repo **Settings → Actions → General → Workflow permissions** →
select **Read and write permissions** (lets the bot save its memory/state).

## STEP 6 — First test run (5 min)
1. Repo → **Actions** tab → "Produce long-form video" → **Run workflow** →
   tick **Dry run** → Run.
2. When it finishes (~25–45 min), download the artifact zip → watch the video.
3. Happy? Run again WITHOUT dry-run. It uploads as **Private, scheduled**
   for the next peak slot. Check YouTube Studio to see it queued.

## STEP 7 — (Optional but recommended) Better music
The bot generates subtle ambient beds, but real tracks are better:
1. YouTube Studio → **Audio Library** → filter: Attribution not required →
   download 3–5 chill/tension tracks.
2. Drop the .mp3 files into `assets/music/` in the repo (drag & drop on
   github.com works). The bot rotates them automatically.

---

## 🗓️ YOUR ONGOING JOB (15 min/week)
- Check YouTube Studio Mondays: skim scheduled videos before they go live
  (they upload 8+ hours before publish time — your veto window).
- Delete/unschedule anything that looks off. That's it.

## 💰 MONETIZATION MILESTONES
- **1,000 subs + 4,000 watch-hours** (or 10M Shorts views in 90 days) →
  YouTube Studio → Earn tab → apply for YouTube Partner Program → set up AdSense.
- During YPP human review, your channel shows original research with cited
  sources & unique screenshots — exactly what passes review.
- Realistic timeline in this niche: 3–6 months of consistent uploads.

## ⚠️ RULES THAT KEEP THE CHANNEL SAFE
1. Never re-upload other people's videos — the bot never does this by design.
2. Don't touch the schedule to "post more" — 4 long + 7 shorts/week is the
   safe, sustainable max. Quality > volume.
3. If a video's subject sends a complaint/legal notice → take that video
   private immediately (the bot uses cautious language to prevent this).
4. Keep using the refresh token weekly (automatic) so it never expires.
