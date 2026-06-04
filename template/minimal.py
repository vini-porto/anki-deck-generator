# =============================================================
#  templates/minimal.py
#  Minimal template — text only, no GIF, no gender badge
#  Focus on language learning without visual distractions.
#  Fields shown: Word, IPA, Example + Translation, Meaning,
#                Synonyms, word audio only
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

FRONT = """
<div class="word">{{Word}}</div>
<div class="ipa">/ {{IPA}} /</div>
{{Sound_Word}}
<div class="example">{{Text_Example_Phrase}}</div>
<div class="example-translation">{{Text_Example_Translation}}</div>
"""

BACK = """
{{FrontSide}}
<hr>
<div class="meaning">{{Text_Meaning}}</div>
{{Synonyms}}
"""
