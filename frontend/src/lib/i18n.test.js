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

  it('setiap t("kunci") di kode ada di kamus', () => {
    const src = join(__dirname, '..');
    const hilang = [];
    for (const f of semuaBerkas(src)) {
      const s = readFileSync(f, 'utf8');
      for (const m of s.matchAll(/\bt\(\s*'([a-z_]+\.[a-z0-9_.]+)'/g)) {
        if (!(m[1] in id)) hilang.push(`${f.slice(src.length + 1)}: ${m[1]}`);
      }
    }
    expect(hilang).toEqual([]);
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
