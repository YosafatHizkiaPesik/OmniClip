import { describe, expect, it } from 'vitest';
import { periksaAkhir, usulanAkhir } from './akhir.js';
import { terapkanOperasi } from './usulan.js';

const F = 30;
function dok() {
  return {
    versi: 1, id: 'mt', nama: 'x', bahan: { b1: { jenis: 'video', durasi: 20 }, b2: { jenis: 'video', durasi: 20 }, n: { jenis: 'audio', durasi: 30 } },
    penanda: [], ekspor: {},
    kanvas: { lebar: 1080, tinggi: 1920, fps: F, latar: '#000' },
    lajur: [
      { id: 'V', jenis: 'video', nama: 'Video 1', item: [
        { id: 'v1', jenis: 'video', bahan: 'b1', mulai: 0, durasi: 150, potong_awal: 60 },
        { id: 'v2', jenis: 'video', bahan: 'b2', mulai: 150, durasi: 150, potong_awal: 0 },
      ] },
      { id: 'A', jenis: 'audio', nama: 'Suara', item: [
        { id: 'm', jenis: 'audio', bahan: 'n', mulai: 0, durasi: 360, potong_awal: 0 },
      ] },
    ],
    durasi: 360,
  };
}

describe('periksaAkhir', () => {
  it('ekor tanpa gambar dan belum menyambung', () => {
    const c = periksaAkhir(dok());
    expect(c.ekorMati).toBe(2);
    expect(c.menyambung).toBe(false);
    expect(c.baik).toBe(false);
  });
});

describe('usulanAkhir', () => {
  it('potong ekor lalu sambungkan detik pertama di ujung; sesudahnya baik', () => {
    const ops = usulanAkhir(dok());
    expect(ops.map((o) => o.jenis)).toEqual(['potong', 'klip']);
    expect(ops[1]).toMatchObject({ bahan: 'b1', mulai: 300, potong_awal: 60, durasi: 30 });
    const { dokumen } = terapkanOperasi(dok(), ops);
    expect(dokumen.durasi).toBe(330);
    const c = periksaAkhir(dokumen);
    expect([c.ekorMati, c.menyambung, c.baik]).toEqual([0, true, true]);
    expect(usulanAkhir(dokumen)).toEqual([]);
  });
});
