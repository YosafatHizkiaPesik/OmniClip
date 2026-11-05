/**
 * Mengompilasi dan memeriksa satu komponen animasi (JOB-4.md bagian 21).
 *
 * Masukan (stdin):  { "sumber": "<TSX/JSX>" }
 * Keluaran (stdout): { "lolos": true, "js": "<CommonJS>", "ekspor": [...], "peringatan": [...] }
 *                 atau { "lolos": false, "masalah": [...], "peringatan": [...] }
 *
 * Dua lintasan, dan urutannya penting:
 *
 *  1. PEMERIKSAAN pada hasil sucrase yang masih berbentuk modul ES (TypeScript
 *     dan JSX sudah dibuang, `import` belum diubah). Di bentuk ini yang terlihat
 *     hanya kode yang ditulis AI. Kalau diperiksa sesudah diubah ke CommonJS,
 *     fungsi pembantu yang disisipkan sucrase sendiri (`Object.prototype...`)
 *     ikut tertangkap sebagai pelanggaran.
 *  2. KELUARAN: CommonJS untuk `muatKomponen.js`, yang menjalankannya dengan
 *     `require` terbatas.
 *
 * Pemeriksaan ini SATU lapis, bukan satu-satunya: kode yang lolos tetap
 * dijalankan di kotak pasir (pratinjau) dan di halaman ber-CSP (render).
 * Analisis statis tidak bisa menutup semua jalan; yang ia lakukan adalah
 * menolak hampir semua kode yang jelas-jelas tidak boleh, dengan pesan yang
 * bisa dikembalikan ke AI untuk diperbaiki.
 */
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import * as eslintScope from 'eslint-scope';
import * as espree from 'espree';
import { transform } from 'sucrase';
import { jalankan, tulis } from './alat.mjs';

export const BATAS_KARAKTER = 30000;

/** Sama dengan MODUL_DIIZINKAN di frontend/src/features/montase/komposisi/muatKomponen.js. */
export const IMPOR_DIIZINKAN = new Set([
  'react', 'react/jsx-runtime', 'remotion', 'zod', '@remotion/shapes', '@remotion/paths',
  '@remotion/noise', '@remotion/zod-types', '@remotion/transitions',
]);

/**
 * Nama global yang boleh dipakai. Semua yang lain ditolak, termasuk `window`,
 * `document`, `globalThis`, `fetch`, `Date`, `setTimeout`. Daftar yang
 * mengizinkan lebih aman daripada daftar yang melarang: global baru di
 * peramban berikutnya otomatis tertolak.
 */
export const GLOBAL_DIIZINKAN = new Set([
  'Math', 'Array', 'Object', 'Number', 'String', 'Boolean', 'JSON', 'Map', 'Set',
  'WeakMap', 'WeakSet', 'Symbol', 'Intl', 'parseInt', 'parseFloat', 'isNaN',
  'isFinite', 'Infinity', 'NaN', 'undefined', 'console', 'Error', 'TypeError',
  'RangeError',
]);

/** Pintu menuju konstruktor Function dan rantai prototipe. */
const ANGGOTA_DILARANG = new Set([
  'constructor', '__proto__', 'prototype', '__defineGetter__', '__defineSetter__',
  '__lookupGetter__', '__lookupSetter__',
]);

const EKSPOR_KONTRAK = ['skema', 'contohProps', 'durasiBawaan', 'kategori'];

/** Alamat jaringan di teks (http, https, //, ws): bahan masuk lewat props, bukan URL luar. */
const URL_LUAR = /(^|[\s("'=])(https?:|wss?:|\/\/[a-z0-9])/i;
/** Kunci gaya yang menjalankan gerak menurut jam peramban. */
const GAYA_DILARANG = /^(animation|transition)([A-Z].*)?$|^(webkit|Webkit)(Animation|Transition)/;

function jelajah(simpul, kunjungi) {
  if (!simpul || typeof simpul.type !== 'string') return;
  kunjungi(simpul);
  for (const [kunci, nilai] of Object.entries(simpul)) {
    if (kunci === 'parent' || kunci === 'loc' || kunci === 'range') continue;
    if (Array.isArray(nilai)) nilai.forEach((n) => jelajah(n, kunjungi));
    else if (nilai && typeof nilai.type === 'string') jelajah(nilai, kunjungi);
  }
}

function namaAnggota(simpul) {
  if (!simpul.computed && simpul.property.type === 'Identifier') return simpul.property.name;
  if (simpul.property.type === 'Literal') return String(simpul.property.value);
  return null;
}

/** Memeriksa kode modul ES (sesudah TS/JSX dibuang). Mengembalikan daftar masalah. */
export function periksaModul(kodeEsm) {
  const masalah = [];
  const peringatan = [];
  const ekspor = new Set();
  let punyaBawaan = false;

  const ast = espree.parse(kodeEsm, { ecmaVersion: 'latest', sourceType: 'module', loc: true, range: true });
  const baris = (s) => s.loc?.start?.line ?? '?';

  const lingkup = eslintScope.analyze(ast, { ecmaVersion: 2022, sourceType: 'module' });
  const sudah = new Set();
  for (const ref of lingkup.globalScope.through) {
    const nama = ref.identifier.name;
    if (GLOBAL_DIIZINKAN.has(nama) || sudah.has(nama)) continue;
    sudah.add(nama);
    masalah.push(`Baris ${baris(ref.identifier)}: memakai "${nama}", yang tidak tersedia di komponen animasi.`);
  }

  jelajah(ast, (s) => {
    switch (s.type) {
      case 'ImportDeclaration':
        if (!IMPOR_DIIZINKAN.has(s.source.value)) {
          masalah.push(`Baris ${baris(s)}: impor "${s.source.value}" tidak diizinkan. Yang boleh: ${[...IMPOR_DIIZINKAN].join(', ')}.`);
        }
        break;
      case 'ImportExpression':
        masalah.push(`Baris ${baris(s)}: import() dinamis tidak diizinkan.`);
        break;
      case 'ExportAllDeclaration':
        masalah.push(`Baris ${baris(s)}: "export * from" tidak diizinkan.`);
        break;
      case 'ExportDefaultDeclaration':
        punyaBawaan = true;
        break;
      case 'ExportNamedDeclaration':
        if (s.source) masalah.push(`Baris ${baris(s)}: ekspor ulang dari modul lain tidak diizinkan.`);
        if (s.declaration?.declarations) {
          s.declaration.declarations.forEach((d) => d.id?.name && ekspor.add(d.id.name));
        } else if (s.declaration?.id?.name) {
          ekspor.add(s.declaration.id.name);
        }
        (s.specifiers ?? []).forEach((sp) => {
          const nama = sp.exported?.name ?? sp.exported?.value;
          if (nama === 'default') punyaBawaan = true;
          else if (nama) ekspor.add(nama);
        });
        break;
      case 'MemberExpression': {
        const nama = namaAnggota(s);
        if (nama && ANGGOTA_DILARANG.has(nama)) {
          masalah.push(`Baris ${baris(s)}: akses "${nama}" tidak diizinkan.`);
        }
        if (nama === 'random' && s.object.type === 'Identifier' && s.object.name === 'Math') {
          masalah.push(`Baris ${baris(s)}: Math.random membuat hasil render berbeda setiap kali. Pakai random(seed) dari "remotion".`);
        }
        break;
      }
      case 'Literal':
      case 'TemplateElement': {
        const teks = s.type === 'Literal' ? s.value : s.value?.cooked;
        if (typeof teks !== 'string') break;
        if (s.type === 'Literal' && ANGGOTA_DILARANG.has(teks)) {
          masalah.push(`Baris ${baris(s)}: teks "${teks}" tidak diizinkan.`);
        }
        if (URL_LUAR.test(teks)) {
          masalah.push(`Baris ${baris(s)}: alamat luar tidak diizinkan; gambar dan berkas masuk lewat props.`);
        }
        if (/@keyframes/i.test(teks)) {
          masalah.push(`Baris ${baris(s)}: animasi CSS (@keyframes) tidak tertangkap saat render. Pakai useCurrentFrame().`);
        }
        break;
      }
      case 'Property': {
        // style={{ animation: ..., transition: ... }}: gerak CSS berjalan
        // menurut jam peramban, bukan bingkai, jadi render tidak menangkapnya.
        const kunci = s.key?.type === 'Identifier' ? s.key.name : s.key?.value;
        if (typeof kunci === 'string' && GAYA_DILARANG.test(kunci)) {
          masalah.push(`Baris ${baris(s)}: gaya "${kunci}" (animasi/transisi CSS) tidak tertangkap saat render. Pakai useCurrentFrame().`);
        }
        break;
      }
      default:
    }
  });

  if (!punyaBawaan) masalah.push('Tidak ada "export default": komponen animasinya harus menjadi ekspor bawaan.');
  for (const nama of EKSPOR_KONTRAK) {
    if (!ekspor.has(nama)) peringatan.push(`Ekspor "${nama}" tidak ada (kontrak bagian 21).`);
  }
  return { masalah, peringatan, ekspor: [...ekspor] };
}

/** Kompilasi + pemeriksaan. Tidak pernah melempar galat untuk kode yang buruk. */
export function kompilasi(sumber) {
  if (typeof sumber !== 'string' || !sumber.trim()) {
    return { lolos: false, masalah: ['Sumber kosong.'], peringatan: [] };
  }
  if (sumber.length > BATAS_KARAKTER) {
    return { lolos: false, masalah: [`Sumber lebih dari ${BATAS_KARAKTER} karakter.`], peringatan: [] };
  }
  const opsi = { jsxRuntime: 'automatic', production: true, filePath: 'komponen.tsx' };
  let esm;
  let cjs;
  try {
    esm = transform(sumber, { ...opsi, transforms: ['typescript', 'jsx'] }).code;
    cjs = transform(sumber, { ...opsi, transforms: ['typescript', 'jsx', 'imports'] }).code;
  } catch (e) {
    return { lolos: false, masalah: [`Gagal dikompilasi: ${e.message}`], peringatan: [] };
  }
  let hasil;
  try {
    hasil = periksaModul(esm);
  } catch (e) {
    return { lolos: false, masalah: [`Gagal dibaca: ${e.message}`], peringatan: [] };
  }
  if (hasil.masalah.length) {
    return { lolos: false, masalah: hasil.masalah, peringatan: hasil.peringatan };
  }
  return { lolos: true, js: cjs, ekspor: hasil.ekspor, peringatan: hasil.peringatan };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  await jalankan(async (m) => tulis(kompilasi(m.sumber)));
}
