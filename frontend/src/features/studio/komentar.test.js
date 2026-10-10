import { describe, it, expect } from 'vitest';
import { komentarUntukRender } from './KomentarPanel';

describe('komentarUntukRender', () => {
  it('membuang komentar kosong dan isian khusus editor', () => {
    const out = komentarUntukRender([
      { id: 'a', posisi: 'pembuka', teks: '  halo  ', suara: '', sintetis: false },
      { id: 'b', posisi: 'sela', t: '4.5', teks: '', suara: '' },
      { id: 'c', posisi: 'sela', t: 4.5, teks: 'di tengah', suara: 'abc', durasi_suara: 2, mode: 'timpa' },
    ]);
    expect(out).toEqual([
      { posisi: 'pembuka', teks: 'halo', suara: '', tampil_teks: true, mode: 'bekukan' },
      { posisi: 'sela', t: 4.5, teks: 'di tengah', suara: 'abc', tampil_teks: false, mode: 'timpa' },
    ]);
  });

  it('pilihan kartu teks orangnya menang atas bawaan', () => {
    const [k] = komentarUntukRender([{ posisi: 'penutup', teks: 'x', suara: 'abc', tampil_teks: true }]);
    expect(k.tampil_teks).toBe(true);
    expect(k.t).toBeUndefined();
  });
});

import { perkiraanNilaiTambah } from './KomentarPanel';

describe('perkiraanNilaiTambah', () => {
  it('tanpa komentar tidak cukup', () => {
    expect(perkiraanNilaiTambah({ daftar: [], sisipan: [], durasiKlip: 30, tambahan: 0 }))
      .toEqual({ persen: 0, cukup: false });
  });
  it('komentar bersuara dua detik sudah cukup', () => {
    const r = perkiraanNilaiTambah({
      daftar: [{ posisi: 'pembuka', teks: 'x', suara: 'abc', durasi_suara: 2 }],
      sisipan: [], durasiKlip: 30, tambahan: 2.3,
    });
    expect(r.cukup).toBe(true);
    expect(r.persen).toBe(7);
  });
});

import { konteksSingkat } from './KomentarPanel';

describe('konteksSingkat', () => {
  it('mengambil kalimat pertama yang pendek', () => {
    expect(konteksSingkat('Windah ditanya soal mabar. Lalu chat meledek.')).toBe('Windah ditanya soal mabar');
  });
  it('memotong di kata, bukan di tengah kata', () => {
    const r = konteksSingkat('kata '.repeat(40));
    expect(r.length).toBeLessThanOrEqual(70);
    expect(r.endsWith('...')).toBe(true);
  });
  it('kosong tetap kosong', () => { expect(konteksSingkat('')).toBe(''); });
});

import { tagPenutur } from './KomentarPanel';

describe('tagPenutur', () => {
  const subs = [
    { start: 0.5, end: 2, text: 'a', speaker: 0 },
    { start: 2.5, end: 4, text: 'b', speaker: 1 },
    { start: 4.5, end: 6, text: 'c', speaker: 0 },
    { start: 30, end: 31, text: 'd', speaker: 1 },
  ];
  it('nama muncul saat ganti penutur, tidak lebih sering dari 15 detik', () => {
    const t = tagPenutur(subs, { 0: 'Windah', 1: 'Ilham' });
    expect(t.map((x) => [x.teks, x.t])).toEqual([['Windah', 0.5], ['Ilham', 2.5], ['Ilham', 30]]);
    expect(t.every((x) => x.jenis === 'teks' && x.asal === 'penutur')).toBe(true);
  });
  it('penutur tanpa nama dilewati', () => {
    expect(tagPenutur(subs, { 1: 'Ilham' }).map((x) => x.teks)).toEqual(['Ilham', 'Ilham']);
  });
});
