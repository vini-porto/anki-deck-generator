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

// ── Shared header data ──────────────────────────────────────────────────

function bannerSummary() {
  const cfg = getCfgStore().get();
  const options = getOptions();
  const provider = cfg.AI_PROVIDER;
  const providerLabel = options.provider_labels[provider] || provider;
  const modelField = options.provider_model_field[provider] || 'AI_MODEL';
  const model = cfg[modelField] || '';
  return `${String(cfg.SOURCE_LANG).toUpperCase()} -> ${cfg.TARGET_LANG}   ·   ${cfg.CARD_TEMPLATE} / ${cfg.CARD_TYPE}   ·   ${providerLabel} (${model})`;
}

function aiKeyMissing() {
  const cfg = getCfgStore().get();
  const options = getOptions();
  const keyField = options.provider_key_field[cfg.AI_PROVIDER];
  if (!keyField) return false; // ollama needs no key
  return String(cfg[keyField] || '').startsWith('your_');
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
      textItem('Giphy API key', 'GIPHY_API_KEY', { secret: true }),
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

async function settingsDeck(crumbs) {
  const options = getOptions();
  const trail = [...crumbs, 'Deck & cards'];
  const items = [
    textItem('Deck name', 'DECK_NAME'),
    pickerItem('Card template', 'CARD_TEMPLATE', options.templates),
    textItem('Output — new deck', 'DECK_OUTPUT_NEW'),
    textItem('Output — full deck', 'DECK_OUTPUT_FULL'),
    separatorItem(),
    backItem(),
  ];
  await runScreen({ title: 'Deck & Card Settings', breadcrumb: trail, summary: bannerSummary(), items });
}

async function settingsGeneration(crumbs) {
  const options = getOptions();
  const trail = [...crumbs, 'Generation'];
  const items = [
    numberItem('Words per run', 'WORDS_PER_RUN', { minVal: 1, step: 5 }),
    numberItem('Total word pool', 'TOTAL_WORD_POOL', { minVal: 100, step: 100 }),
    separatorItem(),
    pickerItem('Meaning exhaustiveness', 'MEANING_EXHAUSTIVENESS', options.meaning_exhaustiveness_options),
    separatorItem(),
    pickerItem('Word source', 'WORD_SOURCE', options.word_sources),
    textItem('Markdown notes folder', 'MARKDOWN_NOTES_PATH'),
    pickerItem('Markdown extraction', 'MARKDOWN_EXTRACTION_MODE', options.markdown_extraction_modes),
    separatorItem(),
    backItem(),
  ];
  await runScreen({ title: 'Generation Settings', breadcrumb: trail, summary: bannerSummary(), items });
}

// ── Card content — guided flow: "Word or phrase?" then "how tested?" ───
// CREATION_MODE stays the one stored setting; CARD_TYPE joins it only for
// the word_meaning-family testing styles. See CLAUDE.md § Creation modes.

const WORD_FAMILY_MODES = new Set(['word_meaning', 'audio_meaning', 'audio_writing', 'audio_typing']);
const PHRASE_FAMILY_MODES = new Set([
  'phrase_context', 'phrase_native_writing', 'phrase_audio_recognition', 'phrase_audio_typing',
]);

function wordContentHint() {
  const c = getCfgStore().get();
  if (!WORD_FAMILY_MODES.has(c.CREATION_MODE)) return '';
  const key = c.CREATION_MODE === 'word_meaning' ? `word_meaning:${c.CARD_TYPE}` : c.CREATION_MODE;
  const options = getOptions();
  const match = options.word_testing_options.find(([v]) => v === key);
  return match ? match[1] : c.CREATION_MODE;
}

function phraseContentHint() {
  const c = getCfgStore().get();
  if (!PHRASE_FAMILY_MODES.has(c.CREATION_MODE)) return '';
  const options = getOptions();
  const match = options.phrase_testing_options.find(([v]) => v === c.CREATION_MODE);
  return match ? match[1] : '';
}

// Hand-built (not pickerItem()) since selecting a word_meaning-family
// option needs to write BOTH CREATION_MODE and CARD_TYPE from one choice —
// pickerItem()'s factory only ever writes a single config key.
function wordTestingItem() {
  const store = getCfgStore();
  const options = getOptions().word_testing_options;
  return {
    kind: 'picker',
    label: 'How do you want to be tested?',
    options,
    getValue: () => {
      const cfg = store.get();
      return cfg.CREATION_MODE === 'word_meaning' ? `word_meaning:${cfg.CARD_TYPE}` : cfg.CREATION_MODE;
    },
    setValue: async (v) => {
      if (v.includes(':')) {
        const [mode, cardType] = v.split(':');
        await store.set('CREATION_MODE', mode, 'str');
        await store.set('CARD_TYPE', cardType, 'str');
      } else {
        await store.set('CREATION_MODE', v, 'str');
      }
    },
  };
}

async function wordContentMenu(crumbs) {
  const trail = [...crumbs, 'Word-based cards'];
  const items = [wordTestingItem(), separatorItem(), backItem()];
  await runScreen({ title: 'Word-Based Cards', breadcrumb: trail, summary: bannerSummary(), items });
}

async function phraseContentMenu(crumbs) {
  const options = getOptions();
  const trail = [...crumbs, 'Phrase-based cards'];
  const items = [
    pickerItem('How do you want to be tested?', 'CREATION_MODE', options.phrase_testing_options),
    separatorItem(),
    backItem(),
  ];
  await runScreen({ title: 'Phrase-Based Cards', breadcrumb: trail, summary: bannerSummary(), items });
}

async function cardContentMenu(crumbs) {
  const options = getOptions();
  const trail = [...crumbs, 'Card content'];
  while (true) {
    const items = [
      actionItem('Word-based cards', 'word', wordContentHint),
      actionItem('Phrase-based cards', 'phrase', phraseContentHint),
      separatorItem(),
      pickerItem('Field verbosity', 'CREATION_MODE_VERBOSITY', options.creation_mode_verbosity_options),
      separatorItem(),
      backItem(),
    ];
    const choice = await runScreen({ title: 'Card Content', breadcrumb: trail, summary: bannerSummary(), items });
    if (choice === undefined || choice === 'back') return;
    if (choice === 'word') await wordContentMenu(trail);
    else if (choice === 'phrase') await phraseContentMenu(trail);
  }
}

function pocketTtsVoiceOptions(langCode) {
  const options = getOptions();
  const pocketLang = options.pocket_tts_lang_map[langCode] || 'english';
  const voices = options.pocket_tts_voices[pocketLang] || options.pocket_tts_voices.english;
  return voices.map((v) => [v, v.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())]);
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

async function settingsAudio(crumbs) {
  const options = getOptions();
  const trail = [...crumbs, 'Audio'];
  while (true) {
    const items = [
      toggleItem('Enable audio (master switch)', 'ENABLE_AUDIO'),
      separatorItem(),
      toggleItem('Word pronunciation audio', 'ENABLE_WORD_AUDIO'),
      toggleItem('Example sentence audio', 'ENABLE_EXAMPLE_AUDIO'),
      toggleItem('Meaning audio (native lang)', 'ENABLE_MEANING_AUDIO'),
      separatorItem(),
      pickerItem('TTS provider', 'TTS_PROVIDER', options.tts_providers),
      actionItem('Pocket TTS settings', 'pocket_tts', () => {
        const c = getCfgStore().get();
        return c.TTS_PROVIDER === 'pocket_tts' ? `${c.POCKET_TTS_VOICE_SOURCE} / ${c.POCKET_TTS_VOICE_TARGET}` : 'n/a — gTTS selected';
      }),
      separatorItem(),
      backItem(),
    ];
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

async function settingsMain(crumbs) {
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
      actionItem('Card content', 'cardcontent', () => wordContentHint() || phraseContentHint()),
      actionItem('Deck & cards', 'deck', () => getCfgStore().get().CARD_TEMPLATE),
      actionItem('Generation', 'generation', () => {
        const c = getCfgStore().get();
        return `${c.WORDS_PER_RUN}/run   pool ${c.TOTAL_WORD_POOL}   meanings: ${c.MEANING_EXHAUSTIVENESS}`;
      }),
      actionItem('Audio', 'audio', () => (getCfgStore().get().ENABLE_AUDIO ? 'ON' : 'OFF')),
      actionItem('GIF', 'gif', () => {
        const c = getCfgStore().get();
        return `${c.ENABLE_GIF ? 'ON' : 'OFF'}  |  rating: ${c.GIF_RATING}`;
      }),
      actionItem('Rate limits', 'ratelimits', () => {
        const c = getCfgStore().get();
        return `AI ${c.DELAY_AI}s  Giphy ${c.DELAY_GIPHY}s  TTS ${c.DELAY_TTS}s`;
      }),
      separatorItem(),
      backItem('Back to main menu'),
    ];
    const choice = await runScreen({ title: 'Configure Settings', breadcrumb: trail, summary: bannerSummary(), items });
    if (choice === undefined || choice === 'back') return;
    if (choice === 'language') await settingsLanguage(trail);
    else if (choice === 'ai') await settingsAi(trail);
    else if (choice === 'cardcontent') await cardContentMenu(trail);
    else if (choice === 'deck') await settingsDeck(trail);
    else if (choice === 'generation') await settingsGeneration(trail);
    else if (choice === 'audio') await settingsAudio(trail);
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

const CARD_TYPE_INFO = [
  [
    'Basic',
    [
      'The classic format. Front shows the word, IPA,',
      'GIF and example sentence. Back reveals the meaning.',
      'Best for recognition practice.',
    ],
  ],
  [
    'Basic + Reversed',
    [
      'Creates 2 Anki cards per note. Card 1 is the usual',
      'word->meaning. Card 2 flips it: you see the English',
      'definition and must recall the foreign word.',
    ],
  ],
  [
    'Type in Answer',
    [
      'Front shows the meaning and the example in your native',
      'language. You TYPE the foreign word. Anki checks your',
      'spelling and highlights any mistakes.',
    ],
  ],
  [
    'Cloze',
    [
      'The example sentence is shown with the target word',
      'blanked out: "Elle est tres ___."  You fill the gap.',
      'Great for learning words in context.',
    ],
  ],
];

async function showCardTypeGuide(crumbs) {
  const trail = [...crumbs, 'Card type guide'];
  const body = [];
  CARD_TYPE_INFO.forEach(([title, lines], i) => {
    if (i > 0) body.push('');
    body.push(styles.warningBold.render(`[${i + 1}] ${title}`));
    for (const line of lines) body.push(styles.muted.render('    ' + line));
  });
  await staticScreen({ title: 'Card Types — How They Work', breadcrumb: trail, summary: bannerSummary(), body });
}

// ── Export flow: JS-native card-type picker, then delegate to Python ───

async function runExportFlow(crumbs) {
  const trail = [...crumbs, 'Export decks'];
  const cfg = getCfgStore().get();
  const choices = [
    ['basic', 'Basic', 'Word -> Meaning  |  Classic recognition card'],
    ['basic_reversed', 'Basic + Reversed', 'Word <-> Meaning  |  2 cards per note (recognition + recall)'],
    ['type_answer', 'Type in Answer', 'Definition shown -> user types the word'],
    ['cloze', 'Cloze', 'Fill in the blank in the example sentence'],
    [null, 'Use config.py default', `Current value: ${cfg.CARD_TYPE}`],
  ];

  const items = [
    ...choices.map(([, label, desc], i) => actionItem(label, `type:${i}`, desc)),
    separatorItem(),
    backItem('Cancel'),
  ];

  const choice = await runScreen({ title: 'Select Card Type for Export', breadcrumb: trail, summary: bannerSummary(), items });
  if (choice === undefined || choice === 'back') return;

  const cardType = choices[Number(choice.split(':')[1])][0];
  runSubprocess(() => bridge.export(cardType || undefined));
}

// ── Main menu ────────────────────────────────────────────────────────

export async function mainMenu() {
  setAppVersion(getOptions().app_version);
  const crumbs = ['Main Menu'];
  while (true) {
    const items = [
      actionItem('Generate new cards', 'generate', () => `Up to ${getCfgStore().get().WORDS_PER_RUN} words from the frequency list`),
      actionItem('Export decks', 'export', 'Build .apkg  —  choose card type before exporting'),
      actionItem('Configure', 'configure', () => {
        const c = getCfgStore().get();
        return `${String(c.SOURCE_LANG).toUpperCase()} -> ${c.TARGET_LANG}`;
      }),
      actionItem('Statistics', 'stats', 'Card counts, POS breakdown, export history'),
      actionItem('Card type guide', 'guide', 'Basic / Reversed / Type / Cloze'),
      separatorItem(),
      backItem('Exit'),
    ];
    const choice = await runScreen({ title: 'Main Menu', breadcrumb: crumbs, summary: bannerSummary(), items });
    if (choice === undefined || choice === 'back') break;
    if (choice === 'generate') runSubprocess(() => bridge.generate());
    else if (choice === 'export') await runExportFlow(crumbs);
    else if (choice === 'configure') await settingsMain(crumbs);
    else if (choice === 'stats') await showStatistics(crumbs);
    else if (choice === 'guide') await showCardTypeGuide(crumbs);
  }
}
