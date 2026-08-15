# =============================================================
#  templates/immersive.py
#  Immersive template — high-contrast dark styling with a large,
#  framed GIF. Field visibility/position/order is entirely
#  user-controlled (see Card fields checklist).
# =============================================================

NAME = "immersive"

CSS = """
/* ── Base ── */
.card {
    font-family: 'Segoe UI', Arial, sans-serif;
    background-color: #0f0f0f;
    color: #f0f0f0;
    text-align: center;
    padding: 20px 20px 24px;
    line-height: 1.65;
    font-size: 17px;
}

/* ── GIF, large framed treatment ── */
.gif-hero {
    width: 100%;
    margin: 0 -20px;
    padding: 0 20px 4px;
}
.gif-hero img {
    width: 100%;
    max-width: 100% !important;
    max-height: 260px !important;
    object-fit: cover;
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}

/* ── Word ── */
.word {
    font-size: 36px;
    font-weight: 800;
    color: #ffffff;
    text-shadow: 0 2px 12px rgba(0,0,0,0.8);
    margin-bottom: 2px;
    letter-spacing: 1px;
}

/* ── IPA ── */
.ipa {
    font-size: 15px;
    color: rgba(255,255,255,0.6);
    font-style: italic;
    margin-bottom: 8px;
}

/* ── Gender badge ── */
.gender-badge {
    display: inline-block;
    font-size: 12px;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 10px;
    margin-bottom: 8px;
    backdrop-filter: blur(4px);
}
.gender-m { background: rgba(37,99,235,0.5); color: #bfdbfe; border: 1px solid #60a5fa55; }
.gender-f { background: rgba(157,23,77,0.5);  color: #fbcfe8; border: 1px solid #f472b655; }

/* ── Example sentence ── */
.example {
    font-size: 19px;
    color: #e2e8f0;
    background: #1a1a2e;
    border-left: 4px solid #60a5fa;
    border-radius: 6px;
    padding: 10px 16px;
    margin: 14px 0 4px 0;
    text-align: left;
}
.example .highlight {
    font-style: italic;
    font-weight: 700;
    color: #7dd3fc;
}

/* ── Example translation ── */
.example-translation {
    font-size: 14px;
    color: #64748b;
    font-style: italic;
    text-align: left;
    margin: 0 0 12px 0;
    padding: 5px 16px;
}

/* ── Divider ── */
hr { border: none; border-top: 1px solid #1e293b; margin: 14px 0; }

/* ── Meaning ── */
.meaning {
    font-size: 17px;
    color: #86efac;
    text-align: left;
    margin: 10px 0;
    padding: 8px 14px;
    background: #0f1f0f;
    border-radius: 6px;
}

/* ── Synonyms ── */
.synonyms-wrap {
    margin-top: 14px;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 6px;
}
.syn-badge {
    background: #1e1b4b;
    color: #c4b5fd;
    border-radius: 14px;
    padding: 3px 12px;
    font-size: 13px;
    border: 1px solid #4c1d9544;
}
"""

# Per-field HTML fragments, assembled dynamically at export time by
# _assemble_side() (main.py) — see CLAUDE.md § Card fields / template/dark.py.
# Earlier versions of this template used a JS-injected full-bleed
# background image (a separate "Image_Raw" field + a <script> that swapped
# it in) — dropped once field position/order became user-configurable,
# since a Model's declared field set must stay identical across every
# interaction (reveal/type_in/cloze) a user might pick, and a hero
# background sized for one fixed layout doesn't compose with that. The
# large framed .gif-hero image (below) keeps a distinct, high-visual-impact
# look using the same plain {{Image}} field every other template uses.
FIELD_HTML = {
    "word":                     '{{#Word}}<div class="word">{{Word}}</div>{{/Word}}',
    "gender":                   '{{Gender}}',
    "ipa":                      '{{#IPA}}<div class="ipa">/ {{IPA}} /</div>{{/IPA}}',
    "audio_word":               '{{Sound_Word}}',
    "image":                    '{{#Image}}<div class="gif-hero">{{Image}}</div>{{/Image}}',
    "text_example_phrase":      '{{#Text_Example_Phrase}}<div class="example">{{Text_Example_Phrase}}</div>{{/Text_Example_Phrase}}',
    "text_example_translation": '{{#Text_Example_Translation}}<div class="example-translation">{{Text_Example_Translation}}</div>{{/Text_Example_Translation}}',
    "audio_example":            '{{Sound_Example}}',
    "text_meaning":             '{{#Text_Meaning}}<div class="meaning">{{Text_Meaning}}</div>{{/Text_Meaning}}',
    "audio_meaning":            '{{Sound_Meaning}}',
    "synonyms":                 '{{Synonyms}}',
}
