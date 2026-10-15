import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import id from '../locales/id';
import en from '../locales/en';

function semuaBerkas(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return semuaBerkas(p);
    return /\.(jsx?|tsx?)$/.test(n) && !/\.test\./.test(n) ? [p] : [];
  });
}

describe('kamus terjemahan', () => {
  it('kunci id dan en sama persis', () => {
    expect(Object.keys(en).filter((k) => !(k in id))).toEqual([]);
    expect(Object.keys(id).filter((k) => !(k in en))).toEqual([]);
  });

  // `tr` = fungsi `t` yang diimpor langsung, untuk fungsi di luar komponen.
  it('setiap t("kunci") di kode ada di kamus', () => {
    const src = join(__dirname, '..');
    const hilang = [];
    for (const f of semuaBerkas(src)) {
      const s = readFileSync(f, 'utf8');
      for (const m of s.matchAll(/\b(?:t|tr)\(\s*'([a-z_]+\.[a-z0-9_.]+)'/g)) {
        if (!(m[1] in id)) hilang.push(`${f.slice(src.length + 1)}: ${m[1]}`);
      }
    }
    expect(hilang).toEqual([]);
  });

  // Tabel konstanta menyimpan kunci sebagai teks biasa (label: 'gaya_kartu.garis')
  // lalu menerjemahkannya saat dirender. Literal berawalan ruang nama kamus
  // yang dikenal harus ada di kamus, supaya salah ketik tidak tampil mentah.
  it('literal kunci di tabel konstanta ada di kamus', () => {
    const ruang = new Set(Object.keys(id).map((k) => k.split('.')[0]));
    const src = join(__dirname, '..');
    const hilang = [];
    for (const f of semuaBerkas(src)) {
      if (f.includes('/locales/')) continue;
      const s = readFileSync(f, 'utf8');
      for (const m of s.matchAll(/'([a-z_]+)\.([a-z0-9_]+)'/g)) {
        if (/^(webm|mp4|mp3|wav|png|jpe?g|json|srt|txt|jsx?|css|svg)$/.test(m[2])) continue;   // nama berkas
        if (ruang.has(m[1]) && !(`${m[1]}.${m[2]}` in id)) hilang.push(`${f.slice(src.length + 1)}: ${m[1]}.${m[2]}`);
      }
    }
    expect(hilang).toEqual([]);
  });

  // Galat "t is not a function" di beranda (15 Oktober 2026) berasal dari
  // variabel lokal bernama `t` yang menimpa fungsi terjemahan. Di berkas yang
  // memakai useT(), nama `t` hanya boleh untuk fungsi terjemahan itu sendiri
  // (termasuk parameter fungsi pembantu yang menerimanya).
  it('tidak ada variabel lokal bernama t di berkas yang memakai useT', () => {
    const src = join(__dirname, '..');
    const temuan = [];
    const pola = [
      /\b(?:const|let|var) t\b(?! = useT\(\))/,
      /\(t\) =>/,
      /\(t, [^)]*\) =>/,
      /\(\[[^\]]*\bt\b[^\]]*\]\) =>/,
    ];
    for (const f of semuaBerkas(src)) {
      const s = readFileSync(f, 'utf8');
      if (!s.includes('useT()')) continue;
      s.split('\n').forEach((baris, i) => {
        if (/^\s*(\/\/|\*)/.test(baris)) return;
        if (pola.some((p) => p.test(baris))) temuan.push(`${f.slice(src.length + 1)}:${i + 1}: ${baris.trim()}`);
      });
    }
    expect(temuan).toEqual([]);
  });

  it('isian {nama} di en sama dengan di id', () => {
    const isian = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(',');
    const beda = Object.keys(id).filter((k) => k in en && isian(id[k]) !== isian(en[k]));
    expect(beda).toEqual([]);
  });

  it('tanpa tanda pisah panjang', () => {
    expect(Object.entries({ ...id, ...en }).filter(([, v]) => v.includes('—'))).toEqual([]);
  });
});
