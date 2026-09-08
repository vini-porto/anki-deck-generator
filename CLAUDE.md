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

## Anki note fields

Every card's `genanki.Model` declares these 11 canonical fields, always,
regardless of which ones the user's Card Fields checklist has enabled (see
§ Card fields below — an unchecked field is simply blank, never omitted
from the field list itself, which is what keeps `MODEL_ID` stable across
checklist changes):

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

The cloze interaction (see § Card fields) uses a different, smaller 9-field
set instead (`Cloze_Text` in place of `Text_Example_Phrase`, no
`Text_Example_Translation`) — a structurally different genanki `Model`
type, same precedent as before.

---

## Database schema (progress.db)

Table: `cards`
- `id`, `word`, `word_label`, `meaning_id` — identity. `word` is NOT NULL on
  every row — every card centers on one single anchor word/phrase, since
  POS/category tagging and subdeck routing hang off it unconditionally.
- `pos`, `ipa`, `gender` — linguistic metadata
- `category` — language-specific study-block label (e.g. "Phrasal Verbs"), empty
  string for ordinary vocabulary — see § Category / subdeck organization
- `text_meaning`, `text_example_phrase`, `text_example_translation`, `synonyms` — text content
- `audio_word`, `audio_meaning`, `audio_example` — paths to MP3/WAV files in audio_files/
- `gif_url` (HTML img tag), `gif_raw_url` (plain URL)
- `exported` (0/1) — tracks whether card has been included in deck_new.apkg
- `date_added`
- `creation_mode` — which genanki `Model` shape this row belongs to:
  `'standard'` (the fixed 11-field model, whatever fields are actually
  populated depends on the Card Fields checklist active when it was
  generated) or `'cloze'` (the cloze-deletion model). See § Card fields.
  Rows from before the field-config redesign keep their old
  `CREATION_MODE`-registry token (e.g. `'word_meaning'`,
  `'phrase_context'`) — those are a dead end for export (clean break, no
  legacy fallback — `export_decks()` only ever builds `'standard'`/`'cloze'`
  Models) but are otherwise inert; a `[WARN]` fires if any are found
  un-exported.
- `content_key` — dedup key (NOT NULL). Spontaneous Mode uses
  `lower(trim(word))`; Annotation Mode hashes `word::sentence` instead
  (`md5(lower(trim(word)) + "::" + lower(trim(sentence)))`) since the same
  word highlighted in two different notes is two distinct cards, not a
  duplicate. See § Word sources.
- `source_phrase` — the raw anchor text (nullable), populated only by
  Annotation Mode, kept for debugging/display.

Table: `export_log` — tracks export history (date, type, card count)

Table: `markdown_file_state` — **unused, dead schema.** Originally
per-file read tracking for `WORD_SOURCE = "markdown_notes"`, one row per
`(creation_mode, file_key)` with a `file_size`/`items_json` baseline. This
mode has since been redesigned to have no dedup at all (see § Word
sources) — nothing reads or writes this table anymore
(`_build_markdown_pending()` no longer consults it, and
`_commit_markdown_file_state()`/`get_markdown_file_state()` were removed
outright). Left in `init_db()`'s schema purely so an existing
`progress.db` doesn't need a migration; safe to ignore.

Uniqueness constraint: `(creation_mode, content_key, meaning_id)` — one row
per distinct piece of content per Model shape. `get_processed_words(conn,
creation_mode)` is likewise filtered by the `standard`/`cloze` value, so
switching the example-phrase interaction between reveal and cloze gives
each its own independent dedup pool — same mechanism as before, now keyed
on Model shape instead of the old CREATION_MODE registry entry. This is
the dedup mechanism for `WORD_SOURCE = "frequency_list"` (Spontaneous
Mode) only; `"markdown_notes"` (Annotation Mode) deliberately has no
dedup mechanism at all — `_content_key()` nonce's every Annotation Mode
key so this same constraint can never block a re-processed highlight
from inserting — see § Word sources.

Soft migrations (additive `ALTER TABLE ADD COLUMN`, wrapped in
`try/except: pass`) are applied on every `init_db()` call, so the schema
can be extended without breaking existing databases — this covers every
column above except `creation_mode`/`content_key`/`source_phrase` and the
`UNIQUE` constraint itself, since SQLite can't `ALTER` a `UNIQUE`
constraint in place. Those instead went through a one-time
`_migrate_to_creation_mode_schema(conn)` migration (create `cards_new`
with the new schema, copy every row across, drop the old table, rename),
gated on whether the `content_key` column already exists — the first real
schema migration this codebase ever needed, and still the only one; the
field-config redesign deliberately did **not** need a second one (see
§ Card fields — `creation_mode` just started being written as
`'standard'`/`'cloze'` going forward instead of a registry token, with no
column/constraint change required).

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

`_pocket_tts_voice_options(lang_code)` (main.py) — the Picker option list
for the Source/Target voice rows — labels each voice as
`"<Voice>(<Language>)"`, e.g. `"Estelle(French)"`, deriving the language
straight from the resolved Pocket TTS language id (strip a trailing
`"_24l"`, title-case what's left) rather than a separate display-name
table. Mirrored identically in `cli/src/screens.mjs`'s
`pocketTtsVoiceOptions()`.

## AI prompt structure

One unified prompt template (`PROMPT_TEMPLATE_UNIFIED` in main.py) drives
every AI call, regardless of mode. It requests a JSON response shaped
like:
```json
{
  "ipa": "...",
  "items": [
    {
      "pos": "Noun",
      "gender": "Feminine",
      "text_meaning": "...",
      "text_example_phrase": "...",
      "text_example_translation": "...",
      "synonyms": "word1, word2, word3",
      "gif_keywords": ["keyword1", "keyword2", "keyword3"],
      "category": "..."
    }
  ]
}
```
— but which of `ipa`/`text_meaning`/`text_example_phrase`/
`text_example_translation`/`synonyms`/`gif_keywords` actually appear in the
schema shown to the AI is built dynamically per call, from whichever
fields are enabled in the current Card Fields checklist and not already
sourced from a note (see § Card fields). `pos` and `category` are always
requested (deck-routing/tagging infrastructure, not checklist fields).

- `_build_dynamic_prompt(mode, anchor, context_sentence, requested_fields,
  known_categories)` (main.py) builds the actual prompt text:
  `FIELD_PROMPT_SPECS` maps each checklist field key to its JSON key and
  instruction sentence; only requested fields get a line in the schema.
- `mode` is `"annotation"` or `"spontaneous"` (see § Word sources) — it
  only changes the *framing*, never the envelope shape:
  - `"spontaneous"`: `context_block` says `For the word "{anchor}",
    {meaning_instruction}` (from `MEANING_EXHAUSTIVENESS_SETTINGS`, see
    below) and `count_instruction` allows up to `max_meanings` items —
    "one card per distinct meaning" survives as before.
  - `"annotation"`: `context_block` quotes the literal sentence the
    highlight was found in and instructs the AI to interpret the word
    strictly as used there; `count_instruction` forces exactly one item
    (a specific highlighted usage has one specific meaning in context, not
    several to enumerate).
- `gif_keywords` must be exactly 3 English single words used to build the
  Giphy query, when requested.
- The prompt is language-agnostic — SOURCE_LANG and TARGET_LANG from
  config.py are injected.
- In Spontaneous Mode, how many items are requested is controlled by
  `config.MEANING_EXHAUSTIVENESS` (`"essential"` | `"important"` (default)
  | `"all"`), via `MEANING_EXHAUSTIVENESS_SETTINGS` in main.py — a dict of
  per-level `instruction` (the phrasing injected into the prompt's opening
  sentence), `max_meanings` (the hard cap stated in the Rules section), and
  `max_tokens` (passed through to whichever `_call_<provider>()` is
  active). `"all"` still caps at 12, not truly unlimited — an uncapped
  prompt for a highly polysemous function word (e.g. "the") can ask for
  dozens of technical senses and truncate mid-response into invalid JSON
  regardless of token budget, which is the exact failure this project hit
  before the cap existed. `current_meaning_exhaustiveness()` resolves the
  active level (falling back to `"important"` for an unset/invalid config
  value). Annotation Mode ignores this setting entirely (always exactly
  one item) and uses a fixed, smaller `max_tokens`.
- `generate_card_content(mode, anchor, context_sentence, requested_fields,
  known_categories)` dispatches through `_build_dynamic_prompt()` then
  whichever `_call_<provider>()` is active (see § AI provider layer),
  parses the response into `{"ipa": ..., "items": [...]}` uniformly — no
  per-mode parse-function dispatch anymore.

---

## Card fields

**Spontaneous Mode only.** Annotation Mode has its own, much simpler
content system — § Annotation Mode content presets, below — since a
free-form 11-field checklist turned out to be more surface than
Annotation Mode's actual job needs. Everything in this section (`config.
CARD_FIELDS_JSON`, `configure_card_fields()`, `save_card_fields()`)
applies to Spontaneous Mode exclusively; Annotation Mode never reads or
writes `CARD_FIELDS_JSON`.

**Card content/layout is fully field-driven, not mode-driven** (within
Spontaneous Mode). The old design it replaced (`CREATION_MODE` picking
from 8 pre-built card shapes, `CARD_TYPE` picking basic/reversed/type-
answer/cloze, `CREATION_MODE_VERBOSITY` toggling which fields a mode
showed, and a 4-axis "Card content" cascading picker over all of it) was
retired in one clean break — see § Versioning. It's replaced by a single
checkbox configuration: which of the 11 canonical fields (§ Anki note
fields) appear on the card, where (front/back), in what order, and how.

### `config.CARD_FIELDS_JSON`

A JSON array, one entry per `FIELD_CATALOG` key (main.py):
```json
{"field": "text_meaning", "enabled": true, "position": "back", "order": 3, "interaction": "reveal"}
```
- `field` — one of `word`, `ipa`, `gender`, `image`, `text_meaning`,
  `text_example_phrase`, `text_example_translation`, `synonyms`,
  `audio_word`, `audio_meaning`, `audio_example` — maps 1:1 to both a
  `cards` DB column and an Anki field name (`FIELD_CATALOG`'s
  `anki_field`, e.g. `text_example_phrase` → `Text_Example_Phrase`).
  `word` can't be disabled — every card needs its anchor.
- `position` — `"front"` or `"back"`.
- `order` — sort key within that side. Deliberately **not** part of the
  genanki `fields=[...]` list, which always stays in fixed canonical
  order regardless — only the assembled Front/Back HTML honors `order`.
  This decoupling is what keeps `MODEL_ID` stable across checklist edits
  (see below).
- `interaction` — `"reveal"` (passive, default) | `"type_in"` (Anki's
  `{{type:Field}}` typed-answer check) | `"cloze"` (blank the field inline
  — legal only for `text_example_phrase`).

`load_card_fields()` (main.py) is Spontaneous-Mode-only — the choke point
every field-configuration consumer in this section reads through
(`build_anki_model()`, `_cloze_active()`, `_assemble_side()`, and
Spontaneous Mode's own branches of `_generate_loop()`/`export_decks()`/
`build_notes()`). Annotation Mode never calls it and never touches
`CARD_FIELDS_JSON` at all — it has its own dedicated Model/Note-building
path (§ Annotation Mode content presets, below). `save_card_fields()`
(main.py) writes `CARD_FIELDS_JSON` wholesale through the existing
`write_config()` (never field-by-field) and is likewise
Spontaneous-Mode-only. `load_card_fields()` merges over
`_DEFAULT_FIELD_ENTRY` so a missing/corrupt blob (a key introduced after a
user's `config.py` was written, hand-edited JSON) always yields one
complete, valid entry per catalog field rather than crashing.
`_enabled_keys()`/`_cloze_active()` are the two derived-state helpers
everything else reads.

### Dynamic Model/Template assembly

A genanki `Model` fixes one field list + one set of Front/Back templates
for every `Note` built with it (fields are matched positionally, not by
name) — so unlike the old per-mode registry, there's no longer "one Model
per mode"; there's one Model *family* (`build_anki_model()`, main.py):
- **`standard`** — the fixed 11 canonical fields (+`Image_Raw` if
  `template.REQUIRES_RAW_IMAGE`), always declared regardless of which
  boxes are checked (unchecked fields are simply blank — exactly the same
  trick the old `always_omit` mechanism already proved safe). Front/Back
  HTML is built by `_assemble_side(template, fields, side)`: sorts enabled
  fields for that side by `order`, then for each emits `template.
  FIELD_HTML[field]` (a plain reveal), `{{type:<AnkiField>}}` (interaction
  `"type_in"`), or `{{cloze:Cloze_Text}}` (the example-phrase field with
  interaction `"cloze"`).
- **`cloze`** — used whenever `_cloze_active()`, a structurally different
  genanki `CLOZE`-type Model with its own smaller field set (§ Anki note
  fields). `_assemble_side()` is called again with `allowed_anki_fields=
  _CLOZE_FIELD_NAMES` so a field that isn't part of the cloze Model's
  declared set (e.g. `Sound_Meaning`, `Text_Example_Translation`) is
  silently skipped rather than referencing a field the Model doesn't have.

**`MODEL_ID` deliberately never changes with the checklist** — only
switching *interaction* to/from `"cloze"` changes the actual Model shape
(handled via the separate `MODEL_ID + 10` offset, same as before this redesign). A
hash-per-config `MODEL_ID` was considered and rejected: it would spawn a
brand-new orphaned Anki note type on every checkbox tweak, which is
strictly worse than the current design's stable identity.

`template/*.py` each expose a `FIELD_HTML` dict (field key → HTML
fragment, e.g. `{{#Text_Meaning}}<div class="meaning">{{Text_Meaning}}
</div>{{/Text_Meaning}}`) instead of the old monolithic `FRONT`/`BACK`
strings — one entry per catalog field, wrapped in `{{#Field}}...{{/Field}}`
so a field that's enabled but happens to come back empty for one specific
card (AI miss, no GIF match) renders nothing instead of an empty box.
`build_notes()` positionally fills all 11 field slots (`""` for whatever
wasn't generated) — no per-field gating needed there at all, since
`_assemble_side()` already decided what's visible. The value list is
built as a `{anki_field_name: value}` dict mapped through the same
`FIELD_CATALOG` order `_build_standard_model()` uses to declare the
Model's fields, deliberately — an earlier version hand-typed the value
list in a stale pre-3.0 order that had silently drifted from
`FIELD_CATALOG`'s order, a real shipped bug (audio/GIF/text landed in the
wrong Anki field and rendered as silent/invisible/misplaced) fixed by
tying both lists to the same source instead of maintaining them
independently.

### Note-sourced vs. AI-generated content

Which fields' *content* comes from the AI vs. the source note is not a
per-field user choice — it's fully determined by `(field, WORD_SOURCE)`:
only `word` and `text_example_phrase` can ever come from a note (Annotation
Mode), everything else is always AI-generated. See § Word sources for the
mechanics; `_generate_loop()`'s `requested = enabled - {"word"} - (
{"text_example_phrase"} if note_sourced_example else set())` is the single
line that encodes this.

### Guided flow — "Choose Card Fields"

`configure_card_fields()` (main.py) is `run_generate_wizard()`'s step 2
for Spontaneous Mode (Annotation Mode gets `configure_annotation_content()`
instead — § Annotation Mode content presets) — mode is no longer chosen
here at all, since it's now the app's outermost screen, above the Main
Menu the wizard itself lives under (§ Interactive menu structure) — not a
persistent Configure sub-screen, since reusing this outside the wizard
would have nothing to attach to (which fields are AI-requestable depends
on the already-active mode). One row per `FIELD_CATALOG` entry,
each opening a detail screen (`_field_detail_menu()`) with Enabled
(Toggle)/Position/Order/Interaction — `_FieldEnabledToggle`/
`_FieldSubPicker`/`_FieldSubNumber` (tui.py subclasses) read/write through
`load_card_fields()`/`save_card_fields()` instead of a flat `config.<KEY>`,
the same override pattern the old `_CardContentPicker` established for
`CREATION_MODE`/`CARD_TYPE`. The JS mirror (`cardFieldsMenu()`/
`fieldDetailMenu()`, screens.mjs) is an independent implementation over
the same `--options-json` `field_catalog`/`interaction_labels` data —
same "no shared runtime between Python and JS" precedent the old cascading
picker set.

**Adding a new field**: add one `FIELD_CATALOG` entry (key, label,
`anki_field`, `interactions_allowed`) + a `_DEFAULT_FIELD_ENTRY` default +
a `FIELD_HTML` snippet in each of the 4 templates. If the field is
AI-sourced, add a `FIELD_PROMPT_SPECS` entry too (§ AI prompt structure).
No schema, Model-family, or dispatch changes needed — `_assemble_side()`/
`build_notes()` are already fully generic over the catalog.

---

## Annotation Mode content presets

**Annotation Mode does not use `CARD_FIELDS_JSON` / `configure_card_fields()`
at all, and its card is deliberately minimal: the highlighted phrase/word
(in its sentence, when available) on the front, its translation on the
back — nothing else.** No IPA, no gender, no synonyms, no separate
example-translation field, and **no image, ever** — GIFs are a
Spontaneous-Mode-only concept (see § Word sources for why the AI is never
even asked for `gif_keywords` in this mode). The only real choices left
are a plain boolean (include word-pronunciation audio or not) and a
card-type pick, both written as plain `config.py` keys and consumed on
the fly:

- `config.ANNOTATION_INCLUDE_AUDIO` (bool, default `True`) — whether
  word-pronunciation audio is generated and included, alongside the
  always-on phrase/word + translation.
- `config.ANNOTATION_CARD_TYPE` — how the card tests you: `"basic"`
  (default, reveal the translation) | `"type_in"` (type the phrase/word to
  flip the card) | `"cloze"` (blank the phrase/word within its sentence).

**Annotation Mode has its own dedicated genanki `Model` — it does not
participate in Spontaneous Mode's general 11-field `Model` at all.** An
earlier version of this feature translated a content preset into a
`CARD_FIELDS_JSON`-shaped list and fed it through the shared
`build_anki_model()`/`build_notes()`/`_assemble_side()` pipeline — that
shipped a real bug (two independently hand-typed field-name/field-value
lists silently drifted apart inside `build_notes()`'s non-cloze branch,
so audio/GIF/text landed in the wrong Anki field and rendered as silent/
invisible/misplaced — this equally affected Spontaneous Mode's own
standard cards, and was fixed there too, see below) and left Annotation
Mode's cards sharing `config.MODEL_ID` with Spontaneous Mode, which risks
Anki not refreshing an already-imported note type's templates on
reimport. Both problems are why Annotation Mode now has its own small,
fixed field set instead:

- **`_ANNOTATION_FIELD_NAMES`** (main.py) — `Word`, `Text_Example_Phrase`,
  `Text_Meaning` (used as "Translation" — see below), `Sound_Word`.
  **`_ANNOTATION_CLOZE_FIELD_NAMES`** — `Cloze_Text`, `Word`,
  `Text_Meaning`, `Sound_Word` (`Word` stays declared-but-unrendered for
  the cloze layout, matching the existing Spontaneous-Mode cloze model's
  precedent of keeping the full identity field set even when a given
  template doesn't surface every one of them). No `Image`/`Image_Raw` in
  either list — a GIF is structurally impossible on an Annotation Mode
  note, not just hidden. Neither list overlaps the canonical 11 fields in
  § Anki note fields — this is a structurally different, smaller Model,
  the same precedent Spontaneous Mode's own cloze Model already set.
- **`_build_annotation_model(template, card_type)`** (main.py) —
  hand-written `qfmt`/`afmt` per `card_type` (only 3 exist, fixed layout,
  no position/order picker for this mode — unlike Spontaneous Mode's
  checklist), reusing the same `template.FIELD_HTML["word"/
  "text_example_phrase"/"text_meaning"/"audio_word"]` snippets every other
  mode already renders with (no template.py changes needed; the
  `"image"` snippet is simply never referenced here). Own `MODEL_ID`
  range: `config.MODEL_ID + 20` (basic/type_in — same field set, only the
  template string differs, matching the existing precedent that
  `MODEL_ID` doesn't change for an interaction-only change) /
  `config.MODEL_ID + 30` (cloze — different field set, needs its own
  Model, the same `MODEL_ID + 10` precedent Spontaneous Mode's cloze
  Model already set) — a range Spontaneous Mode's `MODEL_ID`/
  `MODEL_ID + 10` never uses, so Annotation Mode's note type can never
  collide with or be shadowed by an already-imported Spontaneous Mode one.
- **`build_notes()`** branches on `config.WORD_SOURCE == "markdown_notes"`:
  it builds a `{anki_field_name: value}` dict and maps it through the
  *exact same* `_ANNOTATION_FIELD_NAMES`/`_ANNOTATION_CLOZE_FIELD_NAMES`
  list `_build_annotation_model()` used to declare the Model's fields —
  so the declared names and each Note's positional values can never
  drift apart again. Spontaneous Mode's standard-model branch got the
  identical fix (a `{anki_field_name: value}` dict mapped through
  `FIELD_CATALOG`, replacing the old hand-typed positional list that had
  drifted from `FIELD_CATALOG`'s order) — this is the actual bug fix, not
  just an Annotation Mode change. Cloze text uses `make_cloze_text(
  _strip_example_markup(text_example), word)`, identical to the existing
  Spontaneous-Mode cloze path. **The `(category, note)` deck-routing
  tuple always uses `""` for Annotation Mode regardless of `category`** —
  the `topic::<Category>` tag (built from the un-forced `category` local
  variable, just above) still applies, but the note itself never gets
  filed into a category subdeck (see § Category / subdeck organization).
- **`_effective_annotation_card_type()`** (main.py) — the single source
  of truth for the Cloze/extraction-mode fallback below, used by
  `_generate_loop()`, `export_decks()`/`build_notes()`, and
  `configure_annotation_content()`'s option-list filtering.
- **`_generate_loop()`** no longer calls `load_card_fields()` for
  Annotation Mode — it derives `enabled` directly from
  `{"word", "text_example_phrase", "text_meaning"}` plus `"audio_word"`
  when `config.ANNOTATION_INCLUDE_AUDIO` is true (`"image"` is never
  added — this is what keeps Giphy/`gif_keywords` activity out of this
  mode entirely) and `target_mode` from `_effective_annotation_card_type()`
  (`"annotation"` or `"annotation_cloze"` — `cards.creation_mode` values,
  alongside Spontaneous Mode's existing `"standard"`/`"cloze"`;
  `_warn_legacy_rows()` and `get_all_cards()`/`get_processed_words()` all
  already treat `creation_mode` as an opaque per-mode filter key, so this
  needed no changes there beyond `_warn_legacy_rows()`'s hardcoded
  exclusion list). `strip_for_typing` is always `False` for Annotation
  Mode — its `type_in` card type tests `Word`, never
  `Text_Example_Phrase`, so there's nothing to strip there (cloze
  stripping happens independently inside `build_notes()`, unconditionally,
  same as Spontaneous Mode's cloze path always has). `card_exists()` is
  never consulted for `mode == "annotation"` — see § Word sources, this
  mode has no dedup at all.
- **`load_card_fields()`** is Spontaneous-Mode-only again (no
  `WORD_SOURCE` dispatch) — `CARD_FIELDS_JSON` is never read or written by
  Annotation Mode.

Per-`card_type` field layout (all always populate `Word` +
`Text_Example_Phrase` + `Text_Meaning`; `Sound_Word` is populated only
when `ANNOTATION_INCLUDE_AUDIO` is true, empty string otherwise):

| card_type | front | back |
|---|---|---|
| `basic` | `Text_Example_Phrase` (reveal) only | `Text_Meaning` (reveal) + audio |
| `type_in` | `Text_Meaning` (reveal, the prompt) + `Word` (**`{{type:Word}}`**) | `Text_Example_Phrase` (reveal, full context) + audio |
| `cloze` | `{{cloze:Cloze_Text}}` only | `Text_Meaning` (reveal) + audio |

**`basic`'s front is deliberately just `Text_Example_Phrase`, not
`Word` + `Text_Example_Phrase` stacked** — an earlier version showed both,
which looked redundant (`Text_Example_Phrase` already *is* "phrase/word",
via `highlight_word()`'s `<span>` around the exact anchor text within its
sentence — or the AI-generated fallback example when there's no note
context) and, worse, meant a highlight spanning most of a sentence showed
nearly the same text twice. `Word` stays declared on the Model (still
needed for `type_in`'s `{{type:Word}}` and for browsing/searching in
Anki) — it's just never rendered a second time on `basic`'s front.

**Cloze needs real sentence context**, so it only makes sense when
`MARKDOWN_EXTRACTION_MODE = "highlights"`. If `ANNOTATION_CARD_TYPE ==
"cloze"` while extraction mode is `"all_words"` (e.g. the user switched
extraction mode after picking Cloze), `_effective_annotation_card_type()`
silently falls back to `"basic"` — same defensive spirit as
`load_card_fields()`'s Spontaneous-Mode merge-over-defaults for a
corrupt/stale blob.

**Translation, not a dictionary definition.** `text_meaning`'s AI prompt
instruction (`FIELD_PROMPT_SPECS`, § AI prompt structure) is
mode-conditional in `_build_dynamic_prompt()`: Annotation Mode swaps in
`_ANNOTATION_TRANSLATION_INSTRUCTION` (main.py) — a direct, concise
translation of the anchor phrase/word into `TARGET_LANG`, as literally
used in the quoted sentence — instead of the Spontaneous-Mode "dictionary-
style definition" instruction. No new catalog field, DB column, or Anki
field rename — `Text_Meaning`/`text_meaning` stay exactly as they are
structurally; only the instruction text differs by mode.

### Guided flow — "Choose Content & Card Type"

`configure_annotation_content()` (main.py) is `run_generate_wizard()`'s
step 2 for Annotation Mode — a `Toggle` (include word-pronunciation audio)
plus a `Picker` (Card type) instead of `configure_card_fields()`'s
per-field detail screens, writing `ANNOTATION_INCLUDE_AUDIO`/
`ANNOTATION_CARD_TYPE` directly via the existing `write_config()`. The
Card type picker's option list drops `"cloze"` outright when
`MARKDOWN_EXTRACTION_MODE != "highlights"` (same conditional-row
precedent `configure_generation(mode)`'s "Words per run" row already
established). The JS mirror (`annotationContentMenu()`, screens.mjs) is
an independent implementation over the same `--options-json`
`annotation_card_types` data — same "no shared runtime between Python and
JS" precedent `cardFieldsMenu()` set. `run_generate_wizard()`/
`runGenerateWizard()` branch on `config.WORD_SOURCE`/`WORD_SOURCE` to
call this instead of `configure_card_fields()`/`cardFieldsMenu()` for
Annotation Mode. Since this screen runs once per generation, right before
`_do_generate()`, it already doubles as "pick the card type for this
whole run" — no separate per-run mechanism was needed.

---

## Word sources

`WORD_SOURCE` in config.py controls *where the candidate word strings come
from* — set by the top-level mode-selection screen, above the Main Menu
(§ Interactive menu structure: **Annotation Mode** → `"markdown_notes"`,
**Spontaneous Mode (AI)** → `"frequency_list"`), not meant to be
hand-edited, and deliberately session-only (never written to config.py —
see § Interactive menu structure for the in-memory/`--word-source`
mechanics). `_do_generate()`/`_run_headless()` both derive `mode =
"annotation" if markdown_mode else "spontaneous"` from it once per run and
thread that string through `_generate_loop()`/`generate_card_content()`
(§ AI prompt structure) — it's the same value used to decide prompt
framing there. The two sources use genuinely different dedup strategies,
not just different pool builders, so they're dispatched separately rather
than through one shared filter:

- **Spontaneous Mode (`"frequency_list"`, default)** — `_do_generate()`/
  `_run_headless()` call `get_word_pool()` (dispatches through the
  `WORD_SOURCES` registry to `top_n_list(config.SOURCE_LANG,
  config.TOTAL_WORD_POOL)`), then filter with `get_processed_words(conn,
  target_mode)` where `target_mode` is `"standard"`/`"cloze"` (§ Card
  fields) — a **global, per-word** dedup — once a word has any card under
  the active Model shape, it never resurfaces, regardless of which run
  produced it. Correct for a fixed frequency list, where a word is a word
  no matter when it's seen. Every pending item is normalized to a
  `(word, None)` pair — the `None` context means "nothing note-sourced";
  see below.

- **Annotation Mode (`"markdown_notes"`)** — **has no dedup at all, by
  design.** The database has no bearing on what counts as "new" here:
  every run re-reads the tracked file(s) in full and produces one card
  per highlight found, including exact repeats of a previous run's cards
  and repeats of the same word within one file (e.g. the same word
  highlighted twice, in two different sentences, is two cards — not
  collapsed to one). This is a deliberate product decision, not a
  simplification of a more careful mechanism: an earlier version of this
  mode kept a per-file baseline in `markdown_file_state` (see
  § Database schema) and only surfaced highlights not already seen —
  that table and its supporting code (`_commit_markdown_file_state()`,
  `get_markdown_file_state()`, `_markdown_file_key()`) have since been
  removed; `markdown_file_state` itself is left in the schema, unused,
  purely so an existing `progress.db` doesn't need a migration.
  `_build_markdown_pending(conn, "annotation")` (main.py — the second
  argument is accepted only for call-site symmetry, nothing is read from
  or written to the database) resolves `config.MARKDOWN_NOTES_PATH` into
  a file list (`"folder"` — recursively walks it via
  `_iter_markdown_files`, sorted by path; `"file"` — a single `.md`
  path), strips markdown noise (`_strip_markdown_noise`), and extracts
  every `(item, context)` occurrence per `config.MARKDOWN_EXTRACTION_MODE`
  (capped at `config.TOTAL_WORD_POOL` combined across all files, as a
  safety valve — unrelated to dedup, since there isn't any):
  - `"highlights"` — `_extract_highlights_with_context()` returns every
    `==highlighted==` span **plus the sentence it sits in** (markers
    stripped back out of the captured range). The sentence-boundary walk
    is a simple nearest-punctuation (`.!?`) / paragraph-break scan, not a
    real parser — naive on abbreviations, decimals, quoted dialogue, and
    non-Latin/inverted punctuation. A documented limitation, not a bug.
    The window is additionally clamped so it never crosses into a
    *neighboring* highlight's own `==...==` span — without this, two
    highlights close together with no sentence-ending punctuation between
    them (a compact vocabulary-list note, one highlight per line) each
    swallowed the other's raw markup into their "sentence", producing
    identical bloated contexts for both cards and, when the window cut
    through the middle of a highlight's markers instead of the whole
    thing, a dangling literal `==` that never got substituted back out —
    a real bug, confirmed against a real note sample, not just the
    documented punctuation-naivety limitation above.

    **The highlighted span is always the anchor, verbatim — a heading is
    never substituted in, even when it directly labels the highlight**
    (e.g. `### secondes */səgɔ̃d/*` immediately followed by `- ==Attends-
    moi 2 secondes.==`). An earlier version of this function *did* swap
    the heading's raw text in as the anchor for exactly this shape — a
    narrower attempt to stop an entire highlighted sentence from becoming
    the anchor when a heading clearly named a single intended word — but
    that shipped a worse, real, reported bug: a heading holding more than
    a bare word (IPA notation, a grammar note, anything past the word
    itself) polluted both the visible card front and the AI's translation
    target verbatim, and since that raw heading text doesn't actually
    appear in the quoted sentence, the AI's behavior became unreliable
    (translating the whole sentence in some cases, guessing at the
    nearest real word in others). Removed outright rather than patched —
    today's simplified card (§ Annotation Mode content presets) is built
    around "the literal highlighted span *is* the card," whether that
    span is a single word or a whole sentence, so there's no case where
    substituting a heading in is actually correct. This requires heading
    markup (`#`/`##`/...) to still be present in the text this function
    receives — unlike `"all_words"` mode, the `"highlights"` path calls
    `_strip_markdown_noise(raw, strip_headings=False)` so heading
    *positions* survive, purely so a heading line can still act as a hard
    boundary for the sentence-context walk below (the same defensive
    reason as the neighboring-highlight clamp above — a heading with no
    punctuation after it could otherwise bleed into the *next*
    highlight's context). A highlight is also almost always written as a
    list item (`- ==...==`), so the boundary walk's extracted sentence
    has a leading bullet/ordinal marker (`_MD_LEADING_BULLET_RE`) stripped
    off before use — otherwise a literal `"- "` would leak onto the card
    front the same way the heading text used to.
  - `"all_words"` — `_extract_all_words()` still returns bare words with no
    surrounding context (`context = None` for every item) — a single
    ranked word has no one "sentence" to attribute to it.

  Every file is read and re-extracted in full, every run — there is no
  per-file baseline, no on-disk-size shortcut, and no filtering against
  what a previous run already produced. `_generate_loop()` also skips its
  `card_exists()` gate entirely for `mode == "annotation"` (see below),
  and `_do_generate()`/`_run_headless()` pass `len(pending)` as
  `_generate_loop()`'s limit — **Annotation Mode has no per-run cap**,
  unlike Spontaneous Mode's `config.WORDS_PER_RUN` — so every highlight
  found this run is attempted in the same pass (a document's highlight
  set is finite and user-authored, not an endless pool to throttle
  against).

### Note-sourced content

The `context` half of each `(item, context)` pair is what lets Annotation
Mode source its example phrase from the note itself instead of the AI: in
`_generate_loop()`, whenever `mode == "annotation"` and `context` is
truthy (`note_sourced_example`), `text_example_phrase`'s content becomes
the literal sentence — `highlight_word(context, anchor)` wraps the exact
anchor text in a `<span class="highlight">`, reusing the same CSS class
`highlight_delimited()`'s `**marker**`-based highlighting already uses, so
no template changes were needed — and that field is excluded from the set
requested from the AI for that call. `Word`'s content is always the
literal `anchor` string regardless of mode (never AI-generated).
`text_meaning` is the only other field ever requested from the AI in this
mode (§ Annotation Mode content presets — the card has no IPA, gender,
synonyms, or separate example-translation field to fill in the first
place), generated in the same call using the quoted sentence as context
(§ AI prompt structure). `_content_key()` folds a fresh `uuid4` nonce into
the `word::sentence` hash for Annotation Mode specifically, so no two
calls ever produce the same key — this is what lets a re-processed
highlight (even an exact repeat) insert as a new row instead of being
silently dropped by the `UNIQUE(creation_mode, content_key, meaning_id)`
constraint (§ Database schema) — the mechanical enforcement of "no dedup"
above.

Extraction is still capped at `config.TOTAL_WORD_POOL` overall (across all
files' items combined, not per file). An empty/invalid
`MARKDOWN_NOTES_PATH` (for the active `MARKDOWN_SOURCE_MODE`) still prints
a `[WARN]` and returns an empty pool rather than raising.

No new third-party dependency was needed (pure `os`/`re`), so unlike the
`anthropic`/`pocket_tts` lazy-optional-import pattern (see § AI provider
layer / § Local TTS provider), this code is imported unconditionally at
the top of main.py.

**Known limitations**: no lemmatization/stemming exists anywhere in this
codebase — a word extracted from prose keeps whatever inflected/conjugated
surface form it appeared in, so e.g. "mangera" and "manger" are treated as
two unrelated anchor words. The sentence-boundary heuristic (above) is a
regex walk, not a real sentence parser — treat its output as "close
enough for AI context," not authoritative. And since this mode has no
dedup at all, running it repeatedly over an unchanged note deliberately
produces a fresh duplicate card set every time — that's the point, not a
bug to guard against.

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
- **Annotation Mode never gets a subdeck, tags only.** `build_notes()`
  still computes `category` and the `topic::<Category>` tag exactly as
  above for Annotation Mode, but the `(category, Note)` tuple it appends
  for deck routing always carries `""` for that mode instead — so
  `_build_deck_tree()` files every Annotation Mode card into the root
  deck regardless of category, while the `topic::` tag still applies (see
  § Annotation Mode content presets).

---

## Export logic

`export_decks(conn, template, filename=None)` has two distinct call
shapes, both without ever prompting for a card type (retired in the
field-config redesign — see § Card fields):

- **Auto-export** (`filename=None`) — runs automatically at the end of
  every `_do_generate()`/`_run_headless()` call, no separate step or
  prompt. Writes the same two files as before:
  - `deck_new.apkg` — contains only cards where `exported = 0`. After
    export, those cards are marked `exported = 1`. **The user imports
    this file daily.** It never overwrites existing Anki cards, preserving
    any manual edits the user has made.
  - `deck_full.apkg` — contains all cards regardless of export status.
    Used as a full backup or for a fresh Anki install.

  Both files use the same Anki model (`MODEL_ID`) but different `DECK_ID`s
  (`DECK_ID` for full, `DECK_ID + 1` for new) to avoid conflicts on import.

- **Manual export** (`filename` given — the "Export decks" menu action,
  `run_export()`) — prompts only for an output filename (`ask()`,
  defaulting to `config.DECK_OUTPUT_FULL`) and writes **one** full-backup
  `.apkg` under that name. Does **not** touch the `exported`/
  `mark_as_exported` bookkeeping — a manual export is a point-in-time
  snapshot/backup, not a "new cards" run, so it shouldn't affect what the
  next auto-export considers new.

Every file is actually a small **deck tree**, not a single flat deck:
cards with a `category` are routed into a `"<DECK_NAME>::<Category>"`
subdeck via `_build_deck_tree()`, alongside the root deck for
uncategorized cards — see § Category / subdeck organization.

`_warn_legacy_rows(conn)` fires a one-time `[WARN]` if any
pre-field-config-redesign `creation_mode` rows are found un-exported
(§ Database schema) — they're
no longer reachable by export (clean break), so this keeps that fact
visible rather than silent.

---

## Key design decisions

- **One card per meaning, not per word — Spontaneous Mode only.** A word
  with 3 distinct meanings generates 3 separate cards, each with its own
  GIF and audio (`MEANING_EXHAUSTIVENESS` caps how many, § AI prompt
  structure). Annotation Mode always produces exactly one card per
  highlight — a specific quoted usage has one specific meaning in
  context, not several to enumerate (§ Word sources).

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

## Interactive menu structure

**Mode selection is the outermost screen**, above the Main Menu, not a
step inside "Generate new cards" — every other screen (Generate, Export,
Configure, Statistics) is scoped to whichever mode is currently active,
since what they show/do depends on it (Generation Settings' fields differ
per mode, § Card fields):

```
Choose Creation Mode                          (outermost screen)
  [1] Annotation Mode          — cards from words/phrases highlighted in your notes
  [2] Spontaneous Mode (AI)    — AI invents words and example content automatically
  [0] Exit                                    — quits the app (no screen above this one)

  └─> Main Menu — <Mode Label>
        [1] Generate new cards      — content config (mode-dependent) -> generate + auto-export
        [2] Export decks            — recent exports, then a filename prompt -> writes one full-backup .apkg
        [3] Configure                — Language / AI & API / Deck & cards / Generation / Audio / GIF / Rate limits
        [4] Statistics               — total cards, by POS, recent activity, export history
        [0] Exit                     — back to Choose Creation Mode (not the app)

Generate new cards -> step 2 (mode-dependent)
  Spontaneous Mode -> Choose Card Fields
    one row per field (Word, IPA, Gender, Image, Meaning, Example phrase,
    Example translation, Synonyms, Word/Meaning/Example audio) — each opens
    a detail screen (Enabled / Position / Order / Interaction), see § Card
    fields — then "Continue -> Generate"
  Annotation Mode -> Choose Content & Card Type
    Include word pronunciation audio (Toggle) + Card type (Picker,
    "Cloze" hidden unless Markdown extraction = Highlights), see
    § Annotation Mode content presets — then "Continue -> Generate"

Configure -> Generation Settings           (mode-dependent contents)
  Annotation Mode:    Total word pool, Markdown source mode,
                       Markdown notes path, Markdown extraction
                       (no "Words per run" — every new item found runs in one pass)
  Spontaneous Mode:   Words per run, Total word pool, Meaning exhaustiveness

Configure -> Deck & cards, Audio, GIF     (also mode-dependent)
  Deck & cards:  category toggle relabeled "Category tags" in Annotation
                 Mode (no subdecks there, see § Category / subdeck
                 organization)
  Audio:         "Example sentence audio"/"Meaning audio" toggles hidden
                 in Annotation Mode (no such fields on that card)
  GIF:           row hidden entirely in Annotation Mode (no GIF, ever)
```

**Mode is session-only, never persisted.** Picking Annotation or
Spontaneous at the top never rewrites `config.py`'s `WORD_SOURCE` — it's
confirmed with the user that selecting a mode shouldn't silently become a
new sticky default just from looking at it. `main()` sets
`config.WORD_SOURCE = mode` as a **plain in-memory attribute** (not
through `write_config()`), which every downstream read (`_do_generate()`,
`get_processed_words()`, `configure_generation()`, etc.) already picks up
transparently for the rest of that process's lifetime — never written to
disk, so a fresh `python main.py` always starts back at mode selection
with whatever `WORD_SOURCE` is actually saved in `config.py` (unaffected
by any prior session's in-memory choice).

**`--word-source=<value>` bridge flag** (`_run_cli_bridge()`, only
meaningful alongside `--generate`) is how this same session-only override
crosses the JS TUI's subprocess boundary: `cli/src/bridge.mjs`'s
`generate(wordSource)` passes the mode chosen by `screens.mjs`'s
`pickCreationMode()`/`mainMenu()` (held in the JS process's own in-memory
config cache via `getCfgStore().setLocal()`, itself never calling
`bridge.setConfig()`) as this flag on every `--generate` invocation, so
each fresh Python subprocess gets the right `config.WORD_SOURCE` in memory
for that one run without ever touching `config.py` either. Both frontends
end up with the identical guarantee — mode selection is invisible to
`config.py` end to end — despite the JS side needing an extra hop to get
there that the single-process Python TUI doesn't.

No separate "Card type guide" screen anymore — the old basic/reversed/
type-answer/cloze framing is gone; "Basic + Reversed" specifically was
dropped in the checkbox field-config redesign with no replacement (see
§ Card fields), and what each remaining interaction does is
self-explanatory from the checklist itself.

**Config warnings surface on the Main Menu, not just one screen deeper.**
`_config_warnings()` (main.py) checks `ai_key_missing()` and a new
`giphy_key_missing()` (`config.ENABLE_GIF and config.GIPHY_API_KEY ==
"your_giphy_api_key_here"` — the same condition `_do_generate()` already
silently acted on at generation time); `_mode_main_menu()`'s "Configure"
row hint appends `⚠ N` when either fires. The JS mirror
(`getConfigWarnings()`, screens.mjs) drives the same indicator on
`modeMainMenu()`'s "Configure" row. Per-screen indicators still exist too
(`configure_ai`'s "Provider settings" row, `configure_main`'s "AI & API
keys"/"GIF" rows) — the Main Menu count and the per-screen "! key
missing" suffixes are two views of the same two checks, not separate
logic.

**The Giphy API key lives under GIF Settings** (`configure_gif()`/
`settingsGif()`), not AI & API Settings — it moved there since it's the
only screen that actually uses it (`fetch_gif()`), fixing a
location that never matched what consumed the value.

**Interaction hints are consolidated into one focus-aware status bar/
footer**, replacing the 4 duplicated per-row inline hints
(`Toggle`/`Picker`/`TextInput`/`NumberInput` used to each render their own
"Space/Enter to toggle" / "← → cycle" / "← → adjust, Enter to type" /
"Enter to edit" when focused) plus the old always-generic status bar that
didn't know what was focused. `tui.py`'s `_draw_statusbar(win,
focused_item)` now takes the focused item and looks up its hint from
`_STATUSBAR_HINTS` (keyed on `type(focused_item).__name__`), alongside
fixed `↑↓ navigate`/`Esc·q back` anchors; `_run_inner()` passes
`items[current]`. The widgets' `render()` methods no longer append any
hint text — they only show label + value now. The JS mirror
(`runScreen.mjs`'s `draw()`) computes the same footer from a `KIND_HINTS`
lookup keyed on `items[focused]?.kind`, falling back to the existing
edit-mode hints when `editing` is true; `render.mjs`'s `computeRow()` had
its 4 matching per-kind hint renders removed the same way.

**Back vs. quit**: Esc/q reliably pops exactly one menu level everywhere
in both TUIs — nesting is plain call-stack recursion (`run_menu()`
reuses the live curses window when already inside one), not a
level-skipping mechanism, so this was already correct and needed no
change. Quitting the app is reachable only from the single outermost
mode-selection screen (`_pick_creation_mode()`/`pickCreationMode()`, via
its own Esc/q/'Exit'). The one real gap fixed: `main()`'s interactive body
now wraps the mode-selection loop in `try/except KeyboardInterrupt`
(`print()` + fall through to `finally: conn.close()`) instead of letting
Ctrl+C propagate into a raw traceback — `curses.wrapper()` already
restores the terminal on its own, so this was a UX/consistency fix (now
matching the JS TUI's existing clean `process.exit(0)` on Ctrl+C via
`term.mjs`'s `isExitCombo()`), not a terminal-corruption bug.

**`run_generate_wizard()` is deliberately NOT an `Action(print_mode=True)`**
— it mixes a curses step (`configure_card_fields()`/
`configure_annotation_content()`, a `run_menu()` picker) with a
print-based one (`_do_generate()`). Wrapping the whole Action in
`print_mode=True` used to tear curses down *before* the picker step ran,
forcing that step's own `run_menu()` call to open a second, fully-nested
`curses.wrapper()` session (a second `initscr()`/`endwin()` cycle) just to
get curses back — and restoring the parent window afterward (`_ctx
['stdscr'] = saved; saved.keypad(True); ...`) without a matching fresh
`initscr()` left the terminal's arrow-key escape-sequence parsing state
inconsistent enough that pressing an arrow key right after backing out of
the picker could misnavigate back into it — a real, reported bug. Fixed
by extracting `Action(print_mode=True)`'s suspend/restore logic into
`_tui.run_in_print_mode(func)` (tui.py) and having `run_generate_wizard()`
call the picker step first — while curses is still the *parent's own live
window*, so `run_menu()` takes its normal nested-reuse path
(`_ctx['stdscr'] is not None`) instead of a second `curses.wrapper()` —
then suspend curses only around `_do_generate()`/`pause()` via
`run_in_print_mode()`. One `endwin()`/restore cycle total per "Generate
new cards" invocation, not two nested ones.

**The active Creation Mode is shown in the persistent header on every
screen**, not just the Main Menu's own title (`f'Main Menu — {label}'`,
which is invisible as soon as you navigate into Configure or any
submenu). `tui.py`'s `_draw_banner()` — drawn on every curses screen —
appends `mode: <label>` to its existing info line, reading
`_cfg.WORD_SOURCE` through a small local `_MODE_LABELS` dict (duplicated
from main.py's copy rather than imported, same circular-import avoidance
`write_config`'s lazy import already established). The JS mirror
(`bannerSummary()`, screens.mjs, already the persistent per-screen header
on every `runScreen`/`staticScreen` call) appends the same thing via the
`MODE_LABELS` dict already defined in that file.

## Config options summary (config.py)

```python
AI_PROVIDER                     # "groq" | "openai" | "anthropic" | "gemini" | "ollama"
GROQ_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY / GIPHY_API_KEY
AI_MODEL / OPENAI_MODEL / ANTHROPIC_MODEL / GEMINI_MODEL / OLLAMA_MODEL
OLLAMA_HOST                     # local Ollama server address (default http://localhost:11434)
SOURCE_LANG / TARGET_LANG       # e.g. "fr" / "English"
TTS_SOURCE_LANG / TTS_TARGET_LANG  # gTTS language codes
WORDS_PER_RUN                   # new words per script execution — Spontaneous Mode only;
                                 # Annotation Mode has no per-run cap (§ Word sources)
TOTAL_WORD_POOL                 # total frequency pool size
MEANING_EXHAUSTIVENESS          # "essential" | "important" | "all" (see § AI prompt structure)
CARD_TEMPLATE                   # "dark" | "light" | "minimal" | "immersive"
CARD_FIELDS_JSON                # Spontaneous Mode only — field checklist: enabled/position/order/
                                 # interaction per field (see § Card fields — set via Generate new
                                 # cards' wizard, not hand-edited)
ANNOTATION_INCLUDE_AUDIO         # Annotation Mode only — bool, include word-pronunciation audio
                                 # (see § Annotation Mode content presets)
ANNOTATION_CARD_TYPE            # Annotation Mode only — "basic" | "type_in" | "cloze"
                                 # (see § Annotation Mode content presets)
WORD_SOURCE                     # "frequency_list" | "markdown_notes" (see § Word sources — set via
                                 # Generate new cards' first step, not hand-edited)
MARKDOWN_NOTES_PATH             # folder or single .md file, per MARKDOWN_SOURCE_MODE
MARKDOWN_SOURCE_MODE            # "folder" | "file"
MARKDOWN_EXTRACTION_MODE        # "highlights" | "all_words"
ENABLE_CATEGORIES               # category subdecks + topic:: tags (Annotation Mode: tags only, no
                                 # subdecks — see Category / subdeck organization)
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
- `--generate` (optionally with `--word-source=<value>`) — runs
  `_do_generate(conn)` (the interactive generation loop minus the trailing
  `pause()`) and returns; auto-exports at the end (§ Export logic).
  `--word-source` sets `config.WORD_SOURCE` in-memory for this one
  subprocess invocation only (never persisted) — how the JS TUI's
  session-only mode choice crosses the process boundary, see § Interactive
  menu structure.
- `--export` / `--export=<filename>` — runs `_do_export(conn,
  filename=filename)`; omitting `=<filename>` writes the default new+full
  pair, a filename writes a single full-backup `.apkg` under that name —
  no card-type prompt anywhere anymore (§ Card fields / § Export logic).
- `--stats-json` — `_stats_data(conn)` as JSON (same figures as
  `show_statistics()`, kept as a separate helper with its own queries rather
  than refactoring the working curses screen).
- `--config-json` — `_config_snapshot()`: every public primitive attribute of
  `config` module, as JSON. Generic — reads whatever config.py currently
  exposes, no key whitelist to keep in sync.
- `--options-json` — `_options_snapshot()`: the static Picker option lists
  already defined in main.py (`_AI_PROVIDERS`, `_GROQ_MODELS`,
  `_ANTHROPIC_MODELS`, `_TEMPLATES`, `_GIF_RATINGS`, `field_catalog`,
  `interaction_labels` — § Card fields) plus the provider lookup dicts
  (`AI_PROVIDER_LABELS`, `AI_PROVIDER_MODEL_FIELD`, `AI_PROVIDER_KEY_FIELD`)
  — so the JS Picker screens and banner never hardcode a second copy of
  this data.
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
