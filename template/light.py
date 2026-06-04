# =============================================================
#  templates/light.py
#  Light mode template — clean white with soft accents
#  Fields shown: Word, Gender, IPA, GIF, Example + Translation,
#                Meaning, Synonyms, all audio
# =============================================================

NAME = "light"

CSS = """
/* ── Base ── */
.card {
    font-family: 'Segoe UI', Arial, sans-serif;
    background-color: #ffffff;
    color: #1a1a2e;
    text-align: center;
    padding: 24px 20px;
    line-height: 1.65;
    font-size: 17px;
}

/* ── Word ── */
.word {
    font-size: 32px;
    font-weight: 700;
    color: #2563eb;
    margin-bottom: 2px;
    letter-spacing: 0.5px;
}

/* ── IPA ── */
.ipa {
    font-size: 16px;
    color: #9ca3af;
    font-style: italic;
    margin-bottom: 14px;
}

/* ── Gender badge ── */
.gender-badge {
    display: inline-block;
    font-size: 13px;
    font-weight: 600;
    padding: 2px 12px;
    border-radius: 12px;
    margin-bottom: 10px;
}
.gender-m { background: #dbeafe; color: #1d4ed8; border: 1px solid #93c5fd; }
.gender-f { background: #fce7f3; color: #9d174d; border: 1px solid #f9a8d4; }

/* ── GIF ── */
.gif-box { margin: 10px auto; }
.gif-box img { border-radius: 10px; border: 2px solid #e5e7eb; }

/* ── Example sentence ── */
.example {
    font-size: 19px;
    color: #1a1a2e;
    background: #f8fafc;
    border-left: 4px solid #2563eb;
    border-radius: 6px;
    padding: 10px 16px;
    margin: 14px 0 4px 0;
    text-align: left;
}
.example .highlight {
    font-style: italic;
    font-weight: 700;
    color: #0284c7;
}

/* ── Example translation ── */
.example-translation {
    font-size: 15px;
    color: #9ca3af;
    font-style: italic;
    text-align: left;
    margin: 0 0 12px 0;
    padding: 6px 16px;
}

/* ── Divider ── */
hr { border: none; border-top: 1px solid #e5e7eb; margin: 14px 0; }

/* ── Meaning ── */
.meaning {
    font-size: 17px;
    color: #15803d;
    text-align: left;
    margin: 10px 0;
    padding: 8px 14px;
    background: #f0fdf4;
    border-radius: 6px;
    border: 1px solid #bbf7d0;
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
    background: #ede9fe;
    color: #6d28d9;
    border-radius: 14px;
    padding: 3px 12px;
    font-size: 13px;
    border: 1px solid #ddd6fe;
}
"""

FRONT = """
<div class="word">{{Word}}</div>
{{Gender}}
<div class="ipa">/ {{IPA}} /</div>
{{Sound_Word}}
<div class="gif-box">{{Image}}</div>
<div class="example">{{Text_Example_Phrase}}</div>
<div class="example-translation">{{Text_Example_Translation}}</div>
{{Sound_Example}}
"""

BACK = """
{{FrontSide}}
<hr>
<div class="meaning">{{Text_Meaning}}</div>
{{Sound_Meaning}}
{{Synonyms}}
"""
