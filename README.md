```
  █████╗ ███╗   ██╗██╗  ██╗██╗    ██████╗ ███████╗ ██████╗██╗  ██╗
 ██╔══██╗████╗  ██║██║ ██╔╝██║    ██╔══██╗██╔════╝██╔════╝██║ ██╔╝
 ███████║██╔██╗ ██║█████╔╝ ██║    ██║  ██║█████╗  ██║     █████╔╝ 
 ██╔══██║██║╚██╗██║██╔═██╗ ██║    ██║  ██║██╔══╝  ██║     ██╔═██╗ 
 ██║  ██║██║ ╚████║██║  ██╗██║    ██████╔╝███████╗╚██████╗██║  ██╗
 ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝    ╚═════╝ ╚══════╝ ╚═════╝╚═╝  ╚═╝
            AI-powered Anki flashcard deck generator
```

[![Version](https://img.shields.io/badge/version-2.5.0-blueviolet?style=flat-square)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![AI](https://img.shields.io/badge/AI-Groq%20%7C%20OpenAI%20%7C%20Claude%20%7C%20Gemini%20%7C%20Ollama-orange?style=flat-square)](https://console.groq.com)
[![GIFs](https://img.shields.io/badge/GIFs-Giphy-yellow?style=flat-square)](https://developers.giphy.com)
[![Anki](https://img.shields.io/badge/export-.apkg-lightblue?style=flat-square)](https://apps.ankiweb.net)

**AI-generated flashcards for any language** · example sentences · IPA · audio · animated GIFs · synonyms · gender · POS tags · interactive terminal UI

[Quick Start](#quick-start) · [Interactive Menu](#interactive-menu) · [Card Types](#card-types) · [Templates](#card-templates) · [Categories & Subdecks](#categories--subdecks) · [Local TTS](#local-tts-pocket-tts) · [Configuration](#configuration-reference) · [Daily Workflow](#daily-workflow) · [Roadmap](#roadmap)

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

> Want **local, offline audio** instead of gTTS? Set `TTS_PROVIDER = "pocket_tts"`
> and run `pip install pocket-tts` — see [Local TTS (Pocket TTS)](#local-tts-pocket-tts).

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
for a modern look inspired by Lip Gloss's own showcase demo: a solid violet
title banner in bold white text, breadcrumb navigation on a dark status bar,
a hot-pink caret chip and highlight band marking the focused row, and footer
key hints rendered as small colored badges instead of plain text. It's a
pure frontend: every action shells out to `main.py` under the hood, so both
menus always read and write the exact same `config.py` / `progress.db`.

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

## Creation modes

Controls *what* the AI is asked to generate and what becomes the card's front
(stimulus) vs. back (answer) — a third axis independent of card type
(mechanics, above) and card template (visuals, below). Stored as
`CREATION_MODE` (+ `CARD_TYPE` for the Word-based family) in config.py, but
both interactive menus present it as one screen under
**Configure → Card content** with 4 pickers instead of a flat list of named
styles — pick **Content**, **Front**, **Back**, and **Card type** directly,
and each picker's choices narrow to whatever combination makes sense given
the ones before it:

| Content | Front | Back | Card type |
|---|---|---|---|
| Word | The word (text) | Meaning | Basic / Basic + Reversed / Type in Answer / Cloze |
| Word | The word's audio | Meaning | Basic |
| Word | The word's audio | Word (spelling) | Basic / Type in Answer |
| Phrase | A natural phrase, word highlighted (text) | Meaning + translation | Basic |
| Phrase | The same phrase, audio only | Meaning + translation | Basic |
| Phrase | The same phrase, audio only | Phrase (spelling) | Type in Answer |
| Phrase | A phrase in your native language | Translation | Type in Answer |

"Type in Answer" adds a typed input box to the Front that Anki auto-checks
against the Back field letter-for-letter; "Basic" is a flip-and-self-grade
card; "Basic + Reversed" builds two cards per note (Front→Back and
Back→Front); "Cloze" blanks the anchor word out of the example sentence
(Word content only — every Phrase combination has a single fixed Card type,
since basic_reversed/cloze aren't built for phrase content). Every mode
still centers on one anchor word, so part-of-speech tags and category
subdecks keep working the same way no matter which combination generated
the card.

Every combination except the first row (Word/text/Meaning, i.e. `CARD_TYPE`'s
basic/basic_reversed/type_answer/cloze variants) also respects
`CREATION_MODE_VERBOSITY` (Configure → Card content):

- **Complete** (default) — every applicable field is filled in (IPA,
  gender, synonyms, and — where relevant — the full example/translation)
- **Simple** — only the essential field(s) for that style, everything else
  omitted (and, since the omitted text is never generated, no wasted TTS
  calls for audio that would never be shown)

---

## Word sources

Controls *where candidate words come from* — independent of creation mode
(above), which controls what happens to a word once it's picked. Set via
`WORD_SOURCE` in config.py, or Configure → Generation in either interactive
menu.

| Source | Behavior |
|---|---|
| **Frequency word list** (default) | Top `TOTAL_WORD_POOL` most-frequent words for `SOURCE_LANG`, via `wordfreq` |
| **Markdown notes / Obsidian vault** | Scans `MARKDOWN_NOTES_PATH` recursively for `*.md` files and builds the pool from those instead — useful if you already keep reading/vocabulary notes in Obsidian or a similar app and want cards built from words you've actually encountered, not a generic corpus |

When using markdown notes, `MARKDOWN_EXTRACTION_MODE` controls how words are
pulled out of your notes:

- **Highlights** (recommended, default) — only text wrapped in Obsidian's
  `==highlight==` syntax. High-signal: you already chose which words matter.
- **All words** — every word in your notes, ranked by how often it appears.
  Noisier — with no curation, common function words ("de", "le", "que"...)
  tend to dominate, since a personal-notes corpus isn't curated the way
  `wordfreq`'s frequency corpus is.

`TOTAL_WORD_POOL` still caps the pool size in either mode.

**Known limitation**: there is no lemmatization/stemming. A conjugated verb
or plural noun found in your notes is treated as its own distinct word from
its dictionary form (e.g. "mangera" won't be recognized as "manger").

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

## Categories & subdecks

Many languages have study "blocks" that don't map to part of speech at all,
and vary from language to language — English learners often study **Phrasal
Verbs** or **Verb Conjugation** as their own topic, for example. When
`ENABLE_CATEGORIES` is on (default), the AI may tag a meaning with one of
these language-specific categories, and the card is then organized **two
ways** in Anki:

- **Subdeck** — filed into `<Deck Name>::<Category>`, e.g.
  `French Vocabulary::Phrasal Verbs`, alongside the regular deck.
- **Tag** — `topic::<Category>` (e.g. `topic::Phrasal_Verbs`), so you can
  filter or build Filtered Decks the same way as with `vocab::<POS>` tags.

Plain vocabulary that doesn't fit a special category is left uncategorized
and stays in the root deck — categories only appear when they're genuinely
useful. Categories are **registered and reused**: once the AI introduces
"Phrasal Verbs" for a deck, later runs are told about it and reuse the exact
same name instead of coining near-duplicates like "Phrasal Verb" or "Verbs +
Prepositions".

Turn it off from **Configure → Deck & cards → Category subdecks & tags**, or
set `ENABLE_CATEGORIES = False` in config.py — cards then only go in the root
deck, with no `topic::` tag.

---

## Local TTS (Pocket TTS)

By default, audio is generated via **gTTS** — a free cloud API with one
generic voice per language. As a local, offline alternative, you can switch
to [Pocket TTS](https://github.com/kyutai-labs/pocket-tts) (Kyutai Labs), a
CPU-only engine with multiple realistic AI-generated voices:

```bash
pip install pocket-tts
```

```python
TTS_PROVIDER             = "pocket_tts"  # "gtts" | "pocket_tts"
POCKET_TTS_VOICE_SOURCE  = "alba"        # voice for word + example audio
POCKET_TTS_VOICE_TARGET  = "alba"        # voice for meaning audio
POCKET_TTS_QUANTIZE      = False         # less RAM, faster, no quality loss
```

Or from the menu: **Configure → Audio → TTS provider → Pocket TTS settings**.

**Things to know:**
- Runs entirely on CPU — no GPU, no API key, no per-request network call.
- The **first** time a language is used, its model weights are downloaded
  from Hugging Face and cached in `~/.cache/pocket_tts/` — that's the only
  network access; every run after that is fully offline.
- Only ships models for **English, French, German, Italian, Portuguese, and
  Spanish**. If `TTS_SOURCE_LANG`/`TTS_TARGET_LANG` is anything else (e.g.
  Japanese, Russian), that field automatically falls back to gTTS with a
  one-time `[WARN]` — the rest keeps using Pocket TTS.
- English has 21 voices to choose from; every other supported language
  currently ships exactly one.

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
GEMINI_MODEL    = "gemini-3.5-flash-lite"    # used when AI_PROVIDER = "gemini" (free tier shifts often)
OLLAMA_MODEL    = "llama3.1"                 # used when AI_PROVIDER = "ollama"
OLLAMA_HOST     = "http://localhost:11434"   # local Ollama server address

WORDS_PER_RUN   = 50           # words processed per run
TOTAL_WORD_POOL = 2000         # total pool size (either word source)
MEANING_EXHAUSTIVENESS = "important"  # essential | important | all — meanings (cards) per word

WORD_SOURCE             = "frequency_list"  # frequency_list | markdown_notes — see Word sources
MARKDOWN_NOTES_PATH     = ""                # folder scanned recursively for *.md files
MARKDOWN_EXTRACTION_MODE = "highlights"     # highlights | all_words

CARD_TEMPLATE = "dark"         # dark | light | minimal | immersive
CARD_TYPE     = "basic"        # basic | basic_reversed | type_answer | cloze — Word-based cards only
CREATION_MODE = "word_meaning" # word_meaning | phrase_context | audio_meaning | audio_writing |
                                # audio_typing | phrase_native_writing | phrase_audio_recognition |
                                # phrase_audio_typing
CREATION_MODE_VERBOSITY = "complete"  # complete | simple — audio/production styles only
# Both settings above are best edited via Configure -> Card content in
# either interactive menu (a guided flow), not by hand — see Creation modes.

ENABLE_CATEGORIES = True       # AI-tagged subdecks + topic:: tags (e.g. "Phrasal Verbs")

ENABLE_AUDIO         = True    # master audio switch
ENABLE_WORD_AUDIO    = True
ENABLE_EXAMPLE_AUDIO = True
ENABLE_MEANING_AUDIO = True

TTS_PROVIDER            = "gtts"   # gtts | pocket_tts (local — see Local TTS)
POCKET_TTS_VOICE_SOURCE = "alba"   # voice for word + example audio
POCKET_TTS_VOICE_TARGET = "alba"   # voice for meaning audio
POCKET_TTS_QUANTIZE     = False    # less RAM, faster, no quality loss

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
| `audio_files/` | Generated audio files (MP3 via gTTS, WAV via Pocket TTS — embedded in the .apkg) |

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

Future goals for this project.

- [ ] Add [AnkiConnect](https://ankiweb.net/shared/info/2055492159) support to export/import cards directly into a running Anki instance, without producing a `.apkg` file first — offered **alongside** the existing `.apkg` export, not replacing it
- [ ] Pass the *actual sentence* a markdown-sourced word was found in through to the AI prompt as authentic context, instead of discarding it once the word pool is built — would let **Phrase in Context** reuse the user's real example sentence instead of an AI-invented one

---

## License

MIT — free to use, modify, and share.
