/**
 * Membundel komposisi Montase untuk dirender (dijalankan di CI dan saat
 * pengembangan, tidak di komputer pengguna).
 *
 *   node src/bundel.mjs [folder-keluar]      bawaan: dist/bundel
 *
 * Komposisinya tinggal di frontend/, dan dari sana `react`, `remotion`, dan
 * kawan-kawan akan ditemukan di frontend/node_modules. Dua salinan Remotion di
 * satu bundel membuat konteks React-nya hilang ("No video config found"), jadi
 * semua paket yang boleh diimpor komposisi DIPAKSA ke node_modules mesin ini.
 * Versinya dipatok sama persis dengan frontend (JOB-4.md, aturan Remotion).
 *
 * Bundelnya ditambah satu Content-Security-Policy: kode di dalam halaman
 * render (termasuk komponen buatan AI) hanya boleh menghubungi server bundel
 * itu sendiri dan alamat bertoken OmniClip. Lihat sisipkanCsp().
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { bundle } from '@remotion/bundler';

const AKAR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);

const DIPAKSA = ['react', 'react-dom', 'remotion', '@remotion/media', 'zod'];

function folderPaket(nama) {
  return path.dirname(require.resolve(`${nama}/package.json`));
}

/**
 * Kebijakan untuk halaman render. `'unsafe-eval'` dibutuhkan muatKomponen.js
 * (new Function); jaringan dibatasi ke asal halaman sendiri dan OmniClip di
 * 127.0.0.1 / localhost, jalur bertoken Montase saja.
 */
export function sisipkanCsp(folder) {
  const berkas = path.join(folder, 'index.html');
  const html = fs.readFileSync(berkas, 'utf8');
  if (html.includes('Content-Security-Policy')) return;
  const omniclip = 'http://127.0.0.1:* http://localhost:*';
  const kebijakan = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data: blob: ${omniclip}`,
    `media-src 'self' data: blob: ${omniclip}`,
    `connect-src 'self' data: blob: ${omniclip} ws://localhost:* ws://127.0.0.1:*`,
    `font-src 'self' data: ${omniclip}`,
    "worker-src 'self' blob:",
  ].join('; ');
  const meta = `<meta http-equiv="Content-Security-Policy" content="${kebijakan}">`;
  fs.writeFileSync(berkas, html.replace('<head>', `<head>${meta}`));
}

async function utama() {
  const keluar = path.resolve(process.argv[2] ?? path.join(AKAR, 'dist', 'bundel'));
  const alias = Object.fromEntries(DIPAKSA.map((n) => [n, folderPaket(n)]));
  const mulai = Date.now();
  const hasil = await bundle({
    entryPoint: path.join(AKAR, 'src', 'akar.jsx'),
    outDir: keluar,
    enableCaching: false,
    webpackOverride: (konfig) => ({
      ...konfig,
      // Tanpa source map: bundel ini dijalankan Chrome headless, bukan dibaca
      // orang, dan peta sumbernya lebih besar daripada kodenya sendiri.
      devtool: false,
      resolve: { ...konfig.resolve, alias: { ...konfig.resolve?.alias, ...alias } },
    }),
  });
  sisipkanCsp(hasil);
  console.log(JSON.stringify({ bundel: hasil, detik: (Date.now() - mulai) / 1000 }));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  await utama();
}
