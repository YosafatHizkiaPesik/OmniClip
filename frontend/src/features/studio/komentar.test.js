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
