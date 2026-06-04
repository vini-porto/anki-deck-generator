# =============================================================
#  templates/dark.py
#  Dark mode template — Catppuccin Mocha palette
#  Fields shown: Word, Gender, IPA, GIF, Example + Translation,
#                Meaning, Synonyms, all audio
# =============================================================

NAME = "dark"

CSS = """
/* ── Base ── */
.card {
    font-family: 'Segoe UI', Arial, sans-serif;
    background-color: #1e1e2e;
    color: #cdd6f4;
    text-align: center;
    padding: 24px 20px;
    line-height: 1.65;
    font-size: 17px;
}

/* ── Word ── */
.word {
    font-size: 32px;
    font-weight: 700;
    color: #89b4fa;
    margin-bottom: 2px;
    letter-spacing: 0.5px;
}

/* ── IPA ── */
.ipa {
    font-size: 16px;
    color: #6c7086;
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
.gender-m { background: #1e3a5f; color: #89b4fa; border: 1px solid #89b4fa44; }
.gender-f { background: #3d1f3d; color: #f5c2e7; border: 1px solid #f5c2e744; }

/* ── GIF ── */
.gif-box { margin: 10px auto; }
.gif-box img { border-radius: 10px; border: 2px solid #313244; }

/* ── Example sentence ── */
.example {
    font-size: 19px;
    color: #cdd6f4;
    background: #181825;
    border-left: 4px solid #89b4fa;
    border-radius: 6px;
    padding: 10px 16px;
    margin: 14px 0 4px 0;
    text-align: left;
}
.example .highlight {
    font-style: italic;
    font-weight: 700;
    color: #89dceb;
}

/* ── Example translation ── */
.example-translation {
    font-size: 15px;
    color: #6c7086;
    font-style: italic;
    text-align: left;
    margin: 0 0 12px 0;
    padding: 6px 16px;
}

/* ── Divider ── */
hr { border: none; border-top: 1px solid #313244; margin: 14px 0; }

/* ── Meaning ── */
.meaning {
    font-size: 17px;
    color: #a6e3a1;
    text-align: left;
    margin: 10px 0;
    padding: 8px 14px;
    background: #181825;
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
    background: #313244;
    color: #cba6f7;
    border-radius: 14px;
    padding: 3px 12px;
    font-size: 13px;
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
