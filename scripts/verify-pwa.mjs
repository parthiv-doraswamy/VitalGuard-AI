// Verifies the production build's PWA output. Run after `npm run build`:  node scripts/verify-pwa.mjs
// Fails (exit 1) on an invalid manifest, wrong icon sizes, duplicate precache entries,
// unexpected runtime caching, or anything that could cache API responses.
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const dist = new URL('../dist/', import.meta.url).pathname;
const failures = [];
const check = (condition, message) => { if (!condition) failures.push(message); };

const manifest = JSON.parse(readFileSync(join(dist, 'manifest.webmanifest'), 'utf8'));
for (const field of ['name', 'short_name', 'start_url', 'scope', 'display', 'icons', 'theme_color', 'background_color']) {
  check(manifest[field], `manifest.${field} missing`);
}
check(manifest.display === 'standalone', 'manifest.display must be standalone');
check(manifest.start_url.startsWith(manifest.scope), 'start_url must be inside scope');
for (const icon of manifest.icons.filter((item) => item.type === 'image/png')) {
  const path = join(dist, icon.src);
  if (!existsSync(path)) { failures.push(`icon missing: ${icon.src}`); continue; }
  const bytes = readFileSync(path);
  const actual = `${bytes.readUInt32BE(16)}x${bytes.readUInt32BE(20)}`;
  check(bytes.subarray(1, 4).toString() === 'PNG', `${icon.src} is not a PNG`);
  check(actual === icon.sizes, `${icon.src} is ${actual}, manifest says ${icon.sizes}`);
}
const purposes = manifest.icons.map((icon) => icon.purpose);
check(manifest.icons.some((icon) => icon.sizes === '192x192'), 'needs a 192x192 icon');
check(manifest.icons.some((icon) => icon.sizes === '512x512'), 'needs a 512x512 icon');
check(purposes.includes('maskable'), 'needs a maskable icon');

const html = readFileSync(join(dist, 'index.html'), 'utf8');
check(html.includes('rel="manifest"'), 'index.html must link the manifest');

check(existsSync(join(dist, 'sw.js')), 'dist/sw.js missing');
const workers = readdirSync(dist).filter((name) => /^(sw|service-worker).*\.js$/.test(name));
check(workers.length === 1, `exactly one service worker expected, found ${workers.join(', ')}`);
const sw = readFileSync(join(dist, 'sw.js'), 'utf8');
const precached = [...sw.matchAll(/url:"([^"]+)"/g)].map((match) => match[1]);
check(precached.length > 0, 'nothing precached');
check(new Set(precached).size === precached.length, 'duplicate precache entries');
check(precached.includes('index.html'), 'app shell (index.html) not precached');
check(!precached.some((url) => /api|\.json$/i.test(url)), 'API-like URLs must not be precached');
const routes = [...sw.matchAll(/registerRoute\((\/[^,]+\/),/g)].map((match) => match[1]);
check(routes.every((route) => route.includes('fonts')), `only font runtime routes are allowed, found ${routes.join(' ')}`);
check(sw.includes('denylist:[/^\\/api\\//]'), 'navigation fallback must exclude /api/');

const registrations = readdirSync(join(dist, 'assets')).filter((name) => name.endsWith('.js'))
  .map((name) => (readFileSync(join(dist, 'assets', name), 'utf8').match(/serviceWorker\.register\(/g) || []).length)
  .reduce((sum, count) => sum + count, 0);
check(registrations <= 1, `service worker registered from ${registrations} call sites`);

if (failures.length) {
  console.error('PWA verification FAILED:\n - ' + failures.join('\n - '));
  process.exit(1);
}
console.log(`PWA verification passed: ${precached.length} precached entries, runtime routes: ${routes.length} (fonts only), 1 service worker.`);
