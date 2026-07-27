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
