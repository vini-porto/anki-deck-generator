"""
=============================================================
  Anki Vocabulary Deck Generator
  (version tracked in VERSION / CHANGELOG.md — see version.py)
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
import zlib
import shutil
import sqlite3
import hashlib
import requests
from collections import Counter
import genanki
from gtts import gTTS
from wordfreq import top_n_list

import config
import version as _version
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
_W = 58  # minimum visible width of box interior (between the ║ borders) —
         # print_banner() widens this automatically for unusually long
         # content (e.g. a long AI model name) so the box never overflows


def col(text, *codes):
    """Wrap text in ANSI color codes."""
    return ''.join(_CODES[k] for k in codes) + str(text) + _CODES['reset']


def _vlen(text):
    """Visible length of text (strips ANSI codes before measuring)."""
    return len(_ANSI_RE.sub('', text))


def _clear():
    print('\033[2J\033[H', end='', flush=True)


def _hline(ch='═', width=_W):
    return ch * width


def _row(text='', width=_W):
    """Format one box row. text may contain ANSI codes; padding uses visible length."""
    pad = width - 2 - _vlen(text)
    return f'║ {text}{" " * max(0, pad)} ║'


def print_banner():
    _clear()
    title    = col(f'  Anki Vocabulary Deck Generator  v{_version.APP_VERSION}  ', 'bold', 'cyan')
    lang     = col(f'  Language : {config.SOURCE_LANG.upper()} -> {config.TARGET_LANG}', 'yellow')
    tmpl     = col(f'  Template : {config.CARD_TEMPLATE}   |   Card type : {config.CARD_TYPE}', 'dim')
    provider = AI_PROVIDER_LABELS.get(current_ai_provider(), current_ai_provider())
    model    = col(f'  AI provider : {provider}   |   Model : {current_ai_model()}', 'dim')
    lines = [title, lang, tmpl, model]
    width = max(_W, max(_vlen(t) for t in lines) + 2)
    print('╔' + _hline(width=width) + '╗')
    print(_row(title, width))
    print('╠' + _hline(width=width) + '╣')
    print(_row(lang, width))
    print(_row(tmpl, width))
    print(_row(model, width))
    print('╚' + _hline(width=width) + '╝')
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

def _migrate_to_creation_mode_schema(conn):
    """One-time, irreversible rebuild of `cards`: the old UNIQUE(word,
    meaning_id) can't express per-creation_mode dedup (see § Creation modes
    in CLAUDE.md), and SQLite can't ALTER a UNIQUE constraint in place, so
    this does a real create/copy/drop/rename migration — the first one this
    codebase has ever needed (every prior schema change was an additive
    soft `ALTER TABLE ADD COLUMN`, safe to keep re-running forever).

    No-ops for a brand-new DB (no `cards` table yet — the CREATE TABLE IF
    NOT EXISTS right after this call builds the new schema directly) or a
    DB that's already been migrated (`content_key` column already present).
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(cards)").fetchall()}
    if not cols or "content_key" in cols:
        return

    print(col("  [INFO] Migrating progress.db to the new creation_mode schema "
               "(one-time, irreversible)...", 'yellow'))
    try:
        backup_path = config.DB_PATH + ".pre-creation-mode-migration.bak"
        if not os.path.exists(backup_path):
            shutil.copy2(config.DB_PATH, backup_path)
            print(col(f"  [INFO] Backup written to {backup_path}", 'dim'))
    except Exception as e:
        print(col(f"  [WARN] Could not write migration backup: {e}", 'yellow'))

    # Guarantee every column the copy statement below reads actually exists
    # on the legacy table, even for a DB that predates some of these
    # (already-soft-migrated-elsewhere) columns.
    legacy_migrations = [
        ("word_label",               "TEXT DEFAULT ''"),
        ("pos",                      "TEXT DEFAULT ''"),
        ("gif_url",                  "TEXT DEFAULT ''"),
        ("gif_raw_url",              "TEXT DEFAULT ''"),
        ("gender",                   "TEXT DEFAULT ''"),
        ("text_example_translation", "TEXT DEFAULT ''"),
        ("exported",                 "INTEGER DEFAULT 0"),
        ("category",                 "TEXT DEFAULT ''"),
    ]
    for column, definition in legacy_migrations:
        try:
            conn.execute(f"ALTER TABLE cards ADD COLUMN {column} {definition}")
        except Exception:
            pass

    conn.execute("DROP TABLE IF EXISTS cards_new")
    conn.execute("""
        CREATE TABLE cards_new (
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
            category                 TEXT    DEFAULT '',
            exported                 INTEGER DEFAULT 0,
            date_added               TEXT    DEFAULT (date('now')),
            creation_mode            TEXT    NOT NULL DEFAULT 'word_meaning',
            content_key              TEXT    NOT NULL,
            source_phrase            TEXT,
            UNIQUE(creation_mode, content_key, meaning_id)
        )
    """)
    conn.execute("""
        INSERT INTO cards_new (
            id, word, word_label, meaning_id, pos, ipa,
            text_meaning, text_example_phrase, text_example_translation,
            synonyms, audio_word, audio_meaning, audio_example,
            gif_url, gif_raw_url, gender, category, exported, date_added,
            creation_mode, content_key, source_phrase
        )
        SELECT
            id, word, word_label, meaning_id, pos, ipa,
            text_meaning, text_example_phrase, text_example_translation,
            synonyms, audio_word, audio_meaning, audio_example,
            gif_url, gif_raw_url, gender, category, exported, date_added,
            'word_meaning', LOWER(TRIM(word)), NULL
        FROM cards
    """)
    conn.execute("DROP TABLE cards")
    conn.execute("ALTER TABLE cards_new RENAME TO cards")
    conn.commit()
    print(col("  [OK] Migration complete — every existing card is now "
               "creation_mode='word_meaning', matching its prior behavior.", 'green'))


def init_db():
    """Initialize SQLite database and apply any pending migrations."""
    conn = sqlite3.connect(config.DB_PATH)
    _migrate_to_creation_mode_schema(conn)
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
            category                 TEXT    DEFAULT '',
            exported                 INTEGER DEFAULT 0,
            date_added               TEXT    DEFAULT (date('now')),
            creation_mode            TEXT    NOT NULL DEFAULT 'word_meaning',
            content_key              TEXT    NOT NULL,
            source_phrase            TEXT,
            UNIQUE(creation_mode, content_key, meaning_id)
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
        ("category",                 "TEXT DEFAULT ''"),
    ]
    for column, definition in migrations:
        try:
            conn.execute(f"ALTER TABLE cards ADD COLUMN {column} {definition}")
        except Exception:
            pass
    conn.commit()
    return conn


def card_exists(conn, creation_mode, content_key, meaning_id):
    return conn.execute(
        "SELECT 1 FROM cards WHERE creation_mode=? AND content_key=? AND meaning_id=?",
        (creation_mode, content_key, meaning_id)
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
             gif_url, gif_raw_url, gender, category,
             creation_mode, content_key, source_phrase)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
        data.get("category", ""),
        data["creation_mode"],
        data["content_key"],
        data.get("source_phrase"),
    ))
    conn.commit()


def get_processed_words(conn, creation_mode):
    """Words already used as an anchor *in this specific creation_mode*.
    Deliberately per-mode, not global: a word already anchoring a
    word_meaning card must remain eligible to anchor a phrase_context card
    too (each mode's spaced repetition is independent — see § Creation
    modes in CLAUDE.md)."""
    rows = conn.execute(
        "SELECT DISTINCT word FROM cards WHERE creation_mode=?", (creation_mode,)
    ).fetchall()
    return {r[0] for r in rows}


def get_all_cards(conn, new_only=False, creation_mode=None):
    # text_example_phrase is required for word_meaning/phrase_context/etc.,
    # but modes that declare "text_example" in always_omit (audio_writing,
    # audio_typing) never populate it by design — this filter would
    # otherwise silently exclude every one of their cards from every export.
    mode_def = CREATION_MODES.get(creation_mode, {}) if creation_mode else {}
    needs_example = "text_example" not in mode_def.get("always_omit", ())
    example_clause = (
        "AND text_example_phrase NOT LIKE '[no sentence]%' AND text_example_phrase != ''"
        if needs_example else ""
    )
    filter_clause = "AND exported = 0" if new_only else ""
    mode_clause = "AND creation_mode = ?" if creation_mode else ""
    params = (creation_mode,) if creation_mode else ()
    return conn.execute(f"""
        SELECT word_label, ipa, text_meaning, text_example_phrase,
               text_example_translation, synonyms, audio_word,
               audio_meaning, audio_example, gif_url, gif_raw_url,
               gender, category, word, id
        FROM cards
        WHERE 1=1
          {example_clause}
          {filter_clause}
          {mode_clause}
        ORDER BY id
    """, params).fetchall()


def mark_as_exported(conn, ids):
    conn.executemany(
        "UPDATE cards SET exported = 1 WHERE id = ?",
        [(i,) for i in ids]
    )
    conn.commit()


def get_known_categories(conn):
    """Distinct, non-empty categories already used in this deck (any language run)."""
    rows = conn.execute(
        "SELECT DISTINCT category FROM cards WHERE category != '' ORDER BY category"
    ).fetchall()
    return [r[0] for r in rows]


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
#  Category -> Anki tag / subdeck mapping
#
#  Categories are language-specific study blocks (e.g. "Phrasal Verbs" for
#  English) generated by the AI, not a fixed list like POS_TAG_MAP. They are
#  surfaced as both a `topic::<Category>` tag and a `<Deck>::<Category>`
#  subdeck so cards stay browsable/filterable either way.
# ─────────────────────────────────────────────

def category_to_tag(category):
    """Slugify a category name into a valid, readable Anki tag segment."""
    slug = re.sub(r"[^\w]+", "_", category.strip(), flags=re.UNICODE).strip("_")
    return slug or "Other"


def category_deck_name(base_name, category):
    return f"{base_name}::{category}" if category else base_name


def category_deck_id(base_id, category):
    """
    Deterministic sub-deck ID derived from the category name, stable across
    runs so Anki doesn't spawn a new subdeck each import. Offsets are large
    enough to never collide with base_id itself (DECK_ID vs DECK_ID + 1).
    """
    if not category:
        return base_id
    offset = zlib.crc32(category.strip().lower().encode("utf-8")) % 100_000_000
    return base_id + 1000 + offset


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


# Per MEANING_EXHAUSTIVENESS level: how the prompt asks for meanings, the
# hard cap enforced in the Rules section, and the AI token budget. "all"
# still caps at a finite number rather than truly "every sense" — an
# unbounded prompt for a word like "the" can ask for dozens of technical
# senses and blow through any token budget into truncated/invalid JSON (see
# CHANGELOG's original meaning-cap fix), so "all" means "generous", not
# "unlimited". The larger max_tokens for "all" gives that generous cap
# headroom to actually complete instead of truncating.
MEANING_EXHAUSTIVENESS_SETTINGS = {
    "essential": {
        "label":        "Essential only",
        "max_meanings": 1,
        "instruction":  ('generate flashcard data for only its single most essential, most '
                          'commonly used meaning — the one a learner needs first'),
        "max_tokens":   1024,
    },
    "important": {
        "label":        "Most important",
        "max_meanings": 5,
        "instruction":  ('generate flashcard data for its distinct and relevant meanings — at '
                          'most the 5 most common and useful ones for a learner (fewer if the '
                          "word doesn't have that many)"),
        "max_tokens":   2048,
    },
    "all": {
        "label":        "All meanings",
        "max_meanings": 12,
        "instruction":  ('generate flashcard data for every genuinely distinct meaning a '
                          'learner would realistically encounter — up to 12 (fewer if the word '
                          "doesn't have that many)"),
        "max_tokens":   4096,
    },
}


PROMPT_TEMPLATE = """You are a language expert creating Anki flashcard content \
for {target_lang} speakers learning {source_lang}.

For the word "{word}", {meaning_instruction}. Even extremely common function/grammar words \
(e.g. articles, prepositions, auxiliary verbs) that technically have dozens of senses must stay \
within that limit — pick only the ones that are genuinely worth a separate flashcard.

Return ONLY a valid JSON object (no markdown, no explanation) with this exact structure:
{{
  "ipa": "IPA transcription for {source_lang} pronunciation (e.g. mɛ.zɔ̃)",
  "meanings": [
    {{
      "pos": "part of speech in English (Noun / Verb / Adjective / Adverb / etc.)",
      "gender": "For nouns only: 'Masculine' or 'Feminine'. Empty string for all other parts of speech.",
      "text_meaning": "A single clear sentence written ENTIRELY in {target_lang} explaining this \
meaning. Do NOT include the {source_lang} word/term itself anywhere in this sentence — it is \
already shown separately on the card with its own {source_lang} audio, so repeating it here \
would mix two languages in a single sentence and sound wrong when read aloud. Refer to it only \
implicitly: 'Means to ...' for verbs, 'Describes something/someone that is ...' for adjectives, \
'Refers to ...' or 'A type of ...' for nouns. Keep it concise like a real dictionary entry.",
      "text_example_phrase": "A natural sentence in {source_lang} (10-15 words) using the word \
in this specific meaning. Make it vivid and memorable with real context.",
      "text_example_translation": "The {target_lang} translation of the example sentence above. \
Keep it natural, not word-for-word literal.",
      "synonyms": "up to 6 relevant {source_lang} synonyms for this meaning, comma-separated",
      "category": "A short, reusable study-block label (2-4 words, Title Case) for this meaning, \
ONLY if it belongs to a recognizable grammar/vocabulary category specific to learning \
{source_lang} — a grouping that is distinct from plain vocabulary (e.g. 'Phrasal Verbs' or \
'Verb Conjugation' for English; adapt to whatever is actually relevant for {source_lang}). \
Leave as an empty string for ordinary vocabulary that doesn't belong to a special study block. \
{category_hint}",
      "gif_keywords": ["exactly 3 English single-word keywords that together visually represent \
this meaning and example sentence. Focus on the action, object, and setting. \
Example for a clock melting: ['melting', 'clock', 'fire']. \
Example for someone teasing: ['teasing', 'laughing', 'school']."]
    }}
  ]
}}

Rules:
- Only include meanings that are genuinely distinct and useful for a language learner
- Never return more than {max_meanings} meaning(s), even for words with many technical senses
- The example sentence must clearly illustrate the specific meaning listed
- Synonyms must be in {source_lang}
- IPA must be standard {source_lang} IPA notation
- gif_keywords must be exactly 3 English single words
- gender must be 'Masculine' or 'Feminine' for nouns only, empty string otherwise
- text_meaning must be written entirely in {target_lang} — never include the literal \
{source_lang} word/term being defined, since that would mix languages inside its own audio
- text_example_translation must be a natural {target_lang} translation of the example
- category must reuse an existing category exactly (same spelling/casing) whenever it fits, \
must be an empty string for ordinary vocabulary, and should only introduce a new category when \
the meaning is truly a distinct study block not covered by an existing one
- Return raw JSON only — no markdown fences, no extra text"""


PROMPT_TEMPLATE_PHRASE_CONTEXT = """You are a language expert creating Anki flashcard content \
for {target_lang} speakers learning {source_lang}.

For the word "{word}", generate up to {max_meanings} distinct example phrases that naturally use \
this word in different real-world contexts (fewer if that many genuinely distinct contexts don't \
exist). In each phrase, wrap the EXACT inflected/conjugated surface form you actually used with \
double asterisks, e.g. "Elle a **couru** jusqu'à la gare." — wrap only that one occurrence, using \
the literal form as it appears in your sentence (which may differ from the dictionary/citation \
form given above, since word forms change with conjugation, gender, number, etc.).

Return ONLY a valid JSON object (no markdown, no explanation) with this exact structure:
{{
  "ipa": "IPA transcription for {source_lang} pronunciation of the dictionary form (e.g. mɛ.zɔ̃)",
  "pos": "part of speech in English (Noun / Verb / Adjective / Adverb / etc.) of the dictionary form",
  "gender": "For nouns only: 'Masculine' or 'Feminine'. Empty string for all other parts of speech.",
  "phrases": [
    {{
      "phrase": "A natural sentence in {source_lang} (10-15 words) using the word in a specific \
context, with the exact inflected form wrapped in **double asterisks**.",
      "phrase_translation": "The {target_lang} translation of the phrase above — natural, not \
word-for-word literal.",
      "text_meaning": "A single clear sentence written ENTIRELY in {target_lang} explaining what \
the word means AS USED in this specific phrase. Do NOT include the {source_lang} word/term \
itself anywhere in this sentence. Refer to it only implicitly: 'Means to ...' for verbs, \
'Describes something/someone that is ...' for adjectives, 'Refers to ...' or 'A type of ...' \
for nouns.",
      "synonyms": "up to 6 relevant {source_lang} synonyms for the word as used in this context, \
comma-separated",
      "category": "A short, reusable study-block label (2-4 words, Title Case) for this phrase, \
ONLY if it belongs to a recognizable grammar/vocabulary category specific to learning \
{source_lang}. Leave as an empty string otherwise. {category_hint}",
      "gif_keywords": ["exactly 3 English single-word keywords that together visually represent \
this phrase's context. Focus on the action, object, and setting."]
    }}
  ]
}}

Rules:
- Only include phrases that are genuinely distinct contexts, not near-duplicate sentences
- Never return more than {max_meanings} phrase(s)
- Each phrase must wrap exactly one occurrence of the word (in whatever inflected form it takes) \
in double asterisks — do not wrap any other word in the sentence
- Synonyms must be in {source_lang}
- IPA must be standard {source_lang} IPA notation for the dictionary/citation form
- gif_keywords must be exactly 3 English single words
- gender must be 'Masculine' or 'Feminine' for nouns only, empty string otherwise
- text_meaning must be written entirely in {target_lang} — never include the literal \
{source_lang} word/term being defined
- phrase_translation must be a natural {target_lang} translation of the phrase
- category must reuse an existing category exactly (same spelling/casing) whenever it fits
- Return raw JSON only — no markdown fences, no extra text"""


PROMPT_TEMPLATE_PHRASE_NATIVE_WRITING = """You are a language expert creating Anki flashcard \
content for {target_lang} speakers learning {source_lang}.

For the word "{word}", generate up to {max_meanings} distinct sentences written ENTIRELY in \
{target_lang} (the learner's native language) that would naturally prompt a learner to produce \
this word in {source_lang} when translating the sentence. Then give the correct {source_lang} \
translation of each sentence, wrapping the EXACT inflected/conjugated surface form of the word \
you used with double asterisks, e.g. "Elle a **couru** jusqu'à la gare." — wrap only that one \
occurrence, using the literal form as it appears in your translation (which may differ from the \
dictionary/citation form given above, since word forms change with conjugation, gender, number, \
etc.).

Return ONLY a valid JSON object (no markdown, no explanation) with this exact structure:
{{
  "ipa": "IPA transcription for {source_lang} pronunciation of the dictionary form (e.g. mɛ.zɔ̃)",
  "pos": "part of speech in English (Noun / Verb / Adjective / Adverb / etc.) of the dictionary form",
  "gender": "For nouns only: 'Masculine' or 'Feminine'. Empty string for all other parts of speech.",
  "phrases": [
    {{
      "native_phrase": "A natural sentence written ENTIRELY in {target_lang} (10-15 words) that \
would prompt a learner to produce the word in {source_lang} when translating it.",
      "correct_translation": "The correct {source_lang} translation of the sentence above, with \
the exact inflected form of the word wrapped in **double asterisks**.",
      "text_meaning": "A single clear sentence written ENTIRELY in {target_lang} explaining what \
the word means AS USED in this translation. Do NOT include the {source_lang} word/term itself \
anywhere in this sentence. Refer to it only implicitly: 'Means to ...' for verbs, 'Describes \
something/someone that is ...' for adjectives, 'Refers to ...' or 'A type of ...' for nouns.",
      "synonyms": "up to 6 relevant {source_lang} synonyms for the word as used in this context, \
comma-separated",
      "category": "A short, reusable study-block label (2-4 words, Title Case) for this phrase, \
ONLY if it belongs to a recognizable grammar/vocabulary category specific to learning \
{source_lang}. Leave as an empty string otherwise. {category_hint}",
      "gif_keywords": ["exactly 3 English single-word keywords that together visually represent \
this sentence's context. Focus on the action, object, and setting."]
    }}
  ]
}}

Rules:
- Only include sentences that are genuinely distinct contexts, not near-duplicates
- Never return more than {max_meanings} sentence(s)
- native_phrase must be written entirely in {target_lang} — never include the literal \
{source_lang} word/term being tested
- correct_translation must wrap exactly one occurrence of the word (in whatever inflected form \
it takes) in double asterisks — do not wrap any other word in the sentence
- Synonyms must be in {source_lang}
- IPA must be standard {source_lang} IPA notation for the dictionary/citation form
- gif_keywords must be exactly 3 English single words
- gender must be 'Masculine' or 'Feminine' for nouns only, empty string otherwise
- text_meaning must be written entirely in {target_lang} — never include the literal \
{source_lang} word/term being defined
- category must reuse an existing category exactly (same spelling/casing) whenever it fits
- Return raw JSON only — no markdown fences, no extra text"""


def _clean_json_text(raw):
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return json.loads(raw)


def _call_groq(prompt, max_tokens=2048):
    payload = {
        "model":       config.AI_MODEL,
        "temperature": 0.3,
        "max_tokens":  max_tokens,
        "messages":    [{"role": "user", "content": prompt}],
    }
    resp = requests.post(GROQ_URL, headers=AI_HEADERS, json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"    [Groq] HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()["choices"][0]["message"]["content"]


def _call_openai(prompt, max_tokens=2048):
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       config.OPENAI_MODEL,
        "temperature": 0.3,
        "max_tokens":  max_tokens,
        "messages":    [{"role": "user", "content": prompt}],
    }
    resp = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"    [OpenAI] HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()["choices"][0]["message"]["content"]


def _call_anthropic(prompt, max_tokens=2048):
    try:
        import anthropic
    except ImportError:
        print("    [Claude] Missing dependency — run: pip install anthropic")
        return None
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return next((b.text for b in response.content if b.type == "text"), "")


def _gemini_retry_delay(resp):
    """Seconds to wait before retrying, per Google's own RetryInfo detail on
    a 429 response — respecting the server's own backoff signal instead of
    guessing, since Gemini's free tier enforces both per-minute and per-day
    quotas and only the server knows which one was hit."""
    try:
        details = resp.json().get("error", {}).get("details", [])
    except ValueError:
        return None
    for d in details:
        if d.get("@type", "").endswith("RetryInfo"):
            delay = d.get("retryDelay", "")
            if delay.endswith("s"):
                try:
                    return float(delay[:-1])
                except ValueError:
                    return None
    return None


# Adaptive per-minute throttle for Gemini, on top of whatever DELAY_AI is set
# to. DELAY_AI alone can't respect the free tier's RPM cap (e.g. 15 RPM for
# gemini-2.5-flash-lite) since it's a single fixed value shared by every
# provider, and users have no way to know the right number for whichever
# model Google currently grants free quota to. Instead this ratchets up a
# minimum spacing between requests every time a 429 is seen, so a long run
# self-tunes down to a sustainable pace instead of hammering the same wall
# every single word.
_gemini_last_call_ts = 0.0
_gemini_min_interval = 0.0


def _gemini_throttle():
    global _gemini_last_call_ts
    wait = _gemini_min_interval - (time.time() - _gemini_last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _gemini_last_call_ts = time.time()


def _gemini_post_with_retry(url, payload, max_retries=3):
    """POST to Gemini, retrying on 429 (rate limit) with the server's own
    suggested backoff. Returns the final response, whatever its status —
    the caller still has to handle non-200/non-429 outcomes."""
    global _gemini_min_interval
    attempt = 0
    while True:
        _gemini_throttle()
        resp = requests.post(
            url, params={"key": config.GEMINI_API_KEY}, json=payload, timeout=30
        )
        if resp.status_code != 429:
            return resp
        # Hitting 429 at all means the current pace is too fast for this
        # key's quota — widen the floor for every future call this run, not
        # just this retry loop, so later words don't repeat the same wait.
        _gemini_min_interval = min(max(_gemini_min_interval * 1.5, 5.0), 30.0)
        if attempt >= max_retries:
            return resp
        wait = _gemini_retry_delay(resp) or (5 * (attempt + 1))
        print(col(f"    [Gemini] Rate limited (429) — waiting {wait:.0f}s before "
                   f"retry {attempt + 1}/{max_retries}...", 'yellow'))
        time.sleep(wait)
        attempt += 1


def _call_gemini(prompt, max_tokens=2048):
    url = GEMINI_URL_TMPL.format(model=config.GEMINI_MODEL)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": max_tokens},
    }
    resp = _gemini_post_with_retry(url, payload)
    if resp.status_code == 429:
        print(col(
            "    [Gemini] Still rate-limited after retrying — the free tier's "
            "quota (per-minute or per-day) is exhausted. Slowing down to "
            f"1 request per {_gemini_min_interval:.0f}s for the rest of this run; "
            "this word will be retried on the next run rather than being "
            "skipped for good. Wait a bit, raise DELAY_AI in config.py, or "
            "switch AI_PROVIDER temporarily if this keeps happening.", 'red'))
        return None
    if resp.status_code != 200:
        print(f"    [Gemini] HTTP {resp.status_code}: {resp.text[:300]}")
        return None
    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        block_reason = data.get("promptFeedback", {}).get("blockReason")
        print(col(f"    [Gemini] Prompt blocked: {block_reason}" if block_reason
                   else f"    [Gemini] No candidates returned: {json.dumps(data)[:300]}", 'yellow'))
        return None
    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    if not text:
        print(col(f"    [Gemini] Empty response (finishReason="
                   f"{candidate.get('finishReason', 'UNKNOWN')})", 'yellow'))
        return None
    return text


def _ollama_model_pulled(model):
    """True if `model` is already pulled locally. Hitting /api/chat with a
    model that isn't pulled yet makes some Ollama versions silently start
    downloading it in the background — with stream=False that download
    produces zero output until it's fully done, which looks indistinguishable
    from the script hanging (this is the #1 real cause behind "generation
    gets stuck and doesn't move" reports). Checking first turns that into an
    immediate, actionable error instead."""
    try:
        resp = requests.get(f"{config.OLLAMA_HOST.rstrip('/')}/api/tags", timeout=5)
        if resp.status_code != 200:
            return True  # can't tell — don't block generation on this check
        pulled = {m.get("name", "").split(":")[0] for m in resp.json().get("models", [])}
        return model.split(":")[0] in pulled
    except requests.exceptions.RequestException:
        return True  # unreachable — let the real call below surface that error


def _call_ollama(prompt, max_tokens=2048):
    host = config.OLLAMA_HOST.rstrip('/')
    if not _ollama_model_pulled(config.OLLAMA_MODEL):
        print(col(
            f"    [Ollama] '{config.OLLAMA_MODEL}' isn't pulled yet on {host} — run "
            f"`ollama pull {config.OLLAMA_MODEL}` first, then try again.", 'yellow'))
        return None

    print(col(f"    [Ollama] Waiting on {config.OLLAMA_MODEL} — local CPU inference "
               f"can take a while, this is normal...", 'dim'))
    payload = {
        "model":    config.OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream":   False,
        "options":  {"temperature": 0.3, "num_predict": max_tokens},
    }
    try:
        # (connect timeout, read timeout) — connect fails fast if `ollama serve`
        # isn't running; read is generous since unaccelerated local inference of
        # a ~1000-token structured response can legitimately take minutes.
        resp = requests.post(f"{host}/api/chat", json=payload, timeout=(10, 300))
    except requests.exceptions.ConnectTimeout:
        print(col(f"    [Ollama] Can't reach {host} — is `ollama serve` running?", 'red'))
        return None
    except requests.exceptions.ConnectionError:
        print(col(f"    [Ollama] Connection refused at {host} — is `ollama serve` running "
                   f"and OLLAMA_HOST correct?", 'red'))
        return None
    except requests.exceptions.ReadTimeout:
        print(col(f"    [Ollama] No response after 5 minutes — '{config.OLLAMA_MODEL}' may be "
                   f"too large/slow for this machine. Try a smaller model.", 'red'))
        return None
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


def current_tts_provider():
    return getattr(config, "TTS_PROVIDER", "gtts")


# gTTS-style 2-letter codes (TTS_SOURCE_LANG / TTS_TARGET_LANG) -> Pocket TTS
# language identifiers. Pocket TTS only ships these 6 languages; anything
# else falls back to gTTS per-call — see generate_audio().
POCKET_TTS_LANG_MAP = {
    "en": "english",
    "fr": "french_24l",
    "de": "german_24l",
    "it": "italian",
    "pt": "portuguese",
    "es": "spanish_24l",
}

# Pocket TTS voice catalog per language. English has a wide selection;
# every other supported language currently ships exactly one voice.
POCKET_TTS_VOICES = {
    "english":     ["alba", "anna", "azelma", "bill_boerst", "caro_davy", "charles",
                     "cosette", "eponine", "eve", "fantine", "george", "jane",
                     "javert", "jean", "marius", "mary", "michael", "paul",
                     "peter_yearsley", "stuart_bell", "vera"],
    "french_24l":  ["estelle"],
    "german_24l":  ["juergen"],
    "italian":     ["giovanni"],
    "portuguese":  ["rafael"],
    "spanish_24l": ["lola"],
}

# Loading a Pocket TTS model (and deriving a voice state) is slow, so both
# are cached in memory for the lifetime of this process rather than redone
# per call — see CLAUDE.md § Local TTS provider.
_POCKET_TTS_MODELS = {}        # pocket-tts language id -> TTSModel
_POCKET_TTS_VOICE_STATES = {}  # (language id, voice name) -> voice state dict
_POCKET_TTS_WARNED_LANGS = set()  # gTTS lang codes already warned-and-fell-back-on


def _get_pocket_tts_model(language):
    if language not in _POCKET_TTS_MODELS:
        from pocket_tts import TTSModel
        print(col(f"    [Pocket TTS] Loading '{language}' model (first use, may take a moment)...", 'dim'))
        _POCKET_TTS_MODELS[language] = TTSModel.load_model(
            language=language, quantize=config.POCKET_TTS_QUANTIZE
        )
    return _POCKET_TTS_MODELS[language]


def _get_pocket_tts_voice_state(model, language, voice):
    key = (language, voice)
    if key not in _POCKET_TTS_VOICE_STATES:
        _POCKET_TTS_VOICE_STATES[key] = model.get_state_for_audio_prompt(voice)
    return _POCKET_TTS_VOICE_STATES[key]


def _warn_pocket_tts_unsupported_lang(lang):
    if lang not in _POCKET_TTS_WARNED_LANGS:
        _POCKET_TTS_WARNED_LANGS.add(lang)
        print(col(f"    [WARN] Pocket TTS has no '{lang}' model — falling back to gTTS for this language.", 'yellow'))


def _build_category_hint(known_categories):
    if not known_categories:
        return ("There are no existing categories yet for this deck — only introduce one "
                "if the word truly belongs to a distinct grammar/vocabulary study block.")
    listed = ", ".join(f'"{c}"' for c in known_categories)
    return (f"Categories already used in this deck: {listed}. Reuse one of these exactly "
            f"(same spelling/casing) if it fits — do not invent a near-duplicate name for "
            f"something already covered.")


def current_meaning_exhaustiveness():
    level = getattr(config, "MEANING_EXHAUSTIVENESS", "important")
    return MEANING_EXHAUSTIVENESS_SETTINGS.get(level, MEANING_EXHAUSTIVENESS_SETTINGS["important"])


def current_creation_mode():
    mode = getattr(config, "CREATION_MODE", "word_meaning")
    return mode if mode in CREATION_MODES else "word_meaning"


# ─────────────────────────────────────────────
#  Creation modes — what the AI is asked to generate, and what becomes the
#  Front (stimulus) vs Back (answer) of the card. Structurally parallel to
#  AI_PROVIDER_CALLERS above: one dict entry per mode, each pointing at its
#  own prompt builder / response parser / dedup-key function / field
#  extractor. Every mode still centers on one single anchor word — that's
#  what vocab::<POS>/topic::<Category> tagging and subdeck routing hang
#  off of, unmodified, regardless of which mode produced the card. See
#  CLAUDE.md § Creation modes for how to add a new one.
# ─────────────────────────────────────────────

def _build_word_meaning_prompt(word, known_categories):
    settings = current_meaning_exhaustiveness()
    prompt = PROMPT_TEMPLATE.format(
        word=word,
        source_lang=config.SOURCE_LANG,
        target_lang=config.TARGET_LANG,
        category_hint=_build_category_hint(known_categories),
        meaning_instruction=settings["instruction"],
        max_meanings=settings["max_meanings"],
    )
    return prompt, settings["max_tokens"]


def _parse_word_meaning_response(parsed):
    return {"ipa": parsed.get("ipa", ""), "items": parsed.get("meanings", [])}


def _content_key_word_meaning(word, item):
    return word.strip().lower(), None


def _word_meaning_extract(item):
    text = item.get("text_example_phrase", "")
    return {
        "text_meaning": item.get("text_meaning", ""),
        "text_example_phrase": text,
        "text_example_translation": item.get("text_example_translation", ""),
        "tts_example_text": text,
    }


def _build_phrase_context_prompt(word, known_categories):
    settings = current_meaning_exhaustiveness()
    prompt = PROMPT_TEMPLATE_PHRASE_CONTEXT.format(
        word=word,
        source_lang=config.SOURCE_LANG,
        target_lang=config.TARGET_LANG,
        category_hint=_build_category_hint(known_categories),
        max_meanings=settings["max_meanings"],
    )
    return prompt, settings["max_tokens"]


def _parse_phrase_context_response(parsed):
    top_pos    = parsed.get("pos", "")
    top_gender = parsed.get("gender", "")
    items = [{
        "pos": top_pos,
        "gender": top_gender,
        "phrase_raw": p.get("phrase", ""),
        "phrase_translation": p.get("phrase_translation", ""),
        "text_meaning": p.get("text_meaning", ""),
        "synonyms": p.get("synonyms", ""),
        "category": p.get("category", ""),
        "gif_keywords": p.get("gif_keywords", []),
    } for p in parsed.get("phrases", [])]
    return {"ipa": parsed.get("ipa", ""), "items": items}


def _content_key_phrase_context(word, item):
    stripped = item.get("phrase_raw", "").replace("**", "").strip()
    return hashlib.md5(stripped.lower().encode("utf-8")).hexdigest(), stripped


def _phrase_context_extract(item):
    raw = item.get("phrase_raw", "")
    return {
        "text_meaning": item.get("text_meaning", ""),
        "text_example_phrase": raw,                          # stored WITH ** markers
        "text_example_translation": item.get("phrase_translation", ""),
        "tts_example_text": raw.replace("**", "").strip(),    # stripped for TTS
    }


_PHRASE_CONTEXT_FRONT = """
<div class="example">{{Text_Example_Phrase}}</div>
{{Sound_Example}}
"""

_PHRASE_CONTEXT_BACK = """
{{FrontSide}}
<hr>
<div class="word">{{Word}}</div>
<div class="ipa">/ {{IPA}} /</div>
{{Gender}}
<div class="gif-box">{{Image}}</div>
<div class="meaning">{{Text_Meaning}}</div>
<div class="example-translation">{{Text_Example_Translation}}</div>
{{Sound_Word}}{{Sound_Meaning}}
{{Synonyms}}
"""


# ─────────────────────────────────────────────
#  audio_meaning / audio_writing / audio_typing — all 3 are still
#  word-anchored and want exactly the content word_meaning already
#  generates, so they reuse _build_word_meaning_prompt/
#  _parse_word_meaning_response/_content_key_word_meaning/
#  _word_meaning_extract verbatim (see CREATION_MODES below) — only their
#  Front/Back differ (audio-first, some fields hidden via CREATION_MODE_
#  VERBOSITY's always_omit/simple_omits, see _generate_loop()).
# ─────────────────────────────────────────────

_AUDIO_MEANING_FRONT = """
{{Sound_Word}}
"""

_AUDIO_MEANING_BACK = """
{{FrontSide}}
<hr>
<div class="word">{{Word}}</div>
{{#IPA}}<div class="ipa">/ {{IPA}} /</div>{{/IPA}}
{{Gender}}
<div class="gif-box">{{Image}}</div>
{{#Text_Meaning}}<div class="meaning">{{Text_Meaning}}</div>{{/Text_Meaning}}
{{Sound_Meaning}}
{{#Text_Example_Phrase}}<div class="example">{{Text_Example_Phrase}}</div>{{/Text_Example_Phrase}}
{{#Text_Example_Translation}}<div class="example-translation">{{Text_Example_Translation}}</div>{{/Text_Example_Translation}}
{{Sound_Example}}
{{Synonyms}}
"""

_AUDIO_WRITING_FRONT = """
{{Sound_Word}}
"""

_AUDIO_WRITING_BACK = """
{{FrontSide}}
<hr>
<div class="word">{{Word}}</div>
{{#IPA}}<div class="ipa">/ {{IPA}} /</div>{{/IPA}}
{{Gender}}
<div class="gif-box">{{Image}}</div>
{{Synonyms}}
"""

_AUDIO_TYPING_FRONT = """
{{Sound_Word}}
<br>
{{type:Word}}
"""

_AUDIO_TYPING_BACK = _AUDIO_WRITING_BACK   # identical reveal — only the Front differs


def _build_phrase_native_writing_prompt(word, known_categories):
    settings = current_meaning_exhaustiveness()
    prompt = PROMPT_TEMPLATE_PHRASE_NATIVE_WRITING.format(
        word=word,
        source_lang=config.SOURCE_LANG,
        target_lang=config.TARGET_LANG,
        category_hint=_build_category_hint(known_categories),
        max_meanings=settings["max_meanings"],
    )
    return prompt, settings["max_tokens"]


def _parse_phrase_native_writing_response(parsed):
    top_pos    = parsed.get("pos", "")
    top_gender = parsed.get("gender", "")
    items = [{
        "pos": top_pos,
        "gender": top_gender,
        "native_phrase": p.get("native_phrase", ""),
        "correct_translation": p.get("correct_translation", ""),
        "text_meaning": p.get("text_meaning", ""),
        "synonyms": p.get("synonyms", ""),
        "category": p.get("category", ""),
        "gif_keywords": p.get("gif_keywords", []),
    } for p in parsed.get("phrases", [])]
    return {"ipa": parsed.get("ipa", ""), "items": items}


def _content_key_phrase_native_writing(word, item):
    native = item.get("native_phrase", "").strip()
    return hashlib.md5(native.lower().encode("utf-8")).hexdigest(), native


def _phrase_native_writing_extract(item):
    correct = item.get("correct_translation", "")
    return {
        "text_meaning": item.get("text_meaning", ""),
        "text_example_phrase": correct,                          # SOURCE_LANG answer, WITH ** markers
        "text_example_translation": item.get("native_phrase", ""),  # TARGET_LANG prompt, shown on Front
        "tts_example_text": correct.replace("**", "").strip(),     # stripped for TTS
    }


_PHRASE_NATIVE_WRITING_FRONT = """
<div class="example-translation">{{Text_Example_Translation}}</div>
"""

_PHRASE_NATIVE_WRITING_BACK = """
{{FrontSide}}
<hr>
<div class="example">{{Text_Example_Phrase}}</div>
{{Sound_Example}}
<div class="word">{{Word}}</div>
{{#IPA}}<div class="ipa">/ {{IPA}} /</div>{{/IPA}}
{{Gender}}
<div class="gif-box">{{Image}}</div>
{{#Text_Meaning}}<div class="meaning">{{Text_Meaning}}</div>{{/Text_Meaning}}
{{Synonyms}}
"""


# ─────────────────────────────────────────────
#  phrase_audio_recognition / phrase_audio_typing — phrase-anchored
#  counterparts to audio_writing/audio_typing. Both reuse phrase_context's
#  prompt/parse/content_key verbatim (same content, audio-first
#  presentation). Only phrase_audio_typing needs its own extract_fields:
#  {{type:Text_Example_Phrase}} diffs against the field's literal value, so
#  it can't carry phrase_context's **markers** (those are fine for the
#  other phrase modes, which only ever reveal the field via
#  highlight_delimited(), never type-check it).
# ─────────────────────────────────────────────

_PHRASE_AUDIO_RECOGNITION_FRONT = """
{{Sound_Example}}
"""

_PHRASE_AUDIO_RECOGNITION_BACK = """
{{FrontSide}}
<hr>
<div class="example">{{Text_Example_Phrase}}</div>
<div class="word">{{Word}}</div>
{{#IPA}}<div class="ipa">/ {{IPA}} /</div>{{/IPA}}
{{Gender}}
<div class="gif-box">{{Image}}</div>
{{#Text_Meaning}}<div class="meaning">{{Text_Meaning}}</div>{{/Text_Meaning}}
{{#Text_Example_Translation}}<div class="example-translation">{{Text_Example_Translation}}</div>{{/Text_Example_Translation}}
{{Synonyms}}
"""


def _phrase_audio_typing_extract(item):
    raw = item.get("phrase_raw", "")
    stripped = raw.replace("**", "").strip()
    return {
        "text_meaning": item.get("text_meaning", ""),
        "text_example_phrase": stripped,       # clean — {{type:}} needs a verbatim match
        "text_example_translation": item.get("phrase_translation", ""),
        "tts_example_text": stripped,
    }


_PHRASE_AUDIO_TYPING_FRONT = """
{{Sound_Example}}
<br>
{{type:Text_Example_Phrase}}
"""

_PHRASE_AUDIO_TYPING_BACK = _PHRASE_AUDIO_RECOGNITION_BACK   # identical reveal — only the Front differs


CREATION_MODES = {
    "word_meaning": {
        "label":           "Word -> Meaning",
        "model_id_offset": 0,               # unchanged MODEL_ID; cloze still MODEL_ID+10
        "build_prompt":    _build_word_meaning_prompt,
        "parse_response":  _parse_word_meaning_response,
        "content_key":     _content_key_word_meaning,
        "extract_fields":  _word_meaning_extract,
        "uses_card_type":  True,
        # front/back intentionally absent — build_anki_model()'s word_meaning
        # branch keeps using template.FRONT/BACK + the existing CARD_TYPE
        # variants (_REVERSED_*, _TYPE_*, cloze) exactly as today.
    },
    "phrase_context": {
        "label":           "Phrase in Context",
        "model_id_offset": 20,              # +10 is cloze's existing offset
        "build_prompt":    _build_phrase_context_prompt,
        "parse_response":  _parse_phrase_context_response,
        "content_key":     _content_key_phrase_context,
        "extract_fields":  _phrase_context_extract,
        "uses_card_type":  False,
        "front":           _PHRASE_CONTEXT_FRONT,
        "back":            _PHRASE_CONTEXT_BACK,
    },
    "audio_meaning": {
        "label":           "Audio -> Meaning",
        "model_id_offset": 30,
        "build_prompt":    _build_word_meaning_prompt,     # reused verbatim — same content as word_meaning
        "parse_response":  _parse_word_meaning_response,
        "content_key":     _content_key_word_meaning,
        "extract_fields":  _word_meaning_extract,
        "uses_card_type":  False,
        "front":           _AUDIO_MEANING_FRONT,
        "back":            _AUDIO_MEANING_BACK,
        "simple_omits":    ("ipa", "gender", "synonyms", "text_example", "text_example_translation"),
    },
    "audio_writing": {
        "label":           "Audio Recognition",
        "model_id_offset": 40,
        "build_prompt":    _build_word_meaning_prompt,
        "parse_response":  _parse_word_meaning_response,
        "content_key":     _content_key_word_meaning,
        "extract_fields":  _word_meaning_extract,
        "uses_card_type":  False,
        "front":           _AUDIO_WRITING_FRONT,
        "back":            _AUDIO_WRITING_BACK,
        "always_omit":     ("text_meaning", "text_example", "text_example_translation"),
        "simple_omits":    ("ipa", "gender", "synonyms"),
    },
    "audio_typing": {
        "label":           "Audio Recognition Typing",
        "model_id_offset": 50,
        "build_prompt":    _build_word_meaning_prompt,
        "parse_response":  _parse_word_meaning_response,
        "content_key":     _content_key_word_meaning,
        "extract_fields":  _word_meaning_extract,
        "uses_card_type":  False,
        "front":           _AUDIO_TYPING_FRONT,
        "back":            _AUDIO_TYPING_BACK,
        "always_omit":     ("text_meaning", "text_example", "text_example_translation"),
        "simple_omits":    ("ipa", "gender", "synonyms"),
    },
    "phrase_native_writing": {
        "label":           "Write Response",
        "model_id_offset": 60,
        "build_prompt":    _build_phrase_native_writing_prompt,
        "parse_response":  _parse_phrase_native_writing_response,
        "content_key":     _content_key_phrase_native_writing,
        "extract_fields":  _phrase_native_writing_extract,
        "uses_card_type":  False,
        "front":           _PHRASE_NATIVE_WRITING_FRONT,
        "back":            _PHRASE_NATIVE_WRITING_BACK,
        "simple_omits":    ("ipa", "gender", "synonyms", "text_meaning"),
    },
    "phrase_audio_recognition": {
        "label":           "Phrase Audio Recognition",
        "model_id_offset": 70,
        "build_prompt":    _build_phrase_context_prompt,
        "parse_response":  _parse_phrase_context_response,
        "content_key":     _content_key_phrase_context,
        "extract_fields":  _phrase_context_extract,
        "uses_card_type":  False,
        "front":           _PHRASE_AUDIO_RECOGNITION_FRONT,
        "back":            _PHRASE_AUDIO_RECOGNITION_BACK,
        "simple_omits":    ("ipa", "gender", "synonyms", "text_meaning", "text_example_translation"),
    },
    "phrase_audio_typing": {
        "label":           "Phrase Audio Recognition Typing",
        "model_id_offset": 80,
        "build_prompt":    _build_phrase_context_prompt,
        "parse_response":  _parse_phrase_context_response,
        "content_key":     _content_key_phrase_context,
        "extract_fields":  _phrase_audio_typing_extract,
        "uses_card_type":  False,
        "front":           _PHRASE_AUDIO_TYPING_FRONT,
        "back":            _PHRASE_AUDIO_TYPING_BACK,
        "simple_omits":    ("ipa", "gender", "synonyms", "text_meaning", "text_example_translation"),
    },
}


def generate_card_content(word, known_categories=None, creation_mode=None):
    creation_mode = creation_mode or current_creation_mode()
    mode_def = CREATION_MODES[creation_mode]
    prompt, max_tokens = mode_def["build_prompt"](word, known_categories or [])

    provider = current_ai_provider()
    label    = AI_PROVIDER_LABELS.get(provider, provider)
    call_fn  = AI_PROVIDER_CALLERS.get(provider, _call_groq)
    try:
        raw = call_fn(prompt, max_tokens=max_tokens)
        if not raw:
            return None
        parsed = _clean_json_text(raw)
        return mode_def["parse_response"](parsed)
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
#  Audio generation (gTTS / Pocket TTS)
# ─────────────────────────────────────────────

def generate_audio_gtts(text, lang):
    filename = hashlib.md5((text + lang).encode()).hexdigest() + ".mp3"
    path     = os.path.join(config.AUDIO_DIR, filename)
    if not os.path.exists(path):
        gTTS(text=text, lang=lang).save(path)
        time.sleep(config.DELAY_TTS)
    return path, filename


def generate_audio(text, lang, voice_field="source"):
    """voice_field selects which Pocket TTS voice slot to use — "source" for
    word/example audio (TTS_SOURCE_LANG), "target" for meaning audio
    (TTS_TARGET_LANG). Ignored when TTS_PROVIDER = "gtts"."""
    if not config.ENABLE_AUDIO:
        return "", ""
    os.makedirs(config.AUDIO_DIR, exist_ok=True)

    if current_tts_provider() != "pocket_tts":
        return generate_audio_gtts(text, lang)

    pocket_lang = POCKET_TTS_LANG_MAP.get(lang)
    if pocket_lang is None:
        _warn_pocket_tts_unsupported_lang(lang)
        return generate_audio_gtts(text, lang)

    voice = (config.POCKET_TTS_VOICE_SOURCE if voice_field == "source"
             else config.POCKET_TTS_VOICE_TARGET)
    # Content-address on provider+voice too, so switching provider/voice
    # doesn't collide with a previously-cached gTTS mp3 for the same text+lang.
    filename = hashlib.md5(f"{text}{lang}pocket_tts{voice}".encode()).hexdigest() + ".wav"
    path     = os.path.join(config.AUDIO_DIR, filename)
    if os.path.exists(path):
        return path, filename

    try:
        import scipy.io.wavfile
        model = _get_pocket_tts_model(pocket_lang)
        state = _get_pocket_tts_voice_state(model, pocket_lang, voice)
        audio = model.generate_audio(state, text)
        scipy.io.wavfile.write(path, model.sample_rate, audio.numpy())
        return path, filename
    except ImportError:
        print(col("    [Pocket TTS] Missing dependency — run: pip install pocket-tts", 'yellow'))
        return generate_audio_gtts(text, lang)


# ─────────────────────────────────────────────
#  Formatting helpers
# ─────────────────────────────────────────────

def highlight_word(sentence, word):
    """Wrap the target word in a styled <span> inside the example sentence."""
    pattern = re.compile(re.escape(word), re.IGNORECASE)
    return pattern.sub(
        lambda m: f'<span class="highlight">{m.group()}</span>', sentence
    )


def highlight_delimited(text, delimiter="**", css_class="highlight"):
    """Convert **word**-delimited spans (as returned by the AI for
    phrase-based creation modes) into <span class="...">...</span>. Used
    instead of highlight_word()'s substring match because exact matching
    against the dictionary form fails for inflected/conjugated languages —
    the AI marks the exact surface form it actually used instead. Reuses
    the same "highlight" class highlight_word() uses (not a new one), so it
    picks up the identical `.example .highlight` CSS rule every CARD_TEMPLATE
    already defines — no template file needs to change for a new mode."""
    pattern = re.compile(re.escape(delimiter) + r"(.+?)" + re.escape(delimiter))
    return pattern.sub(lambda m: f'<span class="{css_class}">{m.group(1)}</span>', text)


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


def build_anki_model(template, card_type=None, creation_mode=None):
    """
    Build a genanki Model.
    card_type: "basic" | "basic_reversed" | "type_answer" | "cloze" — only
        meaningful when creation_mode == "word_meaning"; every other mode
        has exactly one fixed note shape (own Model, own MODEL_ID offset),
        the same way "cloze" already is a fixed alternate shape today.
    Defaults to config.CARD_TYPE / config.CREATION_MODE if not specified.
    """
    creation_mode = creation_mode or current_creation_mode()

    if creation_mode != "word_meaning":
        mode_def = CREATION_MODES[creation_mode]
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
        return genanki.Model(
            config.MODEL_ID + mode_def["model_id_offset"],
            f"{config.DECK_NAME} {mode_def['label']} Model",
            fields=fields,
            templates=[{
                "name": mode_def["label"],
                "qfmt": mode_def["front"],
                "afmt": mode_def["back"],
            }],
            css=template.CSS,
        )

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

def build_notes(cards, model, template, card_type=None, creation_mode=None):
    """
    Convert database rows into genanki Note objects.
    Returns (notes, media, ids) where each entry in `notes` is a
    (category, Note) pair — `category` is '' for the root deck, or a
    study-block label the caller routes into a `<Deck>::<Category>` subdeck.
    """
    creation_mode = creation_mode or current_creation_mode()

    if creation_mode != "word_meaning":
        notes = []
        media = []
        ids   = []
        needs_raw = getattr(template, "REQUIRES_RAW_IMAGE", False)
        for row in cards:
            (word_label, ipa, text_meaning, text_example,
             text_example_translation, synonyms, aw, am, ae,
             gif_url, gif_raw_url, gender_str, category, word, card_id) = row
            category = category.strip() if (category and config.ENABLE_CATEGORIES) else ""

            fields = [
                word_label,
                gif_url or "",
                sound_tag(aw) if config.ENABLE_WORD_AUDIO    else "",
                sound_tag(am) if config.ENABLE_MEANING_AUDIO else "",
                sound_tag(ae) if config.ENABLE_EXAMPLE_AUDIO else "",
                text_meaning,
                highlight_delimited(text_example),
                text_example_translation,
                ipa,
                gender_badge(gender_str),
                format_synonyms(synonyms),
            ]
            if needs_raw:
                fields.append(gif_raw_url or "")

            m = re.search(r"\(([^)]+)\)", word_label)
            tags = [f"vocab::{pos_to_tag(m.group(1) if m else '')}"]
            if category:
                tags.append(f"topic::{category_to_tag(category)}")

            notes.append((category, genanki.Note(model=model, fields=fields, tags=tags)))
            ids.append(card_id)
            for path in [aw, am, ae]:
                if path and os.path.exists(path):
                    media.append(path)

        return notes, list(set(media)), ids

    if card_type is None:
        card_type = config.CARD_TYPE

    notes     = []
    media     = []
    ids       = []
    needs_raw = getattr(template, "REQUIRES_RAW_IMAGE", False) and card_type != "cloze"

    for row in cards:
        (word_label, ipa, text_meaning, text_example,
         text_example_translation, synonyms, aw, am, ae,
         gif_url, gif_raw_url, gender_str, category, word, card_id) = row
        category = category.strip() if (category and config.ENABLE_CATEGORIES) else ""

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
        tags = [f"vocab::{tag}"]
        if category:
            tags.append(f"topic::{category_to_tag(category)}")

        notes.append((category, genanki.Note(
            model=model,
            fields=fields,
            tags=tags,
        )))
        ids.append(card_id)

        for path in [aw, am, ae]:
            if path and os.path.exists(path):
                media.append(path)

    return notes, list(set(media)), ids


def _build_deck_tree(base_id, base_name, categorized_notes):
    """
    Build one root genanki.Deck plus one subdeck per distinct category
    (deck name "<base_name>::<Category>"), and file each note into the
    right one. Returns the list of Deck objects for genanki.Package().
    """
    root = genanki.Deck(base_id, base_name)
    decks_by_category = {}
    decks = [root]

    for category, note in categorized_notes:
        if not category:
            root.add_note(note)
            continue
        deck = decks_by_category.get(category)
        if deck is None:
            deck = genanki.Deck(
                category_deck_id(base_id, category),
                category_deck_name(base_name, category),
            )
            decks_by_category[category] = deck
            decks.append(deck)
        deck.add_note(note)

    return decks, len(decks_by_category)


def _export_type_label(card_type, modes_present):
    """Identical to today's label whenever word_meaning is the only mode
    present in the DB — the case for every pre-existing user — so backward
    compatibility is concretely testable, not just assumed."""
    if modes_present == ["word_meaning"]:
        return _CARD_TYPE_LABELS.get(card_type, card_type)
    parts = []
    for m in modes_present:
        if m == "word_meaning":
            parts.append(f"word_meaning:{_CARD_TYPE_LABELS.get(card_type, card_type)}")
        else:
            parts.append(CREATION_MODES[m]["label"])
    return " + ".join(parts)


def export_decks(conn, template, card_type=None):
    """
    Export two .apkg files:
      - deck_new.apkg   : only cards not yet exported (import this daily)
      - deck_full.apkg  : all cards ever generated (full backup)

    Cards with a category are filed into a "<Deck>::<Category>" subdeck
    (e.g. "French Vocabulary::Phrasal Verbs") in addition to the root deck,
    controlled by config.ENABLE_CATEGORIES.

    Different creation_modes need different genanki Models (a Model fixes
    one field-set + one Front/Back for every Note built with it — it can't
    vary per-Note), so this collects cards per distinct creation_mode
    present in the DB, builds one Model per mode, and merges the resulting
    notes/media/ids into a single deck tree / .apkg per export.
    """
    if card_type is None:
        card_type = config.CARD_TYPE

    modes_present = [r[0] for r in conn.execute(
        "SELECT DISTINCT creation_mode FROM cards ORDER BY creation_mode"
    ).fetchall()] or ["word_meaning"]

    def _collect(new_only):
        notes, media, ids = [], [], []
        for mode in modes_present:
            mode_card_type = card_type if mode == "word_meaning" else None
            cards = get_all_cards(conn, new_only=new_only, creation_mode=mode)
            if not cards:
                continue
            model = build_anki_model(template, mode_card_type, creation_mode=mode)
            n, m, i = build_notes(cards, model, template, mode_card_type, creation_mode=mode)
            notes.extend(n)
            media.extend(m)
            ids.extend(i)
        return notes, list(set(media)), ids

    label = _export_type_label(card_type, modes_present)

    # New cards only
    new_notes, new_media, new_ids = _collect(new_only=True)
    if new_notes:
        decks, cat_count = _build_deck_tree(config.DECK_ID + 1, f"{config.DECK_NAME} — New", new_notes)
        pkg_new = genanki.Package(decks)
        pkg_new.media_files = new_media
        pkg_new.write_to_file(config.DECK_OUTPUT_NEW)
        mark_as_exported(conn, new_ids)
        conn.execute(
            "INSERT INTO export_log (type, card_count) VALUES (?, ?)",
            (f"new/{label}", len(new_notes))
        )
        conn.commit()
        subdeck_note = f"  ({cat_count} category subdeck{'s' if cat_count != 1 else ''})" if cat_count else ""
        print(f"\n[OK] New cards    : {config.DECK_OUTPUT_NEW}  ({len(new_notes)} cards)  [{label}]{subdeck_note}")
        print(f"     -> Import THIS file into Anki to preserve your manual edits.")
    else:
        print(f"\n[INFO] No new cards to export.")

    # Full backup
    full_notes, full_media, _ = _collect(new_only=False)
    decks_full, cat_count_full = _build_deck_tree(config.DECK_ID, config.DECK_NAME, full_notes)
    pkg_full = genanki.Package(decks_full)
    pkg_full.media_files = full_media
    pkg_full.write_to_file(config.DECK_OUTPUT_FULL)
    conn.execute(
        "INSERT INTO export_log (type, card_count) VALUES (?, ?)",
        (f"full/{label}", len(full_notes))
    )
    conn.commit()
    subdeck_note_full = f"  ({cat_count_full} category subdeck{'s' if cat_count_full != 1 else ''})" if cat_count_full else ""
    print(f"    Full backup : {config.DECK_OUTPUT_FULL}  ({len(full_notes)} cards total)  [{label}]{subdeck_note_full}")


# ─────────────────────────────────────────────
#  Menu screens
# ─────────────────────────────────────────────

def _stats_data(conn):
    """Same figures as show_statistics(), as plain data for --stats-json."""
    total     = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    new_count = conn.execute("SELECT COUNT(*) FROM cards WHERE exported=0").fetchone()[0]
    exported  = conn.execute("SELECT COUNT(*) FROM cards WHERE exported=1").fetchone()[0]

    by_pos = conn.execute("""
        SELECT pos, COUNT(*) AS cnt FROM cards
        WHERE pos != ''
        GROUP BY pos ORDER BY cnt DESC
    """).fetchall()

    recent_days = conn.execute("""
        SELECT date_added, COUNT(*) FROM cards
        GROUP BY date_added ORDER BY date_added DESC LIMIT 7
    """).fetchall()

    recent_exports = conn.execute("""
        SELECT date, type, card_count FROM export_log
        ORDER BY date DESC LIMIT 5
    """).fetchall()

    return {
        "total": total,
        "exported": exported,
        "pending": new_count,
        "by_pos": [{"pos": p, "count": c} for p, c in by_pos],
        "recent_days": [{"date": d, "count": c} for d, c in recent_days],
        "recent_exports": [{"date": d, "type": t, "count": c} for d, t, c in recent_exports],
    }


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
        SELECT category, COUNT(*) AS cnt FROM cards
        WHERE category != ''
        GROUP BY category ORDER BY cnt DESC
    """).fetchall()
    if rows:
        print(col('  By Category (subdecks):', 'bold'))
        for category, cnt in rows:
            bar = col('█' * min(cnt, 28), 'cyan')
            print(f'  {(category + ":").ljust(24)} {col(str(cnt).rjust(4), "yellow")}  {bar}')
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

_MEANING_EXHAUSTIVENESS_OPTIONS = [
    ("essential", "Essential only — 1 meaning per word"),
    ("important", "Most important — up to 5 meanings (default)"),
    ("all",       "All meanings — up to 12, larger AI token budget"),
]

_TTS_PROVIDERS = [
    ("gtts",       "gTTS — cloud (Google Translate TTS), one voice per language (default)"),
    ("pocket_tts", "Pocket TTS — local/CPU, multiple realistic voices (Kyutai Labs)"),
]

# "Card content" — a guided 2-step flow (Word-based / Phrase-based, then
# "how do you want to be tested?") replaces a single flat CREATION_MODE
# picker + a separate CARD_TYPE picker. _WORD_TESTING_OPTIONS values that
# contain ":" combine CREATION_MODE + CARD_TYPE into one choice (see
# _WordTestingPicker below) since word_meaning's 4 CARD_TYPE variants are,
# from the user's perspective, just more "how tested" answers for word
# content, not a separate axis. Only modes with a real CREATION_MODES
# registry entry are listed — deliberately not exposing
# selectable-but-unimplemented modes in either TUI.
_WORD_FAMILY_MODES = {"word_meaning", "audio_meaning", "audio_writing", "audio_typing"}
_PHRASE_FAMILY_MODES = {"phrase_context", "phrase_native_writing",
                         "phrase_audio_recognition", "phrase_audio_typing"}

_WORD_TESTING_OPTIONS = [
    ("word_meaning:basic",          "See the meaning"),
    ("word_meaning:basic_reversed", "See the meaning, both directions"),
    ("word_meaning:type_answer",    "See the meaning, type the word"),
    ("word_meaning:cloze",          "Fill in the blank in a sentence"),
    ("audio_meaning",               "Hear it, recall the meaning"),
    ("audio_writing",               "Hear it, recall the spelling"),
    ("audio_typing",                "Hear it, type what you heard"),
]

_PHRASE_TESTING_OPTIONS = [
    ("phrase_context",           "See the meaning in context"),
    ("phrase_native_writing",    "Write the translation"),
    ("phrase_audio_recognition", "Hear it, recall the phrase"),
    ("phrase_audio_typing",      "Hear it, type what you heard"),
]

_CREATION_MODE_VERBOSITY_OPTIONS = [
    ("complete", "Complete — every applicable field filled in (default)"),
    ("simple",   "Simple — only the essential fields"),
]

_WORD_SOURCE_OPTIONS = [
    ("frequency_list", "Frequency word list (default)"),
    ("markdown_notes", "Markdown notes / Obsidian vault"),
]

_MARKDOWN_EXTRACTION_OPTIONS = [
    ("highlights", "Only ==highlighted== text (recommended)"),
    ("all_words",  "Every word, ranked by frequency in your notes"),
]


def _options_snapshot():
    """Static picker option lists, as JSON, for alternative frontends
    (e.g. the JS TUI in cli/) so they never hardcode a second copy."""
    return {
        "app_version":          _version.APP_VERSION,
        "ai_providers":         _AI_PROVIDERS,
        "groq_models":          _GROQ_MODELS,
        "anthropic_models":     _ANTHROPIC_MODELS,
        "templates":            _TEMPLATES,
        "card_types":           _CARD_TYPES,
        "card_type_labels":     _CARD_TYPE_LABELS,
        "gif_ratings":          _GIF_RATINGS,
        "provider_labels":      AI_PROVIDER_LABELS,
        "provider_model_field": AI_PROVIDER_MODEL_FIELD,
        "provider_key_field":   AI_PROVIDER_KEY_FIELD,
        "tts_providers":        _TTS_PROVIDERS,
        "pocket_tts_lang_map":  POCKET_TTS_LANG_MAP,
        "pocket_tts_voices":    POCKET_TTS_VOICES,
        "meaning_exhaustiveness_options": _MEANING_EXHAUSTIVENESS_OPTIONS,
        "word_testing_options":   _WORD_TESTING_OPTIONS,
        "phrase_testing_options": _PHRASE_TESTING_OPTIONS,
        "creation_mode_verbosity_options": _CREATION_MODE_VERBOSITY_OPTIONS,
        "word_sources":         _WORD_SOURCE_OPTIONS,
        "markdown_extraction_modes": _MARKDOWN_EXTRACTION_OPTIONS,
    }


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
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        val_repr = f'"{escaped}"'

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
                               hint='e.g. gemini-2.5-flash-lite  gemini-2.5-flash  (free tier shifts often)'),
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
        _tui.TextInput('Output — new deck',  'DECK_OUTPUT_NEW',
                       hint='.apkg file to import into Anki daily'),
        _tui.TextInput('Output — full deck', 'DECK_OUTPUT_FULL',
                       hint='.apkg full backup file'),
        _tui.Separator(),
        _tui.Toggle('Category subdecks & tags', 'ENABLE_CATEGORIES',
                    hint='Files cards like "Phrasal Verbs" into <Deck>::<Category> + topic:: tag'),
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
        _tui.Picker('Meaning exhaustiveness', 'MEANING_EXHAUSTIVENESS',
                    _MEANING_EXHAUSTIVENESS_OPTIONS,
                    hint='How many distinct meanings (cards) per word'),
        _tui.Separator(),
        _tui.Picker('Word source', 'WORD_SOURCE', _WORD_SOURCE_OPTIONS,
                    hint='Where candidate words come from'),
        _tui.TextInput('Markdown notes folder', 'MARKDOWN_NOTES_PATH',
                       hint='Folder scanned recursively for *.md files'),
        _tui.Picker('Markdown extraction', 'MARKDOWN_EXTRACTION_MODE', _MARKDOWN_EXTRACTION_OPTIONS,
                    hint='Only used when Word source = Markdown notes'),
        _tui.Separator(),
        _tui.Back(),
    ])


class _WordTestingPicker(_tui.Picker):
    """Combines CREATION_MODE + CARD_TYPE into one choice — the
    word_meaning-family options need both keys written together."""

    def _idx(self):
        mode = getattr(config, 'CREATION_MODE', 'word_meaning')
        val = f"word_meaning:{getattr(config, 'CARD_TYPE', 'basic')}" if mode == 'word_meaning' else mode
        for i, (v, _) in enumerate(self.options):
            if v == val:
                return i
        return 0

    def _set(self, idx):
        value = self.options[idx % len(self.options)][0]
        if ':' in value:
            mode, card_type = value.split(':', 1)
            write_config('CREATION_MODE', mode)
            write_config('CARD_TYPE', card_type)
        else:
            write_config('CREATION_MODE', value)


def _word_content_hint():
    mode = current_creation_mode()
    if mode not in _WORD_FAMILY_MODES:
        return ''
    key = f"word_meaning:{config.CARD_TYPE}" if mode == "word_meaning" else mode
    return dict(_WORD_TESTING_OPTIONS).get(key, mode)


def _phrase_content_hint():
    mode = current_creation_mode()
    return dict(_PHRASE_TESTING_OPTIONS).get(mode, '') if mode in _PHRASE_FAMILY_MODES else ''


def _configure_word_content():
    _tui.run_menu('Word-Based Cards', [
        _WordTestingPicker('How do you want to be tested?', 'CREATION_MODE', _WORD_TESTING_OPTIONS),
        _tui.Separator(),
        _tui.Back(),
    ])


def _configure_phrase_content():
    _tui.run_menu('Phrase-Based Cards', [
        _tui.Picker('How do you want to be tested?', 'CREATION_MODE', _PHRASE_TESTING_OPTIONS),
        _tui.Separator(),
        _tui.Back(),
    ])


def configure_card_content():
    _tui.run_menu('Card Content', [
        _tui.Action('Word-based cards',   _configure_word_content,   _word_content_hint),
        _tui.Action('Phrase-based cards', _configure_phrase_content, _phrase_content_hint),
        _tui.Separator(),
        _tui.Picker('Field verbosity', 'CREATION_MODE_VERBOSITY', _CREATION_MODE_VERBOSITY_OPTIONS,
                    hint='Simple/complete fields — audio & production styles only'),
        _tui.Separator(),
        _tui.Back(),
    ])


def _pocket_tts_voice_options(lang_code):
    pocket_lang = POCKET_TTS_LANG_MAP.get(lang_code, "english")
    voices      = POCKET_TTS_VOICES.get(pocket_lang, POCKET_TTS_VOICES["english"])
    return [(v, v.replace("_", " ").title()) for v in voices]


def configure_pocket_tts():
    _tui.run_menu('Pocket TTS Settings', [
        _tui.Picker('Source voice', 'POCKET_TTS_VOICE_SOURCE',
                    _pocket_tts_voice_options(config.TTS_SOURCE_LANG),
                    hint=f'Word + example audio ({config.TTS_SOURCE_LANG})'),
        _tui.Picker('Target voice', 'POCKET_TTS_VOICE_TARGET',
                    _pocket_tts_voice_options(config.TTS_TARGET_LANG),
                    hint=f'Meaning audio ({config.TTS_TARGET_LANG})'),
        _tui.Separator(),
        _tui.Toggle('Int8 quantization', 'POCKET_TTS_QUANTIZE',
                    hint='Less RAM, faster, no quality loss — needs pocket-tts[quantize]'),
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
        _tui.Picker('TTS provider', 'TTS_PROVIDER', _TTS_PROVIDERS),
        _tui.Action('Pocket TTS settings',
                    configure_pocket_tts,
                    lambda: (f'{config.POCKET_TTS_VOICE_SOURCE} / {config.POCKET_TTS_VOICE_TARGET}'
                             if current_tts_provider() == 'pocket_tts' else 'n/a — gTTS selected')),
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
        _tui.NumberInput('AI delay',      'DELAY_AI',    min_val=0.0, step=0.1, is_float=True),
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
        _tui.Action('Card content',
                    configure_card_content,
                    lambda: (_word_content_hint() or _phrase_content_hint())),
        _tui.Action('Deck & cards',
                    configure_deck,
                    lambda: config.CARD_TEMPLATE),
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
#  Word sources — where candidate words come from (see config.WORD_SOURCE)
# ─────────────────────────────────────────────

_MD_FRONTMATTER_RE = re.compile(r'\A---\n.*?\n---\n', re.DOTALL)
_MD_CODE_FENCE_RE  = re.compile(r'```.*?```', re.DOTALL)
_MD_INLINE_CODE_RE = re.compile(r'`[^`\n]*`')
_MD_EMBED_RE       = re.compile(r'!\[\[([^\]|]+)(?:\|[^\]]*)?\]\]')
_MD_WIKILINK_RE    = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]*))?\]\]')
_MD_LINK_RE        = re.compile(r'\[([^\]]*)\]\([^)]*\)')
_MD_HEADING_RE     = re.compile(r'^#{1,6}\s+', re.MULTILINE)
_MD_HIGHLIGHT_RE   = re.compile(r'==(.+?)==', re.DOTALL)
_MD_WORD_RE        = re.compile(r'\b[^\W\d_]{2,}\b', re.UNICODE)


def _iter_markdown_files(root):
    """Yield every *.md file path under root, sorted for deterministic,
    reproducible pool order across runs."""
    paths = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith('.md'):
                paths.append(os.path.join(dirpath, name))
    return sorted(paths)


def _strip_markdown_noise(text):
    """Lightweight regex cleanup — strips YAML frontmatter, code, and
    link/embed/heading syntax while keeping their visible display text."""
    text = _MD_FRONTMATTER_RE.sub('', text)
    text = _MD_CODE_FENCE_RE.sub(' ', text)
    text = _MD_INLINE_CODE_RE.sub(' ', text)
    text = _MD_EMBED_RE.sub(r'\1', text)
    text = _MD_WIKILINK_RE.sub(lambda m: m.group(2) or m.group(1), text)
    text = _MD_LINK_RE.sub(r'\1', text)
    text = _MD_HEADING_RE.sub('', text)
    return text


def _extract_highlights(text):
    """Return every ==highlighted== span, in file order."""
    return [m.group(1).strip() for m in _MD_HIGHLIGHT_RE.finditer(text) if m.group(1).strip()]


def _extract_all_words(text):
    """Return every alphabetic word (Unicode-aware, length >= 2), lowercased."""
    return [w.lower() for w in _MD_WORD_RE.findall(text)]


def _build_markdown_word_pool():
    """Build the candidate word pool from config.MARKDOWN_NOTES_PATH,
    per config.MARKDOWN_EXTRACTION_MODE. Returns [] (with a [WARN]) instead
    of raising on a missing/empty path — this is a user-config boundary."""
    root = getattr(config, 'MARKDOWN_NOTES_PATH', '')
    if not root or not os.path.isdir(root):
        print(col(f'  [WARN] MARKDOWN_NOTES_PATH "{root}" is not a valid folder — word pool is empty.', 'yellow'))
        return []

    mode = getattr(config, 'MARKDOWN_EXTRACTION_MODE', 'highlights')
    highlights_seen = []
    highlights_seen_set = set()
    word_counts = Counter()

    for path in _iter_markdown_files(root):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = f.read()
        except OSError:
            continue
        cleaned = _strip_markdown_noise(raw)

        if mode == 'highlights':
            for span in _extract_highlights(cleaned):
                key = span.lower()
                if key not in highlights_seen_set:
                    highlights_seen_set.add(key)
                    highlights_seen.append(span)
        else:
            word_counts.update(_extract_all_words(cleaned))

    if mode == 'highlights':
        pool = highlights_seen
    else:
        pool = [w for w, _count in sorted(word_counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    return pool[:config.TOTAL_WORD_POOL]


WORD_SOURCES = {
    "frequency_list": lambda: top_n_list(config.SOURCE_LANG, config.TOTAL_WORD_POOL),
    "markdown_notes": _build_markdown_word_pool,
}


def get_word_pool():
    """Dispatch to the active config.WORD_SOURCE's pool builder."""
    source = getattr(config, 'WORD_SOURCE', 'frequency_list')
    return WORD_SOURCES.get(source, WORD_SOURCES['frequency_list'])()


# ─────────────────────────────────────────────
#  Generation and export runners
# ─────────────────────────────────────────────

def _do_generate(conn):
    """Card generation loop, printing but not pausing. Shared by the
    interactive curses menu and the headless --generate CLI flag."""
    print_banner()
    print(col('  Generate New Cards', 'bold', 'cyan'))
    print(f'  {"─" * 52}')

    if ai_key_missing():
        field = AI_PROVIDER_KEY_FIELD.get(current_ai_provider(), "GROQ_API_KEY")
        print(col(f'\n  [ERROR] {field} not set in config.py', 'red'))
        return

    if config.ENABLE_GIF and config.GIPHY_API_KEY == "your_giphy_api_key_here":
        print(col('  [WARN] GIPHY_API_KEY not set — GIFs disabled for this run.', 'yellow'))
        config.ENABLE_GIF = False

    all_words = get_word_pool()
    processed = get_processed_words(conn, current_creation_mode())
    pending   = [w for w in all_words if w not in processed]

    print(f'\n  Word pool   : {col(str(len(all_words)), "yellow")}')
    print(f'  In database : {col(str(len(processed)), "green")}')
    print(f'  Pending     : {col(str(len(pending)), "cyan")}')
    print(f'  This run    : {col(f"up to {config.WORDS_PER_RUN} words", "yellow")}')
    print()

    if not pending:
        print(col('  [WARN] Word pool exhausted!', 'yellow'))
        print(f'  Increase TOTAL_WORD_POOL in config.py (currently {config.TOTAL_WORD_POOL}).')
        return

    _generate_loop(conn, pending, config.WORDS_PER_RUN)


def run_generate(conn):
    """Card generation loop (interactive)."""
    _do_generate(conn)
    pause()


def _do_export(conn, card_type):
    """Export decks for a given card type, printing but not pausing. Shared
    by the interactive curses menu and the headless --export CLI flag."""
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


def run_export(conn):
    """Card type selection + export (interactive)."""
    card_type = select_card_type()
    _do_export(conn, card_type)
    pause()


def _generate_loop(conn, pending, limit):
    """Core word-processing loop used by both interactive and headless modes."""
    processed_count  = 0
    creation_mode    = current_creation_mode()
    mode_def         = CREATION_MODES[creation_mode]
    known_categories = get_known_categories(conn) if config.ENABLE_CATEGORIES else []

    # Fields this mode never shows (always_omit) or hides only in "simple"
    # verbosity (simple_omits) — see CLAUDE.md § Creation modes. Empty for
    # word_meaning/phrase_context, which never declare either list.
    omit = set(mode_def.get("always_omit", ()))
    if getattr(config, "CREATION_MODE_VERBOSITY", "complete") == "simple":
        omit |= set(mode_def.get("simple_omits", ()))

    for word in pending:
        if processed_count >= limit:
            break

        print(f'  [{processed_count + 1}/{limit}] {col(word, "bold")}')

        ai_data = generate_card_content(word, known_categories, creation_mode)
        time.sleep(config.DELAY_AI)

        if not ai_data:
            # Deliberately not saved to the DB: get_processed_words() keys
            # off any row existing for this (word, creation_mode) pair, so
            # a stub row here would permanently exclude the word from every
            # future run's pending list for this mode — turning a transient
            # failure (rate limit, timeout, bad JSON) into a silently lost
            # word forever. Leaving it unsaved means it's just picked up
            # again on the next run.
            print(col('    [WARN] AI failed — skipping (will retry next run)', 'yellow'))
            processed_count += 1
            continue

        ipa   = "" if "ipa" in omit else ai_data.get("ipa", "")
        items = ai_data.get("items", [])

        if not items:
            print(col('    [WARN] No content returned — skipping', 'yellow'))
            processed_count += 1
            continue

        # Word-level audio (generated once per word)
        audio_word_path = ""
        if config.ENABLE_AUDIO and config.ENABLE_WORD_AUDIO:
            try:
                audio_word_path, _ = generate_audio(word, lang=config.TTS_SOURCE_LANG, voice_field="source")
                print(col('    [AUDIO] Word audio', 'dim'))
            except Exception as e:
                print(col(f'    [WARN] Word audio error: {e}', 'yellow'))

        for meaning_id, item in enumerate(items):
            content_key, source_phrase = mode_def["content_key"](word, item)
            if card_exists(conn, creation_mode, content_key, meaning_id):
                print(col(f'    [SKIP] Item {meaning_id} already in DB', 'dim'))
                continue

            fields = mode_def["extract_fields"](item)
            pos                      = item.get("pos", "")
            gender                   = "" if "gender" in omit else item.get("gender", "")
            text_meaning             = "" if "text_meaning" in omit else fields["text_meaning"]
            text_example             = "" if "text_example" in omit else fields["text_example_phrase"]
            text_example_translation = "" if "text_example_translation" in omit else fields["text_example_translation"]
            tts_example_text         = "" if "text_example" in omit else fields["tts_example_text"]
            synonyms                 = "" if "synonyms" in omit else item.get("synonyms", "")
            gif_keywords             = item.get("gif_keywords", [])
            category                 = (item.get("category") or "").strip() if config.ENABLE_CATEGORIES else ""
            if category and category not in known_categories:
                known_categories.append(category)

            word_label = f"{word} ({pos})" if len(items) > 1 and pos else word

            audio_example_path = ""
            if config.ENABLE_AUDIO and config.ENABLE_EXAMPLE_AUDIO and tts_example_text:
                try:
                    audio_example_path, _ = generate_audio(
                        tts_example_text, lang=config.TTS_SOURCE_LANG, voice_field="source"
                    )
                    print(col(f'    [AUDIO] Example — item {meaning_id}', 'dim'))
                except Exception as e:
                    print(col(f'    [WARN] Example audio error: {e}', 'yellow'))

            audio_meaning_path = ""
            if config.ENABLE_AUDIO and config.ENABLE_MEANING_AUDIO and text_meaning:
                try:
                    audio_meaning_path, _ = generate_audio(
                        text_meaning, lang=config.TTS_TARGET_LANG, voice_field="target"
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
                "category":                  category,
                "creation_mode":             creation_mode,
                "content_key":               content_key,
                "source_phrase":             source_phrase,
            })
            cat_suffix = col(f'  [{category}]', 'cyan') if category else ''
            print(col(f'    [DONE] [{word_label}] {text_meaning[:60]}...', 'green') + cat_suffix)

        processed_count += 1

    print(col(f'\n  {processed_count} words processed this run.', 'green', 'bold'))
    return processed_count


# ─────────────────────────────────────────────
#  CLI bridge — JSON / headless flags for alternative frontends
#  (e.g. the JS TUI in cli/). Kept additive: --run is unaffected.
# ─────────────────────────────────────────────

def _config_snapshot():
    """Every public primitive setting in config.py, as JSON. Generic (reads
    whatever config.py exposes) so it never drifts from the real settings."""
    return {
        k: getattr(config, k)
        for k in dir(config)
        if not k.startswith('_') and isinstance(getattr(config, k), (str, int, float, bool))
    }


def _coerce_value(raw, type_name):
    if type_name == "bool":
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if type_name == "int":
        return int(raw)
    if type_name == "float":
        return float(raw)
    return raw


def _parse_flags(argv):
    """Parse '--key=value' / bare '--key' tokens into a dict."""
    flags = {}
    for arg in argv:
        if not arg.startswith('--'):
            continue
        key = arg[2:]
        if '=' in key:
            key, value = key.split('=', 1)
            flags[key] = value
        else:
            flags[key] = True
    return flags


def _run_cli_bridge(flags):
    """Handle a recognized bridge flag. Returns True if one was handled."""
    if 'generate' in flags:
        conn = init_db()
        _do_generate(conn)
        conn.close()
        return True

    if 'export' in flags:
        card_type = flags['export'] if isinstance(flags['export'], str) else config.CARD_TYPE
        conn = init_db()
        _do_export(conn, card_type)
        conn.close()
        return True

    if 'stats-json' in flags:
        conn = init_db()
        print(json.dumps(_stats_data(conn)))
        conn.close()
        return True

    if 'config-json' in flags:
        print(json.dumps(_config_snapshot()))
        return True

    if 'options-json' in flags:
        print(json.dumps(_options_snapshot()))
        return True

    if 'set-config' in flags:
        key       = flags['set-config']
        raw       = flags.get('value', '')
        type_name = flags.get('type', 'str')
        ok = write_config(key, _coerce_value(raw, type_name))
        print(json.dumps({"ok": ok}))
        return True

    return False


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

def _run_headless():
    """Non-interactive mode: generate + export without a menu (--run flag)."""
    print("=" * 60)
    print(f"  Anki Vocabulary Deck Generator  v{_version.APP_VERSION}  [headless]")
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
    all_words = get_word_pool()
    processed = get_processed_words(conn, current_creation_mode())
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

    flags = _parse_flags(sys.argv[1:])
    if flags and _run_cli_bridge(flags):
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
