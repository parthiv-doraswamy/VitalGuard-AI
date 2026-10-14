// Regenerates the PWA icons from public/icons/icon.svg (needs @playwright/test + Chromium installed).
//   npm install --no-save @playwright/test@1.56.1 && npx playwright install chromium && node scripts/generate-icons.mjs
import { readFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const svg = readFileSync(new URL('../public/icons/icon.svg', import.meta.url), 'utf8');
// Maskable: full-bleed background, artwork scaled into the central 80% safe zone.
const maskable = svg
  .replace('rx="112"', 'rx="0"')
  .replace('<polyline', '<g transform="translate(51.2 51.2) scale(0.8)"><polyline')
  .replace('<circle cx="404" cy="122" r="30" fill="#5eead4"/>', '<circle cx="404" cy="122" r="30" fill="#5eead4"/></g>');
const outputs = [
  ['icon-192.png', 192, svg], ['icon-512.png', 512, svg], ['icon-maskable-512.png', 512, maskable],
  ['apple-touch-icon-180.png', 180, maskable], ['favicon-32.png', 32, svg],
];
const browser = await chromium.launch();
const page = await browser.newPage();
for (const [name, size, source] of outputs) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<html><body style="margin:0;background:transparent">${source.replace('<svg ', `<svg width="${size}" height="${size}" `)}</body></html>`);
  await page.locator('svg').screenshot({ path: new URL(`../public/icons/${name}`, import.meta.url).pathname, omitBackground: true });
}
await browser.close();
console.log('icons written to public/icons/');
