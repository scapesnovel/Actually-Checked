"""
STEP 5b — EDITOR (the quality engine)
Assembles the final video with professional retention techniques:
- Ken-Burns motion on every clip (nothing static, ever)
- Screenshot "zoom-punch" proof moments with highlight framing
- Word-synced karaoke captions (bold, center-bottom, pop animation)
- On-screen punch text cards
- Crossfade/slide transitions + whoosh SFX markers
- Background music auto-ducked under narration
- Branded intro sting (1.2s) + end-card
Built on ffmpeg filter graphs per-segment, then concat. CPU-friendly for CI.
"""
import json, math, random, subprocess, shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .util import WORK_DIR, ASSETS, load_config
from .broll import fetch_broll

FONT_BOLD = str(ASSETS / "fonts" / "Anton-Regular.ttf")
FONT_MED = str(ASSETS / "fonts" / "Inter-Bold.ttf")
FONT_EMOJI = ASSETS / "fonts" / "NotoColorEmoji.ttf"
SFX = ASSETS / "sfx"

# curated ffmpeg xfade transitions (cool but not cheesy)
TRANSITIONS = ["slideleft", "slideright", "circleopen", "wipeleft",
               "smoothup", "smoothleft", "diagtl", "fade", "radial"]

# ---- caption word styling ---------------------------------------------------
# ASS colors are &HBBGGRR
ASS_WHITE = "&H00FFFFFF&"
ASS_GREEN = "&H00A0E500&"   # brand mint  (0,229,160)
ASS_RED = "&H005747FF&"     # alert red   (255,71,87)
ASS_YELLOW = "&H002ACDFF&"  # (255,205,42)

GREEN_WORDS = {"money", "cash", "pay", "pays", "paid", "payment", "earn",
               "earned", "profit", "free", "legit", "real", "works", "work",
               "working", "proof", "verified", "safe", "win", "true",
               "dollars", "$20", "bonus", "yes"}
RED_WORDS = {"scam", "scams", "fake", "fraud", "warning", "never", "lose",
             "lost", "danger", "dangerous", "risk", "risky", "busted",
             "avoid", "worst", "catch", "flag", "flags", "lie", "lies",
             "stolen", "steal", "no", "not", "don't", "stop", "suspicious"}
YELLOW_WORDS = {"wild", "crazy", "insane", "secret", "hidden", "shocking",
                "truth", "actually", "checked", "but", "however"}

# keyword -> emoji that pops next to the caption at that word's timestamp
KEYWORD_EMOJI = {
    "money": "\U0001F4B0", "cash": "\U0001F4B0", "pay": "\U0001F4B5",
    "pays": "\U0001F4B5", "paid": "\U0001F4B5", "dollars": "\U0001F4B0",
    "earn": "\U0001F4B8", "profit": "\U0001F4C8",
    "scam": "\U0001F6A8", "fraud": "\U0001F6A8", "fake": "\u274C",
    "warning": "\u26A0\uFE0F", "risk": "\u26A0\uFE0F", "danger": "\u26A0\uFE0F",
    "legit": "\u2705", "verified": "\u2705", "safe": "\u2705",
    "proof": "\U0001F9FE", "busted": "\u274C", "avoid": "\U0001F6AB",
    "look": "\U0001F440", "watch": "\U0001F440", "see": "\U0001F440",
    "check": "\U0001F50E", "checked": "\U0001F50E",
    "wild": "\U0001F92F", "crazy": "\U0001F92F", "insane": "\U0001F92F",
    "secret": "\U0001F92B", "hidden": "\U0001F575\uFE0F",
    "free": "\U0001F381", "time": "\u23F0", "phone": "\U0001F4F1",
    "app": "\U0001F4F1", "website": "\U0001F310", "site": "\U0001F310",
    "people": "\U0001F465", "users": "\U0001F465", "reddit": "\U0001F4AC",
    "reviews": "\u2B50", "question": "\u2753", "fire": "\U0001F525",
}


def _word_style(word: str) -> tuple[str, bool]:
    """Return (ass_color, emphasize) for a word."""
    w = "".join(ch for ch in word.lower() if ch.isalnum() or ch in "$'")
    if w in GREEN_WORDS:
        return ASS_GREEN, True
    if w in RED_WORDS:
        return ASS_RED, True
    if w in YELLOW_WORDS:
        return ASS_YELLOW, True
    return ASS_WHITE, False

BRAND_BG = (14, 17, 23)
BRAND_ACCENT = (0, 229, 160)   # mint green — "verified" energy
BRAND_ALERT = (255, 71, 87)    # red — scam energy


def _run(cmd: list[str]):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def _dur(path) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)]).decode().strip())


def make_emoji_sticker(emoji: str, path: Path, px: int = 300):
    """Render a color emoji to transparent PNG (NotoColorEmoji is fixed 109px)."""
    try:
        font = ImageFont.truetype(str(FONT_EMOJI), 109)
        img = Image.new("RGBA", (137, 137), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((6, 6), emoji, font=font, embedded_color=True)
        img = img.resize((px, px), Image.LANCZOS)
        img.save(path)
        return path
    except Exception:
        return None


def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ---------------- generated visual assets ---------------------------------
def make_title_card(text: str, path: Path, size, style="dark"):
    W, H = size
    img = Image.new("RGB", (W, H), BRAND_BG)
    dr = ImageDraw.Draw(img)
    # subtle diagonal texture
    for x in range(-H, W, 90):
        dr.line([(x, H), (x + H, 0)], fill=(22, 27, 36), width=2)
    f = _font(FONT_BOLD, int(H * 0.105))
    words, lines, cur = text.upper().split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if dr.textlength(t, font=f) > W * 0.84:
            lines.append(cur); cur = w
        else:
            cur = t
    lines.append(cur)
    y = int(H * 0.12)   # title lives in the TOP third; captions own the center
    for ln in lines:
        tw = dr.textlength(ln, font=f)
        dr.text(((W - tw) / 2 + 4, y + 4), ln, font=f, fill=(0, 0, 0))
        dr.text(((W - tw) / 2, y), ln, font=f, fill=(255, 255, 255))
        y += int(H * 0.13)
    # accent underline
    dr.rectangle([W * 0.42, y + 10, W * 0.58, y + 18], fill=BRAND_ACCENT)
    img.save(path)


def frame_screenshot(shot_path: str, out_path: Path, size):
    """Put screenshot in a browser-window frame on brand bg = 'proof' look."""
    W, H = size
    bg = Image.new("RGB", (W, H), BRAND_BG)
    shot = Image.open(shot_path).convert("RGB")
    target_w = int(W * 0.86)
    shot = shot.resize((target_w, int(shot.height * target_w / shot.width)))
    max_h = int(H * 0.74)
    if shot.height > max_h:
        shot = shot.crop((0, 0, shot.width, max_h))
    bar_h = int(H * 0.045)
    frame = Image.new("RGB", (shot.width, shot.height + bar_h), (40, 44, 52))
    dr = ImageDraw.Draw(frame)
    for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        dr.ellipse([18 + i * 34, bar_h // 2 - 9, 36 + i * 34, bar_h // 2 + 9],
                   fill=col)
    frame.paste(shot, (0, bar_h))
    # drop shadow
    shadow = Image.new("RGBA", (frame.width + 60, frame.height + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([30, 30, frame.width + 30, frame.height + 30],
                                     fill=(0, 0, 0, 160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    x = (W - frame.width) // 2
    y = (H - frame.height) // 2
    bg.paste(Image.alpha_composite(Image.new("RGBA", shadow.size, (0, 0, 0, 0)),
                                   shadow).convert("RGB"),
             (x - 30, y - 30), shadow)
    bg.paste(frame, (x, y))
    bg.save(out_path)


def frame_screenshot_scroll(shot_path: str, out_path: Path, size,
                            source: str | None = None):
    """Tall 'scroll strip': the FULL screenshot in a browser frame, taller
    than the video. The editor pans down it = looks like real scrolling
    through reviews/comments. Adds a source badge (e.g. TRUSTPILOT.COM).
    Returns the strip height so the caller can compute the pan."""
    W, H = size
    shot = Image.open(shot_path).convert("RGB")
    target_w = int(W * 0.92)
    shot = shot.resize((target_w, int(shot.height * target_w / shot.width)),
                       Image.LANCZOS)
    # keep it readable: strip 1.2x..3x of the video height
    max_strip = int(H * 3.0)
    if shot.height > max_strip:
        shot = shot.crop((0, 0, shot.width, max_strip))
    bar_h = int(H * 0.045)
    frame = Image.new("RGB", (W, shot.height + bar_h + int(H * 0.06)), BRAND_BG)
    # browser chrome bar
    chrome = Image.new("RGB", (shot.width, bar_h), (40, 44, 52))
    dr = ImageDraw.Draw(chrome)
    for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        dr.ellipse([18 + i * 34, bar_h // 2 - 9, 36 + i * 34, bar_h // 2 + 9],
                   fill=col)
    x = (W - shot.width) // 2
    frame.paste(chrome, (x, int(H * 0.03)))
    frame.paste(shot, (x, int(H * 0.03) + bar_h))
    frame.save(out_path)
    return frame.height


def make_source_badge(source: str, out_path: Path, size):
    """'SOURCE: TRUSTPILOT.COM' pill badge overlaid on evidence segments."""
    W, H = size
    fs = int(H * 0.026)
    try:
        f = ImageFont.truetype(str(FONT_BOLD), fs)
    except Exception:
        f = ImageFont.load_default()
    txt = f"SOURCE: {source.upper()}"
    tmp = Image.new("RGBA", (10, 10))
    tw = int(ImageDraw.Draw(tmp).textlength(txt, font=f))
    pad = int(fs * 0.7)
    im = Image.new("RGBA", (tw + pad * 2 + fs, fs + pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, im.width - 1, im.height - 1],
                        radius=im.height // 2, fill=(0, 0, 0, 200),
                        outline=BRAND_ACCENT + (255,), width=3)
    # camera dot = "receipt" feel
    d.ellipse([pad * 0.7, im.height / 2 - fs * 0.28,
               pad * 0.7 + fs * 0.56, im.height / 2 + fs * 0.28],
              fill=(255, 70, 70, 255))
    d.text((pad * 0.9 + fs * 0.7, pad // 2 - 2), txt, font=f,
           fill=(255, 255, 255, 255))
    im.save(out_path)


def make_ass_captions(words: list[dict], seg_dur: float, out_path: Path,
                      size, portrait: bool, position: str = "center"):
    """HUGE captions, title-sized. Per-word color coding
    (green=money/positive, red=scam/warning, yellow=hype), keyword words
    rendered bigger, karaoke highlight, pop-in scale animation.
    position='center' (default) = Alignment 5 dead-center;
    position='bottom' = Alignment 2 + smaller, used on EVIDENCE segments so
    the screenshot/proof stays fully readable."""
    W, H = size
    if position == "bottom":
        fs = int(H * 0.062)      # smaller — evidence owns the screen
        align, marginv = 2, int(H * 0.055)
    else:
        fs = int(H * 0.125)      # BIGGER than title — captions own the screen
        align, marginv = 5, 0
    fs_key = int(fs * 1.25)      # emphasized keywords even bigger
    header = f"""[Script Info]
PlayResX: {W}
PlayResY: {H}
WrapStyle: 1
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, BorderStyle
Style: Cap,Anton,{fs},&H00FFFFFF,&H00B8B8B8,&H00000000,&H96000000,-1,{max(4, fs // 14)},3,{align},40,40,{marginv},1
[Events]
Format: Layer, Start, End, Style, Text
"""
    def ts(t):
        t = max(0, t)
        h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    # build groups first so each group's end can be clamped to the next start
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) == 3 or w is words[-1]:
            groups.append(cur)
            cur = []
    # SYNC FIX: whisper word-onsets + ASS pop-in animation make captions land
    # ~0.25-0.35s AFTER the word is heard. Lead every caption slightly so the
    # text pops exactly when (or a hair before) the word is spoken.
    LEAD = 0.12
    lines = []
    for gi, group in enumerate(groups):
        start = max(0.0, group[0]["start"] - LEAD)
        end = min(group[-1]["end"] + 0.05 - LEAD * 0.5, seg_dur)
        if gi + 1 < len(groups):   # never overlap the next group
            end = min(end, max(start + 0.15,
                               groups[gi + 1][0]["start"] - LEAD - 0.02))
        parts = []
        for gw in group:
            dur_cs = max(1, int((gw["end"] - gw["start"]) * 100))
            color, emph = _word_style(gw["word"])
            size_tag = rf"\fs{fs_key}" if emph else rf"\fs{fs}"
            # karaoke fill from gray secondary to the word's color
            parts.append(r"{\k%d\1c%s%s}%s " % (dur_cs, color, size_tag,
                                                gw["word"].upper()))
        # pop-in scale animation for the whole group (fast = tighter sync feel)
        txt = (r"{\fad(25,20)\fscx78\fscy78"
               r"\t(0,70,\fscx104\fscy104)\t(70,120,\fscx100\fscy100)"
               r"\3c&H00000000&}" + "".join(parts).strip())
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Cap,{txt}")
    out_path.write_text(header + "\n".join(lines), encoding="utf-8")


# ---------------- per-segment clip build -----------------------------------
def build_segment(slug: str, i: int, seg: dict, dur: float, words: list[dict],
                  shots: dict, size, portrait: bool) -> Path:
    W, H = size
    seg_dir = WORK_DIR / slug / "clips"
    seg_dir.mkdir(parents=True, exist_ok=True)
    out = seg_dir / f"clip_{i:03d}.mp4"
    visual = seg.get("visual", "broll:technology")
    src_img = None
    src_vid = None

    evidence = None          # dict -> scrolling proof segment
    if visual.startswith("screenshot:"):
        name = visual.split(":", 1)[1]
        if name in shots:
            meta = shots[name]
            shot_path = meta["path"] if isinstance(meta, dict) else meta
            source = (meta.get("source") if isinstance(meta, dict) else None)
            strip = seg_dir / f"strip_{i:03d}.png"
            strip_h = frame_screenshot_scroll(shot_path, strip, size, source)
            if strip_h > H * 1.15:   # tall enough to scroll through
                evidence = {"strip": strip, "strip_h": strip_h,
                            "source": source}
            else:                    # short page -> classic framed still
                src_img = seg_dir / f"shot_{i:03d}.png"
                frame_screenshot(shot_path, src_img, size)
                evidence = {"still": True, "source": source}
    if visual == "title_card" or (src_img is None and not visual.startswith("broll")):
        src_img = seg_dir / f"card_{i:03d}.png"
        make_title_card(seg.get("onscreen_text") or "ACTUALLY CHECKED",
                        src_img, size)
    if src_img is None:
        q = visual.split(":", 1)[1] if ":" in visual else "computer screen"
        src_vid = fetch_broll(slug, q, i, portrait)
        if src_vid is None:
            src_img = seg_dir / f"card_{i:03d}.png"
            make_title_card(seg.get("onscreen_text") or seg["narration"][:40],
                            src_img, size)

    audio = WORK_DIR / slug / "audio" / f"seg_{i:03d}.mp3"
    total_frames = max(2, int(dur * 30))

    # motion: zoom-punch for proof moments, slow ken-burns otherwise
    if seg.get("zoom"):
        zexpr = "if(lt(on,12),1.0+0.025*on,min(1.32,1.3))"
    else:
        zin = random.choice([True, False])
        zexpr = (f"1.0+0.0009*on" if zin else f"1.14-0.0009*on")
    kb = (f"scale=8000:-1,zoompan=z='{zexpr}':x='iw/2-(iw/zoom/2)':"
          f"y='ih/2-(ih/zoom/2)':d={total_frames}:s={W}x{H}:fps=30")

    vf_extra = ""
    # on-screen punch text (skip title cards which already contain text;
    # skip evidence segments — the proof itself is the star there)
    ost = seg.get("onscreen_text")
    if ost and evidence is None and (
            src_vid is not None or (src_img and "card" not in src_img.name)):
        safe = ost.upper().replace("'", r"\\\'").replace(":", r"\:")
        y = int(H * (0.10 if portrait else 0.10))
        vf_extra = (f",drawtext=fontfile='{FONT_BOLD}':text='{safe}':"
                    f"fontsize={int(H * 0.05)}:fontcolor=white:borderw=5:"
                    f"bordercolor=black:x=(w-text_w)/2:y={y}:"
                    f"enable='gte(t,0.25)'")

    # captions — evidence segments push captions to the BOTTOM (smaller) so
    # screenshots/reviews stay fully readable and build trust
    ass = seg_dir / f"cap_{i:03d}.ass"
    if words:
        make_ass_captions(words, dur, ass, size, portrait,
                          position="bottom" if evidence else "center")
        vf_extra += f",subtitles='{ass}':fontsdir='{ASSETS / 'fonts'}'"

    if evidence and evidence.get("strip"):
        # SCROLLING PROOF: slow pan down the tall screenshot strip, pause
        # at the top first so viewers orient, then glide through content
        strip_h = evidence["strip_h"]
        scroll_range = max(1, strip_h - H)
        hold = min(1.2, dur * 0.2)   # initial hold before scrolling starts
        yexpr = (f"min({scroll_range},"
                 f"max(0,(t-{hold:.2f}))*{scroll_range}/{max(0.5, dur - hold - 0.4):.2f})")
        vf = f"crop={W}:{H}:0:'{yexpr}',setsar=1{vf_extra}"
        _run(["ffmpeg", "-y", "-loop", "1", "-i", str(evidence["strip"]),
              "-i", str(audio), "-t", f"{dur:.3f}", "-vf", vf,
              "-map", "0:v", "-map", "1:a", "-r", "30",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
              "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
              "-pix_fmt", "yuv420p", str(out)])
    elif src_vid is not None:
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},setsar=1{vf_extra}")
        _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src_vid),
              "-i", str(audio), "-t", f"{dur:.3f}", "-vf", vf,
              "-map", "0:v", "-map", "1:a", "-r", "30",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
              "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
              "-pix_fmt", "yuv420p", str(out)])
    else:
        _run(["ffmpeg", "-y", "-loop", "1", "-i", str(src_img),
              "-i", str(audio), "-t", f"{dur:.3f}",
              "-vf", kb + vf_extra, "-map", "0:v", "-map", "1:a",
              "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
              "-crf", "21", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
              "-pix_fmt", "yuv420p", str(out)])

    # ---- emoji sticker pass ------------------------------------------------
    # a) segment reaction emoji: corner, bounces/wobbles for the whole beat
    # b) keyword emojis: pop right ABOVE the center captions exactly when the
    #    word is spoken (word-level whisper timing), visible ~1.4s
    overlays = []   # (emoji, appear_time, lifetime, mode)
    emoji = seg.get("emoji")
    if emoji and evidence is None:   # keep evidence segments clean
        overlays.append((emoji, min(0.6, dur * 0.25), None, "corner"))
    if evidence and evidence.get("source"):
        # SOURCE badge pinned top-right on proof segments = instant trust
        badge = seg_dir / f"badge_{i:03d}.png"
        try:
            make_source_badge(evidence["source"], badge, size)
            badged = seg_dir / f"clip_{i:03d}_b.mp4"
            _run(["ffmpeg", "-y", "-i", str(out), "-i", str(badge),
                  "-filter_complex",
                  f"[0:v][1:v]overlay=x=W-w-{int(W*0.03)}:y={int(H*0.03)}[v]",
                  "-map", "[v]", "-map", "0:a", "-c:v", "libx264",
                  "-preset", "veryfast", "-crf", "21", "-c:a", "copy",
                  str(badged)])
            shutil.move(str(badged), str(out))
        except Exception:
            pass
    used = set()
    kw_events = []
    for wd in (words if evidence is None else []) or []:
        wclean = "".join(ch for ch in wd["word"].lower() if ch.isalnum())
        em = KEYWORD_EMOJI.get(wclean)
        if em and em not in used and wd["start"] < dur - 0.8:
            kw_events.append((em, max(0.0, wd["start"] - 0.05)))
            used.add(em)
        if len(kw_events) >= 3:   # max 3 keyword pops per segment
            break
    for em, t0 in kw_events:
        overlays.append((em, t0, 1.4, "caption"))

    if overlays:
        inputs = ["-i", str(out)]
        fc_parts, vprev = [], "[0:v]"
        pop = SFX / "pop.wav"
        sfx_labels = []
        idx = 1
        ok = True
        for n, (em, t0, life, mode) in enumerate(overlays):
            px = int(H * (0.22 if mode == "corner" else 0.16))
            stk = seg_dir / f"emoji_{i:03d}_{n}.png"
            if not make_emoji_sticker(em, stk, px=px):
                ok = False
                continue
            inputs += ["-loop", "1", "-i", str(stk)]
            if mode == "corner":
                # portrait layout: title 0.10-0.38H, captions (up to 2 lines)
                # 0.37-0.63H, subject chip 0.94H -> only safe band is
                # 0.64-0.92H. Corner reaction pinned RIGHT side there;
                # landscape keeps upper corners.
                if portrait:
                    xpos = f"W-w-{int(W*0.05)}"
                    ybase = int(H * 0.70)
                else:
                    xpos = random.choice([f"W-w-{int(W*0.06)}",
                                          f"{int(W*0.06)}"])
                    ybase = int(H * 0.13)
                ypos = f"{ybase}+{int(H*0.02)}*abs(sin(2*PI*(t-{t0:.2f})*1.4))"
                enable = f"gte(t,{t0:.2f})"
            else:
                # keyword pops: portrait -> LEFT side of the safe lower band
                # (opposite the corner emoji so they never collide);
                # landscape -> just above the center captions.
                if portrait:
                    xpos = f"{int(W*0.07)}"
                    ytarget = int(H * 0.66)
                else:
                    xpos = (f"(W-w)/2+"
                            f"{random.choice([-int(W*0.18), int(W*0.18)])}")
                    ytarget = int(H * 0.26)
                ypos = f"{ytarget}-{int(H*0.02)}*sin(min(1,(t-{t0:.2f})*4)*PI)"
                enable = f"between(t,{t0:.2f},{t0 + life:.2f})"
            fc_parts.append(
                f"[{idx}:v]format=rgba,rotate=0.10*sin(2*PI*t*0.9):c=none,"
                f"fade=t=in:st={t0:.2f}:d=0.18:alpha=1[s{n}];"
                f"{vprev}[s{n}]overlay=x='{xpos}':y='{ypos}':"
                f"enable='{enable}':shortest=1[v{n}]")
            vprev = f"[v{n}]"
            idx += 1
            if pop.exists():
                sfx_labels.append((t0, len(sfx_labels)))
        amap = "0:a"
        if pop.exists() and sfx_labels:
            for t0, j in sfx_labels:
                fc_parts.append(
                    f"[{idx}:a]adelay={int(t0*1000)}|{int(t0*1000)},"
                    f"volume=0.65[p{j}]")
                inputs += ["-i", str(pop)]
                idx += 1
            mix = "".join(f"[p{j}]" for _, j in sfx_labels)
            fc_parts.append(f"[0:a]{mix}amix=inputs={len(sfx_labels)+1}:"
                            f"duration=first:normalize=0[a]")
            amap = "[a]"
        if ok and fc_parts:
            out2 = seg_dir / f"clip_{i:03d}_e.mp4"
            try:
                _run(["ffmpeg", "-y", *inputs,
                      "-filter_complex", ";".join(fc_parts),
                      "-map", vprev, "-map", amap, "-t", f"{dur:.3f}",
                      "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                      "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                      "-pix_fmt", "yuv420p", str(out2)])
                return out2
            except Exception:
                pass
    return out


def concat_with_transitions(clips: list[Path], out: Path, whoosh: bool = True):
    """Join clips with animated xfade transitions + whoosh SFX at each cut."""
    TD = 0.35  # transition duration
    if len(clips) == 1:
        shutil.copy(clips[0], out)
        return []
    durs = [_dur(c) for c in clips]
    inputs = []
    for c in clips:
        inputs += ["-i", str(c)]
    fc, offsets = [], []
    cum = durs[0]
    vprev, aprev = "[0:v]", "[0:a]"
    for i in range(1, len(clips)):
        off = cum - TD
        offsets.append(off)
        trans = random.choice(TRANSITIONS)
        vout, aout = f"[v{i}]", f"[a{i}]"
        fc.append(f"{vprev}[{i}:v]xfade=transition={trans}:"
                  f"duration={TD}:offset={off:.3f}{vout}")
        fc.append(f"{aprev}[{i}:a]acrossfade=d={TD}{aout}")
        vprev, aprev = vout, aout
        cum += durs[i] - TD
    # whoosh SFX layered at every transition
    whoosh_file = SFX / "whoosh.wav"
    amap = aprev
    if whoosh and whoosh_file.exists() and offsets:
        n = len(clips)
        wmix = []
        for j, off in enumerate(offsets):
            fc.append(f"[{n}:a]adelay={int(off*1000)}|{int(off*1000)},"
                      f"volume=0.5[w{j}]")
            wmix.append(f"[w{j}]")
        fc.append(f"{aprev}{''.join(wmix)}amix=inputs={len(wmix)+1}:"
                  f"duration=first:normalize=0[afin]")
        inputs += ["-i", str(whoosh_file)]
        amap = "[afin]"
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc),
          "-map", vprev, "-map", amap, "-r", "30",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
          "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
          "-pix_fmt", "yuv420p", str(out)])
    return offsets


def add_subject_chip(video: Path, subject: str, out: Path, size, portrait):
    """Persistent branded chip naming the checked subject — always visible
    (e.g. 'CHECKING: HONEYGAIN'). Keeps the video honest & searchable."""
    W, H = size
    label = f"CHECKING: {subject.upper()[:26]}"
    fs = int(H * (0.028 if portrait else 0.034))
    y = int(H * (0.945 if portrait else 0.93))
    safe = label.replace("'", r"\\\'").replace(":", r"\:")
    vf = (f"drawtext=fontfile='{FONT_BOLD}':text='{safe}':fontsize={fs}:"
          f"fontcolor=0x00E5A0:box=1:boxcolor=black@0.65:boxborderw=14:"
          f"x=(w-text_w)/2:y={y}")
    _run(["ffmpeg", "-y", "-i", str(video), "-vf", vf,
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
          "-c:a", "copy", str(out)])


def render(slug: str, script: dict, seg_meta: list[dict],
           all_words: list[list[dict]]) -> Path:
    cfg = load_config()
    kind = script["kind"]
    portrait = kind == "short"
    size = tuple(cfg["video"]["short" if portrait else "long"]["resolution"])

    dossier = json.loads((WORK_DIR / slug / "dossier.json").read_text(encoding="utf-8"))
    shots = {s["name"]: s for s in dossier.get("screenshots", [])
             if Path(s["path"]).exists()}

    clips = []
    for i, seg in enumerate(script["segments"]):
        dur = seg_meta[i]["duration"] + 0.18   # tiny breath between segments
        words = all_words[i] if i < len(all_words) else []
        clips.append(build_segment(slug, i, seg, dur, words, shots, size, portrait))

    # join with animated transitions + whoosh SFX
    joined = WORK_DIR / slug / f"joined_{kind}.mp4"
    concat_with_transitions(clips, joined)

    # mood-matched music bed with sidechain ducking
    final = WORK_DIR / slug / f"final_{kind}.mp4"
    mood = script.get("music_mood", "tension")
    music_files = (list((ASSETS / "music" / mood).glob("*.mp3")) or
                   list((ASSETS / "music").glob("*.mp3")))
    if music_files:
        music = random.choice(music_files)
        vol = cfg["video"].get("music_volume_db", -24)
        _run(["ffmpeg", "-y", "-i", str(joined), "-stream_loop", "-1",
              "-i", str(music), "-filter_complex",
              f"[1:a]volume={vol}dB[m];"
              f"[m][0:a]sidechaincompress=threshold=0.05:ratio=8:attack=40:release=400[md];"
              f"[0:a][md]amix=inputs=2:duration=first:normalize=0[a]",
              "-map", "0:v", "-map", "[a]", "-c:v", "copy",
              "-c:a", "aac", "-b:a", "192k", str(final)])
    else:
        shutil.copy(joined, final)

    # persistent subject chip so the checked app/site is ALWAYS named on screen
    subject = dossier.get("topic", {}).get("subject")
    if subject:
        chipped = WORK_DIR / slug / f"final_{kind}_chip.mp4"
        try:
            add_subject_chip(final, subject, chipped, size, portrait)
            return chipped
        except Exception:
            pass
    return final
