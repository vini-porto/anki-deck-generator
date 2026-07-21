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
