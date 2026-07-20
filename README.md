```
  █████╗ ███╗   ██╗██╗  ██╗██╗    ██████╗ ███████╗ ██████╗██╗  ██╗
 ██╔══██╗████╗  ██║██║ ██╔╝██║    ██╔══██╗██╔════╝██╔════╝██║ ██╔╝
 ███████║██╔██╗ ██║█████╔╝ ██║    ██║  ██║█████╗  ██║     █████╔╝ 
 ██╔══██║██║╚██╗██║██╔═██╗ ██║    ██║  ██║██╔══╝  ██║     ██╔═██╗ 
 ██║  ██║██║ ╚████║██║  ██╗██║    ██████╔╝███████╗╚██████╗██║  ██╗
 ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝    ╚═════╝ ╚══════╝ ╚═════╝╚═╝  ╚═╝
            AI-powered Anki flashcard deck generator
```

[![Python](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![AI](https://img.shields.io/badge/AI-Groq%20%7C%20OpenAI%20%7C%20Claude%20%7C%20Gemini%20%7C%20Ollama-orange?style=flat-square)](https://console.groq.com)
[![GIFs](https://img.shields.io/badge/GIFs-Giphy-yellow?style=flat-square)](https://developers.giphy.com)
[![Anki](https://img.shields.io/badge/export-.apkg-lightblue?style=flat-square)](https://apps.ankiweb.net)

**AI-generated flashcards for any language** · example sentences · IPA · audio · animated GIFs · synonyms · gender · POS tags · interactive terminal UI

[Quick Start](#quick-start) · [Interactive Menu](#interactive-menu) · [JavaScript TUI](#javascript-tui) · [Card Types](#card-types) · [Templates](#card-templates) · [Configuration](#configuration-reference) · [Daily Workflow](#daily-workflow) · [Roadmap](#roadmap)

---

## What each card contains

| Field | Description |
|---|---|
| **Word** | The target word (with POS label if multiple meanings) |
| **Gender** | ♂ Masculine / ♀ Feminine badge (nouns only) |
| **IPA** | Phonetic transcription |
| **Image** | Animated GIF contextually matched to the example sentence |
| **Text_Example_Phrase** | A natural example sentence (10–15 words) in the target language |
| **Text_Example_Translation** | Translation of the example sentence into your native language |
| **Text_Meaning** | Clear dictionary-style definition in your native language |
| **Synonyms** | Up to 6 synonyms as visual badges |
| **Sound_Word** | Audio pronunciation of the word |
| **Sound_Example** | Audio of the full example sentence |
| **Sound_Meaning** | Audio of the definition |

---

## Quick start

### 1. Clone the repository
```bash
git clone https://github.com/your-username/anki-vocabulary-deck.git
cd anki-vocabulary-deck
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

> **Windows only:** also run `pip install windows-curses` to enable the interactive menu.

### 4. Get your free API keys

Pick **one** AI provider (set via `AI_PROVIDER` in config.py, or in the Configure menu):

| Provider | Link | Free tier |
|---|---|---|
| **Groq** (default) | https://console.groq.com | 14,400 requests/day |
| **OpenAI** (ChatGPT) | https://platform.openai.com/api-keys | Pay-as-you-go |
| **Anthropic** (Claude) | https://console.anthropic.com/settings/keys | Pay-as-you-go |
| **Gemini** (Google) | https://aistudio.google.com/apikey | Free tier available |
| **Ollama** (local) | https://ollama.com — no API key, runs on your machine | Free, unlimited |

Plus GIFs:

| Service | Link | Free tier |
|---|---|---|
| **Giphy** (GIFs) | https://developers.giphy.com | 100 requests/hour |

> Using **Anthropic/Claude**? Also run `pip install anthropic` — it's an optional
> dependency not installed by `requirements.txt` by default.

### 5. Run
```bash
python main.py
```

The interactive menu opens. Go to **Configure → AI & API keys** to pick your provider and enter your keys directly in the terminal — no need to edit any file manually.

### 6. Generate cards and import into Anki

1. Select **Generate new cards** from the main menu.
2. When done, select **Export decks** and choose a card type.
3. Import `deck_new.apkg` into Anki.

**Always import `deck_new.apkg`** — it contains only new cards and never overwrites your manual edits inside Anki.

---

## Interactive menu

Run `python main.py` to open the arrow-key driven interface:

```
  Main Menu
  ─────────────────────────────────────────────
  ▶ Generate new cards        Up to 50 words from the frequency list
    Export decks               Build .apkg  —  choose card type before exporting
    Configure                  FR -> English
    Statistics                 Card counts, POS breakdown, export history
    Card type guide            Basic / Reversed / Type / Cloze
    ─────────────────────────────────────────────
    ← Exit
```

**Controls:**

| Key | Action |
|---|---|
| `↑` `↓` | Move between items |
| `←` `→` | Change value (pickers, numbers, toggles) |
| `Enter` | Activate / open / confirm |
| `Space` | Toggle boolean / cycle picker |
| `Esc` or `q` | Go back / exit |

### Configure menu

All settings can be changed without touching any file:

```
  Configure Settings
  ──────────────────────────────────────────
    Language          FR -> English
    AI & API keys     Groq
    Deck & cards      dark  |  basic
    Generation        50/run   pool 2000
    Audio             ON
    GIF               ON  |  rating: g
    Rate limits       AI 1.5s  Giphy 0.4s  TTS 0.3s
```

---

## JavaScript TUI

A second, JS-based interactive menu lives in `cli/` — same screens as the
Python curses menu above (Generate, Export, Configure, Statistics, Card type
guide), styled with [Lip Gloss](https://github.com/charmbracelet/lipgloss)
(via `@charmland/lipgloss`, Charm's own WASM build of the real Go library)
for a modern look — gradient title, breadcrumb navigation, no boxed ASCII
banner. It's a pure frontend: every action shells out to `main.py` under the
hood, so both menus always read and write the exact same `config.py` /
`progress.db`.

```
cd cli
npm install
node src/index.mjs
```

Requires Node.js ≥ 20.12 and `python3` on your `PATH` (set `PYTHON_BIN` to
point at a different interpreter, e.g. a venv's). Controls are the same as
the curses menu (`↑↓` navigate, `←→` change value, `Enter` select, `Esc`/`q`
back).

---

## Card types

Choose the Anki note type when exporting. The card type can be changed per-export from the Export menu, or set as the default in Configure → Deck & cards.

| Type | Description |
|---|---|
| **Basic** | Word on front, meaning on back. Classic recognition practice. |
| **Basic + Reversed** | Two cards per note — word→meaning and meaning→word. |
| **Type in Answer** | Definition shown; you type the foreign word. Anki checks your spelling. |
| **Cloze** | Example sentence with the target word blanked out. Fill in the gap. |

---

## Card templates

Controls the visual layout of your cards, independently of the card type.

| Template | Description |
|---|---|
| `dark` | Dark background with blue accents (Catppuccin Mocha palette) |
| `light` | Clean white with soft color accents |
| `minimal` | Text only — no GIF, no gender badge. Focus on language |
| `immersive` | GIF fills the card background with text overlay |

Change the template from **Configure → Deck & cards** in the menu, or edit `config.py` directly:
```python
CARD_TEMPLATE = "minimal"
```

---

## Daily workflow

```
python main.py  →  Generate  →  Export  →  import deck_new.apkg into Anki  →  repeat
```

Your progress is saved in `progress.db`. Words already processed are skipped automatically.

### Headless / cron mode

To generate and export without any menu (for automation or scheduled jobs):
```bash
python main.py --run
```

---

## Filtering cards by part of speech in Anki

Every card is automatically tagged by part of speech:
```
vocab::Noun
vocab::Verb
vocab::Adjective
...
```

Filter in Anki's Card Browser (`B`):
```
tag:vocab::Verb
```

Or create a Filtered Deck:
```
Browse → Create Filtered Deck → tag:vocab::Verb
```

---

## Supported languages

Any language supported by [wordfreq](https://github.com/rspeer/wordfreq).
Change the language from **Configure → Language** in the menu, or edit `config.py`:

```python
SOURCE_LANG     = "es"   # Spanish
TTS_SOURCE_LANG = "es"   # gTTS code for Spanish audio
TARGET_LANG     = "English"
```

Common codes: `fr` French · `es` Spanish · `de` German · `it` Italian · `pt` Portuguese · `ja` Japanese · `ko` Korean · `zh` Mandarin

---

## Configuration reference

All settings live in `config.py` and can also be changed at runtime from the **Configure** menu.

```python
AI_PROVIDER = "groq"           # groq | openai | anthropic | gemini | ollama

GROQ_API_KEY      = "..."      # Groq API key
OPENAI_API_KEY    = "..."      # OpenAI API key
ANTHROPIC_API_KEY = "..."      # Anthropic (Claude) API key
GEMINI_API_KEY    = "..."      # Google Gemini API key
GIPHY_API_KEY     = "..."      # Giphy API key

SOURCE_LANG      = "fr"        # language to learn (BCP-47 code)
TARGET_LANG      = "English"   # your native language
TTS_SOURCE_LANG  = "fr"        # gTTS code for source language audio
TTS_TARGET_LANG  = "en"        # gTTS code for native language audio

AI_MODEL        = "llama-3.3-70b-versatile"  # used when AI_PROVIDER = "groq"
OPENAI_MODEL    = "gpt-4o-mini"              # used when AI_PROVIDER = "openai"
ANTHROPIC_MODEL = "claude-haiku-4-5"         # used when AI_PROVIDER = "anthropic"
GEMINI_MODEL    = "gemini-2.0-flash"         # used when AI_PROVIDER = "gemini"
OLLAMA_MODEL    = "llama3.1"                 # used when AI_PROVIDER = "ollama"
OLLAMA_HOST     = "http://localhost:11434"   # local Ollama server address

WORDS_PER_RUN   = 50           # words processed per run
TOTAL_WORD_POOL = 2000         # total frequency pool size

CARD_TEMPLATE = "dark"         # dark | light | minimal | immersive
CARD_TYPE     = "basic"        # basic | basic_reversed | type_answer | cloze

ENABLE_AUDIO         = True    # master audio switch
ENABLE_WORD_AUDIO    = True
ENABLE_EXAMPLE_AUDIO = True
ENABLE_MEANING_AUDIO = True

ENABLE_GIF = True              # fetch animated GIFs from Giphy
GIF_RATING = "g"               # g | pg | pg-13 | r

DELAY_AI    = 1.5              # seconds between AI provider calls
DELAY_GIPHY = 0.4              # seconds between Giphy calls
DELAY_TTS   = 0.3              # seconds between gTTS calls
```

---

## Output files

| File | Description |
|---|---|
| `deck_new.apkg` | **Import this daily** — new cards only |
| `deck_full.apkg` | Full backup of all cards ever generated |
| `progress.db` | SQLite database tracking all processed words |
| `audio_files/` | Generated MP3 files (embedded in the .apkg) |

---

## API key security

**Never commit your real API keys to GitHub.**
`config.py` is not in `.gitignore` so your settings are preserved locally —
replace your keys with placeholder values before pushing:

```python
GROQ_API_KEY      = "your_groq_api_key_here"
OPENAI_API_KEY    = "your_openai_api_key_here"
ANTHROPIC_API_KEY = "your_anthropic_api_key_here"
GEMINI_API_KEY    = "your_gemini_api_key_here"
GIPHY_API_KEY     = "your_giphy_api_key_here"
```

---

## Roadmap

Future goals for this project. Completed items are struck through.

- [ ] Add multiple realistic AI-generated voices, produced **locally** (no cloud TTS dependency)
- [x] ~~Add a beautiful interactive menu (TUI) built with JavaScript~~ — see [JavaScript TUI](#javascript-tui)
- [x] ~~Include more templates for cards~~ — 4 available: dark, light, minimal, immersive
- [ ] Categorize cards into language-specific subfolders/subdecks (e.g. "Phrasal Verbs", "Verb Conjugation" for English) and track the category in Anki tags

---

## License

MIT — free to use, modify, and share.
