# =============================================================
#  config.py — All user-configurable settings
#  Edit this file before running the script.
# =============================================================


# ─────────────────────────────────────────────────────────────
#  AI PROVIDER
#  Which AI service generates flashcard content. Only the
#  API key and model belonging to the chosen provider are used.
#    "groq"      — free tier, Llama / Gemma / Mixtral  (default)
#    "openai"    — ChatGPT / GPT models
#    "anthropic" — Claude models
#    "gemini"    — Google Gemini
#    "ollama"    — runs locally, no API key or internet required
# ─────────────────────────────────────────────────────────────

AI_PROVIDER = "groq"


# ─────────────────────────────────────────────────────────────
#  API KEYS
#  Get your free keys at:
#    Groq      : https://console.groq.com
#    OpenAI    : https://platform.openai.com/api-keys
#    Anthropic : https://console.anthropic.com/settings/keys
#    Gemini    : https://aistudio.google.com/apikey
#    Giphy     : https://developers.giphy.com
#  Ollama runs locally — no key needed, see OLLAMA_HOST below.
# ─────────────────────────────────────────────────────────────

GROQ_API_KEY      = "your_groq_api_key_here"
OPENAI_API_KEY    = "your_openai_api_key_here"
ANTHROPIC_API_KEY = "your_anthropic_api_key_here"
GEMINI_API_KEY    = "your_gemini_api_key_here"
GIPHY_API_KEY     = "your_giphy_api_key_here"


# ─────────────────────────────────────────────────────────────
#  AI MODELS
#  Only the model belonging to the active AI_PROVIDER is used.
#
#  Groq free-tier models (pick one):
#    "llama-3.3-70b-versatile"  — best quality  (recommended)
#    "llama-3.1-8b-instant"     — faster, lighter
#    "gemma2-9b-it"             — Google Gemma 2
#    "mixtral-8x7b-32768"       — Mixtral
# ─────────────────────────────────────────────────────────────

AI_MODEL        = "llama-3.3-70b-versatile"  # used when AI_PROVIDER = "groq"
OPENAI_MODEL    = "gpt-4o-mini"              # used when AI_PROVIDER = "openai"
ANTHROPIC_MODEL = "claude-haiku-4-5"         # used when AI_PROVIDER = "anthropic"
# Google's free tier drops/adds model access periodically, and per-model
# request-per-day caps vary a lot even within the same "Flash Lite" tier —
# gemini-2.5-flash-lite is capped at a mere 20 RPD on the free tier (that's
# what caused rate-limit errors after ~20 cards), while gemini-3.5-flash-lite
# offers 500 RPD / 15 RPM for the same "lite" cost tier, which is what makes
# a real 500-cards/day workflow possible. If this ever 404s (model retired)
# or shows 0 free-tier quota, check your account's usage/quota dashboard —
# gemini-3.1-flash-lite has the identical 500 RPD / 15 RPM ceiling and is a
# safe same-tier fallback.
GEMINI_MODEL    = "gemini-3.5-flash-lite"    # used when AI_PROVIDER = "gemini"
OLLAMA_MODEL    = "llama3.1"                 # used when AI_PROVIDER = "ollama"
OLLAMA_HOST     = "http://localhost:11434"   # Ollama server address


# ─────────────────────────────────────────────────────────────
#  LANGUAGE SETTINGS
#  SOURCE_LANG : language to learn (BCP-47 code used by wordfreq)
#  TARGET_LANG : your native language for translations/definitions
#  TTS_LANG    : language code for gTTS audio generation
#
#  Common source language codes:
#    French   → "fr"   |  Spanish  → "es"   |  German   → "de"
#    Italian  → "it"   |  Japanese → "ja"   |  Mandarin → "zh"
#    Portuguese→ "pt"  |  Korean   → "ko"   |  Russian  → "ru"
# ─────────────────────────────────────────────────────────────

SOURCE_LANG      = "fr"       # language you are learning
TARGET_LANG      = "English"  # your native language (used in AI prompt)
TTS_SOURCE_LANG  = "fr"       # gTTS code for the source language audio
TTS_TARGET_LANG  = "en"       # gTTS code for the target language audio


# ─────────────────────────────────────────────────────────────
#  DECK GENERATION
#  WORDS_PER_RUN  : how many new words to process each time you
#                   run the script. Adjust daily as needed.
#  TOTAL_WORD_POOL: total number of most-frequent words to draw
#                   from. When exhausted, increase this number.
#  MEANING_EXHAUSTIVENESS: how many distinct meanings the AI generates
#                   per word (one card is made per meaning):
#                     "essential" — only the single most essential meaning
#                     "important" — the handful of most useful ones (default)
#                     "all"       — every genuinely distinct meaning, up to
#                                   a higher cap (uses a bigger AI token
#                                   budget so it doesn't truncate mid-response)
# ─────────────────────────────────────────────────────────────

WORDS_PER_RUN   = 50
TOTAL_WORD_POOL = 2000
MEANING_EXHAUSTIVENESS = "important"   # "essential" | "important" | "all"


# ─────────────────────────────────────────────────────────────
#  WORD SOURCE
#  Where candidate words come from.
#    "frequency_list" — top TOTAL_WORD_POOL most-frequent SOURCE_LANG
#                        words, via wordfreq (default)
#    "markdown_notes"  — scan MARKDOWN_NOTES_PATH for *.md files (e.g. an
#                        Obsidian vault) and build the pool from those
#                        instead. TOTAL_WORD_POOL still caps the result.
#  MARKDOWN_EXTRACTION_MODE (only used when WORD_SOURCE = "markdown_notes"):
#    "highlights" — only text wrapped in ==highlight== syntax (recommended:
#                    high-signal, avoids common function words dominating)
#    "all_words"  — every word in the notes, ranked by how often it appears
#  Note: there is no lemmatization — a conjugated/plural form found in your
#  notes is treated as its own distinct word from its dictionary form.
# ─────────────────────────────────────────────────────────────

WORD_SOURCE               = "frequency_list"  # "frequency_list" | "markdown_notes"
MARKDOWN_NOTES_PATH        = ""                # folder scanned recursively for *.md files
MARKDOWN_EXTRACTION_MODE   = "highlights"     # "highlights" | "all_words"


# ─────────────────────────────────────────────────────────────
#  CARD TEMPLATE
#  Choose the visual layout for your Anki cards.
#  Available templates (see /templates folder for previews):
#
#    "dark"       — Dark background, blue accents (default)
#    "light"      — Clean white, minimal design
#    "minimal"    — No GIF, no gender badge, focus on text
#    "immersive"  — GIF as full card background, text overlay
# ─────────────────────────────────────────────────────────────

CARD_TEMPLATE = "dark"


# ─────────────────────────────────────────────────────────────
#  CARD TYPE
#  Controls the Anki note type used when exporting .apkg files.
#  This is independent of CARD_TEMPLATE (which controls styling).
#
#    "basic"          — classic word-to-meaning card (default)
#    "basic_reversed" — 2 cards per note: word→meaning + meaning→word
#    "type_answer"    — front shows the definition; user types the word
#    "cloze"          — fill-in-the-blank using example sentences
# ─────────────────────────────────────────────────────────────

CARD_TYPE = "basic"


# ─────────────────────────────────────────────────────────────
#  CREATION MODE
#  Controls WHAT the AI is asked to generate and what serves as the Anki
#  card's Front (stimulus) vs Back (answer). Independent of CARD_TEMPLATE
#  (visual styling). CARD_TYPE (note mechanics: basic/basic_reversed/
#  type_answer/cloze) only applies when CREATION_MODE = "word_meaning" —
#  every other mode ships its own single fixed note shape (own Anki note
#  type), and the CARD_TYPE picker has no effect while a different mode
#  is active.
#
#    "word_meaning"          — classic word -> meaning/definition (default)
#    "phrase_context"        — a natural phrase using the word; recall its
#                               meaning from context (word highlighted on front)
#    "audio_meaning"         — hear the word; recall its meaning
#    "audio_writing"         — hear the word; reveal its written form/spelling
#    "audio_typing"          — hear the word; type what you heard (auto-checked)
#    "phrase_native_writing" — a phrase in your native language on the front;
#                               its correct written translation on the back
# ─────────────────────────────────────────────────────────────

CREATION_MODE = "word_meaning"

# CREATION_MODE_VERBOSITY only affects the 4 audio/production modes above
# (audio_meaning, audio_writing, audio_typing, phrase_native_writing) —
# word_meaning and phrase_context are unaffected and always show every field.
#    "complete" — every applicable field is filled in (default)
#    "simple"   — only the essential field(s) for that mode
CREATION_MODE_VERBOSITY = "complete"


# ─────────────────────────────────────────────────────────────
#  CATEGORIES / SUBDECKS
#  Some languages have distinct study "blocks" beyond part of speech —
#  e.g. English "Phrasal Verbs" or "Verb Conjugation". When enabled, the AI
#  may tag a meaning with a short category label, which is then used to:
#    - file the card into a "<DECK_NAME>::<Category>" subdeck in Anki
#    - add a "topic::<Category>" tag alongside the existing vocab::<POS> tag
#  Categories are language-specific and open-ended (not a fixed list) —
#  new ones are only introduced when a meaning doesn't fit an existing one,
#  and existing categories already in progress.db are reused by name.
#  Set to False to disable — cards then only ever go in the root deck.
# ─────────────────────────────────────────────────────────────

ENABLE_CATEGORIES = True


# ─────────────────────────────────────────────────────────────
#  AUDIO
#  ENABLE_AUDIO        : set False to skip all audio generation
#                        (faster runs, smaller .apkg files)
#  ENABLE_WORD_AUDIO   : audio for the word alone
#  ENABLE_EXAMPLE_AUDIO: audio for the example sentence
#  ENABLE_MEANING_AUDIO: audio for the English meaning
#
#  TTS_PROVIDER : "gtts" (cloud, one voice per language, default) or
#                 "pocket_tts" (local/CPU, multiple realistic voices —
#                 https://github.com/kyutai-labs/pocket-tts, requires
#                 `pip install pocket-tts`). Pocket TTS only ships models
#                 for English/French/German/Italian/Portuguese/Spanish —
#                 any other TTS_SOURCE_LANG/TTS_TARGET_LANG falls back to
#                 gTTS automatically. See CLAUDE.md § Local TTS provider.
#  POCKET_TTS_VOICE_SOURCE/TARGET : voice name used for that language slot.
#                 Only English has a wide voice catalog — other languages
#                 currently ship exactly one voice each.
#  POCKET_TTS_QUANTIZE : int8 quantization — less RAM, faster, no quality
#                 loss (needs `pip install pocket-tts[quantize]`).
# ─────────────────────────────────────────────────────────────

ENABLE_AUDIO         = True
ENABLE_WORD_AUDIO    = True
ENABLE_EXAMPLE_AUDIO = True
ENABLE_MEANING_AUDIO = True

TTS_PROVIDER             = "gtts"   # "gtts" | "pocket_tts"
POCKET_TTS_VOICE_SOURCE  = "alba"   # voice for word + example audio (TTS_SOURCE_LANG)
POCKET_TTS_VOICE_TARGET  = "alba"   # voice for meaning audio (TTS_TARGET_LANG)
POCKET_TTS_QUANTIZE      = False


# ─────────────────────────────────────────────────────────────
#  GIF SETTINGS
#  ENABLE_GIF  : set False to disable Giphy entirely
#  GIF_RATING  : content safety filter
#                "g" = family-friendly (recommended)
#                "pg", "pg-13", "r" = progressively less strict
# ─────────────────────────────────────────────────────────────

ENABLE_GIF  = True
GIF_RATING  = "g"


# ─────────────────────────────────────────────────────────────
#  OUTPUT FILES
# ─────────────────────────────────────────────────────────────

DECK_NAME        = "French Vocabulary"   # name shown inside Anki
DECK_OUTPUT_NEW  = "deck_new.apkg"       # import this into Anki daily
DECK_OUTPUT_FULL = "deck_full.apkg"      # full backup — all cards
DB_PATH          = "progress.db"
AUDIO_DIR        = "audio_files"


# ─────────────────────────────────────────────────────────────
#  ANKI IDs
#  These must remain stable after your first run.
#  Do NOT change them once you have imported cards into Anki.
# ─────────────────────────────────────────────────────────────

DECK_ID  = 1234567890
MODEL_ID = 9876543212


# ─────────────────────────────────────────────────────────────
#  RATE LIMITING
#  Delays (in seconds) between API calls to avoid hitting
#  free-tier rate limits.
# ─────────────────────────────────────────────────────────────

DELAY_AI    = 1.5   # between AI provider calls
DELAY_GIPHY = 0.4   # between Giphy calls
DELAY_TTS   = 0.3   # between gTTS calls
