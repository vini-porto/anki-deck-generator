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
[![AI](https://img.shields.io/badge/AI-Groq%20%2F%20LLaMA--3-orange?style=flat-square)](https://console.groq.com)
[![GIFs](https://img.shields.io/badge/GIFs-Giphy-yellow?style=flat-square)](https://developers.giphy.com)
[![Anki](https://img.shields.io/badge/export-.apkg-lightblue?style=flat-square)](https://apps.ankiweb.net)

**AI-generated flashcards for any language** · example sentences · IPA · audio · animated GIFs · synonyms · gender · POS tags · interactive terminal UI

[Quick Start](#quick-start) · [Interactive Menu](#interactive-menu) · [Card Types](#card-types) · [Templates](#card-templates) · [Configuration](#configuration-reference) · [Daily Workflow](#daily-workflow)

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

| Service | Link | Free tier |
|---|---|---|
| **Groq** (AI) | https://console.groq.com | 14,400 requests/day |
| **Giphy** (GIFs) | https://developers.giphy.com | 100 requests/hour |

### 5. Run
```bash
python main.py
```

The interactive menu opens. Go to **Configure → AI & API keys** to enter your keys directly in the terminal — no need to edit any file manually.

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
    AI & API keys     OK
    Deck & cards      dark  |  basic
    Generation        50/run   pool 2000
    Audio             ON
    GIF               ON  |  rating: g
    Rate limits       AI 1.5s  Giphy 0.4s  TTS 0.3s
```

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
GROQ_API_KEY  = "..."          # Groq API key
GIPHY_API_KEY = "..."          # Giphy API key

SOURCE_LANG      = "fr"        # language to learn (BCP-47 code)
TARGET_LANG      = "English"   # your native language
TTS_SOURCE_LANG  = "fr"        # gTTS code for source language audio
TTS_TARGET_LANG  = "en"        # gTTS code for native language audio

AI_MODEL = "llama-3.3-70b-versatile"   # Groq model

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

DELAY_AI    = 1.5              # seconds between Groq calls
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
GROQ_API_KEY  = "your_groq_api_key_here"
GIPHY_API_KEY = "your_giphy_api_key_here"
```

---

## License

MIT — free to use, modify, and share.
