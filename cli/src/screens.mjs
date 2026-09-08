// Screen definitions — mirrors main.py's own grouping (main menu, export
// card-type picker, configure_* settings screens, statistics, card type
// guide). Settings screens read/write config.py exclusively through the
// bridge, never touching any file directly.
//
// Navigation shape: each function below owns one "page." Action/Back rows
// return a token from runScreen(); the function's own while-loop (or a
// single await, for leaf screens) decides what to show next.

import { bridge } from './bridge.mjs';
import { runScreen } from './runScreen.mjs';
import { staticScreen } from './staticScreen.mjs';
import { styles, setAppVersion } from './theme.mjs';
import { disableRawMode, enableRawMode, flushKeys } from './term.mjs';

// Generate/export shell out to Python with inherited stdio — raw mode has
// to step aside for that or keystrokes typed during the run get captured
// by our own listener instead of just scrolling past in the terminal, and
// buffer up as phantom navigation once the menu redraws.
function runSubprocess(fn) {
  disableRawMode();
  try {
    fn();
  } finally {
    enableRawMode();
    flushKeys();
  }
}

let _cfgStore = null;
let _options = null;

function getOptions() {
  if (!_options) _options = bridge.options();
  return _options;
}

function coerceLocal(raw, type) {
  if (type === 'bool') return typeof raw === 'boolean' ? raw : String(raw).toLowerCase() === 'true';
  if (type === 'int') return parseInt(raw, 10);
  if (type === 'float') return parseFloat(raw);
  return raw;
}

function getCfgStore() {
  if (!_cfgStore) {
    let cfg = bridge.config();
    _cfgStore = {
      get: () => cfg,
      async set(key, value, type) {
        await bridge.setConfig(key, value, type);
        cfg = { ...cfg, [key]: coerceLocal(value, type) };
      },
      // Mutates the in-process cache only — never calls bridge.setConfig,
      // so config.py is never rewritten. Used for the mode picker's
      // session-only WORD_SOURCE (confirmed with the user it should not
      // become a new persistent default just from being selected).
      setLocal(key, value) {
        cfg = { ...cfg, [key]: value };
      },
    };
  }
  return _cfgStore;
}

// ── Item descriptor builders (plain objects consumed by runScreen/render) ─

function toggleItem(label, key) {
  const store = getCfgStore();
  return {
    kind: 'toggle',
    label,
    getValue: () => Boolean(store.get()[key]),
    setValue: (v) => store.set(key, String(v), 'bool'),
  };
}

function pickerItem(label, key, options) {
  const store = getCfgStore();
  return {
    kind: 'picker',
    label,
    options,
    getValue: () => store.get()[key],
    setValue: (v) => store.set(key, v, 'str'),
  };
}

function textItem(label, key, { secret = false } = {}) {
  const store = getCfgStore();
  return {
    kind: 'text',
    label,
    secret,
    getValue: () => store.get()[key],
    setValue: (v) => store.set(key, v, 'str'),
  };
}

function numberItem(label, key, { minVal = 0, step = 1, isFloat = false } = {}) {
  const store = getCfgStore();
  return {
    kind: 'number',
    label,
    minVal,
    step,
    isFloat,
    getValue: () => store.get()[key],
    setValue: (v) => store.set(key, String(v), isFloat ? 'float' : 'int'),
  };
}

function actionItem(label, token, description) {
  return { kind: 'action', label, token, description };
}

function backItem(label = 'Back') {
  return { kind: 'back', label };
}

function separatorItem() {
  return { kind: 'separator' };
}

function infoItem(text) {
  return { kind: 'info', text };
}

// ── Shared header data ──────────────────────────────────────────────────

function bannerSummary() {
  const cfg = getCfgStore().get();
  const options = getOptions();
  const provider = cfg.AI_PROVIDER;
  const providerLabel = options.provider_labels[provider] || provider;
  const modelField = options.provider_model_field[provider] || 'AI_MODEL';
  const model = cfg[modelField] || '';
  const modeLabel = MODE_LABELS[cfg.WORD_SOURCE];
  const modePart = modeLabel ? `   ·   ${modeLabel}` : '';
  return `${String(cfg.SOURCE_LANG).toUpperCase()} -> ${cfg.TARGET_LANG}   ·   ${cfg.CARD_TEMPLATE}   ·   ${providerLabel} (${model})${modePart}`;
}

function aiKeyMissing() {
  const cfg = getCfgStore().get();
  const options = getOptions();
  const keyField = options.provider_key_field[cfg.AI_PROVIDER];
  if (!keyField) return false; // ollama needs no key
  return String(cfg[keyField] || '').startsWith('your_');
}

function giphyKeyMissing() {
  const cfg = getCfgStore().get();
  return Boolean(cfg.ENABLE_GIF) && String(cfg.GIPHY_API_KEY || '') === 'your_giphy_api_key_here';
}

function getConfigWarnings() {
  const warnings = [];
  if (aiKeyMissing()) warnings.push('AI provider key missing');
  if (giphyKeyMissing()) warnings.push('Giphy key missing');
  return warnings;
}

// ── Settings screens (mirrors main.py's configure_* functions) ─────────

async function providerSettings(crumbs) {
  const options = getOptions();
  const provider = getCfgStore().get().AI_PROVIDER;
  const trail = [...crumbs, 'Provider settings'];

  let title;
  let fields;
  if (provider === 'groq') {
    title = 'Groq Settings';
    fields = [pickerItem('AI model', 'AI_MODEL', options.groq_models), textItem('Groq API key', 'GROQ_API_KEY', { secret: true })];
  } else if (provider === 'openai') {
    title = 'OpenAI Settings';
    fields = [textItem('AI model', 'OPENAI_MODEL'), textItem('OpenAI API key', 'OPENAI_API_KEY', { secret: true })];
  } else if (provider === 'anthropic') {
    title = 'Claude (Anthropic) Settings';
    fields = [
      pickerItem('AI model', 'ANTHROPIC_MODEL', options.anthropic_models),
      textItem('Anthropic API key', 'ANTHROPIC_API_KEY', { secret: true }),
    ];
  } else if (provider === 'gemini') {
    title = 'Gemini Settings';
    fields = [textItem('AI model', 'GEMINI_MODEL'), textItem('Gemini API key', 'GEMINI_API_KEY', { secret: true })];
  } else {
    title = 'Ollama Settings';
    fields = [textItem('AI model', 'OLLAMA_MODEL'), textItem('Ollama server address', 'OLLAMA_HOST')];
  }

  const items = [...fields, separatorItem(), backItem()];
  await runScreen({ title, breadcrumb: trail, summary: bannerSummary(), items });
}

async function settingsAi(crumbs) {
  const options = getOptions();
  const trail = [...crumbs, 'AI & API'];
  while (true) {
    const cfg = getCfgStore().get();
    const label = options.provider_labels[cfg.AI_PROVIDER] || cfg.AI_PROVIDER;
    const modelField = options.provider_model_field[cfg.AI_PROVIDER] || 'AI_MODEL';
    const model = cfg[modelField] || '';
    const items = [
      pickerItem('AI provider', 'AI_PROVIDER', options.ai_providers),
      actionItem('Provider settings', 'provider', `${label}  |  ${model}` + (aiKeyMissing() ? '   ! key missing' : '')),
      separatorItem(),
      backItem(),
    ];
    const choice = await runScreen({ title: 'AI & API Settings', breadcrumb: trail, summary: bannerSummary(), items });
    if (choice === undefined || choice === 'back') return;
    if (choice === 'provider') await providerSettings(trail);
  }
}

async function settingsLanguage(crumbs) {
  const trail = [...crumbs, 'Language'];
  const items = [
    textItem('Language to learn', 'SOURCE_LANG'),
    textItem('Native language', 'TARGET_LANG'),
    textItem('TTS source lang (gTTS)', 'TTS_SOURCE_LANG'),
    textItem('TTS native lang (gTTS)', 'TTS_TARGET_LANG'),
    separatorItem(),
    backItem(),
  ];
  await runScreen({ title: 'Language Settings', breadcrumb: trail, summary: bannerSummary(), items });
}

// mode: the active WORD_SOURCE value — Annotation Mode never routes cards
// into a category subdeck (tags only, see CLAUDE.md § Category / subdeck
// organization), so the category toggle's label is adjusted to match.
async function settingsDeck(crumbs, mode) {
  const options = getOptions();
  const trail = [...crumbs, 'Deck & cards'];
  const categoriesLabel = mode === 'markdown_notes' ? 'Category tags' : 'Category subdecks & tags';
  const items = [
    textItem('Deck name', 'DECK_NAME'),
    pickerItem('Card template', 'CARD_TEMPLATE', options.templates),
    textItem('Output — new deck', 'DECK_OUTPUT_NEW'),
    textItem('Output — full deck', 'DECK_OUTPUT_FULL'),
    separatorItem(),
    toggleItem(categoriesLabel, 'ENABLE_CATEGORIES'),
    separatorItem(),
    backItem(),
  ];
  await runScreen({ title: 'Deck & Card Settings', breadcrumb: trail, summary: bannerSummary(), items });
}

// mode: the active WORD_SOURCE value ('markdown_notes' | 'frequency_list')
// — which settings show below depends on it, mirroring main.py's
// configure_generation(mode). 'Words per run' is Spontaneous-Mode-only —
// Annotation Mode processes every new item found in a single run, no
// per-run cap (see main.py's _do_generate()).
async function settingsGeneration(crumbs, mode) {
  const options = getOptions();
  const trail = [...crumbs, 'Generation'];
  const items = [];
  if (mode !== 'markdown_notes') {
    items.push(numberItem('Words per run', 'WORDS_PER_RUN', { minVal: 1, step: 5 }));
  }
  items.push(
    numberItem('Total word pool', 'TOTAL_WORD_POOL', { minVal: 100, step: 100 }),
    separatorItem(),
  );
  if (mode === 'markdown_notes') {
    items.push(
      pickerItem('Markdown source mode', 'MARKDOWN_SOURCE_MODE', options.markdown_source_modes),
      textItem('Markdown notes path', 'MARKDOWN_NOTES_PATH'),
      pickerItem('Markdown extraction', 'MARKDOWN_EXTRACTION_MODE', options.markdown_extraction_modes),
    );
  } else {
    items.push(pickerItem('Meaning exhaustiveness', 'MEANING_EXHAUSTIVENESS', options.meaning_exhaustiveness_options));
  }
  items.push(separatorItem(), backItem());
  await runScreen({ title: 'Generation Settings', breadcrumb: trail, summary: bannerSummary(), items });
}

// ── Card fields — the checkbox field configuration, step 2 of the
// Generate wizard (see runGenerateWizard() / pickCreationMode() below).
// Reads/writes config.CARD_FIELDS_JSON as a whole blob rather than one
// config key per field — an independent JS implementation of main.py's
// load_card_fields()/save_card_fields()/_field_detail_menu(), since
// there's no shared runtime between Python and JS to factor it into (same
// precedent the old cascading Card Content picker set). See CLAUDE.md
// § Card fields.

const POSITION_OPTIONS = [['front', 'Front'], ['back', 'Back']];

function loadCardFields() {
  const cfg = getCfgStore().get();
  try {
    return JSON.parse(cfg.CARD_FIELDS_JSON || '[]');
  } catch {
    return [];
  }
}

async function saveCardFields(fields) {
  await getCfgStore().set('CARD_FIELDS_JSON', JSON.stringify(fields), 'str');
}

function fieldSummary(key) {
  const options = getOptions();
  const f = loadCardFields().find((x) => x.field === key);
  if (!f.enabled) return 'off';
  return `${f.position} · #${f.order} · ${options.interaction_labels[f.interaction]}`;
}

function fieldSubPicker(label, fieldKey, attr, opts) {
  return {
    kind: 'picker',
    label,
    options: opts,
    getValue: () => loadCardFields().find((f) => f.field === fieldKey)[attr],
    setValue: async (v) => {
      const fields = loadCardFields();
      for (const f of fields) if (f.field === fieldKey) f[attr] = v;
      await saveCardFields(fields);
    },
  };
}

function fieldEnabledToggle(fieldKey) {
  return {
    kind: 'toggle',
    label: 'Enabled',
    getValue: () => loadCardFields().find((f) => f.field === fieldKey).enabled,
    setValue: async (v) => {
      const fields = loadCardFields();
      for (const f of fields) if (f.field === fieldKey) f.enabled = Boolean(v);
      await saveCardFields(fields);
    },
  };
}

function fieldOrderNumber(fieldKey) {
  return {
    kind: 'number',
    label: 'Order',
    minVal: 0,
    step: 1,
    isFloat: false,
    getValue: () => loadCardFields().find((f) => f.field === fieldKey).order,
    setValue: async (v) => {
      const fields = loadCardFields();
      for (const f of fields) if (f.field === fieldKey) f.order = Math.max(0, Math.round(Number(v)));
      await saveCardFields(fields);
    },
  };
}

async function fieldDetailMenu(crumbs, catalogEntry) {
  const options = getOptions();
  const trail = [...crumbs, catalogEntry.label];
  const items = [];
  if (catalogEntry.key !== 'word') items.push(fieldEnabledToggle(catalogEntry.key));
  items.push(
    fieldSubPicker('Position', catalogEntry.key, 'position', POSITION_OPTIONS),
    fieldOrderNumber(catalogEntry.key),
  );
  if (catalogEntry.interactions_allowed.length > 1) {
    items.push(fieldSubPicker('Interaction', catalogEntry.key, 'interaction',
      catalogEntry.interactions_allowed.map((i) => [i, options.interaction_labels[i]])));
  }
  items.push(separatorItem(), backItem());
  await runScreen({ title: catalogEntry.label, breadcrumb: trail, summary: bannerSummary(), items });
}

// Returns true if the user chose "Continue -> Generate", false if they
// backed/cancelled out.
async function cardFieldsMenu(crumbs) {
  const options = getOptions();
  const trail = [...crumbs, 'Choose Card Fields'];
  const items = [
    ...options.field_catalog.map((c) => actionItem(c.label, `field:${c.key}`, () => fieldSummary(c.key))),
    separatorItem(),
    actionItem('Continue -> Generate', 'continue', 'Proceed with this field configuration'),
    backItem('Cancel'),
  ];
  while (true) {
    const choice = await runScreen({ title: 'Choose Card Fields', breadcrumb: trail, summary: bannerSummary(), items });
    if (choice === undefined || choice === 'back') return false;
    if (choice === 'continue') return true;
    const key = choice.split(':')[1];
    const entry = options.field_catalog.find((c) => c.key === key);
    await fieldDetailMenu(crumbs, entry);
  }
}

// Annotation Mode's generate-wizard step 2, replacing cardFieldsMenu() for
// this mode. The card is fixed — highlighted phrase/word on the front,
// translation on the back, nothing else (see CLAUDE.md § Annotation Mode
// content presets) — so the only real choices left are whether to include
// word-pronunciation audio and how the card tests you. Mirrors main.py's
// configure_annotation_content(). Writes ANNOTATION_INCLUDE_AUDIO/
// ANNOTATION_CARD_TYPE directly; never touches CARD_FIELDS_JSON. Returns
// true if the user chose to continue, false if they backed/cancelled.
async function annotationContentMenu(crumbs) {
  const options = getOptions();
  const trail = [...crumbs, 'Choose Content & Card Type'];
  const cfg = getCfgStore().get();
  const clozeOk = cfg.MARKDOWN_EXTRACTION_MODE === 'highlights';
  const cardTypeOptions = clozeOk
    ? options.annotation_card_types
    : options.annotation_card_types.filter(([key]) => key !== 'cloze');

  let proceed = false;
  const items = [
    toggleItem('Include word pronunciation audio', 'ANNOTATION_INCLUDE_AUDIO'),
    pickerItem('Card type', 'ANNOTATION_CARD_TYPE', cardTypeOptions),
    separatorItem(),
    actionItem('Continue -> Generate', 'continue', 'Proceed with this content configuration'),
    backItem('Cancel'),
  ];
  const choice = await runScreen({
    title: 'Choose Content & Card Type', breadcrumb: trail, summary: bannerSummary(), items,
  });
  if (choice === 'continue') proceed = true;
  return proceed;
}

// Each option's label is "<Voice>(<Language>)", e.g. "Estelle(French)" —
// the language comes straight out of the Pocket TTS language id itself
// (strip a trailing "_24l", title-case what's left), mirroring main.py's
// _pocket_tts_voice_options().
function pocketTtsVoiceOptions(langCode) {
  const options = getOptions();
  const pocketLang = options.pocket_tts_lang_map[langCode] || 'english';
  const voices = options.pocket_tts_voices[pocketLang] || options.pocket_tts_voices.english;
  const titleCase = (s) => s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  const langLabel = titleCase(pocketLang.replace(/_24l$/, ''));
  return voices.map((v) => [v, `${titleCase(v)}(${langLabel})`]);
}

async function pocketTtsSettings(crumbs) {
  const cfg = getCfgStore().get();
  const trail = [...crumbs, 'Pocket TTS settings'];
  const items = [
    pickerItem('Source voice', 'POCKET_TTS_VOICE_SOURCE', pocketTtsVoiceOptions(cfg.TTS_SOURCE_LANG)),
    pickerItem('Target voice', 'POCKET_TTS_VOICE_TARGET', pocketTtsVoiceOptions(cfg.TTS_TARGET_LANG)),
    separatorItem(),
    toggleItem('Int8 quantization', 'POCKET_TTS_QUANTIZE'),
    separatorItem(),
    backItem(),
  ];
  await runScreen({ title: 'Pocket TTS Settings', breadcrumb: trail, summary: bannerSummary(), items });
}

// mode: the active WORD_SOURCE value — Annotation Mode's note has no
// example-sentence or meaning-audio field at all (front = highlighted
// phrase, back = translation, see CLAUDE.md § Annotation Mode content
// presets), so those two toggles are meaningless there and hidden.
async function settingsAudio(crumbs, mode) {
  const options = getOptions();
  const trail = [...crumbs, 'Audio'];
  while (true) {
    const items = [
      toggleItem('Enable audio (master switch)', 'ENABLE_AUDIO'),
      separatorItem(),
      toggleItem('Word pronunciation audio', 'ENABLE_WORD_AUDIO'),
    ];
    if (mode !== 'markdown_notes') {
      items.push(
        toggleItem('Example sentence audio', 'ENABLE_EXAMPLE_AUDIO'),
        toggleItem('Meaning audio (native lang)', 'ENABLE_MEANING_AUDIO'),
      );
    }
    items.push(
      separatorItem(),
      pickerItem('TTS provider', 'TTS_PROVIDER', options.tts_providers),
      actionItem('Pocket TTS settings', 'pocket_tts', () => {
        const c = getCfgStore().get();
        return c.TTS_PROVIDER === 'pocket_tts' ? `${c.POCKET_TTS_VOICE_SOURCE} / ${c.POCKET_TTS_VOICE_TARGET}` : 'n/a — gTTS selected';
      }),
      separatorItem(),
      backItem(),
    );
    const choice = await runScreen({ title: 'Audio Settings', breadcrumb: trail, summary: bannerSummary(), items });
    if (choice === undefined || choice === 'back') return;
    if (choice === 'pocket_tts') await pocketTtsSettings(trail);
  }
}

async function settingsGif(crumbs) {
  const options = getOptions();
  const trail = [...crumbs, 'GIF'];
  const items = [
    toggleItem('Enable GIF (Giphy)', 'ENABLE_GIF'),
    pickerItem('Content rating filter', 'GIF_RATING', options.gif_ratings),
    separatorItem(),
    textItem('Giphy API key', 'GIPHY_API_KEY', { secret: true }),
    separatorItem(),
    backItem(),
  ];
  await runScreen({ title: 'GIF Settings', breadcrumb: trail, summary: bannerSummary(), items });
}

async function settingsRateLimits(crumbs) {
  const trail = [...crumbs, 'Rate limits'];
  const items = [
    numberItem('AI delay', 'DELAY_AI', { minVal: 0, step: 0.1, isFloat: true }),
    numberItem('Giphy delay', 'DELAY_GIPHY', { minVal: 0, step: 0.1, isFloat: true }),
    numberItem('gTTS delay', 'DELAY_TTS', { minVal: 0, step: 0.1, isFloat: true }),
    separatorItem(),
    backItem(),
  ];
  await runScreen({
    title: 'Rate Limiting  (seconds between API calls)',
    breadcrumb: trail,
    summary: bannerSummary(),
    items,
  });
}

// mode: the active WORD_SOURCE value — threaded through to
// settingsGeneration()/settingsDeck()/settingsAudio(), mirroring
// main.py's configure_main(mode). The GIF row is dropped entirely for
// Annotation Mode, which never has a GIF (see CLAUDE.md § Annotation
// Mode content presets).
async function settingsMain(crumbs, mode) {
  const trail = [...crumbs, 'Settings'];
  while (true) {
    const items = [
      actionItem('Language', 'language', () => {
        const c = getCfgStore().get();
        return `${String(c.SOURCE_LANG).toUpperCase()} -> ${c.TARGET_LANG}`;
      }),
      actionItem('AI & API keys', 'ai', () => {
        const c = getCfgStore().get();
        const label = getOptions().provider_labels[c.AI_PROVIDER] || c.AI_PROVIDER;
        return label + (aiKeyMissing() ? '  ! key missing' : '');
      }),
      actionItem('Deck & cards', 'deck', () => getCfgStore().get().CARD_TEMPLATE),
      actionItem('Generation', 'generation', () => {
        const c = getCfgStore().get();
        return mode === 'markdown_notes'
          ? `pool ${c.TOTAL_WORD_POOL}`
          : `${c.WORDS_PER_RUN}/run   pool ${c.TOTAL_WORD_POOL}`;
      }),
      actionItem('Audio', 'audio', () => (getCfgStore().get().ENABLE_AUDIO ? 'ON' : 'OFF')),
    ];
    if (mode !== 'markdown_notes') {
      items.push(actionItem('GIF', 'gif', () => {
        const c = getCfgStore().get();
        return `${c.ENABLE_GIF ? 'ON' : 'OFF'}  |  rating: ${c.GIF_RATING}` + (giphyKeyMissing() ? '  ! key missing' : '');
      }));
    }
    items.push(
      actionItem('Rate limits', 'ratelimits', () => {
        const c = getCfgStore().get();
        return `AI ${c.DELAY_AI}s  Giphy ${c.DELAY_GIPHY}s  TTS ${c.DELAY_TTS}s`;
      }),
      separatorItem(),
      backItem('Back to main menu'),
    );
    const choice = await runScreen({ title: 'Configure Settings', breadcrumb: trail, summary: bannerSummary(), items });
    if (choice === undefined || choice === 'back') return;
    if (choice === 'language') await settingsLanguage(trail);
    else if (choice === 'ai') await settingsAi(trail);
    else if (choice === 'deck') await settingsDeck(trail, mode);
    else if (choice === 'generation') await settingsGeneration(trail, mode);
    else if (choice === 'audio') await settingsAudio(trail, mode);
    else if (choice === 'gif') await settingsGif(trail);
    else if (choice === 'ratelimits') await settingsRateLimits(trail);
  }
}

// ── Statistics & card type guide (static pages) ─────────────────────────

async function showStatistics(crumbs) {
  const stats = bridge.stats();
  const trail = [...crumbs, 'Statistics'];
  const body = [];

  body.push(`Total cards     : ${styles.warningBold.render(String(stats.total))}`);
  body.push(`Exported        : ${styles.success.render(String(stats.exported))}`);
  body.push(`Pending export  : ${styles.accent2.render(String(stats.pending))}`);

  if (stats.by_pos.length) {
    body.push('', styles.bold.render('By Part of Speech:'));
    for (const { pos, count } of stats.by_pos) {
      const bar = '█'.repeat(Math.min(count, 28));
      body.push(
        `  ${(pos + ':').padEnd(16)} ${styles.warning.render(String(count).padStart(4))}  ${styles.accent2.render(bar)}`,
      );
    }
  }

  if (stats.by_category.length) {
    body.push('', styles.bold.render('By Category (subdecks):'));
    for (const { category, count } of stats.by_category) {
      const bar = '█'.repeat(Math.min(count, 28));
      body.push(
        `  ${(category + ':').padEnd(24)} ${styles.warning.render(String(count).padStart(4))}  ${styles.accent.render(bar)}`,
      );
    }
  }

  if (stats.recent_days.length) {
    body.push('', styles.bold.render('Cards added (last 7 sessions):'));
    for (const { date, count } of stats.recent_days) {
      body.push(`  ${date}   ${styles.success.render(`${count} cards`)}`);
    }
  }

  if (stats.recent_exports.length) {
    body.push('', styles.bold.render('Recent exports:'));
    for (const { date, type, count } of stats.recent_exports) {
      body.push(
        `  ${date.slice(0, 16)}  ${String(type).padEnd(22)}  ${styles.accent2.render(`${count} cards`)}`,
      );
    }
  }

  await staticScreen({ title: 'Statistics', breadcrumb: trail, summary: bannerSummary(), body });
}

// ── Mode selection: the outermost screen (Annotation vs Spontaneous) ───
// Session-only by design (confirmed with the user) — picking a mode here
// never calls bridge.setConfig, so config.py's WORD_SOURCE is never
// rewritten just from selecting it. getCfgStore().setLocal() mutates only
// the in-process config cache so the rest of this session's screens (and
// bannerSummary()) see the right value; bridge.generate(mode) carries it
// across the subprocess boundary explicitly for the one call that
// actually needs it in Python (see bridge.mjs).

const MODE_LABELS = {
  markdown_notes: 'Annotation Mode',
  frequency_list: 'Spontaneous Mode (AI)',
};

async function pickCreationMode() {
  const trail = ['Choose Creation Mode'];
  const items = [
    actionItem('Annotation Mode', 'markdown_notes', 'Generate cards from words/phrases highlighted in your notes'),
    actionItem('Spontaneous Mode (AI)', 'frequency_list', 'AI picks words and invents example content automatically'),
    separatorItem(),
    backItem('Exit'),
  ];
  const choice = await runScreen({ title: 'Choose Creation Mode', breadcrumb: trail, summary: bannerSummary(), items });
  return (choice === undefined || choice === 'back') ? null : choice;
}

// ── Generate wizard: content configuration -> generate (+ auto-export).
// Mode is no longer picked here — it's the outer screen this lives under.
// Annotation Mode gets the simplified preset/card-type picker; Spontaneous
// Mode keeps the full field checklist — mirrors main.py's
// run_generate_wizard().

async function runGenerateWizard(crumbs) {
  const mode = getCfgStore().get().WORD_SOURCE;
  const proceed = mode === 'markdown_notes'
    ? await annotationContentMenu(crumbs)
    : await cardFieldsMenu(crumbs);
  if (!proceed) return;
  runSubprocess(() => bridge.generate(mode));   // _do_generate() now auto-exports at the end
}

// ── Export flow: show recent export history, prompt for an output
// filename, then delegate to Python ─────────────────────────────────────

async function runExportFlow(crumbs) {
  const trail = [...crumbs, 'Export decks'];
  const cfg = getCfgStore().get();
  const stats = bridge.stats();
  let filename = cfg.DECK_OUTPUT_FULL;
  const filenameItem = {
    kind: 'text',
    label: 'Output filename',
    secret: false,
    getValue: () => filename,
    setValue: (v) => { filename = v || cfg.DECK_OUTPUT_FULL; },
  };
  const items = [];
  if (stats.recent_exports.length) {
    items.push(infoItem('Recent exports:'));
    for (const { date, type, count } of stats.recent_exports) {
      items.push(infoItem(`  ${date.slice(0, 16)}  ${String(type).padEnd(22)}  ${count} cards`));
    }
    items.push(separatorItem());
  }
  items.push(
    filenameItem,
    separatorItem(),
    actionItem('Export', 'confirm', 'Write one full-backup .apkg under this filename'),
    backItem('Cancel'),
  );

  const choice = await runScreen({ title: 'Export Decks', breadcrumb: trail, summary: bannerSummary(), items });
  if (choice === undefined || choice === 'back') return;

  runSubprocess(() => bridge.export(filename));
}

// ── Mode-scoped Main Menu — 'Exit' here backs out to mode selection, not
// the app; mainMenu()'s outer loop is what actually quits. ─────────────

async function modeMainMenu(mode) {
  const label = MODE_LABELS[mode] || mode;
  const crumbs = [`Main Menu — ${label}`];
  while (true) {
    const items = [
      actionItem('Generate new cards', 'generate', 'Configure content, then generate + export automatically'),
      actionItem('Export decks', 'export', 'Rebuild a full backup .apkg under a chosen filename'),
      actionItem('Configure', 'configure', () => {
        const c = getCfgStore().get();
        const warnings = getConfigWarnings();
        return `${String(c.SOURCE_LANG).toUpperCase()} -> ${c.TARGET_LANG}` + (warnings.length ? `   ⚠ ${warnings.length}` : '');
      }),
      actionItem('Statistics', 'stats', 'Card counts, POS breakdown, export history'),
      separatorItem(),
      backItem('Exit'),
    ];
    const choice = await runScreen({ title: `Main Menu — ${label}`, breadcrumb: crumbs, summary: bannerSummary(), items });
    if (choice === undefined || choice === 'back') return;
    if (choice === 'generate') await runGenerateWizard(crumbs);
    else if (choice === 'export') await runExportFlow(crumbs);
    else if (choice === 'configure') await settingsMain(crumbs, mode);
    else if (choice === 'stats') await showStatistics(crumbs);
  }
}

// ── App entry point: mode selection loop ────────────────────────────────

export async function mainMenu() {
  setAppVersion(getOptions().app_version);
  while (true) {
    const mode = await pickCreationMode();
    if (!mode) break;
    getCfgStore().setLocal('WORD_SOURCE', mode);
    await modeMainMenu(mode);
  }
}

