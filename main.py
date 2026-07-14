"""
=============================================================
  Anki Vocabulary Deck Generator  v2.0
  Generates rich Anki flashcards for any language using
  AI-generated content (Groq), animated GIFs (Giphy),
  and text-to-speech audio (gTTS).
=============================================================
  Quick start:
    1. Edit config.py with your API keys and preferences.
    2. Activate your virtual environment:
         source venv/bin/activate
    3. Install dependencies:
         pip install genanki gTTS wordfreq requests
    4. Run:
         python main.py
    5. Import deck_new.apkg into Anki.

  Non-interactive (for automation / cron jobs):
         python main.py --run

  Daily usage:
    Run -> import deck_new.apkg -> repeat tomorrow.
    Your manual edits in Anki are always preserved.
=============================================================
"""

import os
import re
import sys
import time
import json
import sqlite3
import hashlib
import requests
import genanki
from gtts import gTTS
from wordfreq import top_n_list

import config
import template as tmpl_registry


# ─────────────────────────────────────────────
#  Terminal UI helpers
# ─────────────────────────────────────────────

_ANSI_RE = re.compile(r'\033\[[0-9;]*m')

_CODES = {
    'bold':   '\033[1m',
    'dim':    '\033[2m',
    'cyan':   '\033[96m',
    'green':  '\033[92m',
    'yellow': '\033[93m',
    'red':    '\033[91m',
    'blue':   '\033[94m',
    'reset':  '\033[0m',
}
_W = 58  # visible width of box interior (between the ║ borders)


def col(text, *codes):
    """Wrap text in ANSI color codes."""
    return ''.join(_CODES[k] for k in codes) + str(text) + _CODES['reset']


def _vlen(text):
    """Visible length of text (strips ANSI codes before measuring)."""
    return len(_ANSI_RE.sub('', text))


def _clear():
    print('\033[2J\033[H', end='', flush=True)


def _hline(ch='═'):
    return ch * _W


def _row(text=''):
    """Format one box row. text may contain ANSI codes; padding uses visible length."""
    pad = _W - 2 - _vlen(text)
    return f'║ {text}{" " * max(0, pad)} ║'


def print_banner():
    _clear()
    title    = col('  Anki Vocabulary Deck Generator  v2.0  ', 'bold', 'cyan')
    lang     = col(f'  Language : {config.SOURCE_LANG.upper()} -> {config.TARGET_LANG}', 'yellow')
    tmpl     = col(f'  Template : {config.CARD_TEMPLATE}   |   Card type : {config.CARD_TYPE}', 'dim')
    provider = AI_PROVIDER_LABELS.get(current_ai_provider(), current_ai_provider())
    model    = col(f'  AI provider : {provider}   |   Model : {current_ai_model()}', 'dim')
    print('╔' + _hline() + '╗')
    print(_row(title))
    print('╠' + _hline() + '╣')
    print(_row(lang))
    print(_row(tmpl))
    print(_row(model))
    print('╚' + _hline() + '╝')
    print()


def print_menu(title, options):
    """
    Print a numbered menu.
    options: list of (key, label, description) tuples.
    """
    print(f'  {col(title, "bold", "cyan")}')
    print(f'  {"─" * 52}')
    for key, label, desc in options:
        k = col(f'[{key}]', 'yellow', 'bold')
        lb = col(label, 'bold')
        print(f'  {k}  {lb}')
        if desc:
            print(f'       {col(desc, "dim")}')
    print()


def ask(prompt):
    """Styled prompt for user input."""
    try:
        return input(f'  {col(">>", "cyan", "bold")} {prompt}: ').strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return '0'


def pause():
    try:
        input(f'\n  {col("Press Enter to continue...", "dim")}')
    except (EOFError, KeyboardInterrupt):
        pass


# ─────────────────────────────────────────────
#  Database
# ─────────────────────────────────────────────

def init_db():
    """Initialize SQLite database and apply any pending migrations."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            word                     TEXT    NOT NULL,
            word_label               TEXT    NOT NULL,
            meaning_id               INTEGER NOT NULL,
            pos                      TEXT    DEFAULT '',
            ipa                      TEXT    DEFAULT '',
            text_meaning             TEXT    DEFAULT '',
            text_example_phrase      TEXT    DEFAULT '',
            text_example_translation TEXT    DEFAULT '',
            synonyms                 TEXT    DEFAULT '',
            audio_word               TEXT    DEFAULT '',
            audio_meaning            TEXT    DEFAULT '',
            audio_example            TEXT    DEFAULT '',
            gif_url                  TEXT    DEFAULT '',
            gif_raw_url              TEXT    DEFAULT '',
            gender                   TEXT    DEFAULT '',
            exported                 INTEGER DEFAULT 0,
            date_added               TEXT    DEFAULT (date('now')),
            UNIQUE(word, meaning_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS export_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    DEFAULT (datetime('now')),
            type       TEXT,
            card_count INTEGER DEFAULT 0
        )
    """)
    migrations = [
        ("word_label",               "TEXT DEFAULT ''"),
        ("pos",                      "TEXT DEFAULT ''"),
        ("gif_url",                  "TEXT DEFAULT ''"),
        ("gif_raw_url",              "TEXT DEFAULT ''"),
        ("gender",                   "TEXT DEFAULT ''"),
        ("text_example_translation", "TEXT DEFAULT ''"),
        ("exported",                 "INTEGER DEFAULT 0"),
    ]
    for column, definition in migrations:
        try:
            conn.execute(f"ALTER TABLE cards ADD COLUMN {column} {definition}")
        except Exception:
            pass
    conn.commit()
    return conn


def card_exists(conn, word, meaning_id):
    return conn.execute(
        "SELECT 1 FROM cards WHERE word=? AND meaning_id=?",
        (word, meaning_id)
    ).fetchone() is not None


def word_already_processed(conn, word):
    return conn.execute(
        "SELECT 1 FROM cards WHERE word=?", (word,)
    ).fetchone() is not None


def save_card(conn, data):
    conn.execute("""
        INSERT OR IGNORE INTO cards
            (word, word_label, meaning_id, pos, ipa,
             text_meaning, text_example_phrase, text_example_translation,
             synonyms, audio_word, audio_meaning, audio_example,
             gif_url, gif_raw_url, gender)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data["word"],
        data.get("word_label", data["word"]),
        data["meaning_id"],
        data.get("pos", ""),
        data.get("ipa", ""),
        data.get("text_meaning", ""),
        data.get("text_example_phrase", ""),
        data.get("text_example_translation", ""),
        data.get("synonyms", ""),
        data.get("audio_word", ""),
        data.get("audio_meaning", ""),
        data.get("audio_example", ""),
        data.get("gif_url", ""),
        data.get("gif_raw_url", ""),
        data.get("gender", ""),
    ))
    conn.commit()


def get_processed_words(conn):
    rows = conn.execute("SELECT DISTINCT word FROM cards").fetchall()
    return {r[0] for r in rows}


def get_all_cards(conn, new_only=False):
    filter_clause = "AND exported = 0" if new_only else ""
    return conn.execute(f"""
        SELECT word_label, ipa, text_meaning, text_example_phrase,
               text_example_translation, synonyms, audio_word,
               audio_meaning, audio_example, gif_url, gif_raw_url,
               gender, word, id
        FROM cards
        WHERE text_example_phrase NOT LIKE '[no sentence]%'
          AND text_example_phrase != ''
          {filter_clause}
        ORDER BY id
    """).fetchall()


def mark_as_exported(conn, ids):
    conn.executemany(
        "UPDATE cards SET exported = 1 WHERE id = ?",
        [(i,) for i in ids]
    )
    conn.commit()


# ─────────────────────────────────────────────
#  POS -> Anki tag mapping
# ─────────────────────────────────────────────

POS_TAG_MAP = {
    "noun":         "Noun",
    "verb":         "Verb",
    "adjective":    "Adjective",
    "adverb":       "Adverb",
    "pronoun":      "Pronoun",
    "preposition":  "Preposition",
    "conjunction":  "Conjunction",
    "article":      "Article",
    "interjection": "Interjection",
    "numeral":      "Numeral",
    "determiner":   "Determiner",
    "particle":     "Particle",
}


def pos_to_tag(pos_str):
    if not pos_str:
        return "Other"
    key = pos_str.strip().lower()
    for k, v in POS_TAG_MAP.items():
        if k in key:
            return v
    return pos_str.strip().replace(" ", "_")


# ─────────────────────────────────────────────
#  AI content generation (multi-provider)
# ─────────────────────────────────────────────

GROQ_URL        = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL      = "https://api.openai.com/v1/chat/completions"
GEMINI_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

AI_HEADERS = {
    "Authorization": f"Bearer {config.GROQ_API_KEY}",
    "Content-Type":  "application/json",
}

# Providers whose credential is an API key checked against the config.py
# placeholder. Ollama runs locally and needs no key.
AI_PROVIDER_KEY_FIELD = {
    "groq":      "GROQ_API_KEY",
    "openai":    "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini":    "GEMINI_API_KEY",
}

AI_PROVIDER_MODEL_FIELD = {
    "groq":      "AI_MODEL",
    "openai":    "OPENAI_MODEL",
    "anthropic": "ANTHROPIC_MODEL",
    "gemini":    "GEMINI_MODEL",
    "ollama":    "OLLAMA_MODEL",
}

AI_PROVIDER_LABELS = {
    "groq":      "Groq",
    "openai":    "OpenAI",
    "anthropic": "Claude",
    "gemini":    "Gemini",
    "ollama":    "Ollama",
}


def current_ai_provider():
    return getattr(config, "AI_PROVIDER", "groq")


def current_ai_model():
    field = AI_PROVIDER_MODEL_FIELD.get(current_ai_provider(), "AI_MODEL")
    return getattr(config, field, "")


def ai_key_missing():
    """True if the active provider needs a key and it hasn't been set."""
    field = AI_PROVIDER_KEY_FIELD.get(current_ai_provider())
    if field is None:  # ollama — no key required
        return False
    return getattr(config, field, "").startswith("your_")


PROMPT_TEMPLATE = """You are a language expert creating Anki flashcard content \
for {target_lang} speakers learning {source_lang}.

For the word "{word}", generate flashcard data for ALL its distinct and relevant meanings.

Return ONLY a valid JSON object (no markdown, no explanation) with this exact structure:
{{
  "ipa": "IPA transcription for {source_lang} pronunciation (e.g. mɛ.zɔ̃)",
  "meanings": [
    {{
      "pos": "part of speech in English (Noun / Verb / Adjective / Adverb / etc.)",
      "gender": "For nouns only: 'Masculine' or 'Feminine'. Empty string for all other parts of speech.",
      "text_meaning": "A single clear sentence in {target_lang} explaining this meaning. \
Start with 'To [word] means...' for verbs, 'If something/someone is [word]...' for adjectives, \
or '[Word] is/refers to...' for nouns. Keep it concise like a dictionary entry.",
      "text_example_phrase": "A natural sentence in {source_lang} (10-15 words) using the word \
in this specific meaning. Make it vivid and memorable with real context.",
      "text_example_translation": "The {target_lang} translation of the example sentence above. \
Keep it natural, not word-for-word literal.",
      "synonyms": "up to 6 relevant {source_lang} synonyms for this meaning, comma-separated",
      "gif_keywords": ["exactly 3 English single-word keywords that together visually represent \
this meaning and example sentence. Focus on the action, object, and setting. \
Example for a clock melting: ['melting', 'clock', 'fire']. \
Example for someone teasing: ['teasing', 'laughing', 'school']."]
    }}
  ]
}}

Rules:
- Only include meanings that are genuinely distinct and useful for a language learner
- The example sentence must clearly illustrate the specific meaning listed
- Synonyms must be in {source_lang}
- IPA must be standard {source_lang} IPA notation
- gif_keywords must be exactly 3 English single words
- gender must be 'Masculine' or 'Feminine' for nouns only, empty string otherwise
- text_example_translation must be a natural {target_lang} translation of the example
- Return raw JSON only — no markdown fences, no extra text"""


def _clean_json_text(raw):
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return json.loads(raw)


def _call_groq(prompt):
    payload = {
        "model":       config.AI_MODEL,
        "temperature": 0.3,
        "max_tokens":  1024,
        "messages":    [{"role": "user", "content": prompt}],
    }
    resp = requests.post(GROQ_URL, headers=AI_HEADERS, json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"    [Groq] HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()["choices"][0]["message"]["content"]


def _call_openai(prompt):
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       config.OPENAI_MODEL,
        "temperature": 0.3,
        "max_tokens":  1024,
        "messages":    [{"role": "user", "content": prompt}],
    }
    resp = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"    [OpenAI] HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()["choices"][0]["message"]["content"]


def _call_anthropic(prompt):
    try:
        import anthropic
    except ImportError:
        print("    [Claude] Missing dependency — run: pip install anthropic")
        return None
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return next((b.text for b in response.content if b.type == "text"), "")


def _call_gemini(prompt):
    url = GEMINI_URL_TMPL.format(model=config.GEMINI_MODEL)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
    }
    resp = requests.post(
        url, params={"key": config.GEMINI_API_KEY}, json=payload, timeout=30
    )
    if resp.status_code != 200:
        print(f"    [Gemini] HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    candidates = resp.json().get("candidates", [])
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts)


def _call_ollama(prompt):
    url = f"{config.OLLAMA_HOST.rstrip('/')}/api/chat"
    payload = {
        "model":    config.OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream":   False,
        "options":  {"temperature": 0.3},
    }
    resp = requests.post(url, json=payload, timeout=120)
    if resp.status_code != 200:
        print(f"    [Ollama] HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json().get("message", {}).get("content", "")


AI_PROVIDER_CALLERS = {
    "groq":      _call_groq,
    "openai":    _call_openai,
    "anthropic": _call_anthropic,
    "gemini":    _call_gemini,
    "ollama":    _call_ollama,
}


def generate_card_content(word):
    prompt = PROMPT_TEMPLATE.format(
        word=word,
        source_lang=config.SOURCE_LANG,
        target_lang=config.TARGET_LANG,
    )
    provider = current_ai_provider()
    label    = AI_PROVIDER_LABELS.get(provider, provider)
    call_fn  = AI_PROVIDER_CALLERS.get(provider, _call_groq)
    try:
        raw = call_fn(prompt)
        if not raw:
            return None
        return _clean_json_text(raw)
    except json.JSONDecodeError as e:
        print(f"    [{label}] Invalid JSON for '{word}': {e}")
        return None
    except Exception as e:
        print(f"    [{label}] Error for '{word}': {e}")
        return None


# ─────────────────────────────────────────────
#  GIF search (Giphy)
# ─────────────────────────────────────────────

def fetch_gif(keywords):
    if not config.ENABLE_GIF or not config.GIPHY_API_KEY:
        return "", ""
    query = " ".join(f"#{kw.strip().lower()}" for kw in keywords if kw.strip())
    try:
        resp = requests.get(
            "https://api.giphy.com/v1/gifs/search",
            params={
                "api_key": config.GIPHY_API_KEY,
                "q":       query,
                "limit":   5,
                "rating":  config.GIF_RATING,
                "lang":    "en",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return "", ""
        data = resp.json().get("data", [])
        if not data:
            return "", ""
        gif_url = data[0].get("images", {}).get("downsized", {}).get("url", "")
        if not gif_url:
            return "", ""
        img_tag = (
            f'<img src="{gif_url}" '
            f'style="max-width:260px;max-height:180px;'
            f'border-radius:10px;margin:10px auto;display:block;">'
        )
        return img_tag, gif_url
    except Exception as e:
        print(f"    [Giphy] Error: {e}")
        return "", ""


# ─────────────────────────────────────────────
#  Audio generation (gTTS)
# ─────────────────────────────────────────────

def generate_audio(text, lang):
    if not config.ENABLE_AUDIO:
        return "", ""
    os.makedirs(config.AUDIO_DIR, exist_ok=True)
    filename = hashlib.md5((text + lang).encode()).hexdigest() + ".mp3"
    path     = os.path.join(config.AUDIO_DIR, filename)
    if not os.path.exists(path):
        gTTS(text=text, lang=lang).save(path)
        time.sleep(config.DELAY_TTS)
    return path, filename


# ─────────────────────────────────────────────
#  Formatting helpers
# ─────────────────────────────────────────────

def highlight_word(sentence, word):
    """Wrap the target word in a styled <span> inside the example sentence."""
    pattern = re.compile(re.escape(word), re.IGNORECASE)
    return pattern.sub(
        lambda m: f'<span class="highlight">{m.group()}</span>', sentence
    )


def make_cloze_text(sentence, word):
    """Replace the target word with Anki cloze notation {{c1::word}}."""
    pattern = re.compile(re.escape(word), re.IGNORECASE)
    return pattern.sub(
        lambda m: '{{c1::' + m.group() + '}}', sentence, count=1
    )


def format_synonyms(synonyms_str):
    if not synonyms_str:
        return ""
    badges = "".join(
        f'<span class="syn-badge">{s.strip()}</span>'
        for s in synonyms_str.split(",") if s.strip()
    )
    return f'<div class="synonyms-wrap">{badges}</div>'


def gender_badge(gender):
    if not gender:
        return ""
    if gender.lower().startswith("m"):
        return '<span class="gender-badge gender-m">♂ Masculine</span>'
    if gender.lower().startswith("f"):
        return '<span class="gender-badge gender-f">♀ Feminine</span>'
    return ""


def sound_tag(audio_path):
    if audio_path and os.path.exists(audio_path):
        return f"[sound:{os.path.basename(audio_path)}]"
    return ""


# ─────────────────────────────────────────────
#  Anki model builder
# ─────────────────────────────────────────────

_CARD_TYPE_LABELS = {
    "basic":          "Basic",
    "basic_reversed": "Basic + Reversed",
    "type_answer":    "Type in Answer",
    "cloze":          "Cloze",
}

_REVERSED_FRONT = """
<div class="meaning">{{Text_Meaning}}</div>
<div class="example-translation">{{Text_Example_Translation}}</div>
{{Sound_Meaning}}
"""

_REVERSED_BACK = """
{{FrontSide}}
<hr>
<div class="word">{{Word}}</div>
<div class="ipa">/ {{IPA}} /</div>
{{Gender}}
<div class="gif-box">{{Image}}</div>
<div class="example">{{Text_Example_Phrase}}</div>
{{Sound_Word}}{{Sound_Example}}
{{Synonyms}}
"""

_TYPE_FRONT = """
<div class="ipa">/ {{IPA}} /</div>
<div class="meaning">{{Text_Meaning}}</div>
<div class="example-translation">{{Text_Example_Translation}}</div>
{{Sound_Meaning}}
<br>
{{type:Word}}
"""

_TYPE_BACK = """
{{FrontSide}}
<hr>
<div class="word">{{Word}}</div>
{{Gender}}
<div class="gif-box">{{Image}}</div>
<div class="example">{{Text_Example_Phrase}}</div>
{{Sound_Word}}{{Sound_Example}}
{{Synonyms}}
"""


def build_anki_model(template, card_type=None):
    """
    Build a genanki Model.
    card_type: "basic" | "basic_reversed" | "type_answer" | "cloze"
    Defaults to config.CARD_TYPE if not specified.
    """
    if card_type is None:
        card_type = config.CARD_TYPE

    if card_type == "cloze":
        return genanki.Model(
            config.MODEL_ID + 10,
            f"{config.DECK_NAME} Cloze Model",
            fields=[
                {"name": "Cloze_Text"},
                {"name": "Word"},
                {"name": "IPA"},
                {"name": "Text_Meaning"},
                {"name": "Image"},
                {"name": "Sound_Word"},
                {"name": "Sound_Example"},
                {"name": "Synonyms"},
                {"name": "Gender"},
            ],
            templates=[{
                "name": "Cloze",
                "qfmt": (
                    "{{cloze:Cloze_Text}}<br>"
                    "<div class='gif-box'>{{Image}}</div>"
                    "{{Sound_Word}}"
                ),
                "afmt": (
                    "{{cloze:Cloze_Text}}<br>"
                    "<div class='gif-box'>{{Image}}</div>"
                    "<hr>"
                    "<div class='meaning'>{{Text_Meaning}}</div>"
                    "{{Synonyms}}{{Sound_Example}}"
                ),
            }],
            css=template.CSS,
            model_type=genanki.Model.CLOZE,
        )

    # All non-cloze types share the same base fields
    fields = [
        {"name": "Word"},
        {"name": "Image"},
        {"name": "Sound_Word"},
        {"name": "Sound_Meaning"},
        {"name": "Sound_Example"},
        {"name": "Text_Meaning"},
        {"name": "Text_Example_Phrase"},
        {"name": "Text_Example_Translation"},
        {"name": "IPA"},
        {"name": "Gender"},
        {"name": "Synonyms"},
    ]
    if getattr(template, "REQUIRES_RAW_IMAGE", False):
        fields.append({"name": "Image_Raw"})

    if card_type == "basic_reversed":
        card_templates = [
            {"name": "Word -> Meaning", "qfmt": template.FRONT, "afmt": template.BACK},
            {"name": "Meaning -> Word", "qfmt": _REVERSED_FRONT, "afmt": _REVERSED_BACK},
        ]
    elif card_type == "type_answer":
        card_templates = [{"name": "Type in Answer", "qfmt": _TYPE_FRONT, "afmt": _TYPE_BACK}]
    else:  # basic
        card_templates = [{"name": "Card", "qfmt": template.FRONT, "afmt": template.BACK}]

    return genanki.Model(
        config.MODEL_ID,
        f"{config.DECK_NAME} Model",
        fields=fields,
        templates=card_templates,
        css=template.CSS,
    )


# ─────────────────────────────────────────────
#  .apkg builder
# ─────────────────────────────────────────────

def build_notes(cards, model, template, card_type=None):
    """Convert database rows into genanki Note objects."""
    if card_type is None:
        card_type = config.CARD_TYPE

    notes     = []
    media     = []
    ids       = []
    needs_raw = getattr(template, "REQUIRES_RAW_IMAGE", False) and card_type != "cloze"

    for row in cards:
        (word_label, ipa, text_meaning, text_example,
         text_example_translation, synonyms, aw, am, ae,
         gif_url, gif_raw_url, gender_str, word, card_id) = row

        synonyms_html = format_synonyms(synonyms)
        gender_html   = gender_badge(gender_str)

        if card_type == "cloze":
            fields = [
                make_cloze_text(text_example, word),           # Cloze_Text
                word_label,                                     # Word
                ipa,                                            # IPA
                text_meaning,                                   # Text_Meaning
                gif_url or "",                                  # Image
                sound_tag(aw) if config.ENABLE_WORD_AUDIO    else "",  # Sound_Word
                sound_tag(ae) if config.ENABLE_EXAMPLE_AUDIO else "",  # Sound_Example
                synonyms_html,                                  # Synonyms
                gender_html,                                    # Gender
            ]
        else:
            fields = [
                word_label,
                gif_url or "",
                sound_tag(aw) if config.ENABLE_WORD_AUDIO    else "",
                sound_tag(am) if config.ENABLE_MEANING_AUDIO else "",
                sound_tag(ae) if config.ENABLE_EXAMPLE_AUDIO else "",
                text_meaning,
                highlight_word(text_example, word),
                text_example_translation,
                ipa,
                gender_html,
                synonyms_html,
            ]
            if needs_raw:
                fields.append(gif_raw_url or "")

        tag = pos_to_tag(
            re.search(r"\(([^)]+)\)", word_label).group(1)
            if re.search(r"\(([^)]+)\)", word_label) else ""
        )
        notes.append(genanki.Note(
            model=model,
            fields=fields,
            tags=[f"vocab::{tag}"],
        ))
        ids.append(card_id)

        for path in [aw, am, ae]:
            if path and os.path.exists(path):
                media.append(path)

    return notes, list(set(media)), ids


def export_decks(conn, template, card_type=None):
    """
    Export two .apkg files:
      - deck_new.apkg   : only cards not yet exported (import this daily)
      - deck_full.apkg  : all cards ever generated (full backup)
    """
    if card_type is None:
        card_type = config.CARD_TYPE

    model = build_anki_model(template, card_type)
    label = _CARD_TYPE_LABELS.get(card_type, card_type)

    # New cards only
    new_cards = get_all_cards(conn, new_only=True)
    if new_cards:
        deck_new = genanki.Deck(config.DECK_ID + 1, f"{config.DECK_NAME} — New")
        pkg_new  = genanki.Package(deck_new)
        notes, media, ids = build_notes(new_cards, model, template, card_type)
        for note in notes:
            deck_new.add_note(note)
        pkg_new.media_files = media
        pkg_new.write_to_file(config.DECK_OUTPUT_NEW)
        mark_as_exported(conn, ids)
        conn.execute(
            "INSERT INTO export_log (type, card_count) VALUES (?, ?)",
            (f"new/{label}", len(new_cards))
        )
        conn.commit()
        print(f"\n[OK] New cards    : {config.DECK_OUTPUT_NEW}  ({len(new_cards)} cards)  [{label}]")
        print(f"     -> Import THIS file into Anki to preserve your manual edits.")
    else:
        print(f"\n[INFO] No new cards to export.")

    # Full backup
    all_cards = get_all_cards(conn, new_only=False)
    deck_full = genanki.Deck(config.DECK_ID, config.DECK_NAME)
    pkg_full  = genanki.Package(deck_full)
    notes_full, media_full, _ = build_notes(all_cards, model, template, card_type)
    for note in notes_full:
        deck_full.add_note(note)
    pkg_full.media_files = media_full
    pkg_full.write_to_file(config.DECK_OUTPUT_FULL)
    conn.execute(
        "INSERT INTO export_log (type, card_count) VALUES (?, ?)",
        (f"full/{label}", len(all_cards))
    )
    conn.commit()
    print(f"    Full backup : {config.DECK_OUTPUT_FULL}  ({len(all_cards)} cards total)  [{label}]")


# ─────────────────────────────────────────────
#  Menu screens
# ─────────────────────────────────────────────

def show_statistics(conn):
    print_banner()
    print(col('  Statistics', 'bold', 'cyan'))
    print(f'  {"─" * 52}')

    total     = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    new_count = conn.execute("SELECT COUNT(*) FROM cards WHERE exported=0").fetchone()[0]
    exported  = conn.execute("SELECT COUNT(*) FROM cards WHERE exported=1").fetchone()[0]

    print(f'\n  Total cards     : {col(str(total), "yellow", "bold")}')
    print(f'  Exported        : {col(str(exported), "green")}')
    print(f'  Pending export  : {col(str(new_count), "cyan")}')
    print()

    rows = conn.execute("""
        SELECT pos, COUNT(*) AS cnt FROM cards
        WHERE pos != ''
        GROUP BY pos ORDER BY cnt DESC
    """).fetchall()
    if rows:
        print(col('  By Part of Speech:', 'bold'))
        for pos, cnt in rows:
            bar = col('█' * min(cnt, 28), 'blue')
            print(f'  {(pos + ":").ljust(16)} {col(str(cnt).rjust(4), "yellow")}  {bar}')
    print()

    rows = conn.execute("""
        SELECT date_added, COUNT(*) FROM cards
        GROUP BY date_added ORDER BY date_added DESC LIMIT 7
    """).fetchall()
    if rows:
        print(col('  Cards added (last 7 sessions):', 'bold'))
        for date, cnt in rows:
            print(f'  {date}   {col(str(cnt) + " cards", "green")}')
    print()

    exports = conn.execute("""
        SELECT date, type, card_count FROM export_log
        ORDER BY date DESC LIMIT 5
    """).fetchall()
    if exports:
        print(col('  Recent exports:', 'bold'))
        for date, etype, cnt in exports:
            print(f'  {date[:16]}  {etype:<22}  {col(str(cnt) + " cards", "cyan")}')
    print()
    pause()


def show_card_types():
    print_banner()
    print(col('  Card Types — How They Work', 'bold', 'cyan'))
    print(f'  {"─" * 52}')
    info = [
        ('Basic',
         'The classic format. Front shows the word, IPA,',
         'GIF and example sentence. Back reveals the meaning.',
         'Best for recognition practice.'),
        ('Basic + Reversed',
         'Creates 2 Anki cards per note. Card 1 is the usual',
         'word->meaning. Card 2 flips it: you see the English',
         'definition and must recall the foreign word.'),
        ('Type in Answer',
         'Front shows the meaning and the example in your native',
         'language. You TYPE the foreign word. Anki checks your',
         'spelling and highlights any mistakes.'),
        ('Cloze',
         'The example sentence is shown with the target word',
         'blanked out: "Elle est tres ___."  You fill the gap.',
         'Great for learning words in context.'),
    ]
    for i, (title, *lines) in enumerate(info, 1):
        print(f'\n  {col(f"[{i}] {title}", "yellow", "bold")}')
        for line in lines:
            print(f'      {col(line, "dim")}')
    print()
    pause()


def select_card_type():
    """Interactive card type selection. Returns chosen card_type string."""
    print_banner()
    options = [
        ('1', 'Basic',
         'Word -> Meaning  |  Classic recognition card'),
        ('2', 'Basic + Reversed',
         'Word <-> Meaning  |  2 cards per note (recognition + recall)'),
        ('3', 'Type in Answer',
         'Definition shown -> user types the word'),
        ('4', 'Cloze',
         'Fill in the blank in the example sentence'),
        ('5', f'Use config.py default',
         f'Current value: {col(config.CARD_TYPE, "yellow")}'),
    ]
    print_menu('Select Card Type for Export', options)
    choice = ask('Enter choice')
    mapping = {
        '1': 'basic',
        '2': 'basic_reversed',
        '3': 'type_answer',
        '4': 'cloze',
        '5': config.CARD_TYPE,
    }
    if choice not in mapping:
        print(col('  Invalid choice — using config.py default.', 'yellow'))
        return config.CARD_TYPE
    return mapping[choice]


# ─────────────────────────────────────────────
#  Settings editor — persistent writes to config.py
# ─────────────────────────────────────────────

_AI_PROVIDERS = [
    ("groq",      "Groq — free tier, Llama / Gemma / Mixtral (default)"),
    ("openai",    "OpenAI — ChatGPT / GPT models"),
    ("anthropic", "Anthropic — Claude models"),
    ("gemini",    "Google — Gemini models"),
    ("ollama",    "Ollama — run a model locally, no API key needed"),
]

_GROQ_MODELS = [
    ("llama-3.3-70b-versatile", "Best quality — recommended"),
    ("llama-3.1-8b-instant",    "Faster and lighter"),
    ("gemma2-9b-it",            "Google Gemma 2"),
    ("mixtral-8x7b-32768",      "Mixtral, long context window"),
]

_ANTHROPIC_MODELS = [
    ("claude-haiku-4-5", "Fastest and most cost-effective — recommended"),
    ("claude-sonnet-5",  "Best balance of speed and quality"),
    ("claude-opus-4-8",  "Most capable, highest cost"),
]

_TEMPLATES = [
    ("dark",      "Dark mode — Catppuccin Mocha palette (default)"),
    ("light",     "Light mode — clean white with soft accents"),
    ("minimal",   "Text only — no GIF, no gender badge"),
    ("immersive", "GIF as full card background with text overlay"),
]

_CARD_TYPES = [
    ("basic",          "Word -> Meaning  (classic recognition)"),
    ("basic_reversed", "Word <-> Meaning  (recognition + recall, 2 cards per note)"),
    ("type_answer",    "See definition -> type the word"),
    ("cloze",          "Fill in the blank in the example sentence"),
]

_GIF_RATINGS = [
    ("g",    "Family-friendly — safest (recommended)"),
    ("pg",   "PG — mild content"),
    ("pg-13","PG-13"),
    ("r",    "R — least restrictive"),
]


def write_config(key, value):
    """
    Rewrite a variable assignment in config.py and update the live config module.
    Supports str, int, float, and bool values. Preserves inline comments.
    """
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.py')
    with open(cfg_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if isinstance(value, bool):
        val_repr = str(value)
    elif isinstance(value, (int, float)):
        val_repr = str(value)
    else:
        val_repr = f'"{value}"'

    # Group 1: "KEY   = "   Group 2: the rest of the line (value + optional comment)
    pattern = re.compile(
        rf'^({re.escape(key)}\s*=\s*)(.*)$',
        re.MULTILINE,
    )

    def _replace(m):
        rest = m.group(2)
        # Preserve a trailing inline comment (2+ spaces then #)
        cm = re.search(r'([ \t]{2,}#[^\n]*)$', rest)
        comment = cm.group(1) if cm else ''
        return f'{m.group(1)}{val_repr}{comment}'

    new_content, count = pattern.subn(_replace, content)

    if count == 0:
        print(col(f'  [WARN] Key "{key}" not found in config.py', 'yellow'))
        return False

    with open(cfg_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    setattr(config, key, value)
    return True


# ─────────────────────────────────────────────
#  TUI-based configure menus (arrow-key navigation)
# ─────────────────────────────────────────────

import tui as _tui


def configure_language():
    _tui.run_menu('Language Settings', [
        _tui.TextInput('Language to learn',        'SOURCE_LANG',
                       hint='BCP-47 code, e.g. fr  es  de  ja  pt  ko  ru'),
        _tui.TextInput('Native language',          'TARGET_LANG',
                       hint='Full name used in AI prompt, e.g. English  Spanish'),
        _tui.TextInput('TTS source lang (gTTS)',   'TTS_SOURCE_LANG',
                       hint='Usually the same as Language to learn'),
        _tui.TextInput('TTS native lang (gTTS)',   'TTS_TARGET_LANG',
                       hint='e.g. en  es  pt  de'),
        _tui.Separator(),
        _tui.Back(),
    ])


def configure_ai():
    def _after_groq_key_change():
        AI_HEADERS['Authorization'] = f'Bearer {config.GROQ_API_KEY}'

    class _GroqModelPicker(_tui.Picker):
        def _set(self, idx):
            super()._set(idx)
            _after_groq_key_change()

    class _GroqKey(_tui.TextInput):
        def on_enter(self, win):
            super().on_enter(win)
            _after_groq_key_change()

    def _provider_settings():
        provider = current_ai_provider()
        if provider == "groq":
            _tui.run_menu('Groq Settings', [
                _GroqModelPicker('AI model', 'AI_MODEL', _GROQ_MODELS),
                _GroqKey('Groq API key', 'GROQ_API_KEY', secret=True,
                         hint='Get yours free at console.groq.com'),
                _tui.Separator(),
                _tui.Back(),
            ])
        elif provider == "openai":
            _tui.run_menu('OpenAI Settings', [
                _tui.TextInput('AI model', 'OPENAI_MODEL',
                               hint='e.g. gpt-4o-mini  gpt-4o  gpt-4.1-mini  gpt-4.1'),
                _tui.TextInput('OpenAI API key', 'OPENAI_API_KEY', secret=True,
                               hint='Get yours at platform.openai.com/api-keys'),
                _tui.Separator(),
                _tui.Back(),
            ])
        elif provider == "anthropic":
            _tui.run_menu('Claude (Anthropic) Settings', [
                _tui.Picker('AI model', 'ANTHROPIC_MODEL', _ANTHROPIC_MODELS),
                _tui.TextInput('Anthropic API key', 'ANTHROPIC_API_KEY', secret=True,
                               hint='Get yours at console.anthropic.com/settings/keys'),
                _tui.Separator(),
                _tui.Back(),
            ])
        elif provider == "gemini":
            _tui.run_menu('Gemini Settings', [
                _tui.TextInput('AI model', 'GEMINI_MODEL',
                               hint='e.g. gemini-2.0-flash  gemini-1.5-flash  gemini-1.5-pro'),
                _tui.TextInput('Gemini API key', 'GEMINI_API_KEY', secret=True,
                               hint='Get yours at aistudio.google.com/apikey'),
                _tui.Separator(),
                _tui.Back(),
            ])
        else:  # ollama
            _tui.run_menu('Ollama Settings', [
                _tui.TextInput('AI model', 'OLLAMA_MODEL',
                               hint='Must already be pulled locally, e.g. llama3.1  mistral  qwen2.5'),
                _tui.TextInput('Ollama server address', 'OLLAMA_HOST',
                               hint='e.g. http://localhost:11434'),
                _tui.Separator(),
                _tui.Back(),
            ])

    _tui.run_menu('AI & API Settings', [
        _tui.Picker('AI provider', 'AI_PROVIDER', _AI_PROVIDERS),
        _tui.Action('Provider settings',
                    _provider_settings,
                    lambda: (f'{AI_PROVIDER_LABELS.get(current_ai_provider(), current_ai_provider())}'
                             f'  |  {current_ai_model()}'
                             + ('' if not ai_key_missing() else '   ! key missing'))),
        _tui.Separator(),
        _tui.TextInput('Giphy API key', 'GIPHY_API_KEY', secret=True,
                       hint='Get yours free at developers.giphy.com'),
        _tui.Separator(),
        _tui.Back(),
    ])


def configure_deck():
    _tui.run_menu('Deck & Card Settings', [
        _tui.TextInput('Deck name',          'DECK_NAME',
                       hint='Name shown inside Anki — avoid changing after first import'),
        _tui.Picker('Card template',         'CARD_TEMPLATE',  _TEMPLATES),
        _tui.Picker('Card type',             'CARD_TYPE',      _CARD_TYPES),
        _tui.TextInput('Output — new deck',  'DECK_OUTPUT_NEW',
                       hint='.apkg file to import into Anki daily'),
        _tui.TextInput('Output — full deck', 'DECK_OUTPUT_FULL',
                       hint='.apkg full backup file'),
        _tui.Separator(),
        _tui.Back(),
    ])


def configure_generation():
    _tui.run_menu('Generation Settings', [
        _tui.NumberInput('Words per run',   'WORDS_PER_RUN',
                         hint='Words processed each time the script runs',
                         min_val=1, step=5),
        _tui.NumberInput('Total word pool', 'TOTAL_WORD_POOL',
                         hint='Size of frequency list to draw from',
                         min_val=100, step=100),
        _tui.Separator(),
        _tui.Back(),
    ])


def configure_audio():
    _tui.run_menu('Audio Settings', [
        _tui.Toggle('Enable audio (master switch)', 'ENABLE_AUDIO'),
        _tui.Separator(),
        _tui.Toggle('Word pronunciation audio',     'ENABLE_WORD_AUDIO'),
        _tui.Toggle('Example sentence audio',       'ENABLE_EXAMPLE_AUDIO'),
        _tui.Toggle('Meaning audio (native lang)',  'ENABLE_MEANING_AUDIO'),
        _tui.Separator(),
        _tui.Back(),
    ])


def configure_gif():
    _tui.run_menu('GIF Settings', [
        _tui.Toggle('Enable GIF (Giphy)',    'ENABLE_GIF'),
        _tui.Picker('Content rating filter', 'GIF_RATING', _GIF_RATINGS),
        _tui.Separator(),
        _tui.Back(),
    ])


def configure_ratelimits():
    _tui.run_menu('Rate Limiting  (seconds between API calls)', [
        _tui.NumberInput('Groq AI delay', 'DELAY_AI',    min_val=0.0, step=0.1, is_float=True),
        _tui.NumberInput('Giphy delay',   'DELAY_GIPHY', min_val=0.0, step=0.1, is_float=True),
        _tui.NumberInput('gTTS delay',    'DELAY_TTS',   min_val=0.0, step=0.1, is_float=True),
        _tui.Separator(),
        _tui.Back(),
    ])


def configure_main():
    _tui.run_menu('Configure Settings', [
        _tui.Action('Language',
                    configure_language,
                    lambda: f'{config.SOURCE_LANG.upper()} -> {config.TARGET_LANG}'),
        _tui.Action('AI & API keys',
                    configure_ai,
                    lambda: (f'{AI_PROVIDER_LABELS.get(current_ai_provider(), current_ai_provider())}'
                             + ('' if not ai_key_missing() else '  ! key missing'))),
        _tui.Action('Deck & cards',
                    configure_deck,
                    lambda: f'{config.CARD_TEMPLATE}  |  {config.CARD_TYPE}'),
        _tui.Action('Generation',
                    configure_generation,
                    lambda: f'{config.WORDS_PER_RUN}/run   pool {config.TOTAL_WORD_POOL}'),
        _tui.Action('Audio',
                    configure_audio,
                    lambda: 'ON' if config.ENABLE_AUDIO else 'OFF'),
        _tui.Action('GIF',
                    configure_gif,
                    lambda: f'{"ON" if config.ENABLE_GIF else "OFF"}  |  rating: {config.GIF_RATING}'),
        _tui.Action('Rate limits',
                    configure_ratelimits,
                    lambda: f'AI {config.DELAY_AI}s  Giphy {config.DELAY_GIPHY}s  TTS {config.DELAY_TTS}s'),
        _tui.Separator(),
        _tui.Back('Back to main menu'),
    ])


# ─────────────────────────────────────────────
#  Generation and export runners
# ─────────────────────────────────────────────

def run_generate(conn):
    """Card generation loop (interactive)."""
    print_banner()
    print(col('  Generate New Cards', 'bold', 'cyan'))
    print(f'  {"─" * 52}')

    if ai_key_missing():
        field = AI_PROVIDER_KEY_FIELD.get(current_ai_provider(), "GROQ_API_KEY")
        print(col(f'\n  [ERROR] {field} not set in config.py', 'red'))
        pause()
        return

    if config.ENABLE_GIF and config.GIPHY_API_KEY == "your_giphy_api_key_here":
        print(col('  [WARN] GIPHY_API_KEY not set — GIFs disabled for this run.', 'yellow'))
        config.ENABLE_GIF = False

    all_words = top_n_list(config.SOURCE_LANG, config.TOTAL_WORD_POOL)
    processed = get_processed_words(conn)
    pending   = [w for w in all_words if w not in processed]

    print(f'\n  Word pool   : {col(str(len(all_words)), "yellow")}')
    print(f'  In database : {col(str(len(processed)), "green")}')
    print(f'  Pending     : {col(str(len(pending)), "cyan")}')
    print(f'  This run    : {col(f"up to {config.WORDS_PER_RUN} words", "yellow")}')
    print()

    if not pending:
        print(col('  [WARN] Word pool exhausted!', 'yellow'))
        print(f'  Increase TOTAL_WORD_POOL in config.py (currently {config.TOTAL_WORD_POOL}).')
        pause()
        return

    _generate_loop(conn, pending, config.WORDS_PER_RUN)
    pause()


def run_export(conn):
    """Card type selection + export."""
    card_type = select_card_type()

    print_banner()
    label = _CARD_TYPE_LABELS.get(card_type, card_type)
    print(col(f'  Exporting Decks  [{label}]', 'bold', 'cyan'))
    print(f'  {"─" * 52}')
    print()

    template = tmpl_registry.load(config.CARD_TEMPLATE)
    try:
        export_decks(conn, template, card_type)
    except Exception as e:
        print(col(f'\n  [ERROR] Export failed: {e}', 'red'))
    pause()


def _generate_loop(conn, pending, limit):
    """Core word-processing loop used by both interactive and headless modes."""
    processed_count = 0

    for word in pending:
        if processed_count >= limit:
            break

        print(f'  [{processed_count + 1}/{limit}] {col(word, "bold")}')

        ai_data = generate_card_content(word)
        time.sleep(config.DELAY_AI)

        if not ai_data:
            print(col('    [WARN] AI failed — skipping', 'yellow'))
            save_card(conn, {
                "word": word, "word_label": word,
                "meaning_id": 0,
                "text_example_phrase": f"[no sentence] {word}",
            })
            processed_count += 1
            continue

        ipa      = ai_data.get("ipa", "")
        meanings = ai_data.get("meanings", [])

        if not meanings:
            print(col('    [WARN] No meanings returned — skipping', 'yellow'))
            processed_count += 1
            continue

        # Word-level audio (generated once per word)
        audio_word_path = ""
        if config.ENABLE_AUDIO and config.ENABLE_WORD_AUDIO:
            try:
                audio_word_path, _ = generate_audio(word, lang=config.TTS_SOURCE_LANG)
                print(col('    [AUDIO] Word audio', 'dim'))
            except Exception as e:
                print(col(f'    [WARN] Word audio error: {e}', 'yellow'))

        for meaning_id, meaning in enumerate(meanings):
            if card_exists(conn, word, meaning_id):
                print(col(f'    [SKIP] Meaning {meaning_id} already in DB', 'dim'))
                continue

            pos                      = meaning.get("pos", "")
            gender                   = meaning.get("gender", "")
            text_meaning             = meaning.get("text_meaning", "")
            text_example             = meaning.get("text_example_phrase", "")
            text_example_translation = meaning.get("text_example_translation", "")
            synonyms                 = meaning.get("synonyms", "")
            gif_keywords             = meaning.get("gif_keywords", [])

            word_label = f"{word} ({pos})" if len(meanings) > 1 and pos else word

            audio_example_path = ""
            if config.ENABLE_AUDIO and config.ENABLE_EXAMPLE_AUDIO:
                try:
                    audio_example_path, _ = generate_audio(
                        text_example, lang=config.TTS_SOURCE_LANG
                    )
                    print(col(f'    [AUDIO] Example — meaning {meaning_id}', 'dim'))
                except Exception as e:
                    print(col(f'    [WARN] Example audio error: {e}', 'yellow'))

            audio_meaning_path = ""
            if config.ENABLE_AUDIO and config.ENABLE_MEANING_AUDIO:
                try:
                    audio_meaning_path, _ = generate_audio(
                        text_meaning, lang=config.TTS_TARGET_LANG
                    )
                except Exception:
                    pass

            gif_html    = ""
            gif_raw_url = ""
            if config.ENABLE_GIF:
                keywords = gif_keywords if isinstance(gif_keywords, list) else []
                if not keywords:
                    keywords = [word, pos.lower()] if pos else [word]
                gif_html, gif_raw_url = fetch_gif(keywords)
                query_display = " ".join(f"#{k}" for k in keywords)
                status = col('found', 'green') if gif_html else col('not found', 'dim')
                print(f'    [GIF] {col(query_display, "dim")} — {status}')
                time.sleep(config.DELAY_GIPHY)

            save_card(conn, {
                "word":                      word,
                "word_label":                word_label,
                "meaning_id":                meaning_id,
                "pos":                       pos,
                "gender":                    gender,
                "ipa":                       ipa,
                "text_meaning":              text_meaning,
                "text_example_phrase":       text_example,
                "text_example_translation":  text_example_translation,
                "synonyms":                  synonyms,
                "audio_word":                audio_word_path,
                "audio_meaning":             audio_meaning_path,
                "audio_example":             audio_example_path,
                "gif_url":                   gif_html,
                "gif_raw_url":               gif_raw_url,
            })
            print(col(f'    [DONE] [{word_label}] {text_meaning[:60]}...', 'green'))

        processed_count += 1

    print(col(f'\n  {processed_count} words processed this run.', 'green', 'bold'))
    return processed_count


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

def _run_headless():
    """Non-interactive mode: generate + export without a menu (--run flag)."""
    print("=" * 60)
    print("  Anki Vocabulary Deck Generator  v2.0  [headless]")
    print(f"  Language : {config.SOURCE_LANG.upper()}  |  "
          f"Template : {config.CARD_TEMPLATE}  |  "
          f"Card type : {config.CARD_TYPE}  |  "
          f"AI provider : {AI_PROVIDER_LABELS.get(current_ai_provider(), current_ai_provider())}  |  "
          f"AI model : {current_ai_model()}")
    print("=" * 60)

    if ai_key_missing():
        field = AI_PROVIDER_KEY_FIELD.get(current_ai_provider(), "GROQ_API_KEY")
        print(f"\n[ERROR] Please set your {field} in config.py")
        sys.exit(1)
    if config.ENABLE_GIF and config.GIPHY_API_KEY == "your_giphy_api_key_here":
        print("\n[WARN] GIPHY_API_KEY not set — GIFs will be disabled.")
        config.ENABLE_GIF = False

    conn      = init_db()
    all_words = top_n_list(config.SOURCE_LANG, config.TOTAL_WORD_POOL)
    processed = get_processed_words(conn)
    pending   = [w for w in all_words if w not in processed]

    print(f"\n  Word pool   : {len(all_words)}")
    print(f"  In database : {len(processed)}")
    print(f"  Pending     : {len(pending)}")
    print(f"  This run    : up to {config.WORDS_PER_RUN} words\n")

    if not pending:
        print("[WARN] Word pool exhausted!")
        print(f"   Increase TOTAL_WORD_POOL in config.py "
              f"(currently {config.TOTAL_WORD_POOL}) and run again.")
    else:
        _generate_loop(conn, pending, config.WORDS_PER_RUN)

    template = tmpl_registry.load(config.CARD_TEMPLATE)
    export_decks(conn, template)
    conn.close()


def main():
    if "--run" in sys.argv:
        _run_headless()
        return

    conn = init_db()

    _tui.run_menu('Main Menu', [
        _tui.Action('Generate new cards',
                    lambda: run_generate(conn),
                    lambda: f'Up to {config.WORDS_PER_RUN} words from the frequency list',
                    print_mode=True),
        _tui.Action('Export decks',
                    lambda: run_export(conn),
                    'Build .apkg  —  choose card type before exporting',
                    print_mode=True),
        _tui.Action('Configure',
                    configure_main,
                    lambda: f'{config.SOURCE_LANG.upper()} -> {config.TARGET_LANG}'),
        _tui.Action('Statistics',
                    lambda: show_statistics(conn),
                    'Card counts, POS breakdown, export history',
                    print_mode=True),
        _tui.Action('Card type guide',
                    show_card_types,
                    'Basic / Reversed / Type / Cloze',
                    print_mode=True),
        _tui.Separator(),
        _tui.Back('Exit'),
    ])

    conn.close()


if __name__ == "__main__":
    main()
