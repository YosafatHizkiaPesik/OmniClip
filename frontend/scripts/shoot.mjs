/**
 * Potret layar untuk putaran pemeriksaan.
 *
 * Firefox `--screenshot` menembak pada peristiwa `load`, sebelum React sempat
 * mengambil datanya — jadi setiap potret rute yang memuat data hanya
 * memperlihatkan pemuat berputar. Di sini halamannya benar-benar ditunggu
 * sampai jaringannya sunyi, gerak masuk diendapkan, lalu diperiksa isinya
 * sebelum berkasnya dianggap sah.
 */
import { firefox } from 'playwright';
import { mkdir } from 'node:fs/promises';

const BASE = process.env.BASE ?? 'http://localhost:5173';
const OUT = process.env.OUT ?? '.impeccable/review';
const ROUTES = [
  ['home', '/'],
  ['watch', '/watch/dSq0Z5XpoLc'],
  ['studio', '/studio'],
  ['editor', '/studio/dSq0Z5XpoLc'],
  ['clips', '/clips'],
  ['downloads', '/downloads'],
  ['settings', '/settings'],
];
const SIZES = [['desktop', 1440, 1000], ['mobile', 390, 844]];

await mkdir(OUT, { recursive: true });
const browser = await firefox.launch();
const only = process.argv.slice(2);
let bad = 0;

for (const [size, width, height] of SIZES) {
  const ctx = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 1,
    reducedMotion: 'reduce',      // gerak masuk diendapkan: elemen yang masih
                                  // beranimasi terbaca sebagai elemen hilang
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
  page.on('pageerror', (e) => errors.push(`PAGEERROR ${String(e).slice(0, 160)}`));

  for (const [name, path] of ROUTES) {
    if (only.length && !only.includes(name)) continue;
    errors.length = 0;
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle', { timeout: 25000 }).catch(() => {});
    await page.waitForTimeout(900);
    const file = `${OUT}/${name}-${size}.png`;
    await page.screenshot({ path: file, fullPage: size === 'desktop' });
    // Sahkan: halaman kosong atau masih memuat bukan bukti apa pun.
    const text = (await page.locator('body').innerText()).trim();
    const loading = /Membuka partitur|Memuat/i.test(text) && text.length < 120;
    const status = loading ? 'MASIH MEMUAT' : text.length < 40 ? 'HAMPIR KOSONG' : 'ok';
    if (status !== 'ok') bad += 1;
    console.log(`${status === 'ok' ? ' ok  ' : 'GAGAL'} ${name}-${size}  ${text.length} char`
      + (errors.length ? `  · ${errors.length} galat konsol: ${errors[0]}` : ''));
  }
  await ctx.close();
}
await browser.close();
process.exit(bad ? 1 : 0);
