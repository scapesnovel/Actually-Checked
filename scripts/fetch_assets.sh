#!/usr/bin/env bash
# Fetch free fonts (SIL OFL) and background music (Pixabay CC0 / local).
# Idempotent — skips anything already present.
set -e
cd "$(dirname "$0")/.."

mkdir -p assets/fonts assets/music

# Anton (SIL OFL) — captions / thumbnails
if [ ! -f assets/fonts/Anton-Regular.ttf ]; then
  curl -sL -o assets/fonts/Anton-Regular.ttf \
    "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf" || true
fi
# Inter Bold (SIL OFL) — secondary text
if [ ! -f assets/fonts/Inter-Bold.ttf ]; then
  curl -sL -o assets/fonts/Inter-Bold.ttf \
    "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf" || true
fi

# Background music: prefer tracks committed to assets/music/ (drop in any
# YouTube Audio Library mp3s). Fallback: generate two subtle synth beds with
# ffmpeg so the pipeline always has music.
count=$(ls assets/music/*.mp3 2>/dev/null | wc -l || echo 0)
if [ "$count" -lt 1 ]; then
  echo "No music found — generating subtle ambient beds with ffmpeg..."
  ffmpeg -y -f lavfi -i "sine=frequency=110:duration=90" \
    -f lavfi -i "sine=frequency=220:duration=90" \
    -f lavfi -i "anoisesrc=color=brown:duration=90:amplitude=0.03" \
    -filter_complex "[0:a]volume=0.12[a0];[1:a]volume=0.06,atempo=1.0[a1];[2:a]volume=0.5[a2];[a0][a1][a2]amix=inputs=3,highpass=f=60,lowpass=f=2000,aecho=0.6:0.4:60:0.3[out]" \
    -map "[out]" -q:a 5 assets/music/ambient_bed_1.mp3 2>/dev/null || true
  ffmpeg -y -f lavfi -i "sine=frequency=146.83:duration=90" \
    -f lavfi -i "sine=frequency=196:duration=90" \
    -filter_complex "[0:a]volume=0.10[a0];[1:a]volume=0.07[a1];[a0][a1]amix=inputs=2,lowpass=f=1500,aecho=0.7:0.5:80:0.35[out]" \
    -map "[out]" -q:a 5 assets/music/ambient_bed_2.mp3 2>/dev/null || true
fi
echo "Assets ready."

# Noto Color Emoji (for popping emoji stickers)
if [ ! -f assets/fonts/NotoColorEmoji.ttf ]; then
  curl -sL -o assets/fonts/NotoColorEmoji.ttf \
    "https://github.com/googlefonts/noto-emoji/raw/main/fonts/NotoColorEmoji.ttf" || true
fi

# Sound effects (generated once, free): whoosh + pop + ding
mkdir -p assets/sfx
if [ ! -f assets/sfx/whoosh.wav ]; then
  ffmpeg -y -f lavfi -i "anoisesrc=d=0.45:color=pink:amplitude=0.7" \
    -af "highpass=f=300,lowpass=f=5000,afade=t=in:d=0.08,afade=t=out:st=0.15:d=0.3,volume=0.9" \
    assets/sfx/whoosh.wav 2>/dev/null || true
fi
if [ ! -f assets/sfx/pop.wav ]; then
  ffmpeg -y -f lavfi -i "sine=frequency=740:duration=0.09" \
    -af "afade=t=in:d=0.01,afade=t=out:st=0.04:d=0.05,volume=0.8" \
    assets/sfx/pop.wav 2>/dev/null || true
fi
if [ ! -f assets/sfx/ding.wav ]; then
  ffmpeg -y -f lavfi -i "sine=frequency=1320:duration=0.35" \
    -af "afade=t=out:st=0.05:d=0.3,volume=0.5" assets/sfx/ding.wav 2>/dev/null || true
fi

# Mood music folders (drop YT Audio Library mp3s in; generated fallbacks)
mkdir -p assets/music/tension assets/music/chill assets/music/upbeat
if [ ! -f assets/music/tension/bed.mp3 ] && [ -z "$(ls assets/music/tension/*.mp3 2>/dev/null)" ]; then
  ffmpeg -y -f lavfi -i "sine=frequency=82.4:duration=90" -f lavfi -i "sine=frequency=110:duration=90" \
    -f lavfi -i "anoisesrc=color=brown:duration=90:amplitude=0.02" \
    -filter_complex "[0:a]volume=0.14,tremolo=f=2:d=0.6[a0];[1:a]volume=0.07[a1];[2:a]volume=0.5[a2];[a0][a1][a2]amix=inputs=3,lowpass=f=900[out]" \
    -map "[out]" -q:a 5 assets/music/tension/bed.mp3 2>/dev/null || true
fi
if [ -z "$(ls assets/music/chill/*.mp3 2>/dev/null)" ]; then
  cp assets/music/ambient_bed_1.mp3 assets/music/chill/bed.mp3 2>/dev/null || true
fi
if [ -z "$(ls assets/music/upbeat/*.mp3 2>/dev/null)" ]; then
  ffmpeg -y -f lavfi -i "sine=frequency=196:duration=90" -f lavfi -i "sine=frequency=246.9:duration=90" \
    -filter_complex "[0:a]volume=0.10,tremolo=f=4:d=0.7[a0];[1:a]volume=0.06,tremolo=f=8:d=0.5[a1];[a0][a1]amix=inputs=2,lowpass=f=1800[out]" \
    -map "[out]" -q:a 5 assets/music/upbeat/bed.mp3 2>/dev/null || true
fi
echo "Extended assets ready."

# Install caption font system-wide so libass always resolves "Anton"
mkdir -p ~/.fonts && cp -f assets/fonts/Anton-Regular.ttf ~/.fonts/ 2>/dev/null || true
command -v fc-cache >/dev/null && fc-cache -f >/dev/null 2>&1 || true
