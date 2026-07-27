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
- `id`, `word`, `word_label`, `meaning_id` — identity. `word` is NOT NULL on
  every row regardless of `creation_mode` — every mode centers on one single
  anchor word, even modes where the word never appears on the card itself
  (see § Creation modes), since POS/category tagging and subdeck routing
  hang off it unconditionally.
- `pos`, `ipa`, `gender` — linguistic metadata
- `category` — language-specific study-block label (e.g. "Phrasal Verbs"), empty
  string for ordinary vocabulary — see § Category / subdeck organization
- `text_meaning`, `text_example_phrase`, `text_example_translation`, `synonyms` — text content
- `audio_word`, `audio_meaning`, `audio_example` — paths to MP3/WAV files in audio_files/
- `gif_url` (HTML img tag), `gif_raw_url` (plain URL)
- `exported` (0/1) — tracks whether card has been included in deck_new.apkg
- `date_added`
- `creation_mode` — which `CREATION_MODES` entry produced this row (`'word_meaning'`
  default). See § Creation modes.
- `content_key` — per-mode dedup key (NOT NULL). `word_meaning` uses
  `lower(trim(word))`; phrase-based modes hash the generated phrase instead
  (e.g. `md5(lower(trim(phrase)))`) since the word alone isn't unique across
  different phrases built around it. Each mode defines its own normalization —
  modes are never required to be consistent with each other.
- `source_phrase` — raw phrase text (nullable), populated only by phrase-based
  modes, kept for debugging/display.

Table: `export_log` — tracks export history (date, type, card count)

Uniqueness constraint: `(creation_mode, content_key, meaning_id)` — one row per
distinct piece of content per mode. Dedup is explicitly **per-mode, not
global**: the same word (or phrase) appearing under two different
`creation_mode`s is not a duplicate — each mode's spaced repetition is
independent by design (e.g. a sentence already used as `text_example_phrase`
supporting content in a `word_meaning` card can separately become the primary
content of a `phrase_context` card). `get_processed_words(conn, creation_mode)`
is likewise filtered per-mode, so a word already anchoring a `word_meaning`
card remains eligible to anchor a `phrase_context` card too.

Soft migrations (additive `ALTER TABLE ADD COLUMN`, wrapped in
`try/except: pass`) are applied on every `init_db()` call, so the schema can
be extended without breaking existing databases — this covers every column
above except the three `creation_mode`/`content_key`/`source_phrase` columns
and the `UNIQUE` constraint itself, since SQLite can't `ALTER` a `UNIQUE`
constraint in place. Those instead go through `_migrate_to_creation_mode_
schema(conn)` — the first *real* migration this codebase has needed (create
`cards_new` with the new schema, copy every row across with
`creation_mode='word_meaning'`, `content_key=LOWER(TRIM(word))` (preserving
`id`), drop the old table, rename). It runs once, as the very first statement
in `init_db()`, gated on whether the `content_key` column already exists
(`PRAGMA table_info(cards)`), and takes a `progress.db.pre-creation-mode-
migration.bak` backup first (best-effort — warns rather than failing if the
backup itself can't be written). Every card that existed before this feature
shipped ends up `creation_mode='word_meaning'`, matching its exact prior
behavior — this is what makes the feature backward compatible in practice,
not just in intent.

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

## Local TTS provider (Pocket TTS)

`TTS_PROVIDER` in config.py (`"gtts"` default, or `"pocket_tts"`) selects
between cloud gTTS and [Pocket TTS](https://github.com/kyutai-labs/pocket-tts)
(Kyutai Labs) — a CPU-only, local TTS engine with multiple realistic voices,
lazily imported (`from pocket_tts import TTSModel`) so it's not a hard
dependency, same pattern as the `anthropic` SDK above.

Two real constraints from Pocket TTS's own API shape this implementation
(verified by extracting and reading the actual wheel, not just its docs —
worth re-checking if a `pocket-tts` upgrade is ever needed):

- `TTSModel.load_model(language=...)` loads an entire model per language and
  is slow — `generate_audio()`'s helpers `_get_pocket_tts_model()` /
  `_get_pocket_tts_voice_state()` cache the loaded model and derived voice
  state in module-level dicts (`_POCKET_TTS_MODELS`,
  `_POCKET_TTS_VOICE_STATES`) for the process lifetime, keyed by Pocket
  TTS's own language id / `(language, voice)` — never reload per call.
- Pocket TTS only ships weights for 6 languages (`POCKET_TTS_LANG_MAP` maps
  `TTS_SOURCE_LANG`/`TTS_TARGET_LANG`'s gTTS-style 2-letter codes —
  `"fr"`, `"en"`, etc. — to Pocket TTS's own identifiers, e.g. `"french_24l"`,
  note the required `_24l` suffix). Any other language falls back to gTTS
  per-call with a one-time `[WARN]` (`_warn_pocket_tts_unsupported_lang()`) —
  this was an explicit product decision (fall back, don't hard-error) so
  generation never silently stops. `POCKET_TTS_VOICES` lists the real voice
  catalog per language: 21 for English, exactly 1 for each of French,
  German, Italian, Portuguese, Spanish.

`generate_audio(text, lang, voice_field)` takes `voice_field="source"` (word
+ example audio, uses `POCKET_TTS_VOICE_SOURCE`) or `"target"` (meaning
audio, uses `POCKET_TTS_VOICE_TARGET`) so the two Pocket TTS voice slots
apply to the right field regardless of which physical language each one
resolves to. Output is WAV (`scipy.io.wavfile.write`), unlike gTTS's MP3 —
`sound_tag()` doesn't care about the extension, and cache filenames are
content-addressed on `text + lang + provider + voice` (not just `text +
lang`) so switching provider/voice can't collide with a previously-cached
gTTS file for the same text.

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
- How many meanings are requested is controlled by `config.MEANING_EXHAUSTIVENESS`
  (`"essential"` | `"important"` (default) | `"all"`), via
  `MEANING_EXHAUSTIVENESS_SETTINGS` in main.py — a dict of per-level
  `instruction` (the phrasing injected into the prompt's opening sentence),
  `max_meanings` (the hard cap stated in the Rules section, injected as
  `{max_meanings}`), and `max_tokens` (passed through to whichever
  `_call_<provider>()` is active). `"all"` still caps at 12, not truly
  unlimited — an uncapped prompt for a highly polysemous function word
  (e.g. "the") can ask for dozens of technical senses and truncate mid-
  response into invalid JSON regardless of token budget, which is the exact
  failure this project hit before the cap existed. `current_meaning_
  exhaustiveness()` resolves the active level (falling back to `"important"`
  for an unset/invalid config value) and both `generate_card_content()` and
  every `_call_<provider>()` take `max_tokens` from it — see § AI provider
  layer for the dispatch mechanism this plugs into.
- The JSON shape above is `word_meaning`'s specifically — other
  `CREATION_MODE`s use their own prompt template and JSON shape entirely
  (e.g. `phrase_context` returns a `"phrases"` array, not `"meanings"`) —
  see § Creation modes.

---

## Creation modes

`CREATION_MODE` in config.py is a third independent axis alongside
`CARD_TEMPLATE` (visual styling) and `CARD_TYPE` (note mechanics — see
§ Card types below). It controls two things: what the AI is asked to
generate (the prompt shape), and what serves as the card's Front (stimulus)
vs Back (answer). Every mode still centers on exactly one anchor `word` —
that's what `vocab::<POS>` tagging, `topic::<Category>` tagging, and subdeck
routing hang off of, unmodified, regardless of which mode produced the card
(see § Category / subdeck organization).

`CARD_TYPE` (`basic`/`basic_reversed`/`type_answer`/`cloze`) only applies
when `CREATION_MODE == "word_meaning"`. Every other mode ships as its own
single fixed-shape Anki note type — own `genanki.Model`, own `MODEL_ID`
offset, own hardcoded Front/Back — the same precedent `cloze` already sets
today (a fixed alternate shape, distinct from `CARD_TEMPLATE`-driven
`basic`). This isn't an arbitrary restriction: a genanki `Model` fixes one
field-set and one set of Front/Back templates for every `Note` built with
it — it can't vary per-`Note` within one `Model` — so a mode whose content
model differs from word→meaning (a phrase instead of a word, audio-only
fronts, etc.) needs its own `Model` regardless. `export_decks()` handles
this by querying the distinct `creation_mode`s actually present in the DB,
building one `Model` per mode present, and merging the resulting notes into
a single deck tree / `.apkg` — confirmed via genanki's own source that one
`Package`/`Deck` natively supports `Note`s referencing different `Model`s.

`CREATION_MODES` (main.py, structurally parallel to `AI_PROVIDER_CALLERS`)
is the registry: one dict entry per mode, each providing —
- `build_prompt(word, known_categories) -> (prompt, max_tokens)`
- `parse_response(parsed_json) -> {"ipa": str, "items": [dict, ...]}`
- `content_key(word, item) -> (content_key, source_phrase | None)` — the
  mode's own dedup normalization (see § Database schema)
- `extract_fields(item) -> {"text_meaning", "text_example_phrase",
  "text_example_translation", "tts_example_text"}` — `tts_example_text` is
  separate from `text_example_phrase` because phrase-based modes store the
  AI's `**word**`-delimited markup in the DB field but must generate audio
  from the delimiter-stripped text, or literal asterisks reach gTTS/Pocket TTS
- `model_id_offset`, `label`, and (for non-`word_meaning` modes) `front`/`back`

`_generate_loop()` resolves `current_creation_mode()` once per run, passes it
into `generate_card_content()` (which dispatches through the mode's
`build_prompt`/`parse_response` before/after the existing, mode-agnostic
`AI_PROVIDER_CALLERS` call), and uses `mode_def["content_key"]`/`["extract_
fields"]` per item instead of the old hardcoded `meaning.get(...)` reads.

**`phrase_context`** (the one non-`word_meaning` mode currently implemented):
asks the AI for up to N distinct phrases using the anchor word in different
contexts, with the exact inflected/conjugated surface form it used wrapped
in `**double asterisks**` — not Python-side substring matching against the
dictionary form, which reliably fails for inflected/conjugated languages (a
conjugated French verb usually doesn't literally contain its infinitive as a
substring). `highlight_delimited()` converts that markup to `<span
class="highlight">` at note-build time, reusing the exact CSS class
`highlight_word()` already uses for `word_meaning` — every `CARD_TEMPLATE`
already defines `.example .highlight` identically, so no template file
needed to change. Front = the phrase (word highlighted) + its audio only;
Back reveals the dictionary form, IPA/gender, a GIF, the in-context meaning,
and the phrase's translation.

**`audio_meaning` / `audio_writing` / `audio_typing`** (audio-first,
word-anchored modes): all 3 point their `build_prompt`/`parse_response`/
`content_key`/`extract_fields` at the exact same functions `word_meaning`
uses (`_build_word_meaning_prompt` etc.) — they want identical AI content
(IPA, gender, meaning, example, translation, synonyms, category,
gif_keywords), just rendered differently. Only Front/Back and
`model_id_offset` differ per mode. `audio_meaning`'s Front is bare
`{{Sound_Word}}`; Back reveals everything. `audio_writing`'s Front is the
same bare audio; Back reveals only the written word (+ IPA/gender/synonyms
in "complete" verbosity) — no meaning is ever shown, by design (a pure
recognition drill, not a comprehension one). `audio_typing` is
`audio_writing` with `{{type:Word}}` (Anki's built-in typed-answer
directive — same mechanic `CARD_TYPE = "type_answer"` already uses at
`_TYPE_FRONT`) appended to the Front instead of a passive reveal — Anki
diffs the typed input against the literal `Word` field with zero custom
checking code.

**`phrase_native_writing`** ("Write Response" in both TUIs): the one mode
besides `phrase_context` with its own prompt (`PROMPT_TEMPLATE_PHRASE_
NATIVE_WRITING`) — same rules-section structure, but reversed direction:
asks for phrases **in `TARGET_LANG`** (the user's native language) plus the
correct `SOURCE_LANG` translation (word's exact inflected form wrapped in
`**markers**`, same convention `phrase_context` uses, reusing
`highlight_delimited()` unchanged). `_phrase_native_writing_extract()` maps
`correct_translation` → `text_example_phrase` (Back, highlighted) and
`native_phrase` → `text_example_translation` (Front) — reusing that field
slot for the native-language prompt is what lets `build_notes()`'s already-
generic non-`word_meaning` branch handle this mode with zero code changes.
`content_key` hashes the native phrase (the front-facing text), mirroring
`_content_key_phrase_context` hashing what *its* front shows.

**`phrase_audio_recognition` / `phrase_audio_typing`** (audio-first,
phrase-anchored modes — the phrase-level counterparts to the 3 audio modes
above): both reuse `phrase_context`'s `build_prompt`/`parse_response`/
`content_key` verbatim (identical content, audio-first presentation).
`phrase_audio_recognition` also reuses `_phrase_context_extract` verbatim,
since its Back just reveals `Text_Example_Phrase` via `highlight_delimited()`
same as `phrase_context`'s. `phrase_audio_typing` needs its own
`_phrase_audio_typing_extract`: Anki's `{{type:Text_Example_Phrase}}`
directive diffs the typed answer against that field's *literal* value, so
the `**`-markers `phrase_context`/`phrase_audio_recognition` rely on for
highlighting would leak into what the user has to type — this extract
function strips them at write time instead (`text_example_phrase` becomes
the same clean string as `tts_example_text`).

### `CREATION_MODE_VERBOSITY` — simple vs. complete fields

Every mode above except `word_meaning`/`phrase_context` supports two
verbosity levels via `config.CREATION_MODE_VERBOSITY` (`"complete"`
default, or `"simple"`). This does **not** need a second `genanki.Model`
per mode/verbosity combination — Anki/genanki support mustache-style
`{{#Field}}...{{/Field}}` conditionals (new to this codebase; not used by
any pre-existing template) that make a wrapped display block vanish
whenever the field is empty. So a mode's Front/Back wrap every optional
block (e.g. `{{#IPA}}<div class="ipa">/ {{IPA}} /</div>{{/IPA}}`) and
verbosity is implemented as a single generic blanking step in
`_generate_loop()`:

```python
omit = set(mode_def.get("always_omit", ()))
if config.CREATION_MODE_VERBOSITY == "simple":
    omit |= set(mode_def.get("simple_omits", ()))
```

applied to `ipa`/`gender`/`synonyms`/`text_meaning`/`text_example`/
`text_example_translation` right after each is read, before they reach
`save_card()`. Two registry keys drive it: `always_omit` (fields a mode
never uses regardless of verbosity — e.g. `audio_writing`/`audio_typing`
always omit `text_meaning` since showing one would defeat the "pure
recognition drill" point of those modes) and `simple_omits` (extras hidden
only in `"simple"`). `word_meaning`/`phrase_context` never populate either
list, so `omit` stays empty and they're completely unaffected regardless of
`CREATION_MODE_VERBOSITY`. Blanking `text_meaning`/`text_example` upstream
also skips their TTS generation for free — main.py's meaning/example audio
gates require the source text to be non-empty (`and text_meaning` /
`and tts_example_text`), so a mode/verbosity combo that will never display
that audio never requests it from the TTS provider either.

### Guided TUI flow — "Card content"

Both TUIs present `CREATION_MODE`/`CARD_TYPE`/`CREATION_MODE_VERBOSITY` as
one guided flow (**Configure → Card content**) instead of three separate
pickers on unrelated screens — a deliberate presentation-layer redesign
(no config.py schema change; `CREATION_MODE`/`CARD_TYPE` are still the two
stored settings). Step 1 picks a content-unit family
(`_WORD_FAMILY_MODES`/`_PHRASE_FAMILY_MODES`, main.py — word_meaning/
audio_meaning/audio_writing/audio_typing vs. phrase_context/
phrase_native_writing/phrase_audio_recognition/phrase_audio_typing); Step 2
shows a testing-style list filtered to that family
(`_WORD_TESTING_OPTIONS`/`_PHRASE_TESTING_OPTIONS`). Neither `run_menu()`
(curses) nor `runScreen()` (JS) supports rebuilding one screen's item list
live off another item's value — both TUIs implement Step 1 → Step 2 as two
nested screens instead (curses: `configure_card_content()` → `Action` →
`_configure_word_content()`/`_configure_phrase_content()`; JS:
`cardContentMenu()` → `wordContentMenu()`/`phraseContentMenu()` — same
nested-screen idiom `_provider_settings()`/`providerSettings()` already
established for AI-provider-dependent fields).

The Word family's first 4 testing styles are `CARD_TYPE` variants
(basic/basic_reversed/type_answer/cloze), which need **both**
`CREATION_MODE="word_meaning"` and `CARD_TYPE=<variant>` written from one
selection — a picker writing two config keys at once isn't natively
supported by either `Picker`/`pickerItem()`, so this is a one-off
extension: curses subclasses `Picker` (`_WordTestingPicker`, main.py),
overriding `_idx()`/`_set()` to read/write both keys (same idiom
`_GroqModelPicker` already uses for a different purpose); JS hand-builds a
picker-shaped item object (`wordTestingItem()`, screens.mjs) bypassing the
`pickerItem()` factory, since `runScreen.mjs` only requires
`{kind, label, options, getValue, setValue}` — nothing enforces going
through the factory.

**Adding a new mode**: add one `CREATION_MODES` entry (its prompt/parse/
content-key/extract-fields functions — reuse `word_meaning`'s or
`phrase_context`'s if the mode wants identical content, same as most modes
above — plus Front/Back if it's phrase- or audio-based, optionally
`always_omit`/`simple_omits` for verbosity support) and one tuple to
`_WORD_TESTING_OPTIONS` or `_PHRASE_TESTING_OPTIONS` (main.py, feeds both
TUIs via `_options_snapshot()`) plus the matching membership set
(`_WORD_FAMILY_MODES`/`_PHRASE_FAMILY_MODES`) so hints resolve correctly —
mirror the same addition in `cli/src/screens.mjs`'s `WORD_FAMILY_MODES`/
`PHRASE_FAMILY_MODES`/`word_testing_options`/`phrase_testing_options`. No
schema, migration, or dispatch changes are needed —
`build_anki_model()`/`build_notes()`'s non-`word_meaning` branches are
already fully generic over `mode_def["front"]`/`["back"]`/
`["model_id_offset"]`/`["label"]` and the shared 11-field model.

---

## Word sources

`WORD_SOURCE` in config.py is a separate axis from `CREATION_MODE` — it
controls *where the candidate word strings come from*, not what happens to
them once picked. `_do_generate()` and `_run_headless()` both call
`get_word_pool()` (main.py, right before the "Generation and export
runners" section) instead of calling `top_n_list()` directly; everything
downstream (`get_processed_words(conn, creation_mode)` filtering,
`_generate_loop(conn, pending, limit)`) is unchanged and unaware of which
source produced `pending` — it only ever consumes a plain `list[str]`.

`WORD_SOURCES` registry (structurally parallel to `AI_PROVIDER_CALLERS` /
`CREATION_MODES`), each entry a zero-arg callable returning `list[str]`:
- `"frequency_list"` (default) — `top_n_list(config.SOURCE_LANG,
  config.TOTAL_WORD_POOL)`, i.e. exactly today's pre-feature behavior.
- `"markdown_notes"` — `_build_markdown_word_pool()`: recursively walks
  `config.MARKDOWN_NOTES_PATH` for `*.md` files (`_iter_markdown_files`,
  sorted by path for deterministic pool order), strips markdown noise
  (`_strip_markdown_noise` — YAML frontmatter, code fences/spans,
  wikilinks/embeds/links, headings, via regex; no markdown-parser
  dependency, since Obsidian's syntax surface is small and predictable
  enough not to warrant one), then extracts per
  `config.MARKDOWN_EXTRACTION_MODE`:
  - `"highlights"` (recommended default) — `_extract_highlights()` pulls
    `==highlighted==` spans, first-seen order, exact-duplicate-collapsed.
    High-signal since it's explicit user curation.
  - `"all_words"` — `_extract_all_words()` tokenizes every Unicode
    alphabetic word (`\b[^\W\d_]{2,}\b`), ranked by descending frequency
    (`collections.Counter`, alphabetical tiebreak for determinism). No
    stopword filtering exists, so common function words dominate a
    personal-notes corpus (unlike `wordfreq`'s curated corpus) — this is
    why `highlights` is the recommended default, not `all_words`.
  Either mode is capped at `config.TOTAL_WORD_POOL`, same sizing knob the
  frequency-list source uses. An empty/invalid `MARKDOWN_NOTES_PATH` prints
  a `[WARN]` and returns `[]` rather than raising — a user-config boundary,
  handled the same way other config-driven paths in this codebase are.

No new third-party dependency was needed (pure `os`/`re`/`collections`), so
unlike the `anthropic`/`pocket_tts` lazy-optional-import pattern (see
§ AI provider layer / § Local TTS provider), this code is imported
unconditionally at the top of main.py.

**Known limitation**: no lemmatization/stemming exists anywhere in this
codebase. A word extracted from prose keeps whatever inflected/conjugated
surface form it appeared in — it is not normalized to a dictionary form,
so e.g. "mangera" and "manger" are treated as two unrelated anchor words.

**Deferred (not built)**: passing the *actual sentence* a markdown-sourced
word was found in through to the AI prompt as authentic context (would
need a signature change to every `CREATION_MODES` entry's `build_prompt`,
since today it only ever receives `(word, known_categories)`) — tracked as
a roadmap item, see README.md § Roadmap.

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
pocket-tts — optional, only required when TTS_PROVIDER = "pocket_tts" (local TTS)
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
- `CARD_TYPE` only applies when `CREATION_MODE = "word_meaning"` (the default) — see § Creation modes.

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
MEANING_EXHAUSTIVENESS          # "essential" | "important" | "all" (see § AI prompt structure)
CARD_TEMPLATE                   # "dark" | "light" | "minimal" | "immersive"
CARD_TYPE                       # "basic" | "basic_reversed" | "type_answer" | "cloze" — Word-based cards only
CREATION_MODE                   # word_meaning | phrase_context | audio_meaning | audio_writing |
                                 # audio_typing | phrase_native_writing | phrase_audio_recognition |
                                 # phrase_audio_typing (see § Creation modes)
CREATION_MODE_VERBOSITY         # "complete" | "simple" — audio/production testing styles only
                                 # (CREATION_MODE/CARD_TYPE/CREATION_MODE_VERBOSITY are best set via
                                 # Configure -> Card content's guided flow, not hand-edited together)
WORD_SOURCE                     # "frequency_list" | "markdown_notes" (see § Word sources)
MARKDOWN_NOTES_PATH             # folder scanned recursively for *.md files
MARKDOWN_EXTRACTION_MODE        # "highlights" | "all_words"
ENABLE_CATEGORIES               # category subdecks + topic:: tags (see Category / subdeck organization)
ENABLE_AUDIO / ENABLE_GIF       # toggle features on/off
ENABLE_WORD_AUDIO / ENABLE_EXAMPLE_AUDIO / ENABLE_MEANING_AUDIO
TTS_PROVIDER                    # "gtts" | "pocket_tts" (see § Local TTS provider)
POCKET_TTS_VOICE_SOURCE / POCKET_TTS_VOICE_TARGET / POCKET_TTS_QUANTIZE
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
