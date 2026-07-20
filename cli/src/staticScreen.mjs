// Read-only page (Statistics, Card Type Guide): header + pre-built body
// lines + "press any key" footer. `body` is an array of already-styled
// strings (built by screens.mjs via theme.mjs helpers).

import { nextKey, isExitCombo, clearScreen } from './term.mjs';
import { buildHeader, buildFooter, frame } from './render.mjs';
import { styles } from './theme.mjs';

export async function staticScreen({ title, breadcrumb = [], summary = '', body = [] }) {
  clearScreen();
  const lines = [
    buildHeader({ breadcrumb, summary }),
    '',
    styles.accentBold.render(title),
    '',
    ...body,
    '',
    buildFooter(['Press any key to continue']),
  ];
  process.stdout.write(frame(lines));

  const key = await nextKey();
  if (isExitCombo(key)) {
    clearScreen();
    process.exit(0);
  }
  return 'back';
}
