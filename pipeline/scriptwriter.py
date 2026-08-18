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

Retention rules you MUST follow:
- Cold open: first 2 sentences state the burning question + tease the most
  surprising finding WITHOUT revealing it ("...and what I found in their
  terms of service is honestly wild. Stick around for that.")
- Open loop every ~90 seconds ("but that's not even the weird part")
- Every claim tied to evidence from the dossier — cite where it came from
  in-narration ("on their own Trustpilot page...", "one Redditor put it this way")
- Rhetorical questions to re-engage ("sound familiar?")
- Verdict near the END (that's why they stay), then 1-line CTA:
  subscribe framed as service ("we check this stuff weekly so you don't
  get burned — that's the whole channel")
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
    shots = [{"name": s["name"], "source": s.get("source", "web")}
             for s in dossier.get("screenshots", [])]

    if kind == "long":
        length_spec = (f"{v['target_minutes_min']}-{v['target_minutes_max']} minutes "
                       f"(~{v['target_minutes_min'] * 150}-{v['target_minutes_max'] * 150} words)")
        seg_spec = ("10-16 segments. This is the DEEP DIVE: walk through EVERY key "
                    "finding from the dossier one by one — don't summarize, show the "
                    "work. Cover the red flags AND the green flags in detail, quote "
                    "real users, explain what the domain/company info means, and pair "
                    "each major finding with its own evidence segment (screenshot "
                    "visual + source named in narration). The viewer should finish "
                    "feeling like they watched the full investigation, not a recap")
    else:
        length_spec = "35-48 seconds (~95-125 words)"
        seg_spec = "3-5 segments. Segment 1 = instant hook, last = verdict + 'follow for the full breakdown'"

    prompt = f"""Write the {kind}-form script.

TOPIC: {dossier['topic']['topic']}
VERDICT: {findings['verdict']} (confidence: {findings['confidence']})
KEY FINDINGS: {json.dumps(findings['key_findings'], indent=1)}
RED FLAGS: {json.dumps(findings.get('red_flags', []))}
GREEN FLAGS: {json.dumps(findings.get('green_flags', []))}
REAL USER QUOTES: {json.dumps(findings.get('best_user_quotes', []))}
DOMAIN INFO: {json.dumps(dossier.get('domain_info'))}
AVAILABLE SCREENSHOTS (use as visual proof — "source" tells you which site it
captures; name that source in the narration when it's on screen): {json.dumps(shots)}

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
     "zoom": true|false (zoom-punch emphasis moment)}}
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
