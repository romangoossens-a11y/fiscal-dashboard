// Copy pinned vendor files and the Inter font from node_modules into assets/,
// so the live page loads nothing from third party CDNs.
import { copyFileSync, mkdirSync } from 'node:fs';

const copies = [
  ['node_modules/alpinejs/dist/cdn.min.js', 'assets/vendor/alpine.min.js'],
  ['node_modules/chart.js/dist/chart.umd.js', 'assets/vendor/chart.umd.js'],
];
for (const w of [300, 400, 500, 600, 700]) {
  copies.push([`node_modules/@fontsource/inter/files/inter-latin-${w}-normal.woff2`,
               `assets/fonts/inter-latin-${w}-normal.woff2`]);
}

mkdirSync('assets/vendor', { recursive: true });
mkdirSync('assets/fonts', { recursive: true });
for (const [from, to] of copies) {
  copyFileSync(from, to);
  console.log(`${from} -> ${to}`);
}
