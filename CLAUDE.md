# CLAUDE.md — Project Context for Claude Code

This file gives you full context about the project so you can assist
with new features, refactoring, and bug fixes effectively.

Current version: tracked in `VERSION` (repo root) — see `CHANGELOG.md` for
history and § Versioning below for how/when to bump it. Do not hardcode a
version number here; it will only go stale again.

---

## What this project does

Generates rich Anki flashcard decks (.apkg) for vocabulary learning.
For each word in a frequency list, it:
1. Calls an AI provider (Groq, OpenAI, Anthropic/Claude, Google Gemini, or a local
   Ollama model — selected via `AI_PROVIDER` in config.py) to generate all card
   content via a structured JSON prompt.
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
├── main.py              # Main script — all logic + interactive menu + CLI bridge flags
├── tui.py               # Curses rendering layer for the Python interactive menu
├── config.py            # All user-configurable settings (API keys, language, etc.)
├── requirements.txt     # pip dependencies
├── CLAUDE.md            # This file
├── README.md            # GitHub documentation
├── .gitignore
├── template/            # Note: folder is "template" (no 's'), import is "import template"
│   ├── __init__.py      # Loads and exposes all templates via tmpl_registry.load(name)
│   ├── dark.py          # Dark mode (Catppuccin Mocha palette) — default
│   ├── light.py         # Light mode with soft color accents
│   ├── minimal.py       # Text only, no GIF, no gender badge
│   └── immersive.py     # GIF as full card background with text overlay
└── cli/                 # JS TUI — a second frontend over main.py, see § JavaScript TUI
    ├── package.json      # deps: @charmland/lipgloss (WASM build of Go's charmbracelet/lipgloss)
    └── src/
        ├── index.mjs        # entry point
        ├── bridge.mjs       # subprocess wrapper around `python3 -B main.py --flag`
        ├── term.mjs         # raw-mode keypress capture (readline), queued so no key is ever dropped
        ├── theme.mjs        # Lip Gloss Style singletons + precomputed gradient title
        ├── render.mjs       # pure string builders: header/footer/row-per-item-kind/edit-box
        ├── runScreen.mjs    # the interactive list loop (focus, editing, keypress dispatch)
        ├── staticScreen.mjs # read-only page loop (Statistics, Card type guide)
        └── screens.mjs      # screen definitions (mirrors main.py's configure_* grouping)
```

## Running the script

- **Interactive (default):** `python main.py` — shows the main menu
- **Headless (automation/cron):** `python main.py --run` — generates + exports without menu
- **Alternative JS frontend:** `cd cli && npm install && node src/index.mjs` — see § JavaScript TUI
- **CLI bridge flags** (used by the JS TUI, but callable directly): `--generate`,
  `--export[=<card_type>]`, `--stats-json`, `--config-json`, `--options-json`,
  `--set-config=<KEY> --value=<VALUE> --type=<str|int|float|bool>`

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
- `category` — language-specific study-block label (e.g. "Phrasal Verbs"), empty
  string for ordinary vocabulary — see § Category / subdeck organization
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

## AI provider layer

`AI_PROVIDER` in config.py selects which service `generate_card_content()` calls:
`"groq"` (default), `"openai"`, `"anthropic"`, `"gemini"`, or `"ollama"` (local,
no API key). Each provider has its own API key + model config fields (e.g.
`ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL`); only the active provider's fields are
used. `main.py` dispatches through `AI_PROVIDER_CALLERS` to one of `_call_groq`,
`_call_openai`, `_call_anthropic`, `_call_gemini`, `_call_ollama` — all return
raw response text that is then parsed as JSON by the shared prompt/parsing logic.
Groq, OpenAI, Gemini, and Ollama are called via raw HTTP (`requests`); Claude is
called via the official `anthropic` SDK (lazily imported so it's not a hard
dependency for users on other providers).

To add a new provider: write a `_call_<provider>(prompt) -> str` function, add
it to `AI_PROVIDER_CALLERS` / `AI_PROVIDER_KEY_FIELD` / `AI_PROVIDER_MODEL_FIELD`
/ `AI_PROVIDER_LABELS`, add its config.py fields, and add a branch in
`configure_ai()`'s `_provider_settings()` for the settings TUI.

## AI prompt structure

The prompt asks for a JSON response with this shape (identical across all providers):
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

Cards with a category also get a `topic::<Category>` tag (e.g.
`topic::Phrasal_Verbs`), slugified via `category_to_tag()` — see
§ Category / subdeck organization.

---

## Category / subdeck organization

**Problem it solves:** POS tagging (`vocab::Noun`, `vocab::Verb`) is
language-agnostic, but many languages have study "blocks" that don't map to
POS at all and vary from language to language — e.g. English has "Phrasal
Verbs" and "Verb Conjugation"; other languages may have their own distinct
groupings (French might warrant "Faux Amis", Japanese might warrant "Keigo").

**How it works:**
- `cards.category` — a soft-migrated column (like `pos`/`gender`), one per
  card/meaning, populated by the AI as an extra field in the same JSON response
  (`PROMPT_TEMPLATE` in main.py). Empty string means ordinary vocabulary with
  no special category.
- **Categories are language-specific and open-ended** — unlike `POS_TAG_MAP`
  (a small fixed set), there's no hardcoded list. `get_known_categories(conn)`
  reads every distinct category already stored in `progress.db` and
  `_build_category_hint()` feeds that list back into the prompt so the AI
  reuses an existing name (exact spelling/casing) instead of coining a
  near-duplicate; `_generate_loop()` also appends newly-coined categories to
  the in-memory list as it goes so reuse works within a single run, not just
  across runs.
- **Anki tags** — `build_notes()` adds a `topic::<Category>` tag (slugified via
  `category_to_tag()`) alongside the existing `vocab::<POS>` tag.
- **Anki subdecks** — `export_decks()` routes each `(category, note)` pair
  (`build_notes()` returns notes as `(category, Note)` tuples) through
  `_build_deck_tree()`, which creates one `genanki.Deck` per category named
  `"<DECK_NAME>::<Category>"` (Anki's `::` subdeck syntax) plus the root deck
  for uncategorized cards, then bundles them all into one `genanki.Package`.
  `category_deck_id()` derives a stable subdeck ID from a CRC32 hash of the
  category name (offset from the root DECK_ID) so re-running the generator
  doesn't spawn duplicate subdecks in Anki.
- `config.ENABLE_CATEGORIES` (default `True`) is the master switch — when
  `False`, the AI isn't asked for a category, and even a category already
  stored in the DB is ignored at export time (no subdeck, no `topic::` tag).

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

Each file is actually a small **deck tree**, not a single flat deck: cards
with a `category` are routed into a `"<DECK_NAME>::<Category>"` subdeck via
`_build_deck_tree()`, alongside the root deck for uncategorized cards. The
"new" tree and "full" tree derive their subdeck IDs from different base IDs
(DECK_ID vs DECK_ID + 1), so both stay independently stable across runs — see
§ Category / subdeck organization.

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

## Versioning

`VERSION` (repo root, plain text, e.g. `2.3.0`) is the single source of
truth for the project's release version — `version.py` reads it and exposes
`APP_VERSION`, which both `main.py` (headless banner, `--options-json`
bridge output) and `tui.py` (menu title) import rather than hardcoding a
number. The JS TUI reads it from the bridge's `app_version` field
(`cli/src/screens.mjs`'s `mainMenu()` calls `theme.mjs`'s `setAppVersion()`
once at startup) and `cli/package.json`'s own `version` field is kept in
sync by hand — there is one project version, not per-frontend versions.

**Bump `VERSION` and add a `CHANGELOG.md` entry on every user-facing
change** (follow [Semantic Versioning](https://semver.org/)):
- **PATCH** (`x.y.Z`) — bug fixes, small visual/UX tweaks, internal
  refactors with no new capability.
- **MINOR** (`x.Y.0`) — new backward-compatible features (a new provider,
  a new card type, a new screen).
- **MAJOR** (`X.0.0`) — breaking changes or a fundamentally redesigned
  experience (e.g. the original curses-menu rewrite).

Never hand-edit the version number in `README.md`'s badge, `tui.py`, or
`main.py` directly — change `VERSION` and everything else follows from it.
Update the README badge text to match `VERSION` after bumping (it's a
static `img.shields.io` badge, not generated at build time, so it doesn't
update itself).

---

## Dependencies

```
genanki    — creates .apkg files for Anki
gTTS       — Google Text-to-Speech for audio generation
wordfreq   — frequency-ranked word lists for any language
requests   — HTTP calls to Groq/OpenAI/Gemini/Ollama and Giphy APIs
anthropic  — optional, only required when AI_PROVIDER = "anthropic"
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
AI_PROVIDER                     # "groq" | "openai" | "anthropic" | "gemini" | "ollama"
GROQ_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY / GIPHY_API_KEY
AI_MODEL / OPENAI_MODEL / ANTHROPIC_MODEL / GEMINI_MODEL / OLLAMA_MODEL
OLLAMA_HOST                     # local Ollama server address (default http://localhost:11434)
SOURCE_LANG / TARGET_LANG       # e.g. "fr" / "English"
TTS_SOURCE_LANG / TTS_TARGET_LANG  # gTTS language codes
WORDS_PER_RUN                   # new words per script execution
TOTAL_WORD_POOL                 # total frequency pool size
CARD_TEMPLATE                   # "dark" | "light" | "minimal" | "immersive"
CARD_TYPE                       # "basic" | "basic_reversed" | "type_answer" | "cloze"
ENABLE_CATEGORIES               # category subdecks + topic:: tags (see Category / subdeck organization)
ENABLE_AUDIO / ENABLE_GIF       # toggle features on/off
ENABLE_WORD_AUDIO / ENABLE_EXAMPLE_AUDIO / ENABLE_MEANING_AUDIO
GIF_RATING                      # Giphy content filter: "g" | "pg" | "pg-13"
DECK_NAME / DECK_OUTPUT_NEW / DECK_OUTPUT_FULL / DB_PATH / AUDIO_DIR
DECK_ID / MODEL_ID              # stable Anki identifiers — never change after first run
DELAY_AI / DELAY_GIPHY / DELAY_TTS  # rate limiting delays in seconds
```

## JavaScript TUI

`cli/` is a second, JS-based interactive menu with the same screens as
`tui.py`'s curses menu. It is a **pure frontend** — it contains no business
logic of its own (no AI calls, no SQLite, no .apkg writing) and instead
shells out to `main.py` as a subprocess for everything, so both frontends
always operate on the exact same `config.py` / `progress.db`.

Styling is built on [Lip Gloss](https://github.com/charmbracelet/lipgloss)
via `@charmland/lipgloss` — Charm's own WASM build of the real Go source
(not a reimplementation; its npm maintainers list is the actual Charm team).
Two prior attempts at this same feature preceded this one: a hand-rolled
zero-dependency ANSI menu that mirrored `tui.py`'s curses visual language
byte-for-byte (looked like a straight port, not a modern UI), then an
Ink+React rebuild that looked right but rendered with no color at all in
the user's real terminal (Konsole) due to Ink/chalk's color-support
detection misfiring. Lip Gloss does its own color-profile detection
(`DetectFromEnvVars`, real Go `termenv` logic) — different code path,
independent of whatever Ink/chalk got wrong.

Lip Gloss is styling-only, like the Go original — no input loop or screen
model (that's Bubble Tea's job in Go, and there's no JS Bubble Tea here). So
this is a hand-rolled raw-mode keypress loop (`cli/src/term.mjs`, via
`node:readline`), same shape as the original zero-dependency attempt, with
Lip Gloss building the styled strings instead of manual ANSI. `cli/src/
theme.mjs` holds the palette and a **fixed set of pre-built `Style`
singletons** — deliberately never `new Style()` per redraw. The WASM side
has its own Go GC with no visibility into JS reachability; a Style object
that goes out of scope in JS can get collected out from under a still-cached
handle, which surfaced as a real `"type assert failed"` WASM panic under a
redraw loop that minted a fresh Style per row per keystroke. A second,
related crash (`"table index is out of bounds"`) showed up when several
redraws fired within milliseconds of each other (e.g. arrow-key
auto-repeat) — `term.mjs`'s `nextKeyBatch()` drains a whole burst of queued
keys and `runScreen.mjs` applies all of them before a single redraw, instead
of one redraw per key. Both fixes were confirmed against a scripted
pseudo-TTY stress test (rapid up/down and left/right bursts) before being
considered done — this is beta software (`2.0.0-beta.3`); if new Lip Gloss
methods get used here later, re-run that kind of burst test rather than
assuming stability.

**Navigation**: `runScreen.mjs` is a plain async function (not a component
tree) that owns one screen's focus/editing state and redraw loop, returning
a token once an Action/Back row is chosen. `screens.mjs`'s functions
(`mainMenu`, `settingsMain`, etc.) drive navigation via sequential `await
runScreen(...)` calls — same shape as `tui.py`'s nested `run_menu()` calls
reusing one curses window. Items are plain descriptors (`{kind: 'action'|
'toggle'|'picker'|'text'|'number'|'separator'|'back', ...}`) built by
helpers in `screens.mjs` (`actionItem`, `toggleItem`, `pickerItem`,
`textItem`, `numberItem`) — Action/Back rows return their token, ending the
screen; Toggle/Picker/Text/Number rows mutate config in place via
`getValue()`/`setValue()` closures and redraw the same screen.

**Bridge protocol** (`main.py`'s `_parse_flags()` / `_run_cli_bridge()`,
consumed by `cli/src/bridge.mjs`):
- `--generate` — runs `_do_generate(conn)` (the interactive generation loop
  minus the trailing `pause()`) and returns.
- `--export` / `--export=<card_type>` — runs `_do_export(conn, card_type)`
  (export minus the interactive `select_card_type()` prompt and `pause()`);
  omitting `=<card_type>` falls back to `config.CARD_TYPE`.
- `--stats-json` — `_stats_data(conn)` as JSON (same figures as
  `show_statistics()`, kept as a separate helper with its own queries rather
  than refactoring the working curses screen).
- `--config-json` — `_config_snapshot()`: every public primitive attribute of
  `config` module, as JSON. Generic — reads whatever config.py currently
  exposes, no key whitelist to keep in sync.
- `--options-json` — `_options_snapshot()`: the static Picker option lists
  already defined in main.py (`_AI_PROVIDERS`, `_GROQ_MODELS`,
  `_ANTHROPIC_MODELS`, `_TEMPLATES`, `_CARD_TYPES`, `_CARD_TYPE_LABELS`,
  `_GIF_RATINGS`) plus the provider lookup dicts (`AI_PROVIDER_LABELS`,
  `AI_PROVIDER_MODEL_FIELD`, `AI_PROVIDER_KEY_FIELD`) — so the JS Picker
  screens and banner never hardcode a second copy of this data.
- `--set-config=<KEY> --value=<VALUE> --type=<str|int|float|bool>` — coerces
  `VALUE` per `type` and calls the existing `write_config(key, value)`
  unchanged.

`Generate`/`Export` are invoked with `stdio: 'inherit'` so Python's own
`col()`-colored progress output prints directly into the same terminal —
this is the JS equivalent of `tui.py`'s `Action(print_mode=True)`
curses-suspend pattern. Unlike the settings screens, raw mode here is a
single session-long `enableRawMode()` in `index.mjs`, not per-screen — so
`screens.mjs`'s `runSubprocess()` helper explicitly calls
`disableRawMode()` before `bridge.generate()`/`bridge.export()` and
`enableRawMode()` + `flushKeys()` after, so keystrokes typed while Python
has the terminal don't get captured by our own listener and replayed as
phantom navigation once the menu redraws. `cli/src/bridge.mjs` always
launches Python with
`-B` (`python3 -B main.py ...`): config.py is rewritten by every
`--set-config` call, and since Python's bytecode-cache invalidation is
`(mtime, size)`-based, two writes with equal-length values within the same
filesystem-mtime tick (e.g. rapid Left/Right presses on a NumberInput) can
otherwise make a subsequent read see a stale cached module. `-B` forces a
fresh read+compile from the real file on every invocation.

Adding a new setting to a `configure_*` screen in `tui.py`? Add the matching
item descriptor (via `toggleItem`/`pickerItem`/`textItem`/`numberItem`) to
the corresponding screen function in `cli/src/screens.mjs` too (same
grouping: Language / AI & API / Deck & cards / Generation / Audio / GIF /
Rate limits) — `_config_snapshot()` and `_options_snapshot()` already expose
whatever main.py defines, so the JS side only needs the new menu item, not a
new bridge flag (unless the setting needs a picker option list that isn't in
`_options_snapshot()` yet, in which case add it there first).

Run it: `cd cli && npm install && node src/index.mjs` (needs `python3` on
`PATH`, or set `PYTHON_BIN` to a specific interpreter, e.g. a venv's).
