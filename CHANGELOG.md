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
