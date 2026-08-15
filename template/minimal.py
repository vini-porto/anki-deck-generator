# =============================================================
#  templates/minimal.py
#  Minimal template — plain, distraction-light serif styling.
#  Field visibility is entirely user-controlled (see Card fields
#  checklist) — this template just renders whatever's enabled
#  with a quieter visual treatment than dark/light.
# =============================================================

NAME = "minimal"

CSS = """
/* ── Base ── */
.card {
    font-family: 'Georgia', serif;
    background-color: #fafafa;
    color: #1a1a1a;
    text-align: center;
    padding: 32px 24px;
    line-height: 1.8;
    font-size: 18px;
    max-width: 520px;
    margin: 0 auto;
}

/* ── Word ── */
.word {
    font-size: 36px;
    font-weight: 700;
    color: #1a1a1a;
    margin-bottom: 4px;
    letter-spacing: 1px;
}

/* ── IPA ── */
.ipa {
    font-size: 17px;
    color: #888;
    font-style: italic;
    margin-bottom: 20px;
}

/* ── Gender badge (opt-in field, no visual flourish here by design) ── */
.gender-badge {
    display: inline-block;
    font-size: 12px;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 10px;
    margin-bottom: 10px;
    border: 1px solid #ccc;
    color: #555;
}
.gender-m, .gender-f { background: #f0f0f0; }

/* ── GIF (opt-in field) ── */
.gif-box { margin: 12px auto; }
.gif-box img { border-radius: 8px; filter: grayscale(15%); }

/* ── Example sentence ── */
.example {
    font-size: 20px;
    color: #1a1a1a;
    padding: 12px 0;
    margin: 16px 0 4px 0;
    text-align: center;
    border-top: 1px solid #e0e0e0;
    border-bottom: 1px solid #e0e0e0;
}
.example .highlight {
    font-style: italic;
    font-weight: 700;
}

/* ── Example translation ── */
.example-translation {
    font-size: 15px;
    color: #aaa;
    font-style: italic;
    text-align: center;
    margin: 4px 0 16px 0;
}

/* ── Divider ── */
hr { border: none; border-top: 1px solid #e0e0e0; margin: 16px 0; }

/* ── Meaning ── */
.meaning {
    font-size: 17px;
    color: #333;
    text-align: center;
    margin: 12px 0;
}

/* ── Synonyms ── */
.synonyms-wrap {
    margin-top: 16px;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 6px;
}
.syn-badge {
    background: #f0f0f0;
    color: #555;
    border-radius: 14px;
    padding: 3px 12px;
    font-size: 13px;
}
"""

# Per-field HTML fragments, assembled dynamically at export time by
# _assemble_side() (main.py) — see CLAUDE.md § Card fields / template/dark.py.
# Unlike the pre-3.0 fixed layout (which never showed Gender/Image/
# Sound_Example/Sound_Meaning), every field is now available here too if
# the user's checklist enables it — "minimal" is a styling choice, not a
# field restriction.
FIELD_HTML = {
    "word":                     '{{#Word}}<div class="word">{{Word}}</div>{{/Word}}',
    "gender":                   '{{Gender}}',
    "ipa":                      '{{#IPA}}<div class="ipa">/ {{IPA}} /</div>{{/IPA}}',
    "audio_word":               '{{Sound_Word}}',
    "image":                    '{{#Image}}<div class="gif-box">{{Image}}</div>{{/Image}}',
    "text_example_phrase":      '{{#Text_Example_Phrase}}<div class="example">{{Text_Example_Phrase}}</div>{{/Text_Example_Phrase}}',
    "text_example_translation": '{{#Text_Example_Translation}}<div class="example-translation">{{Text_Example_Translation}}</div>{{/Text_Example_Translation}}',
    "audio_example":            '{{Sound_Example}}',
    "text_meaning":             '{{#Text_Meaning}}<div class="meaning">{{Text_Meaning}}</div>{{/Text_Meaning}}',
    "audio_meaning":            '{{Sound_Meaning}}',
    "synonyms":                 '{{Synonyms}}',
}
