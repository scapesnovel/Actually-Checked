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
help everyone"), and invite topic suggestions near the end ("got something
you want us to check next? comments are open").
"""


def write_script(dossier: dict, kind: str = "long") -> dict:
    cfg = load_config()
    v = cfg["video"]["long" if kind == "long" else "short"]
    findings = dossier["findings"]
    shots = [s["name"] for s in dossier.get("screenshots", [])]

    if kind == "long":
        length_spec = (f"{v['target_minutes_min']}-{v['target_minutes_max']} minutes "
                       f"(~{v['target_minutes_min'] * 150}-{v['target_minutes_max'] * 150} words)")
        seg_spec = "8-14 segments"
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
AVAILABLE SCREENSHOTS (use as visual proof): {shots}

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
 "description": str (YouTube description: 2-line summary, then 'SOURCES:' —
   leave the literal placeholder {{SOURCES}} where links go, then chapters placeholder {{CHAPTERS}}),
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
