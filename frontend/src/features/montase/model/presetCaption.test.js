import { describe, expect, it } from 'vitest';
import { PRESET_CAPTION, terapkanCaption } from './presetCaption.js';
import { pasangSubtitle } from './suntingan.js';

function dok() {
  return {
    versi: 1, id: 'mt', nama: 'x', durasi: 90, bahan: {}, penanda: [], ekspor: {},
    kanvas: { lebar: 1080, tinggi: 1920, fps: 30, latar: '#000' },
    lajur: [{ id: 'V', jenis: 'video', nama: 'Video 1', item: [] }, { id: 'T', jenis: 'teks', nama: 'Teks', item: [] }],
  };
}
const potongan = [{ mulai: 0, durasi: 30, teks: 'halo semua' }, { mulai: 30, durasi: 30, teks: 'apa kabar' }];

describe('preset caption', () => {
  it('sepuluh preset dengan id unik dan font bawaan', () => {
    expect(PRESET_CAPTION).toHaveLength(10);
    expect(new Set(PRESET_CAPTION.map((p) => p.id)).size).toBe(10);
    expect(PRESET_CAPTION.every((p) => p.gaya.font && p.gaya.letak === 'bawah')).toBe(true);
  });

  it('diterapkan ke seluruh lajur subtitle dan dipakai saat subtitle dibuat ulang', () => {
    const { dokumen, lajurId } = pasangSubtitle(dok(), potongan);
    const d = terapkanCaption(dokumen, lajurId, 'kotak_ungu');
    const lajur = d.lajur.find((l) => l.id === lajurId);
    expect(lajur.gaya_caption).toBe('kotak_ungu');
    expect(lajur.item.every((i) => i.gaya.sorot === 'kotak' && i.gaya.warna_sorot === '#7C3AED')).toBe(true);
    expect(lajur.item.map((i) => i.teks)).toEqual(['halo semua', 'apa kabar']);
    const ulang = pasangSubtitle(d, potongan).dokumen.lajur.find((l) => l.id === lajurId);
    expect(ulang.item[0].gaya.sorot).toBe('kotak');
  });

  it('preset tak dikenal atau lajur terkunci: dokumen tidak berubah', () => {
    const { dokumen, lajurId } = pasangSubtitle(dok(), potongan);
    expect(terapkanCaption(dokumen, lajurId, 'tidak_ada')).toBe(dokumen);
  });
});
