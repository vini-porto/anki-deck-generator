# =============================================================
#  templates/immersive.py
#  Immersive template — GIF as full card background with
#  text overlay. High visual impact, great for concrete words.
#  Fields shown: Word, Gender, IPA, GIF (background), Example,
#                Translation, Meaning, Synonyms, all audio
# =============================================================

NAME = "immersive"

CSS = """
/* ── Base ── */
.card {
    font-family: 'Segoe UI', Arial, sans-serif;
    background-color: #0f0f0f;
    color: #f0f0f0;
    text-align: center;
    padding: 0;
    line-height: 1.65;
    font-size: 17px;
}

/* ── GIF hero background ── */
.gif-hero {
    position: relative;
    width: 100%;
    min-height: 220px;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    overflow: hidden;
    border-radius: 0 0 16px 16px;
}
.gif-hero img {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    object-fit: cover;
    filter: brightness(0.45);
    border-radius: 0 0 16px 16px;
}
.gif-hero-content {
    position: relative;
    z-index: 2;
    padding: 20px 20px 24px;
    width: 100%;
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

/* ── Body content below GIF ── */
.card-body {
    padding: 20px 20px 24px;
}

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

# GIF used as hero background via inline style trick
FRONT = """
<div class="gif-hero">
    <div id="gif-bg"></div>
    <div class="gif-hero-content">
        <div class="word">{{Word}}</div>
        {{Gender}}
        <div class="ipa">/ {{IPA}} /</div>
        {{Sound_Word}}
    </div>
</div>
<div class="card-body">
    <div class="example">{{Text_Example_Phrase}}</div>
    <div class="example-translation">{{Text_Example_Translation}}</div>
    {{Sound_Example}}
</div>
<script>
(function() {
    var gifField = {{Image_Raw}};
    var hero = document.querySelector('.gif-hero');
    if (gifField && hero) {
        var img = document.createElement('img');
        img.src = gifField;
        hero.insertBefore(img, hero.firstChild);
    }
})();
</script>
"""

# Immersive back is simpler — meaning + synonyms below the front
BACK = """
{{FrontSide}}
<div class="card-body">
    <hr>
    <div class="meaning">{{Text_Meaning}}</div>
    {{Sound_Meaning}}
    {{Synonyms}}
</div>
"""

# Note: the immersive template requires an extra field "Image_Raw"
# that stores just the GIF URL (not the full <img> tag).
# The main script handles this automatically when this template is active.
REQUIRES_RAW_IMAGE = True
