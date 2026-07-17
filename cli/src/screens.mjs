// Screen definitions — mirrors main.py's own grouping (main menu, export
// card-type picker, configure_* settings screens, statistics, card type
// guide). Settings screens read/write config.py exclusively through the
// bridge, never touching any file directly.

import { bridge } from './bridge.mjs';
import { runMenu, enableRawMode, disableRawMode, clearScreen, paint, nextKey, renderBanner } from './ui.mjs';
import { Action, Toggle, Picker, TextInput, NumberInput, Separator, Back } from './components.mjs';

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

function storeBinding() {
  const store = getCfgStore();
  return { getConfig: () => store.get(), setConfig: (k, v, t) => store.set(k, v, t) };
}

function bannerData() {
  const cfg = getCfgStore().get();
  const options = getOptions();
  const provider = cfg.AI_PROVIDER;
  const providerLabel = options.provider_labels[provider] || provider;
  const modelField = options.provider_model_field[provider] || 'AI_MODEL';
  return { cfg, providerLabel, currentModel: cfg[modelField] || '' };
}

function aiKeyMissing() {
  const cfg = getCfgStore().get();
  const options = getOptions();
  const keyField = options.provider_key_field[cfg.AI_PROVIDER];
  if (!keyField) return false; // ollama needs no key
  return String(cfg[keyField] || '').startsWith('your_');
}

// ── Settings screens (mirrors main.py's configure_* functions) ─────────

async function providerSettings() {
  const sb = storeBinding();
  const options = getOptions();
  const provider = getCfgStore().get().AI_PROVIDER;

  if (provider === 'groq') {
    await runMenu('Groq Settings', [
      new Picker('AI model', 'AI_MODEL', options.groq_models, sb),
      new TextInput('Groq API key', 'GROQ_API_KEY', { ...sb, secret: true }),
      new Separator(),
      new Back(),
    ], bannerData);
  } else if (provider === 'openai') {
    await runMenu('OpenAI Settings', [
      new TextInput('AI model', 'OPENAI_MODEL', sb),
      new TextInput('OpenAI API key', 'OPENAI_API_KEY', { ...sb, secret: true }),
      new Separator(),
      new Back(),
    ], bannerData);
  } else if (provider === 'anthropic') {
    await runMenu('Claude (Anthropic) Settings', [
      new Picker('AI model', 'ANTHROPIC_MODEL', options.anthropic_models, sb),
      new TextInput('Anthropic API key', 'ANTHROPIC_API_KEY', { ...sb, secret: true }),
      new Separator(),
      new Back(),
    ], bannerData);
  } else if (provider === 'gemini') {
    await runMenu('Gemini Settings', [
      new TextInput('AI model', 'GEMINI_MODEL', sb),
      new TextInput('Gemini API key', 'GEMINI_API_KEY', { ...sb, secret: true }),
      new Separator(),
      new Back(),
    ], bannerData);
  } else {
    await runMenu('Ollama Settings', [
      new TextInput('AI model', 'OLLAMA_MODEL', sb),
      new TextInput('Ollama server address', 'OLLAMA_HOST', sb),
      new Separator(),
      new Back(),
    ], bannerData);
  }
}

async function settingsAi() {
  const sb = storeBinding();
  const options = getOptions();
  await runMenu('AI & API Settings', [
    new Picker('AI provider', 'AI_PROVIDER', options.ai_providers, sb),
    new Action('Provider settings', providerSettings, () => {
      const cfg = getCfgStore().get();
      const label = options.provider_labels[cfg.AI_PROVIDER] || cfg.AI_PROVIDER;
      const modelField = options.provider_model_field[cfg.AI_PROVIDER] || 'AI_MODEL';
      const model = cfg[modelField] || '';
      return `${label}  |  ${model}` + (aiKeyMissing() ? '   ! key missing' : '');
    }),
    new Separator(),
    new TextInput('Giphy API key', 'GIPHY_API_KEY', { ...sb, secret: true }),
    new Separator(),
    new Back(),
  ], bannerData);
}

async function settingsLanguage() {
  const sb = storeBinding();
  await runMenu('Language Settings', [
    new TextInput('Language to learn', 'SOURCE_LANG', sb),
    new TextInput('Native language', 'TARGET_LANG', sb),
    new TextInput('TTS source lang (gTTS)', 'TTS_SOURCE_LANG', sb),
    new TextInput('TTS native lang (gTTS)', 'TTS_TARGET_LANG', sb),
    new Separator(),
    new Back(),
  ], bannerData);
}

async function settingsDeck() {
  const sb = storeBinding();
  const options = getOptions();
  await runMenu('Deck & Card Settings', [
    new TextInput('Deck name', 'DECK_NAME', sb),
    new Picker('Card template', 'CARD_TEMPLATE', options.templates, sb),
    new Picker('Card type', 'CARD_TYPE', options.card_types, sb),
    new TextInput('Output — new deck', 'DECK_OUTPUT_NEW', sb),
    new TextInput('Output — full deck', 'DECK_OUTPUT_FULL', sb),
    new Separator(),
    new Back(),
  ], bannerData);
}

async function settingsGeneration() {
  const sb = storeBinding();
  await runMenu('Generation Settings', [
    new NumberInput('Words per run', 'WORDS_PER_RUN', { ...sb, minVal: 1, step: 5 }),
    new NumberInput('Total word pool', 'TOTAL_WORD_POOL', { ...sb, minVal: 100, step: 100 }),
    new Separator(),
    new Back(),
  ], bannerData);
}

async function settingsAudio() {
  const sb = storeBinding();
  await runMenu('Audio Settings', [
    new Toggle('Enable audio (master switch)', 'ENABLE_AUDIO', sb),
    new Separator(),
    new Toggle('Word pronunciation audio', 'ENABLE_WORD_AUDIO', sb),
    new Toggle('Example sentence audio', 'ENABLE_EXAMPLE_AUDIO', sb),
    new Toggle('Meaning audio (native lang)', 'ENABLE_MEANING_AUDIO', sb),
    new Separator(),
    new Back(),
  ], bannerData);
}

async function settingsGif() {
  const sb = storeBinding();
  const options = getOptions();
  await runMenu('GIF Settings', [
    new Toggle('Enable GIF (Giphy)', 'ENABLE_GIF', sb),
    new Picker('Content rating filter', 'GIF_RATING', options.gif_ratings, sb),
    new Separator(),
    new Back(),
  ], bannerData);
}

async function settingsRateLimits() {
  const sb = storeBinding();
  await runMenu('Rate Limiting  (seconds between API calls)', [
    new NumberInput('AI delay', 'DELAY_AI', { ...sb, minVal: 0, step: 0.1, isFloat: true }),
    new NumberInput('Giphy delay', 'DELAY_GIPHY', { ...sb, minVal: 0, step: 0.1, isFloat: true }),
    new NumberInput('gTTS delay', 'DELAY_TTS', { ...sb, minVal: 0, step: 0.1, isFloat: true }),
    new Separator(),
    new Back(),
  ], bannerData);
}

async function settingsMain() {
  await runMenu('Configure Settings', [
    new Action('Language', settingsLanguage, () => {
      const cfg = getCfgStore().get();
      return `${String(cfg.SOURCE_LANG).toUpperCase()} -> ${cfg.TARGET_LANG}`;
    }),
    new Action('AI & API keys', settingsAi, () => {
      const cfg = getCfgStore().get();
      const label = getOptions().provider_labels[cfg.AI_PROVIDER] || cfg.AI_PROVIDER;
      return label + (aiKeyMissing() ? '  ! key missing' : '');
    }),
    new Action('Deck & cards', settingsDeck, () => {
      const cfg = getCfgStore().get();
      return `${cfg.CARD_TEMPLATE}  |  ${cfg.CARD_TYPE}`;
    }),
    new Action('Generation', settingsGeneration, () => {
      const cfg = getCfgStore().get();
      return `${cfg.WORDS_PER_RUN}/run   pool ${cfg.TOTAL_WORD_POOL}`;
    }),
    new Action('Audio', settingsAudio, () => (getCfgStore().get().ENABLE_AUDIO ? 'ON' : 'OFF')),
    new Action('GIF', settingsGif, () => {
      const cfg = getCfgStore().get();
      return `${cfg.ENABLE_GIF ? 'ON' : 'OFF'}  |  rating: ${cfg.GIF_RATING}`;
    }),
    new Action('Rate limits', settingsRateLimits, () => {
      const cfg = getCfgStore().get();
      return `AI ${cfg.DELAY_AI}s  Giphy ${cfg.DELAY_GIPHY}s  TTS ${cfg.DELAY_TTS}s`;
    }),
    new Separator(),
    new Back('Back to main menu'),
  ], bannerData);
}

// ── Statistics & card type guide (static prints, mirrors print_mode) ───

async function showStatistics() {
  const stats = bridge.stats();
  clearScreen();
  process.stdout.write(renderBanner(bannerData()) + '\n\n');
  process.stdout.write(paint('  Statistics', 'bold', 'cyan') + '\n');
  process.stdout.write(paint('  ' + '─'.repeat(52), 'dim') + '\n\n');

  process.stdout.write(`  Total cards     : ${paint(String(stats.total), 'yellow', 'bold')}\n`);
  process.stdout.write(`  Exported        : ${paint(String(stats.exported), 'green')}\n`);
  process.stdout.write(`  Pending export  : ${paint(String(stats.pending), 'cyan')}\n\n`);

  if (stats.by_pos.length) {
    process.stdout.write(paint('  By Part of Speech:', 'bold') + '\n');
    for (const { pos, count } of stats.by_pos) {
      const bar = paint('█'.repeat(Math.min(count, 28)), 'blue');
      process.stdout.write(`  ${(pos + ':').padEnd(16)} ${paint(String(count).padStart(4), 'yellow')}  ${bar}\n`);
    }
    process.stdout.write('\n');
  }

  if (stats.recent_days.length) {
    process.stdout.write(paint('  Cards added (last 7 sessions):', 'bold') + '\n');
    for (const { date, count } of stats.recent_days) {
      process.stdout.write(`  ${date}   ${paint(count + ' cards', 'green')}\n`);
    }
    process.stdout.write('\n');
  }

  if (stats.recent_exports.length) {
    process.stdout.write(paint('  Recent exports:', 'bold') + '\n');
    for (const { date, type, count } of stats.recent_exports) {
      process.stdout.write(`  ${date.slice(0, 16)}  ${String(type).padEnd(22)}  ${paint(count + ' cards', 'cyan')}\n`);
    }
    process.stdout.write('\n');
  }

  process.stdout.write(paint('  Press any key to continue...', 'dim') + '\n');
  await nextKey();
}

const CARD_TYPE_INFO = [
  ['Basic', [
    'The classic format. Front shows the word, IPA,',
    'GIF and example sentence. Back reveals the meaning.',
    'Best for recognition practice.',
  ]],
  ['Basic + Reversed', [
    'Creates 2 Anki cards per note. Card 1 is the usual',
    'word->meaning. Card 2 flips it: you see the English',
    'definition and must recall the foreign word.',
  ]],
  ['Type in Answer', [
    'Front shows the meaning and the example in your native',
    'language. You TYPE the foreign word. Anki checks your',
    'spelling and highlights any mistakes.',
  ]],
  ['Cloze', [
    'The example sentence is shown with the target word',
    'blanked out: "Elle est tres ___."  You fill the gap.',
    'Great for learning words in context.',
  ]],
];

async function showCardTypeGuide() {
  clearScreen();
  process.stdout.write(renderBanner(bannerData()) + '\n\n');
  process.stdout.write(paint('  Card Types — How They Work', 'bold', 'cyan') + '\n');
  process.stdout.write(paint('  ' + '─'.repeat(52), 'dim') + '\n');
  CARD_TYPE_INFO.forEach(([title, lines], i) => {
    process.stdout.write(`\n  ${paint(`[${i + 1}] ${title}`, 'yellow', 'bold')}\n`);
    for (const line of lines) process.stdout.write(`      ${paint(line, 'dim')}\n`);
  });
  process.stdout.write('\n' + paint('  Press any key to continue...', 'dim') + '\n');
  await nextKey();
}

// ── Export flow: JS-native card-type picker, then delegate to Python ───

async function runExportFlow() {
  const cfg = getCfgStore().get();
  const choices = [
    ['basic', 'Basic', 'Word -> Meaning  |  Classic recognition card'],
    ['basic_reversed', 'Basic + Reversed', 'Word <-> Meaning  |  2 cards per note (recognition + recall)'],
    ['type_answer', 'Type in Answer', 'Definition shown -> user types the word'],
    ['cloze', 'Cloze', 'Fill in the blank in the example sentence'],
    [null, 'Use config.py default', `Current value: ${cfg.CARD_TYPE}`],
  ];

  let chosen;
  const items = choices.map(
    ([value, label, desc]) => new Action(label, () => { chosen = value; return 'back'; }, desc),
  );
  items.push(new Separator(), new Back('Cancel'));

  await runMenu('Select Card Type for Export', items, bannerData);
  if (chosen === undefined) return; // cancelled via Back/Esc

  disableRawMode();
  bridge.export(chosen || undefined);
  enableRawMode();
}

// ── Main menu ────────────────────────────────────────────────────────

export async function mainMenu() {
  await runMenu('Main Menu', [
    new Action('Generate new cards', async () => {
      disableRawMode();
      bridge.generate();
      enableRawMode();
    }, () => `Up to ${getCfgStore().get().WORDS_PER_RUN} words from the frequency list`),
    new Action('Export decks', runExportFlow, 'Build .apkg  —  choose card type before exporting'),
    new Action('Configure', settingsMain, () => {
      const cfg = getCfgStore().get();
      return `${String(cfg.SOURCE_LANG).toUpperCase()} -> ${cfg.TARGET_LANG}`;
    }),
    new Action('Statistics', showStatistics, 'Card counts, POS breakdown, export history'),
    new Action('Card type guide', showCardTypeGuide, 'Basic / Reversed / Type / Cloze'),
    new Separator(),
    new Back('Exit'),
  ], bannerData);
}
