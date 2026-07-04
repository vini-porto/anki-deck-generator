# CLAUDE.md — Project Context for Claude Code

This file gives you full context about the project so you can assist
with new features, refactoring, and bug fixes effectively.

Current version: **v2.0** (branch: `v2-interactive-menu`)
Changes from v1: interactive menu, 4 card types, statistics screen, settings view.

---

## What this project does

Generates rich Anki flashcard decks (.apkg) for vocabulary learning.
For each word in a frequency list, it:
1. Calls the Groq API (LLaMA 3) to generate all card content via a structured JSON prompt.
2. Fetches an animated GIF from Giphy using 3 AI-generated hashtag keywords.
3. Generates 3 MP3 audio files via gTTS (word, example sentence, meaning).
4. Saves everything to a SQLite database (progress.db).
5. Exports two .apkg files: one with only new cards (import daily) and one full backup.

The script is incremental — it tracks which words have been processed and
which cards have been exported, so it can be run daily without duplicating content
or overwriting manual edits the user has made inside Anki.

---

## File structure

```
anki-deck-generator/
├── main.py              # Main script — all logic + interactive menu
├── config.py            # All user-configurable settings (API keys, language, etc.)
├── requirements.txt     # pip dependencies
├── CLAUDE.md            # This file
├── README.md            # GitHub documentation
├── .gitignore
└── template/            # Note: folder is "template" (no 's'), import is "import template"
    ├── __init__.py      # Loads and exposes all templates via tmpl_registry.load(name)
    ├── dark.py          # Dark mode (Catppuccin Mocha palette) — default
    ├── light.py         # Light mode with soft color accents
    ├── minimal.py       # Text only, no GIF, no gender badge
    └── immersive.py     # GIF as full card background with text overlay
```

## Running the script

- **Interactive (default):** `python main.py` — shows the main menu
- **Headless (automation/cron):** `python main.py --run` — generates + exports without menu

---

## Card fields (Anki model)

Every card has these 11 fields:

| Field | Content |
|---|---|
| `Word` | The word, optionally labeled with POS: "maison (Noun)" |
| `Image` | HTML `<img>` tag with Giphy GIF URL |
| `Sound_Word` | `[sound:xxx.mp3]` — word pronunciation |
| `Sound_Meaning` | `[sound:xxx.mp3]` — meaning read aloud in target language |
| `Sound_Example` | `[sound:xxx.mp3]` — example sentence read aloud |
| `Text_Meaning` | Dictionary-style definition in target language |
| `Text_Example_Phrase` | Natural sentence (10–15 words) with word highlighted |
| `Text_Example_Translation` | Translation of the example sentence |
| `IPA` | Phonetic transcription |
| `Gender` | HTML badge: "♂ Masculine" or "♀ Feminine" (nouns only) |
| `Synonyms` | HTML badges for up to 6 synonyms |

The immersive template adds a 12th field: `Image_Raw` (plain GIF URL, no HTML tag),
used to set the GIF as a CSS background via JavaScript.

---

## Database schema (progress.db)

Table: `cards`
- `id`, `word`, `word_label`, `meaning_id` — identity
- `pos`, `ipa`, `gender` — linguistic metadata
- `text_meaning`, `text_example_phrase`, `text_example_translation`, `synonyms` — text content
- `audio_word`, `audio_meaning`, `audio_example` — paths to MP3 files in audio_files/
- `gif_url` (HTML img tag), `gif_raw_url` (plain URL)
- `exported` (0/1) — tracks whether card has been included in deck_new.apkg
- `date_added`

Table: `export_log` — tracks export history (date, type, card count)

Uniqueness constraint: `(word, meaning_id)` — one row per word per distinct meaning.

Soft migrations are applied on every `init_db()` call via ALTER TABLE,
so the database schema can be extended without breaking existing databases.

---

## Groq prompt structure

The prompt asks for a JSON response with this shape:
```json
{
  "ipa": "...",
  "meanings": [
    {
      "pos": "Noun",
      "gender": "Feminine",
      "text_meaning": "...",
      "text_example_phrase": "...",
      "text_example_translation": "...",
      "synonyms": "word1, word2, word3",
      "gif_keywords": ["keyword1", "keyword2", "keyword3"]
    }
  ]
}
```

- One entry per distinct meaning of the word.
- `gif_keywords` must be exactly 3 English single words used to build the Giphy query.
- The prompt is language-agnostic — SOURCE_LANG and TARGET_LANG from config.py are injected.

---

## Template system

Each template is a Python module in `templates/` with three variables:
- `NAME` — string identifier matching the filename
- `CSS` — stylesheet string injected into the Anki card model
- `FRONT` — Anki front template (uses `{{FieldName}}` syntax)
- `BACK` — Anki back template (always starts with `{{FrontSide}}`)

Optionally:
- `REQUIRES_RAW_IMAGE = True` — signals that the template needs the extra `Image_Raw` field
  (used by the immersive template to set GIF as background via JS)

To add a new template:
1. Create `templates/my_template.py` with NAME, CSS, FRONT, BACK.
2. Import and register it in `templates/__init__.py`.
3. Set `CARD_TEMPLATE = "my_template"` in `config.py`.

---

## Anki tags

Each card is tagged `vocab::<POS>` (e.g. `vocab::Noun`, `vocab::Verb`).
This allows the user to filter cards by part of speech in Anki's Card Browser
or create Filtered Decks (e.g. "study only verbs today").

POS strings from the AI are normalized via the `pos_to_tag()` function
using the `POS_TAG_MAP` dictionary in main.py.

---

## Export logic

Two .apkg files are generated on every run:

- `deck_new.apkg` — contains only cards where `exported = 0`.
  After export, those cards are marked `exported = 1`.
  **The user imports this file daily.** It never overwrites existing Anki cards,
  preserving any manual edits the user has made.

- `deck_full.apkg` — contains all cards regardless of export status.
  Used as a full backup or for a fresh Anki install.

Both files use the same Anki model (MODEL_ID) but different DECK_IDs
(DECK_ID for full, DECK_ID + 1 for new) to avoid conflicts on import.

---

## Key design decisions

- **One card per meaning, not per word.** A word with 3 distinct meanings
  generates 3 separate cards, each with its own GIF and audio.

- **Word label includes POS when multiple meanings exist.**
  "courir" with one meaning → label is just "courir".
  "courir" with two meanings → labels are "courir (Verb)" and "courir (Noun)".

- **GIF query uses 3 hashtag-style keywords generated by the AI**, not the word itself.
  This produces contextually accurate GIFs (e.g. "#melting #clock #fire" for "déformer").

- **Audio files are content-addressed** (MD5 hash of text + lang = filename).
  The same sentence never generates two audio files.

- **All settings are in config.py**, not hardcoded. The script reads config at runtime,
  so users never need to touch main.py.

- **No emojis in terminal output.** All status messages use plain text prefixes:
  [OK], [WARN], [ERROR], [INFO], [AUDIO], [GIF], [SKIP], [DONE].

---

## Dependencies

```
genanki    — creates .apkg files for Anki
gTTS       — Google Text-to-Speech for audio generation
wordfreq   — frequency-ranked word lists for any language
requests   — HTTP calls to Groq and Giphy APIs
```

---

## Card types (CARD_TYPE in config.py)

| Value | Description |
|---|---|
| `basic` | Classic: word on front, meaning on back (default) |
| `basic_reversed` | Two cards per note — word→meaning AND meaning→word |
| `type_answer` | Front shows definition; user types the foreign word |
| `cloze` | Fill-in-the-blank using the example sentence |

- Card type can also be selected at runtime from the Export menu (overrides config for that session).
- Cloze uses a different genanki model type (`CLOZE`) and different fields — `MODEL_ID + 10` to avoid conflicts.
- `CARD_TEMPLATE` (visual styling) and `CARD_TYPE` (Anki note type) are independent settings.

## Interactive menu structure

```
Main Menu
  [1] Generate new cards      — runs the AI/GIF/audio loop
  [2] Export decks            — shows card type selector, then exports .apkg files
  [3] Card type guide         — explains each card type
  [4] Statistics              — total cards, by POS, recent activity, export history
  [5] Settings                — shows all config.py values
  [0] Exit

Export -> Card Type Selection
  [1] Basic           [2] Basic + Reversed
  [3] Type in Answer  [4] Cloze
  [5] Use config.py default
```

## Config options summary (config.py)

```python
GROQ_API_KEY / GIPHY_API_KEY   # API credentials
AI_MODEL                        # Groq model string
SOURCE_LANG / TARGET_LANG       # e.g. "fr" / "English"
TTS_SOURCE_LANG / TTS_TARGET_LANG  # gTTS language codes
WORDS_PER_RUN                   # new words per script execution
TOTAL_WORD_POOL                 # total frequency pool size
CARD_TEMPLATE                   # "dark" | "light" | "minimal" | "immersive"
CARD_TYPE                       # "basic" | "basic_reversed" | "type_answer" | "cloze"
ENABLE_AUDIO / ENABLE_GIF       # toggle features on/off
ENABLE_WORD_AUDIO / ENABLE_EXAMPLE_AUDIO / ENABLE_MEANING_AUDIO
GIF_RATING                      # Giphy content filter: "g" | "pg" | "pg-13"
DECK_NAME / DECK_OUTPUT_NEW / DECK_OUTPUT_FULL / DB_PATH / AUDIO_DIR
DECK_ID / MODEL_ID              # stable Anki identifiers — never change after first run
DELAY_AI / DELAY_GIPHY / DELAY_TTS  # rate limiting delays in seconds
```
