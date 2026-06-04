"""
=============================================================
  Anki Vocabulary Deck Generator
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

  Daily usage:
    Run → import deck_new.apkg → repeat tomorrow.
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

# Load all settings from config.py
import config
import templates as tmpl_registry


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
    # Soft migrations — adds new columns without breaking existing databases
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
            pass  # Column already exists
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
    """
    Fetch cards from the database.
    If new_only=True, returns only cards not yet exported.
    """
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
#  POS → Anki tag mapping
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
    """Convert a raw POS string from the AI into a standardized Anki tag."""
    if not pos_str:
        return "Other"
    key = pos_str.strip().lower()
    for k, v in POS_TAG_MAP.items():
        if k in key:
            return v
    return pos_str.strip().replace(" ", "_")  # fallback: use raw value


# ─────────────────────────────────────────────
#  AI content generation (Groq)
# ─────────────────────────────────────────────

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
AI_HEADERS = {
    "Authorization": f"Bearer {config.GROQ_API_KEY}",
    "Content-Type":  "application/json",
}

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


def generate_card_content(word):
    """
    Call the Groq API to generate all flashcard content for a word.
    Returns a dict with 'ipa' and 'meanings', or None on failure.
    """
    prompt = PROMPT_TEMPLATE.format(
        word=word,
        source_lang=config.SOURCE_LANG,
        target_lang=config.TARGET_LANG,
    )
    payload = {
        "model":       config.AI_MODEL,
        "temperature": 0.3,
        "max_tokens":  1024,
        "messages":    [{"role": "user", "content": prompt}],
    }
    try:
        resp = requests.post(GROQ_URL, headers=AI_HEADERS, json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"    [Groq] HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip any residual markdown fences
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"    [Groq] Invalid JSON for '{word}': {e}")
        return None
    except Exception as e:
        print(f"    [Groq] Error for '{word}': {e}")
        return None


# ─────────────────────────────────────────────
#  GIF search (Giphy)
# ─────────────────────────────────────────────

def fetch_gif(keywords):
    """
    Search Giphy using hashtag-style keywords.
    Returns an HTML <img> tag or an empty string if disabled/not found.
    """
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
        return img_tag, gif_url  # (html tag, raw url)
    except Exception as e:
        print(f"    [Giphy] Error: {e}")
        return "", ""


# ─────────────────────────────────────────────
#  Audio generation (gTTS)
# ─────────────────────────────────────────────

def generate_audio(text, lang):
    """
    Generate an MP3 file using gTTS.
    Returns (full_path, filename) or ("", "") on failure/disabled.
    """
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
#  Anki model builder
# ─────────────────────────────────────────────

def build_anki_model(template):
    """
    Build a genanki Model using the CSS and templates from the chosen layout.
    Supports an optional extra field (Image_Raw) for the immersive template.
    """
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
    # Immersive template needs the raw GIF URL as a separate field
    if getattr(template, "REQUIRES_RAW_IMAGE", False):
        fields.append({"name": "Image_Raw"})

    return genanki.Model(
        config.MODEL_ID,
        f"{config.DECK_NAME} Model",
        fields=fields,
        templates=[{
            "name": "Card",
            "qfmt": template.FRONT,
            "afmt": template.BACK,
        }],
        css=template.CSS,
    )


# ─────────────────────────────────────────────
#  Formatting helpers
# ─────────────────────────────────────────────

def highlight_word(sentence, word):
    """Wrap the target word in a styled <span> inside the example sentence."""
    pattern = re.compile(re.escape(word), re.IGNORECASE)
    return pattern.sub(
        lambda m: f'<span class="highlight">{m.group()}</span>', sentence
    )


def format_synonyms(synonyms_str):
    """Convert a comma-separated synonym string into badge HTML."""
    if not synonyms_str:
        return ""
    badges = "".join(
        f'<span class="syn-badge">{s.strip()}</span>'
        for s in synonyms_str.split(",") if s.strip()
    )
    return f'<div class="synonyms-wrap">{badges}</div>'


def gender_badge(gender):
    """Return a styled gender badge HTML element, or empty string."""
    if not gender:
        return ""
    if gender.lower().startswith("m"):
        return '<span class="gender-badge gender-m">♂ Masculine</span>'
    if gender.lower().startswith("f"):
        return '<span class="gender-badge gender-f">♀ Feminine</span>'
    return ""


def sound_tag(audio_path):
    """Return an Anki [sound:filename] tag if the file exists."""
    if audio_path and os.path.exists(audio_path):
        return f"[sound:{os.path.basename(audio_path)}]"
    return ""


# ─────────────────────────────────────────────
#  .apkg builder
# ─────────────────────────────────────────────

def build_notes(cards, model, template):
    """Convert database rows into genanki Note objects."""
    notes  = []
    media  = []
    ids    = []
    needs_raw = getattr(template, "REQUIRES_RAW_IMAGE", False)

    for row in cards:
        (word_label, ipa, text_meaning, text_example,
         text_example_translation, synonyms, aw, am, ae,
         gif_url, gif_raw_url, gender_str, word, card_id) = row

        example_html = highlight_word(text_example, word)
        synonyms_html = format_synonyms(synonyms)
        gender_html   = gender_badge(gender_str)

        fields = [
            word_label,                      # Word
            gif_url or "",                   # Image
            sound_tag(aw) if config.ENABLE_WORD_AUDIO    else "",  # Sound_Word
            sound_tag(am) if config.ENABLE_MEANING_AUDIO else "",  # Sound_Meaning
            sound_tag(ae) if config.ENABLE_EXAMPLE_AUDIO else "",  # Sound_Example
            text_meaning,                    # Text_Meaning
            example_html,                    # Text_Example_Phrase
            text_example_translation,        # Text_Example_Translation
            ipa,                             # IPA
            gender_html,                     # Gender
            synonyms_html,                   # Synonyms
        ]

        if needs_raw:
            fields.append(gif_raw_url or "")  # Image_Raw (immersive only)

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


def export_decks(conn, model, template):
    """
    Export two .apkg files:
      - deck_new.apkg   : only cards added in this run (import this daily)
      - deck_full.apkg  : all cards ever generated (full backup)
    """
    # ── New cards only ──────────────────────────────────────────
    new_cards = get_all_cards(conn, new_only=True)
    if new_cards:
        deck_new = genanki.Deck(config.DECK_ID + 1, f"{config.DECK_NAME} — New")
        pkg_new  = genanki.Package(deck_new)
        notes, media, ids = build_notes(new_cards, model, template)
        for note in notes:
            deck_new.add_note(note)
        pkg_new.media_files = media
        pkg_new.write_to_file(config.DECK_OUTPUT_NEW)
        mark_as_exported(conn, ids)
        print(f"\n[OK] New cards    : {config.DECK_OUTPUT_NEW}  ({len(new_cards)} cards)")
        print(f"     -> Import THIS file into Anki to preserve your manual edits.")
    else:
        print(f"\n[INFO] No new cards to export.")

    # ── Full backup ─────────────────────────────────────────────
    all_cards = get_all_cards(conn, new_only=False)
    deck_full = genanki.Deck(config.DECK_ID, config.DECK_NAME)
    pkg_full  = genanki.Package(deck_full)
    notes_full, media_full, _ = build_notes(all_cards, model, template)
    for note in notes_full:
        deck_full.add_note(note)
    pkg_full.media_files = media_full
    pkg_full.write_to_file(config.DECK_OUTPUT_FULL)
    print(f"    Full backup : {config.DECK_OUTPUT_FULL}  ({len(all_cards)} cards total)")


# ─────────────────────────────────────────────
#  Main loop
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Anki Vocabulary Deck Generator")
    print(f"  Language : {config.SOURCE_LANG.upper()}  |  "
          f"Template : {config.CARD_TEMPLATE}  |  "
          f"AI model : {config.AI_MODEL}")
    print("=" * 60)

    # Validate API keys
    if config.GROQ_API_KEY == "your_groq_api_key_here":
        print("\n[ERROR] Please set your GROQ_API_KEY in config.py")
        sys.exit(1)
    if config.ENABLE_GIF and config.GIPHY_API_KEY == "your_giphy_api_key_here":
        print("\n[WARN] GIPHY_API_KEY not set -- GIFs will be disabled for this run.")
        config.ENABLE_GIF = False

    # Load card template
    template = tmpl_registry.load(config.CARD_TEMPLATE)
    model    = build_anki_model(template)

    conn = init_db()

    # Build pending word list
    all_words   = top_n_list(config.SOURCE_LANG, config.TOTAL_WORD_POOL)
    processed   = get_processed_words(conn)
    pending     = [w for w in all_words if w not in processed]

    print(f"\n  Word pool   : {len(all_words)}")
    print(f"  In database : {len(processed)}")
    print(f"  Pending     : {len(pending)}")
    print(f"  This run    : up to {config.WORDS_PER_RUN} words\n")

    # Pool exhausted — prompt user to increase TOTAL_WORD_POOL
    if not pending:
        print("[WARN] Word pool exhausted!")
        print(f"   Increase TOTAL_WORD_POOL in config.py "
              f"(currently {config.TOTAL_WORD_POOL}) and run again.")
        export_decks(conn, model, template)
        conn.close()
        return

    processed_today = 0

    for word in pending:
        if processed_today >= config.WORDS_PER_RUN:
            break

        print(f"[{processed_today + 1}/{config.WORDS_PER_RUN}] {word}")

        # ── Step 1: Generate content with AI ────────────────────
        ai_data = generate_card_content(word)
        time.sleep(config.DELAY_AI)

        if not ai_data:
            print(f"    [WARN] AI failed -- skipping '{word}'")
            save_card(conn, {
                "word": word, "word_label": word,
                "meaning_id": 0,
                "text_example_phrase": f"[no sentence] {word}",
            })
            processed_today += 1
            continue

        ipa      = ai_data.get("ipa", "")
        meanings = ai_data.get("meanings", [])

        if not meanings:
            print(f"    [WARN] No meanings returned -- skipping")
            processed_today += 1
            continue

        # ── Step 2: Word-level audio (generated once per word) ──
        audio_word_path = ""
        if config.ENABLE_AUDIO and config.ENABLE_WORD_AUDIO:
            try:
                audio_word_path, _ = generate_audio(word, lang=config.TTS_SOURCE_LANG)
                print(f"    [AUDIO] Word audio")
            except Exception as e:
                print(f"    [WARN] Word audio error: {e}")

        # ── Step 3: One card per meaning ────────────────────────
        for meaning_id, meaning in enumerate(meanings):
            if card_exists(conn, word, meaning_id):
                print(f"    [SKIP] Meaning {meaning_id} already exists -- skipping")
                continue

            pos                      = meaning.get("pos", "")
            gender                   = meaning.get("gender", "")
            text_meaning             = meaning.get("text_meaning", "")
            text_example             = meaning.get("text_example_phrase", "")
            text_example_translation = meaning.get("text_example_translation", "")
            synonyms                 = meaning.get("synonyms", "")
            gif_keywords             = meaning.get("gif_keywords", [])

            # Word label includes POS when multiple meanings exist
            word_label = f"{word} ({pos})" if len(meanings) > 1 and pos else word

            # Example sentence audio
            audio_example_path = ""
            if config.ENABLE_AUDIO and config.ENABLE_EXAMPLE_AUDIO:
                try:
                    audio_example_path, _ = generate_audio(
                        text_example, lang=config.TTS_SOURCE_LANG
                    )
                    print(f"    [AUDIO] Example audio -- meaning {meaning_id}")
                except Exception as e:
                    print(f"    [WARN] Example audio error: {e}")

            # Meaning audio (spoken in target language)
            audio_meaning_path = ""
            if config.ENABLE_AUDIO and config.ENABLE_MEANING_AUDIO:
                try:
                    audio_meaning_path, _ = generate_audio(
                        text_meaning, lang=config.TTS_TARGET_LANG
                    )
                except Exception:
                    pass

            # GIF — unique per meaning using AI-generated keywords
            gif_html    = ""
            gif_raw_url = ""
            if config.ENABLE_GIF:
                keywords = gif_keywords if isinstance(gif_keywords, list) else []
                if not keywords:
                    keywords = [word, pos.lower()] if pos else [word]
                gif_html, gif_raw_url = fetch_gif(keywords)
                query_display = " ".join(f"#{k}" for k in keywords)
                print(f"    [GIF] Query: '{query_display}' -- {'found' if gif_html else 'not found'}")
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
            print(f"    [DONE] [{word_label}] {text_meaning[:65]}...")

        processed_today += 1

    print(f"\nWords processed this run: {processed_today}")
    export_decks(conn, model, template)
    conn.close()


if __name__ == "__main__":
    main()
