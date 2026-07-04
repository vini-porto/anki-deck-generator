# =============================================================
#  config.py — All user-configurable settings
#  Edit this file before running the script.
# =============================================================


# ─────────────────────────────────────────────────────────────
#  API KEYS
#  Get your free keys at:
#    Groq  : https://console.groq.com
#    Giphy : https://developers.giphy.com
# ─────────────────────────────────────────────────────────────

GROQ_API_KEY  = "your_groq_api_key_here"
GIPHY_API_KEY = "your_giphy_api_key_here"


# ─────────────────────────────────────────────────────────────
#  AI MODEL
#  Groq free-tier models (pick one):
#    "llama-3.3-70b-versatile"  — best quality  (recommended)
#    "llama-3.1-8b-instant"     — faster, lighter
#    "gemma2-9b-it"             — Google Gemma 2
#    "mixtral-8x7b-32768"       — Mixtral
# ─────────────────────────────────────────────────────────────

AI_MODEL = "llama-3.3-70b-versatile"


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
# ─────────────────────────────────────────────────────────────

WORDS_PER_RUN   = 50
TOTAL_WORD_POOL = 2000


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
#  AUDIO
#  ENABLE_AUDIO        : set False to skip all audio generation
#                        (faster runs, smaller .apkg files)
#  ENABLE_WORD_AUDIO   : audio for the word alone
#  ENABLE_EXAMPLE_AUDIO: audio for the example sentence
#  ENABLE_MEANING_AUDIO: audio for the English meaning
# ─────────────────────────────────────────────────────────────

ENABLE_AUDIO         = True
ENABLE_WORD_AUDIO    = True
ENABLE_EXAMPLE_AUDIO = True
ENABLE_MEANING_AUDIO = True


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

DELAY_AI    = 1.5   # between Groq calls
DELAY_GIPHY = 0.4   # between Giphy calls
DELAY_TTS   = 0.3   # between gTTS calls
