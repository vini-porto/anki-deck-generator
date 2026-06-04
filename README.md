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

**AI-generated flashcards for any language** · example sentences · IPA · audio · animated GIFs · synonyms · gender · POS tags

[Quick Start](#quick-start) · [Configuration](#configuration-reference) · [Templates](#card-templates) · [Daily Workflow](#daily-workflow)

---

## What each card contains

| Field | Description |
|---|---|
| **Word** | The target word (with POS label if multiple meanings) |
| **Gender** | ♂ Masculine / ♀ Feminine badge (nouns only) |
| **IPA** | Phonetic transcription |
| **Image** | Animated GIF contextually matched to the example sentence |
| **Text_Example_Phrase** | A natural example sentence (10–15 words) in the target language |
| **Text_Example_Translation** | English translation of the example sentence |
| **Text_Meaning** | Clear dictionary-style definition in English |
| **Synonyms** | Up to 6 synonyms as visual badges |
| **Sound_Word** | Audio pronunciation of the word |
| **Sound_Example** | Audio of the full example sentence |
| **Sound_Meaning** | Audio of the English definition |

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

### 4. Get your free API keys

| Service | Link | Free tier |
|---|---|---|
| **Groq** (AI) | https://console.groq.com | 14,400 requests/day |
| **Giphy** (GIFs) | https://developers.giphy.com | 100 requests/hour |

### 5. Configure
Open `config.py` and fill in your keys and preferences:

```python
GROQ_API_KEY  = "your_groq_api_key_here"
GIPHY_API_KEY = "your_giphy_api_key_here"

SOURCE_LANG  = "fr"       # language to learn
TARGET_LANG  = "English"  # your native language

WORDS_PER_RUN   = 50      # new words to add today
TOTAL_WORD_POOL = 2000    # total vocabulary pool size

CARD_TEMPLATE = "dark"    # dark | light | minimal | immersive
```

### 6. Run
```bash
python main.py
```

### 7. Import into Anki
Import `deck_new.apkg` into Anki.
**Always import this file** — it only contains new cards and will never overwrite your manual edits.

---

## Daily workflow

```
python main.py  →  import deck_new.apkg into Anki  →  repeat tomorrow
```

Your progress is saved in `progress.db`. Words already processed are skipped automatically.

---

## Card templates

| Template | Description |
|---|---|
| `dark` | Dark background with blue accents (Catppuccin Mocha palette) |
| `light` | Clean white with soft color accents |
| `minimal` | Text only — no GIF, no gender badge. Focus on language |
| `immersive` | GIF fills the card background with text overlay |

Change the template in `config.py`:
```python
CARD_TEMPLATE = "minimal"
```

---

## Filtering cards by category in Anki

Every card is automatically tagged by part of speech:
```
vocab::Noun
vocab::Verb
vocab::Adjective
...
```

In Anki's Card Browser (`B`), filter by tag:
```
tag:vocab::Verb
```

Or create a Filtered Deck with only verbs:
```
Browse → Create Filtered Deck → tag:vocab::Verb
```

---

## Supported languages

Any language supported by [wordfreq](https://github.com/rspeer/wordfreq).
Change `SOURCE_LANG` in `config.py` to switch languages:

```python
SOURCE_LANG     = "es"   # Spanish
TTS_SOURCE_LANG = "es"   # gTTS code for Spanish audio
```

Common codes: `fr` French · `es` Spanish · `de` German · `it` Italian · `pt` Portuguese · `ja` Japanese · `ko` Korean · `zh` Mandarin

---

## Configuration reference

All settings are in `config.py`. Key options:

```python
# How many words to process per run (adjust daily)
WORDS_PER_RUN = 50

# Total vocabulary pool — increase when exhausted
TOTAL_WORD_POOL = 2000

# AI model (Groq free tier)
AI_MODEL = "llama-3.3-70b-versatile"

# Disable GIFs for faster/offline runs
ENABLE_GIF = False

# Disable individual audio tracks
ENABLE_WORD_AUDIO    = True
ENABLE_EXAMPLE_AUDIO = True
ENABLE_MEANING_AUDIO = False
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

## ⚠️ API key security

**Never commit your real API keys to GitHub.**
`config.py` is not in `.gitignore` so your settings are preserved locally,
but make sure to replace your keys with placeholder values before pushing:

```python
GROQ_API_KEY  = "your_groq_api_key_here"
GIPHY_API_KEY = "your_giphy_api_key_here"
```

---

## License

MIT — free to use, modify, and share.
