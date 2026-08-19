"""
STEP 3 — SCRIPTWRITER
Turns the investigation dossier into a retention-engineered script.
Structure: cold-open hook -> promise -> investigation w/ open loops ->
proof segments (mapped to screenshots) -> verdict -> CTA.
Casual smart-friend voice. Monetization-safe language enforced.
"""
import json

from .util import gemini_json, load_config, WORK_DIR

SYSTEM = """You write scripts for "Actually Checked", a faceless YouTube channel.
Voice: casual smart friend — like texting your sharpest friend who did the
homework for you. Contractions, direct address ("you"), light humor, zero fluff.
NEVER robotic, NEVER "in this video we will". No emojis in narration.
NEVER say "dossier", "our data", "the data we have", or talk about your own
research files — you're a person who checked things, not a system reading a
report ("I checked their Trustpilot page" not "the dossier shows"). If a
piece of data is missing, just don't mention it — never narrate its absence
("there are zero official ratings available to verify" is FORBIDDEN; instead
move to a source you DO have).

NARRATIVE ARC (MANDATORY — this is the channel's signature structure,
modeled on top investigation channels):
1. THE HOOK + THE CLAIM (two separate beats):
   - SEGMENT 1 is ALWAYS visual="title_card" — the eye-catching branded
     opener with huge center captions and a reaction emoji. NEVER open the
     video on a screenshot; hook first, evidence second. Narration: the
     burning question + tease the most surprising finding WITHOUT revealing
     it ("Is V Shred actually legit? I dug into the data... and you need to
     see what I found.")
   - SEGMENT 2 = THE CLAIM: introduce what the app/site claims to do, in its
     own marketing language ("V Shred says it'll build you a custom plan for
     your exact body type. That's the pitch.") — and while saying it, SHOW
     the claim: visual="screenshot:official_site" with zoom=true so the
     camera magnifies the site's own marketing text. Show, don't just tell.
2. THE INVESTIGATION — walk through the research SOURCE BY SOURCE, like a
   detective laying out evidence. Each source gets its own beat:
   - STEELMAN BOTH SIDES like an honest analyst. Never a lazy one-sided
     take: present the strongest evidence it's REAL first ("let's be fair —
     here's the best case FOR it"), THEN pivot to the red flags ("but then
     I found something that changes the picture"). The pivot IS the
     retention hook.
   - START WITH THE NUMBERS: if rating stats exist, lead with them
     ("First stop: Trustpilot. Two point three out of five. And get this —
     fifty-eight percent of all reviews are one star. That's not a few
     unlucky users, that's a pattern.")
   - READ REAL COMMENTS out loud, introduced with emphasis ("and listen to
     what this user actually wrote: quote..."). Reading real user words is
     the single most trusted moment in the video — use the best_user_quotes.
   - NAME THE PATTERN: if the_pattern exists in the findings, dedicate a
     beat to walking through it step by step ("here's the story that keeps
     repeating: you complete offers... your balance grows... you hit
     withdraw... and THAT's when the problems start"). A recurring pattern
     across independent users is the most damning — or most reassuring —
     evidence there is. Interpret it honestly: also give the innocent
     explanation when one exists ("to be fair, bigger payouts attract
     harder fraud checks — but from YOUR side the result feels the same").
   - Teach judgment as you go ("here's a tip: ignore the star number for a
     second and read the one-star reviews — if they all describe the SAME
     problem, that problem is real.")
   - Transition between sources explicitly ("okay, that's Trustpilot. But
     one review site is never enough — let's see what Reddit says.")
3. THE RISK — a dedicated beat spelling out what a viewer actually risks by
   trying this: time, money, personal data. Be concrete ("worst case here
   isn't losing money — it's forty hours of your life for a payout that may
   never come.")
4. THE VERDICT — near the END (that's why they stay). NUANCED and scored,
   never binary: use the legitimacy/reliability scores when present ("so
   here's my honest score: six out of ten that it's real... but only three
   out of ten that you can RELY on it. And that gap? That gap is the whole
   story."). "Real but unreliable" is a verdict; "scam / not scam" alone
   is lazy.
5. THE WAY FORWARD — deliver the way_forward RULES as a numbered rulebook,
   one by one, punchy ("Rule one: never put in your own money. Rule two:
   the moment you hit ten dollars, test a withdrawal — you're not cashing
   out, you're testing THEM."). If results vary by region, say so as
   general knowledge ("and heads up — offers and payouts vary a LOT
   depending on where you live, so test yours before you commit hours") —
   NEVER name specific countries; this channel speaks to everyone.
   Then 1-line CTA: subscribe framed as service ("we check this stuff so you
   don't get burned — that's the whole channel").

Retention devices:
- Open loop every ~60-90 seconds ("but that's not even the weird part")
- Rhetorical questions to re-engage ("sound familiar?")
- Numbers beat adjectives: "58% one-star" beats "lots of bad reviews" every time
- Every claim tied to evidence from the dossier — always cite the source
  in-narration ("on their own Trustpilot page...", "one Redditor put it this way")
Ad-safety: no profanity, no accusations-as-fact (use "red flags", "users
report"), no medical/financial advice claims, family-friendly.

Community loop (MANDATORY): early in the video (within the first 3 segments)
invite viewers to share their OWN experience with the subject in the comments
("if you've actually used this, drop your experience below — real stories
help everyone"), and invite topic suggestions near the end ("got a site or
app you want us to check next? drop it in the comments — that's literally
how we pick what to investigate").

Evidence-first visuals (MANDATORY): screenshots are the trust engine of this
channel. Prefer "screenshot:<name>" visuals over b-roll whenever a matching
screenshot exists — every major claim should sit on top of the receipt that
proves it. When a screenshot is on screen, NAME the source out loud in the
narration ("here's their Trustpilot page...", "this is a real Reddit thread",
"straight from their own website", "look at these search results"). Make it
clear we researched across MULTIPLE independent sources, never just one.

Verdict-aware CTA (MANDATORY, near the end):
- POSITIVE verdict (legit / actually works / actually pays): tell viewers the
  official link is in the description, invite them to try it — but CAUTIOUSLY
  ("start small, never pay to withdraw, never share more info than needed").
  Then ask: "if you try it and have a BAD experience, comment below so others
  can see — that's how we keep each other safe."
- NEGATIVE verdict (scam / avoid / not worth it): clear warn-off, tell them to
  share this with someone who might fall for it, and ask anyone already burned
  to share their story in the comments.
- MIXED/unclear: present both sides, tell viewers to proceed only with money
  they can afford to lose, ask for real experiences below.
ALWAYS end by asking which site or app they want checked next.
"""


def write_script(dossier: dict, kind: str = "long") -> dict:
    cfg = load_config()
    v = cfg["video"]["long" if kind == "long" else "short"]
    findings = dossier["findings"]
    shots = [{"name": s["name"], "source": s.get("source", "web"),
              "shows": s.get("reads", ""),
              "visible_rating": s.get("visible_rating"),
              "quotable_on_screen": [h["text"] for h in s.get("highlights", [])]}
             for s in dossier.get("screenshots", [])]

    if kind == "long":
        min_words = v['target_minutes_min'] * 140
        max_words = v['target_minutes_max'] * 150
        length_spec = (f"{v['target_minutes_min']}-{v['target_minutes_max']} minutes. "
                       f"HARD REQUIREMENT: total narration MUST be at least "
                       f"{min_words} words (target {min_words}-{max_words}). "
                       f"A script under {min_words} words is a FAILED script")
        seg_spec = ("14-20 segments following the full narrative arc. This is the "
                    "DEEP DIVE: introduce the claim, then walk through EVERY source "
                    "and EVERY key finding one by one — don't summarize, show the "
                    "work. Read multiple real user quotes in full. Explain the "
                    "rating numbers and what each percentage means. Cover red flags "
                    "AND green flags in detail. Explain the domain/company info. "
                    "Dedicate full segments to THE RISK and THE WAY FORWARD. Pair "
                    "each major finding with its own evidence segment (screenshot "
                    "visual + source named in narration). Each segment's narration "
                    "should be 60-110 words — substantial beats, not one-liners. "
                    "The viewer should finish feeling like they watched the full "
                    "investigation, not a recap")
    else:
        min_words = 130
        length_spec = ("50-60 seconds (~140-165 words). Use the full minute — "
                       "a Short that ends too fast can't build trust")
        seg_spec = ("5-7 segments compressing the narrative arc: (1) the claim + "
                    "hook, (2) the numbers from source #1 (rating + percentages), "
                    "(3) a real user quote read aloud, (4) cross-check with a "
                    "second source, (5) the risk in one line, (6) verdict + way "
                    "forward, (7) 'full breakdown on the channel' + what should "
                    "we check next")

    prompt = f"""Write the {kind}-form script.

TOPIC: {dossier['topic']['topic']}
WHAT IT CLAIMS: {findings.get('what_it_claims', 'unknown')}
VERDICT: {findings['verdict']} (confidence: {findings['confidence']})
SCORES (use in the verdict beat): {json.dumps(findings.get('scores'))}
RATING STATS (lead with these numbers): {findings.get('rating_stats')}
TRUSTPILOT DATA: {json.dumps(dossier.get('trustpilot_rating'))}
STRONGEST EVIDENCE FOR (steelman first): {json.dumps(findings.get('strongest_evidence_for', []))}
STRONGEST EVIDENCE AGAINST: {json.dumps(findings.get('strongest_evidence_against', []))}
THE PATTERN (dedicate a beat if not null): {findings.get('the_pattern')}
KEY FINDINGS: {json.dumps(findings['key_findings'], indent=1)}
RED FLAGS: {json.dumps(findings.get('red_flags', []))}
GREEN FLAGS: {json.dumps(findings.get('green_flags', []))}
REAL USER QUOTES (read the best ones aloud): {json.dumps(findings.get('best_user_quotes', []))}
THE RISK: {findings.get('risk_assessment')}
WAY FORWARD RULES (deliver as numbered rulebook): {json.dumps(findings.get('way_forward'))}
DOMAIN INFO: {json.dumps(dossier.get('domain_info'))}
AVAILABLE SCREENSHOTS — each was READ by our vision system. "shows" is what
the page ACTUALLY displays, and "quotable_on_screen" are the exact review/
rating/claim snippets that will POP on screen while this screenshot is the
visual. HARD RULE: when a screenshot is on screen, the narration MUST match
what it shows — talk about the visible rating, read the quotable snippets
aloud (they appear as pop-cards as you speak them), never describe something
the screenshot doesn't contain. Name the source out loud too.
{json.dumps(shots, indent=1)}

Target length: {length_spec}. {seg_spec}.

Return JSON:
{{"title": str (<=95 chars, curiosity + searchable, e.g. "I Checked If X Actually Pays... (Proof Inside)"),
 "hook_text": str (5-8 word on-screen text for the opening),
 "segments": [
   {{"narration": str (what the voice says, natural spoken English),
     "visual": "screenshot:<name>" | "broll:<2-4 word b-roll search query>" | "title_card",
     "onscreen_text": str|null (short punch text, <=6 words),
     "emoji": str|null (ONE reaction emoji that pops on screen for this beat,
        e.g. \"🚩\" for red flag, \"💰\" money, \"🤔\" suspicious, \"✅\" verified,
        \"❌\" busted, \"👀\" look-at-this, \"🔥\" wild fact. Use on ~60% of
        segments, null on the rest — variety keeps it fresh),
     "zoom": true|false — on screenshot visuals true = MAGNIFIED evidence
        (camera zooms in and pans across the page so details are big and
        readable; nothing gets cropped, the camera travels). Use true when
        the narration points at something specific on the page (a claim, a
        rating, a review); false for general scrolling context}}
 ],
 "music_mood": "tension"|"chill"|"upbeat" (tension for scam exposes,
    upbeat for methods-that-work, chill for neutral explainers),
 "pinned_comment": str (friendly first comment: ask viewers to share their
    real experience with the subject + suggest the next thing to check.
    1-3 sentences, 1-2 emojis),
 "description": str (YouTube description: 2-line summary — for a POSITIVE
   verdict explicitly say "Official link below — try it cautiously" — then
   'SOURCES:' with the literal placeholder {{SOURCES}} where links go, then
   chapters placeholder {{CHAPTERS}}),
 "tags": [15-20 SEO tags],
 "category": "money"|"scam"|"viral",
 "thumbnail": {{"big_text": str (<=4 words, e.g. "ACTUALLY PAYS?"),
                "small_text": str (<=5 words),
                "style": "alarm"|"money"|"shock",
                "verdict_emoji_concept": str}}
}}"""
    script = gemini_json(prompt, system=SYSTEM, temperature=0.95)

    # LENGTH ENFORCEMENT: a "10 minute" script that comes back at 2 minutes
    # kills the channel. Count narration words; if short, ask the model to
    # EXPAND (deeper source walkthroughs, more quotes) up to 2 retries.
    def _wc(s):
        return sum(len(seg.get("narration", "").split())
                   for seg in s.get("segments", []))
    if kind == "long":
        for _ in range(2):
            wc = _wc(script)
            if wc >= min_words:
                break
            expand = gemini_json(
                prompt + f"""

PREVIOUS ATTEMPT (only {wc} words of narration — TOO SHORT, minimum is
{min_words}): {json.dumps(script.get('segments', []))[:8000]}

Rewrite the FULL script at proper depth. Expand every investigation beat:
spend more time on each source, read MORE real user quotes in full, explain
the rating numbers and percentages, add the risk and way-forward segments
if missing. Same JSON format. Total narration MUST exceed {min_words} words.""",
                system=SYSTEM, temperature=0.9)
            if _wc(expand) > wc:
                script = expand

    script["kind"] = kind
    out = WORK_DIR / dossier["slug"] / f"script_{kind}.json"
    out.write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    return script


if __name__ == "__main__":
    import sys
    slug = sys.argv[1]
    dossier = json.loads((WORK_DIR / slug / "dossier.json").read_text(encoding="utf-8"))
    s = write_script(dossier, sys.argv[2] if len(sys.argv) > 2 else "long")
    print(s["title"], "|", len(s["segments"]), "segments")
