// Add a content fingerprint to every local asset link in index.html, for
// example assets/app.js?v=1a2b3c4d. GitHub Pages lets browsers cache files
// for ten minutes, so without this a visitor could get a new index.html with
// an old app.js right after a deploy. Runs last in `npm run build`.
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';

const assets = ['assets/app.css', 'assets/app.js', 'assets/vendor/chart.umd.js', 'assets/vendor/alpine.min.js'];
let html = readFileSync('index.html', 'utf8');
for (const path of assets) {
  const hash = createHash('sha256').update(readFileSync(path)).digest('hex').slice(0, 8);
  const pattern = new RegExp(`(["'])${path.replace(/[.]/g, '\\.')}(\\?v=[0-9a-f]+)?\\1`, 'g');
  if (!pattern.test(html)) throw new Error(`${path} is not referenced in index.html`);
  html = html.replace(pattern, `$1${path}?v=${hash}$1`);
}
writeFileSync('index.html', html);
console.log('index.html asset links stamped');
