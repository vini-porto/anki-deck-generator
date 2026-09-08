# Changelog

All notable changes to this project are documented here. Versioning follows
[Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`:

- **MAJOR** — breaking changes or a fundamentally redesigned experience
- **MINOR** — new backward-compatible features
- **PATCH** — fixes and small refinements

The current release is tracked in the `VERSION` file at the repo root (the
single source of truth main.py, tui.py, and the JS TUI all read from) and is
shown in the README badge and in both interactive menus.

## [Unreleased]
### Fixed
- **Standard (non-cloze) cards could have audio, GIF, and text landing in
  the wrong Anki field** — silent audio, invisible GIFs, and misplaced/
  missing text depending on which fields were enabled. Root cause:
  `build_notes()` built its Note field *values* in a stale, hand-typed
  order that had silently drifted from `FIELD_CATALOG`'s order (which
  `_build_standard_model()` uses to declare the Model's field *names* —
  genanki matches the two positionally, not by name). This affected
  Spontaneous Mode's standard cards too, not just Annotation Mode's — the
  fix ties both lists to the same source so they can't drift apart again.
- **Two highlights close together in a Markdown note (e.g. a compact
  vocabulary list, one `==highlight==` per line, no period between them)
  could swallow each other's raw text into their "sentence" context** —
  producing identical, bloated content for both resulting cards instead
  of two clean, distinct ones, and sometimes leaving a literal, un-stripped
  `==` in the card when the window cut through the middle of the other
  highlight's markers. `_extract_highlights_with_context()`'s
  sentence-boundary window is now clamped to never cross into a
  neighboring highlight's own span.
- **A heading directly above a highlight (e.g. a personal note-taking
  convention like `### secondes */səgɔ̃d/*` followed by `- ==Attends-moi
  2 secondes.==`) had its raw text — IPA notation and all — used verbatim
  as the card's anchor and translation target, instead of the actual
  highlighted text.** This polluted the visible card front with the
  heading's contents and made translation unreliable: since that raw
  anchor doesn't actually appear in the quoted sentence, the AI would
  sometimes translate the whole sentence and sometimes guess at whichever
  real word looked closest instead. The highlighted span is now always
  the anchor, full stop, regardless of any heading above it — a heading
  is only ever used as a sentence-boundary marker for the surrounding
  context. A highlight's extracted sentence also no longer keeps a
  leading list-bullet marker (`"- "`) — that leaked onto the card front
  the same way.
- **After entering Annotation Mode's "Choose Content & Card Type" screen
  and backing out, arrow keys could misnavigate back into it.** Root
  cause: `run_generate_wizard()` ran entirely under `Action
  (print_mode=True)`, which tore curses down *before* the content-picker
  step — forcing that step to open a second, fully-nested curses session
  just to display itself, and restoring the parent window afterward
  without matching that session's own terminal-state changes. Fixed by
  running the picker while the parent's curses window is still live (its
  normal behavior) and only suspending curses around the actual
  print-based generate step.
- **Gemini calls frequently failed with `Read timed out` and were skipped
  outright** — the request had a fixed 30s timeout with no retry, so any
  response slower than that (not uncommon on Gemini's free-tier models)
  lost the word for the entire run instead of recovering. The timeout is
  now 60s and a read timeout is retried (up to 3 times, same retry budget
  the existing 429 handling already used) before the word is given up on.
### Changed
- **Annotation Mode's "basic" card type no longer shows the phrase/word
  twice.** The front used to show a bare `Word` line stacked above the
  full highlighted sentence, which was redundant (and, for a highlight
  spanning most of a sentence, nearly duplicated text) — now the front is
  just the highlighted sentence.
- **Annotation Mode now has its own dedicated, minimal Anki note type**
  instead of sharing Spontaneous Mode's general 11-field one — just Word,
  Example phrase, Translation, and Word audio (+ a Cloze variant). No
  Image field — Annotation Mode never has a GIF (see below). Own Anki
  note-type ID range, so it can't collide with an already-imported
  Spontaneous Mode note type. Already-generated cards don't need
  regenerating — a fresh "Export decks" re-exports everything correctly
  from the same underlying data; since it's a new note type, you'll
  likely want to delete your old, broken-content Annotation Mode
  cards/note-type in Anki after importing the corrected export.
- **Annotation Mode's card is now deliberately minimal: the highlighted
  phrase/word on the front, its translation on the back, nothing else.**
  "Generate new cards" now shows a simple "Choose Content & Card Type"
  step for Annotation Mode: a single "Include word pronunciation audio"
  toggle and a Card type picker (Basic, Type-in-answer, or Cloze deletion
  — Cloze only offered when Markdown extraction = Highlights, since it
  needs real sentence context). The old 4-way content preset (which also
  offered an image) is gone — Annotation Mode never fetches a GIF or asks
  the AI for `gif_keywords` at all now. Spontaneous Mode is unaffected —
  it keeps the full field checklist exactly as before. Annotation Mode's
  "Translation" field also now asks the AI for a direct translation of
  the phrase/word instead of a dictionary-style definition.
- **Annotation Mode no longer routes cards into a category subdeck** —
  only the `topic::<Category>` tag still applies; every Annotation Mode
  card now lands in the root deck. Spontaneous Mode's subdeck routing is
  unaffected. The "Category subdecks & tags" toggle is relabeled
  "Category tags" while in Annotation Mode to match.
- **Annotation Mode no longer deduplicates anything.** Every run now
  re-reads the tracked markdown file(s) in full and generates one card
  per highlight found — including exact repeats of a previous run's
  cards, and repeats of the same word within one file (previously
  collapsed to a single card). The database has no bearing on what counts
  as "new" in this mode anymore; the previous per-file "already read"
  tracking has been removed.
- **Annotation Mode no longer caps a run at `WORDS_PER_RUN`.** Every
  highlighted item/word found across the tracked markdown file(s) is now
  processed in a single run instead of requiring repeated runs to work
  through one document — `WORDS_PER_RUN` now only governs Spontaneous
  Mode, and its setting row is hidden from Annotation Mode's Generation
  Settings screen accordingly.
- **The Pocket TTS voice picker now shows the language alongside each
  voice name**, e.g. "Estelle(French)" instead of just "Estelle".
- **Audio and GIF settings are trimmed to what's relevant per mode.**
  Annotation Mode's Audio Settings screen hides the "Example sentence
  audio"/"Meaning audio" toggles (that card has no such fields), and its
  Configure menu drops the GIF row entirely (Annotation Mode never has a
  GIF).

## [2.6.0] - 2026-08-15
### Changed
- **Menu restructured around two top-level creation modes**: "Annotation
  Mode" (cards from words/phrases highlighted in your notes) and
  "Spontaneous Mode (AI)" (AI invents words and content from scratch),
  replacing the old nested Word source picker. Mode selection is now the
  very first screen the app shows — above the Main Menu, not a step inside
  Generate new cards — and every other screen (Generate, Export, Configure,
  Statistics) is scoped to whichever mode is active; Configure → Generation
  in particular now only shows the settings relevant to that mode
  (Markdown notes settings for Annotation, Meaning exhaustiveness for
  Spontaneous). "Exit" on the mode-scoped Main Menu returns to mode
  selection rather than quitting the app, so switching modes mid-session
  doesn't require a restart. Mode selection is session-only by design —
  picking one never rewrites `config.py`.
- **Card content is now a checkbox field configuration**, not a choice
  between pre-built card shapes. Step 2 of Generate new cards lets you
  enable/disable each of the 11 fields and set its position (front/back),
  order, and interaction (reveal / type-the-answer / cloze deletion for
  the example phrase) — replacing `CREATION_MODE` (8 fixed modes),
  `CARD_TYPE`, `CREATION_MODE_VERBOSITY`, and the 4-axis "Card content"
  cascading picker entirely. New `CARD_FIELDS_JSON` config key.
- **Export is automatic.** Generating cards now exports `deck_new.apkg`/
  `deck_full.apkg` at the end with zero prompts — the old card-type
  selection step before export is gone. The manual "Export decks" menu
  action still exists (for rebuilding a backup on demand) — it now shows
  recent export history, then prompts for an output filename and writes a
  single full-backup `.apkg`.
- **Annotation Mode now passes real note context to the AI**: a
  highlighted word/phrase and the sentence it was found in are used
  directly as the Word/Example phrase fields' content (no AI call wasted
  on them), and every other requested field is AI-generated using that
  quoted sentence as authentic context — instead of being generated from
  the bare word with no context, as before.
### Removed
- "Basic + Reversed" (auto-generating a second, flipped meaning→word card
  per note) has no equivalent in the new field-checklist system and is not
  carried forward. Cards already exported to Anki are unaffected.
- The `CREATION_MODE`/`CARD_TYPE`/`CREATION_MODE_VERBOSITY` config keys and
  the entire 8-mode `CREATION_MODES` registry are deleted outright (clean
  break, not deprecated). `progress.db` rows created before this release
  keep their old shape but are no longer reachable by export — a one-time
  `[WARN]` flags any that are still un-exported.
- The Giphy API key moved from AI & API Settings to GIF Settings, since
  it's only ever used by GIF fetching — it was never actually read by
  anything under AI & API Settings.
- The Main Menu's "Configure" row now shows a `⚠ N` warning count when an
  AI provider key or the Giphy key (while GIFs are enabled) is still
  unset, instead of only surfacing that one screen deeper.
- Every interactive row's separate inline hint ("Space/Enter to toggle",
  "← → cycle", "← → adjust, Enter to type", "Enter to edit") was removed
  in favor of one status bar/footer that shows the right hint for
  whatever's currently focused — previously both existed at once, and the
  always-on status bar never actually matched the focused row's controls.
- The active Creation Mode (Annotation / Spontaneous AI) is now shown in
  the persistent header on every screen, not just the Main Menu's own
  title — no more losing track of which mode is active while deep in
  Configure.
- Statistics again include a category/subdeck breakdown in both TUIs
  (previously computed only by the Python curses screen, never exposed to
  the JS bridge).
### Fixed
- `write_config()` now appends a config.py key that doesn't exist yet
  instead of failing — needed for `CARD_FIELDS_JSON` on any config.py
  written before this release, but fixes the same latent gap for every
  future new setting too.
- Generating cards no longer re-exports and re-logs an identical full
  backup when a run finds nothing new (exhausted pool, no new markdown
  content, every AI call failed) — "Recent exports" was piling up
  near-duplicate-looking entries every time Generate ran, even as a no-op.
- Ctrl+C during interactive navigation now exits the Python TUI cleanly
  instead of crashing with a raw traceback, matching the JS TUI's
  existing clean-exit behavior.

## [2.5.0] - 2026-07-26
### Added
- `MEANING_EXHAUSTIVENESS` setting — choose how many distinct meanings the
  AI generates per word ("essential", "important", or "all") instead of a
  fixed cap.
- `CREATION_MODE`: a third independent axis (alongside card type and card
  template) controlling what the AI generates and what becomes a card's
  front vs. back, via a `CREATION_MODES` registry. 8 modes total: Word →
  Meaning, Phrase in Context, Audio → Meaning, Audio Recognition, Audio
  Recognition Typing, Write Response, Phrase Audio Recognition, and Phrase
  Audio Recognition Typing.
- `CREATION_MODE_VERBOSITY` ("complete"/"simple") — trims a card down to
  its essential field(s) for the audio/production modes, also skipping TTS
  generation for any field that would never be shown.
- `WORD_SOURCE`: generate cards from the user's own markdown notes (e.g. an
  Obsidian vault) instead of only a frequency word list, extracting either
  `==highlighted==` spans or every word ranked by occurrence.
- A guided "Card content" configuration flow in both interactive menus
  ("What's the card about — word or phrase?" then "How do you want to be
  tested?"), replacing a single flat mode picker plus a separately-located
  card type picker.
### Fixed
- The curses menu's title banner no longer misaligns with long AI model
  names (e.g. `gemini-3.5-flash-lite`) — box width is now computed from
  content length instead of hardcoded.
- Gemini generation reliability: failed generations are no longer saved as
  incomplete stub cards, and requests now adaptively pace themselves to the
  provider's actual per-minute rate limit.
- `get_all_cards()` no longer silently excludes every card from a mode that
  doesn't populate an example sentence by design (Audio Recognition /
  Audio Recognition Typing) from every export.
- `write_config()` now escapes embedded quotes/backslashes in string
  values before writing them into config.py.
### Changed
- Removed the standalone "Versioning" README section (redundant with the
  version badge and this changelog).

## [2.4.1] - 2026-07-24
### Fixed
- `Text_Meaning` no longer embeds the raw source-language word inside the
  native-language definition sentence (the AI prompt previously instructed
  it to open with e.g. "To [word] means..."). That mixed two languages in
  one sentence, which sounded wrong when read aloud by `Sound_Meaning`'s
  single-language TTS voice. Only affects newly generated cards.

## [2.4.0] - 2026-07-24
### Added
- Local, offline text-to-speech via [Pocket TTS](https://github.com/kyutai-labs/pocket-tts)
  (Kyutai Labs) as an alternative to gTTS, selectable per-run via
  `TTS_PROVIDER` — CPU-only, no API key, multiple realistic voices (21 for
  English), with automatic per-field fallback to gTTS for languages Pocket
  TTS doesn't ship a model for.

## [2.3.0] - 2026-07-21
### Added
- Version tracking: the `VERSION` file, this changelog, a version badge in
  the README, and the version number displayed in both interactive menus
  (curses `tui.py` and the JS TUI).

## [2.2.1] - 2026-07-19
### Changed
- Rebuilt the JS TUI's rendering layer on Lip Gloss (`@charmland/lipgloss`),
  replacing the earlier Ink/React implementation, after Ink's color-support
  detection failed to render color in the user's real terminal.
### Fixed
- A memory-leak crash in the JS TUI (unconditional per-call WASM heap
  growth inside the Lip Gloss binding), worked around via render-output
  memoization.

## [2.2.0] - 2026-07-16
### Added
- A zero-dependency JavaScript TUI (`cli/`) as a second frontend over
  `main.py`, mirroring the curses menu's screens through the same bridge
  protocol.

## [2.1.0] - 2026-07-14
### Added
- Multi-provider AI support: OpenAI, Anthropic (Claude), Google Gemini, and
  local Ollama models, alongside the existing Groq provider.
- Card categorization into Anki subdecks and `topic::` tags for
  language-specific study blocks (e.g. Phrasal Verbs).

## [2.0.0] - 2026-07-04
### Added
- Interactive terminal menu (curses), 4 Anki card types (basic, basic +
  reversed, type-the-answer, cloze), a statistics screen, and an in-app
  settings editor.

## [1.0.0] - 2026-06-04
### Added
- Initial release: AI-generated flashcard content, Giphy GIFs, gTTS audio,
  incremental SQLite-backed generation, and `.apkg` export.
