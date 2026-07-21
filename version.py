"""Single source of truth for the project's release version.

Reads from VERSION (repo root) so main.py, tui.py, and the JS TUI (via the
--options-json bridge flag) all report the same number without hand-syncing
separate copies. Bump VERSION — and add a CHANGELOG.md entry — on every
user-facing change: PATCH for fixes/small tweaks, MINOR for new backward-
compatible features, MAJOR for breaking changes or a redesigned experience.
"""

from pathlib import Path

APP_VERSION = (Path(__file__).parent / "VERSION").read_text().strip()
