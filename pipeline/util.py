"""Shared utilities: config, state, LLM client, HTTP session."""
import json, os, re, time, random, pathlib
import yaml
import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state"
WORK_DIR = ROOT / "work"
ASSETS = ROOT / "assets"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def load_config() -> dict:
    with open(ROOT / "config" / "channel.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def http() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return s


# ---------------- state (history of covered topics, learnings) ------------
def _state_path(name: str) -> pathlib.Path:
    STATE_DIR.mkdir(exist_ok=True)
    return STATE_DIR / f"{name}.json"


def load_state(name: str, default):
    p = _state_path(name)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def save_state(name: str, data):
    _state_path(name).write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                 encoding="utf-8")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


# ---------------- Gemini (free tier) ---------------------------------------
# Preferred model names (aliases first — Google keeps "-latest" aliases
# pointing at current models even as versioned names get retired).
GEMINI_MODELS = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]
_discovered_models: list | None = None


def _list_gemini_models(key: str) -> list:
    """Ask the API which generateContent-capable flash models exist NOW.
    Makes the pipeline immune to Google renaming/retiring models."""
    global _discovered_models
    if _discovered_models is not None:
        return _discovered_models
    models = []
    try:
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models"
            f"?key={key}&pageSize=200", timeout=30)
        r.raise_for_status()
        for m in r.json().get("models", []):
            name = m.get("name", "").removeprefix("models/")
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" not in methods:
                continue
            low = name.lower()
            # prefer cheap/fast flash-family text models; skip specialty ones
            if "flash" in low and not any(
                    x in low for x in ("image", "audio", "tts", "live",
                                       "embed", "thinking", "exp")):
                models.append(name)
    except Exception:  # noqa: BLE001
        pass
    # newest first (rough sort: version number desc, shorter names first)
    models.sort(key=lambda n: (n, len(n)), reverse=True)
    _discovered_models = models
    return models


def gemini(prompt: str, system: str = "", json_mode: bool = False,
           temperature: float = 0.9, max_retries: int = 4) -> str:
    """Call Gemini REST API with model fallback + backoff (free tier friendly)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY env var missing")
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 8192},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"

    # static preferred list + whatever the API says actually exists today
    candidates = list(GEMINI_MODELS)
    for m in _list_gemini_models(key):
        if m not in candidates:
            candidates.append(m)

    last_err = None
    for model in candidates:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={key}")
        for attempt in range(max_retries):
            try:
                r = requests.post(url, json=body, timeout=120)
                if r.status_code == 404:      # model retired -> next model
                    last_err = f"404 model not found: {model}"
                    break
                if r.status_code == 429:      # rate limited -> backoff
                    time.sleep(8 * (attempt + 1) + random.random() * 4)
                    continue
                r.raise_for_status()
                data = r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"Gemini failed on all models: {last_err}")


def gemini_json(prompt: str, system: str = "", temperature: float = 0.9):
    txt = gemini(prompt, system=system, json_mode=True, temperature=temperature)
    txt = re.sub(r"^```(json)?|```$", "", txt.strip(), flags=re.M).strip()
    return json.loads(txt)


def gemini_vision_json(prompt: str, image_path: str,
                       temperature: float = 0.3, max_retries: int = 3):
    """Send an IMAGE + prompt to Gemini, get JSON back. Used to make the
    bot actually READ the screenshots it's about to show as proof."""
    import base64
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY env var missing")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    body = {
        "contents": [{"role": "user", "parts": [
            {"inlineData": {"mimeType": "image/png", "data": b64}},
            {"text": prompt}]}],
        "generationConfig": {"temperature": temperature,
                             "maxOutputTokens": 8192,
                             "responseMimeType": "application/json"},
    }
    candidates = list(GEMINI_MODELS)
    for m in _list_gemini_models(key):
        if m not in candidates:
            candidates.append(m)
    last_err = None
    for model in candidates:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={key}")
        for attempt in range(max_retries):
            try:
                r = requests.post(url, json=body, timeout=150)
                if r.status_code == 404:
                    last_err = f"404: {model}"
                    break
                if r.status_code == 429:
                    time.sleep(8 * (attempt + 1) + random.random() * 4)
                    continue
                r.raise_for_status()
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                txt = re.sub(r"^```(json)?|```$", "", txt.strip(),
                             flags=re.M).strip()
                return json.loads(txt)
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"Gemini vision failed on all models: {last_err}")
